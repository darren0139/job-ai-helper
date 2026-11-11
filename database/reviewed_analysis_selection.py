"""Authorized application-local selection for reviewed exclusion analyses."""
from contextlib import closing
from copy import deepcopy
import hashlib
import json
import os
import uuid

from analysis_stability.requirement_presentation import score_value
from analysis_stability.reviewed_jd_exclusions import (
    REVIEWED_ANALYSIS_CONTRACT, REVIEWED_HISTORY, REVIEWED_SELECTED,
    project_requirement_scope, requirement_scope_sha256,
    reviewed_exclusions_candidate, verify_effective_analysis,
)
from analysis_stability.stable_evidence_scoring import (
    canonicalise_requirements, compute_deterministic_alignment, stable_analysis_input_fingerprint,
)
from database import analysis_cache_manager as cache
from rag.jd_identity import build_job_identity
from tailoring.document_grounded_analysis import (
    analyze_actual_resume_against_jd, seal_document_report, validate_document_report,
)
from tailoring.job_match_ab_analysis import current_ab_identity
from tailoring.phase9e_blueprint_selection import fingerprint_value

FLAG = "JOB_AI_HELPER_REVIEW419_EXCLUSIONS"
MODEL = "deterministic-review419-saved-document-v1"


def enabled():
    return os.environ.get(FLAG) == "1"


def _source_and_ordinary(connection, application_id):
    """Read the trusted linked version and ordinary receipt in one transaction."""
    app = connection.execute("SELECT report_json FROM applications WHERE id=?", (application_id,)).fetchone()
    link = connection.execute("""
        SELECT l.job_description_id, l.source_version_id, l.linked_at, l.updated_at,
               j.canonical_jd_id, v.raw_text, v.jd_profile_json
        FROM application_job_links l JOIN job_descriptions j ON j.id=l.job_description_id
        JOIN job_description_versions v ON v.job_description_id=l.job_description_id
            AND v.source_version_id=l.source_version_id
        WHERE l.application_id=?
    """, (application_id,)).fetchall()
    if not app or not app["report_json"] or len(link) != 1:
        raise ValueError("A saved ordinary analysis and unique original JD link are required.")
    source = dict(link[0])
    raw = source.pop("raw_text")
    profile = json.loads(source.pop("jd_profile_json"))
    title = profile.get("job_title") or profile.get("title")
    company = profile.get("company") or profile.get("company_name")
    if not title or not company:
        raise ValueError("The linked JD profile identity is incomplete.")
    identity = build_job_identity(company=company, title=title, location=profile.get("location") or "",
                                  raw_jd_text=raw)
    if (identity.source_version_id != source["source_version_id"]
            or identity.canonical_jd_id != source["canonical_jd_id"]):
        raise ValueError("The linked JD identity could not be authenticated.")
    ordinary = json.loads(app["report_json"])
    meta = ordinary.get("meta") or {}
    analysis_id = (meta.get("analysis_cache") or {}).get("analysis_id")
    frozen = connection.execute("""
        SELECT * FROM application_analysis_versions
        WHERE application_id=? AND analysis_id=? AND status='active'
    """, (application_id, analysis_id)).fetchone()
    if (not frozen or cache._is_reviewed_snapshot(cache._row_to_dict(frozen))
            or cache._row_to_dict(frozen)["report"] != ordinary
            or ordinary.get("raw_jd_text") != raw
            or frozen["cache_version"] != cache.ANALYSIS_CACHE_VERSION
            or frozen["pipeline_contract_version"] != cache.ANALYSIS_PIPELINE_CONTRACT_VERSION):
        raise ValueError("The current ordinary receipt does not match the linked original JD.")
    if ((meta.get("jd_user_inputs") or {}).get("preferred_requirement_overrides")
            or ordinary["stable_analysis"].get("jd_user_override_policy_version")):
        raise ValueError("Reviewed exclusions cannot be combined with local preferred overrides.")
    authority = validate_document_report(ordinary)
    if score_value(ordinary["stable_analysis"]) is None or authority["identity"] != current_ab_identity(raw):
        raise ValueError("A current publishable ordinary document receipt is required.")
    rows = canonicalise_requirements(profile, raw)["requirements"]
    with reviewed_exclusions_candidate():
        _, scope = project_requirement_scope(raw, rows)
    if scope is None:
        raise ValueError("This exact linked JD is outside the reviewed exclusions.")
    if requirement_scope_sha256(ordinary["stable_analysis"]["canonical_requirements"]) != scope["original_requirement_scope_sha256"]:
        raise ValueError("The saved ordinary requirement scope differs from the approved original.")
    source.update(raw_jd_sha256=hashlib.sha256(raw.encode()).hexdigest(),
                  jd_profile_sha256=fingerprint_value(profile))
    binding = {"version": REVIEWED_ANALYSIS_CONTRACT, "application_id": application_id,
               "source": source, "ordinary_analysis_id": analysis_id,
               "ordinary_report_sha256": fingerprint_value(ordinary), "effective_requirement_scope": scope}
    return raw, profile, rows, ordinary, binding


def _selected(connection, application_id):
    rows = connection.execute("""
        SELECT * FROM application_analysis_versions WHERE application_id=? AND status=?
    """, (application_id, REVIEWED_SELECTED)).fetchall()
    if len(rows) > 1:
        raise ValueError("Conflicting reviewed selections require explicit rollback.")
    return rows[0] if rows else None


def _verified_key(report, raw, ordinary, binding):
    stable = report["stable_analysis"]
    baseline = ordinary["stable_analysis"]
    authority = validate_document_report(report)
    scope = verify_effective_analysis(raw, stable, require_active=True)
    if (scope != binding["effective_requirement_scope"]
            or authority["identity"] != current_ab_identity(raw)
            or report["raw_jd_text"] != raw
            or report["raw_resume_text"] != ordinary["raw_resume_text"]
            or report["resume_profile"] != ordinary["resume_profile"]):
        raise ValueError("Reviewed report source, policy or applicant-evidence authority changed.")
    excluded = set(scope["excluded_requirement_ids"])
    surviving = [r for r in baseline["canonical_requirements"] if r["requirement_id"] not in excluded]
    if (len(baseline["canonical_requirements"]) - len(surviving) != len(excluded)
            or stable["canonical_requirements"] != surviving
            or baseline["credited_requirement_count"] != stable["credited_requirement_count"]):
        raise ValueError("Reviewed analysis changed the surviving applicant evidence or weights.")
    expected = compute_deterministic_alignment(surviving)
    if score_value(stable) is None or any(stable.get(k) != v for k, v in expected.items()):
        raise ValueError("Reviewed score does not reproduce from unchanged surviving evidence.")
    if stable["input_fingerprint"] != stable_analysis_input_fingerprint(
        report["raw_resume_text"], raw, baseline["capability_taxonomy_version"],
        baseline["technology_registry_version"], stable["scoring_version"], scope
    ):
        raise ValueError("Reviewed native fingerprint is inconsistent.")
    return cache.build_analysis_input_fingerprint(resume_text=report["raw_resume_text"], jd_text=raw,
        degree="", actual_page_count=None, model_id=MODEL, retrieval_config={"mode":"lexical"},
        pipeline_contract_version=REVIEWED_ANALYSIS_CONTRACT)


def _state(connection, application_id):
    raw, profile, rows, ordinary, binding = _source_and_ordinary(connection, application_id)
    selected = _selected(connection, application_id)
    selected_id = selected["analysis_id"] if selected else None
    token = fingerprint_value([binding, selected_id])
    return raw, profile, rows, ordinary, binding, selected, token


def get_reviewed_selection(application_id):
    """Current-facing only. Historical rows are available from the version list."""
    if not enabled():
        return None
    with closing(cache._connect()) as connection, connection:
        connection.execute("BEGIN")
        raw, _, _, ordinary, binding, selected, token = _state(connection, int(application_id))
        result = {"token": token, "selected": None}
        if selected is None:
            return result
        snapshot = cache._row_to_dict(selected)
        report = snapshot["report"]
        try:
            with reviewed_exclusions_candidate():
                key = _verified_key(report, raw, ordinary, binding)
            if (snapshot["pipeline_contract_version"] != REVIEWED_ANALYSIS_CONTRACT
                    or snapshot["cache_version"] != cache.ANALYSIS_CACHE_VERSION
                    or snapshot["analysis_model"] != MODEL or snapshot["input_fingerprint"] != key
                    or report["meta"].get("review419_selection") != binding):
                raise ValueError("Reviewed selection is stale.")
        except (ValueError, KeyError, TypeError):
            result["stale"] = True
        else:
            if enabled():
                result["selected"] = snapshot
        return result


def save_and_select_reviewed_analysis(application_id, *, expected_token):
    """Explicit opt-in. Build the native result inside the serialized write boundary."""
    if not enabled():
        raise ValueError("Reviewed exclusions are off.")
    app_id = int(application_id)
    with closing(cache._connect()) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        raw, profile, rows, ordinary, binding, selected, token = _state(connection, app_id)
        if token != expected_token:
            raise ValueError("Application source or selection changed. Reload before retrying.")
        with reviewed_exclusions_candidate():
            report = analyze_actual_resume_against_jd(
                resume_text=ordinary["raw_resume_text"], resume_profile=ordinary["resume_profile"],
                jd_text=raw, jd_profile=profile, canonical_requirements=rows)
            report["meta"] = {"document_analysis": report.pop("document_analysis"), "review419_selection": binding}
            seal_document_report(report)
            key = _verified_key(report, raw, ordinary, binding)
        if not enabled():
            raise ValueError("Reviewed exclusions were disabled before the save.")
        now = cache._now()
        analysis_id = uuid.uuid4().hex
        if selected:
            connection.execute("""UPDATE application_analysis_versions SET status=?,updated_at=?
                WHERE application_id=? AND analysis_id=? AND status=?""",
                (REVIEWED_HISTORY, now, app_id, selected["analysis_id"], REVIEWED_SELECTED))
        connection.execute("""INSERT INTO application_analysis_versions
            (application_id,analysis_id,input_fingerprint,cache_version,pipeline_contract_version,
             analysis_model,resume_filename,report_json,status,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)""", (app_id, analysis_id, key, cache.ANALYSIS_CACHE_VERSION,
            REVIEWED_ANALYSIS_CONTRACT, MODEL, "", json.dumps(report, ensure_ascii=False), REVIEWED_SELECTED, now, now))
        return analysis_id


def restore_ordinary_analysis(application_id, *, expected_token):
    """Retire only the scoped selection. The ordinary report never moved."""
    app_id = int(application_id)
    with closing(cache._connect()) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        *_, selected, token = _state(connection, app_id)
        if token != expected_token or selected is None:
            raise ValueError("Application source or selection changed. Reload before retrying.")
        connection.execute("""UPDATE application_analysis_versions SET status=?, updated_at=?
            WHERE application_id=? AND analysis_id=? AND status=?""",
            (REVIEWED_HISTORY, cache._now(), app_id, selected["analysis_id"], REVIEWED_SELECTED))

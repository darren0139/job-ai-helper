"""Bounded local plans and explicit resumable native JD analysis, never Analyze All."""

from taxonomy_discovery.offline_execution import offline_execution
from collections import Counter, defaultdict
from contextlib import closing
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from database import job_match_manager as snapshots, jd_library_manager as library
from database.user_profile_manager import get_all_evidence_items_for_snapshot
from job_discovery.matching import (_default_extract_jd_profile, _default_stable_builder,
    _identity, build_profile_evidence_context, current_match_versions, summarize_stable_match)
from taxonomy_discovery.corpus_coverage import corpus_coverage, _coverage_plan, _evidence_context, _profile_valid
from taxonomy_discovery.regression_corpus import duplicate_credit_violations
from tailoring.phase9b_role_family import suggest_role_family

PLAN_VERSION = "tqd3-bounded-model-plan-v1"
MAX_BATCH = 50


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def _limit(value):
    if type(value) is not int or not 1 <= value <= MAX_BATCH:
        raise ValueError("Batch limit must be an integer between 1 and 50")
    return value


def classify_role(job):
    """Title establishes occupation; JD tokens can qualify an otherwise ambiguous title."""
    title = str(job.get("title") or "").lower()
    jd = str(job.get("description") or "").lower()
    excluded = r"\b(biolog|chemist|chemical|civil|mechanical|electrical|sales|administrat|accountant|recruit|product manager|product management|nurse|physician|marketing|finance|business analyst)"
    if re.search(excluded, title):
        return "non_software", "Title identifies a non-software occupation"
    roles = (
        ("backend", r"back[ -]?end"), ("frontend", r"front[ -]?end"),
        ("fullstack", r"full[ -]?stack"), ("cloud_devops", r"devops|site reliability|cloud engineer|\bsre\b"),
        ("data_engineering", r"data engineer|analytics engineer"),
        ("ai_ml", r"machine learning|\bml engineer|\bai engineer|data scientist"),
        ("security", r"cybersecurity|security engineer|application security"),
        ("embedded_systems", r"embedded|firmware"), ("mobile", r"android|ios developer|mobile.*(engineer|developer)"),
        ("qa_test", r"software test|test automation|\bsdet\b|qa engineer"),
        ("infrastructure_platform", r"platform engineer|infrastructure engineer"),
        ("systems_low_level", r"systems programmer|kernel|low.level|compiler engineer"),
        ("software_engineering", r"software (engineer|developer)|application developer|programmer"),
    )
    for family, pattern in roles:
        if re.search(pattern, title):
            return family, "Explicit software role in title: " + family
    if re.search(r"\b(engineer|developer|technical)\b", title) and re.search(
            r"\b(software development|programming|python|javascript|typescript|kubernetes|coding|backend|frontend)\b", jd):
        return "other_technical", "Technical title with explicit software implementation in JD"
    return "ambiguous", "No conservative software occupation signal; human review required"


def _jobs(db_path):
    path = Path(db_path or snapshots.DB_PATH).resolve()
    with closing(sqlite3.connect(path.as_uri()+"?mode=ro", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute("SELECT * FROM discovered_jobs ORDER BY id")]


def _jd_hash(job):
    # Native discovered content_hash also includes posting metadata. Deduplicate
    # exact JD content independently; retain native hash for snapshot currentness.
    return hashlib.sha256(str(job.get("description") or "").encode("utf-8")).hexdigest()


def _context(job_id, db_path):
    path = Path(db_path or snapshots.DB_PATH).resolve()
    with closing(sqlite3.connect(path.as_uri()+"?mode=ro", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM job_match_snapshots WHERE discovered_job_id=? ORDER BY id DESC LIMIT 1", (job_id,)).fetchone()
    if row:
        context = _evidence_context(snapshots._decode_row(dict(row)))
        if context is None:
            raise ValueError("Historical evidence unavailable/invalid; cannot reconstruct")
        return context
    evidence = get_all_evidence_items_for_snapshot(read_only=True, db_path=path)
    if not evidence:
        raise ValueError("Canonical candidate evidence unavailable")
    return build_profile_evidence_context(evidence)


def model_plan(*, db_path=None, software_only=True, limit=25):
    _limit(limit)
    coverage = corpus_coverage(db_path=db_path)
    states = {r["discovered_job_id"]: r for r in coverage["jobs"]}
    classified, eligible, excluded = [], [], Counter()
    for job in _jobs(db_path):
        family, reason = classify_role(job)
        state = states[job["id"]]
        row = {"discovered_job_id": job["id"], "title":job.get("title"), "company":job.get("company"),
            "lifecycle_status":job.get("lifecycle_status"), "role_family":family,
            "current_jd_content_hash":job["content_hash"], "classification_reason":reason,
            "exact_jd_text_hash":_jd_hash(job),
            "compatible_jd_extraction":state["reusable_jd_profile_available"],
            "evidence_source":deepcopy(state["evidence_source"]),
            "current_snapshot":state["analysis_current"] and not state["snapshot_hash_mismatch"],
            "estimated_jd_analysis_tasks":int(not state["reusable_jd_profile_available"])}
        row["native_role_family_hint"] = suggest_role_family({"jd_profile":{"job_title":job.get("title")}})
        classified.append(row)
        if software_only and family in {"ambiguous", "non_software"}:
            excluded[family] += 1
        elif not state["model_required"]:
            excluded["current_or_cached_or_blocked"] += 1
        elif not job.get("title") or not job.get("company"):
            excluded["missing_native_library_identity"] += 1
        else:
            try:
                row["evidence_fingerprint"] = _context(job["id"], db_path)["evidence_fingerprint"]
                eligible.append(row)
            except (ValueError, TypeError, sqlite3.Error):
                excluded["missing_or_invalid_evidence"] += 1
    groups = defaultdict(list)
    for row in eligible:
        groups[row["exact_jd_text_hash"]].append(row)
    candidates, duplicates = [], []
    for content_hash, group in sorted(groups.items()):
        group.sort(key=lambda r:(r["lifecycle_status"] != "active", r["discovered_job_id"]))
        candidates.append(group[0])
        if len(group) > 1:
            duplicates.append({"content_hash":content_hash, "job_ids":[r["discovered_job_id"] for r in group],
                "canonical_job_id":group[0]["discovered_job_id"]})
    selected, families, companies = [], Counter(), Counter()
    while candidates and len(selected) < limit:
        # Underrepresented occupations/employers first; active wins equal diversity.
        chosen = min(candidates, key=lambda r:(families[r["role_family"]], companies[str(r["company"]).casefold()],
            r["lifecycle_status"] != "active", r["discovered_job_id"]))
        candidates.remove(chosen)
        chosen["selection_reason"] = "Deterministic least represented role/company; active wins ties"
        selected.append(chosen)
        families[chosen["role_family"]] += 1
        companies[str(chosen["company"]).casefold()] += 1
    duplicate_count = sum(len(g["job_ids"])-1 for g in duplicates)
    excluded["exact_duplicate"] = duplicate_count
    result = {"plan_version":PLAN_VERSION, "current_versions":coverage["current_versions"],
        "limit":limit, "software_only":software_only, "jobs":selected,
        "summary":{"discovered_jobs":len(classified), "software_eligible_jobs":sum(r["role_family"] not in {"ambiguous","non_software"} for r in classified),
            "ambiguous_jobs":sum(r["role_family"]=="ambiguous" for r in classified),
            "non_software_jobs":sum(r["role_family"]=="non_software" for r in classified),
            "total_candidate_jobs":len(eligible), "distinct_jd_hashes":len({r["exact_jd_text_hash"] for r in classified}),
            "eligible_distinct_jd_hashes":len(groups), "exact_duplicates_excluded":duplicate_count,
            "eligible_lifecycle_counts":dict(Counter(r["lifecycle_status"] for r in eligible)),
            "role_family_counts":dict(Counter(r["role_family"] for r in classified)),
            "company_counts":dict(Counter(r["company"] for r in classified)),
            "planned_jobs":len(selected), "selected_role_families":dict(families),
            "selected_companies":dict(Counter(r["company"] for r in selected)),
            "selected_lifecycle_counts":dict(Counter(r["lifecycle_status"] for r in selected)),
            "estimated_jd_analysis_tasks":sum(r["estimated_jd_analysis_tasks"] for r in selected), "exclusion_reasons":dict(excluded)},
        "exact_duplicate_groups":duplicates, "read_only":True}
    result["plan_fingerprint"] = fingerprint(result)
    return result


def execution_preview(plan, *, db_path=None, limit=25):
    _limit(limit)
    material = {k:v for k,v in plan.items() if k != "plan_fingerprint"}
    if plan.get("plan_version") != PLAN_VERSION or fingerprint(material) != plan.get("plan_fingerprint"):
        raise ValueError("Invalid or edited plan fingerprint")
    if plan["current_versions"] != current_match_versions():
        raise ValueError("Plan resolver versions stale; generate a new plan")
    if len(plan["jobs"]) > _limit(plan["limit"]) or len({r["discovered_job_id"] for r in plan["jobs"]}) != len(plan["jobs"]):
        raise ValueError("Plan selection invalid")
    coverage = corpus_coverage(db_path=db_path)
    rows = {r["discovered_job_id"]:r for r in coverage["jobs"]}
    jobs = {r["id"]:r for r in _jobs(db_path)}
    evaluated = []
    for selected in plan["jobs"]:
        jid = selected["discovered_job_id"]
        current, job = rows.get(jid), jobs.get(jid)
        status = "ready"
        if not current or current["current_jd_content_hash"] != selected["current_jd_content_hash"] or _jd_hash(job) != selected["exact_jd_text_hash"]:
            status = "stale_plan"
        else:
            try:
                if job.get("title") != selected["title"] or job.get("company") != selected["company"]:
                    status = "stale_plan"
                elif _context(jid, db_path)["evidence_fingerprint"] != selected["evidence_fingerprint"]:
                    status = "stale_plan"
                elif current["analysis_current"] and not current["snapshot_hash_mismatch"]:
                    status = "already_completed"
                elif current["status"] in {"other_blocker","missing_or_invalid_jd"}:
                    status = "blocked"
                elif plan["software_only"] and classify_role(job)[0] in {"ambiguous","non_software"}:
                    status = "stale_plan"
            except (ValueError, TypeError, sqlite3.Error):
                status = "blocked"
        evaluated.append({**selected, "execution_status":status,
            "estimated_jd_analysis_tasks":int(status=="ready" and not current["reusable_jd_profile_available"])})
    ready = [r for r in evaluated if r["execution_status"]=="ready"][:limit]
    return {"jobs_in_plan":len(evaluated), "valid_current_jobs":sum(r["execution_status"] in {"ready","already_completed"} for r in evaluated),
        "already_completed":sum(r["execution_status"]=="already_completed" for r in evaluated),
        "stale_plan_jobs":sum(r["execution_status"]=="stale_plan" for r in evaluated),
        "jobs_remaining":sum(r["execution_status"]=="ready" for r in evaluated), "requested_batch_limit":limit,
        "maximum_jd_analysis_tasks":sum(r["estimated_jd_analysis_tasks"] for r in ready), "jobs":evaluated}


def model_run(plan, *, db_path=None, limit=25, execute=False, extractor=None, receipt_callback=None):
    if execute is not True:
        raise ValueError("Model execution requires explicit execute=True / --execute")
    preview = execution_preview(plan, db_path=db_path, limit=limit)
    if receipt_callback:
        receipt_callback({"execution_preview":preview})  # Before any paid request.
    before = corpus_coverage(db_path=db_path)
    result = {"plan_fingerprint":plan["plan_fingerprint"], "started_at":datetime.now(timezone.utc).isoformat(),
        "ended_at":None, "execution_preview":preview, "jobs":[], "jobs_attempted":0, "jobs_succeeded":0,
        "jobs_failed":0, "jobs_skipped":0, "already_completed":0, "stale_plan_jobs":0,
        "model_analysis_tasks_attempted":0, "new_snapshot_count":0}
    extract = extractor or _default_extract_jd_profile
    for selected in preview["jobs"]:
        jid = selected["discovered_job_id"]
        record = {"discovered_job_id":jid}
        # Recheck every job, including evidence and resolver versions, immediately before spend.
        current = execution_preview(plan, db_path=db_path, limit=limit)
        row = next(r for r in current["jobs"] if r["discovered_job_id"]==jid)
        status = row["execution_status"]
        if status != "ready" or result["jobs_attempted"] >= limit:
            record["status"] = status if status != "ready" else "batch_limit"
            result["jobs_skipped"] += 1
            if status in {"already_completed", "stale_plan"}:
                result["already_completed" if status=="already_completed" else "stale_plan_jobs"] += 1
        else:
            result["jobs_attempted"] += 1
            try:
                job = next(r for r in _jobs(db_path) if r["id"]==jid)
                context = _context(jid, db_path)
                _, reusable = _coverage_plan(db_path=db_path)
                cached = reusable.get(jid)
                if cached:
                    profile = cached["jd_profile"]
                    record["jd_cache_identity"] = cached["provenance"]["jd_profile_source"]
                else:
                    if result["model_analysis_tasks_attempted"] >= preview["maximum_jd_analysis_tasks"]:
                        raise ValueError("Cached inputs changed; reviewed model budget exhausted. Generate a fresh preview.")
                    result["model_analysis_tasks_attempted"] += 1
                    # One native JD-analysis task. No outer retry; native extractor owns its bounded policy.
                    profile = extract(job["description"])
                    if not _profile_valid(profile):
                        raise ValueError("Native extractor returned invalid JD profile")
                    library.init_jd_library(db_path=db_path)
                    record["jd_cache_identity"] = library.save_job_description_to_library(raw_text=job["description"],
                        jd_profile=profile, title=job["title"], company=job["company"],
                        location=job.get("location") or "", source_url=job.get("source_url") or "", db_path=db_path)
                    # Extraction is committed before matching: interruption cannot require a second paid extraction.
                    _, persisted = _coverage_plan(db_path=db_path)
                    if jid not in persisted:
                        raise ValueError("Persisted extraction conflicts or inputs changed; review before retry")
                    profile = persisted[jid]["jd_profile"]
                latest = execution_preview(plan, db_path=db_path, limit=limit)
                if next(r for r in latest["jobs"] if r["discovered_job_id"]==jid)["execution_status"] != "ready":
                    raise ValueError("Inputs changed during extraction; snapshot not saved")
                with offline_execution('Snapshot scoring forbids network'):
                    stable = _default_stable_builder(raw_jd_text=job["description"], jd_profile=profile, context=context)
                if duplicate_credit_violations(stable, context):
                    raise ValueError("Duplicate/evidence invariant failed")
                final_preview = execution_preview(plan, db_path=db_path, limit=limit)
                if next(r for r in final_preview["jobs"] if r["discovered_job_id"]==jid)["execution_status"] != "ready":
                    raise ValueError("Inputs changed during matching; snapshot not saved")
                summary = summarize_stable_match(stable)
                summary["corpus_expansion_provenance"] = {"plan_fingerprint":plan["plan_fingerprint"],
                    "jd_cache_identity":record["jd_cache_identity"], "job_content_hash":job["content_hash"],
                    "exact_jd_text_hash":selected["exact_jd_text_hash"], "evidence_source":selected["evidence_source"],
                    "evidence_fingerprint":context["evidence_fingerprint"]}
                saved = snapshots.save_job_match_snapshot(**_identity(job,context,plan["current_versions"]),
                    jd_profile=profile,evidence_snapshot=context["evidence_items"],stable_analysis=stable,summary=summary,db_path=db_path)
                record.update(status="succeeded", snapshot_id=saved["id"])
                result["jobs_succeeded"] += 1
                result["new_snapshot_count"] += 1
            except Exception as exc:
                record.update(status="failed", reason=str(exc))
                result["jobs_failed"] += 1
        result["jobs"].append(record)
        if receipt_callback:
            receipt_callback(deepcopy(result))
    after = corpus_coverage(db_path=db_path)
    result["ended_at"] = datetime.now(timezone.utc).isoformat()
    result["growth"] = {"replayable_distinct_jobs_before":before["replayable_jobs_before"],
        "replayable_distinct_jobs_after":after["replayable_jobs_before"],
        "newly_replayable_distinct_jobs":after["replayable_jobs_before"]-before["replayable_jobs_before"],
        "new_snapshot_count":result["new_snapshot_count"],
        "successful_role_families":dict(Counter(r["role_family"] for r in preview["jobs"] if any(j["discovered_job_id"]==r["discovered_job_id"] and j["status"]=="succeeded" for j in result["jobs"]))),
        "successful_companies":dict(Counter(r["company"] for r in preview["jobs"] if any(j["discovered_job_id"]==r["discovered_job_id"] and j["status"]=="succeeded" for j in result["jobs"]))),
        "successful_lifecycle_counts":dict(Counter(r["lifecycle_status"] for r in preview["jobs"] if any(j["discovered_job_id"]==r["discovered_job_id"] and j["status"]=="succeeded" for j in result["jobs"])))}
    if receipt_callback:
        receipt_callback(deepcopy(result))
    return result

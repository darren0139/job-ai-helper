"""Operational adapters over the existing corpus/TQ-D3 contracts.

No resolver, consolidation, scorer, research interpreter, or publication engine
is implemented here. Audit and tranche operations are strictly read-only.
"""
from __future__ import annotations

from collections import Counter
from contextlib import ExitStack
from copy import deepcopy
from datetime import datetime, timezone
import csv
import hashlib
import io
import json
import re
from pathlib import Path
import subprocess
import zipfile

from database import taxonomy_discovery_review_manager as store
from job_discovery.matching import current_match_versions
from taxonomy_discovery import bulk_candidate_operations as bulk
from taxonomy_discovery import corpus_gap_resolution as gaps
from taxonomy_discovery import governed_publication as publication
from taxonomy_discovery import governed_research as research
from taxonomy_discovery.corpus_expansion import fingerprint
from taxonomy_discovery.regression_corpus import export_saved_corpus, replay_current_corpus
from taxonomy_discovery.technology_registry import REGISTRY_PATH, get_default_registry, normalise
from tailoring.capability_taxonomy import TAXONOMY_PATH, get_default_taxonomy
from taxonomy_discovery.offline_execution import offline_execution, research_execution, network_blocker

AUDIT_SCHEMA_VERSION = "taxonomy-maintenance-audit-v1"
REPO_ROOT = Path(__file__).resolve().parents[1]
CAPABILITY_GAP = "ACTUAL_CAPABILITY_TAXONOMY_GAP"
IDENTITY_GAP = "TECHNOLOGY_IDENTITY_GAP"
RELATIONSHIP_GAP = "CONTEXTUAL_RELATIONSHIP_GAP"
EVIDENCE_PROBLEM = "EVIDENCE_POLICY_PROBLEM"
PARSING_PROBLEM = "JD_PARSING_CANONICALISATION_PROBLEM"
NOISE = "NON_REQUIREMENT_NOISE"
MANUAL = "MANUAL_REVIEW"
RESEARCH_READY = "RESEARCH_READY"
NEEDS_DECOMPOSITION = "NEEDS_DECOMPOSITION"
REVIEW_FIX_LAYER = "REVIEW_FIX_LAYER"
FIX_LAYERS = (CAPABILITY_GAP, IDENTITY_GAP, RELATIONSHIP_GAP,
              EVIDENCE_PROBLEM, PARSING_PROBLEM, NOISE, MANUAL)
ROUTE_LAYERS = {
    "possible_new_capability": CAPABILITY_GAP,
    "technology_identity_missing": IDENTITY_GAP,
    "technology_relationship_missing": RELATIONSHIP_GAP,
    "needs_decomposition": PARSING_PROBLEM,
    "noise_or_non_capability": NOISE,
    "local_resolver_issue": PARSING_PROBLEM,
    "phrase_or_alias_gap": PARSING_PROBLEM,
    "manual_review": MANUAL,
}


def production_identity():
    """Reuse production versions/fingerprints; schema version is audit-only."""
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
                          capture_output=True, text=True, check=True).stdout.strip()
    from taxonomy_discovery.source_authority import load_source_authority_registry
    return {
        "git_head": head, "audit_schema_version": AUDIT_SCHEMA_VERSION,
        **current_match_versions(),
        "taxonomy_fingerprint": fingerprint(get_default_taxonomy().capabilities),
        "registry_fingerprint": fingerprint(get_default_registry().entries),
        "taxonomy_bytes_sha256": hashlib.sha256(Path(TAXONOMY_PATH).read_bytes()).hexdigest(),
        "registry_bytes_sha256": hashlib.sha256(Path(REGISTRY_PATH).read_bytes()).hexdigest(),
        "source_authority_fingerprint": fingerprint(load_source_authority_registry()),
        "implementation_fingerprint": fingerprint({name: hashlib.sha256(
            (REPO_ROOT / name).read_bytes()).hexdigest() for name in (
                "analysis_stability/stable_evidence_scoring.py",
                "tailoring/production_requirement_resolver.py",
                "tailoring/capability_taxonomy.py", "job_discovery/matching.py",
                "taxonomy_discovery/corpus_gap_resolution.py",
                "taxonomy_discovery/regression_corpus.py",
                "taxonomy_discovery/research_readiness.py",
                "taxonomy_discovery/governed_research.py",
                "taxonomy_discovery/capability_sufficiency.py",
                "taxonomy_discovery/source_authority.py",
                "taxonomy_discovery/offline_execution.py",
                "taxonomy_discovery/maintenance_service.py",
            )}),
    }


def _seal(value, key):
    value[key] = fingerprint({k: v for k, v in value.items() if k != key})
    return value


def _intact(value, key):
    if value.get(key) != fingerprint({k: v for k, v in value.items() if k != key}):
        raise ValueError("Maintenance artifact edited or incomplete")


def _related(candidate, saved):
    concept = normalise(candidate.get("concept_key", ""))
    return [row for row in saved if
            row["result"].get("candidate", {}).get("candidate_id") == candidate.get("candidate_id")
            or normalise(row["result"].get("candidate", {}).get("concept_key", "")) == concept]


def capability_boundary(candidate, readiness=None):
    """Conservative maintenance gate; never split or reclassify production rows.

    Native decomposition/eligibility/atomicity remain authoritative. Long prose
    is held for review even when those contracts cannot safely split it. Short
    coherent noun concepts (including 'data analysis and insights') can proceed.
    """
    from analysis_stability.stable_evidence_scoring import classify_jd_statement_semantics, _split_non_preference_clause
    from taxonomy_discovery.research_atomicity import candidate_atomicity
    from taxonomy_discovery.research_readiness import _capability_requires_decomposition
    text = str(candidate.get("concept_key") or candidate.get("normalized_cluster") or "")
    semantic = classify_jd_statement_semantics(text)
    if not semantic["score_eligible"] or re.search(r"^(?:strong|excellent|good|effective)\b.*\bskills?$", text, re.I):
        return REVIEW_FIX_LAYER, "Candidate eligibility / generic skill boundary requires fix-layer review"
    atomicity = candidate_atomicity(candidate)
    state = (readiness or {}).get("research_readiness")
    if (state == "needs_decomposition" or atomicity["atomicity_status"] == "compound_requires_decomposition"
            or _capability_requires_decomposition(candidate, atomicity)
            or len(_split_non_preference_clause(text, "required", text)) > 1):
        return NEEDS_DECOMPOSITION, "Native decomposition or research atomicity requires review"
    joined = re.split(r"\s+(?:and|&)\s+", text, flags=re.I)
    if len(joined) > 1 and sum(len(part.split()) >= 2 for part in joined) > 1:
        return NEEDS_DECOMPOSITION, "Multiple named scopes; review decomposition before capability research"
    if len(text.split()) > 7:
        return NEEDS_DECOMPOSITION, "Sentence-sized scope; normalize into bounded concepts before research"
    if state in {"blocked_noise_or_insufficient", "manual_review"}:
        return REVIEW_FIX_LAYER, "Native readiness requires manual / fix-layer review"
    return RESEARCH_READY, "Bounded capability concept; governed readiness still required"


def route_for_review(snapshot, selected_ids, destination):
    """Read-only routing receipt; no candidate, draft, or knowledge mutation."""
    _intact(snapshot, "audit_fingerprint")
    if destination not in {NEEDS_DECOMPOSITION, REVIEW_FIX_LAYER}:
        raise ValueError("Select a review destination")
    by_id = {r["candidate_id"]: r for r in snapshot["gap_rows"]}
    if not selected_ids or any(cid not in by_id for cid in selected_ids):
        raise ValueError("Select existing candidates")
    return _seal({"audit_fingerprint": snapshot["audit_fingerprint"], "destination": destination,
                  "candidate_ids": sorted(set(selected_ids)), "production_writes": 0,
                  "provider_calls": 0}, "routing_fingerprint")


def list_gap_rows(audit, *, saved_rows, publications):
    """Present native consolidated candidates; never recluster requirements."""
    requirements = {(r["job_id"], r["requirement_id"]): r for r in audit["requirements"]}
    for job in audit["corpus"]["jobs"]:
        for raw in job["baseline_stable_analysis"].get("canonical_requirements", []):
            row = requirements.get((job["job_id"], raw["requirement_id"]))
            if row is not None:
                for key in ("source_provenance", "sources", "parent_text", "semantic_type", "eligibility_rule"):
                    row[key] = deepcopy(raw.get(key))
    native = bulk.build_candidate_queue(audit["candidates"], saved_rows=saved_rows,
                                        publications=publications, include_hidden=True)
    state_by_id = {r["candidate_id"]: r for r in native["rows"]}
    rows = []
    for item in audit["queue"]:
        candidate = item["candidate"]
        state = state_by_id[item["candidate_id"]]
        related = _related(candidate, saved_rows)
        affected = [requirements[key] for key in gaps._route_requirement_keys(item)
                    if key in requirements]
        layer = ROUTE_LAYERS.get(item["operational_route"], MANUAL)
        # Native routing is the authority. Uncertain or compound concepts cannot
        # be promoted to a capability just to fill a research tranche.
        if layer == CAPABILITY_GAP and candidate["candidate_route"] != "possible_new_capability":
            layer = MANUAL
        from taxonomy_discovery.research_readiness import NEEDS_DECOMPOSITION, BLOCKED_NOISE_OR_INSUFFICIENT, MANUAL_REVIEW
        readiness_state = state["research_readiness"]["research_readiness"]
        boundary, boundary_reason = capability_boundary(candidate, state["research_readiness"]) if layer == CAPABILITY_GAP else (REVIEW_FIX_LAYER, "Review native fix layer")
        rows.append({
            "candidate_id": item["candidate_id"], "concept": item["concept"],
            "fix_layer": layer, "reason": item["blocker_reason"] + (
                "; " + state["research_readiness"]["blocker_reason"]
                if readiness_state in {NEEDS_DECOMPOSITION, BLOCKED_NOISE_OR_INSUFFICIENT, MANUAL_REVIEW} else ""),
            "boundary_state": boundary, "boundary_reason": boundary_reason,
            "frequency": item["occurrences"], "distinct_jobs": item["job_count"],
            "required_core_impact": round(sum(gaps._weight(r) for r in affected
                if r["importance"] in {"required", "core", "deal_breaker"}), 6),
            "supporting_preferred_impact": round(sum(gaps._weight(r) for r in affected
                if r["importance"] not in {"required", "core", "deal_breaker"}), 6),
            "review_priority": item["priority_score"],
            "sample_requirement": item["example_jd_text"], "job_ids": item["job_ids"],
            "capability_resolution": state["full_production_resolution"],
            "technology_identity": state["registry_resolution"],
            "contextual_relationships": state["approved_capability_relationships"],
            "research_targets": [r["result"]["research_result_id"] for r in related],
            "research_status": state["research_status"],
            "latest_research_actions": [r["result"]["recommended_next_action"] for r in related],
            "review_status": state["review_status"],
            "publication_status": state["publication_status"],
            "next_action": ("Send to decomposition review" if layer == CAPABILITY_GAP and boundary == NEEDS_DECOMPOSITION else
                            "Send to manual / fix-layer review" if layer == CAPABILITY_GAP and boundary == REVIEW_FIX_LAYER else
                            "Review existing research" if related else
                            "Research capability boundary" if layer == CAPABILITY_GAP else
                            "Review " + layer.lower().replace("_", " ")),
            "readiness": state["research_readiness"],
            "parent_candidate_id": item.get("parent_candidate_id"),
            "requirements": deepcopy(affected), "candidate": deepcopy(candidate),
        })
    # Existing maintenance triage already groups active caps by capability.
    for item in audit["top_20_taxonomy_maintenance_priorities"]:
        if item["operational_route"] != "existing_capability_evidence_boundary":
            continue
        affected = [r for r in audit["requirements"] if r["taxonomy_cap_status"] == "applied"
                    and r["current_resolution"].get("capability_id") == item["concept"]]
        rows.append({
            "candidate_id": item["candidate_id"], "concept": item["concept"],
            "fix_layer": EVIDENCE_PROBLEM, "reason": "; ".join(item["usefulness_reasons"]),
            "boundary_state": REVIEW_FIX_LAYER, "boundary_reason": "Native evidence-policy review; excluded from capability research",
            "frequency": item["occurrences"], "distinct_jobs": item["job_count"],
            "required_core_impact": item["required_core_impact"],
            "supporting_preferred_impact": round(sum(gaps._weight(r) for r in affected
                if r["importance"] not in {"required", "core", "deal_breaker"}), 6),
            "review_priority": item["maintenance_priority_score"],
            "sample_requirement": affected[0]["requirement_text"] if affected else "",
            "job_ids": sorted({r["job_id"] for r in affected}),
            "capability_resolution": {"capability_id": item["concept"]},
            "technology_identity": {}, "contextual_relationships": [], "research_targets": [],
            "research_status": "evidence_policy_review", "latest_research_actions": [],
            "review_status": "unreviewed", "publication_status": "not_published",
            "next_action": "Review evidence policy; excluded from taxonomy research",
            "readiness": {}, "parent_candidate_id": None,
            "requirements": deepcopy(affected), "candidate": None,
        })
    return sorted(rows, key=lambda r: (-r["review_priority"], -r["frequency"], r["concept"], r["candidate_id"]))


def run_corpus_audit(*, explicit_execution=False, corpus=None, db_path=None, review_db_path=None,
                     job_ids=None):
    if explicit_execution is not True:
        raise ValueError("Explicit corpus audit required")
    source = deepcopy(corpus) if corpus is not None else export_saved_corpus(db_path=db_path)
    if job_ids is not None:
        selected = set(job_ids)
        if not selected or not selected.issubset({j["job_id"] for j in source["jobs"]}):
            raise ValueError("Select existing corpus job IDs")
        source["jobs"] = [j for j in source["jobs"] if j["job_id"] in selected]
        source["job_count"] = len(source["jobs"])
    with offline_execution("Maintenance audit is offline"):
        audit = gaps.audit_corpus_resolution(corpus=source, replay_current=True)
        saved = store.list_governed_research_results(db_path=review_db_path)
        pubs = publication.list_publications(db_path=review_db_path)
        rows = list_gap_rows(audit, saved_rows=saved, publications=pubs)
    manifest = {
        **production_identity(), "timestamp": datetime.now(timezone.utc).isoformat(),
        "scope": "frozen" if corpus is not None else "stored",
        "selected_job_ids": list(job_ids) if job_ids is not None else None,
        "job_ids": sorted(j["job_id"] for j in source["jobs"]),
        "corpus_fingerprint": fingerprint(source),
        "replayed_corpus_fingerprint": fingerprint(audit["corpus"]),
    }
    excluded = [{"job_id": job["job_id"], "source": deepcopy(row)}
                for job in audit["corpus"]["jobs"]
                for row in job["baseline_stable_analysis"].get("canonicalisation_debug", {}).get("filtered_non_requirement_rows", [])]
    return _seal({"manifest": manifest, "audit": audit, "gap_rows": rows,
                  "parsing_noise_diagnostics": excluded,
                  "fix_layer_counts": dict(Counter(r["fix_layer"] for r in rows)),
                  "existing_research_backlog_count": len(saved),
                  "network_calls": 0, "model_calls": 0, "production_writes": 0}, "audit_fingerprint")


def currentness(snapshot, *, db_path=None):
    try:
        _intact(snapshot, "audit_fingerprint")
        manifest = snapshot["manifest"]
        blockers = [key + " changed" for key, value in production_identity().items()
                    if manifest.get(key) != value]
        if manifest["scope"] == "stored":
            source = export_saved_corpus(db_path=db_path)
            if manifest["selected_job_ids"] is not None:
                source["jobs"] = [j for j in source["jobs"] if j["job_id"] in manifest["selected_job_ids"]]
                source["job_count"] = len(source["jobs"])
            if fingerprint(source) != manifest["corpus_fingerprint"]:
                blockers.append("Stored corpus/evidence changed")
        if snapshot["audit"]["corpus"].get("current_replay", {}).get("jobs_blocked"):
            blockers.append("Frozen inputs unavailable; current replay incomplete")
        if not snapshot["audit"]["corpus"]["jobs"]:
            blockers.append("Corpus empty")
        return {"current": not blockers, "blockers": blockers}
    except (ValueError, KeyError, OSError) as exc:
        return {"current": False, "blockers": [str(exc)]}


def _require_current(snapshot, db_path=None):
    status = currentness(snapshot, db_path=db_path)
    if not status["current"]:
        raise ValueError("STALE / unavailable: " + "; ".join(status["blockers"]))


def build_research_tranche(snapshot, *, size=5, explicit_creation=False, db_path=None, routing=None):
    if explicit_creation is not True:
        raise ValueError("Explicit tranche construction required")
    if type(size) is not int or not 1 <= size <= 20:
        raise ValueError("Tranche size must be 1 to 20")
    _require_current(snapshot, db_path)
    routed = {}
    for receipt in routing or []:
        _intact(receipt, "routing_fingerprint")
        if receipt["audit_fingerprint"] != snapshot["audit_fingerprint"]:
            raise ValueError("Routing belongs to an earlier audit")
        routed.update({cid: receipt["destination"] for cid in receipt["candidate_ids"]})
    eligible = [r for r in snapshot["gap_rows"] if r["fix_layer"] == CAPABILITY_GAP
                and r.get("boundary_state") == RESEARCH_READY and r["candidate_id"] not in routed
                and not r["parent_candidate_id"] and r["publication_status"] != "published"
                and r["review_status"] not in {"reject", "defer"}]
    # Existing consolidated queue contains one target per candidate; persisted
    # targets remain references, never a second saved candidate or research row.
    selected = eligible[:size]
    excluded = deepcopy([r for r in snapshot["gap_rows"] if r["fix_layer"] == CAPABILITY_GAP
                         and (r.get("boundary_state") != RESEARCH_READY or r["candidate_id"] in routed)])
    for row in excluded:
        if row["candidate_id"] in routed:
            row["boundary_state"] = routed[row["candidate_id"]]
            row["boundary_reason"] = "Explicit session-only review routing; native candidate unchanged"
            row["next_action"] = "Review selected " + row["boundary_state"].lower().replace("_", " ")
    return _seal({"audit_fingerprint": snapshot["audit_fingerprint"],
                  "targets": deepcopy(selected), "requested_size": size,
                  "excluded_targets": excluded,
                  "provider_calls": 0, "production_writes": 0,
                  "expected_benefit": "Bounded knowledge/provenance; no predicted score increase"},
                 "tranche_fingerprint")


def get_concept_detail(snapshot, candidate_id, *, review_db_path=None):
    _intact(snapshot, "audit_fingerprint")
    row = next(r for r in snapshot["gap_rows"] if r["candidate_id"] == candidate_id)
    saved = store.list_governed_research_results(db_path=review_db_path)
    return {**deepcopy(row), "persisted_research": _related(row["candidate"], saved)
            if row["candidate"] else []}


def plan_research(snapshot, tranche, selected_ids, *, db_path=None, review_db_path=None, transport=None):
    _require_current(snapshot, db_path)
    _intact(tranche, "tranche_fingerprint")
    if tranche["audit_fingerprint"] != snapshot["audit_fingerprint"]:
        raise ValueError("Tranche belongs to a different audit")
    candidates = [r["candidate"] for r in tranche["targets"]]
    plan = bulk.prepare_bulk_plan(candidates, selected_candidate_ids=selected_ids,
        saved_rows=store.list_governed_research_results(db_path=review_db_path),
        publications=publication.list_publications(db_path=review_db_path))
    from taxonomy_discovery.tavily_research import tavily_api_key_from_env
    blocker = network_blocker()
    if transport is None and not tavily_api_key_from_env():
        blocker = blocker or "Tavily research is not configured. TAVILY_API_KEY is unavailable."
    plan["provider_blocker"] = blocker if plan["planned_tavily_calls"] else None
    targets = {item["candidate_id"]: item for item in plan["execution_targets"]}
    readiness_by_id = {item["candidate_id"]: item for item in plan["selected_readiness"]}
    rows = {row["candidate_id"]: row for row in tranche["targets"]}
    preview = []
    for cid in selected_ids:
        item = targets.get(cid)
        status = "READY TO EXECUTE" if item else "BLOCKED"
        readiness = readiness_by_id[cid]
        reason = "Governed plan ready" if item else readiness.get("blocker_reason", "No executable target")
        if readiness["research_readiness"] == "stale_research":
            status, reason = "EXISTING RESEARCH / REFRESH REQUIRED", "Stale existing research; inspect / refresh saved evidence"
        elif item and item["external"] and blocker:
            status, reason = "BLOCKED", blocker
        preview.append({"candidate_id": cid, "concept": rows[cid]["concept"], "execution_status": status,
                        "planned_calls": item["planned_tavily_calls"] if item else 0, "reason": reason})
    plan["execution_preview"] = preview
    return _seal(plan, "plan_fingerprint")


def execute_research(snapshot, tranche, selected_ids, *, explicit_execution=False,
                     transport=None, db_path=None, review_db_path=None, confirmed_plan_fingerprint=None):
    if explicit_execution is not True:
        raise ValueError("Explicit research execution required")
    plan = plan_research(snapshot, tranche, selected_ids, db_path=db_path, review_db_path=review_db_path, transport=transport)
    if plan["provider_blocker"]:
        raise ValueError(plan["provider_blocker"])
    if transport is None and confirmed_plan_fingerprint is None:
        raise ValueError("Confirm the exact previewed research plan before provider execution")
    if confirmed_plan_fingerprint is not None and confirmed_plan_fingerprint != plan["plan_fingerprint"]:
        raise ValueError("Research plan changed; preview and confirm again")
    provider = transport
    def isolated_provider(target):
        with research_execution():
            return provider(target) if provider else research.tavily_transport(target, explicit_execution=True)
    with research_execution():
        return bulk.execute_bulk_plan(plan, [r["candidate"] for r in tranche["targets"]],
            explicit_execution=True, transport=isolated_provider, db_path=review_db_path)


def review_group(row, new_ids=()):
    """Presentation only; validate native currentness without changing review."""
    result = row["result"]
    try:
        research.validate_result(result)
    except (ValueError, OSError, KeyError, TypeError):
        return "STALE / REFRESH REQUIRED"
    if result.get("conflicts_blockers") or result.get("recommended_next_action") == "research_more":
        return "BLOCKED / RESEARCH_MORE"
    if result["research_result_id"] in new_ids or row["review"].get("decision", "undecided") in {"unreviewed", "undecided"}:
        return "NEW / NEEDS REVIEW"
    return "HISTORICAL"


def build_review_targets(snapshot, *, saved_rows=None, new_ids=()):
    """One actionable primary per native scope/lineage; history stays immutable."""
    _intact(snapshot, "audit_fingerprint")
    saved = store.list_governed_research_results() if saved_rows is None else saved_rows
    candidates = {r["candidate"]["candidate_id"]: r["candidate"] for r in snapshot["gap_rows"] if r["candidate"]}
    grouped = {}
    for row in saved:
        historical = row["result"]["candidate"]
        compatible = [c for c in candidates.values() if research.compatible_saved_candidate(c, historical)]
        current = compatible[0] if len(compatible) == 1 else None
        key = ("current", current["candidate_id"]) if current else (
            "historical", research.research_lineage_key(historical),
            fingerprint(sorted(research._source_lineage(historical))) if research._source_lineage(historical)
            else historical["candidate_fingerprint"])
        group = grouped.setdefault(key, {"current_candidate": current, "attempts": [],
            "binding_blocker": (None if current else "Saved evidence cannot be associated unambiguously with a current candidate lineage")})
        group["attempts"].append(row)
    output = []
    for key, group in grouped.items():
        current = group["current_candidate"]
        def rank(row):
            exact = bool(current and row["result"]["candidate_fingerprint"] == current["candidate_fingerprint"])
            valid = review_group(row) != "STALE / REFRESH REQUIRED"
            result = row["result"]
            try:
                research._validate_saved_integrity(result)
                intact = True
            except (ValueError, KeyError, TypeError):
                intact = False
            return (intact, exact and valid, exact, valid,
                    result.get("re_evaluated_at") or result.get("executed_at", ""), result["research_result_id"])
        attempts = sorted(group["attempts"], key=rank, reverse=True)
        selection = research.select_saved_interpretation(current, attempts) if current else None
        primary = selection["primary"] if selection and selection["primary"] else attempts[0]
        if selection and not selection["primary"]:
            group["binding_blocker"] = selection["reason"]
        status = review_group(primary, new_ids)
        if group["binding_blocker"]:
            status = "STALE / REFRESH REQUIRED"
        if current and primary["result"]["candidate_fingerprint"] != current["candidate_fingerprint"]:
            status = "STALE / REFRESH REQUIRED"
        historical = [row for row in attempts if row is not primary or status == "STALE / REFRESH REQUIRED"]
        output.append({**group, "attempts": attempts, "historical_attempts": historical,
            "group_id": fingerprint(key), "primary": primary, "status": status,
            "interpretation_selection": {k: v for k, v in (selection or {}).items() if k != "primary"},
            "concept": current["concept_key"] if current else primary["result"]["candidate"]["concept_key"]})
    order = {"NEW / NEEDS REVIEW": 0, "STALE / REFRESH REQUIRED": 1, "BLOCKED / RESEARCH_MORE": 2, "HISTORICAL": 3}
    return sorted(output, key=lambda group: (group["primary"]["result"]["research_result_id"] not in new_ids,
                  order[group["status"]], group["concept"], group["group_id"]))


def refresh_saved_research(snapshot, candidate_id, *, explicit_execution=False, db_path=None, review_db_path=None,
                           persist=True):
    """Current audit chooses the lineage and most relevant immutable evidence."""
    if explicit_execution is not True:
        raise ValueError("Explicit saved-evidence refresh required")
    _require_current(snapshot, db_path)
    targets = build_review_targets(snapshot, saved_rows=store.list_governed_research_results(db_path=review_db_path))
    applicable = [g for g in targets if g["current_candidate"] and g["current_candidate"]["candidate_id"] == candidate_id]
    if len(applicable) != 1:
        raise ValueError("Saved evidence cannot be associated with the current candidate lineage")
    group = applicable[0]
    if group["binding_blocker"]:
        raise ValueError(group["binding_blocker"])
    # Only the native governor performs reinterpretation and result persistence.
    with offline_execution("Saved-evidence refresh is offline"):
        return research.re_evaluate_saved_evidence(group["primary"]["result"],
            current_candidate=group["current_candidate"], explicit_execution=True,
            persist=persist, db_path=review_db_path)


def _saved_drafts(result_ids, review_db_path, *, approved):
    saved = {r["result"]["research_result_id"]: r
             for r in store.list_governed_research_results(db_path=review_db_path)}
    if not result_ids or len(set(result_ids)) != len(result_ids):
        raise ValueError("Select distinct saved drafts")
    rows = [saved[rid] for rid in result_ids]
    for row in rows:
        if not row["draft"]:
            raise ValueError("Saved draft required")
        research.validate_result(row["result"])
        review = row["review"]
        if review.get("decision") in {"reject", "defer"}:
            raise ValueError("Draft rejected or deferred")
        if approved and (review.get("decision") != "approve_for_publication"
                         or not review.get("reviewer") or not review.get("updated_at")):
            raise ValueError("Explicit human approval required for controlled validation")
    published = {r["research_result_id"] for r in publication.list_publications(db_path=review_db_path)
                 if r["status"] == "published"}
    if published.intersection(result_ids):
        raise ValueError("Select approved but unpublished drafts")
    return rows


def run_candidate_validation(snapshot, result_ids, *, explicit_execution=False, approved=True,
                             db_path=None, review_db_path=None):
    """Native combined/per-item regression; retain production scoring unchanged."""
    if explicit_execution is not True:
        raise ValueError("Explicit candidate validation required")
    _require_current(snapshot, db_path)
    rows = _saved_drafts(result_ids, review_db_path, approved=approved)
    native = bulk.preview_bulk_regression(snapshot["audit"]["corpus"], [
        {"result_id": r["result"]["research_result_id"], "draft": r["draft"]} for r in rows])
    report = native["combined"]
    if report is None:
        raise ValueError("Combined overlay unsupported; select one artifact family or one draft")
    # Reuse native overlay contracts to collect full rankings and cap receipts.
    with ExitStack() as stack:
        stack.enter_context(offline_execution("Offline validation"))
        if all(r["draft"]["kind"] == "capability" for r in rows):
            from taxonomy_discovery.taxonomy_evolution import temporary_overlay
            from tailoring.capability_taxonomy import temporary_taxonomy_scope
            stack.enter_context(temporary_taxonomy_scope(temporary_overlay([r["draft"]["proposal"] for r in rows])))
        elif len(rows) == 1 and rows[0]["draft"]["kind"] == "resolver_improvement":
            from taxonomy_discovery.resolver_improvement import resolver_overlay
            from tailoring.capability_taxonomy import temporary_taxonomy_scope
            stack.enter_context(temporary_taxonomy_scope(resolver_overlay(rows[0]["draft"])))
        elif len(rows) == 1 and rows[0]["draft"]["kind"] == "technology":
            from taxonomy_discovery.focused_verification_preview import _shadow_registry
            from taxonomy_discovery.technology_registry import temporary_registry_scope
            stack.enter_context(temporary_registry_scope(_shadow_registry(rows[0]["draft"])))
        else:
            raise ValueError("Unsupported temporary artifact scope")
        after = replay_current_corpus(snapshot["audit"]["corpus"])
        overlay_canaries = bulk.bulk_canary_status()
    before = snapshot["audit"]["corpus"]
    before_rank = gaps._integrated_ranking(before)
    after_rank = gaps._integrated_ranking(after)
    changes = [{"job_id": j["job_id"], **c} for j in report["jobs"] for c in j.get("requirement_changes", [])]
    warnings = []
    for c in changes:
        current = c.get("after") or {}
        if current.get("match_label") == "direct":
            warnings.append({"job_id": c["job_id"], "requirement_id": c["requirement_id"],
                "reason": "New/changed DIRECT: inspect evidence overlap, compound completeness, negation, and child provenance"})
    for job in report["jobs"]:
        warnings.extend({"job_id": job["job_id"], "reason": v} for v in job.get("duplicate_credit_violations", []))
    for row in rows:
        for proposal in (row["draft"].get("proposal_bundle") or {}).get("proposals", []):
            if proposal["technology_id"] in {"aws", "azure", "gcp"} and proposal.get("proposed_capability_id"):
                warnings.append({"result_id": row["result"]["research_result_id"],
                    "reason": "Broad cloud identity mapping: verify contextual boundaries; no universal capability inference"})
    warnings.extend({"reason": "Overlay canary failed: " + name} for name, value in overlay_canaries.items() if not value["safe"])
    caps = [{"job_id": j["job_id"], "requirement_id": r["requirement_id"],
             "label": r.get("match_label"), "cap_status": r.get("capability_taxonomy_cap_status"),
             "warnings": deepcopy(r.get("validation_warnings", [])),
             "evidence": deepcopy(r.get("evidence", [])),
             "does_not_prove": deepcopy(r.get("capability_does_not_prove", []))}
            for j in after["jobs"] for r in j["baseline_stable_analysis"].get("canonical_requirements", [])
            if r.get("capability_taxonomy_cap_status") == "applied" or r.get("match_label") == "none"]
    return _seal({"audit_fingerprint": snapshot["audit_fingerprint"],
        "manifest": deepcopy(snapshot["manifest"]), "approved_validation": approved,
        "draft_fingerprints": {r["result"]["research_result_id"]: fingerprint(r["draft"]) for r in rows},
        "native": native, "overlay_canaries": overlay_canaries, "before_ranking": before_rank, "after_ranking": after_rank,
        "ranking_changes": [{"before": b, "after": a} for b in before_rank
            for a in after_rank if a["job_id"] == b["job_id"] and a != b],
        "requirement_receipts": changes, "caps_rejections": caps, "warnings": warnings,
        "newly_resolved": sum(c["newly_resolved"] for c in changes),
        "newly_unresolved": sum(c["newly_unresolved"] for c in changes),
        "newly_direct": sum((c.get("after") or {}).get("match_label") == "direct"
            and (c.get("before") or {}).get("match_label") != "direct" for c in changes),
        "none_to_positive": sum((c.get("before") or {}).get("match_label") == "none"
            and (c.get("after") or {}).get("match_label") in {"direct", "transferable", "weak"} for c in changes),
        "production_writes": 0, "model_calls": 0, "network_calls": 0}, "validation_fingerprint")


def publication_preflight(snapshot, validation, result_id, *, db_path=None, review_db_path=None, proposal_db_path=None):
    try:
        _require_current(snapshot, db_path)
        _intact(validation, "validation_fingerprint")
        if validation["audit_fingerprint"] != snapshot["audit_fingerprint"] or not validation["approved_validation"]:
            raise ValueError("Current approved validation required")
        rows = _saved_drafts([result_id], review_db_path, approved=True)
        if validation["draft_fingerprints"].get(result_id) != fingerprint(rows[0]["draft"]):
            raise ValueError("Validated draft identity changed")
        if validation["native"]["publication_blockers"]:
            raise ValueError("Controlled validation has publication blockers")
        if any(not row["safe"] for row in validation["overlay_canaries"].values()):
            raise ValueError("Controlled overlay failed production canaries")
        return publication.prepare_publication(result_id, db_path=review_db_path, proposal_db_path=proposal_db_path)
    except (ValueError, KeyError, OSError) as exc:
        return {"ready": False, "blockers": [str(exc)]}


def publish_validated(snapshot, validation, result_id, *, explicit_publish=False,
                      db_path=None, review_db_path=None, proposal_db_path=None):
    if explicit_publish is not True:
        raise ValueError("Explicit confirmed publication required")
    preflight = publication_preflight(snapshot, validation, result_id, db_path=db_path,
        review_db_path=review_db_path, proposal_db_path=proposal_db_path)
    if not preflight["ready"]:
        raise ValueError("Publication blocked: " + "; ".join(preflight["blockers"]))
    return publication.publish_approved_change(result_id, explicit_publish=True,
        db_path=review_db_path, proposal_db_path=proposal_db_path)


def export_audit_bundle(snapshot, *, tranche=None, validation=None):
    _intact(snapshot, "audit_fingerprint")
    rows = [{k: v for k, v in r.items() if k not in {"candidate", "requirements", "readiness"}}
            for r in snapshot["gap_rows"]]
    for exported, original in zip(rows, snapshot["gap_rows"]):
        exported["contributing_requirements"] = [{k: row.get(k) for k in (
            "job_id", "snapshot_id", "requirement_id", "requirement_text", "importance",
            "score_eligible", "match_label", "current_resolution", "provenance",
            "source_provenance", "sources", "parent_text")}
            for row in original["requirements"]]
    summary = snapshot["audit"]["summary"]
    markdown = "# Taxonomy Maintenance\n\nUnresolved requirements are not automatically taxonomy gaps.\n\n" + "\n".join(
        f"- {key}: {value}" for key, value in summary.items())
    exported_validation = deepcopy(validation)
    if exported_validation:
        # Validation receipts need identities and before/after outcomes, not
        # provider request payloads embedded in native draft research evidence.
        for item in exported_validation["native"]["per_item"]:
            item["draft"] = {"kind": item["draft"]["kind"], "draft_fingerprint": fingerprint(item["draft"])}
    files = {"manifest.json": snapshot["manifest"], "audit_summary.json": summary,
             "consolidated_gaps.json": rows,
             "research_tranche.json": ({"tranche_fingerprint": tranche["tranche_fingerprint"],
                "targets": [{"candidate_id": r["candidate_id"], "concept": r["concept"],
                             "reason": r["reason"]} for r in tranche["targets"]]} if tranche else None),
             "controlled_validation.json": exported_validation}
    csv_buffer = io.StringIO(newline="")
    if rows:
        writer = csv.DictWriter(csv_buffer, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                          for k, v in r.items()} for r in rows)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as bundle:
        for name, value in files.items():
            bundle.writestr(name, json.dumps(value, indent=2, ensure_ascii=False))
        bundle.writestr("consolidated_gaps.csv", csv_buffer.getvalue())
        bundle.writestr("summary.md", markdown)
    return {"zip": buffer.getvalue(), "debug_summary": markdown}

"""Bounded orchestration over the governed single-candidate TQ-D3 contracts.

Planning is pure/read-only.  Research, draft persistence, review and publication
remain separate explicit operations implemented by their existing owners.
"""
from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import closing
from copy import deepcopy
from datetime import datetime, timezone
import json
import sqlite3
import threading

from job_discovery.matching import current_match_versions
from tailoring.capability_taxonomy import get_default_taxonomy, classify_requirement_record
from tailoring.production_requirement_resolver import resolve_requirement_with_production_knowledge
from taxonomy_discovery.corpus_expansion import fingerprint
from taxonomy_discovery.technology_registry import resolve_requirement_text, normalise


BULK_OPERATIONS_VERSION = "tqd3-bulk-gap-operations-v2"
MAX_WORKING_BATCH = 25
MAX_EXTERNAL_CANDIDATES_PER_RUN = 8
MAX_TAVILY_CALLS_PER_RUN = 20
MAX_QUERIES_PER_CANDIDATE = 3
MAX_PARALLELISM = 4
SYSTEMIC_FAILURE_THRESHOLD = 2

ACTIONABLE_ROUTES = (
    "existing_capability_resolver_issue",
    "technology_relationship",
    "technology_identity",
    "possible_new_capability",
)
ROUTE_WEIGHT = {route: (len(ACTIONABLE_ROUTES) - index) * 10_000 for index, route in enumerate(ACTIONABLE_ROUTES)}
TERMINAL_QUEUE_STATES = {"already_published", "already_rejected", "deferred", "resolved_locally", "research_current_cached"}
EXECUTABLE_QUEUE_STATES = {"external_research_required", "known_identity_missing_relationship", "research_more_required", "local_review_required"}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _valid_result(result):
    from taxonomy_discovery.governed_research import validate_result
    try:
        validate_result(result)
        return True
    except (ValueError, KeyError, TypeError, OSError):
        return False


def _latest_saved(candidate, saved_rows):
    exact = [row for row in saved_rows if row["result"].get("candidate_fingerprint") == candidate["candidate_fingerprint"]]
    exact.sort(key=lambda row: (row["result"].get("executed_at", ""), row["result"].get("research_result_id", "")), reverse=True)
    stale = [row for row in saved_rows if row["result"].get("candidate", {}).get("concept_key") == candidate.get("concept_key")]
    stale.sort(key=lambda row: (row["result"].get("executed_at", ""), row["result"].get("research_result_id", "")), reverse=True)
    return (exact[0] if exact else None), (stale[0] if stale else None)


def _published_candidate_ids(publications):
    return {row.get("candidate_id") for row in publications if row.get("status") == "published"}


def _atomicity(candidate):
    from taxonomy_discovery.research_atomicity import candidate_atomicity
    return candidate_atomicity(candidate)


def _production_resolution(text):
    resolved = resolve_requirement_with_production_knowledge({"text": text, "atomic_focus": text})
    diagnostics = deepcopy(resolved.get("taxonomy_diagnostics") or {})
    diagnostics.pop("capability_record", None)
    decision = deepcopy(resolved.get("decision") or {})
    return {
        "text": text,
        "resolution_source": resolved.get("resolution_source"),
        "capability_id": decision.get("capability_id"),
        "taxonomy_diagnostics": diagnostics,
        "registry_resolution": deepcopy(resolved.get("registry_resolution")),
    }


def _component_terms(candidate, atomicity, product_names):
    """Conservative decomposition signals; never identity or relationship proof."""
    from taxonomy_discovery.candidate_refinement import phrase_present
    text = " ".join(candidate.get("examples") or [candidate.get("normalized_cluster", "")])
    terms = {normalise(term): term for term in atomicity.get("detected_entities", []) if normalise(term)}
    atomic_terms = list(terms.values())
    for configured in product_names:
        if phrase_present(text, configured):
            if any(phrase_present(configured, term) or phrase_present(term, configured) for term in atomic_terms):
                continue
            terms.setdefault(normalise(configured), configured)
            continue
        # Vendor-qualified local vocabulary can still identify a conservative
        # decomposition boundary when the source omits only the vendor prefix.
        # This is a review signal; the production resolver must still decide it.
        words = configured.split()
        suffix = " ".join(words[1:])
        if len(words) >= 3 and phrase_present(text, suffix):
            terms.setdefault(normalise(suffix), suffix)
    return [terms[key] for key in sorted(terms)]


def _local_resolution(candidate, atomicity=None, product_names=()):
    text = " ".join(candidate.get("examples") or [candidate.get("normalized_cluster", "")])
    atomicity = atomicity or _atomicity(candidate)
    full = _production_resolution(text)
    component_terms = _component_terms(candidate, atomicity, product_names)
    raw_components = [_production_resolution(entity) for entity in component_terms]
    components_by_identity = {}
    for row in raw_components:
        registry = row.get("registry_resolution") or {}
        key = ("technology", registry["technology_id"]) if registry.get("technology_id") else ("text", normalise(row["text"]))
        existing = components_by_identity.get(key)
        if existing is None or len(row["text"]) < len(existing["text"]):
            components_by_identity[key] = row
    components = [components_by_identity[key] for key in sorted(components_by_identity)]
    resolved_components = [row for row in components if row.get("capability_id")]
    recognized_components = [row for row in components if (row.get("registry_resolution") or {}).get("status") in {"recognized_unmapped", "resolved"}]
    unresolved_components = [row for row in components if not row.get("capability_id")]
    compound = atomicity.get("atomicity_status") == "compound_requires_decomposition" or len(component_terms) > 1
    full_resolved = bool(full.get("capability_id"))
    if compound and (full_resolved or resolved_components or recognized_components):
        state = "partial_resolution"
    elif full_resolved or (len(components) == 1 and len(resolved_components) == 1):
        state = "already_resolved"
    elif len(components) == 1 and recognized_components:
        state = "known_identity_missing_relationship"
    else:
        state = "unresolved"
    registry = full.get("registry_resolution") or resolve_requirement_text(text)
    return {
        "taxonomy": full if full.get("resolution_source") == "canonical_taxonomy" else None,
        "registry": registry,
        "full_resolution": full,
        "component_resolutions": components,
        "recognized_technology_identities": [{
            "text": row["text"],
            "technology_id": (row.get("registry_resolution") or {}).get("technology_id"),
            "technology_label": (row.get("registry_resolution") or {}).get("technology_label"),
            "registry_status": (row.get("registry_resolution") or {}).get("status"),
        } for row in recognized_components],
        "approved_capability_relationships": [{
            "text": row["text"],
            "capability_id": row.get("capability_id"),
            "resolution_source": row.get("resolution_source"),
        } for row in resolved_components],
        "unresolved_components": [row["text"] for row in unresolved_components],
        "operational_atomicity": "compound_requires_decomposition" if compound else atomicity.get("atomicity_status"),
        "decomposition_required": compound,
        "current_knowledge_state": state,
        "resolved": state == "already_resolved",
        "partial": state == "partial_resolution",
    }


def _priority(candidate, *, local, atomicity, state):
    importance = candidate.get("importance_distribution") or {}
    jobs = int(candidate.get("job_count") or candidate.get("observed_job_count") or 0)
    occurrences = int(candidate.get("occurrence_count") or candidate.get("observed_occurrence_count") or 0)
    route = ROUTE_WEIGHT.get(candidate.get("candidate_route"), 0)
    required = int(importance.get("required", 0))
    core = int(importance.get("core", 0))
    preferred = int(importance.get("preferred", 0))
    readiness = 100 if state in EXECUTABLE_QUEUE_STATES else 0
    local_evidence = 25 if local["current_knowledge_state"] in {"already_resolved", "partial_resolution", "known_identity_missing_relationship"} else 0
    risk = 500 if local.get("decomposition_required") else 0
    components = {
        "route": route,
        "distinct_jobs": jobs * 300,
        "occurrences": occurrences * 30,
        "required": required * 80,
        "core": core * 50,
        "preferred": preferred * 10,
        "research_readiness": readiness,
        "local_evidence": local_evidence,
        "collateral_risk_penalty": -risk,
    }
    return sum(components.values()), components


def build_candidate_queue(candidates, *, saved_rows=None, publications=None, include_hidden=False,
                          authority_registry_path=None):
    """Build a deterministic, read-only queue from current candidates and governance state."""
    from database.taxonomy_discovery_review_manager import list_governed_research_results
    from taxonomy_discovery.governed_publication import list_publications
    saved_rows = list_governed_research_results() if saved_rows is None else deepcopy(saved_rows)
    publications = list_publications() if publications is None else deepcopy(publications)
    from taxonomy_discovery.candidate_refinement import product_context_names
    product_names = product_context_names()
    published_ids = _published_candidate_ids(publications)
    rows = []
    for candidate in candidates:
        atomicity = _atomicity(candidate)
        local = _local_resolution(candidate, atomicity, product_names)
        exact, stale = _latest_saved(candidate, saved_rows)
        historical_result = (exact or stale or {}).get("result")
        review = (exact or {}).get("review") or {"decision": "undecided"}
        decision = review.get("decision", "undecided")
        current = bool(exact and _valid_result(exact["result"]))
        result = exact["result"] if exact else None
        blockers = []
        if candidate["candidate_id"] in published_ids or (result and any(
                p.get("research_result_id") == result.get("research_result_id") and p.get("status") == "published"
                for p in publications)):
            state = "already_published"
        elif decision == "reject":
            state = "already_rejected"
        elif decision == "defer":
            state = "deferred"
        elif local["decomposition_required"]:
            state = "partial_resolution_decomposition_required" if local["partial"] else "blocked"
            blockers.append("partial_current_knowledge_requires_decomposition" if local["partial"] else "compound_requires_decomposition")
        elif local["resolved"]:
            state = "resolved_locally"
        elif current:
            state = "research_more_required" if result.get("recommended_next_action") == "research_more" else "research_current_cached"
        elif exact or stale:
            state = "stale_requires_refresh"
            blockers.append("persisted_research_fingerprint_or_knowledge_is_stale")
        elif local["current_knowledge_state"] == "known_identity_missing_relationship":
            state = "known_identity_missing_relationship"
        elif candidate.get("candidate_route") == "existing_capability_resolver_issue":
            state = "local_review_required"
        elif candidate.get("candidate_route") in ACTIONABLE_ROUTES:
            state = "external_research_required"
        else:
            state = "blocked"
            blockers.append("route_not_actionable_by_default")
        score, components = _priority(candidate, local=local, atomicity=atomicity, state=state)
        jobs = sorted({p.get("job_id") for p in candidate.get("provenance", []) if p.get("job_id") is not None})
        rows.append({
            "candidate_id": candidate["candidate_id"],
            "candidate_fingerprint": candidate["candidate_fingerprint"],
            "concept": candidate.get("concept_key") or candidate.get("normalized_cluster"),
            "route": candidate.get("candidate_route"),
            "example": (candidate.get("examples") or [""])[0],
            "source_job_ids": jobs,
            "occurrence_count": candidate.get("occurrence_count", 0),
            "distinct_job_count": candidate.get("job_count", len(jobs)),
            "importance_distribution": deepcopy(candidate.get("importance_distribution") or {}),
            "taxonomy_resolution": deepcopy(local["taxonomy"]),
            "registry_resolution": deepcopy(local["registry"]),
            "full_production_resolution": deepcopy(local["full_resolution"]),
            "component_resolutions": deepcopy(local["component_resolutions"]),
            "recognized_technology_identities": deepcopy(local["recognized_technology_identities"]),
            "approved_capability_relationships": deepcopy(local["approved_capability_relationships"]),
            "unresolved_components": deepcopy(local["unresolved_components"]),
            "local_evidence_status": local["current_knowledge_state"],
            "research_status": state,
            "external_research_required": state in {"external_research_required", "known_identity_missing_relationship", "research_more_required"},
            "draft_status": "saved" if exact and exact.get("draft") else "none",
            "review_status": decision,
            "publication_status": "published" if state == "already_published" else "not_published",
            "blockers": blockers,
            "priority_score": score,
            "priority_components": components,
            "priority_reason": ", ".join(f"{key}={value}" for key, value in components.items() if value),
            "atomicity": atomicity.get("atomicity_status"),
            "operational_atomicity": local["operational_atomicity"],
            "research_result_id": result.get("research_result_id") if result else None,
            "prior_recommended_action": historical_result.get("recommended_next_action") if historical_result else None,
            "current_result": current,
            "candidate": deepcopy(candidate),
        })
    rows.sort(key=lambda row: (-row["priority_score"], row["concept"], row["candidate_id"]))
    for index, row in enumerate(rows, 1):
        row["priority_rank"] = index
    actionable = [row for row in rows if row["route"] in ACTIONABLE_ROUTES]
    visible = rows if include_hidden else actionable
    default = [row for row in actionable if row["research_status"] not in TERMINAL_QUEUE_STATES]
    for index, row in enumerate(default, 1):
        row["work_queue_rank"] = index
    from taxonomy_discovery.research_readiness import audit_candidate_queue
    readiness = audit_candidate_queue(rows, authority_registry_path=authority_registry_path)
    readiness_by_id = {row["candidate_id"]: row for row in readiness["candidates"]}
    for row in rows:
        row["research_readiness"] = deepcopy(readiness_by_id[row["candidate_id"]])
    return {
        "bulk_operations_version": BULK_OPERATIONS_VERSION,
        "rows": rows,
        "visible_rows": visible,
        "default_rows": default,
        "route_counts": dict(sorted(Counter(row["route"] for row in rows).items())),
        "status_counts": dict(sorted(Counter(row["research_status"] for row in rows).items())),
        "research_readiness": readiness,
        "current_versions": current_match_versions(),
        "maximum_working_batch": MAX_WORKING_BATCH,
        "queue_fingerprint": fingerprint([{k: v for k, v in row.items() if k != "candidate"} for row in rows]),
    }


def _research_round(row, saved_rows):
    exact, _ = _latest_saved(row["candidate"], saved_rows)
    if row["research_status"] != "research_more_required" or not exact:
        return 0
    prior_round = int(exact["result"]["research"]["target"].get("research_round", 0))
    if prior_round >= MAX_QUERIES_PER_CANDIDATE - 1:
        return None
    return prior_round + 1


def prepare_bulk_plan(candidates, *, selected_candidate_ids, saved_rows=None, publications=None,
                      authority_registry_path=None):
    """Pure local/cache-first precheck and exact next-run budget preview."""
    from database.taxonomy_discovery_review_manager import list_governed_research_results
    from taxonomy_discovery.governed_research import research_plan
    selected = list(dict.fromkeys(selected_candidate_ids))
    if not selected or len(selected) > MAX_WORKING_BATCH:
        raise ValueError(f"Select 1 to {MAX_WORKING_BATCH} candidates")
    by_id = {candidate["candidate_id"]: candidate for candidate in candidates}
    if any(candidate_id not in by_id for candidate_id in selected):
        raise ValueError("Unknown selected candidate")
    saved_rows = list_governed_research_results() if saved_rows is None else deepcopy(saved_rows)
    queue = build_candidate_queue(candidates, saved_rows=saved_rows, publications=publications, include_hidden=True,
                                  authority_registry_path=authority_registry_path)
    queue_by_id = {row["candidate_id"]: row for row in queue["rows"]}
    selected_rows = sorted((queue_by_id[candidate_id] for candidate_id in selected), key=lambda row: row["priority_rank"])
    execution = []
    exhausted_candidate_ids = []
    for row in selected_rows:
        if row["research_status"] not in EXECUTABLE_QUEUE_STATES:
            continue
        round_number = _research_round(row, saved_rows)
        if round_number is None:
            exhausted_candidate_ids.append(row["candidate_id"])
            continue
        readiness = row["research_readiness"]
        if row["external_research_required"] and not readiness["paid_research_eligible"]:
            continue
        plan = research_plan([row["candidate"]], selected_candidate_ids=[row["candidate_id"]],
                             external_resolver=False, research_round=round_number,
                             authority_registry_path=authority_registry_path)
        target = plan["targets"][0]
        if target["external_requested"] and not readiness["paid_research_eligible"]:
            continue
        if len(target["questions"]) > MAX_QUERIES_PER_CANDIDATE:
            raise ValueError("Single-candidate plan exceeds query ceiling")
        execution.append({
            "candidate_id": row["candidate_id"],
            "priority_rank": row["priority_rank"],
            "research_route": row["route"],
            "research_purpose": readiness["research_purpose"],
            "external": bool(target["external_requested"]),
            "planned_tavily_calls": 1 if target["external_requested"] else 0,
            "planned_questions": deepcopy(target["questions"]),
            "planned_query": target.get("search_query"),
            "authority_state": readiness["authority_state"],
            "research_readiness": readiness["research_readiness"],
            "single_candidate_plan": plan,
        })
    external = [item for item in execution if item["external"]]
    next_external, calls = [], 0
    for item in external:
        planned = item["planned_tavily_calls"]
        if len(next_external) >= MAX_EXTERNAL_CANDIDATES_PER_RUN or calls + planned > MAX_TAVILY_CALLS_PER_RUN:
            break
        next_external.append(item)
        calls += planned
    next_ids = {item["candidate_id"] for item in next_external}
    next_execution = [item for item in execution if not item["external"] or item["candidate_id"] in next_ids]
    state_counts = Counter(row["research_status"] for row in selected_rows)
    selected_readiness = [deepcopy(row["research_readiness"]) for row in selected_rows]
    readiness_counts = Counter(row["research_readiness"] for row in selected_readiness)
    current_external = [row for row in selected_rows if row["external_research_required"]]
    from taxonomy_discovery.source_authority import load_source_authority_registry
    authority_rules = load_source_authority_registry(authority_registry_path)
    plan = {
        "bulk_operations_version": BULK_OPERATIONS_VERSION,
        "queue_fingerprint": queue["queue_fingerprint"],
        "current_versions": current_match_versions(),
        "selected_candidate_ids": [row["candidate_id"] for row in selected_rows],
        "selected_count": len(selected_rows),
        "precheck_counts": dict(sorted(state_counts.items())),
        "execution_targets": next_execution,
        "pending_external_candidate_ids": [item["candidate_id"] for item in external if item["candidate_id"] not in next_ids],
        "external_candidates_required": len(current_external),
        "ready_external_candidates": len(external),
        "blocked_by_readiness": len(current_external) - len(external),
        "selected_readiness": selected_readiness,
        "readiness_state_counts": dict(sorted(readiness_counts.items())),
        "readiness_blockers": [{"candidate_id": row["candidate_id"],
                                "research_readiness": row["research_readiness"],
                                "reason": row["blocker_reason"]}
                               for row in selected_readiness if not row["paid_research_eligible"]],
        "query_strategy_exhausted_candidate_ids": exhausted_candidate_ids,
        "external_candidates_next_run": len(next_external),
        "planned_tavily_calls": calls,
        "hard_tavily_call_cap": MAX_TAVILY_CALLS_PER_RUN,
        "maximum_external_candidates_per_run": MAX_EXTERNAL_CANDIDATES_PER_RUN,
        "maximum_queries_per_candidate": MAX_QUERIES_PER_CANDIDATE,
        "maximum_parallelism": MAX_PARALLELISM,
        "network_calls_during_preview": 0,
        "model_calls_during_preview": 0,
        "production_writes_during_preview": 0,
        "authority_rules_version": authority_rules.get("version"),
        "authority_rules_fingerprint": fingerprint(authority_rules),
    }
    plan["plan_fingerprint"] = fingerprint(plan)
    return plan


class _CallBudget:
    def __init__(self, transport):
        self.transport = transport
        self.lock = threading.Lock()
        self.total = 0
        self.completed = 0
        self.by_candidate = Counter()

    def __call__(self, target):
        candidate_id = target["candidate"]["candidate_id"]
        with self.lock:
            if self.total >= MAX_TAVILY_CALLS_PER_RUN:
                raise RuntimeError("Tavily hard call cap reached")
            if self.by_candidate[candidate_id] >= MAX_QUERIES_PER_CANDIDATE:
                raise RuntimeError("Per-candidate Tavily call cap reached")
            self.total += 1
            self.by_candidate[candidate_id] += 1
        response = self.transport(target)
        with self.lock:
            self.completed += 1
        return response


def _systemic(error):
    text = str(error).lower()
    return any(term in text for term in ("auth", "api key", "unauthorized", "forbidden", "knowledge changed", "fingerprint", "stale"))


def _save_run_receipt(receipt, *, db_path):
    from database.taxonomy_discovery_review_manager import _connect, _resolved_path
    with closing(_connect(_resolved_path(db_path), create_parent=True)) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS governed_bulk_operation_runs (
            plan_fingerprint TEXT PRIMARY KEY, receipt_json TEXT NOT NULL, updated_at TEXT NOT NULL)""")
        conn.execute("INSERT OR REPLACE INTO governed_bulk_operation_runs VALUES (?,?,?)",
                     (receipt["plan_fingerprint"], json.dumps(receipt, sort_keys=True), _now()))
        conn.commit()


def load_bulk_run_receipt(plan_fingerprint, *, db_path=None):
    """Read-only receipt reload; a missing database/table remains side-effect free."""
    from database.taxonomy_discovery_review_manager import _resolved_path
    path = _resolved_path(db_path)
    if not path.exists():
        return None
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as conn:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='governed_bulk_operation_runs'").fetchone():
            return None
        row = conn.execute("SELECT receipt_json FROM governed_bulk_operation_runs WHERE plan_fingerprint=?", (plan_fingerprint,)).fetchone()
    return json.loads(row[0]) if row else None


def execute_bulk_plan(plan, candidates, *, explicit_execution=False, transport=None, db_path=None, authority_registry_path=None):
    """Execute local work plus the next bounded external tranche and persist progress."""
    if explicit_execution is not True:
        raise ValueError("Explicit bulk research execution required")
    expected = fingerprint({key: value for key, value in plan.items() if key != "plan_fingerprint"})
    if plan.get("bulk_operations_version") != BULK_OPERATIONS_VERSION or plan.get("plan_fingerprint") != expected:
        raise ValueError("Bulk research plan stale/edited")
    if plan.get("current_versions") != current_match_versions():
        raise ValueError("Bulk research knowledge versions changed")
    from taxonomy_discovery.source_authority import load_source_authority_registry
    if plan.get("authority_rules_fingerprint") != fingerprint(load_source_authority_registry(authority_registry_path)):
        raise ValueError("Bulk research authority readiness changed; prepare the plan again")
    external = [item for item in plan["execution_targets"] if item["external"]]
    from taxonomy_discovery.research_readiness import PAID_RESEARCH_READY_STATES
    if any(item.get("research_readiness") not in PAID_RESEARCH_READY_STATES for item in external):
        raise ValueError("Paid research target did not pass readiness")
    if len(external) > MAX_EXTERNAL_CANDIDATES_PER_RUN or sum(item["planned_tavily_calls"] for item in external) > MAX_TAVILY_CALLS_PER_RUN:
        raise ValueError("Bulk research budget exceeds hard limits")
    if external and transport is None:
        from taxonomy_discovery.governed_research import tavily_transport
        transport = lambda target: tavily_transport(target, explicit_execution=True)
    budget = _CallBudget(transport) if external else None
    by_id = {candidate["candidate_id"]: candidate for candidate in candidates}
    receipt = {
        "bulk_operations_version": BULK_OPERATIONS_VERSION,
        "plan_fingerprint": plan["plan_fingerprint"],
        "started_at": _now(),
        "outcomes": {},
        "calls_attempted": 0,
        "calls_completed": 0,
        "cache_hits": 0,
        "candidates_completed": 0,
        "candidates_failed": 0,
        "candidates_pending": len(plan.get("pending_external_candidate_ids", [])),
        "pending_candidate_ids": list(plan.get("pending_external_candidate_ids", [])),
        "approval": False,
    }
    _save_run_receipt(receipt, db_path=db_path)

    def run(item):
        from taxonomy_discovery.governed_research import execute_plan
        candidate = by_id[item["candidate_id"]]
        result = execute_plan(item["single_candidate_plan"], [candidate], explicit_execution=True,
                              transport=budget if item["external"] else None, db_path=db_path,
                              authority_registry_path=authority_registry_path)
        return item, result

    systemic_failures = 0
    targets = list(plan["execution_targets"])
    local = [item for item in targets if not item["external"]]
    external = [item for item in targets if item["external"]]
    groups = [[item] for item in local] + [external[index:index + MAX_PARALLELISM] for index in range(0, len(external), MAX_PARALLELISM)]
    for group_index, group in enumerate(groups):
        if systemic_failures >= SYSTEMIC_FAILURE_THRESHOLD:
            ids = [item["candidate_id"] for remaining in groups[group_index:] for item in remaining]
            receipt["pending_candidate_ids"].extend(cid for cid in ids if cid not in receipt["pending_candidate_ids"])
            break
        if len(group) == 1 and not group[0]["external"]:
            completed = [(group[0], run(group[0]))]
        else:
            completed = []
            with ThreadPoolExecutor(max_workers=min(MAX_PARALLELISM, len(group))) as executor:
                futures = {executor.submit(run, item): item for item in group}
                for future in as_completed(futures):
                    item = futures[future]
                    try:
                        completed.append((item, future.result()))
                    except Exception as exc:
                        completed.append((item, (item, {"results": [], "failures": [{"candidate_id": item["candidate_id"], "error": str(exc)}]})))
        for item, (_, outcome) in sorted(completed, key=lambda pair: pair[0]["priority_rank"]):
            cid = item["candidate_id"]
            failures = outcome.get("failures", [])
            if failures:
                error = failures[0].get("error", "research failed")
                receipt["outcomes"][cid] = {"status": "failed", "error": error}
                receipt["candidates_failed"] += 1
                systemic_failures += int(_systemic(error))
            else:
                result = outcome["results"][0]
                status = "cached" if result.get("executed_at", "") < receipt["started_at"] else "completed"
                receipt["outcomes"][cid] = {"status": status, "research_result_id": result["research_result_id"]}
                receipt["candidates_completed"] += 1
                receipt["cache_hits"] += int(status == "cached")
            receipt["calls_attempted"] = budget.total if budget else 0
            receipt["calls_completed"] = budget.completed if budget else 0
            _save_run_receipt(receipt, db_path=db_path)
    receipt["candidates_pending"] = len(receipt["pending_candidate_ids"])
    receipt["completed_at"] = _now()
    _save_run_receipt(receipt, db_path=db_path)
    return receipt


def create_bulk_drafts(results, *, selected_result_ids, explicit_creation=False, capability_fields=None,
                       db_path=None, proposal_db_path=None):
    """Explicitly create eligible drafts; capability drafts require supplied human fields."""
    if explicit_creation is not True:
        raise ValueError("Explicit bulk draft creation required")
    from taxonomy_discovery.governed_research import create_draft
    from database.taxonomy_discovery_review_manager import save_governed_research_draft
    by_id = {result["research_result_id"]: result for result in results}
    output = {"created": [], "skipped": [], "failed": []}
    for result_id in selected_result_ids:
        result = by_id.get(result_id)
        if not result:
            output["failed"].append({"result_id": result_id, "error": "unknown result"})
            continue
        if result.get("recommended_next_action") in {"research_more", "no_change", "requirement_decomposition_review"}:
            output["skipped"].append({"result_id": result_id, "reason": result["recommended_next_action"]})
            continue
        fields = (capability_fields or {}).get(result_id)
        if result.get("recommended_next_action") == "new_capability_proposal" and not fields:
            output["skipped"].append({"result_id": result_id, "reason": "manual_capability_fields_required"})
            continue
        try:
            draft = create_draft(result, explicit_creation=True, capability_fields=fields)
            save_governed_research_draft(result, draft, db_path=db_path, proposal_db_path=proposal_db_path)
            output["created"].append({"result_id": result_id, "draft": draft})
        except (ValueError, KeyError, TypeError, OSError, sqlite3.Error) as exc:
            output["failed"].append({"result_id": result_id, "error": str(exc)})
    output["approval"] = False
    return output


def bulk_canary_status():
    """Read-only permanent resolver/registry controls for every batch preview."""
    taxonomy = get_default_taxonomy()
    web = classify_requirement_record({"text": "Knowledge of web services, API, REST, and gRPC"}, taxonomy)
    aws = classify_requirement_record({"text": "Hands-on experience with Amazon Web Services (EC2, Cognito, S3, DynamoDB, etc.)"}, taxonomy)
    cpp = resolve_requirement_text("C++")
    react = resolve_requirement_text("React")
    return {
        "web_services_positive": {"capability_id": (web or {}).get("capability_id"), "safe": (web or {}).get("capability_id") == "backend.api_development"},
        "aws_negative": {"capability_id": (aws or {}).get("capability_id"), "safe": (aws or {}).get("capability_id") != "backend.api_development"},
        "cpp": {"resolution": cpp, "safe": cpp.get("status") == "resolved" and cpp.get("capability_id") == "language.modern_cpp"},
        "react": {"resolution": react, "safe": react.get("status") == "resolved" and react.get("capability_id") == "frontend.ui_development"},
    }


def preview_bulk_regression(corpus, result_drafts):
    """Read-only per-item previews plus a combined overlay where native code supports it."""
    from taxonomy_discovery.governed_research import temporary_impact, knowledge_fingerprint
    items = []
    for item in result_drafts:
        report = temporary_impact(corpus, item["draft"])
        items.append({"result_id": item["result_id"], "draft": deepcopy(item["draft"]), "report": report})
    kinds = {item["draft"]["kind"] for item in items}
    blockers = []
    if len(items) == 1:
        combined = deepcopy(items[0]["report"])
        supported = True
    elif kinds == {"capability"}:
        from taxonomy_discovery.taxonomy_evolution import temporary_regression
        proposals = [item["draft"]["proposal"] for item in items]
        combined = temporary_regression(corpus, proposals)
        combined.update(knowledge_fingerprint=knowledge_fingerprint(), score_increase_is_correctness=False,
                        selected_result_ids=[item["result_id"] for item in items])
        combined.pop("regression_fingerprint", None)
        combined["regression_fingerprint"] = fingerprint(combined)
        supported = True
    else:
        combined = None
        supported = False
        blockers.append("combined_overlay_not_supported_for_selected_artifact_family")
        if len(kinds) > 1:
            blockers.append("mixed_artifact_atomicity_unsupported")
    if combined:
        if combined.get("unexpectedly_changed_requirements"):
            blockers.append("unexpected_requirement_changes")
        if any(job.get("duplicate_credit_violations") for job in combined.get("jobs", [])):
            blockers.append("duplicate_credit_violations")
        if any(job.get("classification") == "hard_regression/invariant_violation" for job in combined.get("jobs", [])):
            blockers.append("hard_regression")
    return {
        "review_only": True,
        "per_item": items,
        "combined": combined,
        "combined_overlay_supported": supported,
        "publication_blockers": sorted(set(blockers)),
        "production_writes": 0,
        "canaries": bulk_canary_status(),
    }


def prepare_publication_tranche(result_ids, *, db_path=None, proposal_db_path=None):
    """Read-only existing publication preflight, grouped and blocked if atomicity is unavailable."""
    from taxonomy_discovery.governed_publication import prepare_publication
    items = [{"result_id": result_id, **prepare_publication(result_id, db_path=db_path, proposal_db_path=proposal_db_path)}
             for result_id in list(dict.fromkeys(result_ids))]
    family_for_kind = {
        "resolver_improvement": "taxonomy",
        "capability": "taxonomy",
        "technology_identity": "technology_registry",
        "technology_relationship": "technology_registry",
    }
    families = {family_for_kind.get(item.get("kind"), item.get("kind")) for item in items if item.get("ready")}
    blockers = [blocker for item in items for blocker in item.get("blockers", [])]
    if len(families) > 1:
        blockers.append("mixed_artifact_atomicity_unsupported_split_tranche_by_family")
    if len(items) > 1:
        blockers.append("native_multi_proposal_single_version_publication_unavailable")
    report = {
        "bulk_operations_version": BULK_OPERATIONS_VERSION,
        "items": items,
        "artifact_families": sorted(family for family in families if family),
        "ready": bool(items) and all(item.get("ready") for item in items) and not blockers,
        "blockers": sorted(set(blockers)),
        "network_calls_required": 0,
        "model_calls_required": 0,
        "all_or_nothing": True,
        "current_versions": current_match_versions(),
    }
    report["preflight_fingerprint"] = fingerprint(report)
    return report


def publish_publication_tranche(preflight, *, explicit_publish=False, db_path=None, proposal_db_path=None):
    """Explicit singleton delegation to the mature idempotent publication/linkage contract."""
    if explicit_publish is not True:
        raise ValueError("Explicit confirmed tranche publication required")
    if preflight.get("preflight_fingerprint") != fingerprint({k: v for k, v in preflight.items() if k != "preflight_fingerprint"}):
        raise ValueError("Publication preflight stale/edited")
    if not preflight.get("ready") or len(preflight.get("items", [])) != 1:
        raise ValueError("Publication tranche is not safely publishable")
    result_id = preflight["items"][0]["result_id"]
    current = prepare_publication_tranche([result_id], db_path=db_path, proposal_db_path=proposal_db_path)
    if current != preflight:
        raise ValueError("Publication preflight changed; run it again")
    from taxonomy_discovery.governed_publication import publish_approved_change
    return publish_approved_change(result_id, explicit_publish=True, db_path=db_path, proposal_db_path=proposal_db_path)

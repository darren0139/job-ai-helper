"""Impact-first orchestration of native maintenance contracts; no knowledge engine."""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import hashlib
import json

from taxonomy_discovery import maintenance_service as maintenance
from taxonomy_discovery import governed_research as research
from taxonomy_discovery import bulk_candidate_operations as bulk
from database import taxonomy_discovery_review_manager as store
from taxonomy_discovery.corpus_expansion import fingerprint

ASSISTANT_VERSION = "taxonomy-gap-reduction-assistant-v1"
TERMINAL = {"NEEDS_SCOPE_REFINEMENT", "RESEARCH_EXHAUSTED", "BLOCKED_EVIDENCE_INSUFFICIENT", "DEFERRED"}
DEFAULT_OPTIONS = {"include_local": True, "include_research": True, "include_scope": True, "calculate_impact": True}


def _dependency_projection(snapshot, actions, gap_rows, unresolved, links):
    """Read-only graph projection of native routes, not a dependency inference engine.

    Shared provenance establishes diagnostic association. Only native ALL/ANY
    structure establishes list mode; no prerequisite capability is invented.
    """
    from tailoring.phase6d6_structured_matching import technology_requirement_structure
    by_candidate = {r["candidate_id"]: r for r in gap_rows}
    by_action = {a["action_id"]: a for a in actions}
    raw = {(j["job_id"], r["requirement_id"]): r for j in snapshot["audit"]["corpus"]["jobs"]
           for r in j["baseline_stable_analysis"].get("canonical_requirements", [])}
    requirements = {(r["job_id"], r["requirement_id"]): r for r in unresolved}
    graphs, bundle_groups, family_groups = [], {}, {}
    for a in actions:
        a.setdefault("mentioned_requirements", a["requirements_affected"])
        a.setdefault("atomically_addressable_requirements", 0)
        a.setdefault("estimated_directly_resolvable", 0)
        a.setdefault("validated_resolved", None)
        a.update(unique_requirements=len({(r["job_id"], r["requirement_id"]) for r in a["requirement_keys"]}),
                 dependency_ids=[], dependent_requirement_count=0, shared_requirement_keys=[], bundle_ids=[])
        a["impact_role"] = ("FOUNDATIONAL" if a["fix_layer"] == maintenance.IDENTITY_GAP else
            "TERMINAL_REVIEW" if a["fix_layer"] in {maintenance.MANUAL, maintenance.NOISE}
                or a["research_state"] in TERMINAL else "DEPENDENCY")
        # A ready native governed draft is still review work here. No direct
        # count is fabricated from its corpus mentions or research eligibility.
        a["direct_impact_state"] = "requires_temporary_validation"
    for key, r in sorted(requirements.items()):
        related = sorted(links.get(key, []), key=lambda a: a["action_id"])
        structure = technology_requirement_structure(raw.get(key) or {"text": r["requirement_text"], "importance": r["importance"]})
        nodes = [{"dependency_id": a["action_id"], "candidate_id": a["candidate_id"],
            "fix_layer": "NEEDS_DECOMPOSITION" if a["research_state"] == maintenance.NEEDS_DECOMPOSITION else a["fix_layer"],
            "concept": a["concept"], "impact_role": a["impact_role"],
            "native_route": (by_candidate[a["candidate_id"]].get("candidate") or {}).get("operational_route"),
            "native_reason": by_candidate[a["candidate_id"]]["reason"],
            "research_parent_candidate_id": by_candidate[a["candidate_id"]].get("parent_candidate_id")}
            for a in related]
        graph_id = "gapdependency_" + fingerprint(key)[:24]
        graph = {"graph_id": graph_id, "job_id": key[0], "requirement_id": key[1],
            "requirement_text": r["requirement_text"], "current_resolution": r["current_resolution"],
            "native_structure": structure, "nodes": nodes,
            "edges": [{"from": graph_id, "to": n["dependency_id"], "relation": "native_gap_route_diagnostic"} for n in nodes],
            "list_mode": structure["mode"], "joint_blockers_proven": False,
            "association_semantics": "native_list_" + structure["mode"] if structure["mode"] else "co_occurring_native_diagnostics_not_proven_all",
            "residual_boundary": "Identity/component recognition alone supplies no approved capability relationship or parent resolution",
            "validated_resolved": None}
        graphs.append(graph)
        active_ids = tuple(n["dependency_id"] for n in nodes if n["impact_role"] != "TERMINAL_REVIEW")
        if len(active_ids) > 1:
            bundle_groups.setdefault(active_ids, []).append(key)
        for a in related:
            companions = [b["action_id"] for b in related if b["action_id"] != a["action_id"]]
            a["dependency_ids"] = sorted(set(a["dependency_ids"]) | set(companions))
            if companions:
                a["shared_requirement_keys"].append({"job_id": key[0], "requirement_id": key[1]})
            if a["research_state"] == maintenance.NEEDS_DECOMPOSITION or a["fix_layer"] == maintenance.PARSING_PROBLEM:
                family = structure["source"]
                entry = family_groups.setdefault(family, {"keys": set(), "action_ids": set(), "downstream_ids": set(), "sources": set()})
                entry["keys"].add(key); entry["action_ids"].add(a["action_id"])
                entry["downstream_ids"].update(b["action_id"] for b in related if b["fix_layer"] in {maintenance.IDENTITY_GAP, maintenance.CAPABILITY_GAP, maintenance.RELATIONSHIP_GAP})
                entry["sources"].add((by_candidate[a["candidate_id"]].get("candidate") or {}).get("operational_route"))
    def metrics(keys):
        keys = sorted(set(keys))
        return {"unique_unresolved_requirements": len(keys),
            "requirement_keys": [{"job_id": k[0], "requirement_id": k[1]} for k in keys],
            "required_core_weight": round(sum(maintenance.gaps._weight(requirements[k]) for k in keys
                if requirements[k]["importance"] in {"required", "core", "deal_breaker"}), 6),
            "jobs_affected": len({k[0] for k in keys})}
    bundles = []
    for ids, keys in sorted(bundle_groups.items()):
        bid = "gapbundle_" + fingerprint(ids)[:24]
        bundles.append({"bundle_id": bid, "dependency_ids": list(ids), "impact_role": "DEPENDENCY",
            **metrics(keys), "estimated_directly_resolvable": 0, "validated_resolved": None,
            "state": "joint_review_and_temporary_validation_required",
            "why": "Native diagnostics share source requirements; this is a review bundle, not proof that all nodes are semantically mandatory"})
        for aid in ids:
            by_action[aid]["bundle_ids"].append(bid)
    families = [{"family_id": "gapparser_" + fingerprint(name)[:24], "family": name, **metrics(f["keys"]),
        "dependency_ids": sorted(f["action_ids"]), "downstream_action_ids": sorted(f["downstream_ids"]),
        "downstream_actions_unlocked_for_review": len(f["downstream_ids"]),
        "native_routes": sorted(s for s in f["sources"] if s),
        "native_component_identity_handled": name in {"native_jd_decomposition", "native_structured_match", "native_structured_alternatives"},
        "code_change_required": False if name in {"native_jd_decomposition", "native_structured_match", "native_structured_alternatives"} else None,
        "code_change_diagnostic": "Native component identity already handled; parent/capability review remains" if name in {"native_jd_decomposition", "native_structured_match", "native_structured_alternatives"} else "Native scope/parser diagnosis required; no automatic parser patch inferred",
        "impact_role": "DEPENDENCY", "estimated_directly_resolvable": 0, "validated_resolved": None}
        for name, f in sorted(family_groups.items())]
    priority = lambda v: (-v["required_core_weight"], -v["unique_unresolved_requirements"], -v["jobs_affected"],
        -v.get("downstream_actions_unlocked_for_review", 0), v.get("family_id", v.get("bundle_id", "")))
    families.sort(key=priority); bundles.sort(key=priority)
    foundational = [a for a in actions if a["impact_role"] == "FOUNDATIONAL"]
    seen = set()
    for index, a in enumerate(foundational, 1):
        keys = {(r["job_id"], r["requirement_id"]) for r in a["requirement_keys"]} & requirements.keys()
        a["foundational_rank"] = index
        a["marginal_mentioned_requirements"] = len(keys - seen)
        a["marginal_directly_resolvable"] = 0
        a["dependent_requirement_count"] = len(a["shared_requirement_keys"])
        a["unlocks_dependency_bundles"] = len(a["bundle_ids"])
        seen.update(keys)
    for a in actions:
        a["dependent_requirement_count"] = len(a["shared_requirement_keys"])
        a["dependency_meaning"] = "shared native remediation diagnostics; conditional list semantics retained, not automatic execution prerequisites"
    direct_priority = sorted([{"kind": "parser_family", **f} for f in families] + [{"kind": "review_bundle", **b} for b in bundles], key=priority)
    marginal_seen = set()
    for rank, item in enumerate(direct_priority, 1):
        keys = {(r["job_id"], r["requirement_id"]) for r in item["requirement_keys"]}
        item["priority_rank"] = rank
        item["marginal_blocked_requirements"] = len(keys - marginal_seen)
        item["marginal_directly_resolvable"] = 0
        marginal_seen.update(keys)
    return {"requirement_dependency_graphs": graphs, "dependency_bundles": bundles,
        "decomposition_parser_bottlenecks": families, "foundational_priority": foundational,
        "direct_gap_reduction_priority": direct_priority, "directly_resolving_actions": [],
        "dependency_impact_summary": {"unique_unresolved_requirements": len(requirements),
            "unique_identity_mentioned_unresolved_requirements": len(seen),
            "shared_identity_requirements": sum(sum(a["fix_layer"] == maintenance.IDENTITY_GAP for a in links.get(k, [])) > 1 for k in requirements),
            "unique_bundle_requirement_union": len(set(k for keys in bundle_groups.values() for k in keys)),
            "estimated_directly_resolvable": 0, "validated_resolved": None,
            "counts_are_blocked_review_opportunities_not_expected_resolutions": True}}


def _saved_identity(rows):
    return fingerprint(sorted([{"id": r["result"]["research_result_id"],
        "result": fingerprint(r["result"]), "draft": fingerprint(r.get("draft")),
        "review": r.get("review")} for r in rows], key=lambda r: r["id"]))


def _history(candidate, saved):
    records = []
    for row in saved:
        try:
            value = row["result"]
            research._validate_saved_integrity(value)
            if research.compatible_saved_candidate(candidate, value["candidate"]):
                records.append(value)
        except (ValueError, KeyError, TypeError):
            continue
    # Local reinterpretations are not new provider calls or research rounds.
    requests = {}
    for result in sorted(records, key=lambda r: (r.get("re_evaluated_at") or r["executed_at"], r["research_result_id"])):
        if result["research"]["target"].get("external_requested"):
            requests[result["provider_request_id"]] = result
    ordered = sorted(requests.values(), key=lambda r: (int(r["research"]["target"].get("research_round", 0)), r["executed_at"]))
    rounds = max((int(r["research"]["target"].get("research_round", 0)) + 1 for r in ordered), default=0)
    # The native round ceiling also captures historical attempts not present as separate requests.
    used = max(len(requests), rounds)
    return ordered, used, max(0, bulk.MAX_QUERIES_PER_CANDIDATE - used), rounds


def _support(result):
    bundle = (result or {}).get("support_bundle") or {}
    supported = sorted(f for f, value in bundle.get("fields", {}).items() if value.get("status") == "supported")
    missing = sorted(f for f, value in bundle.get("fields", {}).items() if value.get("status") != "supported")
    return bundle, supported, missing


def _research_state(row, saved, required_weight):
    c = row.get("candidate")
    base = {"research_state": "FIX_LAYER_REQUIRED", "calls_used": 0, "calls_remaining": 0,
        "research_round": 0, "round_number": 0, "maximum_rounds": bulk.MAX_QUERIES_PER_CANDIDATE,
        "current_missing_evidence": [], "previous_missing_evidence": [], "new_support_gained": [],
        "supported_semantic_fields": [], "missing_semantic_fields": [], "selected_result_id": None,
        "next_query": None, "provider_calls_required": 0, "local_action_available": False,
        "next_action_reason": row["reason"], "proposed_action": row["next_action"],
        "reactivation_event": "Human-reviewed fix-layer change or new corpus evidence"}
    if ((c or {}).get("operational_route") == "needs_decomposition"
            or row.get("boundary_state") == maintenance.NEEDS_DECOMPOSITION
            or (row.get("parent_candidate_id") and row["fix_layer"] == maintenance.CAPABILITY_GAP)):
        return {**base, "research_state": maintenance.NEEDS_DECOMPOSITION,
                "proposed_action": "Send to Decomposition Review"}
    if row["fix_layer"] != maintenance.CAPABILITY_GAP or not c:
        return base
    selection = research.select_saved_interpretation(c, saved)
    history, used, remaining, rounds = _history(c, saved)
    chosen = selection["primary"]
    result = chosen["result"] if chosen else None
    bundle, supported, missing = _support(result)
    previous = next((v for v in reversed(history) if result and v["provider_request_id"] != result["provider_request_id"]), None)
    previous_bundle, previous_supported, _ = _support(previous)
    base.update(calls_used=used, calls_remaining=remaining, research_round=rounds,
        round_number=rounds, selected_result_id=result["research_result_id"] if result else None,
        current_missing_evidence=bundle.get("missing_evidence", []),
        previous_missing_evidence=previous_bundle.get("missing_evidence", []),
        supported_semantic_fields=supported, missing_semantic_fields=missing,
        new_support_gained=sorted(set(supported) - set(previous_supported)))
    def outcome(state, reason, action="Human scope / fix-layer review"):
        return {**base, "research_state": state, "next_action_reason": reason, "proposed_action": action}
    if selection["ambiguous"]:
        return outcome("BLOCKED_EVIDENCE_INSUFFICIENT", selection["reason"])
    if row["review_status"] in {"reject", "defer"} or row["publication_status"] == "published":
        return outcome("DEFERRED", "Existing governance decision; no further research")
    if result and not selection["current"]:
        value = outcome("FIX_LAYER_REQUIRED", "Saved interpretation needs explicit local refresh", "Refresh saved evidence locally")
        value["local_action_available"] = True
        return value
    if result and result.get("review_eligible") and result.get("proposal_eligible"):
        return outcome("ELIGIBLE_FOR_HUMAN_REVIEW", "Current governed support; draft/review remains explicit", "Inspect / review governed evidence")
    if used and not remaining:
        return outcome("RESEARCH_EXHAUSTED", "Native research-round ceiling reached", "Defer pending new scope or reviewed source evidence")
    if row.get("boundary_state") != maintenance.RESEARCH_READY:
        return outcome("NEEDS_SCOPE_REFINEMENT", row.get("boundary_reason", "Native scope/coherence unresolved"))
    if bundle.get("conflicts"):
        return outcome("NEEDS_SCOPE_REFINEMENT", "Governed semantic/overlap conflicts require human scope review")
    repeated = bool(previous and bundle and bundle.get("missing_evidence") == previous_bundle.get("missing_evidence")
                    and not base["new_support_gained"])
    broad = bool(result and supported and {"definition", "boundaries"} <= set(missing))
    if broad or repeated:
        return outcome("NEEDS_SCOPE_REFINEMENT", "Repeated partial support or unresolved definition/boundaries; refine scope before further calls")
    if required_weight == 0 and len(row.get("job_ids", [])) <= 1:
        return outcome("DEFERRED", "Preferred-only single-job gap; low safe corpus benefit does not justify an external call")
    if not row.get("readiness", {}).get("paid_research_eligible"):
        return outcome("BLOCKED_EVIDENCE_INSUFFICIENT", "Native governed readiness blocks paid research")
    native = bulk.prepare_bulk_plan([c], selected_candidate_ids=[c["candidate_id"]], saved_rows=saved, publications=[])
    target = next(iter(native["execution_targets"]), None)
    if not target or not target["external"]:
        return outcome("BLOCKED_EVIDENCE_INSUFFICIENT", "No executable bounded native research target")
    query = target.get("planned_query") or " ".join(target.get("planned_questions", []))
    prior_queries = {" ".join(q.lower().split()) for r in history for q in r["research"]["target"].get("questions", [])}
    if not query or " ".join(query.lower().split()) in prior_queries:
        return outcome("RESEARCH_EXHAUSTED", "No materially new bounded native query; do not repeat calls")
    if result and (result.get("next_research_plan") or {}).get("call_budget") == 0:
        return outcome("RESEARCH_EXHAUSTED", "Saved missing-evidence plan has no remaining call budget")
    value = outcome("TARGETED_RESEARCH_AVAILABLE" if result else "RESEARCH_READY",
        "One new native bounded query justified; impact and run budget still govern selection", "Preview bounded governed research")
    value.update(next_query=query, provider_calls_required=target["planned_tavily_calls"])
    return value


def build_plan(snapshot, *, max_actions=10, research_budget=3, options=None, selected_research_ids=None,
               db_path=None, review_db_path=None, transport=None):
    """Pure dry-run, reusing an exact current native audit. No drafts or calls."""
    maintenance._require_current(snapshot, db_path)
    if type(max_actions) is not int or not 1 <= max_actions <= bulk.MAX_WORKING_BATCH:
        raise ValueError("Maximum actions must be 1 to 25")
    if type(research_budget) is not int or not 0 <= research_budget <= bulk.MAX_TAVILY_CALLS_PER_RUN:
        raise ValueError("Research budget must be 0 to 20")
    options = {**DEFAULT_OPTIONS, **(options or {})}
    if set(options) != set(DEFAULT_OPTIONS) or any(type(v) is not bool for v in options.values()):
        raise ValueError("Invalid assistant options")
    saved = store.list_governed_research_results(db_path=review_db_path)
    pubs = maintenance.publication.list_publications(db_path=review_db_path)
    # Reconcile changed saved research without replaying normalization/scoring.
    gap_rows = maintenance.list_gap_rows(deepcopy(snapshot["audit"]), saved_rows=saved, publications=pubs)
    noise_keys = set().union(*(maintenance.gaps._route_requirement_keys(q) for q in snapshot["audit"]["queue"]
        if q["operational_route"] == "noise_or_non_capability" and not q.get("parent_candidate_id")))
    actions = []
    for row in gap_rows:
        reqs = {(r["job_id"], r["requirement_id"]): r for r in row["requirements"]}
        technical = [r for k, r in reqs.items() if r["score_eligible"] and k not in noise_keys and row["fix_layer"] != maintenance.NOISE]
        core = sum(maintenance.gaps._weight(r) for r in technical if r["importance"] in {"required", "core", "deal_breaker"})
        other = sum(maintenance.gaps._weight(r) for r in technical if r["importance"] not in {"required", "core", "deal_breaker"})
        unresolved_core = sum(maintenance.gaps._weight(r) for r in technical
            if r["current_resolution"]["status"] != "resolved" and r["importance"] in {"required", "core", "deal_breaker"})
        unresolved_total = sum(maintenance.gaps._weight(r) for r in technical if r["current_resolution"]["status"] != "resolved")
        state = _research_state(row, saved, core)
        action = {"action_id": "gapaction_" + fingerprint({"candidate": row["candidate_id"], "layer": row["fix_layer"]})[:24],
            "candidate_id": row["candidate_id"], "concept": row["concept"], "fix_layer": row["fix_layer"],
            "requirements_affected": len(reqs), "meaningful_technical_requirements_affected": len(technical),
            "unresolved_requirements_affected": sum(r["current_resolution"]["status"] != "resolved" for r in technical), "requirement_ids": sorted({key[1] for key in reqs}),
            "requirement_keys": [{"job_id": k[0], "requirement_id": k[1]} for k in sorted(reqs)],
            "jobs_affected": len({k[0] for k in reqs}), "job_ids": sorted({k[0] for k in reqs}),
            "importance_distribution": dict(Counter(r["importance"] for r in reqs.values())),
            "required_core_weight": round(core, 6), "preferred_weight": round(other, 6),
            "unresolved_required_core_weight": round(unresolved_core, 6), "unresolved_weight": round(unresolved_total, 6),
            "weighted_impact": round(core + other, 6), "impact_kind": "estimated_addressable_weight",
            "observed_jd_phrases": sorted({r["requirement_text"] for r in reqs.values()}),
            "existing_taxonomy_overlaps": (row.get("candidate") or {}).get("overlap", {}),
            "scope_questions": ["Is this one bounded reusable behavior?", "Which observed components need separate scope review?"],
            "risk_flags": [row["boundary_reason"]] if row["boundary_state"] != maintenance.RESEARCH_READY else [],
            "estimated_effort": "bounded external research" if state["provider_calls_required"] else "human/local review",
            **state}
        action["priority_reason"] = (f"Unresolved required/core weight {unresolved_core:g}; unresolved weight {unresolved_total:g}; addressable required/core weight {core:g}; total weight {core + other:g}; "
            f"{action['jobs_affected']} jobs / {len(reqs)} requirements; " + state["next_action_reason"] + "; estimated, not validated resolution")
        if row["fix_layer"] == maintenance.IDENTITY_GAP:
            from tailoring.phase6d6_structured_matching import technology_requirement_structure
            from taxonomy_discovery.technology_registry import _candidate_terms, normalise
            aliases = {normalise(t) for t in (row["candidate"].get("technology_terms") or [row["concept"]])}
            addressable = []
            for k, r in reqs.items():
                text = r["requirement_text"]
                structure = technology_requirement_structure({"text": text, "importance": r["importance"], "score_eligible": r["score_eligible"]})
                focuses = [c["atomic_focus"] for c in structure["components"]] or [text]
                if any(aliases.intersection(normalise(t) for t in _candidate_terms(f)) for f in focuses):
                    addressable.append({"job_id": k[0], "requirement_id": k[1]})
            action.update(mentioned_requirements=len(reqs), atomically_addressable_requirements=len(addressable),
                atomically_addressable_requirement_keys=addressable, estimated_directly_resolvable=0,
                validated_resolved=None, impact_kind="foundational_identity_mentions")
            action["priority_reason"] = action["priority_reason"].replace("addressable required/core weight", "mentioned required/core weight")
            action["priority_reason"] += f"; {len(addressable)} natively addressable; foundational identity dependency; zero estimated direct capability resolutions; decomposition may be required"
        actions.append(action)
    key = lambda a: (-a["unresolved_required_core_weight"], -a["unresolved_weight"],
        -a["required_core_weight"], -a["weighted_impact"], -a["jobs_affected"],
        -a["requirements_affected"], a["provider_calls_required"], len(a["risk_flags"]), a["action_id"])
    actions.sort(key=key if options["calculate_impact"] else lambda a: a["action_id"])
    for index, action in enumerate(actions, 1):
        action["rank"] = index
    enabled = [a for a in actions if (options["include_research"] if a["provider_calls_required"] else
        options["include_scope"] if a["research_state"] in TERMINAL | {maintenance.NEEDS_DECOMPOSITION} else options["include_local"])]
    top = enabled[:max_actions]
    eligible = [a for a in top if a["research_state"] in {"RESEARCH_READY", "TARGETED_RESEARCH_AVAILABLE"}]
    if selected_research_ids is not None:
        if len(set(selected_research_ids)) != len(selected_research_ids) or not set(selected_research_ids) <= {a["candidate_id"] for a in eligible}:
            raise ValueError("Select distinct eligible research actions from this ranked plan")
        eligible = [a for a in eligible if a["candidate_id"] in selected_research_ids]
    selected, calls = [], 0
    for action in eligible:
        if calls + action["provider_calls_required"] <= research_budget and len(selected) < bulk.MAX_EXTERNAL_CANDIDATES_PER_RUN:
            selected.append(action["candidate_id"]); calls += action["provider_calls_required"]
    candidates = {r["candidate_id"]: r for r in gap_rows}
    tranche = maintenance._seal({"audit_fingerprint": snapshot["audit_fingerprint"],
        "targets": [candidates[cid] for cid in selected]}, "tranche_fingerprint")
    native = maintenance.plan_research(snapshot, tranche, selected, db_path=db_path,
        review_db_path=review_db_path, transport=transport) if selected else None
    links = {}
    for action in actions:
        for key in action["requirement_keys"]:
            links.setdefault((key["job_id"], key["requirement_id"]), []).append(action)
    unresolved = [r for r in snapshot["audit"]["requirements"] if r["score_eligible"]
        and (r["job_id"], r["requirement_id"]) not in noise_keys and r["current_resolution"]["status"] != "resolved"]
    routing = [{"job_id": r["job_id"], "requirement_id": r["requirement_id"],
        "action_ids": [a["action_id"] for a in links.get((r["job_id"], r["requirement_id"]), [])],
        "fix_layers": sorted({a["fix_layer"] for a in links.get((r["job_id"], r["requirement_id"]), [])})}
        for r in sorted(unresolved, key=lambda r: (r["job_id"], r["requirement_id"]))]
    summary = snapshot["audit"]["summary"]
    baseline = {"technical_requirements": summary["meaningful_technical_requirements"],
        "resolved": summary["taxonomy_resolved_requirements"], "unresolved": summary["taxonomy_unresolved_requirements"],
        "required_core_weighted_coverage": summary["required_core_weighted_coverage"],
        "overall_weighted_coverage": summary["overall_weighted_coverage"]}
    identity_keys = {(r["job_id"], r["requirement_id"]) for a in actions if a["fix_layer"] == maintenance.IDENTITY_GAP for r in a["requirement_keys"]}
    dependencies = _dependency_projection(snapshot, actions, gap_rows, unresolved, links)
    return maintenance._seal({"assistant_version": ASSISTANT_VERSION,
        "assistant_implementation_fingerprint": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "audit_identity": snapshot["manifest"], "audit_fingerprint": snapshot["audit_fingerprint"],
        "saved_research_fingerprint": _saved_identity(saved), "publication_fingerprint": fingerprint(pubs),
        "interpretation_version": research.INTERPRETATION_VERSION, "options": options,
        "max_actions": max_actions, "research_budget": research_budget, "selected_research_ids": selected_research_ids,
        **dependencies, "baseline": baseline, "identity_impact_summary": {
            "unique_mentioned_requirement_keys": [dict(job_id=k[0], requirement_id=k[1]) for k in sorted(identity_keys)],
            "unique_mentioned_requirements": len(identity_keys),
            "estimated_directly_resolvable": 0, "validated_resolved": None,
            "overlapping_mentions_are_not_additive_direct_impact": True},
        "routing_summary": dict(Counter(a["fix_layer"] for a in actions)),
        "ranked_actions": top, "all_actions": actions,
        "unresolved_requirement_routing": routing,
        "unrouted_unresolved_requirement_keys": [{"job_id": r["job_id"], "requirement_id": r["requirement_id"]} for r in routing if not r["action_ids"]],
        "research_plan": native, "research_tranche": tranche, "planned_external_calls": calls,
        "deferred_actions": [a for a in actions if a["research_state"] == "DEFERRED"],
        "terminal_actions": [a for a in actions if a["research_state"] in TERMINAL],
        "validation_results": [], "potential_gap_delta": {"validated": False, "newly_resolved": None,
            "reason": "Addressable requirement weight is an estimate; no overlay ran"},
        "warnings": (["No high-value eligible capability research action; continue local/fix-layer/scope review"] if not selected else []) + ["Job Match Health and Taxonomy Knowledge remain separate", "Action families can share requirements; do not sum estimated affected counts"],
        "next_actions": [a["proposed_action"] for a in top], "provider_calls": 0,
        "model_calls": 0, "production_writes": 0, "automatic_approval": False, "automatic_publication": False},
        "assistant_plan_fingerprint")


def validate_plan(snapshot, plan, confirmed_fingerprint, *, db_path=None, review_db_path=None, transport=None):
    maintenance._intact(plan, "assistant_plan_fingerprint")
    if not confirmed_fingerprint or confirmed_fingerprint != plan["assistant_plan_fingerprint"]:
        raise ValueError("Confirm the exact assistant plan fingerprint")
    fresh = build_plan(snapshot, max_actions=plan["max_actions"], research_budget=plan["research_budget"],
        options=plan["options"], selected_research_ids=plan["selected_research_ids"], db_path=db_path,
        review_db_path=review_db_path, transport=transport)
    if fresh["assistant_plan_fingerprint"] != confirmed_fingerprint:
        raise ValueError("Assistant plan changed; re-preview before execution")


def execute_plan(snapshot, plan, *, confirmed_fingerprint=None, explicit_execution=False,
                 allow_external_research=False, db_path=None, review_db_path=None, transport=None):
    if explicit_execution is not True:
        raise ValueError("Explicit assistant execution required")
    validate_plan(snapshot, plan, confirmed_fingerprint, db_path=db_path, review_db_path=review_db_path, transport=transport)
    if plan["planned_external_calls"] and not allow_external_research:
        raise ValueError("Explicit external-research confirmation required")
    receipt = {"assistant_plan_fingerprint": confirmed_fingerprint, "local_refreshes": [], "research": None,
               "automatic_approval": False, "automatic_publication": False, "drafts_created": 0, "production_writes": 0}
    # Execute external tranche before refreshes, which change saved-research currentness.
    if plan["research_plan"]:
        receipt["research"] = maintenance.execute_research(snapshot, plan["research_tranche"],
            plan["research_plan"]["selected_candidate_ids"], explicit_execution=True,
            confirmed_plan_fingerprint=plan["research_plan"]["plan_fingerprint"], db_path=db_path,
            review_db_path=review_db_path, transport=transport)
    for action in plan["ranked_actions"]:
        if action["local_action_available"]:
            value = maintenance.refresh_saved_research(snapshot, action["candidate_id"], explicit_execution=True,
                db_path=db_path, review_db_path=review_db_path)
            receipt["local_refreshes"].append(value["research_result_id"])
    return receipt


def validate_drafts(snapshot, plan, result_ids, *, confirmed_fingerprint=None, explicit_execution=False,
                    db_path=None, review_db_path=None):
    if explicit_execution is not True:
        raise ValueError("Explicit temporary validation required")
    validate_plan(snapshot, plan, confirmed_fingerprint, db_path=db_path, review_db_path=review_db_path)
    eligible = {a["selected_result_id"] for a in plan["all_actions"] if a["research_state"] == "ELIGIBLE_FOR_HUMAN_REVIEW"}
    if not result_ids or not set(result_ids) <= eligible:
        raise ValueError("Current governed eligible saved drafts required")
    # Review preview is explicitly unapproved; native draft/currentness gates still apply.
    return maintenance.run_candidate_validation(snapshot, result_ids, explicit_execution=True, approved=False,
        db_path=db_path, review_db_path=review_db_path)


def markdown_report(plan):
    b = plan["baseline"]
    lines = ["# Taxonomy Gap Reduction Assistant", "", f"Resolved: {b['resolved']}; unresolved: {b['unresolved']}; technical: {b['technical_requirements']}",
        f"Required/core coverage: {b['required_core_weighted_coverage']['percent']}%; overall: {b['overall_weighted_coverage']['percent']}%", "",
        "Estimated addressable impact; no validated gap reduction or score uplift claimed.", "",
        "| Rank | Concept | Fix layer | Requirements | Jobs | State | Calls |", "|---|---|---|---:|---:|---|---:|"]
    for a in plan["ranked_actions"]:
        lines.append(f"| {a['rank']} | {a['concept'].replace('|', '/')} | {a['fix_layer']} | {a['requirements_affected']} | {a['jobs_affected']} | {a['research_state']} | {a['provider_calls_required']} |")
    lines += ["", "## Identity impact (foundational mentions, not direct resolution gains)", "",
        "| Concept | Mentioned | Natively addressable | Estimated directly resolvable | Validated resolved |",
        "|---|---:|---:|---:|---|"]
    for a in plan["ranked_actions"]:
        if a["fix_layer"] == maintenance.IDENTITY_GAP:
            lines.append(f"| {a['concept']} | {a['mentioned_requirements']} | {a['atomically_addressable_requirements']} | {a['estimated_directly_resolvable']} | Not validated |")
    lines += ["", f"Unique identity-mentioned requirements across the full plan: {plan['identity_impact_summary']['unique_mentioned_requirements']}. Overlapping mentions are not additive direct impact."]
    lines += ["", "## Foundational priority", "", "Foundational does not mean directly resolving.", "",
        "| Priority | Concept | Mentions | Addressable | Direct estimate | Bundles |", "|---|---|---:|---:|---:|---:|"]
    for a in plan["foundational_priority"][:plan["max_actions"]]:
        lines.append(f"| {a['foundational_rank']} | {a['concept']} | {a['mentioned_requirements']} | {a['atomically_addressable_requirements']} | {a['estimated_directly_resolvable']} | {a['unlocks_dependency_bundles']} |")
    lines += ["", "## Direct / bundle review priority", "", "No direct resolution is claimed without temporary validation.", "",
        "| Priority | Kind | Family/bundle | Unique blocked | Core weight | Direct estimate |", "|---|---|---|---:|---:|---:|"]
    for item in plan["direct_gap_reduction_priority"][:plan["max_actions"]]:
        lines.append(f"| {item['priority_rank']} | {item['kind']} | {item.get('family', item.get('bundle_id'))} | {item['unique_unresolved_requirements']} | {item['required_core_weight']} | {item['estimated_directly_resolvable']} |")
    lines += ["", "Dependency impact union:", "```json", json.dumps(plan["dependency_impact_summary"], indent=2), "```"]
    lines += ["", "## Terminal / deferred", ""]
    lines += [f"- {a['concept']}: {a['research_state']} — {a['next_action_reason']}" for a in plan["terminal_actions"]]
    lines += ["", "Plan fingerprint: " + plan["assistant_plan_fingerprint"], "No automatic approval/publication. Research requires separate exact-plan confirmation."]
    return "\n".join(lines)

"""Read-only assistant diagnostics over native parsing; never a replacement parser."""
from copy import deepcopy
import re

from analysis_stability import stable_evidence_scoring as scoring
from taxonomy_discovery import maintenance_service as maintenance
from taxonomy_discovery.corpus_expansion import fingerprint
from taxonomy_discovery.technology_registry import resolve_requirement_text


def diagnose(requirement):
    """Recompute native probes without turning diagnostic terms into scoring rows."""
    text = requirement.get("atomic_focus") or requirement.get("text", "")
    surface = scoring._normalise_requirement_surface(text)
    probes = {
        "coherent_parent": scoring._preserves_coherent_parent(surface),
        "example_or_one_of_marker": bool(scoring._EXAMPLE_OR_ALTERNATIVE_INTRODUCER.search(surface)),
        "bounded_named_terms": scoring._split_bounded_named_terms(surface),
        "shared_head_and_list": scoring._split_shared_head_and_list(surface),
        "independent_and_pair": scoring._split_safe_independent_and_pair(surface),
        "non_requirement_reason": scoring._classify_non_requirement_row(surface),
    }
    clauses = scoring._split_single_requirement_clause(text, requirement.get("importance", "core"))
    # These delimiters diagnose scope only. They never establish mandatory
    # components, relationships, evidence completeness, or scoring allocation.
    alternative = bool(re.search(r"\b(?:or|equivalent|one or more)\b|/", surface, re.I))
    coordinated = bool(re.search(r"\b(?:and|along with|as well as)\b|[,;&]", surface, re.I))
    wrapper = re.match(r"^(?:proficient|proficiency|knowledge|experience|familiarity|skills?)\s+(?:in|of|with|using)\s+(.+)$", surface, re.I)
    terms = [p.strip(" ,;:.-") for p in re.split(r",|\band\b", wrapper.group(1), flags=re.I)] if wrapper else []
    bounded = len(terms) >= 2 and all(scoring._is_bounded_named_term(p) for p in terms)
    bare_terms = [p.strip(" ,;:.-") for p in re.split(r",|\band\b", surface, flags=re.I)]
    bare_bounded = 2 <= len(bare_terms) <= 10 and all(scoring._is_bounded_named_term(p) for p in bare_terms)
    # A presentation probe is explicitly counterfactual, diagnostic only.
    # No stripped text is passed back to the resolver or scorer.
    presentation = re.sub(r"^[\u00b7\u2022*-]+\s*", "", surface)
    presentation_wrapper = re.match(r"^(?:proficient|proficiency|knowledge|experience|familiarity|skills?)\s+(?:in|of|with|using)\s+(.+)$", presentation, re.I)
    presentation_terms = [p.strip(" ,;:.-") for p in re.split(r",|\band\b", presentation_wrapper.group(1), flags=re.I)] if presentation_wrapper else []
    presentation_bounded = presentation != surface and len(presentation_terms) >= 2 and all(scoring._is_bounded_named_term(p) for p in presentation_terms)
    probes["diagnostic_presentation_prefix"] = {"changed": presentation != surface, "bounded_named_tail_after_prefix": presentation_bounded,
        "basis": "Diagnostic surface check only; not a canonicalisation correction or native parser result"}
    parents = [p.get("raw_parent_text", "") for p in requirement.get("source_provenance", [])]
    parent_coherent = any(scoring._preserves_coherent_parent(p) for p in parents)
    punctuation_boundary = any(surface.lower().startswith(m.group(1).lower() + " ")
        for p in parents for m in re.finditer(r"(?<!\w)\.([A-Za-z][A-Za-z0-9]+)\b", p))
    probes["parent_coherent_scope"] = parent_coherent
    probes["parent_technical_punctuation_boundary"] = punctuation_boundary
    if probes["non_requirement_reason"] or not scoring.requirement_is_score_eligible(requirement):
        family, correct, change = "native_ineligible_or_noise", True, False
        why = "Native eligibility/exclusion applies; structure is not the remediation layer."
    elif probes["coherent_parent"]:
        family, correct, change = "native_intentionally_coherent_parent", True, False
        why = "Native coherent-parent predicate explicitly preserves this scope."
    elif parent_coherent:
        family, correct, change = "canonical_child_parent_example_scope_review", None, None
        why = "Recorded parent preserves example scope but this canonical child does not; inspect sentence/source boundaries before list admission."
    elif punctuation_boundary:
        family, correct, change = "canonical_technical_punctuation_boundary_review", None, None
        why = "Canonical focus starts with an undotted token found dotted in recorded parent; inspect native punctuation/source boundaries."
    elif probes["example_or_one_of_marker"]:
        family, correct, change = "example_or_one_of_scope_not_globally_preserved", None, None
        why = "Native whole-parent preservation is false despite an example/one-of marker (nested or independent prefix); scope needs review."
    elif len(clauses) > 1:
        family, correct, change = "native_children_not_identity_structure", None, None
        why = "Native decomposition produces clauses; the identity adapter does not admit all as atomic components."
    elif alternative:
        family, correct, change = "alternative_or_slash_scope_review", None, None
        why = "Alternative/slash semantics require review; no ALL-list inference is safe."
    elif presentation_bounded:
        family, correct, change = "presentation_prefixed_named_list_review", None, None
        why = "Presentation prefix blocks the diagnostic wrapper check; native admission still requires separate validation."
    elif bounded:
        family, correct, change = "bounded_named_list_wrapper_not_admitted", False, True
        why = "Bounded named terms are present but the existing native wrapper/list contract does not admit them."
    elif bare_bounded:
        family, correct, change = "bare_named_list_without_native_wrapper", False, True
        why = "A bounded named list lacks the native controlled wrapper; identity structure is not admitted."
    elif re.search(r"\([^)]*[,;&][^)]*\)", surface):
        family, correct, change = "parenthetical_scope_review", None, None
        why = "Parenthetical contents may be examples, product components, or lifecycle activities; no mandatory child inference."
    elif coordinated:
        family, correct, change = "coordinated_activity_or_mixed_scope_review", None, None
        why = "Coordination alone does not prove independent requirements or a named technology list."
    else:
        family, correct, change = "no_structural_split_demonstrated", True, False
        why = "No native split or diagnostic list boundary demonstrated; inspect capability/relationship routes instead."
    return {"root_cause": family, "native_behavior_correct": correct, "code_change_required": change,
        "why_structure_unavailable": why, "scope_semantics": "examples_or_one_of" if probes["example_or_one_of_marker"] or parent_coherent else
            "alternative_or_slash_unproven" if alternative else "coordination_unproven" if coordinated else "single_scope",
        "native_probe_basis": "Read-only recomputation on atomic_focus; not a historical execution trace",
        "native_rule_probes": probes, "native_probe_clauses": clauses,
        "recommended_next_action": "No parser change; review native remediation routes" if change is False else
            "Review bounded list admission with native AND/OR fixtures" if change is True else "Manual scope/provenance review before proposing a parser change",
        "risk_if_changed": "Over-splitting can turn examples/alternatives into obligations, duplicate parent weight, or change evidence completeness",
        "classification_basis": "Native predicate/admission boundary; unknown correctness denotes review, not a proven parser defect",
        "estimated_directly_resolvable": 0, "validated_resolved": None}


def project(snapshot, graphs, family, raw, requirements):
    """Partition one existing family, retaining unique native dependency sets."""
    keys = {(r["job_id"], r["requirement_id"]) for r in family.get("requirement_keys", [])}
    jobs = {j["job_id"]: j for j in snapshot["audit"]["corpus"]["jobs"]}
    traces, clusters = [], {}
    for graph in graphs:
        key = graph["job_id"], graph["requirement_id"]
        if key not in keys:
            continue
        row, diagnostic = raw[key], requirements[key]
        trace = {"job_id": key[0], "requirement_id": key[1], "original_text": row.get("text"),
            "importance": row["importance"], "weight": maintenance.gaps._weight(diagnostic),
            "source_provenance": deepcopy(row.get("source_provenance", [])),
            "raw_parent_texts": sorted({p.get("raw_parent_text", "") for p in row.get("source_provenance", [])}),
            "native_structure": {k: deepcopy(row.get(k)) for k in ("atomic_group_id", "parent_requirement_id",
                "scoring_parent_occurrence_id", "group_weight_fraction", "structured_match_kind", "structured_match_group_mode", "structured_match_status")},
            "identity_structure": deepcopy(graph["native_structure"]),
            "decomposition_recorded": deepcopy(jobs[key[0]]["baseline_stable_analysis"].get("canonicalisation_debug", {}).get("decomposition")),
            "decomposition_ran": "canonical_requirement_decomposition_version" in jobs[key[0]]["baseline_stable_analysis"].get("canonicalisation_debug", {}),
            "actual_group_rows": [{k: deepcopy(r.get(k)) for k in ("requirement_id", "text", "is_atomic", "group_weight_fraction", "source_provenance")}
                for r in jobs[key[0]]["baseline_stable_analysis"].get("canonical_requirements", [])
                if r.get("atomic_group_id") == row.get("atomic_group_id")],
            "registry_resolution": deepcopy(row.get("technology_registry_resolution")),
            "taxonomy_diagnostics": {k: deepcopy(v) for k, v in row.items() if k.startswith("capability_")},
            "current_resolution": deepcopy(graph["current_resolution"]),
            "existing_capability_overlaps": [{"candidate_id": n["candidate_id"],
                "overlaps": deepcopy(n.get("existing_taxonomy_overlaps", []))} for n in graph["nodes"]],
            "native_remediation_routes": deepcopy(graph["nodes"]),
            "diagnostic_entity_resolutions": [{"concept": n["concept"], "basis": "existing native remediation candidate, not scoring component",
                "resolution": resolve_requirement_text(n["concept"])} for n in graph["nodes"]
                if n.get("remediation_fix_layer", n["fix_layer"]) in {maintenance.IDENTITY_GAP, maintenance.RELATIONSHIP_GAP}],
            **diagnose(row)}
        traces.append(trace)
        clusters.setdefault(trace["root_cause"], []).append(trace)
    output = []
    for name, rows in sorted(clusters.items()):
        nodes = {n["dependency_id"]: n for r in rows for n in r["native_remediation_routes"]}
        item = {"subfamily_id": "gapstructure_" + fingerprint(name)[:24], "root_cause": name,
            "unique_unresolved_requirements": len(rows), "jobs_affected": len({r["job_id"] for r in rows}),
            "required_core_weight": round(sum(r["weight"] for r in rows if r["importance"] in {"core", "required", "deal_breaker"}), 6),
            "preferred_weight": round(sum(r["weight"] for r in rows if r["importance"] == "preferred"), 6),
            "requirement_keys": [{"job_id": r["job_id"], "requirement_id": r["requirement_id"]} for r in rows],
            **{k: rows[0][k] for k in ("native_behavior_correct", "code_change_required", "recommended_next_action", "risk_if_changed")},
            "shared_requirements": sum(len({n["dependency_id"] for n in r["native_remediation_routes"]}) > 1 for r in rows),
            "dependency_ids": sorted(nodes), "estimated_directly_resolvable": 0, "validated_resolved": None}
        for label, layer in (("identity", maintenance.IDENTITY_GAP), ("relationship", maintenance.RELATIONSHIP_GAP), ("capability", maintenance.CAPABILITY_GAP)):
            item[label + "_action_ids_for_review"] = sorted(aid for aid, n in nodes.items() if n.get("remediation_fix_layer", n["fix_layer"]) == layer)
        item["downstream_actions_unlocked_for_review"] = len(set().union(*(set(item[k + "_action_ids_for_review"]) for k in ("identity", "relationship", "capability"))))
        output.append(item)
    output.sort(key=lambda r: (-r["required_core_weight"], -r["unique_unresolved_requirements"], r["root_cause"]))
    for item in output:
        item["unique_marginal_requirements"] = item["unique_unresolved_requirements"]  # disjoint partition
    review_proposals = {
        "presentation_prefixed_named_list_review": "Evaluate a native controlled named-list wrapper after presentation-prefix normalization, preserving parent weight and refusing OR/examples/mixed prose",
        "bounded_named_list_wrapper_not_admitted": "Evaluate a controlled comma-list extension to the existing native bounded-named-term contract; no generic comma splitting",
        "bare_named_list_without_native_wrapper": "Evaluate native identity-structure admission of bounded bare lists only after verifying recorded parent scope",
        "canonical_child_parent_example_scope_review": "Trace native sentence/source segmentation and preserve the recorded example scope before considering any child admission",
        "canonical_technical_punctuation_boundary_review": "Trace native sentence punctuation handling of dotted technical names; preserve technical punctuation without broad normalization",
    }
    fixes = [{**deepcopy(item), "example_requirements": [r["original_text"] for r in traces if r["root_cause"] == item["root_cause"]][:3],
        "exact_current_boundary": next(r["why_structure_unavailable"] for r in traces if r["root_cause"] == item["root_cause"]),
        "proposed_generic_review": review_proposals[item["root_cause"]],
        "native_architecture_to_reuse": "stable_evidence_scoring native source/sentence/decomposition contracts and technology_requirement_structure adapter",
        "temporary_validation_strategy": "Future approved change: frozen native replay with AND/OR/example fixtures, parent-allocation conservation, row/evidence/score/rank deltas; no parser overlay currently available"}
        for item in output if item["root_cause"] in review_proposals]
    return {"total": len(traces), "subfamilies": output, "requirement_traces": traces,
        "candidate_fix_reviews": fixes,
        "partition_unique_requirements": len({(r["job_id"], r["requirement_id"]) for r in traces}),
        "recommendation": "NO SAFE GENERIC FIX YET",
        "recommendation_reason": "Bounded list admission is a review candidate; heterogeneous scope and provenance require fixtures before nominating a production correction.",
        "simulation": "No native parser overlay contract available; no production monkeypatch or simulated resolution gain claimed",
        "estimated_directly_resolvable": 0, "validated_resolved": None}

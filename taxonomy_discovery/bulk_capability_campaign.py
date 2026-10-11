"""Read-only clustering/orchestration over the existing Gap Reduction Assistant.

No embeddings, provider execution, publishing, or alternate resolver/scorer.
Whole-topic equivalence is a planning hypothesis, never taxonomy equivalence.
"""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import hashlib
import re

from taxonomy_discovery import maintenance_service as maintenance, corpus_gap_resolution as gaps
from taxonomy_discovery import governed_research as research
from taxonomy_discovery.corpus_expansion import fingerprint
from taxonomy_discovery.technology_identity_remediation import _records
from taxonomy_discovery.technology_registry import normalise
from tailoring.phase6d6_structured_matching import technology_requirement_structure

VERSION = "bulk-capability-gap-campaign-v1"
EXISTING = "EXISTING_CAPABILITY_MISSING_RULE"
GAP = "TRUE_CAPABILITY_TAXONOMY_GAP"
IDENTITY = "TECHNOLOGY_IDENTITY_DEPENDENCY"
RELATIONSHIP = "CONTEXTUAL_RELATIONSHIP_DEPENDENCY"
PARSER = "PARSER_OR_CANONICALISATION_BLOCKED"
MIXED = "DECOMPOSITION_OR_MIXED_SCOPE_BLOCKED"
NOT = "NOT_TAXONOMY_ADDRESSABLE"
SCOPE = "NEEDS_SCOPE_REVIEW"
LAYERS = {maintenance.IDENTITY_GAP: IDENTITY, maintenance.RELATIONSHIP_GAP: RELATIONSHIP,
          maintenance.PARSING_PROBLEM: PARSER, "NEEDS_DECOMPOSITION_OR_MIXED_SCOPE": MIXED}
CORE = {"required", "core", "deal_breaker"}
BOUNDARY_FIELDS = ("concept", "domain", "definition", "responsibilities", "inclusions", "exclusions",
    "requirement_predicates", "evidence_predicates", "does_not_prove", "neighbouring_capabilities",
    "technology_independent_semantics", "full_source_parent_provenance")
PROVEN = "PROVEN_TRUE_CAPABILITY_GAP"
DEFER = "UNDETERMINED_DEFER"
STRUCTURE = "PARSER_OR_DECOMPOSITION_DEPENDENCY"
GAP_PROOF_FIELDS = ("meaningful_activity","bounded_scope","reusable","evidence_predicate_to_research",
    "negative_boundary_to_research","existing_insufficient","not_identity_only",
    "not_primary_parser_or_decomposition","not_primary_relationship","not_vague")


def implementation():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _key(row):
    return row["job_id"], row["requirement_id"]


def _subject(text):
    text = str(text).replace("\u200b", "").strip().lstrip("·•*- ").rstrip(". ")
    return re.sub(r"^(?:(?:hands-on|proven|prior)\s+)?(?:knowledge|experience|familiarity|proficiency|understanding|expertise)\s+(?:of|with|in)\s+", "", text, flags=re.I)


def _profile_index():
    index = {}
    for p in gaps.load_capability_closure_profiles()["profiles"]:
        for term in p["aliases"] + (p.get("new_capability") or {}).get("requirement_terms", []):
            key = normalise(term)
            if key in index and index[key] != p:
                raise ValueError("Ambiguous native closure profile alias")
            index[key] = p
    return index


def _bounded_topic(text):
    # Only complete knowledge/experience noun phrases, not topic words embedded
    # in delivery prose. Multiple/alternative obligations remain visible.
    subject = _subject(text)
    return bool(subject != str(text).strip().rstrip(". ") and len(subject.split()) <= 8
        and not re.search(r"\b(?:and|or|using|such|including|to|with|for)\b|[,;/()]", subject, re.I)
        and re.search(r"\b(?:coding|software|systems|network|security|authentication|integration|database|querying|persistence|automation|testing|reliability|architecture|governance|pipelines|microservices)\b", subject, re.I))


def inventory(snapshot, plan):
    """Retain the exact native unresolved union, including all diagnostics."""
    native = _records(snapshot["audit"]["corpus"])
    address = plan["taxonomy_addressability"]
    rows = []
    for r in address["rows"]:
        row = deepcopy(r)
        key = _key(row)
        row["native_requirement"] = deepcopy(native[key])
        row["research_state"] = [{k: deepcopy(a.get(k)) for k in (
            "candidate_id", "research_state", "calls_used", "calls_remaining", "next_query",
            "research_round", "missing_semantic_fields", "selected_result_id", "next_action_reason")}
            for a in plan["all_actions"] if key in {(q["job_id"], q["requirement_id"]) for q in a["requirement_keys"]}]
        row["structure_diagnostics"] = technology_requirement_structure(native[key])
        row["relationship_diagnostics"] = [deepcopy(c) for c in plan.get("contextual_relationship_inventory", {}).get("candidates", [])
            if key in {(q["job_id"], q["requirement_id"]) for q in c.get("requirements", [])}]
        row["lane"] = NOT if r["semantic_addressability"] == NOT else LAYERS.get(r["primary_blocker"],
            GAP if r["semantic_addressability"] == GAP else EXISTING if r["semantic_addressability"] == "EXISTING_TAXONOMY_SUPPORTED" else SCOPE)
        if row["lane"] == SCOPE and gaps._local_identity(_subject(row["canonical_text"])):
            from taxonomy_discovery.technology_registry import resolve_requirement_text
            known = resolve_requirement_text(_subject(row["canonical_text"]))
            row["lane"] = RELATIONSHIP if known.get("technology_id") else IDENTITY
        rows.append(row)
    keys = {_key(r) for r in rows}
    if len(keys) != len(rows) or len(rows) != snapshot["audit"]["summary"]["taxonomy_unresolved_requirements"]:
        raise ValueError("Campaign must preserve the complete unique unresolved union")
    return sorted(rows, key=_key)


def cluster_inventory(rows, actions):
    """Semantic grouping requires whole-topic identity or native typed dependency.

    Residual prose is retained in a diagnostic pool, not sold as a capability.
    """
    profiles = _profile_index()
    groups = {}
    memberships = {}
    by_key = {_key(r): r for r in rows}
    def add(row, concept, kind, *, profile=None, opportunity=True):
        cid = "capcluster_" + fingerprint({"concept":normalise(concept), "type":kind})[:24]
        c = groups.setdefault(cid, {"cluster_id":cid, "canonical_concept":concept,
            "remediation_type":kind, "profile":deepcopy(profile), "opportunity":opportunity,
            "requirement_keys":[], "raw_mentions":0})
        key = _key(row)
        if key not in c["requirement_keys"]:
            c["raw_mentions"] += max(1, len(row["provenance"]))
            c["requirement_keys"].append(key)
        memberships.setdefault(key, set()).add(cid)
    for row in rows:
        key = _key(row); lane = row["lane"]
        topic = _subject(row["canonical_text"])
        profile = profiles.get(normalise(topic))
        if lane in (NOT, SCOPE):
            if lane == NOT:
                add(row, row.get("manual_review_triage", {}).get("reason_code") or "Non-addressable context", NOT, opportunity=False)
            elif profile and profile.get("new_capability") and not profile.get("relationship_research_required"):
                add(row, profile["canonical_concept"], SCOPE, profile=profile)
            elif _bounded_topic(row["canonical_text"]):
                add(row, topic, SCOPE)
            else:
                add(row, "Unproven complete scope — manual triage", SCOPE, opportunity=False)
        elif lane in (GAP, EXISTING):
            profile = (row.get("proof") or {}).get("profile") or profile
            concept = (profile or {}).get("canonical_concept") or topic
            add(row, concept, lane, profile=profile)
        else:
            associated = [a for a in actions if LAYERS.get(a["fix_layer"]) == lane
                and key in {(q["job_id"], q["requirement_id"]) for q in a["requirement_keys"]}]
            for a in associated:
                add(row, a["concept"], lane)
            if not associated:
                add(row, row["primary_blocker"], lane)
        # Secondary technology dependencies are diagnostics, never new capability
        # definitions. Shared source requirements explicitly retain one weight.
        for a in actions:
            kind = LAYERS.get(a["fix_layer"])
            if kind in (IDENTITY, RELATIONSHIP) and key in {(q["job_id"], q["requirement_id"]) for q in a["requirement_keys"]}:
                add(row, a["concept"], kind)
    clusters = list(groups.values())
    for c in clusters:
        keys = sorted(c["requirement_keys"]); members = [by_key[k] for k in keys]
        c["requirement_keys"] = keys
        c["requirements"] = len(keys); c["requirement_ids"] = [k[1] for k in keys]
        c["job_ids"] = sorted({k[0] for k in keys}); c["jobs"] = len(c["job_ids"])
        c["required_core_weight"] = round(sum(r["weight"] for r in members if r["importance"] in CORE), 6)
        c["preferred_supporting_weight"] = round(sum(r["weight"] for r in members if r["importance"] not in CORE), 6)
        c["exclusive_requirements"] = sum(len(memberships[k]) == 1 for k in keys)
        c["shared_requirements"] = sum(len(memberships[k]) > 1 for k in keys)
        c["shared_cluster_ids"] = sorted(set().union(*(memberships[k] for k in keys)) - {c["cluster_id"]})
        c["existing_capability_overlaps"] = [deepcopy(r["existing_capability_overlaps"]) for r in members]
        c["technology_dependencies"] = [deepcopy(r["technology_identities"]) for r in members]
        c["structural_dependencies"] = [deepcopy(r["structure_diagnostics"]) for r in members]
        c["provenance"] = [{"job_id":r["job_id"],"requirement_id":r["requirement_id"],"source_provenance":r["provenance"]} for r in members]
        c["employer_recurrence"] = None  # Job count is not employer recurrence.
        c["recurrence_basis"] = "distinct jobs; employer identity unavailable"
        c["scope_confidence"] = "native_bounded_hypothesis" if c["remediation_type"] in (GAP, EXISTING) else "whole_topic_boundary_unproven" if c["remediation_type"] == SCOPE and c["opportunity"] else "dependency_or_manual"
        c["false_positive_risk"] = "boundary_and_evidence_validation_required"
        c["expected_direct_gain"] = None
        c["research_readiness"] = [s for r in members for s in r["research_state"]]
        c["recommended_next_action"] = "Use current governed evidence; research only after scope/authority readiness" if c["remediation_type"] == GAP else "Validate native requirement rule with complete provenance" if c["remediation_type"] == EXISTING else "Review complete scope and neighbouring capability boundaries" if c["remediation_type"] == SCOPE else "Use existing dependency workflow; not a capability fix"
        bounded = c["remediation_type"] in (GAP, EXISTING)
        dependency = c["remediation_type"] in (IDENTITY, RELATIONSHIP, PARSER, MIXED)
        c["priority_components"] = {"unique_core_weight":c["required_core_weight"],
            "unique_requirements":c["requirements"],"jobs":c["jobs"],"employer_recurrence":None,
            "reuse_potential":min(c["jobs"],3) if c["opportunity"] else 0,
            "existing_taxonomy_overlap":sum(bool(x) for x in c["existing_capability_overlaps"]),
            "scope_clarity":2 if bounded else 1 if c["opportunity"] and not dependency else 0,
            "validation_feasibility":int(bounded),"false_positive_risk":0 if bounded else 2,
            "dependency_cost":2 if dependency else 0 if c["remediation_type"]==EXISTING else 1}
    # Weight is the first ranking criterion, but manual diagnostic pools are not
    # actionable opportunities. Clarity, reuse and dependency cost break ties.
    clusters.sort(key=lambda c: (not c["opportunity"], -c["required_core_weight"], -c["requirements"], -c["jobs"],
        -c["priority_components"]["reuse_potential"], -c["priority_components"]["existing_taxonomy_overlap"],
        -c["priority_components"]["scope_clarity"], -c["priority_components"]["validation_feasibility"],
        c["priority_components"]["false_positive_risk"], c["priority_components"]["dependency_cost"],c["cluster_id"]))
    owned = set()
    for rank, c in enumerate(clusters, 1):
        marginal = set(c["requirement_keys"]) - owned
        c["rank"] = rank
        c["unique_marginal_core_weight"] = round(sum(by_key[k]["weight"] for k in marginal if by_key[k]["importance"] in CORE), 6)
        owned.update(c["requirement_keys"])
    return clusters, {k:sorted(v) for k,v in memberships.items()}


def select_batch(clusters, size=5):
    if type(size) is not int or not 1 <= size <= 7:
        raise ValueError("Batch size must be 1 to 7")
    selected = []; owned = set()
    eligible = [c for c in clusters if c["opportunity"] and c["remediation_type"] in (GAP, EXISTING, SCOPE)]
    eligible.sort(key=lambda c: (c["remediation_type"] not in (GAP, EXISTING), -c["required_core_weight"], -c["requirements"], -c["jobs"], c["cluster_id"]))
    for c in eligible:
        keys = set(c["requirement_keys"])
        if keys & owned:
            continue
        selected.append(c["cluster_id"]); owned.update(keys)
        if len(selected) == size:
            break
    return selected


def ranked_work_queue(clusters, rows):
    """Greedy marginal union ranking; shared mentions never get extra weight."""
    by_key = {_key(r):r for r in rows}
    remaining = [deepcopy(c) for c in clusters if c["opportunity"]]
    queue=[]; owned=set()
    while remaining:
        for c in remaining:
            keys={tuple(k) for k in c["requirement_keys"]}-owned
            p=c["priority_components"]
            c["marginal_requirement_keys"]=sorted(keys)
            c["unique_marginal_requirements"]=len(keys)
            c["unique_marginal_core_weight"]=round(sum(by_key[k]["weight"] for k in keys if by_key[k]["importance"] in CORE),6)
            c["work_priority"]=(-c["unique_marginal_core_weight"],-len(keys),-c["jobs"],
                -len({k[0] for k in keys}),-p["reuse_potential"],-p["scope_clarity"],
                -p["validation_feasibility"],p["false_positive_risk"],p["dependency_cost"],c["cluster_id"])
        chosen=min(remaining,key=lambda c:c["work_priority"])
        remaining.remove(chosen); chosen["rank"]=len(queue)+1
        owned.update(tuple(k) for k in chosen["requirement_keys"]); queue.append(chosen)
    return queue


def build(snapshot, plan, *, size=5, high_impact=False):
    if high_impact and not plan.get("lazy_addressability"):
        raise ValueError("High-impact campaign requires a lazy Addressability Assistant plan")
    maintenance._require_current(snapshot)
    maintenance._intact(plan, "assistant_plan_fingerprint")
    if plan["audit_fingerprint"] != snapshot["audit_fingerprint"]:
        raise ValueError("Assistant plan belongs to a different audit")
    rows = inventory(snapshot, plan)
    clusters, memberships = cluster_inventory(rows, plan["all_actions"])
    work=ranked_work_queue(clusters,rows) if high_impact else []
    selected = [c["cluster_id"] for c in work[:10]] if high_impact else select_batch(clusters, size)
    union = set().union(*(set(c["requirement_keys"]) for c in clusters if c["cluster_id"] in selected))
    return maintenance._seal({"campaign_version":VERSION,"implementation_fingerprint":implementation(),
        "audit_fingerprint":snapshot["audit_fingerprint"],"assistant_plan_fingerprint":plan["assistant_plan_fingerprint"],
        "size":size,"inventory":rows,"clusters":clusters,"top_25": [c for c in clusters if c["opportunity"]][:25],
        **({"high_impact":True,"work_queue":work,"top_15":work[:15]} if high_impact else {}),
        "membership":[{"job_id":k[0],"requirement_id":k[1],"cluster_ids":v} for k,v in sorted(memberships.items())],
        "lane_counts":dict(Counter(r["lane"] for r in rows)),"batch_1":selected,
        "batch_unique_requirements":len(union),"batch_unique_core_weight":round(sum(r["weight"] for r in rows if _key(r) in union and r["importance"] in CORE),6),
        "baseline":plan["baseline"],"model_calls":0,"provider_calls":0,"production_writes":0},"campaign_fingerprint")


def current(snapshot, plan, campaign):
    try:
        maintenance._intact(campaign,"campaign_fingerprint")
        maintenance._intact(plan,"assistant_plan_fingerprint")
        return (maintenance.currentness(snapshot)["current"] and campaign["audit_fingerprint"] == snapshot["audit_fingerprint"]
            and campaign["assistant_plan_fingerprint"] == plan["assistant_plan_fingerprint"] and campaign["implementation_fingerprint"] == implementation())
    except (KeyError, ValueError):
        return False


def _native_candidates(snapshot, cluster):
    keys = {tuple(k) for k in cluster["requirement_keys"]}
    candidates = [r["candidate"] for r in snapshot["gap_rows"] if r.get("candidate") and
        r["candidate"]["candidate_route"] in ("possible_new_capability", "existing_capability_resolver_issue") and
        {_key(q) for q in r["requirements"]} and {_key(q) for q in r["requirements"]}.issubset(keys)]
    lineage_ids = {c["candidate_id"] for c in candidates}
    definition = (cluster.get("profile") or {}).get("new_capability")
    if not candidates and definition:
        native_rows = [q for q in snapshot["audit"]["queue"]
            if gaps._route_requirement_keys(q) and gaps._route_requirement_keys(q).issubset(keys)
            and q["operational_route"] != "noise_or_non_capability"]
        if native_rows:
            lineage_ids = {q["candidate"]["candidate_id"] for q in native_rows}
            candidates = [gaps._closure_candidate(native_rows, capability=definition)]
    return sorted(candidates, key=lambda c:c["candidate_id"]), lineage_ids


def _prepare(snapshot, plan, cluster, saved):
    """Consume native sufficiency/history, never infer evidence from a profile."""
    decision = {"cluster_id":cluster["cluster_id"], "concept":cluster["canonical_concept"],
        "remediation_type":cluster["remediation_type"], "requirements":cluster["requirements"],
        "jobs":cluster["jobs"], "core_weight":cluster["required_core_weight"],
        "decision":"NEEDS_SCOPE_REVIEW", "draft":None, "research_plan":None,
        "reason":"Complete capability/evidence boundary is not yet proven", "candidate_definition":None}
    if cluster["remediation_type"] not in (GAP, EXISTING):
        return decision
    profile = cluster.get("profile") or {}
    definition = profile.get("new_capability") or {}
    if definition:
        decision["candidate_definition"] = {"capability_id_candidate":definition["capability_id"],
            "label":definition["label"],"domain":definition["domain"],"what_it_is":definition["definition"],
            "what_it_is_not":definition["does_not_prove"],"responsibilities":None,
            "inclusions":definition["requirement_terms"],"exclusions":definition["boundaries"],
            "requirement_predicates":definition["requirement_terms"],"evidence_predicates":None,
            "evidence_that_proves_it":None,"evidence_that_does_not_prove_it":definition["does_not_prove"],
            "neighbouring_capabilities":profile["closest_capability_ids"],
            "technology_relationships":[],"provenance":cluster["provenance"],
            "status":"LOCAL_BOUNDARY_HYPOTHESIS_NOT_A_SUFFICIENT_PROPOSAL"}
    candidates, lineage_ids = _native_candidates(snapshot, cluster)
    if not candidates:
        return {**decision,"decision":"NEEDS_RESEARCH","reason":"No bounded native candidate for this complete cluster; scope review before research"}
    candidate = sorted(candidates,key=lambda c:c["candidate_id"])[0]
    selection = research.select_saved_interpretation(candidate, saved)
    if selection.get("ambiguous"):
        return {**decision,"reason":"Ambiguous cached interpretations; inspect locally before additional research"}
    primary = selection.get("primary")
    selected = primary.get("result") if primary else None
    if selected and selection.get("current") and not selection.get("ambiguous"):
        try:
            research.validate_result(selected)
            cached = next((r.get("draft") for r in saved if r["result"]["research_result_id"] == selected["research_result_id"]), None)
            if cached and not selected["conflicts_blockers"] and selected["recommended_next_action"] in ("new_capability_proposal", "resolver_improvement"):
                if cached["kind"] == "capability":
                    from taxonomy_discovery.capability_sufficiency import FIELDS
                    bundle = selected.get("support_bundle") or {}
                    if (bundle.get("missing_evidence") or bundle.get("conflicts") or
                        not all(bundle.get("fields", {}).get(f, {}).get("status") == "supported" for f in FIELDS)):
                        raise ValueError("Current governed capability boundary/evidence fields are incomplete")
                    from taxonomy_discovery.taxonomy_evolution import temporary_overlay
                    proposal = cached["proposal"]
                    if proposal.get("governed_research", {}).get("result_fingerprint") != selected["result_fingerprint"]:
                        raise ValueError("Draft does not bind this exact governed result")
                    temporary_overlay([proposal])  # Native proposal/schema validation only.
                    decision["candidate_definition"] = {"native_proposal":deepcopy(proposal),
                        "governed_boundary_evidence":deepcopy(bundle),"status":"CURRENT_GOVERNED_DRAFT_FOR_TEMPORARY_REVIEW"}
                elif cached["kind"] == "resolver_improvement":
                    from taxonomy_discovery.resolver_improvement import resolver_overlay
                    resolver_overlay(cached)
                else:
                    raise ValueError("Identity/relationship artifacts are separate workflows")
                return {**decision,"decision":"READY_FOR_TEMPORARY_VALIDATION","draft":deepcopy(cached),
                    "reason":"Exact current governed result and existing native draft","research_result_id":selected["research_result_id"]}
        except (ValueError, KeyError, TypeError) as exc:
            decision["cached_evidence_blocker"] = str(exc)
    states = [s for s in cluster["research_readiness"] if s["candidate_id"] in lineage_ids | {candidate["candidate_id"]}]
    if any(s["research_state"] in ("RESEARCH_EXHAUSTED", "DEFERRED", "NEEDS_SCOPE_REFINEMENT", "BLOCKED_EVIDENCE_INSUFFICIENT") for s in states):
        return {**decision,"decision":"NEEDS_SCOPE_REVIEW","reason":"Existing sufficiency/history says refine, defer or stop; no new provider plan"}
    if primary and not selection.get("current"):
        return {**decision,"decision":"NEEDS_RESEARCH","reason":"Saved evidence is stale; explicit local governed refresh required before any research"}
    if selected and not any(s.get("next_query") and s.get("research_round", 0) > 0
                            and s.get("selected_result_id") == selected["research_result_id"] for s in states):
        return {**decision,"reason":"Partial support has no materially new bounded query; refine scope instead of repeating research"}
    decision.update(decision="NEEDS_RESEARCH",reason="Local hypotheses do not supply sufficient governed evidence predicates")
    try:
        next_round = min(2, max(1, max((s.get("research_round") or 0 for s in states),default=0))) if selected else 0
        decision["research_plan"] = research.research_plan([candidate],selected_candidate_ids=[candidate["candidate_id"]],
            research_round=next_round,previous_result=selected)
        decision["research_authorization"] = "RESEARCH_AUTHORIZATION_REQUIRED"
    except ValueError as exc:
        decision["research_readiness_blocker"] = str(exc)
    return decision


def _scope_review(snapshot, cluster):
    """Record whole native scope and taxonomy contracts, never infer equivalence."""
    from tailoring.capability_taxonomy import get_default_taxonomy
    from tailoring.production_requirement_resolver import resolve_requirement_with_production_knowledge
    records = _records(snapshot["audit"]["corpus"])
    keys = {tuple(k) for k in cluster["requirement_keys"]}
    rows = [deepcopy(records[k]) for k in sorted(keys)]
    resolutions = [resolve_requirement_with_production_knowledge(r) for r in rows]
    taxonomy = [{"capability_id":c["capability_id"], "label":c["label"], "domain":c["domain"],
        "requirement":deepcopy(c["requirement"]), "evidence_tiers":deepcopy(c["evidence_tiers"]),
        "does_not_prove":deepcopy(c.get("does_not_prove", []))} for c in get_default_taxonomy().capabilities]
    return {"classification":cluster["remediation_type"], "requirements":rows,
        "native_resolutions":resolutions,"existing_taxonomy_checked":taxonomy,
        "automatic_equivalence":False, "parent_context_is_not_child_equivalence":True,
        "reason":"Complete native scope is unresolved; lexical overlap and neighbouring parent activities do not prove equivalence"}


def _boundary_review(decision, cluster, scope, result=None):
    """Missing fields stay missing. Local closure definitions remain hypotheses."""
    fields = {f:{"status":"missing", "evidence":[]} for f in BOUNDARY_FIELDS}
    bundle = (result or {}).get("support_bundle") or {}
    for f in ("definition", "responsibilities", "inclusions", "exclusions", "evidence_predicates"):
        source = bundle.get("fields", {}).get(f, {})
        fields[f] = {"status":"sufficient" if source.get("status")=="supported" and source.get("evidence") else "missing",
            "evidence":deepcopy(source.get("evidence", [])), "tentative_evidence":deepcopy(source.get("tentative_evidence", []))}
    if scope["requirements"] and all(r.get("source_provenance") and all(
        p.get("parent_text") and p.get("raw_parent_text") and p.get("source")
        for p in r["source_provenance"]) for r in scope["requirements"]):
        fields["full_source_parent_provenance"] = {"status":"sufficient", "evidence":deepcopy(cluster["provenance"])}
    draft = decision.get("draft") or {}
    proposal = draft.get("proposal") or {}
    # A valid native draft alone does not establish all campaign boundaries.
    # In particular, never exempt resolver drafts from missing scope evidence.
    if proposal:
        for f, key in (("concept","label"),("domain","domain"),("requirement_predicates","positive_match_concepts")):
            if proposal.get(key):
                fields[f] = {"status":"sufficient", "evidence":[deepcopy(proposal[key])]}
        if fields["exclusions"]["status"]=="sufficient" and proposal.get("does_not_prove"):
            fields["does_not_prove"]={"status":"sufficient", "evidence":deepcopy(proposal["does_not_prove"])}
        # These are explicit reviewed boundaries, not inferred from absence of
        # technology words or a nearest-neighbour lexical retrieval score.
        known = {c["capability_id"] for c in scope["existing_taxonomy_checked"]}
        neighbours = (cluster.get("profile") or {}).get("closest_capability_ids") or []
        boundaries = bundle.get("fields",{}).get("boundaries",{})
        boundary_text = " ".join(normalise(e.get("text","")) for e in boundaries.get("evidence",[]))
        neighbour_labels = {c["capability_id"]:normalise(c["label"]) for c in scope["existing_taxonomy_checked"]}
        explicit_neighbours = all(normalise(cid) in boundary_text or neighbour_labels.get(cid,"\0") in boundary_text for cid in neighbours)
        if neighbours and all(c in known for c in neighbours) and explicit_neighbours and boundaries.get("status")=="supported" and boundaries.get("evidence"):
            fields["neighbouring_capabilities"]={"status":"sufficient", "evidence":deepcopy(boundaries["evidence"]),
                "native_review_neighbours":neighbours}
        independent = [e for f in ("definition","boundaries","exclusions") for e in bundle.get("fields",{}).get(f,{}).get("evidence",[])
            if re.search(r"\b(?:technology independent|vendor neutral|vendor independent|not vendor specific)\b",normalise(e.get("text","")))]
        if independent:
            fields["technology_independent_semantics"]={"status":"sufficient", "evidence":deepcopy(independent)}
    missing = [f for f in BOUNDARY_FIELDS if fields[f]["status"]!="sufficient"]
    return {"fields":fields,"complete":not missing,"missing_fields":missing,
        "local_hypothesis":deepcopy(decision.get("candidate_definition")),
        "existing_taxonomy_checked":scope["existing_taxonomy_checked"]}


def _mature(snapshot, plan, cluster, saved):
    """Explicit local maturation; immutable provider evidence, no DB writes."""
    scope = _scope_review(snapshot, cluster)
    candidates, _ = _native_candidates(snapshot, cluster)
    refreshed = None
    history = []
    rows = list(saved)
    selection = research.select_saved_interpretation(candidates[0], saved) if candidates else {}
    if selection.get("primary") and not selection.get("ambiguous"):
        primary = selection["primary"]["result"]
        # Inspect every compatible record, but preserve native primary selection.
        for r in saved:
            result = r["result"]
            if research.compatible_saved_candidate(candidates[0],result["candidate"]):
                history.append({"research_result_id":result["research_result_id"],
                    "research_round":result["research"]["target"].get("research_round",0),
                    "raw_evidence_fingerprint":fingerprint(result["research"]),
                    "provider_request_id":result["research"].get("raw_provider_evidence",{}).get("raw_response",{}).get("request_id")})
        try:
            from taxonomy_discovery.offline_execution import offline_execution
            if not selection.get("current"):
                with offline_execution("Batch maturation reinterprets saved evidence locally only"):
                    refreshed = research.re_evaluate_saved_evidence(primary,current_candidate=candidates[0],
                        explicit_execution=True,persist=False)
                if primary["research"]["raw_provider_evidence"] != refreshed["research"]["raw_provider_evidence"]:
                    raise ValueError("Local refresh changed raw provider evidence")
                # Drafts bound to the previous interpretation are never silently
                # rebound to newly interpreted evidence.
                rows.append({"result":refreshed,"draft":None,"review":{}})
            else:
                research.validate_result(primary)
        except (ValueError, KeyError, TypeError) as exc:
            scope["local_refresh_blocker"] = str(exc)
    d = _prepare(snapshot,plan,cluster,rows)
    d.update(scope_review=scope,classification=scope["classification"],
        scope_state="COMPLETE_NATIVE_BOUNDARY_REQUIRED", research_history=history,
        local_refresh=refreshed, local_refresh_persisted=False)
    interpreted = refreshed or ((selection.get("primary") or {}).get("result") if selection.get("current") else None)
    boundary = _boundary_review(d,cluster,scope,interpreted)
    d["boundary_review"] = boundary
    d["scope_state"] = "BOUNDARY_COMPLETE" if boundary["complete"] else "BOUNDARY_INCOMPLETE"
    if d.get("draft") and not boundary["complete"]:
        d.update(draft=None,decision="NEEDS_SCOPE_REVIEW",reason="Complete boundary fields are required before temporary overlay")
    if interpreted and interpreted.get("support_bundle") and not interpreted["support_bundle"].get("eligible_for_human_review"):
        next_plan = interpreted.get("next_research_plan") or {}
        # Never reset the native round counter to evade an exhausted budget.
        d.update(draft=None,decision="NEEDS_RESEARCH",research_authorization="RESEARCH_AUTHORIZATION_REQUIRED",
            research_state="RESEARCH_EXHAUSTED" if not next_plan.get("call_budget") else "LOCAL_EVIDENCE_INSUFFICIENT",
            reason="Local refreshed evidence remains insufficient; no external call is authorized")
        d["authorization_request"]={"candidate":deepcopy(candidates[0]),
            "missing_semantic_fields":deepcopy(interpreted["support_bundle"].get("missing_evidence",[])),
            "bounded_queries":[next_plan["query"]] if next_plan.get("query") else [],
            "expected_source_classes":list(research.SOURCE_CLASSES),
            "planned_scopes":deepcopy(next_plan.get("planned_scopes",[])),
            "maximum_provider_calls":next_plan.get("call_budget",0),"automatic_execution":False,
            "budget_blocker":"Native research rounds exhausted; explicit authorization and budget review required" if not next_plan.get("call_budget") else None}
        d["research_plan"] = None
    if scope.get("local_refresh_blocker") or selection.get("ambiguous"):
        d.update(draft=None,decision="NEEDS_SCOPE_REVIEW",reason="Cached interpretation is ambiguous or failed local validation")
    d.setdefault("research_state",{"NEEDS_SCOPE_REVIEW":"SCOPE_REVIEW","NEEDS_RESEARCH":"RESEARCH_AUTHORIZATION_REQUIRED"}.get(d["decision"],"CURRENT_GOVERNED_DRAFT"))
    return d


def _overlay(drafts):
    from tailoring.capability_taxonomy import get_default_taxonomy
    if not drafts:
        return get_default_taxonomy()
    if all(d["kind"] == "capability" for d in drafts):
        from taxonomy_discovery.taxonomy_evolution import temporary_overlay
        return temporary_overlay([d["proposal"] for d in drafts])
    if len(drafts) == 1 and drafts[0]["kind"] == "resolver_improvement":
        from taxonomy_discovery.resolver_improvement import resolver_overlay
        return resolver_overlay(drafts[0])
    raise ValueError("Existing native combined overlay does not support mixed artifact families")


def _replay(snapshot, drafts, intended):
    """Native scorer/audit receipts; this is reporting, not a scoring engine."""
    from taxonomy_discovery.regression_corpus import replay_current_corpus, duplicate_credit_violations
    from taxonomy_discovery.technology_identity_remediation import _receipt
    from taxonomy_discovery.offline_execution import offline_execution
    from tailoring.capability_taxonomy import temporary_taxonomy_scope
    before = snapshot["audit"]["corpus"]
    with offline_execution("Bulk campaign preview forbids network"), temporary_taxonomy_scope(_overlay(drafts)):
        after = replay_current_corpus(before)
        audit = gaps.audit_corpus_resolution(corpus=after)
    if after["current_replay"]["jobs_blocked"]:
        raise ValueError("Complete frozen inputs required")
    b, a = _records(before), _records(after)
    rb = {_key(r):r["current_resolution"] for r in snapshot["audit"]["requirements"]}
    ra = {_key(r):r["current_resolution"] for r in audit["requirements"]}
    changes=[]; evidence=[]; unexpected=[]; newly=[]; lost=[]; violations=[]
    for key in sorted(b.keys() | a.keys()):
        old, new = _receipt(b.get(key)), _receipt(a.get(key))
        # Temporary version differences alone do not represent resolution gain.
        semantic = ("status","resolution_source","capability_id","technology_id","registry_status","registry_reason")
        if old != new or any((rb.get(key) or {}).get(k) != (ra.get(key) or {}).get(k) for k in semantic):
            changes.append({"job_id":key[0],"requirement_id":key[1],"before":old,"after":new})
            if key not in intended or any((old or {}).get(k)!=(new or {}).get(k) for k in ("text","importance","source_provenance","group_weight_fraction","atomic_group_id","score_eligible")):
                unexpected.append(key)
        if any((old or {}).get(k)!=(new or {}).get(k) for k in ("evidence","match_label","match_value","weighted_evidence_contribution")):
            evidence.append(key)
        if rb.get(key,{}).get("status") != "resolved" and ra.get(key,{}).get("status") == "resolved": newly.append(key)
        if rb.get(key,{}).get("status") == "resolved" and ra.get(key,{}).get("status") != "resolved": lost.append(key)
    old_jobs={j["job_id"]:j for j in before["jobs"]}
    score=[]
    for j in after["jobs"]:
        old=old_jobs[j["job_id"]]
        if old["metrics"]["deterministic_alignment_score"] != j["metrics"]["deterministic_alignment_score"]:
            score.append({"job_id":j["job_id"],"before":old["metrics"],"after":j["metrics"]})
        ctx=j["frozen_inputs"]["context"]
        violations.extend({"job_id":j["job_id"],"reason":v} for v in duplicate_credit_violations(j["baseline_stable_analysis"],ctx))
    ranking_before=gaps._integrated_ranking(before); ranking_after=gaps._integrated_ranking(after)
    return {"baseline":snapshot["audit"]["summary"],"after":audit["summary"],"changed_requirements":changes,
        "newly_resolved":newly,"newly_unresolved":lost,"evidence_deltas":evidence,"score_deltas":score,
        "before_ranking":ranking_before,"after_ranking":ranking_after,"ranking_changed":ranking_before!=ranking_after,
        "unexpected_changes":unexpected,"duplicate_credit_violations":violations,
        "corpus":after,"audit":audit,"production_writes":0,"model_calls":0,"network_calls":0}


def _decision(report):
    if report["unexpected_changes"] or report["newly_unresolved"] or report["duplicate_credit_violations"]:
        return "UNSAFE"
    if report["evidence_deltas"] or report["score_deltas"] or report["ranking_changed"]:
        return "NEEDS_SCOPE_REVIEW"  # New credit needs evidence-level human assessment.
    return "VALIDATED_SAFE" if report["newly_resolved"] else "VALIDATED_ZERO_IMPACT"


def _review_high_impact(snapshot,plan,cluster,saved,projection):
    """Reuse native whole-scope review, never treat a dependency as a gap."""
    kind=cluster["remediation_type"]
    dependency={IDENTITY:IDENTITY,RELATIONSHIP:RELATIONSHIP,PARSER:STRUCTURE,MIXED:STRUCTURE}.get(kind)
    if dependency:
        return {"cluster_id":cluster["cluster_id"],"concept":cluster["canonical_concept"],
            "classification":dependency,"decision":dependency,"draft":None,
            "scope_review":_scope_review(snapshot,cluster),"reason":"Native typed dependency; use its existing governed workflow",
            "research_state":"NO_EXTERNAL_EXECUTION","scope_state":"DEPENDENCY_ONLY"}
    rows=[r for r in projection["rows"] if _key(r) in {tuple(k) for k in cluster["requirement_keys"]}]
    from taxonomy_discovery.taxonomy_addressability import GAP as TRUE, SUPPORTED, NOT_ADDRESSABLE
    if rows and all(r["semantic_addressability"]==NOT_ADDRESSABLE for r in rows):
        return {"cluster_id":cluster["cluster_id"],"concept":cluster["canonical_concept"],
            "classification":NOT,"decision":NOT,"draft":None,"scope_review":_scope_review(snapshot,cluster),
            "reason":"Native whole-statement non-addressable proof; retained in unresolved accounting"}
    contracts=[r.get("proof",{}).get("gap_contract") or {} for r in rows]
    classification = PROVEN if rows and all(r["semantic_addressability"]==TRUE for r in rows) and all(
        all(p.get(k) for k in GAP_PROOF_FIELDS) for p in contracts) else EXISTING if rows and all(
        r["semantic_addressability"]==SUPPORTED for r in rows) else DEFER
    scoped=deepcopy(cluster)
    if classification==PROVEN:
        scoped["remediation_type"]=GAP
        scoped["profile"]=deepcopy(rows[0]["proof"]["profile"])
    elif classification==EXISTING:
        scoped["remediation_type"]=EXISTING
    d=_mature(snapshot,plan,scoped,saved)
    d["classification"]=classification
    if d["classification"]==DEFER:
        d.update(draft=None,decision=DEFER,reason="Whole reusable scope remains unproven after bounded native inspection; continue to next cluster")
    elif d["decision"]=="NEEDS_SCOPE_REVIEW":
        d["decision"]=DEFER
    return d


def gap_accounting(projection, decisions=()):
    """Disjoint requirement-key ledger, not a count of overlapping actions."""
    dependencies={tuple(k) for d in decisions if d["classification"] in (IDENTITY,RELATIONSHIP,STRUCTURE)
        for k in d["requirement_keys"]}
    groups={k:[] for k in ("proven_true_gaps","maintenance_dependencies","not_addressable","undetermined")}
    for r in projection["rows"]:
        contract=r.get("proof",{}).get("gap_contract") or {}
        category="proven_true_gaps" if r["semantic_addressability"]==GAP and all(contract.get(k) for k in GAP_PROOF_FIELDS) else (
            "not_addressable" if r["semantic_addressability"]==NOT else "maintenance_dependencies" if _key(r) in dependencies else "undetermined")
        groups[category].append(list(_key(r)))
    return {"raw_unresolved":len(projection["rows"]),"counts":{k:len(v) for k,v in groups.items()},"requirement_keys":groups}


def validate(snapshot, plan, campaign, *, explicit_execution=False, review_db_path=None, mature=False):
    if explicit_execution is not True:
        raise ValueError("Explicit campaign validation required")
    if not current(snapshot,plan,campaign):
        raise ValueError("Stale campaign; build again")
    if campaign.get("high_impact") and not plan.get("lazy_addressability"):
        raise ValueError("Lazy Addressability plan required")
    from taxonomy_discovery import gap_reduction_assistant as assistant
    from database import taxonomy_discovery_review_manager as store
    assistant.validate_plan(snapshot,plan,plan["assistant_plan_fingerprint"],review_db_path=review_db_path)
    saved=store.list_governed_research_results(db_path=review_db_path)
    high=campaign.get("high_impact",False)
    projection=None
    if high:
        from taxonomy_discovery.taxonomy_addressability import project
        chosen={tuple(k) for c in campaign["clusters"] if c["cluster_id"] in campaign["batch_1"] for k in c["requirement_keys"]}
        unresolved=[r for r in snapshot["audit"]["requirements"] if _key(r) in {_key(q) for q in plan["taxonomy_addressability"]["rows"]}]
        projection=project(snapshot,unresolved,snapshot["gap_rows"],previous=plan["taxonomy_addressability"],reviewed_keys=chosen)
    by_id={c["cluster_id"]:c for c in campaign["clusters"]}
    decisions=[]; safe=[]; intended=set()
    for cid in campaign["batch_1"]:
        c=by_id[cid]; d=_review_high_impact(snapshot,plan,c,saved,projection) if high else (_mature if mature else _prepare)(snapshot,plan,c,saved)
        d["requirement_keys"]=deepcopy(c["requirement_keys"])
        if d["draft"]:
            try:
                report=_replay(snapshot,[d["draft"]],{tuple(k) for k in c["requirement_keys"]})
                d.update(report=report,decision=_decision(report))
            except ValueError as exc:
                d.update(decision="UNSAFE",reason="Native individual replay failed closed",replay_blocker=str(exc))
            if d["decision"] == "VALIDATED_SAFE":
                safe.append(d["draft"]); intended.update(tuple(k) for k in c["requirement_keys"])
        decisions.append(d)
    try:
        combined=_replay(snapshot,safe,intended)
        combined_decision=_decision(combined)
    except ValueError as exc:
        # Unsupported combined families fail closed; do not grant independent
        # gains or stop validation of research/scope items.
        combined=_replay(snapshot,[],set())
        combined_decision="UNSAFE"; combined["combination_blocker"]=str(exc)
    post=deepcopy(snapshot); post["audit"]=combined["audit"]
    post["gap_rows"]=maintenance.list_gap_rows(post["audit"],saved_rows=saved,
        publications=maintenance.publication.list_publications(db_path=review_db_path))
    from taxonomy_discovery.taxonomy_addressability import project
    noise=set().union(*(gaps._route_requirement_keys(q) for q in post["audit"]["queue"]
        if q["operational_route"]=="noise_or_non_capability" and not q.get("parent_candidate_id")))
    unresolved=[r for r in post["audit"]["requirements"] if r["score_eligible"] and _key(r) not in noise and r["current_resolution"]["status"]!="resolved"]
    projection=project(post,unresolved,post["gap_rows"],previous=projection,reviewed_keys=[]) if high else project(post,unresolved,post["gap_rows"])
    post_plan={**plan,"taxonomy_addressability":projection}
    rows=inventory(post,post_plan)
    clusters,_=cluster_inventory(rows,plan["all_actions"])
    # Completed, exhausted, or current Batch-1 scope/research actions are not
    # proposed again as the next tranche. Dependence impact uses post-overlay rows.
    remaining=[c for c in clusters if c["cluster_id"] not in campaign["batch_1"]]
    if high:
        reviewed_scopes={(normalise(by_id[cid]["canonical_concept"]),frozenset(tuple(k) for k in by_id[cid]["requirement_keys"])) for cid in campaign["batch_1"]}
        remaining=[c for c in remaining if (normalise(c["canonical_concept"]),frozenset(tuple(k) for k in c["requirement_keys"])) not in reviewed_scopes]
    next_work=ranked_work_queue(remaining,rows) if high else []
    return maintenance._seal({"campaign_fingerprint":campaign["campaign_fingerprint"],
        "implementation_fingerprint":implementation(),"decisions":decisions,"combined":combined,
        "combined_decision":combined_decision,"batch_2":[c["cluster_id"] for c in next_work[:10]] if high else select_batch(remaining,7 if mature else campaign["size"]),
        **({"high_impact":True,"next_work_queue":next_work[:10],"gap_accounting":gap_accounting(projection,decisions),
            "reviewed_requirement_keys":[list(k) for k in sorted(chosen)],
            "addressability_movements":[{"job_id":r["job_id"],"requirement_id":r["requirement_id"],
                "before":next(q["semantic_addressability"] for q in plan["taxonomy_addressability"]["rows"] if _key(q)==_key(r)),
                "after":r["semantic_addressability"]} for r in projection["rows"] if _key(r) in chosen]} if high else {}),
        "post_batch_clusters":clusters,"post_addressability":projection,
        "individually_validated_safe":sum(d["decision"]=="VALIDATED_SAFE" for d in decisions),
        "research_required":sum(d["decision"]=="NEEDS_RESEARCH" for d in decisions),
        "scope_review_required":sum(d["decision"] in ("NEEDS_SCOPE_REVIEW",DEFER) for d in decisions),
        "validated_zero_impact":sum(d["decision"]=="VALIDATED_ZERO_IMPACT" for d in decisions),
        "unsafe":sum(d["decision"]=="UNSAFE" for d in decisions),"matured_locally":mature,
        "production_writes":0,"provider_calls":0,"model_calls":0,"publication":False,"approval":False},"validation_fingerprint")


def table(clusters, decisions=()):
    outcomes={d["cluster_id"]:d for d in decisions}
    return [{"Rank":c.get("rank"),"Concept":c["canonical_concept"],"Requirements":c["requirements"],"Jobs":c["jobs"],
        "Unique requirements":c.get("unique_marginal_requirements",c["requirements"]),
        "Core weight":c["required_core_weight"],"Unique marginal weight":c["unique_marginal_core_weight"],
        "Remediation":c["remediation_type"],"Scope":c["scope_confidence"],
        "Classification":outcomes.get(c["cluster_id"],{}).get("classification",c["remediation_type"]),
        "Scope state":outcomes.get(c["cluster_id"],{}).get("scope_state",c["scope_confidence"]),
        "Research state":outcomes.get(c["cluster_id"],{}).get("research_state",
            ", ".join(sorted({s["research_state"] for s in c.get("research_readiness",[]) if s.get("research_state")})) or "NOT_MATURED"),
        "Validated impact":len(outcomes.get(c["cluster_id"],{}).get("report",{}).get("newly_resolved",[])) if c["cluster_id"] in outcomes else None,
        "Decision":outcomes.get(c["cluster_id"],{}).get("decision","NOT_VALIDATED"),
        "Requirement IDs":", ".join(c["requirement_ids"]),"Next action":c["recommended_next_action"]} for c in clusters]

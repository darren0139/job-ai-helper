"""Read-only semantic accounting, separate from native remediation and scoring.

Closure profiles are boundary hypotheses, never approved taxonomy knowledge.
Unproven equivalence stays visible as undetermined; lexical overlap is not proof.
"""
from collections import Counter
from copy import deepcopy
import re

from taxonomy_discovery import maintenance_service as maintenance
from taxonomy_discovery import corpus_gap_resolution as gaps
from taxonomy_discovery.technology_identity_remediation import _records
from taxonomy_discovery.technology_registry import normalise
from taxonomy_discovery.technology_registry import get_default_registry
from tailoring.capability_taxonomy import get_default_taxonomy
from tailoring.production_requirement_resolver import resolve_requirement_with_production_knowledge
from tailoring.phase6d6_structured_matching import technology_requirement_structure

SUPPORTED = "EXISTING_TAXONOMY_SUPPORTED"
GAP = "TRUE_CAPABILITY_TAXONOMY_GAP"
NOT_ADDRESSABLE = "NOT_TAXONOMY_ADDRESSABLE"
UNDETERMINED = "UNDETERMINED_NEEDS_SCOPE_REVIEW"
STATUSES = (SUPPORTED, GAP, NOT_ADDRESSABLE, UNDETERMINED)
CORE = {"required", "core", "deal_breaker"}
VAGUE = re.compile(r"(?:(?:strong|good|solid|broad)\s+technical\s+(?:background|knowledge)|"
                   r"(?:knowledge|understanding|awareness)\s+of\s+(?:modern|current|latest|new)\s+technologies)", re.I)

# Whole-statement maintenance predicates. No keyword alone is an exclusion.
# Technical activity, identity and native scope dependencies win over these.
MANUAL_RULES = (
    ("SUBJECTIVE_MOTIVATION_OR_ATTITUDE", "SUBJECTIVE_OR_MOTIVATIONAL",
     r"(?:public service spirit:\s*)?you care deeply about (?:the public good|public service) and understand the responsibility of working on (?:critical national infrastructure|public services)(?: that impacts (?:millions of )?lives daily)?",
     "Public-service commitment and responsibility describe motivation, not an engineering activity"),
    ("CULTURE_OR_VALUES", "CULTURE_OR_VALUES",
     r"(?:you (?:share|embrace)|alignment with) (?:our|the team's|company) values of (?:integrity|respect|teamwork|inclusion|honesty|empathy)(?:(?:,\s*| and )(?:integrity|respect|teamwork|inclusion|honesty|empathy))*",
     "Whole statement requests alignment with interpersonal values, without a technical obligation"),
    ("GENERIC_ASPIRATION", "GENERIC_UNBOUNDED_EXPECTATION",
     r"(?:continuous learning:\s*)?you will (?:constantly|continuously) (?:explore|learn about) new technologies(?:, system architectures,? and security practices)?",
     "Continuous learning is behaviour; referenced technical topics are learning objects, not implementation obligations"),
    ("PRODUCT_OR_MISSION_CONTEXT", "EMPLOYER_MISSION_CONTEXT",
     r"you will be at the forefront of developing (?:the|our|a) (?:next generation|new|future) [a-z][a-z -]{1,75} (?:system|platform|product|service)",
     "Forefront/future-product framing names an employer outcome without specifying a reusable engineering capability"),
    ("GENERIC_TECHNICAL_BREADTH", "GENERIC_UNBOUNDED_EXPECTATION",
     r"(?:good|strong|broad) understanding of (?:prevailing|modern|current) technologies(?: and technology markets)?",
     "Generic technology breadth supplies no bounded activity or technical evidence predicate"),
    ("GENERIC_ASPIRATION", "GENERIC_UNBOUNDED_EXPECTATION",
     r"ability to learn new software and technologies (?:quickly|rapidly)",
     "Learning speed is a behavioural expectation, not proof of a technical capability"),
    ("NON_TECHNICAL_COLLABORATION_OR_BEHAVIOUR", "NON_TECHNICAL_BEHAVIOURAL_REQUIREMENT",
     r"plan and guide your team's professional growth(?:,? in both general and technical areas)?",
     "Team professional-development responsibility is not a technical implementation obligation"),
)
ROLE_FUNCTIONS = {
    "engineering": ["fellow engineers", "software engineers", "engineers", "technical lead", "architect"],
    "policy": ["policy officers", "various partner agencies", "partner agencies"],
    "design": ["ux designers", "designers", "solution architects"],
    "security": ["cybersecurity specialists"],
    "business": ["business analysts", "product owners", "project manager"],
}


def manual_triage(requirement, routes):
    """Inspect entire manual-review scope; never execute scoring or research."""
    raw = requirement.get("atomic_focus") or requirement.get("text", "")
    text = raw.replace("\u200b", "").replace("\u2019", "'").strip().rstrip(". ")
    result = {"subfamily": "UNDECIDED", "reason_code": None, "decision": None,
              "rule": None, "why": "No complete high-confidence manual predicate", "guard": None}
    forbidden = {maintenance.IDENTITY_GAP, maintenance.RELATIONSHIP_GAP, maintenance.PARSING_PROBLEM,
                 "NEEDS_DECOMPOSITION_OR_MIXED_SCOPE"}
    if routes & forbidden or technology_requirement_structure(requirement)["mode"]:
        return {**result, "guard": "Native identity/relationship/parser/scope dependency; do not exclude"}
    for parent in requirement.get("source_provenance", []):
        value = parent.get("raw_parent_text")
        if value:
            surface = value.replace("\u200b", "").replace("\u2019", "'").strip().rstrip(". ")
            surface = re.sub(r"^[\u00b7\u2022*-]+\s*", "", surface)
            if surface.casefold() != text.casefold():
                grounding = parent.get("grounding") or {}
                sentence = str(grounding.get("sentence_text") or "").replace("\u200b", "").replace("\u2019", "'").strip().rstrip(". ")
                if not (grounding.get("kind") == "explicit_raw_section" and grounding.get("span_id")
                        and isinstance(grounding.get("sentence_index"), int) and sentence.casefold() == text.casefold()):
                    return {**result, "guard": "Recorded parent has additional/different scope without exact native sentence grounding; no exclusion or inferred equivalence"}
                result["native_sentence_scope"] = deepcopy(grounding)
    # Bounded explicit collaboration has full activity scope and at least two
    # named functions. General teamwork is explicitly insufficient in taxonomy.
    roles = re.fullmatch(r"(?:you will |you'll )?(?:work|collaborate) closely with (.+?)(?: within an agile environment| as part of the project delivery)?", text, re.I)
    if roles:
        parts = [p.strip().lower() for p in re.split(r",\s*(?:and\s+)?|\s+and\s+", roles[1])]
        functions = {f for p in parts for f, names in ROLE_FUNCTIONS.items() if p in names}
        known = {name for names in ROLE_FUNCTIONS.values() for name in names}
        capability = get_default_taxonomy().by_id().get("collaboration.cross_functional")
        if capability and len(functions) >= 2 and all(p in known for p in parts):
            return {**result, "subfamily": "NON_TECHNICAL_COLLABORATION_OR_BEHAVIOUR", "reason_code": "COMPLETE_CROSS_FUNCTIONAL_SCOPE",
                "decision": SUPPORTED, "rule": "explicit_collaboration_with_multiple_named_functions", "functions": sorted(functions),
                "capability_id": capability["capability_id"], "capability_boundary": deepcopy(capability),
                "why": "Complete collaboration activity names multiple functions; no additional technical delivery obligation"}
    # Exact identities embedded in an otherwise generic-looking phrase remain
    # technical. Word boundaries protect short aliases from substring collisions.
    identities = [e["technology_id"] for e in get_default_registry().entries
        if any(re.search(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", text, re.I)
               for alias in [e["label"], *e["aliases"]] if alias)]
    if identities:
        return {**result, "subfamily": "POSSIBLE_TECHNICAL_CAPABILITY", "guard": "Recognized technology mention", "technology_ids": sorted(set(identities))}
    for family, code, pattern, why in MANUAL_RULES:
        if re.fullmatch(pattern, text, re.I):
            if family == "PRODUCT_OR_MISSION_CONTEXT" and re.search(r"\b(?:security|cybersecurity|database|network|api|backend|authentication|distributed|microservices|reliability)\b", text, re.I):
                return {**result, "subfamily": "POSSIBLE_TECHNICAL_CAPABILITY", "guard": "Potential bounded technical product activity; mission wording alone is insufficient"}
            return {**result, "subfamily": family, "reason_code": code, "decision": NOT_ADDRESSABLE,
                "rule": pattern, "why": why, "non_addressable_contract": {
                    "legitimate_jd_context": True, "not_reusable_technical_activity": True,
                    "not_technology_identity": True, "not_hidden_parser_or_scope_failure": True,
                    "not_relationship_problem": True, "not_bounded_missing_capability": True,
                    "deterministic_whole_statement_reason": code}}
    technical = re.search(r"\b(?:software|security|cybersecurity|code|api|backend|database|network|distributed|microservices|architectures?|reliability|failsafe|tested|testing|querying|infrastructure)\b", text, re.I)
    if technical:
        result.update(subfamily="POSSIBLE_TECHNICAL_CAPABILITY", guard="Technical activity or mixed behavioural/technical scope; no exclusion")
    return result


def _subject(text):
    # Diagnostic wrapper removal only; never passed to the scorer or persisted.
    return re.sub(r"^(?:knowledge|experience|familiarity|proficiency|understanding)\s+(?:of|with|in)\s+", "", text.strip().rstrip("."), flags=re.I)


def classify(requirement, routes, profiles):
    """Return one semantic decision with an inspectable, conservative proof."""
    text = requirement.get("atomic_focus") or requirement.get("text", "")
    subject = _subject(text)
    native = resolve_requirement_with_production_knowledge(requirement)
    cid = native["decision"].get("capability_id")
    proof = {"native_resolution": native, "profile": None, "gap_contract": None}
    structure = technology_requirement_structure(requirement)
    proof["native_structure"] = structure
    mixed = bool(structure["mode"] or re.search(r"\b(?:and|or|such as|including)\b|[,;/]", subject, re.I))
    exact = normalise(subject) == normalise(native["taxonomy_diagnostics"].get("matched_phrase") or "")
    if cid and (not mixed or exact):
        return SUPPORTED, "Native production capability exists; unresolved audit status requires plumbing/evidence review", proof
    if cid and mixed:
        return UNDETERMINED, "Native capability covers a component, but full mixed/alternative scope equivalence is unproven", proof
    # Full diagnostic subject equivalence can establish knowledge existence,
    # but never fixes production resolution or changes requirement eligibility.
    tail = resolve_requirement_with_production_knowledge({"text": subject})
    proof["subject_resolution"] = tail
    if tail["decision"].get("capability_id") and not mixed:
        return SUPPORTED, "Exact native capability for the complete diagnostic subject; wrapper/plumbing remains unresolved", proof
    taxonomy_ids = get_default_taxonomy().by_id()
    permitted = {d["capability_id"] for d in gaps.CAPABILITY_DRAFT_DISPOSITIONS
                 if d["disposition"] == "retain_capability_candidate"}
    for profile in profiles:
        definition = profile.get("new_capability")
        if not definition:
            continue
        if normalise(subject) not in {normalise(t) for t in definition["requirement_terms"]}:
            continue
        proof["profile"] = deepcopy(profile)
        # No identity-only/language profiles; no scope-sensitive distributed-
        # systems profile admission merely from its capability-shaped name.
        if definition["capability_id"] not in permitted:
            return UNDETERMINED, "Native closure hypothesis needs scope/evidence-boundary review; a name is not a proven capability gap", proof
        primary_scope = technology_requirement_structure(requirement)
        proof["native_structure"] = primary_scope
        if primary_scope["mode"] or maintenance.RELATIONSHIP_GAP in routes:
            return UNDETERMINED, "Relationship or mixed requirement scope must be established before claiming a missing capability", proof
        complete = all(definition.get(k) for k in ("definition", "requirement_terms", "does_not_prove", "boundaries")) and bool(profile.get("why_existing_insufficient"))
        if complete and definition["capability_id"] not in taxonomy_ids:
            proof["gap_contract"] = {
                "meaningful_activity": definition["definition"], "bounded_scope": subject,
                "reusable": profile["canonical_concept"], "evidence_predicate_to_research": definition["definition"],
                "negative_boundary_to_research": definition["does_not_prove"],
                "existing_insufficient": profile["why_existing_insufficient"],
                "not_identity_only": True, "not_primary_parser_or_decomposition": True,
                "not_primary_relationship": True, "not_vague": True,
                "review_only": True, "authority_or_publication_claim": False}
            return GAP, "Bounded native retained closure profile with explicit evidence/negative boundaries and no native equivalent; research and human review still required", proof
        return UNDETERMINED, "Native closure boundary contract incomplete or current taxonomy overlap needs review", proof
    # Only whole generic phrases qualify. Concrete technologies or native route
    # dependencies cannot be excluded merely because they remain unresolved.
    if VAGUE.fullmatch(text.strip().rstrip(".")) and not routes.intersection({maintenance.IDENTITY_GAP, maintenance.RELATIONSHIP_GAP, maintenance.PARSING_PROBLEM}):
        return NOT_ADDRESSABLE, "VAGUE_TECHNICAL_SCOPE: whole phrase specifies no activity, technical object, or bounded evidence predicate", proof
    return UNDETERMINED, "No complete native equivalence or bounded gap contract; preserve unresolved accounting and review scope", proof


def project(snapshot, unresolved, gap_rows):
    """Pure projection of the exact existing meaningful-unresolved union."""
    raw = _records(snapshot["audit"]["corpus"])
    profiles = gaps.load_capability_closure_profiles()["profiles"]
    linked = {}
    for candidate in gap_rows:
        for req in candidate["requirements"]:
            linked.setdefault((req["job_id"], req["requirement_id"]), []).append(candidate)
    rows = []
    for audit in sorted(unresolved, key=lambda r: (r["job_id"], r["requirement_id"])):
        key = audit["job_id"], audit["requirement_id"]
        source = raw[key]
        related = linked.get(key, [])
        routes = {r["fix_layer"] for r in related}
        if any(r.get("boundary_state") == maintenance.NEEDS_DECOMPOSITION for r in related):
            routes.add("NEEDS_DECOMPOSITION_OR_MIXED_SCOPE")
        structure = technology_requirement_structure(source)
        if structure["mode"]:
            routes.add("NEEDS_DECOMPOSITION_OR_MIXED_SCOPE")
        status, reason, proof = classify(source, routes, profiles)
        # Candidate routes are diagnostic associations, not proof of necessity.
        # Semantic gap claims use the contract above, never route-name equality.
        blockers = routes - {maintenance.CAPABILITY_GAP}
        if not blockers:
            blockers.add(maintenance.MANUAL if status != GAP else maintenance.CAPABILITY_GAP)
        order = [maintenance.PARSING_PROBLEM, "NEEDS_DECOMPOSITION_OR_MIXED_SCOPE", maintenance.IDENTITY_GAP,
                 maintenance.RELATIONSHIP_GAP, maintenance.EVIDENCE_PROBLEM, maintenance.NOISE, maintenance.MANUAL, maintenance.CAPABILITY_GAP, "NONE"]
        ordered = sorted(blockers, key=lambda b: (order.index(b) if b in order else len(order), b))
        originals = list(dict.fromkeys(p["raw_parent_text"] for p in source.get("source_provenance", []) if p.get("raw_parent_text")))
        rows.append({"job_id": key[0], "requirement_id": key[1], "original_text": "\n".join(originals) or source.get("parent_text") or source["text"],
            "canonical_text": source["text"], "importance": audit["importance"], "weight": gaps._weight(audit),
            "semantic_addressability": status, "addressability_reason": reason, "primary_blocker": ordered[0],
            "secondary_blockers": ordered[1:], "native_fix_layers": sorted(routes),
            "existing_capability_overlaps": [deepcopy(r["candidate"].get("overlap", {})) for r in related if r.get("candidate")],
            "technology_identities": {"requirement": deepcopy(audit.get("technology_identity_resolution")),
                "associated_candidates": [deepcopy(r.get("technology_identity")) for r in related if r.get("technology_identity")]},
            "native_candidate_review": [{k: deepcopy(r.get(k)) for k in ("candidate_id", "concept", "fix_layer", "parent_candidate_id", "boundary_state", "boundary_reason", "readiness", "research_status")} for r in related],
            "provenance": deepcopy(source.get("source_provenance", [])), "audit_provenance": deepcopy(audit["provenance"]),
            "confidence": "native_boundary_hypothesis" if status == GAP else "native_exact" if status == SUPPORTED else "bounded_generic_phrase" if status == NOT_ADDRESSABLE else "undecided",
            "review_state": "HUMAN_REVIEW_REQUIRED", "proof": proof,
            "recommended_next_action": "Research evidence and negative boundary after governed readiness review" if status == GAP else
                "Review existing taxonomy resolution and dependency scope" if status == SUPPORTED else
                "Retain JD context; document taxonomy-unsuitable scope without changing eligibility" if status == NOT_ADDRESSABLE else "Review scope; do not exclude or create a capability"})
    v1_counts = dict(Counter(r["semantic_addressability"] for r in rows))
    manual = [r for r in rows if r["primary_blocker"] == maintenance.MANUAL]
    for row in manual:
        triage = manual_triage(raw[(row["job_id"], row["requirement_id"])], set(row["native_fix_layers"]))
        row["manual_review_triage"] = triage
        row["v1_semantic_addressability"] = row["semantic_addressability"]
        if row["semantic_addressability"] == UNDETERMINED and triage["decision"]:
            row["semantic_addressability"] = triage["decision"]
            row["addressability_reason"] = triage["reason_code"] + ": " + triage["why"]
            row["confidence"] = "high_confidence_whole_scope_manual_predicate"
            row["recommended_next_action"] = "Review documented maintenance classification; retain JD row and scoring eligibility"
    expected = snapshot["audit"]["summary"]["taxonomy_unresolved_requirements"]
    keys = {(r["job_id"], r["requirement_id"]) for r in rows}
    noise = set().union(*(gaps._route_requirement_keys(q) for q in snapshot["audit"]["queue"]
        if q["operational_route"] == "noise_or_non_capability" and not q.get("parent_candidate_id")))
    expected_keys = {(r["job_id"], r["requirement_id"]) for r in snapshot["audit"]["requirements"]
        if r["score_eligible"] and r["current_resolution"]["status"] != "resolved" and (r["job_id"], r["requirement_id"]) not in noise}
    if len(rows) != len(keys) or len(keys) != expected or keys != expected_keys:
        raise ValueError("Addressability must account for the complete unique meaningful unresolved union")
    summary = {}
    for status in STATUSES:
        selected = [r for r in rows if r["semantic_addressability"] == status]
        summary[status] = {"count": len(selected), "weight": round(sum(r["weight"] for r in selected), 6),
            "required_core_weight": round(sum(r["weight"] for r in selected if r["importance"] in CORE), 6)}
    groups = {}
    for row in rows:
        if row["semantic_addressability"] != GAP:
            continue
        p = row["proof"]["profile"]
        groups.setdefault(p["canonical_concept"], {"profile": p, "rows": []})["rows"].append(row)
    ranked = [{"concept": concept, "unique_requirements": len(g["rows"]), "jobs": sorted({r["job_id"] for r in g["rows"]}),
               "required_core_weight": round(sum(r["weight"] for r in g["rows"] if r["importance"] in CORE), 6),
               "requirements": [{"job_id": r["job_id"], "requirement_id": r["requirement_id"]} for r in g["rows"]],
               "why_reusable": g["profile"]["new_capability"]["definition"],
               "why_existing_insufficient": g["profile"]["why_existing_insufficient"],
               "evidence_boundary_to_research": g["profile"]["new_capability"]["definition"],
               "negative_boundary_to_research": g["profile"]["new_capability"]["does_not_prove"],
               "overlap_risks": g["profile"]["closest_capability_ids"], "scope_clarity": "bounded_native_profile",
               "recurrence": len(g["rows"]),
               "research_readiness": "REVIEW_NATIVE_READINESS_BEFORE_EXECUTION"} for concept, g in groups.items()]
    ranked.sort(key=lambda g: (-g["required_core_weight"], -g["unique_requirements"], -len(g["jobs"]), g["concept"]))
    return maintenance._seal({"audit_fingerprint": snapshot["audit_fingerprint"], "classification_version": "taxonomy-addressability-triage-v2",
        "v1_status_counts": {s: v1_counts.get(s, 0) for s in STATUSES},
        "manual_review_triage": {"manual_review_before": len(manual),
            "HIGH_CONFIDENCE_CLASSIFIED_FROM_MANUAL_REVIEW": sum(r["v1_semantic_addressability"] == UNDETERMINED and r["semantic_addressability"] != UNDETERMINED for r in manual),
            "REMAINING_MANUAL_REVIEW_UNDETERMINED": sum(r["semantic_addressability"] == UNDETERMINED for r in manual),
            "subfamily_counts": dict(Counter(r["manual_review_triage"]["subfamily"] for r in manual))},
        "raw_summary": deepcopy(snapshot["audit"]["summary"]),
        "rows": rows, "summary": summary, "unique_unresolved_requirements": len(keys), "top_true_capability_gaps": ranked,
        "primary_blocker_counts": dict(Counter(r["primary_blocker"] for r in rows)),
        "blocker_association_counts": dict(Counter(b for r in rows for b in [r["primary_blocker"], *r["secondary_blockers"]])),
        "semantic_count_total": sum(s["count"] for s in summary.values()), "raw_denominator_unchanged": True,
        "approval": False, "publication": False, "production_writes": 0, "network_calls": 0, "model_calls": 0}, "addressability_fingerprint")

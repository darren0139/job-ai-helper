"""Offline review of limitation hypotheses; never a production eligibility rule."""
from collections import Counter
from copy import deepcopy
import argparse
import json
from pathlib import Path

from scripts import audit_jd_scoring_eligibility as audit
from taxonomy_discovery.coverage_presentation import analyzed_jobs_coverage

PROVEN = "PROVEN_SYSTEM_EVALUATION_LIMITATION"
CANDIDATE = "CANDIDATE_EVIDENCE_GAP"
LEGITIMATE = "LEGITIMATE_SCOREABLE_REQUIREMENT"
AMBIGUOUS = "AMBIGUOUS_NEEDS_POLICY_REVIEW"


def calibrate_requirement(receipt, native):
    """A diagnostic route is not proof of a failed satisfaction predicate.

    No new text recognizer or absence-of-evidence exclusion is introduced.
    Existing resolved predicates / validated structured paths disprove automatic
    system neutralization. Other cases require an independent path review.
    """
    structure = receipt.get("evaluability_evidence", {}).get("native_structure") or {}
    resolved = receipt.get("knowledge_status") in {"CAPABILITY_RESOLVED", "TECHNOLOGY_IDENTITY_RESOLVED"}
    accepted = (native.get("structured_match_status") in {"applied", "confirmed_existing_direct"}
        and (native.get("structured_match_kind"), native.get("structured_match_group_mode")) in {
            ("programming_language_group", "any"),
            ("collaborative_system_integration_transfer", "behavioral_transfer")})
    independent = resolved or accepted
    positive = receipt.get("evidence_label") != "none" and bool(receipt.get("selected_evidence"))
    decision = LEGITIMATE if independent else AMBIGUOUS
    checks = {
        "legitimate_jd_requirement": {"status": "uncertain", "basis":
            "Production score eligibility records intended inclusion, not reviewed satisfaction semantics."},
        "analyzer_inability_proven": {"status": "not_proven", "basis":
            "Missing exported structure does not prove absence of an independent matcher path."},
        "known_system_failure": {"status": "not_proven", "basis":
            "Operational triage blocker is a remediation hypothesis, not a parser failure or completeness proof."},
        "none_not_candidate_gap": {"status": "uncertain", "basis":
            "A zero selected match is not a reviewed negative evidence predicate."},
        "no_independent_evaluation_path": {"status": "disproved" if independent else "not_proven", "basis":
            "Native resolved/validated path exists." if independent else
            "No accepted path is recorded here; exhaustive independent evidence-path review is absent."},
        "generic_rule": {"status": "confirmed", "basis":
            "Uses native statuses and proof availability; no sentence, job or requirement ID matching."},
    }
    reason = ("Native governed evaluation path remains scoreable; no automatic exclusion."
        if independent else "The six-condition exclusion contract is not proven by this receipt.")
    if structure.get("source") == "native_coherent_example_or_alternative_parent":
        reason += " Native parent preservation is intentional; empty components are not canonicalisation corruption."
    if receipt.get("route") == "NOT_TAXONOMY_ADDRESSABLE":
        reason += " Taxonomy addressability cannot establish legitimacy or scoring eligibility."
    if positive and not independent:
        reason += " Selected component evidence is retained, but whole-parent completeness is unproven."
    return {"decision": decision, "reason": reason, "proof_conditions": checks,
        "tailoring_action": "AMBIGUOUS_DO_NOT_AUTO_RECOMMEND",
        "native_match_contract": {k: deepcopy(v) for k,v in native.items()
            if k.startswith("structured_match_") or k in {"source_provenance", "atomic_group_id", "group_weight_fraction"}}}


def build_calibration(snapshot, plan):
    original = audit.build_audit(snapshot, plan)
    jobs = snapshot["audit"]["corpus"]["jobs"]
    native = {(j["job_id"],r["requirement_id"]):r for j in jobs
        for r in j["baseline_stable_analysis"]["canonical_requirements"]}
    reviews = []
    positives = []
    for row in original["requirements"]:
        key = row["job_id"], row["requirement_id"]
        if row["evaluability"] == audit.LIMITED:
            reviews.append({**deepcopy(row), **calibrate_requirement(row, native[key])})
        if row["route"] in {audit.campaign.PARSER, audit.campaign.MIXED} and row["evidence_label"] in {"direct", "transferable"}:
            contract = native[key]
            bounded = (contract.get("structured_match_status") == "applied"
                and contract.get("structured_match_kind") == "collaborative_system_integration_transfer"
                and contract.get("structured_match_group_mode") == "behavioral_transfer")
            positives.append({**deepcopy(row), "review": "VALIDATED_BOUNDED_BEHAVIORAL_TRANSFER" if bounded else AMBIGUOUS,
                "reason": "Native collaboration-transfer contract credits behavior across domains, not complete DSP/FPGA/RF engineering." if bounded else
                "Selected evidence supports a named component; stored receipt does not prove the complete parent obligation.",
                "native_match_contract": calibrate_requirement(row, contract)["native_match_contract"]})
    # Only proven rows can enter this preview. The current receipts prove none;
    # do not manufacture an exclusion contract to reproduce the old +1.03.
    neutralized = {(r["job_id"],r["requirement_id"]) for r in reviews if r["decision"] == PROVEN}
    preview = []
    for j in original["jobs"]:
        stable = next(x for x in jobs if x["job_id"] == j["job_id"])["baseline_stable_analysis"]
        ids = {rid for jid,rid in neutralized if jid == j["job_id"]}
        score = audit.counterfactual(stable, j["production_receipt"], ids)
        preview.append({"job_id":j["job_id"], "production_score":j["current_score"], "temporary_score":score,
            "delta":score-j["current_score"], "production_rank":j["current_rank"],
            "rows_neutralized":len(ids), "neutralized_weight":sum(r["effective_score_weight"] for r in reviews
                if r["job_id"]==j["job_id"] and r["requirement_id"] in ids), "requirement_ids":sorted(ids)})
    for rank,j in enumerate(sorted(preview,key=lambda j:(-j["temporary_score"],j["job_id"])),1):
        j["temporary_rank"] = rank
        j["rank_delta"] = j["production_rank"]-rank
    analyses = [{"job_id":j["job_id"], "status":"current", "raw_jd_text":j["frozen_inputs"]["raw_jd_text"],
        "stable_analysis":j["baseline_stable_analysis"]} for j in jobs]
    return {"verdict":"MORE_POLICY_REVIEW_REQUIRED" if any(r["decision"] == AMBIGUOUS for r in reviews)
            else "NO_PRODUCTION_SCORING_CHANGE_JUSTIFIED",
        "limitation_count":len(reviews), "decisions":dict(Counter(r["decision"] for r in reviews)),
        "tailoring_actions":dict(Counter(r["tailoring_action"] for r in reviews)),
        "reviews":reviews, "structural_positive_reviews":positives, "preview":preview,
        "jobs_affected":sum(j["delta"] != 0 for j in preview),
        "average_delta":sum(j["delta"] for j in preview)/len(preview) if preview else 0,
        "largest_delta":max((j["delta"] for j in preview),default=0),
        "rank_changes":sum(j["rank_delta"] != 0 for j in preview),
        "analyzed_frozen_jobs_summary":analyzed_jobs_coverage(snapshot,plan,analyses),
        "native_audit":original, "read_only":True}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt",required=True)
    parser.add_argument("--output",required=True)
    parser.add_argument("--final-adjudication",action="store_true")
    args=parser.parse_args(argv)
    from taxonomy_discovery.offline_execution import offline_execution
    receipt=json.loads(Path(args.receipt).read_text(encoding="utf-8-sig"))
    with offline_execution("Eligibility calibration forbids network"):
        if args.final_adjudication:
            traces, replay = trace_native_corpus(receipt["snapshot"]["audit"]["corpus"])
            result=build_adjudication(receipt["snapshot"],receipt["plan"],traces=traces)
            result["production_replay"] = replay
        else:
            result=build_calibration(receipt["snapshot"],receipt["plan"])
    Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k not in
        {"reviews","structural_positive_reviews","preview","native_audit","analyzed_frozen_jobs_summary","production_replay"}},indent=2))


def trace_native_corpus(corpus):
    """Observe native calls during the existing replay; no matching substitute."""
    from unittest.mock import patch
    from analysis_stability import stable_evidence_scoring as scorer
    from tailoring import phase6d6_structured_matching as structured
    from taxonomy_discovery import regression_corpus
    records, phase = {}, {"job_id":None,"keyword":False}
    best, keyword = scorer._best_resume_evidence, scorer.build_deterministic_keyword_match
    canonical, match = scorer.canonicalise_requirements, structured.structured_match_requirement
    builder = regression_corpus._default_stable_builder

    def observe_best(requirement, term, index, acronyms):
        result=best(requirement,term,index,acronyms)
        if phase["keyword"]:
            evidence, similarity, coverage, overlap=result
            record=records.setdefault((phase["job_id"],requirement["requirement_id"]),{})
            record["keyword_search"]={"evidence_index_count":len(index),
                "candidate":deepcopy(evidence),"similarity":similarity,"coverage":coverage,"overlap":overlap}
        return result

    def observe_keyword(**kwargs):
        phase["keyword"]=True
        try: result=keyword(**kwargs)
        finally: phase["keyword"]=False
        missing={r["keyword"] for r in result["missing"]}
        for row in kwargs["requirements"]:
            record=records.setdefault((phase["job_id"],row["requirement_id"]),{})
            focus=row.get("atomic_focus") or row["text"]
            record["keyword_outcome"]="missing" if focus in missing else "present"
        return result

    def observe_canonical(**kwargs):
        result=canonical(**kwargs)
        for row in result["requirements"]:
            records.setdefault((phase["job_id"],row["requirement_id"]),{})["canonical_scope"]={
                k:deepcopy(row.get(k)) for k in ("is_atomic","parent_text","atomic_focus","source_provenance","atomic_group_id")}
        return result

    def observe_structured(requirement,**kwargs):
        result=match(requirement,**kwargs)
        records.setdefault((phase["job_id"],requirement["requirement_id"]),{})["structured_decision"]=deepcopy(result)
        return result

    ids=iter(j["job_id"] for j in corpus["jobs"])
    def observe_builder(**kwargs):
        phase["job_id"]=next(ids)
        return builder(**kwargs)
    with patch.object(scorer,"_best_resume_evidence",side_effect=observe_best), \
        patch.object(scorer,"build_deterministic_keyword_match",side_effect=observe_keyword), \
        patch.object(scorer,"canonicalise_requirements",side_effect=observe_canonical), \
        patch.object(structured,"structured_match_requirement",side_effect=observe_structured), \
        patch.object(regression_corpus,"_default_stable_builder",side_effect=observe_builder):
        replay=regression_corpus.replay_current_corpus(corpus)
    changes=[j["job_id"] for j in replay["jobs"]
        if j["baseline_stable_analysis"] != j["saved_stable_analysis"]]
    if replay["current_replay"]["jobs_blocked"] or changes:
        raise ValueError("Native adjudication replay unavailable or production analysis changed")
    return records,{**replay["current_replay"],"analysis_changes":changes,
        "scores":{str(j["job_id"]):j["baseline_stable_analysis"]["deterministic_alignment_score"] for j in replay["jobs"]}}


def adjudicate_requirement(receipt, native, trace=None):
    """Freeze uncertain negative semantics; native diagnostics are not a parser."""
    structure=receipt.get("evaluability_evidence",{}).get("native_structure") or {}
    reason=receipt.get("evaluability_evidence",{}).get("semantic_review_reason") or ""
    scope="UNKNOWN"
    basis="No native governed satisfaction unit is recorded."
    if reason.startswith("EMPLOYER_MISSION_CONTEXT:"):
        scope,basis="NON_EVIDENCE_CONTEXT","Existing reviewed employer-mission context contract."
    elif structure.get("source")=="native_coherent_example_or_alternative_parent":
        scope,basis="COHERENT_PARENT","Native decomposer deliberately preserves the coherent example parent."
    elif structure.get("components") and structure.get("mode") in {"any","all"}:
        scope="ONE_OF" if structure["mode"]=="any" else "ALL_OF"
        basis="Existing native component/mode contract; no new parsing."
    elif native.get("is_atomic") is True:
        scope,basis="ATOMIC","Native canonical row explicitly marks an atomic clause."
    accepted=calibrate_requirement(receipt,native)["decision"]==LEGITIMATE
    path="YES" if accepted else "UNKNOWN"
    negative="UNKNOWN"
    native_trace=deepcopy(trace) if trace else {}
    search=native_trace.get("keyword_search")
    if search and native_trace.get("keyword_outcome")=="missing":
        # The native lexical path actually ran. Rejected candidates do not
        # establish an exhaustive negative result over an unknown parent scope.
        negative="CANDIDATE_REJECTED" if search.get("candidate") else "SEARCHED_BUT_SCOPE_LIMITED"
    adjudication="LEGITIMATE_SCOREABLE_NON_TAXONOMY_REQUIREMENT" if accepted and receipt.get("route")=="NOT_TAXONOMY_ADDRESSABLE" else "AMBIGUOUS_FREEZE"
    return {"final_adjudication":adjudication,"satisfaction_scope":scope,"scope_basis":basis,
        "negative_evidence_status":negative,"independent_evidence_path":path,
        "independent_path_function": "Native resolved/validated path recorded in calibration receipt" if accepted else None,
        "native_trace":native_trace,
        "export_vs_production":("Native canonical scope observed, not merely an export omission; whole-parent satisfaction remains unproven."
            if trace and trace.get("canonical_scope") else "Original parser state absent from this compact receipt; UNKNOWN."),
        "negative_contract": "Lexical NONE is a threshold outcome, not proof of semantic absence. Structured None does not distinguish inapplicability from no qualifying evidence. Recovery audit records successes only.",
        "system_limitation_proof":{**calibrate_requirement(receipt,native)["proof_conditions"],
            "no_exact_text_or_id_rule":{"status":"confirmed","basis":"Only native status/proof fields select decisions."}},
        "tailoring_action":"UNKNOWN_DO_NOT_AUTO_RECOMMEND"}


def build_adjudication(snapshot,plan,*,traces=None):
    original=audit.build_audit(snapshot,plan,include_counterfactuals=False)
    native={(j["job_id"],r["requirement_id"]):r for j in snapshot["audit"]["corpus"]["jobs"]
        for r in j["baseline_stable_analysis"]["canonical_requirements"]}
    reviews,controls=[],[]
    for row in original["requirements"]:
        key=row["job_id"],row["requirement_id"]
        if row["evaluability"]==audit.LIMITED:
            reviews.append({**deepcopy(row),**adjudicate_requirement(row,native[key],(traces or {}).get(key))})
        if row["route"] in {audit.campaign.PARSER,audit.campaign.MIXED} and row["evidence_label"] in {"direct","transferable"}:
            controls.append({**deepcopy(row),"support_scope":"BOUNDED_COMPONENT_SUPPORT",
                "whole_parent_support_proven":False,"native_match_contract":calibrate_requirement(row,native[key])["native_match_contract"]})
    proven=[r for r in reviews if r["final_adjudication"]=="SYSTEM_EVALUATION_LIMITATION_PROVEN"]
    preview=None
    if proven:
        preview=[]
        for j in original["jobs"]:
            stable=next(x for x in snapshot["audit"]["corpus"]["jobs"] if x["job_id"]==j["job_id"])["baseline_stable_analysis"]
            ids={r["requirement_id"] for r in proven if r["job_id"]==j["job_id"]}
            preview.append({"job_id":j["job_id"],"production_score":j["current_score"],
                "preview_score":audit.counterfactual(stable,j["production_receipt"],ids)})
    return {"verdict":"BOUNDED_SCORING_POLICY_PROVEN" if proven else "SCORING_POLICY_FROZEN_NO_CHANGE",
        "reviews":reviews,"structural_positive_reviews":controls,
        "decisions":dict(Counter(r["final_adjudication"] for r in reviews)),
        "satisfaction_scopes":dict(Counter(r["satisfaction_scope"] for r in reviews)),
        "negative_evidence":dict(Counter(r["negative_evidence_status"] for r in reviews)),
        "independent_paths":dict(Counter(r["independent_evidence_path"] for r in reviews)),
        "tailoring_actions":dict(Counter(r["tailoring_action"] for r in reviews)),
        "preview_status":"BOUNDED_PREVIEW" if proven else "NO_BOUNDED_EXCLUSION_SET_PROVEN","preview":preview,
        "production_scores":{str(j["job_id"]):j["current_score"] for j in original["jobs"]},
        "production_ranks":{str(j["job_id"]):j["current_rank"] for j in original["jobs"]},
        "explainer_semantics":{
            "MATCHED_DIRECT":"Native direct credit with linked evidence; retain its recorded scope.",
            "MATCHED_TRANSFERABLE":"Native transferable credit; do not imply whole-parent completeness.",
            "CANDIDATE_EVIDENCE_GAP":"Governed satisfaction scope plus proven negative evidence; NONE alone is insufficient.",
            "SYSTEM_EVALUATION_LIMITATION":"Only SYSTEM_EVALUATION_LIMITATION_PROVEN with every hard proof condition satisfied.",
            "PROVEN_TAXONOMY_GAP":"Authoritative reviewed knowledge gap; independent of evidence credit.",
            "NOT_TAXONOMY_ADDRESSABLE":"Reviewed knowledge dimension; does not determine scoring eligibility.",
            "DEFERRED_BUT_EVALUABLE":"Deferred knowledge with an accepted independent native evidence path.",
            "UNKNOWN_REVIEW_PENDING":"Unclassified satisfaction/evidence policy; never assert candidate deficiency."},
        "native_audit":original,"read_only":True,
        "next_step":"Freeze scoring-policy work for this branch; implement Initial Analysis Explainer with UNKNOWN_REVIEW_PENDING. Unresolved policy work is post-merge backlog."}


if __name__ == "__main__":
    main()

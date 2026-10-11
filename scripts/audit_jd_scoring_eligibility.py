"""Explicit, offline report over native reviewed accounting and scoring receipts.

Evaluability decisions are diagnostic hypotheses, never production eligibility.
Counterfactuals subtract frozen Phase 8 receipt allocations; no resolver, matcher,
research, storage or production scoring contract is changed by this module.
"""
from collections import Counter
from copy import deepcopy
import argparse
import csv
import json
from pathlib import Path

from analysis_stability.stable_evidence_scoring import (
    compute_deterministic_alignment, requirement_is_score_eligible,
    requirement_is_tailoring_eligible,
)
from taxonomy_discovery import bulk_capability_campaign as campaign
from taxonomy_discovery.coverage_presentation import confirmed_coverage, jd_coverage
from tailoring.phase8_score_explainability import build_score_breakdown

EVALUABLE = "EVALUABLE"
LIMITED = "NOT_RELIABLY_EVALUABLE"
AMBIGUOUS = "AMBIGUOUS_NEEDS_POLICY_REVIEW"


def evaluability(row, reviewed):
    """Report-only conservative rules backed by existing typed receipts.

    A NONE is not evidence of missing system capability. A structural blocker
    plus missing native unit/mode is; positive subset matches stay ambiguous
    unless production explicitly validated an ANY language-group contract.
    Deferred prose without a calibrated predicate remains unknown, not excluded.
    """
    knowledge = row.get("knowledge_status", "UNRESOLVED")
    if knowledge in {"CAPABILITY_RESOLVED", "TECHNOLOGY_IDENTITY_RESOLVED"}:
        return EVALUABLE, "NATIVE_REQUIREMENT_PREDICATE"
    if not reviewed:
        return AMBIGUOUS, "NO_REVIEWED_EVALUABILITY_PROOF"
    lane = reviewed["lane"]
    if lane in {campaign.PARSER, campaign.MIXED}:
        structure = reviewed.get("structure_diagnostics") or {}
        if (row.get("structured_match_kind") == "programming_language_group"
                and row.get("structured_match_group_mode") == "any"
                and row.get("structured_match_status") in {"applied", "confirmed_existing_direct"}):
            return EVALUABLE, "NATIVE_ANY_LANGUAGE_CONTRACT"
        if not structure.get("components") or not structure.get("mode"):
            if row.get("match_label") == "none":
                return LIMITED, "PARSER_NORMALIZATION_BLOCKED" if lane == campaign.PARSER else "STRUCTURAL_SCOPE_UNPROVEN"
            return AMBIGUOUS, "PARENT_CHILD_COMPLETENESS_UNPROVEN"
        return AMBIGUOUS, "COMPOUND_COMPLETENESS_REQUIRES_POLICY_REVIEW"
    if lane == campaign.GAP:
        # NAC currently gets DIRECT from generic access-control evidence. The
        # authoritative taxonomy gap proves missing calibration, not a loss.
        return AMBIGUOUS, "AUTHORITATIVE_SYSTEM_CAPABILITY_GAP_WITH_EXISTING_CREDIT"
    if lane == campaign.NOT:
        reason = reviewed.get("addressability_reason", "")
        if reason.startswith("EMPLOYER_MISSION_CONTEXT:"):
            return LIMITED, "REQUIREMENT_SEMANTICS_UNDETERMINED"
        return AMBIGUOUS, "NON_TAXONOMY_REQUIREMENT_NEEDS_EVIDENCE_POLICY"
    if row.get("match_label") in {"direct", "transferable", "weak"} and row.get("evidence"):
        return EVALUABLE, "PRODUCTION_GROUNDED_MATCH_WITHOUT_CAPABILITY_MAPPING"
    return AMBIGUOUS, "NO_CALIBRATED_NEGATIVE_PREDICATE"


def _receipt(stable):
    rows = stable["canonical_requirements"]
    actual = compute_deterministic_alignment(rows)
    if actual["deterministic_alignment_score"] != stable["deterministic_alignment_score"]:
        raise ValueError("Frozen receipt does not reproduce the production score")
    eligible = deepcopy(stable)
    eligible["canonical_requirements"] = [r for r in rows if requirement_is_score_eligible(r)]
    receipt = build_score_breakdown(eligible)
    if not receipt["score_parity"]:
        raise ValueError("Phase 8 contribution receipt does not reconcile")
    return receipt


def counterfactual(stable, receipt, excluded):
    """Diagnostic only: frozen allocations, native formula/evidence component.

    Passing exclusions straight into the scorer would redistribute weight among
    retained siblings. The requested denominator-only experiment instead removes
    original receipt allocations. Production compute supplies its unchanged
    component coefficients and Evidence Strength rounding for the retained rows.
    """
    rows = [r for r in stable["canonical_requirements"] if r["requirement_id"] not in excluded]
    native = compute_deterministic_alignment(rows)
    points = [r for r in receipt["requirements"] if r["requirement_id"] not in excluded]
    weights = native["score_weights"]
    coverage_points = 0.0
    for component in ("required_core_coverage", "preferred_coverage"):
        retained = [r for r in points if r["component"] == component]
        denominator = sum(_allocation(r, receipt) for r in retained)
        numerator = sum(_allocation(r, receipt) * r["match_value"] for r in retained)
        coverage_points += (100 * numerator / denominator if denominator else 0) * weights[component]
    return int(max(0, min(100, round(coverage_points + native["evidence_strength_score"] * weights["evidence_strength"]))))


def _allocation(row, receipt):
    # Phase 8 serializes displayed fractions/points rounded to six decimals.
    # Recover exact native division from its original group membership, avoiding
    # a lossy reconstruction at a half-point rounding boundary.
    count = sum(r["component"] == row["component"] and r["atomic_group_id"] == row["atomic_group_id"]
                for r in receipt["requirements"])
    return row["importance_weight"] / count


def build_audit(snapshot, plan, *, include_counterfactuals=True):
    view = confirmed_coverage(snapshot, plan)
    inventory = campaign.inventory(snapshot, plan)
    operational = {(r["job_id"], r["requirement_id"]): r for r in inventory}
    audit_rows = {(r["job_id"], r["requirement_id"]): r for r in snapshot["audit"]["requirements"]}
    meaningful = set(operational) | {key for key,row in audit_rows.items()
        if row["current_resolution"]["knowledge_status"] in {"CAPABILITY_RESOLVED", "TECHNOLOGY_IDENTITY_RESOLVED"}}
    if len(meaningful) != snapshot["audit"]["summary"]["meaningful_technical_requirements"]:
        raise ValueError("Native meaningful technical union does not reconcile")
    requirements, jobs = [], []
    for job in snapshot["audit"]["corpus"]["jobs"]:
        jid = job["job_id"]
        stable = job["baseline_stable_analysis"]
        receipt = _receipt(stable)
        if include_counterfactuals and counterfactual(stable, receipt, set()) != stable["deterministic_alignment_score"]:
            raise ValueError("Unchanged frozen-allocation counterfactual does not reconcile")
        point_rows = {r["requirement_id"]: r for r in receipt["requirements"]}
        evidence_component = next(c for c in receipt["components"] if c["key"] == "evidence_strength")
        total_strength = evidence_component["numerator"]
        classified = []
        for row in stable["canonical_requirements"]:
            key = jid, row["requirement_id"]
            if key not in meaningful:  # other canonical rows stay in the full scorer receipt
                continue
            reviewed = operational.get(key)
            native = audit_rows[key]
            label, reason = evaluability(row, reviewed)
            point = point_rows.get(row["requirement_id"], {})
            eligible = requirement_is_score_eligible(row)
            in_denominator = eligible and row.get("importance") in campaign.CORE | {"preferred"}
            # Supporting rows are neutral in coverage but positive evidence can
            # enter the production Evidence Strength mean. Phase 8's coverage
            # row list omits them, so retain that native component explicitly.
            strength = min(5, max(0, int(row.get("evidence_strength", 0))))
            evidence_points = evidence_component["weighted_points"] * strength / total_strength if eligible and row["match_label"] != "none" and total_strength else 0
            contribution = point.get("overall_coverage_points", 0) + evidence_points
            state = "EXCLUDED" if not eligible else "FULL" if row["match_value"] == 1 else "PARTIAL" if row["match_value"] > 0 else "ZERO"
            tailoring = "SYSTEM_EVALUATION_LIMITATION" if label == LIMITED else (
                "TAILORABLE_EVIDENCE_GAP" if label == EVALUABLE and row["match_label"] in {"none", "weak", "transferable"}
                and requirement_is_tailoring_eligible(row) else "AMBIGUOUS" if label == AMBIGUOUS else "NOT_A_GAP")
            semantics = ["MATCHED_DIRECT" if row["match_label"] == "direct" else "MATCHED_TRANSFERABLE"
                         if row["match_label"] == "transferable" else "CANDIDATE_EVIDENCE_GAP" if label == EVALUABLE else "UNKNOWN"]
            if label == LIMITED: semantics = ["SYSTEM_EVALUATION_LIMITATION"]
            if reviewed and reviewed["lane"] == campaign.GAP: semantics.append("PROVEN_TAXONOMY_GAP")
            if reviewed and reviewed["lane"] == campaign.NOT: semantics.append("NOT_TAXONOMY_ADDRESSABLE")
            if reviewed and reviewed["lane"] == campaign.SCOPE and label == EVALUABLE: semantics.append("DEFERRED_BUT_EVALUABLE")
            item = {"job_id": jid, "requirement_id": row["requirement_id"], "text": row["text"],
                "importance": row["importance"], "atomic_group_id": row.get("atomic_group_id"),
                "source_group_weight_fraction": row.get("group_weight_fraction"),
                "effective_score_weight": _allocation(point, receipt) if point else 0,
                "knowledge_status": native["current_resolution"]["knowledge_status"],
                "resolution_source": native["current_resolution"].get("resolution_source"),
                "route": reviewed["lane"] if reviewed else native["current_resolution"]["knowledge_status"],
                "capability_id": row.get("capability_id"),
                "technology_id": (row.get("knowledge_resolution") or {}).get("technology_id"),
                "evidence_label": row["match_label"], "selected_evidence": deepcopy(row.get("evidence", [])),
                "selected_evidence_ids": [e.get("evidence_id") for e in row.get("evidence", [])],
                "selected_evidence_sources": [e.get("source") for e in row.get("evidence", [])],
                "match_value": row["match_value"], "weighted_numerator_contribution": point.get("coverage_numerator_contribution", 0),
                "weighted_score_contribution": contribution, "cap_status": row.get("capability_taxonomy_cap_status"),
                "weighted_evidence_strength_contribution": evidence_points,
                "evidence_strength": strength,
                "cap_rejection": deepcopy(row.get("validation_warnings", [])) + [deepcopy(w) for w in stable.get("validation_warnings", []) if w.get("requirement_id") == row["requirement_id"]],
                "score_eligible": eligible, "included_in_score_denominator": in_denominator,
                "contributes": state, "evaluability": label, "evaluability_reason": reason,
                "evaluability_evidence": {"primary_blocker": reviewed.get("primary_blocker"),
                    "native_structure": deepcopy(reviewed.get("structure_diagnostics")),
                    "semantic_review_reason": reviewed.get("addressability_reason")} if reviewed else {},
                "tailoring_classification": tailoring, "currently_tailoring_eligible": requirement_is_tailoring_eligible(row),
                "explainer_semantics": semantics}
            requirements.append(item); classified.append(item)
        excluded = {r["requirement_id"] for r in classified if r["evaluability"] == LIMITED}
        unsafe = {r["requirement_id"] for r in stable["canonical_requirements"]
            if audit_rows[(jid,r["requirement_id"])] ["current_resolution"]["knowledge_status"] == "UNRESOLVED"}
        current = stable["deterministic_alignment_score"]
        a, b = (counterfactual(stable, receipt, excluded), counterfactual(stable, receipt, unsafe)) if include_counterfactuals else (current, current)
        jobs.append({"job_id": jid, "current_score": current, "counterfactual_a": a, "delta": a-current,
            "counterfactual_b_unsafe": b, "unsafe_delta": b-current,
            "unsafe_excluded_all_canonical_unresolved": len(unsafe),
            "excluded_not_reliably_evaluable": len(excluded),
            "excluded_core_weight": sum(r["effective_score_weight"] for r in classified if r["requirement_id"] in excluded and r["importance"] in campaign.CORE),
            "production_receipt": receipt})
    for field, rank_field in (("current_score", "current_rank"), ("counterfactual_a", "counterfactual_rank"),
                              ("counterfactual_b_unsafe", "unsafe_rank")):
        for rank, row in enumerate(sorted(jobs, key=lambda r: (-r[field], r["job_id"])), 1): row[rank_field] = rank
    for row in jobs: row["rank_delta"] = row["current_rank"] - row["counterfactual_rank"]
    groups = {}
    for route in sorted({r["route"] for r in requirements}):
        rr = [r for r in requirements if r["route"] == route]
        groups[route] = {"requirements": len(rr), "required_core_weight": sum(r["effective_score_weight"] for r in rr if r["importance"] in campaign.CORE),
            "preferred_weight": sum(r["effective_score_weight"] for r in rr if r["importance"] == "preferred"),
            "included": sum(r["included_in_score_denominator"] for r in rr),
            "excluded": sum(not r["score_eligible"] for r in rr),
            "not_in_coverage_denominator": sum(not r["included_in_score_denominator"] for r in rr),
            "labels": dict(Counter(r["evidence_label"] for r in rr)),
            "evaluability": dict(Counter(r["evaluability"] for r in rr)),
            "contributions": dict(Counter(r["contributes"] for r in rr)),
            "weighted_contribution": sum(r["weighted_score_contribution"] for r in rr)}
    limited = [r for r in requirements if r["evaluability"] == LIMITED]
    # Exclusions depend on typed structural receipts; they are report hypotheses
    # rather than an approved fairness policy. Positive structural/NAC cases
    # remain unresolved policy questions, so do not assert a proved bounded fix.
    verdict = "SCORING_ELIGIBILITY_POLICY_AMBIGUOUS" if any(r["evaluability"] != EVALUABLE for r in requirements) else "NO_SCORING_FAIRNESS_PROBLEM_FOUND"
    return {"verdict": verdict, "read_only": True, "counterfactuals_computed": include_counterfactuals,
        "policy_qualification": "Typed missing-scope classifications are diagnostic hypotheses. Positive structural credit, uncalibrated NAC evidence and ambiguous negative predicates prevent a proved neutralization policy.",
        "global": {k: view[k] for k in ("numerator", "denominator", "percentage", "weighted")},
        "per_jd": {str(jid): jd_coverage(snapshot, plan, job_id=jid,
            raw_jd_text=next(j for j in snapshot["audit"]["corpus"]["jobs"] if j["job_id"] == jid)["frozen_inputs"]["raw_jd_text"],
            stable_analysis=next(j for j in snapshot["audit"]["corpus"]["jobs"] if j["job_id"] == jid)["baseline_stable_analysis"])
            for jid in (163, 566, 31, 16) if any(j["job_id"] == jid for j in jobs)},
        "requirements": requirements, "route_summary": groups, "jobs": jobs,
        "not_reliably_evaluable_count": len(limited),
        "not_reliably_evaluable_core_weight": sum(r["effective_score_weight"] for r in limited if r["importance"] in campaign.CORE),
        "tailoring_summary": dict(Counter(r["tailoring_classification"] for r in requirements)),
        "largest_bounded_delta": max((r["delta"] for r in jobs), default=0),
        "average_bounded_delta": sum(r["delta"] for r in jobs)/len(jobs) if jobs else 0,
        "jobs_affected": sum(r["delta"] != 0 for r in jobs),
        "rank_changes": sum(r["rank_delta"] != 0 for r in jobs),
        "network_calls": 0, "model_calls": 0, "publication_calls": 0, "production_mutations": 0,
        "counterfactual_contract": "Report only: frozen native score allocations; native component weights and evidence-strength formula. No sibling weight redistribution.",
        "ranking_contract": "Audit score-descending, job-id tie break; not the live Job Finder search/freshness ordering."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    from taxonomy_discovery.offline_execution import offline_execution
    receipt = json.loads(Path(args.receipt).read_text(encoding="utf-8-sig"))
    with offline_execution("Scoring audit forbids network"):
        result = build_audit(receipt["snapshot"], receipt["plan"])
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    csv_path = Path(args.output).with_suffix(".csv")
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(result["requirements"][0]))
        writer.writeheader()
        for row in result["requirements"]:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in row.items()})
    print(json.dumps({k:v for k,v in result.items() if k not in {"requirements","jobs","per_jd"}}, indent=2))


if __name__ == "__main__":
    main()

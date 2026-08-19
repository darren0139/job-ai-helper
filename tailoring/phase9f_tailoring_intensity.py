"""Pure Phase 9F-C deterministic tailoring-intensity recommendation.

Phase 9F-C consumes one already-ranked, current Phase 9F-B result.  It never
scores resumes, ranks sources, reads persistence, or calls model, embedding,
or Chroma APIs.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from tailoring.phase9f_starting_source_ranking import (
    PHASE9F_B_VERSION,
    Phase9FBRankingError,
    fingerprint_value,
    validate_ranked_candidate_comparison_contract,
    validate_ranked_result_contract,
)
from tailoring.phase9f_exact_verified_reuse import (
    Phase9FExactVerifiedReuseError,
    validate_exact_verified_reuse_proof,
)


PHASE9F_C_VERSION = "phase9f-tailoring-intensity-v2"
PHASE9F_C_POLICY_VERSION = "phase9f-tailoring-intensity-policy-v2"

FULL_REQUIRED_CORE_BELOW = 50
FULL_IMPORTANT_GAP_MINIMUM = 3
FULL_IMPORTANT_GAP_RATIO_NUMERATOR = 1
FULL_IMPORTANT_GAP_RATIO_DENOMINATOR = 5
REUSE_REQUIRED_CORE_MINIMUM = 80
REUSE_ALIGNMENT_MINIMUM = 80
REUSE_EVIDENCE_MINIMUM = 60

IMPORTANT_REQUIREMENTS = {"deal_breaker", "required", "core"}
RATIO_SCOPE_REQUIREMENTS = {"required", "core"}
VALID_IMPORTANCE = IMPORTANT_REQUIREMENTS | {"preferred"}
VALID_MATCH_LABELS = {"direct", "transferable", "weak", "none"}

INTENSITY_LABELS = {
    "reuse": "Reuse",
    "minor": "Minor",
    "full": "Full",
}


class Phase9FCTailoringIntensityError(ValueError):
    """A deterministic Phase 9F-C validation failure."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = str(code)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def zero_cost_diagnostics() -> dict[str, int]:
    return {
        "model_call_count": 0,
        "embedding_call_count": 0,
        "chroma_read_count": 0,
        "chroma_write_count": 0,
        "persistence_write_count": 0,
    }


def tailoring_intensity_policy_identity() -> dict[str, Any]:
    return {
        "policy_version": PHASE9F_C_POLICY_VERSION,
        "precedence": [
            "fail_closed_invalid_phase9f_b",
            "fail_closed_insufficient_important_requirement_scope",
            "reuse_exact_verified_source",
            "full_deal_breaker_gap",
            "full_required_core_below_partial",
            "full_broad_important_gap_deficiency",
            "reuse_all_gates_passed",
            "minor_remaining_valid_scope",
        ],
        "full": {
            "deal_breaker_gap_minimum": 1,
            "required_core_exclusive_maximum": FULL_REQUIRED_CORE_BELOW,
            "important_gap_minimum": FULL_IMPORTANT_GAP_MINIMUM,
            "important_gap_ratio": {
                "numerator": FULL_IMPORTANT_GAP_RATIO_NUMERATOR,
                "denominator": FULL_IMPORTANT_GAP_RATIO_DENOMINATOR,
                "comparison": "inclusive",
                "integer_rule": (
                    "important_gap_count * 5 >= "
                    "important_requirement_count"
                ),
            },
        },
        "reuse": {
            "deal_breaker_gap_count": 0,
            "important_gap_count": 0,
            "required_core_minimum": REUSE_REQUIRED_CORE_MINIMUM,
            "alignment_minimum": REUSE_ALIGNMENT_MINIMUM,
            "evidence_minimum": REUSE_EVIDENCE_MINIMUM,
        },
        "preferred_coverage": "explanatory_only",
        "role_family": "explanatory_only",
        "source_type": "identity_only_not_an_intensity_rule",
        "historical_scores": "provenance_only",
        "source_age": "provenance_only",
        "weighted_phase9f_c_score": False,
    }


def _failure_result(
    *,
    code: str,
    message: str,
    ranking_result: Any,
    expected_ranking_input_fingerprint: str,
    diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    observed = ranking_result if isinstance(ranking_result, dict) else {}
    identity = {
        "format_version": PHASE9F_C_VERSION,
        "policy": tailoring_intensity_policy_identity(),
        "status": "fail_closed",
        "failure_code": code,
        "expected_phase9f_b_ranking_input_fingerprint": _clean(
            expected_ranking_input_fingerprint
        ),
        "observed_phase9f_b_ranking_input_fingerprint": _clean(
            observed.get("ranking_input_fingerprint")
        ),
        "observed_phase9f_b_ranking_fingerprint": _clean(
            observed.get("ranking_fingerprint")
        ),
        "diagnostics": deepcopy(diagnostics or {}),
    }
    return {
        "phase9f_c_version": PHASE9F_C_VERSION,
        "policy_version": PHASE9F_C_POLICY_VERSION,
        "status": "fail_closed",
        "recommended_intensity": None,
        "user_facing_label": "No intensity recommendation",
        "failure_code": code,
        "failure_message": message,
        "semantic_identity": identity,
        "decisive_rule": {
            "code": code,
            "outcome": "fail_closed",
        },
        "evaluated_rules": [],
        "reason_codes": [code],
        "explanation": [message],
        "recommendation_fingerprint": fingerprint_value(identity),
        "zero_cost_diagnostics": zero_cost_diagnostics(),
    }


def _metric(candidate: dict[str, Any], key: str) -> int:
    value = candidate.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise Phase9FCTailoringIntensityError(
            f"The Phase 9F-B winner metric {key} is invalid.",
            code="winner_metric_invalid",
        )
    metric = value
    if not 0 <= metric <= 100:
        raise Phase9FCTailoringIntensityError(
            f"The Phase 9F-B winner metric {key} is outside 0..100.",
            code="winner_metric_out_of_range",
        )
    return metric


def _count(candidate: dict[str, Any], key: str) -> int:
    value = candidate.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise Phase9FCTailoringIntensityError(
            f"The Phase 9F-B winner count {key} is invalid.",
            code="winner_gap_count_invalid",
        )
    count = value
    if count < 0:
        raise Phase9FCTailoringIntensityError(
            f"The Phase 9F-B winner count {key} is negative.",
            code="winner_gap_count_invalid",
        )
    return count


def _canonical_outcomes(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    rows = candidate.get("canonical_requirement_results")
    if not isinstance(rows, list):
        raise Phase9FCTailoringIntensityError(
            "The Phase 9F-B winner has no canonical requirement outcomes.",
            code="canonical_requirement_outcomes_missing",
        )
    outcomes: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise Phase9FCTailoringIntensityError(
                "A canonical requirement outcome is invalid.",
                code="canonical_requirement_outcome_invalid",
            )
        requirement_id = _clean(row.get("requirement_id"))
        importance = _clean(row.get("importance")).lower()
        match_label = _clean(row.get("match_label")).lower()
        if not requirement_id or requirement_id in seen:
            raise Phase9FCTailoringIntensityError(
                "Canonical requirement outcome IDs are missing or duplicated.",
                code="canonical_requirement_ids_ambiguous",
            )
        if importance not in VALID_IMPORTANCE:
            raise Phase9FCTailoringIntensityError(
                "A canonical requirement has unsupported importance.",
                code="canonical_requirement_importance_invalid",
            )
        if match_label not in VALID_MATCH_LABELS:
            raise Phase9FCTailoringIntensityError(
                "A canonical requirement has an unsupported match label.",
                code="canonical_requirement_match_invalid",
            )
        evidence = row.get("evidence_strength")
        if isinstance(evidence, bool) or not isinstance(evidence, int):
            raise Phase9FCTailoringIntensityError(
                "A canonical requirement evidence strength is invalid.",
                code="canonical_requirement_evidence_invalid",
            )
        evidence_strength = evidence
        if not 0 <= evidence_strength <= 5:
            raise Phase9FCTailoringIntensityError(
                "A canonical requirement evidence strength is outside 0..5.",
                code="canonical_requirement_evidence_invalid",
            )
        if match_label == "none" and evidence_strength != 0:
            raise Phase9FCTailoringIntensityError(
                "An unsupported requirement cannot retain evidence strength.",
                code="canonical_requirement_evidence_inconsistent",
            )
        seen.add(requirement_id)
        outcomes.append(
            {
                "requirement_id": requirement_id,
                "importance": importance,
                "match_label": match_label,
                "evidence_strength": evidence_strength,
            }
        )
    return sorted(outcomes, key=lambda row: row["requirement_id"])


def _selected_source_identity(candidate: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "source_type",
        "source_id",
        "source_version",
        "source_fingerprint",
        "source_content_fingerprint",
        "normalized_source_fingerprint",
        "stable_input_fingerprint",
        "comparison_result_fingerprint",
    )
    identity = {key: deepcopy(candidate.get(key)) for key in fields}
    for field in fields:
        value = identity[field]
        if field == "source_version":
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value <= 0
            ):
                raise Phase9FCTailoringIntensityError(
                    "The selected source version is invalid.",
                    code="selected_source_identity_incomplete",
                )
        elif not _clean(value):
            raise Phase9FCTailoringIntensityError(
                "The selected source identity is incomplete.",
                code="selected_source_identity_incomplete",
            )
    if any(
        key in candidate
        for key in (
            "exact_verified_reuse_eligible",
            "exact_verified_reuse_reason_code",
            "exact_verified_reuse_proof_fingerprint",
        )
    ):
        identity["exact_verified_reuse_eligible"] = bool(
            candidate.get("exact_verified_reuse_eligible")
        )
        identity["exact_verified_reuse_reason_code"] = _clean(
            candidate.get("exact_verified_reuse_reason_code")
        )
        identity["exact_verified_reuse_proof_fingerprint"] = _clean(
            candidate.get("exact_verified_reuse_proof_fingerprint")
        )
    return identity


def _exact_jd_identity(
    ranking_result: dict[str, Any],
    outcomes: list[dict[str, Any]],
) -> dict[str, Any]:
    phase9f_b_semantic = ranking_result.get("semantic_identity")
    if not isinstance(phase9f_b_semantic, dict):
        raise Phase9FCTailoringIntensityError(
            "The Phase 9F-B semantic identity is missing.",
            code="phase9f_b_semantic_identity_missing",
        )
    exact_jd = phase9f_b_semantic.get("exact_jd")
    if not isinstance(exact_jd, dict):
        raise Phase9FCTailoringIntensityError(
            "The exact current-JD semantic identity is missing.",
            code="exact_jd_identity_missing",
        )
    required_fields = (
        "raw_jd_sha256",
        "structured_profile_fingerprint",
        "canonical_requirement_fingerprint",
    )
    if any(not _clean(exact_jd.get(field)) for field in required_fields):
        raise Phase9FCTailoringIntensityError(
            "The exact current-JD semantic identity is incomplete.",
            code="exact_jd_identity_incomplete",
        )
    expected_ids = sorted(
        _clean(value) for value in exact_jd.get("canonical_requirement_ids") or []
    )
    outcome_ids = sorted(row["requirement_id"] for row in outcomes)
    if expected_ids != outcome_ids:
        raise Phase9FCTailoringIntensityError(
            "The winner outcomes do not match the exact current-JD scope.",
            code="canonical_requirement_scope_mismatch",
        )
    provenance = ranking_result.get("jd_provenance") or {}
    return {
        "semantic_identity": deepcopy(exact_jd),
        "canonical_jd_id": _clean(provenance.get("canonical_jd_id")),
        "source_version_id": _clean(provenance.get("source_version_id")),
        "phase9f_a_snapshot_fingerprint": _clean(
            provenance.get("phase9f_a_snapshot_fingerprint")
        ),
    }


def _minor_reason_codes(
    *,
    overall: int,
    required: int,
    evidence: int,
    important_gaps: int,
) -> list[str]:
    reasons: list[str] = []
    if important_gaps:
        reasons.append("bounded_important_gaps")
    if required < REUSE_REQUIRED_CORE_MINIMUM:
        reasons.append("required_core_below_reuse_minimum")
    if overall < REUSE_ALIGNMENT_MINIMUM:
        reasons.append("alignment_below_reuse_minimum")
    if evidence < REUSE_EVIDENCE_MINIMUM:
        reasons.append("evidence_below_reuse_minimum")
    return reasons or ["remaining_valid_scope_requires_minor_tailoring"]


def recommend_tailoring_intensity(
    ranking_result: Any,
    *,
    expected_ranking_input_fingerprint: str,
) -> dict[str, Any]:
    """Recommend Reuse, Minor, or Full from the exact current 9F-B winner."""
    exact_proof: dict[str, Any] | None = None
    try:
        validated = validate_ranked_result_contract(
            ranking_result,
            expected_ranking_input_fingerprint=(
                expected_ranking_input_fingerprint
            ),
        )
        winner = validated["recommended_source"]
        validate_ranked_candidate_comparison_contract(winner)
        outcomes = _canonical_outcomes(winner)
        source_identity = _selected_source_identity(winner)
        exact_jd_identity = _exact_jd_identity(ranking_result, outcomes)

        overall = _metric(winner, "deterministic_alignment_score")
        required = _metric(winner, "required_core_coverage_score")
        preferred = _metric(winner, "preferred_coverage_score")
        evidence = _metric(winner, "evidence_strength_score")
        important_gaps = _count(winner, "important_gap_count")
        deal_breakers = _count(winner, "deal_breaker_gap_count")

        computed_gap_rows = [
            row
            for row in outcomes
            if row["importance"] in IMPORTANT_REQUIREMENTS
            and row["match_label"] == "none"
        ]
        computed_deal_breakers = sum(
            row["importance"] == "deal_breaker"
            for row in computed_gap_rows
        )
        if (
            important_gaps != len(computed_gap_rows)
            or deal_breakers != computed_deal_breakers
        ):
            raise Phase9FCTailoringIntensityError(
                "The Phase 9F-B gap counts do not match canonical outcomes.",
                code="canonical_gap_count_mismatch",
            )
        important_requirement_count = sum(
            row["importance"] in RATIO_SCOPE_REQUIREMENTS
            for row in outcomes
        )
        if important_requirement_count == 0:
            return _failure_result(
                code="insufficient_important_requirement_scope",
                message=(
                    "No canonical Core or Required requirements are available; "
                    "Phase 9F-C cannot safely recommend Reuse, Minor, or Full."
                ),
                ranking_result=ranking_result,
                expected_ranking_input_fingerprint=(
                    expected_ranking_input_fingerprint
                ),
                diagnostics={
                    "important_requirement_count": 0,
                    "canonical_requirement_count": len(outcomes),
                },
            )

        canonical_scope = _clean(
            winner.get("canonical_requirement_scope_fingerprint")
        )
        exact_scope = _clean(
            exact_jd_identity["semantic_identity"].get(
                "canonical_requirement_fingerprint"
            )
        )
        if not canonical_scope or canonical_scope != exact_scope:
            raise Phase9FCTailoringIntensityError(
                "The winner canonical requirement scope is inconsistent.",
                code="canonical_requirement_fingerprint_mismatch",
            )
        try:
            candidate_proof = validate_exact_verified_reuse_proof(
                winner.get("exact_verified_reuse"),
                source_type=_clean(winner.get("source_type")),
                source_id=_clean(winner.get("source_id")),
                source_fingerprint=_clean(winner.get("source_fingerprint")),
            )
        except Phase9FExactVerifiedReuseError as exc:
            raise Phase9FCTailoringIntensityError(
                str(exc), code="exact_verified_reuse_proof_invalid"
            ) from exc
        if candidate_proof.get("eligible") is True:
            exact_proof = candidate_proof
    except Phase9FBRankingError as exc:
        diagnostic = getattr(exc, "diagnostic", {}) or {}
        return _failure_result(
            code=_clean(diagnostic.get("code")) or "invalid_phase9f_b_result",
            message=_clean(diagnostic.get("message")) or str(exc),
            ranking_result=ranking_result,
            expected_ranking_input_fingerprint=(
                expected_ranking_input_fingerprint
            ),
        )
    except Phase9FCTailoringIntensityError as exc:
        return _failure_result(
            code=exc.code,
            message=str(exc),
            ranking_result=ranking_result,
            expected_ranking_input_fingerprint=(
                expected_ranking_input_fingerprint
            ),
        )

    broad_gap_deficiency = bool(
        important_gaps >= FULL_IMPORTANT_GAP_MINIMUM
        and important_gaps * FULL_IMPORTANT_GAP_RATIO_DENOMINATOR
        >= important_requirement_count * FULL_IMPORTANT_GAP_RATIO_NUMERATOR
    )
    reuse_gates = {
        "no_deal_breaker_gaps": deal_breakers == 0,
        "no_important_gaps": important_gaps == 0,
        "required_core_at_least_80": (
            required >= REUSE_REQUIRED_CORE_MINIMUM
        ),
        "alignment_at_least_80": overall >= REUSE_ALIGNMENT_MINIMUM,
        "evidence_at_least_60": evidence >= REUSE_EVIDENCE_MINIMUM,
    }
    evaluated_rules = [
        {
            "code": "reuse_exact_verified_source",
            "matched": exact_proof is not None,
            "observed": {
                "proof_fingerprint": _clean(
                    (exact_proof or {}).get("proof_fingerprint")
                ),
                "verified_score": int(
                    (exact_proof or {}).get("verified_score") or 0
                ),
            },
            "operator": "authoritative exact immutable JD/artifact proof",
            "threshold": True,
        },
        {
            "code": "full_deal_breaker_gap",
            "matched": deal_breakers >= 1,
            "observed": deal_breakers,
            "operator": ">=",
            "threshold": 1,
        },
        {
            "code": "full_required_core_below_partial",
            "matched": required < FULL_REQUIRED_CORE_BELOW,
            "observed": required,
            "operator": "<",
            "threshold": FULL_REQUIRED_CORE_BELOW,
        },
        {
            "code": "full_broad_important_gap_deficiency",
            "matched": broad_gap_deficiency,
            "observed": {
                "important_gap_count": important_gaps,
                "important_requirement_count": important_requirement_count,
            },
            "operator": "gaps >= 3 and gaps * 5 >= important scope",
            "threshold": {"minimum_gap_count": 3, "minimum_ratio": "1/5"},
        },
        {
            "code": "reuse_all_gates_passed",
            "matched": all(reuse_gates.values()),
            "observed": deepcopy(reuse_gates),
            "operator": "all",
            "threshold": True,
        },
    ]

    if exact_proof is not None:
        intensity = "reuse"
        decisive_code = "reuse_exact_verified_source"
        explanation = [
            "This Blueprint is the approved one-page artifact already verified against this exact JD.",
            f"Verified exact-JD score: {int(exact_proof.get('verified_score') or 0)}.",
            "Fresh Phase 9F-B metrics remain diagnostic and do not retarget this exact verified artifact.",
        ]
    elif deal_breakers >= 1:
        intensity = "full"
        decisive_code = "full_deal_breaker_gap"
        explanation = [
            f"{deal_breakers} unsupported deal-breaker requirement(s) exist.",
            "Deal-breaker gaps take precedence over all aggregate scores.",
        ]
    elif required < FULL_REQUIRED_CORE_BELOW:
        intensity = "full"
        decisive_code = "full_required_core_below_partial"
        explanation = [
            f"Required/Core coverage is {required}%, below the 50% boundary.",
            "This is a material current-JD deficiency requiring broad tailoring.",
        ]
    elif broad_gap_deficiency:
        intensity = "full"
        decisive_code = "full_broad_important_gap_deficiency"
        explanation = [
            f"{important_gaps} of {important_requirement_count} Core/Required "
            "requirements are unsupported.",
            "The gap count is at least 3 and its scope is at least 20%.",
        ]
    elif all(reuse_gates.values()):
        intensity = "reuse"
        decisive_code = "reuse_all_gates_passed"
        explanation = [
            "All deterministic Reuse gates passed.",
            "No important or deal-breaker gaps remain for the current JD.",
        ]
    else:
        intensity = "minor"
        decisive_code = "minor_remaining_valid_scope"
        explanation = [
            "No Full rule fired, but one or more Reuse gates did not pass.",
            "Preserve the selected source and make bounded, targeted changes.",
        ]

    matched_full_codes = [
        row["code"] for row in evaluated_rules[1:4] if row["matched"]
    ]
    if intensity == "full":
        reason_codes = matched_full_codes
    elif intensity == "reuse":
        reason_codes = [decisive_code]
    else:
        reason_codes = _minor_reason_codes(
            overall=overall,
            required=required,
            evidence=evidence,
            important_gaps=important_gaps,
        )

    metrics = {
        "current_jd_alignment": overall,
        "required_core_coverage": required,
        "preferred_coverage": preferred,
        "evidence_strength": evidence,
        "important_gap_count": important_gaps,
        "deal_breaker_gap_count": deal_breakers,
        "important_requirement_count": important_requirement_count,
        "important_gap_ratio": {
            "numerator": important_gaps,
            "denominator": important_requirement_count,
        },
    }
    semantic_identity = {
        "format_version": PHASE9F_C_VERSION,
        "policy": tailoring_intensity_policy_identity(),
        "phase9f_b": {
            "format_version": PHASE9F_B_VERSION,
            "ranking_input_fingerprint": _clean(
                ranking_result.get("ranking_input_fingerprint")
            ),
            "ranking_fingerprint": validated["ranking_fingerprint"],
        },
        "selected_source": source_identity,
        "exact_verified_reuse": deepcopy(exact_proof or {}),
        "exact_jd": exact_jd_identity,
        "current_jd_winner": {
            "metrics": metrics,
            "canonical_requirement_scope_fingerprint": canonical_scope,
            "canonical_requirement_outcomes": outcomes,
        },
    }
    recommendation_identity = {
        "semantic_identity": semantic_identity,
        "recommended_intensity": intensity,
        "decisive_rule_code": decisive_code,
        "reason_codes": reason_codes,
    }
    return {
        "phase9f_c_version": PHASE9F_C_VERSION,
        "policy_version": PHASE9F_C_POLICY_VERSION,
        "status": "recommended",
        "recommended_intensity": intensity,
        "user_facing_label": INTENSITY_LABELS[intensity],
        "semantic_identity": semantic_identity,
        "selected_source_context": {
            "display_name": _clean(winner.get("source_display_name")),
            "source_type": _clean(winner.get("source_type")),
            "role_family_relationship": _clean(
                winner.get("role_family_relationship")
            ),
            "role_family_prior_applied": bool(
                winner.get("role_family_prior_applied")
            ),
            "exact_verified_reuse": deepcopy(exact_proof or {}),
        },
        "metrics": metrics,
        "important_gaps": deepcopy(winner.get("important_gaps") or []),
        "decisive_rule": next(
            (
                deepcopy(row)
                for row in evaluated_rules
                if row["code"] == decisive_code
            ),
            {
                "code": decisive_code,
                "matched": True,
                "observed": None,
                "operator": "fallback",
                "threshold": None,
            },
        ),
        "evaluated_rules": evaluated_rules,
        "reuse_gates": reuse_gates,
        "reason_codes": reason_codes,
        "explanation": explanation,
        "recommendation_fingerprint": fingerprint_value(
            recommendation_identity
        ),
        "zero_cost_diagnostics": zero_cost_diagnostics(),
    }

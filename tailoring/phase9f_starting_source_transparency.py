"""Pure Phase 9F-B ranking transparency helpers.

The helpers in this module explain an already-computed ranking. They do not
score resumes, call external services, read persistence, or mutate ranking
results.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from copy import deepcopy
from io import StringIO
from typing import Any, Iterable


PHASE9F_B_TRANSPARENCY_VERSION = "phase9f-starting-source-transparency-v1"
MAX_EVIDENCE_SNIPPET_CHARS = 240
MAX_REASON_CHARS = 220


_METRIC_RULES = (
    {
        "key": "deal_breaker_free",
        "label": "No deal-breaker gap",
        "direction": "higher",
    },
    {
        "key": "deal_breaker_gap_count",
        "label": "Deal-breaker gaps",
        "direction": "lower",
    },
    {
        "key": "required_core_coverage_score",
        "label": "Required/Core coverage",
        "direction": "higher",
    },
    {
        "key": "deterministic_alignment_score",
        "label": "Current JD alignment",
        "direction": "higher",
    },
    {
        "key": "evidence_strength_score",
        "label": "Evidence strength",
        "direction": "higher",
    },
    {
        "key": "important_gap_count",
        "label": "Important gaps",
        "direction": "lower",
    },
    {
        "key": "preferred_coverage_score",
        "label": "Preferred coverage",
        "direction": "higher",
    },
)

_PRIORITY_LABELS = {
    "no_deal_breaker_gap": "No deal-breaker gap",
    "fewer_deal_breaker_gaps": "Fewer deal-breaker gaps",
    "required_core_coverage": "Higher Required/Core coverage",
    "overall_canonical_alignment": "Higher Current JD alignment",
    "evidence_strength": "Higher evidence strength",
    "fewer_important_gaps": "Fewer important gaps",
    "preferred_coverage": "Higher Preferred coverage",
    "same_family_near_tie_prior": (
        "Same-family prior only inside the calibrated near tie"
    ),
    "stable_source_fingerprint": "Stable source fingerprint tie-break",
}

_TOLERANCE_LABELS = {
    "deal_breaker_gap_count": "Deal-breaker gap difference",
    "required_core_coverage_points": "Required/Core",
    "overall_alignment_points": "Current JD alignment",
    "evidence_strength_points": "Evidence strength",
    "important_gap_count": "Important-gap difference",
    "preferred_coverage_points": "Preferred coverage",
}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def _clip(value: Any, limit: int) -> str:
    cleaned = _clean(value)
    if len(cleaned) <= limit:
        return cleaned
    clipped = cleaned[: max(1, limit - 1)].rstrip()
    if " " in clipped:
        clipped = clipped.rsplit(" ", 1)[0]
    return clipped.rstrip(".,;:") + "…"


def compact_requirement_transparency(
    requirement_rows: Iterable[dict[str, Any]],
    validation_warnings: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Copy the smallest scorer-emitted evidence needed for explanation."""
    warnings_by_requirement: dict[str, list[dict[str, str]]] = defaultdict(list)
    for warning in validation_warnings:
        if not isinstance(warning, dict):
            continue
        requirement_id = _clean(warning.get("requirement_id"))
        if not requirement_id:
            continue
        warnings_by_requirement[requirement_id].append(
            {
                "code": _clean(warning.get("code")),
                "message": _clip(warning.get("message"), MAX_REASON_CHARS),
            }
        )

    compact: list[dict[str, Any]] = []
    for row in requirement_rows:
        if not isinstance(row, dict):
            continue
        requirement_id = _clean(row.get("requirement_id"))
        evidence_rows = []
        for evidence in row.get("evidence", []) or []:
            if not isinstance(evidence, dict):
                continue
            evidence_rows.append(
                {
                    "section": _clean(evidence.get("section")),
                    "source": _clean(evidence.get("source")),
                    "text": _clip(
                        evidence.get("text"),
                        MAX_EVIDENCE_SNIPPET_CHARS,
                    ),
                    "reason": _clip(evidence.get("reason"), MAX_REASON_CHARS),
                    "evidence_similarity": _clean(
                        evidence.get("evidence_similarity")
                    ),
                }
            )
        compact.append(
            {
                "requirement_id": requirement_id,
                "text": _clean(row.get("text")),
                "importance": _clean(row.get("importance")),
                "match_label": _clean(row.get("match_label")),
                "evidence_strength": int(row.get("evidence_strength") or 0),
                "matched_keyword": _clean(row.get("matched_keyword")),
                "match_source": _clean(row.get("match_source")),
                "match_similarity": row.get("match_similarity"),
                "match_coverage": row.get("match_coverage"),
                "supporting_evidence": evidence_rows,
                "deterministic_reasons": deepcopy(
                    warnings_by_requirement.get(requirement_id, [])
                ),
                "taxonomy": {
                    "cap_status": _clean(
                        row.get("capability_taxonomy_cap_status")
                    ),
                    "capability_id": _clean(row.get("capability_id")),
                    "does_not_prove": [
                        _clip(value, MAX_REASON_CHARS)
                        for value in row.get("capability_does_not_prove", []) or []
                        if _clean(value)
                    ],
                },
            }
        )
    return compact


def _metric_value(candidate: dict[str, Any], key: str) -> int:
    if key == "deal_breaker_free":
        return int(int(candidate.get("deal_breaker_gap_count") or 0) == 0)
    return int(candidate.get(key) or 0)


def _metric_comparisons(
    winner: dict[str, Any],
    runner_up: dict[str, Any],
) -> list[dict[str, Any]]:
    comparisons = []
    for rule in _METRIC_RULES:
        winner_value = _metric_value(winner, rule["key"])
        runner_value = _metric_value(runner_up, rule["key"])
        if winner_value == runner_value:
            favored = "equal"
        elif (
            rule["direction"] == "higher" and winner_value > runner_value
        ) or (
            rule["direction"] == "lower" and winner_value < runner_value
        ):
            favored = "winner"
        else:
            favored = "runner_up"
        comparisons.append(
            {
                "metric": rule["label"],
                "metric_key": rule["key"],
                "winner_value": winner_value,
                "runner_up_value": runner_value,
                "preferred_direction": rule["direction"],
                "favored": favored,
            }
        )
    return comparisons


def _near_tie_checks(
    family_candidate: dict[str, Any],
    anchor: dict[str, Any],
    tolerances: dict[str, Any],
) -> list[dict[str, Any]]:
    specifications = (
        (
            "deal_breaker_gap_count",
            abs(
                int(anchor.get("deal_breaker_gap_count") or 0)
                - int(family_candidate.get("deal_breaker_gap_count") or 0)
            ),
            "deal_breaker_gap_count",
        ),
        (
            "required_core_coverage_points",
            int(anchor.get("required_core_coverage_score") or 0)
            - int(family_candidate.get("required_core_coverage_score") or 0),
            "required_core_coverage_score",
        ),
        (
            "overall_alignment_points",
            int(anchor.get("deterministic_alignment_score") or 0)
            - int(family_candidate.get("deterministic_alignment_score") or 0),
            "deterministic_alignment_score",
        ),
        (
            "evidence_strength_points",
            int(anchor.get("evidence_strength_score") or 0)
            - int(family_candidate.get("evidence_strength_score") or 0),
            "evidence_strength_score",
        ),
        (
            "important_gap_count",
            int(family_candidate.get("important_gap_count") or 0)
            - int(anchor.get("important_gap_count") or 0),
            "important_gap_count",
        ),
        (
            "preferred_coverage_points",
            int(anchor.get("preferred_coverage_score") or 0)
            - int(family_candidate.get("preferred_coverage_score") or 0),
            "preferred_coverage_score",
        ),
    )
    checks = []
    for tolerance_key, raw_difference, metric_key in specifications:
        difference = max(0, int(raw_difference))
        threshold = int(tolerances.get(tolerance_key) or 0)
        checks.append(
            {
                "metric": _TOLERANCE_LABELS[tolerance_key],
                "metric_key": metric_key,
                "difference": difference,
                "tolerance": threshold,
                "within_tolerance": difference <= threshold,
            }
        )
    return checks


def _source_provenance_map(result: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (_clean(row.get("source_type")), _clean(row.get("source_id"))): row
        for row in result.get("source_provenance", []) or []
        if isinstance(row, dict)
    }


def _source_context(result: dict[str, Any]) -> list[dict[str, Any]]:
    provenance = _source_provenance_map(result)
    rows = []
    for candidate in result.get("ranked_candidates", []) or []:
        source_type = _clean(candidate.get("source_type"))
        source_id = _clean(candidate.get("source_id"))
        source_provenance = provenance.get((source_type, source_id), {})
        is_blueprint = source_type == "global_blueprint"
        rows.append(
            {
                "rank": int(candidate.get("rank") or 0),
                "source_type": source_type,
                "source_id": source_id,
                "source_display_name": _clean(
                    candidate.get("source_display_name")
                ),
                "source_version": int(candidate.get("source_version") or 0),
                "frozen_or_created_at": _clean(
                    source_provenance.get("created_at")
                ),
                "source_fingerprint": _clean(
                    candidate.get("source_fingerprint")
                ),
                "historical_blueprint_provenance_applicable": is_blueprint,
                "historical_blueprint_score_label": (
                    "Available in Blueprint provenance"
                    if is_blueprint
                    else "Not applicable"
                ),
            }
        )
    return rows


def _requirement_comparison(result: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = result.get("ranked_candidates", []) or []
    if not candidates:
        return []
    expected_ids = [
        _clean(row.get("requirement_id"))
        for row in candidates[0].get("canonical_requirement_results", []) or []
    ]
    if not expected_ids:
        return []

    comparison: list[dict[str, Any]] = []
    for candidate in candidates:
        compact_results = {
            _clean(row.get("requirement_id")): row
            for row in candidate.get("canonical_requirement_results", []) or []
            if isinstance(row, dict)
        }
        transparency_results = {
            _clean(row.get("requirement_id")): row
            for row in candidate.get("canonical_requirement_transparency", []) or []
            if isinstance(row, dict)
        }
        if set(compact_results) != set(expected_ids):
            return []
        for requirement_id in expected_ids:
            semantic = compact_results[requirement_id]
            details = transparency_results.get(requirement_id, {})
            evidence_rows = details.get("supporting_evidence", []) or []
            evidence = evidence_rows[0] if evidence_rows else {}
            reasons = details.get("deterministic_reasons", []) or []
            reason = reasons[0] if reasons else {}
            taxonomy = details.get("taxonomy") or {}
            comparison.append(
                {
                    "requirement_id": requirement_id,
                    "requirement_text": _clean(details.get("text")),
                    "importance": _clean(
                        details.get("importance") or semantic.get("importance")
                    ),
                    "source_rank": int(candidate.get("rank") or 0),
                    "source_name": _clean(candidate.get("source_display_name")),
                    "source_type": _clean(candidate.get("source_type")),
                    "match_label": _clean(semantic.get("match_label")),
                    "evidence_strength": int(
                        semantic.get("evidence_strength") or 0
                    ),
                    "evidence_section": _clean(evidence.get("section")),
                    "evidence_source": _clean(evidence.get("source")),
                    "supporting_evidence": _clean(evidence.get("text")),
                    "matched_keyword": _clean(details.get("matched_keyword")),
                    "deterministic_reason_code": _clean(reason.get("code")),
                    "deterministic_reason": _clean(reason.get("message")),
                    "taxonomy_cap_status": _clean(taxonomy.get("cap_status")),
                    "capability_id": _clean(taxonomy.get("capability_id")),
                }
            )
    return comparison


REQUIREMENT_COMPARISON_CSV_COLUMNS = (
    "Requirement ID",
    "Requirement",
    "Importance",
    "Source rank",
    "Source",
    "Source type",
    "Match",
    "Evidence strength",
    "Evidence section",
    "Evidence source",
    "Supporting evidence",
    "Matched keyword",
    "Deterministic reason code",
    "Deterministic reason",
    "Taxonomy cap",
    "Capability ID",
)


def build_requirement_comparison_csv(
    transparency: dict[str, Any],
) -> str:
    """Serialize the existing requirement explanation rows without rescoring."""
    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=REQUIREMENT_COMPARISON_CSV_COLUMNS,
        lineterminator="\n",
        extrasaction="ignore",
    )
    writer.writeheader()
    for row in transparency.get("requirement_comparison", []) or []:
        if not isinstance(row, dict):
            continue
        writer.writerow(
            {
                "Requirement ID": _clean(row.get("requirement_id")),
                "Requirement": _clean(row.get("requirement_text")),
                "Importance": _clean(row.get("importance")),
                "Source rank": int(row.get("source_rank") or 0),
                "Source": _clean(row.get("source_name")),
                "Source type": _clean(row.get("source_type")),
                "Match": _clean(row.get("match_label")),
                "Evidence strength": int(row.get("evidence_strength") or 0),
                "Evidence section": _clean(row.get("evidence_section")),
                "Evidence source": _clean(row.get("evidence_source")),
                "Supporting evidence": _clean(row.get("supporting_evidence")),
                "Matched keyword": _clean(row.get("matched_keyword")),
                "Deterministic reason code": _clean(
                    row.get("deterministic_reason_code")
                ),
                "Deterministic reason": _clean(
                    row.get("deterministic_reason")
                ),
                "Taxonomy cap": _clean(row.get("taxonomy_cap_status")),
                "Capability ID": _clean(row.get("capability_id")),
            }
        )
    return output.getvalue()


def build_ranking_transparency(result: dict[str, Any]) -> dict[str, Any]:
    """Explain one existing result without changing or re-scoring it."""
    candidates = sorted(
        (
            deepcopy(row)
            for row in result.get("ranked_candidates", []) or []
            if isinstance(row, dict)
        ),
        key=lambda row: int(row.get("rank") or 0),
    )
    policy = (
        (result.get("semantic_identity") or {}).get("ranking_policy") or {}
    )
    priority = [
        {
            "position": index,
            "policy_key": _clean(key),
            "label": _PRIORITY_LABELS.get(_clean(key), _clean(key)),
        }
        for index, key in enumerate(policy.get("priority_order", []) or [], start=1)
    ]
    tolerances = deepcopy(policy.get("role_family_near_tie_tolerances") or {})
    base = {
        "transparency_version": PHASE9F_B_TRANSPARENCY_VERSION,
        "ranking_input_fingerprint": _clean(
            result.get("ranking_input_fingerprint")
        ),
        "ranking_fingerprint": _clean(result.get("ranking_fingerprint")),
        "priority_order": priority,
        "near_tie_tolerances": tolerances,
        "role_family_score_bonus": int(policy.get("role_family_score_bonus") or 0),
        "role_family_statement": (
            "Role family never adds points to the canonical score."
        ),
        "source_context": _source_context(result),
        "requirement_comparison": _requirement_comparison(result),
        "zero_cost_diagnostics": {
            "model_call_count": 0,
            "embedding_call_count": 0,
            "chroma_read_count": 0,
            "chroma_write_count": 0,
            "persistence_write_count": 0,
        },
    }
    if not candidates:
        return {**base, "winner_explanation": None, "pairwise_comparison": None}

    winner = candidates[0]
    if len(candidates) == 1:
        explanation = {
            "winner_name": _clean(winner.get("source_display_name")),
            "runner_up_name": "",
            "headline": "This was the only eligible immutable starting source.",
            "deciding_rule": "only_eligible_source",
            "summary_lines": [],
        }
        return {
            **base,
            "winner_explanation": explanation,
            "pairwise_comparison": None,
        }

    runner_up = candidates[1]
    comparisons = _metric_comparisons(winner, runner_up)
    canonical_equal = all(row["favored"] == "equal" for row in comparisons)
    all_candidates_canonical_equal = all(
        all(
            comparison["favored"] == "equal"
            for comparison in _metric_comparisons(winner, candidate)
        )
        for candidate in candidates[1:]
    )
    role_prior_applied = bool(winner.get("role_family_prior_applied"))

    near_tie_status = "not_eligible"
    near_tie_checks: list[dict[str, Any]] = []
    if role_prior_applied:
        near_tie_status = "applied"
        near_tie_checks = _near_tie_checks(winner, runner_up, tolerances)
    elif runner_up.get("role_family_prior_eligible"):
        near_tie_checks = _near_tie_checks(runner_up, winner, tolerances)
        near_tie_status = (
            "within_tolerance_not_selected"
            if all(row["within_tolerance"] for row in near_tie_checks)
            else "outside_tolerance"
        )
    elif winner.get("role_family_prior_eligible"):
        near_tie_status = "not_needed_strict_winner_is_same_family"

    if role_prior_applied:
        deciding_rule = "same_family_near_tie_prior"
        headline = (
            f"{_clean(winner.get('source_display_name'))} ranked above "
            f"{_clean(runner_up.get('source_display_name'))} because the "
            "high/medium-confidence same-family prior broke a calibrated near tie."
        )
    else:
        decisive = next(
            (row for row in comparisons if row["favored"] == "winner"),
            None,
        )
        if decisive is None and canonical_equal:
            deciding_rule = "stable_source_fingerprint"
            decisive_label = "stable source fingerprint tie-break"
        elif decisive is None:
            deciding_rule = "deterministic_priority_order"
            decisive_label = "deterministic priority order"
        else:
            deciding_rule = decisive["metric_key"]
            decisive_label = decisive["metric"]
        headline = (
            f"{_clean(winner.get('source_display_name'))} ranked above "
            f"{_clean(runner_up.get('source_display_name'))}. The first "
            f"decisive rule was {decisive_label}."
        )

    summary_lines = []
    for row in comparisons:
        if row["metric_key"] == "deal_breaker_free":
            continue
        if row["winner_value"] != row["runner_up_value"]:
            summary_lines.append(
                f"{row['metric']}: {row['winner_value']} vs "
                f"{row['runner_up_value']} ({row['favored'].replace('_', ' ')} favored)."
            )
    if all_candidates_canonical_equal:
        summary_lines.append(
            "All eligible candidates had equal displayed canonical metrics."
        )
    elif canonical_equal:
        summary_lines.append("The #1 and #2 displayed canonical metrics were equal.")

    failed_checks = [
        deepcopy(row) for row in near_tie_checks if not row["within_tolerance"]
    ]
    if role_prior_applied:
        prior_reason = (
            "Applied because the winner was same-family eligible and every "
            "calibrated near-tie check passed."
        )
    elif near_tie_status == "outside_tolerance":
        prior_reason = (
            "Not applied because the eligible same-family candidate exceeded "
            "one or more calibrated near-tie tolerances."
        )
    elif near_tie_status == "not_needed_strict_winner_is_same_family":
        prior_reason = (
            "Not needed because the strict canonical comparator already ranked "
            "the same-family candidate first."
        )
    elif near_tie_status == "within_tolerance_not_selected":
        prior_reason = (
            "The candidate was eligible and within tolerance, but did not "
            "displace the strict winner under the same-family candidate order."
        )
    else:
        prior_reason = (
            "Not applied because neither displayed candidate was an eligible "
            "same-family source for the current role-family confidence."
        )
    pairwise = {
        "winner_name": _clean(winner.get("source_display_name")),
        "runner_up_name": _clean(runner_up.get("source_display_name")),
        "winner_source_id": _clean(winner.get("source_id")),
        "runner_up_source_id": _clean(runner_up.get("source_id")),
        "winner_role_family_relationship": _clean(
            winner.get("role_family_relationship")
        ),
        "runner_up_role_family_relationship": _clean(
            runner_up.get("role_family_relationship")
        ),
        "winner_role_family_prior_eligible": bool(
            winner.get("role_family_prior_eligible")
        ),
        "runner_up_role_family_prior_eligible": bool(
            runner_up.get("role_family_prior_eligible")
        ),
        "metric_comparisons": comparisons,
        "canonical_metrics_equal": canonical_equal,
        "all_candidates_canonical_metrics_equal": (
            all_candidates_canonical_equal
        ),
        "deciding_rule": deciding_rule,
        "near_tie_status": near_tie_status,
        "near_tie_checks": near_tie_checks,
        "failed_near_tie_checks": failed_checks,
        "role_family_prior_applied": role_prior_applied,
        "role_family_prior_reason": prior_reason,
        "role_family_statement": base["role_family_statement"],
    }
    return {
        **base,
        "winner_explanation": {
            "winner_name": pairwise["winner_name"],
            "runner_up_name": pairwise["runner_up_name"],
            "headline": headline,
            "deciding_rule": deciding_rule,
            "summary_lines": summary_lines,
            "near_tie_status": near_tie_status,
            "failed_near_tie_checks": failed_checks,
            "role_family_prior_applied": role_prior_applied,
        },
        "pairwise_comparison": pairwise,
    }

"""Deterministic explainability helpers for Phase 8 alignment scores.

This reconstructs the existing stable scorer arithmetic from canonical rows for
presentation/audit only. It never changes match labels, weights, taxonomy caps,
or the stored scorer result.
"""
from __future__ import annotations

from typing import Any

from analysis_stability.stable_evidence_scoring import (
    IMPORTANCE_WEIGHTS,
    MATCH_VALUES,
)

PHASE8_SCORE_EXPLAINABILITY_VERSION = "phase8-score-explainability-v1"
PHASE8_SCORE_EXPLAINABILITY_PRESENTATION_PATCH = "phase8-score-explainability-presentation-v2"
PHASE8_SCORE_RECEIPT_VERSION = "phase8-score-receipt-v2-jd-map"

_REQUIRED_CORE = {"deal_breaker", "required", "core"}
_PREFERRED = {"preferred"}
_MATCH_RANK = {"none": 0, "weak": 1, "transferable": 2, "direct": 3}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def _rows(analysis: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(analysis, dict):
        return []
    return [
        row
        for row in analysis.get("canonical_requirements", []) or []
        if isinstance(row, dict)
    ]


def _label(row: dict[str, Any]) -> str:
    value = _clean(row.get("match_label")).lower()
    return value if value in MATCH_VALUES else "none"


def _value(row: dict[str, Any]) -> float:
    label = _label(row)
    try:
        value = float(row.get("match_value"))
    except (TypeError, ValueError):
        value = float(MATCH_VALUES[label])
    return max(0.0, min(1.0, value))


def _strength(row: dict[str, Any]) -> int:
    try:
        value = int(row.get("evidence_strength", 0) or 0)
    except (TypeError, ValueError):
        value = 0
    return min(5, max(0, value))


def _evidence(row: dict[str, Any]) -> str:
    values = row.get("evidence", []) or []
    if not isinstance(values, list):
        return ""
    for item in values:
        if isinstance(item, dict):
            text = _clean(
                item.get("text")
                or item.get("matched_resume_term")
                or item.get("snippet")
            )
        else:
            text = _clean(item)
        if text:
            return text
    return ""


def _coverage_component(
    rows: list[dict[str, Any]],
    *,
    accepted: set[str],
    key: str,
    name: str,
) -> dict[str, Any]:
    eligible = [
        row
        for row in rows
        if _clean(row.get("importance")).lower() in accepted
    ]
    group_counts: dict[str, int] = {}
    for row in eligible:
        requirement_id = _clean(row.get("requirement_id"))
        group_id = _clean(row.get("atomic_group_id") or requirement_id)
        group_counts[group_id] = group_counts.get(group_id, 0) + 1

    numerator = 0.0
    denominator = 0.0
    contributions: list[dict[str, Any]] = []
    for row in eligible:
        requirement_id = _clean(row.get("requirement_id"))
        group_id = _clean(row.get("atomic_group_id") or requirement_id)
        importance = _clean(row.get("importance")).lower()
        group_fraction = 1.0 / max(1, group_counts.get(group_id, 1))
        importance_weight = float(IMPORTANCE_WEIGHTS.get(importance, 0.0))
        effective_weight = importance_weight * group_fraction
        match_value = _value(row)
        numerator_part = effective_weight * match_value
        numerator += numerator_part
        denominator += effective_weight
        contributions.append(
            {
                "requirement_id": requirement_id,
                "requirement": _clean(row.get("text") or row.get("atomic_focus")),
                "importance": importance,
                "component": key,
                "atomic_group_id": group_id,
                "group_weight_fraction": round(group_fraction, 6),
                "importance_weight": importance_weight,
                "effective_weight": round(effective_weight, 6),
                "match_label": _label(row),
                "match_value": match_value,
                "coverage_numerator_contribution": round(numerator_part, 6),
                "evidence_strength": _strength(row),
                "evidence": _evidence(row),
            }
        )

    score = 100.0 * numerator / denominator if denominator else 0.0
    for item in contributions:
        item["component_coverage_points"] = round(
            100.0 * float(item["coverage_numerator_contribution"]) / denominator
            if denominator
            else 0.0,
            6,
        )
    return {
        "key": key,
        "label": name,
        "score": score,
        "numerator": numerator,
        "denominator": denominator,
        "requirements": contributions,
    }


def build_score_breakdown(analysis: dict[str, Any] | None) -> dict[str, Any]:
    analysis = analysis if isinstance(analysis, dict) else {}
    rows = _rows(analysis)
    required = _coverage_component(
        rows,
        accepted=_REQUIRED_CORE,
        key="required_core_coverage",
        name="Required/Core coverage",
    )
    preferred = _coverage_component(
        rows,
        accepted=_PREFERRED,
        key="preferred_coverage",
        name="Preferred coverage",
    )

    credited = [row for row in rows if _label(row) != "none"]
    evidence_values = [_strength(row) for row in credited]
    evidence_score = (
        round(100 * sum(evidence_values) / (5 * len(evidence_values)))
        if evidence_values
        else 0
    )

    if preferred["denominator"]:
        required_weight, preferred_weight = 0.80, 0.10
    else:
        required_weight, preferred_weight = 0.90, 0.0
    evidence_weight = 0.10

    components = [
        {
            "key": required["key"],
            "label": required["label"],
            "score": required["score"],
            "weight": required_weight,
            "weighted_points": required["score"] * required_weight,
            "numerator": required["numerator"],
            "denominator": required["denominator"],
        },
        {
            "key": preferred["key"],
            "label": preferred["label"],
            "score": preferred["score"],
            "weight": preferred_weight,
            "weighted_points": preferred["score"] * preferred_weight,
            "numerator": preferred["numerator"],
            "denominator": preferred["denominator"],
        },
        {
            "key": "evidence_strength",
            "label": "Evidence strength",
            "score": float(evidence_score),
            "weight": evidence_weight,
            "weighted_points": float(evidence_score) * evidence_weight,
            "numerator": float(sum(evidence_values)),
            "denominator": float(5 * len(evidence_values)),
        },
    ]
    unrounded_total = sum(float(row["weighted_points"]) for row in components)
    reconstructed = int(max(0, min(100, round(unrounded_total))))
    try:
        scorer_score = int(analysis.get("deterministic_alignment_score", 0) or 0)
    except (TypeError, ValueError):
        scorer_score = 0

    requirement_rows = [*required["requirements"], *preferred["requirements"]]
    by_id = {
        str(row.get("requirement_id") or ""): row
        for row in requirement_rows
        if str(row.get("requirement_id") or "")
    }
    component_weights = {
        "required_core_coverage": required_weight,
        "preferred_coverage": preferred_weight,
    }
    for row in requirement_rows:
        row["overall_coverage_points"] = round(
            float(row.get("component_coverage_points", 0.0))
            * component_weights.get(str(row.get("component") or ""), 0.0),
            6,
        )
        row["overall_evidence_points"] = 0.0

    if credited:
        # The production scorer rounds Evidence Strength before applying the
        # 10% overall weight. Allocate that already-rounded component total
        # proportionally so requirement contributions reconcile exactly.
        total_evidence_strength = sum(evidence_values)
        rounded_evidence_weighted_points = (
            float(evidence_score) * evidence_weight
        )
        for source in credited:
            target = by_id.get(_clean(source.get("requirement_id")))
            if target is not None:
                target["overall_evidence_points"] = round(
                    (
                        rounded_evidence_weighted_points
                        * _strength(source)
                        / total_evidence_strength
                    )
                    if total_evidence_strength
                    else 0.0,
                    6,
                )
    for row in requirement_rows:
        row["overall_point_contribution"] = round(
            float(row.get("overall_coverage_points", 0.0))
            + float(row.get("overall_evidence_points", 0.0)),
            6,
        )

    return {
        "explainability_version": PHASE8_SCORE_EXPLAINABILITY_VERSION,
        "scorer_score": scorer_score,
        "reconstructed_score": reconstructed,
        "score_parity": scorer_score == reconstructed,
        "unrounded_total": round(unrounded_total, 6),
        "components": components,
        "requirements": requirement_rows,
        "match_values": dict(MATCH_VALUES),
        "importance_weights": dict(IMPORTANCE_WEIGHTS),
        "formula": (
            "Required/Core coverage × required weight + Preferred coverage × "
            "preferred weight + Evidence strength × 10%"
        ),
    }



def _score_receipt_component_kind(row: dict[str, Any]) -> str:
    key = str(row.get("key") or "").strip().lower()
    label = str(row.get("label") or "").strip().lower()
    combined = f"{key} {label}"
    if "preferred" in combined:
        return "preferred"
    if "evidence" in combined:
        return "evidence"
    return "required_core"


def build_score_receipt(breakdown: dict[str, Any] | None) -> dict[str, Any]:
    # Presentation-only audit data derived from the existing score breakdown.
    # It does not rescore, reclassify, reconcile, or modify any requirement.
    breakdown = breakdown if isinstance(breakdown, dict) else {}

    component_rows: list[dict[str, Any]] = []
    component_weights: dict[str, float] = {}
    for row in breakdown.get("components", []) or []:
        if not isinstance(row, dict):
            continue
        kind = _score_receipt_component_kind(row)
        item = {
            "key": str(row.get("key") or ""),
            "kind": kind,
            "label": str(row.get("label") or row.get("key") or ""),
            "score": float(row.get("score", 0.0) or 0.0),
            "weight": float(row.get("weight", 0.0) or 0.0),
            "weighted_points": float(row.get("weighted_points", 0.0) or 0.0),
        }
        component_rows.append(item)
        component_weights[kind] = float(item["weight"])

    component_subtotal = sum(
        float(row.get("weighted_points", 0.0)) for row in component_rows
    )
    try:
        subtotal_before_rounding = float(
            breakdown.get("unrounded_total", component_subtotal) or 0.0
        )
    except (TypeError, ValueError):
        subtotal_before_rounding = component_subtotal

    try:
        final_score = int(
            breakdown.get(
                "reconstructed_score",
                max(0, min(100, round(subtotal_before_rounding))),
            )
            or 0
        )
    except (TypeError, ValueError):
        final_score = int(max(0, min(100, round(subtotal_before_rounding))))

    requirement_rows = [
        row
        for row in (breakdown.get("requirements", []) or [])
        if isinstance(row, dict)
    ]
    requirement_subtotal = sum(
        float(row.get("overall_point_contribution", 0.0) or 0.0)
        for row in requirement_rows
    )

    required_core_rows = [
        row
        for row in requirement_rows
        if str(row.get("importance") or "").strip().lower() != "preferred"
    ]
    preferred_rows = [
        row
        for row in requirement_rows
        if str(row.get("importance") or "").strip().lower() == "preferred"
    ]

    required_core_denominator = sum(
        float(row.get("effective_weight", 0.0) or 0.0)
        for row in required_core_rows
    )
    preferred_denominator = sum(
        float(row.get("effective_weight", 0.0) or 0.0)
        for row in preferred_rows
    )
    evidence_denominator = 5.0 * len(requirement_rows)

    required_core_max = 100.0 * component_weights.get("required_core", 0.0)
    preferred_max = 100.0 * component_weights.get("preferred", 0.0)
    evidence_max = 100.0 * component_weights.get("evidence", 0.0)
    maximum_score = required_core_max + preferred_max + evidence_max

    pool_rows: list[dict[str, Any]] = []
    if required_core_rows or required_core_max:
        pool_rows.append(
            {
                "kind": "required_core",
                "label": "Required/Core coverage",
                "requirement_count": len(required_core_rows),
                "denominator": required_core_denominator,
                "denominator_display": f"{required_core_denominator:.3f} raw weight",
                "weight": component_weights.get("required_core", 0.0),
                "max_final_points": required_core_max,
            }
        )
    if preferred_rows or preferred_max:
        pool_rows.append(
            {
                "kind": "preferred",
                "label": "Preferred coverage",
                "requirement_count": len(preferred_rows),
                "denominator": preferred_denominator,
                "denominator_display": f"{preferred_denominator:.3f} raw weight",
                "weight": component_weights.get("preferred", 0.0),
                "max_final_points": preferred_max,
            }
        )
    if requirement_rows or evidence_max:
        pool_rows.append(
            {
                "kind": "evidence",
                "label": "Evidence strength",
                "requirement_count": len(requirement_rows),
                "denominator": evidence_denominator,
                "denominator_display": (
                    f"5 × {len(requirement_rows)} = "
                    f"{evidence_denominator:.0f} evidence units"
                ),
                "weight": component_weights.get("evidence", 0.0),
                "max_final_points": evidence_max,
            }
        )

    evidence_share = (
        evidence_max / len(requirement_rows)
        if requirement_rows
        else 0.0
    )

    jd_requirement_rows: list[dict[str, Any]] = []
    for index, row in enumerate(requirement_rows, start=1):
        importance = str(row.get("importance") or "").strip().lower()
        pool_kind = "preferred" if importance == "preferred" else "required_core"
        effective_weight = float(row.get("effective_weight", 0.0) or 0.0)
        match_value = float(row.get("match_value", 0.0) or 0.0)

        if pool_kind == "preferred":
            pool_denominator = preferred_denominator
            pool_max_points = preferred_max
        else:
            pool_denominator = required_core_denominator
            pool_max_points = required_core_max

        coverage_max_points = (
            (effective_weight / pool_denominator) * pool_max_points
            if pool_denominator > 0.0
            else 0.0
        )
        max_final_points = coverage_max_points + evidence_share
        current_final_points = float(
            row.get("overall_point_contribution", 0.0) or 0.0
        )
        gap_to_max = max(0.0, max_final_points - current_final_points)

        jd_requirement_rows.append(
            {
                "index": index,
                "requirement_id": str(row.get("requirement_id") or ""),
                "requirement": str(row.get("requirement") or ""),
                "importance": importance,
                "pool_kind": pool_kind,
                "match_label": str(row.get("match_label") or "none"),
                "match_value": match_value,
                "importance_weight": float(
                    row.get("importance_weight", 0.0) or 0.0
                ),
                "effective_weight": effective_weight,
                "coverage_raw_earned": match_value * effective_weight,
                "coverage_raw_max": effective_weight,
                "coverage_max_final_points": coverage_max_points,
                "evidence_max_final_points": evidence_share,
                "max_final_points": max_final_points,
                "current_final_points": current_final_points,
                "gap_to_max": gap_to_max,
            }
        )

    jd_max_total = sum(
        float(row.get("max_final_points", 0.0))
        for row in jd_requirement_rows
    )

    return {
        "version": PHASE8_SCORE_RECEIPT_VERSION,
        "components": component_rows,
        "component_subtotal": component_subtotal,
        "subtotal_before_rounding": subtotal_before_rounding,
        "final_score": final_score,
        "stored_scorer_score": int(breakdown.get("scorer_score", 0) or 0),
        "score_parity": bool(breakdown.get("score_parity", False)),
        "requirement_subtotal": requirement_subtotal,
        "component_subtotal_parity": abs(
            component_subtotal - subtotal_before_rounding
        ) <= 1e-6,
        "requirement_subtotal_parity": abs(
            requirement_subtotal - subtotal_before_rounding
        ) <= 1e-4,
        "maximum_score": maximum_score,
        "maximum_score_parity": abs(maximum_score - 100.0) <= 1e-6,
        "pools": pool_rows,
        "jd_requirements": jd_requirement_rows,
        "jd_requirement_max_total": jd_max_total,
        "jd_requirement_max_total_parity": abs(
            jd_max_total - maximum_score
        ) <= 1e-4,
    }


def _raw_after_labels(
    result: dict[str, Any],
    before_rows: dict[str, dict[str, Any]],
) -> dict[str, str]:
    labels = {key: _label(row) for key, row in before_rows.items()}
    raw = result.get("raw_comparison_before_reconciliation", {}) or {}
    for bucket in ("improved_requirements", "regressed_requirements", "added_requirements"):
        for row in raw.get(bucket, []) or []:
            if not isinstance(row, dict):
                continue
            requirement_id = _clean(row.get("requirement_id"))
            after_label = _clean(row.get("after_label") or row.get("match_label")).lower()
            if requirement_id and after_label in MATCH_VALUES:
                labels[requirement_id] = after_label
    return labels


def build_requirement_change_rows(result: dict[str, Any] | None) -> list[dict[str, Any]]:
    result = result if isinstance(result, dict) else {}
    before = result.get("before_stable_analysis", {}) or {}
    after = result.get("after_stable_analysis", {}) or {}
    before_rows = {
        _clean(row.get("requirement_id")): row
        for row in _rows(before)
        if _clean(row.get("requirement_id"))
    }
    after_rows = {
        _clean(row.get("requirement_id")): row
        for row in _rows(after)
        if _clean(row.get("requirement_id"))
    }
    raw_labels = _raw_after_labels(result, before_rows)
    before_points = {
        str(row.get("requirement_id") or ""): row
        for row in build_score_breakdown(before).get("requirements", []) or []
    }
    after_points = {
        str(row.get("requirement_id") or ""): row
        for row in build_score_breakdown(after).get("requirements", []) or []
    }

    output: list[dict[str, Any]] = []
    ids = list(dict.fromkeys([*before_rows.keys(), *after_rows.keys()]))
    for requirement_id in ids:
        left = before_rows.get(requirement_id, {})
        right = after_rows.get(requirement_id, {})
        before_label = _label(left)
        final_label = _label(right)
        raw_label = raw_labels.get(requirement_id, before_label)
        before_rank = _MATCH_RANK.get(before_label, 0)
        final_rank = _MATCH_RANK.get(final_label, 0)
        if final_rank > before_rank:
            change, symbol = "improved", "↑"
        elif final_rank < before_rank:
            change, symbol = "regressed", "↓"
        else:
            change, symbol = "maintained", "="
        source = right or left
        left_points = float(
            (before_points.get(requirement_id) or {}).get("overall_point_contribution", 0.0)
        )
        right_points = float(
            (after_points.get(requirement_id) or {}).get("overall_point_contribution", 0.0)
        )
        output.append(
            {
                "requirement_id": requirement_id,
                "requirement": _clean(source.get("text") or source.get("atomic_focus")),
                "importance": _clean(source.get("importance")).lower(),
                "before": before_label,
                "raw_after": raw_label,
                "verified_after": final_label,
                "change": change,
                "change_symbol": symbol,
                "reconciliation_applied": raw_label != final_label,
                "before_overall_points": round(left_points, 3),
                "after_overall_points": round(right_points, 3),
                "overall_point_delta": round(right_points - left_points, 3),
                "evidence_after": _evidence(right),
            }
        )

    change_rank = {"regressed": 0, "improved": 1, "maintained": 2}
    importance_rank = {"deal_breaker": 0, "required": 1, "core": 2, "preferred": 3}
    output.sort(
        key=lambda row: (
            change_rank.get(str(row.get("change")), 9),
            importance_rank.get(str(row.get("importance")), 9),
            str(row.get("requirement") or "").lower(),
        )
    )
    return output


def build_phase8_explainability(result: dict[str, Any] | None) -> dict[str, Any]:
    result = result if isinstance(result, dict) else {}
    changes = build_requirement_change_rows(result)
    return {
        "explainability_version": PHASE8_SCORE_EXPLAINABILITY_VERSION,
        "before": build_score_breakdown(result.get("before_stable_analysis", {}) or {}),
        "after": build_score_breakdown(result.get("after_stable_analysis", {}) or {}),
        "requirement_changes": changes,
        "changed_requirements": [
            row
            for row in changes
            if row.get("change") != "maintained" or row.get("reconciliation_applied")
        ],
        "reconciled_requirements": [
            row for row in changes if row.get("reconciliation_applied")
        ],
    }

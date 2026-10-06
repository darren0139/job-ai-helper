"""Quality-gated deterministic Best Match ranking for Job Finder."""

from __future__ import annotations

from typing import Any

from analysis_stability.stable_evidence_scoring import IMPORTANCE_WEIGHTS


RANKING_VERSION = "job-match-ranking-v1"
MIN_ELIGIBLE_REQUIREMENTS = 3
MIN_IMPORTANT_TAXONOMY_COVERAGE = 0.75
MIN_OVERALL_TAXONOMY_COVERAGE = 0.65

IMPORTANT_IMPORTANCE = {"deal_breaker", "required", "core"}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def _weight(importance: Any) -> float:
    return float(
        IMPORTANCE_WEIGHTS.get(_clean(importance).lower(), 0.0)
    )


def build_ranking_quality(
    taxonomy_resolution: dict[str, Any] | None,
) -> dict[str, Any]:
    """Decide whether taxonomy understanding is sufficient for ranking."""
    resolution = (
        taxonomy_resolution
        if isinstance(taxonomy_resolution, dict)
        else {}
    )
    rows = [
        row
        for row in resolution.get("rows", []) or []
        if isinstance(row, dict)
    ]

    total_weight = 0.0
    resolved_weight = 0.0
    important_weight = 0.0
    resolved_important_weight = 0.0
    resolved_count = 0
    important_count = 0
    resolved_important_count = 0

    for row in rows:
        importance = _clean(row.get("importance")).lower()
        weight = _weight(importance)
        resolved = _clean(row.get("status")).lower() == "resolved"

        total_weight += weight
        if resolved:
            resolved_weight += weight
            resolved_count += 1

        if importance in IMPORTANT_IMPORTANCE:
            important_count += 1
            important_weight += weight
            if resolved:
                resolved_important_count += 1
                resolved_important_weight += weight

    eligible_count = len(rows)
    unresolved_count = eligible_count - resolved_count
    unresolved_important_count = important_count - resolved_important_count

    overall_coverage = (
        resolved_weight / total_weight if total_weight > 0 else 0.0
    )
    important_coverage = (
        resolved_important_weight / important_weight
        if important_weight > 0
        else (1.0 if eligible_count > 0 else 0.0)
    )

    reasons: list[str] = []
    if eligible_count == 0:
        reasons.append("no_score_eligible_requirements")
    elif eligible_count < MIN_ELIGIBLE_REQUIREMENTS:
        reasons.append("too_few_score_eligible_requirements")

    if eligible_count > 0 and overall_coverage < MIN_OVERALL_TAXONOMY_COVERAGE:
        reasons.append("insufficient_overall_taxonomy_coverage")

    if (
        important_weight > 0
        and important_coverage < MIN_IMPORTANT_TAXONOMY_COVERAGE
    ):
        reasons.append("insufficient_important_taxonomy_coverage")

    ranking_eligible = not reasons
    if ranking_eligible:
        status = "eligible"
    elif "no_score_eligible_requirements" in reasons:
        status = "no_score_eligible_requirements"
    elif "too_few_score_eligible_requirements" in reasons:
        status = "insufficient_requirement_count"
    else:
        status = "insufficient_taxonomy_coverage"

    return {
        "ranking_version": RANKING_VERSION,
        "ranking_eligible": ranking_eligible,
        "ranking_status": status,
        "ranking_ineligible_reasons": reasons,
        "eligible_requirement_count": eligible_count,
        "resolved_requirement_count": resolved_count,
        "taxonomy_gap_count": unresolved_count,
        "important_requirement_count": important_count,
        "resolved_important_requirement_count": resolved_important_count,
        "important_taxonomy_gap_count": unresolved_important_count,
        "overall_taxonomy_coverage": round(overall_coverage, 6),
        "important_taxonomy_coverage": round(important_coverage, 6),
        "overall_taxonomy_coverage_pct": round(overall_coverage * 100),
        "important_taxonomy_coverage_pct": round(important_coverage * 100),
        "minimum_overall_taxonomy_coverage": (
            MIN_OVERALL_TAXONOMY_COVERAGE
        ),
        "minimum_important_taxonomy_coverage": (
            MIN_IMPORTANT_TAXONOMY_COVERAGE
        ),
        "minimum_eligible_requirements": MIN_ELIGIBLE_REQUIREMENTS,
    }


def best_match_sort_key(
    snapshot: dict[str, Any] | None,
    *,
    search_relevance: float = 0.0,
    freshness_timestamp: float = 0.0,
    discovered_job_id: int = 0,
) -> tuple[Any, ...]:
    """Build a deterministic descending Best Match sort key."""
    summary = (
        snapshot.get("summary")
        if isinstance(snapshot, dict)
        and isinstance(snapshot.get("summary"), dict)
        else {}
    )
    analyzed = bool(summary)
    eligible = bool(summary.get("ranking_eligible"))

    if eligible:
        bucket = 2
        alignment = int(
            summary.get("deterministic_alignment_score", 0) or 0
        )
        required_core = int(
            summary.get("required_core_coverage_score", 0) or 0
        )
        important_gaps = int(
            summary.get("important_gap_count", 0) or 0
        )
        direct_count = int(
            summary.get("direct_requirement_count", 0) or 0
        )
        preferred = int(
            summary.get("preferred_coverage_score", 0) or 0
        )
        evidence_strength = int(
            summary.get("evidence_strength_score", 0) or 0
        )
        taxonomy_quality = int(
            summary.get("important_taxonomy_coverage_pct", 0) or 0
        )
    elif analyzed:
        bucket = 1
        alignment = -1
        required_core = -1
        important_gaps = 10**9
        direct_count = -1
        preferred = -1
        evidence_strength = -1
        taxonomy_quality = int(
            summary.get("important_taxonomy_coverage_pct", 0) or 0
        )
    else:
        bucket = 0
        alignment = -1
        required_core = -1
        important_gaps = 10**9
        direct_count = -1
        preferred = -1
        evidence_strength = -1
        taxonomy_quality = -1

    return (
        bucket,
        alignment,
        required_core,
        -important_gaps,
        direct_count,
        preferred,
        evidence_strength,
        taxonomy_quality,
        float(search_relevance or 0.0),
        float(freshness_timestamp or 0.0),
        -int(discovered_job_id or 0),
    )

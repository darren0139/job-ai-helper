"""
deterministic_project_rules.py

Generic warning-only consistency validator for Job AI Helper project scoring.

This is a drop-in replacement for the earlier deterministic rules module.

What it does:
- Keeps the existing public function name:
      apply_deterministic_evidence_floors(...)
- Clamps component scores to the allowed 0-5 range.
- Removes exact duplicate requirement labels.
- Removes an exact requirement from the transferable list when the same
  requirement already exists in the direct-match list.
- Records warnings when the LLM output is internally inconsistent.
- Does not add semantic matches.
- Does not raise relevance scores because of a matched-requirement label.
- Does not contain gaming, QA, cloud, RLS, DevOps, networking, or other
  domain-specific keyword rules.
- Does not cache LLM responses.

The caller should continue recalculating relevance_score and final_score after
this function returns because duplicate removal and score clamping may affect
the deterministic ranking.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def _normalise_text(value: Any) -> str:
    """Return lowercase alphanumeric text with collapsed whitespace."""
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9+#./-]+", " ", text)
    return " ".join(text.split())


def _safe_score(value: Any) -> int:
    """Convert a value to an integer score clamped from 0 to 5."""
    try:
        numeric = int(round(float(value)))
    except (TypeError, ValueError):
        numeric = 0

    return max(0, min(5, numeric))


def _deduplicate_requirements(
    values: Any,
) -> tuple[list[str], list[dict[str, str]]]:
    """
    Remove exact normalised duplicate requirement labels.

    This intentionally avoids fuzzy semantic merging. Two differently worded
    requirements are kept unless their normalised text is exactly the same.
    """
    if not isinstance(values, list):
        return [], []

    cleaned: list[str] = []
    seen: dict[str, str] = {}
    removals: list[dict[str, str]] = []

    for raw_value in values:
        value = " ".join(
            str(raw_value or "").split()
        ).strip()

        if not value:
            continue

        key = _normalise_text(value)

        if key in seen:
            removals.append(
                {
                    "removed": value,
                    "kept": seen[key],
                }
            )
            continue

        seen[key] = value
        cleaned.append(value)

    return cleaned, removals


def _remove_exact_direct_transferable_overlap(
    direct_requirements: list[str],
    transferable_requirements: list[str],
) -> tuple[list[str], list[dict[str, str]]]:
    """
    Remove an exact transferable duplicate when the same requirement is
    already listed as a direct match. Direct evidence takes precedence.
    """
    direct_by_key = {
        _normalise_text(value): value
        for value in direct_requirements
    }

    kept_transferable: list[str] = []
    removals: list[dict[str, str]] = []

    for value in transferable_requirements:
        key = _normalise_text(value)

        if key in direct_by_key:
            removals.append(
                {
                    "removed": value,
                    "kept_as_direct": direct_by_key[key],
                }
            )
            continue

        kept_transferable.append(value)

    return kept_transferable, removals


# ---------------------------------------------------------------------------
# Public compatibility function
# ---------------------------------------------------------------------------

def apply_deterministic_evidence_floors(
    *,
    ranked_rows: list[dict[str, Any]],
    project_candidates: list[dict[str, Any]],
    jd_profile: dict[str, Any],
    raw_jd_text: str = "",
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    """
    Apply generic, warning-only consistency validation.

    The project_candidates, jd_profile, and raw_jd_text arguments are retained
    for drop-in compatibility with the earlier implementation. This version
    does not perform domain-specific semantic matching.

    Returns:
        updated_rows:
            Deep-copied rows after safe structural cleanup.

        debug_rows:
            Records of score clamping, duplicate cleanup, and warnings.

    Important:
        This function never raises a relevance component from zero merely
        because the LLM listed a direct or transferable requirement.
    """
    del project_candidates
    del jd_profile
    del raw_jd_text

    updated_rows = deepcopy(ranked_rows)
    debug_rows: list[dict[str, Any]] = []

    for row in updated_rows:
        project_title = (
            row.get("display_title")
            or row.get("title")
            or "Untitled Project"
        )

        # ---------------------------------------------------------------
        # 1. Clamp component scores to the documented 0-5 range.
        # ---------------------------------------------------------------
        score_fields = (
            "must_have_match_score",
            "responsibility_match_score",
            "tool_domain_match_score",
            "evidence_strength_score",
            "impact_scope_score",
        )

        for field in score_fields:
            original_value = row.get(field, 0)
            corrected_value = _safe_score(original_value)
            row[field] = corrected_value

            try:
                original_numeric = int(
                    round(float(original_value))
                )
            except (TypeError, ValueError):
                original_numeric = None

            if original_numeric != corrected_value:
                debug_rows.append(
                    {
                        "project": project_title,
                        "action": "clamp_score",
                        "field": field,
                        "before": original_value,
                        "after": corrected_value,
                    }
                )

        # ---------------------------------------------------------------
        # 2. Remove exact duplicate requirement labels.
        # ---------------------------------------------------------------
        direct_requirements, direct_removals = (
            _deduplicate_requirements(
                row.get(
                    "matched_jd_requirements",
                    [],
                )
            )
        )

        (
            transferable_requirements,
            transferable_removals,
        ) = _deduplicate_requirements(
            row.get(
                "transferable_jd_requirements",
                [],
            )
        )

        for removal in direct_removals:
            debug_rows.append(
                {
                    "project": project_title,
                    "action": (
                        "remove_duplicate_direct_requirement"
                    ),
                    **removal,
                }
            )

        for removal in transferable_removals:
            debug_rows.append(
                {
                    "project": project_title,
                    "action": (
                        "remove_duplicate_transferable_requirement"
                    ),
                    **removal,
                }
            )

        (
            transferable_requirements,
            overlap_removals,
        ) = _remove_exact_direct_transferable_overlap(
            direct_requirements,
            transferable_requirements,
        )

        for removal in overlap_removals:
            debug_rows.append(
                {
                    "project": project_title,
                    "action": (
                        "remove_direct_transferable_overlap"
                    ),
                    **removal,
                }
            )

        row[
            "matched_jd_requirements"
        ] = direct_requirements
        row[
            "transferable_jd_requirements"
        ] = transferable_requirements

        # ---------------------------------------------------------------
        # 3. Report contradictions without changing relevance scores.
        # ---------------------------------------------------------------
        must_have = row[
            "must_have_match_score"
        ]
        responsibility = row[
            "responsibility_match_score"
        ]
        tool_domain = row[
            "tool_domain_match_score"
        ]

        if (
            direct_requirements
            and max(
                must_have,
                responsibility,
                tool_domain,
            )
            == 0
        ):
            debug_rows.append(
                {
                    "project": project_title,
                    "action": (
                        "warning_direct_match_zero_score_contradiction"
                    ),
                    "reason": (
                        "The model listed at least one direct JD "
                        "requirement, but all relevance component "
                        "scores were zero. No score was changed."
                    ),
                    "matched_requirements": direct_requirements,
                }
            )

        if (
            transferable_requirements
            and responsibility == 0
            and tool_domain == 0
        ):
            debug_rows.append(
                {
                    "project": project_title,
                    "action": (
                        "warning_transferable_match_zero_score_contradiction"
                    ),
                    "reason": (
                        "The model listed transferable JD requirements, "
                        "but both responsibility and tool/domain scores "
                        "were zero. No score was changed."
                    ),
                    "transferable_requirements": (
                        transferable_requirements
                    ),
                }
            )

        if (
            not direct_requirements
            and not transferable_requirements
            and max(
                must_have,
                responsibility,
                tool_domain,
            )
            > 0
        ):
            debug_rows.append(
                {
                    "project": project_title,
                    "action": (
                        "warning_nonzero_relevance_without_requirement_labels"
                    ),
                    "reason": (
                        "The model assigned a non-zero relevance score "
                        "but did not list any direct or transferable "
                        "requirement labels. No score was changed."
                    ),
                }
            )

    return updated_rows, debug_rows

"""
Deterministic Skills-section compaction for whole-resume fitting.

This module never invents or rewrites skill names. It removes one supported,
lowest-value skill at a time, while preserving at least one item per category
and a configurable minimum number of total skills. The DOCX fitter renders the
result after each change and may later restore a removed skill when space allows.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalise_key(value: Any) -> str:
    return "".join(
        character.lower()
        for character in _clean_text(value)
        if character.isalnum()
    )


def _safe_score(value: Any, minimum: int = 0, maximum: int = 5) -> int:
    try:
        numeric = int(round(float(value)))
    except (TypeError, ValueError):
        numeric = minimum
    return max(minimum, min(maximum, numeric))


def _priority_map(skills_result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    priorities: dict[str, dict[str, Any]] = {}

    for raw_row in skills_result.get("skill_priorities", []) or []:
        if not isinstance(raw_row, dict):
            continue

        skill = _clean_text(raw_row.get("skill"))
        key = _normalise_key(skill)
        if not key or key in priorities:
            continue

        priorities[key] = {
            "skill": skill,
            "jd_relevance": _safe_score(raw_row.get("jd_relevance")),
            "evidence_strength": _safe_score(raw_row.get("evidence_strength")),
            "required_match": bool(raw_row.get("required_match")),
            "preferred_match": bool(raw_row.get("preferred_match")),
            "reason": _clean_text(raw_row.get("reason")),
        }

    return priorities


def skill_priority_score(
    skill: str,
    skills_result: dict[str, Any],
) -> int:
    """
    Return a deterministic value score for retaining a skill.

    Larger values mean the skill is more valuable and should be removed later.
    """
    priority = _priority_map(skills_result).get(
        _normalise_key(skill),
        {},
    )

    jd_relevance = _safe_score(priority.get("jd_relevance", 1))
    evidence_strength = _safe_score(priority.get("evidence_strength", 2))
    required_match = bool(priority.get("required_match"))
    preferred_match = bool(priority.get("preferred_match"))

    return (
        jd_relevance * 100
        + evidence_strength * 20
        + (400 if required_match else 0)
        + (120 if preferred_match else 0)
    )


def count_skill_items(skills_result: dict[str, Any] | None) -> int:
    if not isinstance(skills_result, dict):
        return 0

    return sum(
        len(
            [
                item
                for item in row.get("items", []) or []
                if _clean_text(item)
            ]
        )
        for row in skills_result.get("skill_lines", []) or []
        if isinstance(row, dict)
    )


def compact_skills_one_step(
    tailored_skills: dict[str, Any],
    *,
    minimum_items_per_category: int = 1,
    minimum_total_items: int = 8,
) -> tuple[dict[str, Any], bool, dict[str, Any]]:
    """Remove one lowest-value skill without rewriting any skill name."""
    compacted = deepcopy(tailored_skills)
    skill_lines = compacted.get("skill_lines", []) or []
    total_items = count_skill_items(compacted)

    if total_items <= minimum_total_items:
        return (
            compacted,
            False,
            {
                "section": "skills",
                "change_type": "none",
                "reason": "The Skills section is already at its minimum total item count.",
            },
        )

    candidates: list[dict[str, Any]] = []

    for category_index, row in enumerate(skill_lines):
        if not isinstance(row, dict):
            continue

        category = _clean_text(row.get("category")) or "Skills"
        items = [
            _clean_text(item)
            for item in row.get("items", []) or []
            if _clean_text(item)
        ]

        if len(items) <= minimum_items_per_category:
            continue

        for item_index, skill in enumerate(items):
            value_score = skill_priority_score(skill, compacted)
            candidates.append(
                {
                    "category_index": category_index,
                    "category": category,
                    "item_index": item_index,
                    "skill": skill,
                    "skill_priority_score": value_score,
                    "category_item_count": len(items),
                }
            )

    if not candidates:
        return (
            compacted,
            False,
            {
                "section": "skills",
                "change_type": "none",
                "reason": "No removable Skills item remains without emptying a category.",
            },
        )

    target = min(
        candidates,
        key=lambda row: (
            int(row["skill_priority_score"]),
            -int(row["category_item_count"]),
            -len(str(row["skill"]).split()),
            str(row["category"]).lower(),
            str(row["skill"]).lower(),
        ),
    )

    target_row = skill_lines[int(target["category_index"])]
    target_items = [
        _clean_text(item)
        for item in target_row.get("items", []) or []
        if _clean_text(item)
    ]

    removed_skill = target_items.pop(int(target["item_index"]))
    target_row["items"] = target_items

    change = {
        "section": "skills",
        "change_type": "remove_skill",
        "category": target["category"],
        "category_index": target["category_index"],
        "removed_skill": removed_skill,
        "removed_skill_index": target["item_index"],
        "skill_priority_score": target["skill_priority_score"],
        "category_item_count_before": target["category_item_count"],
    }

    compacted.setdefault("skills_fitting_changes", []).append(deepcopy(change))
    compacted.setdefault("notes", []).append(
        f"Removed lower-priority skill '{removed_skill}' from {target['category']} during one-page fitting."
    )

    return compacted, True, change


def count_skill_reduction_candidates(
    tailored_skills: dict[str, Any] | None,
    *,
    minimum_items_per_category: int = 1,
    minimum_total_items: int = 8,
) -> int:
    """Simulate deterministic removals to calculate a bounded retry limit."""
    if not isinstance(tailored_skills, dict):
        return 0

    working = deepcopy(tailored_skills)
    count = 0

    while True:
        working, changed, _ = compact_skills_one_step(
            working,
            minimum_items_per_category=minimum_items_per_category,
            minimum_total_items=minimum_total_items,
        )
        if not changed:
            return count
        count += 1


def restore_skill_change(
    tailored_skills: dict[str, Any],
    change: dict[str, Any],
) -> tuple[dict[str, Any], bool, dict[str, Any]]:
    """Restore one previously removed skill to its original category and position."""
    restored = deepcopy(tailored_skills)

    if str(change.get("change_type", "")) != "remove_skill":
        return restored, False, {
            "section": "skills",
            "change_type": "restore_unavailable",
            "reason": "Unsupported Skills fitting change.",
        }

    category = _clean_text(change.get("category"))
    removed_skill = _clean_text(change.get("removed_skill"))

    if not category or not removed_skill:
        return restored, False, {
            "section": "skills",
            "change_type": "restore_unavailable",
            "reason": "The removed Skills item is unavailable.",
        }

    rows = restored.get("skill_lines", []) or []
    target_row = next(
        (
            row
            for row in rows
            if isinstance(row, dict)
            and _clean_text(row.get("category")) == category
        ),
        None,
    )

    if target_row is None:
        return restored, False, {
            "section": "skills",
            "change_type": "restore_unavailable",
            "reason": "The original Skills category is unavailable.",
        }

    items = [
        _clean_text(item)
        for item in target_row.get("items", []) or []
        if _clean_text(item)
    ]

    if _normalise_key(removed_skill) in {_normalise_key(item) for item in items}:
        return restored, False, {
            "section": "skills",
            "change_type": "restore_unavailable",
            "reason": "The skill is already present.",
        }

    insert_index = int(change.get("removed_skill_index", len(items)) or 0)
    insert_index = max(0, min(insert_index, len(items)))
    items.insert(insert_index, removed_skill)
    target_row["items"] = items

    restore_info = {
        "section": "skills",
        "change_type": "restore_removed_skill",
        "restored_change_type": "remove_skill",
        "category": category,
        "restored_skill": removed_skill,
    }

    restored.setdefault("notes", []).append(
        f"Restored skill '{removed_skill}' after confirming the resume still fits on one page."
    )

    return restored, True, restore_info


def skill_restoration_quality_gain(change: dict[str, Any]) -> int:
    """Return the value recovered by restoring a removed skill."""
    return int(change.get("skill_priority_score", 0) or 0) * 10 + len(
        _clean_text(change.get("removed_skill")).split()
    )

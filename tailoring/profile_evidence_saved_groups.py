"""UI-only ordering of saved Profile & Evidence records.

This module does not update, filter, or reclassify stored evidence. The caller's
existing date/recent-edit sort is preserved *within* each displayed group.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

GROUP_ORDER = ("work", "project", "skill", "other")
GROUP_HEADINGS = {
    "work": "💼 Saved Work Experience",
    "project": "📁 Saved Projects",
    "skill": "🧩 Saved Skills",
    "other": "📚 Other Saved Evidence",
}


def saved_evidence_group(item: Mapping[str, Any]) -> str:
    """Map existing evidence categories to display-only sections."""
    category = str(item.get("category") or "").strip().casefold()
    if category in {"work experience", "internship"}:
        return "work"
    if category == "project":
        return "project"
    if category == "skill":
        return "skill"
    return "other"


def ordered_saved_evidence_items(items: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Stable group sort: never drop, merge, rewrite, or deduplicate records."""
    order = {group: index for index, group in enumerate(GROUP_ORDER)}
    return sorted(items, key=lambda item: order[saved_evidence_group(item)])


def saved_evidence_group_heading(group: str) -> str:
    return GROUP_HEADINGS[group]


def saved_evidence_item_label(item: Mapping[str, Any]) -> str:
    """Use 'Role — Employer' for work rows; retain all other display titles."""
    title = str(item.get("title") or "").strip()
    employer = str(item.get("subtitle") or "").strip()
    if saved_evidence_group(item) == "work" and employer:
        return f"{title} — {employer}" if title else employer
    return title

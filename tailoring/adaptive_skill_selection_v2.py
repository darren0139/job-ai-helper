"""Deterministic fit-time skill selection from an already saved, evidence-backed ranking.

Never creates skills, modifies evidence, invokes a provider or awards Job Match credit.
A new selection is a derived fit input, not an edit of the frozen initial résumé.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Any

POLICY_VERSION = "adaptive-skill-fit-selection-v2"
MODES = ("legacy", "balanced", "preserve_supported", "jd_focused", "manual")
MAX_SUPPORTED = 100


def _key(value: Any) -> str:
    # Preserve meaningful language symbols: C, C++, C#, and F# are distinct.
    # Other punctuation/spacing remains normalized as in Adaptive Skills V2.
    return "".join(
        c.casefold() for c in str(value or "")
        if c.isalnum() or c in "+#"
    )


def _ranking(skills: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(skills, dict):
        return []
    ranked = skills.get("deterministic_skill_ranking")
    if not isinstance(ranked, list):
        return []
    result, seen = [], set()
    for row in ranked:
        if not isinstance(row, dict):
            raise ValueError("Malformed saved deterministic skill ranking")
        skill = str(row.get("skill") or "").strip()
        key = _key(row.get("skill_key") or skill)
        if not key or not skill or not isinstance(row.get("category"), str):
            raise ValueError("Incomplete saved deterministic skill candidate")
        if key in seen:
            raise ValueError("Duplicate skill identity in saved deterministic ranking")
        seen.add(key)
        result.append(row)
    return result


def supported_skill_options(skills: dict[str, Any]) -> list[dict[str, str]]:
    """Return ONLY candidate skills previously admitted by deterministic provenance."""
    return [
        {"key": _key(row.get("skill_key") or row["skill"]),
         "label": str(row["skill"]),
         "category": str(row["category"])}
        for row in _ranking(skills)
    ]


def normalise_adaptive_fit_settings(
    mode: Any, selected_keys: Any = None,
) -> tuple[str, list[str]]:
    mode = str(mode or "").strip().lower()
    if mode not in MODES:
        raise ValueError("Unsupported adaptive Skills selection mode")
    if selected_keys is None:
        selected_keys = []
    if not isinstance(selected_keys, (list, tuple)):
        raise ValueError("Manual Skills selection must be a list")
    result, seen = [], set()
    for value in selected_keys:
        if not isinstance(value, str):
            raise ValueError("Skill identity must be a string")
        key = _key(value)
        if not key or key in seen:
            raise ValueError("Empty or duplicate manual Skill identity")
        seen.add(key)
        result.append(key)
    if len(result) > MAX_SUPPORTED:
        raise ValueError("Too many manually selected skills")
    if mode == "manual" and not result:
        raise ValueError("Select at least one supported Skill in Manual mode")
    if mode != "manual" and result:
        raise ValueError("Manual Skill identities are only allowed in Manual mode")
    return mode, result


def _selected_rows(ranking: list[dict[str, Any]], mode: str, keys: list[str]) -> list[dict[str, Any]]:
    primary = [r for r in ranking if r.get("required_match") or r.get("preferred_match") or r.get("selected_project_support")]
    rest = [r for r in ranking if r not in primary]
    ordered = primary + rest  # mirror canonical deterministic Skills selection priority
    if mode == "balanced":
        return ordered[:min(30, MAX_SUPPORTED)]
    if mode == "preserve_supported":
        if len(ordered) > MAX_SUPPORTED:
            raise ValueError("Supported skill pool exceeds the 100-item safety bound")
        return ordered
    if mode == "jd_focused":
        matched = [r for r in ranking if r.get("required_match") or r.get("preferred_match")]
        return (matched if matched else ordered[:min(8, len(ordered))])[:20]
    if mode == "manual":
        offered = {_key(r.get("skill_key") or r["skill"]): r for r in ranking}
        unexpected = sorted(set(keys) - offered.keys())
        if unexpected:
            raise ValueError("Manual selection includes skills not in the saved supported pool")
        chosen = set(keys)
        return [r for r in ranking if _key(r.get("skill_key") or r["skill"]) in chosen]
    return []


def apply_adaptive_skill_selection(
    skills: dict[str, Any] | None,
    *,
    mode: str = "legacy",
    selected_keys: list[str] | None = None,
) -> dict[str, Any] | None:
    """Copy-and-reselect saved deterministic candidates; no inference or scorer work.

    The original ranked pool is retained in the result for later fitting revisions.
    """
    mode, keys = normalise_adaptive_fit_settings(mode, selected_keys)
    if mode == "legacy" or not skills:
        return deepcopy(skills)
    ranked = _ranking(skills)
    if not ranked:
        raise ValueError("No saved deterministic ranking; generate Skills before Adaptive fit")
    chosen = _selected_rows(ranked, mode, keys)
    if not chosen:
        raise ValueError("Adaptive Skills mode selected no supported skills")
    out = deepcopy(skills)
    selected_keys_set = {_key(r.get("skill_key") or r["skill"]) for r in chosen}
    original_categories = [
        str(x.get("category")) for x in out.get("skill_lines", [])
        if isinstance(x, dict) and x.get("category")
    ]
    by_category: dict[str, list[str]] = defaultdict(list)
    for row in chosen:
        by_category[str(row["category"])].append(str(row["skill"]))
    category_order = dict.fromkeys([*original_categories, *sorted(by_category)])
    out["skill_lines"] = [
        {"category": category, "items": by_category[category]}
        for category in category_order if by_category.get(category)
    ]
    out["skill_priorities"] = deepcopy(chosen)
    out["adaptive_fit_selection"] = {
        "policy_version": POLICY_VERSION,
        "mode": mode,
        "selected_count": len(chosen),
        "supported_pool_count": len(ranked),
        "selected_skill_keys": [
            _key(r.get("skill_key") or r["skill"]) for r in chosen
        ],
        "not_selected_skill_keys": [
            _key(r.get("skill_key") or r["skill"]) for r in ranked
            if _key(r.get("skill_key") or r["skill"]) not in selected_keys_set
        ],
        "source": "saved_deterministic_skill_ranking",
        "scorer_modified": False,
    }
    return out

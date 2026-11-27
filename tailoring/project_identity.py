"""
Stable project identity helpers for Skills support.

Older writer output may shorten ``title`` while preserving a canonical
``display_title`` and stable ``project_id``. These helpers prevent cosmetic
title changes from changing which Evidence Library skills receive
selected-project support.
"""

from __future__ import annotations

from collections import Counter
import re
from typing import Any


PROJECT_IDENTITY_VERSION = "phase6b2.1-stable-project-identity-v1"


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalise_title_key(value: Any) -> str:
    text = _clean_text(value).lower()
    text = text.replace("row-level", "row level")
    text = text.replace("cross-functional", "cross functional")
    text = re.sub(r"[^a-z0-9+#.]+", " ", text)
    return " ".join(text.split())


def _base_title_key(value: Any) -> str:
    """
    Return a conservative base-project key.

    Only trailing parenthetical or square-bracket metadata is removed. This
    maps ``QueryAI`` and ``QueryAI (React, Team of 4)`` to the same fallback
    key without deleting meaningful words from the project name.
    """
    original = _clean_text(value)
    text = original

    while text:
        updated = re.sub(
            r"\s*(?:\([^()]*\)|\[[^\[\]]*\])\s*$",
            "",
            text,
        ).strip()
        if updated == text:
            break
        text = updated

    return _normalise_title_key(text or original)


def build_selected_project_identity_index(
    *,
    selected_projects: list[dict[str, Any]],
    evidence_items: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Build a deterministic project-identity index.

    Match priority:
    1. stable project_id;
    2. exact canonical title, preferring display_title;
    3. unique base title after removing trailing metadata.
    """
    selected_records: list[dict[str, str]] = []

    for project in selected_projects:
        if not isinstance(project, dict):
            continue

        writer_title = _clean_text(project.get("title"))
        display_title = _clean_text(project.get("display_title"))
        canonical_title = display_title or writer_title

        selected_records.append(
            {
                "project_id": _clean_text(project.get("project_id")),
                "writer_title": writer_title,
                "display_title": display_title,
                "canonical_title": canonical_title,
                "exact_title_key": _normalise_title_key(canonical_title),
                "base_title_key": _base_title_key(canonical_title),
            }
        )

    evidence_records: list[dict[str, str]] = []
    for item in evidence_items:
        if not isinstance(item, dict):
            continue

        title = _clean_text(item.get("title"))
        evidence_records.append(
            {
                "project_id": _clean_text(item.get("project_id")),
                "title": title,
                "exact_title_key": _normalise_title_key(title),
                "base_title_key": _base_title_key(title),
            }
        )

    selected_base_counts = Counter(
        record["base_title_key"]
        for record in selected_records
        if record["base_title_key"]
    )
    evidence_base_counts = Counter(
        record["base_title_key"]
        for record in evidence_records
        if record["base_title_key"]
    )

    return {
        "version": PROJECT_IDENTITY_VERSION,
        "_selected_identity_rows": [dict(r) for r in selected_projects if isinstance(r, dict)],
        "_evidence_identity_rows": [dict(r) for r in evidence_items if isinstance(r, dict)],
        "selected_project_ids": {
            record["project_id"]
            for record in selected_records
            if record["project_id"]
        },
        "selected_exact_title_keys": {
            record["exact_title_key"]
            for record in selected_records
            if record["exact_title_key"]
        },
        "selected_base_title_keys": {
            record["base_title_key"]
            for record in selected_records
            if record["base_title_key"]
        },
        "selected_base_counts": dict(selected_base_counts),
        "evidence_base_counts": dict(evidence_base_counts),
        "debug": {
            "version": PROJECT_IDENTITY_VERSION,
            "selected_projects": selected_records,
            "evidence_projects": evidence_records,
        },
    }


def match_evidence_project_to_selected(
    item: dict[str, Any], identity_index: dict[str, Any],
) -> tuple[bool, str]:
    """Resolve selected project support without mixing distinct title variants."""
    from tailoring.project_title_resolution_v1 import resolve_project, full_title, title_key
    selected = identity_index.get('_selected_identity_rows') or []
    evidence = identity_index.get('_evidence_identity_rows') or []
    row, method = resolve_project(item, selected)
    if row is None:
        return False, ''
    # The entire evidence scope must agree with the same selection. The item
    # may be a different dict instance from the original index, so compare
    # full title and ID, not object identity across the caller boundary.
    reverse, _ = resolve_project(row, evidence)
    if reverse is None or (title_key(full_title(reverse)) != title_key(full_title(item))
            or _clean_text(reverse.get('project_id')) != _clean_text(item.get('project_id'))):
        return False, ''
    return True, {'project_id': 'project_id', 'exact_title': 'exact_display_title',
                  'unique_subtitle_alias': 'unique_base_title'}[method]

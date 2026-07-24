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
    item: dict[str, Any],
    identity_index: dict[str, Any],
) -> tuple[bool, str]:
    """Return whether an Evidence Library item belongs to a selected project."""
    item_id = _clean_text(item.get("project_id"))
    if (
        item_id
        and item_id in identity_index.get("selected_project_ids", set())
    ):
        return True, "project_id"

    title = _clean_text(item.get("title"))
    exact_key = _normalise_title_key(title)
    if (
        exact_key
        and exact_key
        in identity_index.get("selected_exact_title_keys", set())
    ):
        return True, "exact_display_title"

    base_key = _base_title_key(title)
    selected_base_counts = identity_index.get("selected_base_counts", {}) or {}
    evidence_base_counts = identity_index.get("evidence_base_counts", {}) or {}

    if (
        base_key
        and base_key
        in identity_index.get("selected_base_title_keys", set())
        and int(selected_base_counts.get(base_key, 0)) == 1
        and int(evidence_base_counts.get(base_key, 0)) == 1
    ):
        return True, "unique_base_title"

    return False, ""

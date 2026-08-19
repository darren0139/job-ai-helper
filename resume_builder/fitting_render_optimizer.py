"""
Exact-safe Phase 6C.1 rendering helpers.

These helpers reduce expensive LibreOffice work without changing the Phase 6C
evidence-protection decision rule:

1. Compare every candidate inside the current protection tier.
2. Stop before higher tiers only after the current tier has at least one
   measurable layout improvement.
3. Reuse identical rendered states within the same fitting run.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


PHASE6C1_OPTIMIZATION_VERSION = "phase6c1-exact-safe-render-v2-format-metadata"


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def candidate_protection_tier(candidate: dict[str, Any]) -> int:
    change = candidate.get("change", {}) or {}
    try:
        value = int(change.get("protection_tier", 0) or 0)
    except (TypeError, ValueError):
        value = 0
    return max(0, value)


def group_candidates_by_protection_tier(
    candidates: list[dict[str, Any]],
) -> list[tuple[int, list[dict[str, Any]]]]:
    """
    Group candidates by ascending protection tier while preserving deterministic
    candidate order inside each tier.
    """
    grouped: dict[int, list[dict[str, Any]]] = {}

    for candidate in candidates:
        tier = candidate_protection_tier(candidate)
        grouped.setdefault(tier, []).append(candidate)

    result: list[tuple[int, list[dict[str, Any]]]] = []
    for tier in sorted(grouped):
        ordered = sorted(
            grouped[tier],
            key=lambda candidate: int(
                candidate.get("candidate_order", 99) or 99
            ),
        )
        result.append((tier, ordered))

    return result


def rendered_candidate_is_effective(
    candidate: dict[str, Any],
    *,
    layout_effect_threshold: float,
) -> bool:
    return bool(candidate.get("reaches_one_page")) or float(
        candidate.get("space_saved_ratio", 0.0) or 0.0
    ) >= float(layout_effect_threshold)


def source_docx_signature(path: str | Path) -> str:
    """Hash the source DOCX so a cache entry cannot cross résumé templates."""
    source = Path(path)
    digest = hashlib.sha256()

    with source.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def _render_projects_payload(
    projects_state: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not isinstance(projects_state, dict):
        return []

    payload: list[dict[str, Any]] = []
    for project in projects_state.get("recommended_projects", []) or []:
        if not isinstance(project, dict):
            continue
        payload.append(
            {
                "title": _clean_text(project.get("title")),
                "display_title": _clean_text(
                    project.get("display_title")
                    or project.get("title")
                ),
                "subtitle": _clean_text(project.get("subtitle")),
                "resume_header_tools": [
                    _clean_text(item)
                    for item in project.get("resume_header_tools", []) or []
                    if _clean_text(item)
                ],
                "resume_header_context": [
                    _clean_text(item)
                    for item in project.get("resume_header_context", []) or []
                    if _clean_text(item)
                ],
                "canonical_tools": [
                    _clean_text(item)
                    for item in project.get("canonical_tools", []) or []
                    if _clean_text(item)
                ],
                "period": _clean_text(project.get("period")),
                "bullets": [
                    _clean_text(bullet)
                    for bullet in project.get("draft_bullets", []) or []
                    if _clean_text(bullet)
                ],
            }
        )
    return payload


def _render_skills_payload(
    skills_state: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not isinstance(skills_state, dict):
        return []

    payload: list[dict[str, Any]] = []
    for row in skills_state.get("skill_lines", []) or []:
        if not isinstance(row, dict):
            continue
        payload.append(
            {
                "category": _clean_text(row.get("category")),
                "items": [
                    _clean_text(item)
                    for item in row.get("items", []) or []
                    if _clean_text(item)
                ],
            }
        )
    return payload


def build_render_state_fingerprint(
    *,
    source_signature: str,
    projects_state: dict[str, Any] | None,
    skills_state: dict[str, Any] | None,
    layout_options: dict[str, Any],
) -> str:
    """
    Fingerprint only data that changes rendered document content/layout.

    Debug notes, evidence metadata, and fitting history are deliberately
    excluded so semantically identical DOCX states share one render.
    """
    payload = {
        "version": PHASE6C1_OPTIMIZATION_VERSION,
        "source_signature": str(source_signature),
        "projects": _render_projects_payload(projects_state),
        "skills": _render_skills_payload(skills_state),
        "layout_options": layout_options,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

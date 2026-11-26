"""B1.6: exact-order lazy project-reduction descriptors for Phase 6C path planning.

Only the *coarse planning path* uses this helper. A descriptor carries the exact
Phase 6C change receipt and a small geometry projection for B1.3's sorter,
not a complete copied résumé. The winner is fully materialized afterwards.
Local refinement and all actual render candidates use the original builder.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from resume_builder.evidence_aware_fitting import (
    PHASE6C_FITTING_VERSION,
    _bullet_evidence_summary,
    _candidate_sort_key,
    _clean_text,
    _metadata_rows_for_project,
    _support_counts,
    build_evidence_aware_project_reductions,
    remove_project_bullet,
    sync_project_bullet_metadata,
)

VERSION = "phase6c-v312b16-lazy-path-v1"
MARKER = "_v312b16_lazy_project_reduction"


def _valid_geometry(projects_state: dict[str, Any]) -> bool:
    """Use original construction for unexpected states instead of approximating."""
    if not isinstance(projects_state, dict):
        return False
    projects = projects_state.get("recommended_projects")
    if not isinstance(projects, list) or not projects:
        return False
    for p in projects:
        if not isinstance(p, dict):
            return False
        bullets = p.get("draft_bullets")
        if not isinstance(bullets, list) or not bullets:
            return False
        if any(not isinstance(b, str) or not b.strip() for b in bullets):
            return False
        if not all(isinstance(row, dict) for row in (p.get("bullet_evidence_priorities") or [])):
            return False
    return True


def lazy_project_reductions(
    projects_state: dict[str, Any],
    *,
    prefer_balanced_bullets: bool = False,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Produce original sorted candidates but replace their heavy states with projections.

    The candidate change dictionaries are the same as those from the original
    Phase 6C one-step builder; materialization validates the removed evidence.
    """
    if not _valid_geometry(projects_state):
        return build_evidence_aware_project_reductions(
            projects_state, prefer_balanced_bullets=prefer_balanced_bullets
        )
    base = deepcopy(projects_state)
    projects = base.get("recommended_projects", []) or []
    for p in projects:
        sync_project_bullet_metadata(p)
    counts = _support_counts(projects)
    geometry = [
        {key: deepcopy(p[key]) for key in ("project_id", "title", "display_title") if key in p}
        | {"draft_bullets": list(p["draft_bullets"])}
        for p in projects
    ]
    candidates: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for project_index, project in enumerate(projects):
        bullets = project.get("draft_bullets", []) or []
        if len(bullets) <= 1:
            continue
        rows = _metadata_rows_for_project(project)
        for bullet_index, bullet in enumerate(bullets):
            summary = _bullet_evidence_summary(
                project=project, row=rows[bullet_index], bullet=bullet,
                global_support_counts=counts,
            )
            previous_space_action = _clean_text(project.get("space_action")) or "keep_full"
            project_title = _clean_text(
                project.get("display_title") or project.get("title") or "Untitled Project"
            )
            change = {
                "fitting_version": PHASE6C_FITTING_VERSION,
                "change_type": "remove_bullet",
                "project": project_title,
                "removed_bullet": _clean_text(bullet),
                "removed_bullet_index": bullet_index,
                "removed_bullet_metadata": deepcopy(rows[bullet_index]),
                "previous_space_action": previous_space_action,
                "deletion_strategy": "phase6c_evidence_aware",
                "project_bullet_count_before": len(bullets),
                **summary,
            }
            # Only the geometry read by B1.3's _counts() is needed for sorting.
            # This is NOT a renderable state, and is never passed to a renderer.
            projected = {"recommended_projects": [
                {**p, "draft_bullets": (
                    p["draft_bullets"][:bullet_index]
                    + p["draft_bullets"][bullet_index + 1:]
                    if i == project_index else p["draft_bullets"]
                )}
                for i, p in enumerate(geometry)
            ]}
            projected[MARKER] = (project_index, bullet_index)
            candidates.append((projected, change))
    if not candidates:
        # Whole-project fallback is unusual, inexpensive, and has different
        # conservation rules: leave the original implementation authoritative.
        return build_evidence_aware_project_reductions(
            projects_state, prefer_balanced_bullets=prefer_balanced_bullets
        )
    candidates.sort(
        key=lambda item: _candidate_sort_key(
            item, prefer_balanced_bullets=prefer_balanced_bullets
        )
    )
    return candidates


def materialize_selected(
    source_projects: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    """Replace a selected projected state with the exact source-owned full state."""
    thin = candidate.get("projects")
    marker = thin.get(MARKER) if isinstance(thin, dict) else None
    if marker is None:
        return candidate
    if not (
        isinstance(marker, tuple) and len(marker) == 2
        and all(isinstance(n, int) and n >= 0 for n in marker)
    ):
        raise ValueError("B16_INVALID_PROJECT_DESCRIPTOR")
    pi, bi = marker
    base = deepcopy(source_projects)
    projects = base.get("recommended_projects", []) or []
    for p in projects:
        sync_project_bullet_metadata(p)
    if pi >= len(projects):
        raise ValueError("B16_PROJECT_INDEX_OUTSIDE_SOURCE")
    target = projects[pi]
    previous_space_action = _clean_text(target.get("space_action")) or "keep_full"
    removed_bullet, removed_metadata = remove_project_bullet(target, bullet_index=bi)
    target["space_action"] = (
        "single_bullet" if len(target.get("draft_bullets", []) or []) == 1 else "shorten"
    )
    change = candidate.get("change")
    if not isinstance(change, dict) or (
        change.get("removed_bullet") != removed_bullet
        or change.get("removed_bullet_metadata") != removed_metadata
        or change.get("previous_space_action") != previous_space_action
    ):
        raise ValueError("B16_SOURCE_METADATA_CHANGED_DURING_SELECTION")
    title = _clean_text(target.get("display_title") or target.get("title") or "Untitled Project")
    if title != change.get("project"):
        raise ValueError("B16_PROJECT_IDENTITY_CHANGED_DURING_SELECTION")
    base.setdefault("notes_for_user", []).append(
        "Phase 6C removed the lowest-loss available bullet "
        f"candidate from {title} after rendered comparison."
    )
    out = candidate.copy()
    out["projects"] = base
    return out

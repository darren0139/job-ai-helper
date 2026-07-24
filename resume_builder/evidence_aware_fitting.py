"""
Phase 6C evidence-aware one-page fitting helpers.

Phase 6B.1 emits bullet-level evidence metadata. This module turns that
metadata into deterministic fitting candidates without calling an LLM or
rendering a document. The DOCX fitter remains responsible for rendering each
candidate and comparing actual space saved.
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any

PHASE6C_FITTING_VERSION = "phase6c-evidence-aware-fitting-v1"
PHASE6C_RETENTION_TIEBREAK_VERSION = "phase6c2-retention-priority-v1"


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _clean_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = _clean_text(item)
        if text and text not in seen:
            cleaned.append(text)
            seen.add(text)
    return cleaned


def project_priority_score(project: dict[str, Any]) -> int:
    """Mirror the fitter's project-level relevance score."""
    priority = _clean_text(project.get("priority")).lower()
    base = {
        "high": 300,
        "medium": 200,
        "low": 100,
    }.get(priority, 150)

    fit_score = int(project.get("project_fit_score", 0) or 0)
    direct_matches = len(project.get("matched_jd_requirements", []) or [])
    transferable_matches = len(
        project.get("transferable_jd_requirements", []) or []
    )

    return (
        base
        + fit_score
        + direct_matches * 10
        + transferable_matches * 5
    )


def _default_metadata_row(index: int, bullet: str) -> dict[str, Any]:
    return {
        "bullet_index": index,
        "bullet_text": bullet,
        "supported_requirement_ids": [],
        "protected_requirement_ids": [],
        "unique_required_core_count": 0,
        "evidence_value": 0.0,
        "protect_during_fitting": False,
        "evidence_priority": index + 1,
    }


def _metadata_rows_for_project(
    project: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Return one metadata row per current bullet.

    Phase 6B.1 emits rows in bullet order. Phase 6C preserves that one-to-one
    order when compact wording is substituted and explicitly reindexes rows
    after deletion/restoration.
    """
    bullets = [
        _clean_text(value)
        for value in (project.get("draft_bullets", []) or [])
        if _clean_text(value)
    ]
    raw_rows = project.get("bullet_evidence_priorities", []) or []
    rows_by_index: dict[int, dict[str, Any]] = {}

    for raw in raw_rows:
        if not isinstance(raw, dict):
            continue
        try:
            index = int(raw.get("bullet_index"))
        except (TypeError, ValueError):
            continue
        if index < 0 or index >= len(bullets) or index in rows_by_index:
            continue
        rows_by_index[index] = deepcopy(raw)

    rows: list[dict[str, Any]] = []
    for index, bullet in enumerate(bullets):
        row = rows_by_index.get(index, _default_metadata_row(index, bullet))
        row["bullet_index"] = index
        row["bullet_text"] = bullet
        row["supported_requirement_ids"] = _clean_string_list(
            row.get("supported_requirement_ids", [])
        )
        row["protected_requirement_ids"] = _clean_string_list(
            row.get("protected_requirement_ids", [])
        )
        row["unique_required_core_count"] = max(
            0,
            int(row.get("unique_required_core_count", 0) or 0),
        )
        row["evidence_value"] = max(
            0.0,
            float(row.get("evidence_value", 0.0) or 0.0),
        )
        row["protect_during_fitting"] = bool(
            row.get("protect_during_fitting")
            or row["protected_requirement_ids"]
            or row["unique_required_core_count"]
        )
        try:
            row["evidence_priority"] = int(
                row.get("evidence_priority", index + 1) or index + 1
            )
        except (TypeError, ValueError):
            row["evidence_priority"] = index + 1
        rows.append(row)

    return rows


def sync_project_bullet_metadata(
    project: dict[str, Any],
    *,
    bullet_texts: list[str] | None = None,
) -> dict[str, Any]:
    """
    Synchronize Phase 6B.1 evidence rows with the current bullet list.

    This is safe for one-to-one wording substitutions such as compact bullets.
    For deletion, use ``remove_project_bullet`` so the deleted row is removed
    before the remaining rows are reindexed.
    """
    if bullet_texts is not None:
        project["draft_bullets"] = [
            _clean_text(value)
            for value in bullet_texts
            if _clean_text(value)
        ]

    rows = _metadata_rows_for_project(project)
    project["bullet_evidence_priorities"] = rows
    project["protected_bullet_indexes"] = [
        int(row["bullet_index"])
        for row in rows
        if row.get("protect_during_fitting")
    ]
    return project


def _support_counts(projects: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for project in projects:
        for row in _metadata_rows_for_project(project):
            counts.update(row.get("supported_requirement_ids", []) or [])
    return counts


def _bullet_evidence_summary(
    *,
    project: dict[str, Any],
    row: dict[str, Any],
    bullet: str,
    global_support_counts: Counter[str],
) -> dict[str, Any]:
    supported = _clean_string_list(
        row.get("supported_requirement_ids", [])
    )
    protected = _clean_string_list(
        row.get("protected_requirement_ids", [])
    )
    globally_unique = sorted(
        requirement_id
        for requirement_id in supported
        if global_support_counts.get(requirement_id, 0) == 1
    )
    unique_core_count = max(
        0,
        int(row.get("unique_required_core_count", 0) or 0),
    )
    evidence_value = max(
        0.0,
        float(row.get("evidence_value", 0.0) or 0.0),
    )
    explicitly_protected = bool(
        row.get("protect_during_fitting")
        or protected
        or unique_core_count
    )

    try:
        evidence_priority = max(
            1,
            int(row.get("evidence_priority", 1) or 1),
        )
    except (TypeError, ValueError):
        evidence_priority = 1

    if unique_core_count > 0:
        protection_tier = 2
    elif explicitly_protected or globally_unique:
        protection_tier = 1
    else:
        protection_tier = 0

    project_priority = project_priority_score(project)
    word_count = max(1, len(_clean_text(bullet).split()))

    # Large tier weights make "preserve unique required/core evidence" a hard
    # preference while still allowing an emergency fallback when every
    # remaining bullet is protected.
    evidence_loss_score = int(
        project_priority
        + round(evidence_value * 100)
        + len(supported) * 20
        + len(protected) * 450
        + len(globally_unique) * 650
        + unique_core_count * 1600
        + protection_tier * 900
    )

    reasons: list[str] = []
    if unique_core_count:
        reasons.append(
            f"carries {unique_core_count} unique required/core requirement(s)"
        )
    if globally_unique:
        reasons.append(
            "is the only retained bullet supporting "
            + ", ".join(globally_unique)
        )
    if protected:
        reasons.append(
            "was marked protected for "
            + ", ".join(protected)
        )
    if not reasons:
        reasons.append(
            "contains no unique protected requirement evidence"
        )

    return {
        "supported_requirement_ids": supported,
        "protected_requirement_ids": protected,
        "globally_unique_requirement_ids": globally_unique,
        "unique_required_core_count": unique_core_count,
        "protect_during_fitting": explicitly_protected,
        "protection_tier": protection_tier,
        "evidence_value": round(evidence_value, 4),
        "evidence_priority": evidence_priority,
        "retention_tiebreak_version": (
            PHASE6C_RETENTION_TIEBREAK_VERSION
        ),
        "retention_tiebreak_reason": (
            "Higher Phase 6B.1 evidence-priority numbers are weaker "
            "retention candidates when protection, loss, and layout are equal."
        ),
        "evidence_loss_score": evidence_loss_score,
        "estimated_space_saved_words": word_count,
        "evidence_loss_reason": "; ".join(reasons),
        "project_priority_score": project_priority,
    }


def remove_project_bullet(
    project: dict[str, Any],
    *,
    bullet_index: int,
) -> tuple[str, dict[str, Any]]:
    """Remove one bullet and its matching evidence metadata row."""
    bullets = [
        _clean_text(value)
        for value in (project.get("draft_bullets", []) or [])
        if _clean_text(value)
    ]
    rows = _metadata_rows_for_project(project)

    if bullet_index < 0 or bullet_index >= len(bullets):
        raise IndexError("Bullet index is outside the current project bullets.")

    removed_bullet = bullets.pop(bullet_index)
    removed_metadata = rows.pop(bullet_index)

    for new_index, row in enumerate(rows):
        row["bullet_index"] = new_index
        row["bullet_text"] = bullets[new_index]

    project["draft_bullets"] = bullets
    project["bullet_evidence_priorities"] = rows
    sync_project_bullet_metadata(project)
    return removed_bullet, removed_metadata


def restore_removed_bullet_metadata(
    project: dict[str, Any],
    *,
    bullet_index: int,
    bullet_text: str,
    removed_metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    """Reinsert metadata when the fitter restores an earlier bullet deletion."""
    bullets = [
        _clean_text(value)
        for value in (project.get("draft_bullets", []) or [])
        if _clean_text(value)
    ]
    insert_index = max(0, min(int(bullet_index), max(0, len(bullets) - 1)))

    # Read the surviving rows in their current order. Calling
    # _metadata_rows_for_project here would incorrectly align those rows against
    # the already-restored bullet list before the removed row is reinserted.
    rows = [
        deepcopy(row)
        for row in (project.get("bullet_evidence_priorities", []) or [])
        if isinstance(row, dict)
    ]
    rows.sort(
        key=lambda row: int(row.get("bullet_index", 0) or 0)
    )

    restored_row = (
        deepcopy(removed_metadata)
        if isinstance(removed_metadata, dict)
        else _default_metadata_row(insert_index, _clean_text(bullet_text))
    )
    rows.insert(insert_index, restored_row)

    for new_index, row in enumerate(rows[: len(bullets)]):
        row["bullet_index"] = new_index
        row["bullet_text"] = bullets[new_index]

    project["bullet_evidence_priorities"] = rows[: len(bullets)]
    sync_project_bullet_metadata(project)
    return project


def _candidate_sort_key(
    item: tuple[dict[str, Any], dict[str, Any]],
    *,
    prefer_balanced_bullets: bool,
) -> tuple[Any, ...]:
    _, change = item
    words = max(
        1,
        int(change.get("estimated_space_saved_words", 1) or 1),
    )
    loss = int(change.get("evidence_loss_score", 0) or 0)
    bullets_before = int(
        change.get("project_bullet_count_before", 0) or 0
    )
    evidence_priority = max(
        0,
        int(change.get("evidence_priority", 0) or 0),
    )

    return (
        int(change.get("protection_tier", 0) or 0),
        round(loss / words, 6),
        loss,
        -bullets_before if prefer_balanced_bullets else 0,
        int(change.get("project_priority_score", 0) or 0),
        -words,
        -evidence_priority,
        _clean_text(change.get("project")).lower(),
        int(change.get("removed_bullet_index", 0) or 0),
    )


def build_evidence_aware_project_reductions(
    tailored_projects: dict[str, Any],
    *,
    minimum_bullets_per_project: int = 1,
    minimum_projects_to_keep: int = 3,
    prefer_balanced_bullets: bool = False,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """
    Build every safe one-step project reduction for rendered comparison.

    Bullet candidates are returned first. Whole-project candidates are returned
    only after every project is already at the minimum bullet count.
    """
    base = deepcopy(tailored_projects)
    projects = base.get("recommended_projects", []) or []

    for project in projects:
        sync_project_bullet_metadata(project)

    support_counts = _support_counts(projects)
    bullet_candidates: list[
        tuple[dict[str, Any], dict[str, Any]]
    ] = []

    for project_index, project in enumerate(projects):
        bullets = project.get("draft_bullets", []) or []
        if len(bullets) <= minimum_bullets_per_project:
            continue

        rows = _metadata_rows_for_project(project)
        for bullet_index, bullet in enumerate(bullets):
            summary = _bullet_evidence_summary(
                project=project,
                row=rows[bullet_index],
                bullet=bullet,
                global_support_counts=support_counts,
            )
            candidate_state = deepcopy(base)
            target = candidate_state["recommended_projects"][
                project_index
            ]
            previous_space_action = _clean_text(
                target.get("space_action")
            ) or "keep_full"
            removed_bullet, removed_metadata = remove_project_bullet(
                target,
                bullet_index=bullet_index,
            )
            target["space_action"] = (
                "single_bullet"
                if len(target.get("draft_bullets", []) or []) == 1
                else "shorten"
            )

            project_title = _clean_text(
                target.get("display_title")
                or target.get("title")
                or "Untitled Project"
            )
            change = {
                "fitting_version": PHASE6C_FITTING_VERSION,
                "change_type": "remove_bullet",
                "project": project_title,
                "removed_bullet": removed_bullet,
                "removed_bullet_index": bullet_index,
                "removed_bullet_metadata": removed_metadata,
                "previous_space_action": previous_space_action,
                "deletion_strategy": "phase6c_evidence_aware",
                "project_bullet_count_before": len(bullets),
                **summary,
            }
            candidate_state.setdefault(
                "notes_for_user",
                [],
            ).append(
                "Phase 6C removed the lowest-loss available bullet "
                f"candidate from {project_title} after rendered comparison."
            )
            bullet_candidates.append((candidate_state, change))

    if bullet_candidates:
        return sorted(
            bullet_candidates,
            key=lambda item: _candidate_sort_key(
                item,
                prefer_balanced_bullets=prefer_balanced_bullets,
            ),
        )

    if len(projects) <= minimum_projects_to_keep:
        return []

    project_candidates: list[
        tuple[dict[str, Any], dict[str, Any]]
    ] = []
    for project_index, project in enumerate(projects):
        rows = _metadata_rows_for_project(project)
        supported = sorted(
            {
                requirement_id
                for row in rows
                for requirement_id in (
                    row.get("supported_requirement_ids", []) or []
                )
            }
        )
        protected = sorted(
            {
                requirement_id
                for row in rows
                for requirement_id in (
                    row.get("protected_requirement_ids", []) or []
                )
            }
        )
        global_unique = sorted(
            requirement_id
            for requirement_id in supported
            if support_counts.get(requirement_id, 0) == 1
        )
        unique_core = sum(
            int(row.get("unique_required_core_count", 0) or 0)
            for row in rows
        )
        evidence_value = sum(
            float(row.get("evidence_value", 0.0) or 0.0)
            for row in rows
        )
        priority = project_priority_score(project)
        word_count = sum(
            len(_clean_text(bullet).split())
            for bullet in (project.get("draft_bullets", []) or [])
        )
        protection_tier = (
            3 if unique_core > 0
            else 2 if protected or global_unique
            else 1
        )
        loss = int(
            10000
            + priority * 10
            + round(evidence_value * 100)
            + len(protected) * 700
            + len(global_unique) * 900
            + unique_core * 2000
        )

        candidate_state = deepcopy(base)
        removed_project = candidate_state[
            "recommended_projects"
        ].pop(project_index)
        title = _clean_text(
            removed_project.get("display_title")
            or removed_project.get("title")
            or "Untitled Project"
        )
        candidate_state.setdefault(
            "projects_to_remove_or_deprioritize",
            [],
        ).append(
            {
                "title": title,
                "reason": (
                    "Removed only after every retained project had reached "
                    "the minimum bullet count."
                ),
            }
        )

        change = {
            "fitting_version": PHASE6C_FITTING_VERSION,
            "change_type": "remove_project",
            "project": title,
            "removed_project_index": project_index,
            "removed_project_data": deepcopy(project),
            "project_priority_score": priority,
            "supported_requirement_ids": supported,
            "protected_requirement_ids": protected,
            "globally_unique_requirement_ids": global_unique,
            "unique_required_core_count": unique_core,
            "protect_during_fitting": bool(
                protected or global_unique or unique_core
            ),
            "protection_tier": protection_tier,
            "evidence_value": round(evidence_value, 4),
            "evidence_loss_score": loss,
            "estimated_space_saved_words": max(1, word_count),
            "evidence_loss_reason": (
                "whole-project fallback after all projects reached the "
                "minimum bullet count"
            ),
            "deletion_strategy": "phase6c_project_fallback",
        }
        project_candidates.append((candidate_state, change))

    return sorted(
        project_candidates,
        key=lambda item: _candidate_sort_key(
            item,
            prefer_balanced_bullets=prefer_balanced_bullets,
        ),
    )

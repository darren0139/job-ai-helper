from __future__ import annotations

from typing import Any


def select_batch_jobs(
    jobs: list[dict[str, Any]] | None,
    *,
    limit: int,
) -> list[dict[str, Any]]:
    """Return a stable valid subset for explicit Job Match batch analysis."""
    safe_limit = max(0, int(limit or 0))
    if safe_limit <= 0:
        return []

    selected: list[dict[str, Any]] = []
    seen_ids: set[int] = set()

    for raw in jobs or []:
        if not isinstance(raw, dict):
            continue

        job_id = int(raw.get("id", 0) or 0)
        if job_id <= 0 or job_id in seen_ids:
            continue

        description = str(raw.get("description") or "").strip()
        if len(description) < 100:
            continue

        seen_ids.add(job_id)
        selected.append(raw)
        if len(selected) >= safe_limit:
            break

    return selected


def job_is_analyzable(
    job: dict[str, Any] | None,
) -> bool:
    if not isinstance(job, dict):
        return False
    if int(job.get("id", 0) or 0) <= 0:
        return False
    if not str(job.get("content_hash") or "").strip():
        return False
    return len(str(job.get("description") or "").strip()) >= 100


def classify_batch_jobs(
    jobs: list[dict[str, Any]] | None,
    match_states: dict[int, dict[str, Any]] | None,
) -> dict[str, Any]:
    states = match_states or {}
    current_jobs: list[dict[str, Any]] = []
    stale_jobs: list[dict[str, Any]] = []
    not_analyzed_jobs: list[dict[str, Any]] = []
    not_analyzable_jobs: list[dict[str, Any]] = []
    pending_jobs: list[dict[str, Any]] = []
    seen_ids: set[int] = set()

    for raw in jobs or []:
        if not isinstance(raw, dict):
            continue

        job_id = int(raw.get("id", 0) or 0)
        if job_id <= 0 or job_id in seen_ids:
            continue
        seen_ids.add(job_id)

        state = states.get(job_id) or {}
        status = str(state.get("status") or "none").strip().lower()

        if status == "current":
            current_jobs.append(raw)
            continue

        if not job_is_analyzable(raw):
            not_analyzable_jobs.append(raw)
            continue

        if status == "stale":
            stale_jobs.append(raw)
            pending_jobs.append(raw)
            continue

        not_analyzed_jobs.append(raw)
        pending_jobs.append(raw)

    return {
        "current_jobs": current_jobs,
        "stale_jobs": stale_jobs,
        "not_analyzed_jobs": not_analyzed_jobs,
        "not_analyzable_jobs": not_analyzable_jobs,
        "pending_jobs": pending_jobs,
        "current_count": len(current_jobs),
        "stale_count": len(stale_jobs),
        "not_analyzed_count": len(not_analyzed_jobs),
        "not_analyzable_count": len(not_analyzable_jobs),
        "pending_count": len(pending_jobs),
        "total_count": (
            len(current_jobs)
            + len(stale_jobs)
            + len(not_analyzed_jobs)
            + len(not_analyzable_jobs)
        ),
    }


def select_pending_batch_jobs(
    jobs: list[dict[str, Any]] | None,
    match_states: dict[int, dict[str, Any]] | None,
    *,
    limit: int,
) -> list[dict[str, Any]]:
    safe_limit = max(0, int(limit or 0))
    if safe_limit <= 0:
        return []

    classified = classify_batch_jobs(
        jobs,
        match_states,
    )
    return list(
        classified["pending_jobs"][:safe_limit]
    )


def match_display_label(
    job: dict[str, Any],
    state: dict[str, Any] | None,
) -> str:
    state = state or {}
    status = str(state.get("status") or "none").strip().lower()

    if status == "current":
        snapshot = state.get("snapshot")
        summary = (
            snapshot.get("summary")
            if isinstance(snapshot, dict)
            and isinstance(snapshot.get("summary"), dict)
            else {}
        )
        if summary.get("ranking_eligible") is True:
            return "Eligible"
        if summary.get("ranking_eligible") is False:
            return "Provisional"

        ranking_status = str(
            summary.get("ranking_status") or ""
        ).strip().lower()
        if ranking_status == "eligible":
            return "Eligible"
        if ranking_status:
            return "Provisional"
        return "Analyzed"

    if status == "stale":
        return "Stale"

    if not job_is_analyzable(job):
        return "Not analyzable"

    return "Not analyzed"

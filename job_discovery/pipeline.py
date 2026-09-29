from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Callable

from database.job_discovery_manager import (
    get_latest_successful_discovery_run,
    list_discovered_jobs_by_scope,
    list_target_companies,
    mark_expired_jobs,
    mark_missing_jobs_removed,
    record_discovery_run,
    upsert_discovered_jobs,
)
from job_discovery.config import load_job_discovery_config
from job_discovery.models import SearchSpec
from job_discovery.sources import (
    AshbySource,
    CareersGovSource,
    GreenhouseSource,
    LeverSource,
    MyCareersFutureSource,
    SmartRecruitersSource,
)


ProgressCallback = Callable[[dict[str, Any]], None]


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _targets(
    config: dict[str, Any],
    key: str,
    overrides: dict[str, list[str]] | None,
    target_selection: dict[str, list[str]] | None = None,
) -> list[dict[str, str]]:
    # One-off runtime identifiers intentionally remain the highest-priority path.
    if overrides and overrides.get(key):
        return [
            {"identifier": str(value).strip(), "company": ""}
            for value in overrides[key]
            if str(value).strip()
        ]

    saved_targets = list_target_companies(include_disabled=False, provider=key)
    if saved_targets:
        requested = {
            str(value or "").strip().casefold()
            for value in (target_selection or {}).get(key, [])
            if str(value or "").strip()
        }
        if requested:
            saved_targets = [
                target
                for target in saved_targets
                if str(target.get("ats_identifier") or "").strip().casefold() in requested
            ]
        return [
            {
                "identifier": str(target.get("ats_identifier") or "").strip(),
                "company": str(target.get("company_name") or "").strip(),
            }
            for target in saved_targets
            if str(target.get("ats_identifier") or "").strip()
        ]

    # If this provider exists in the registry but every target is disabled, respect
    # that state rather than silently reactivating legacy V1 config entries.
    registry_rows = list_target_companies(include_disabled=True, provider=key)
    if registry_rows:
        return []

    target_root = config.get("targets") if isinstance(config.get("targets"), dict) else {}
    values = target_root.get(key, []) if isinstance(target_root, dict) else []
    return [dict(value) for value in values if isinstance(value, dict)]


def _build_sources(
    selected_sources: list[str],
    *,
    target_overrides: dict[str, list[str]] | None = None,
    target_selection: dict[str, list[str]] | None = None,
) -> list[Any]:
    selected = set(selected_sources)
    config = load_job_discovery_config()
    sources: list[Any] = []
    if "mycareersfuture" in selected:
        sources.append(MyCareersFutureSource())
    if "careers_gov" in selected:
        sources.append(CareersGovSource())

    for target in _targets(config, "greenhouse", target_overrides, target_selection):
        if "greenhouse" in selected:
            sources.append(GreenhouseSource(target["identifier"], company_name=target.get("company", "")))
    for target in _targets(config, "lever", target_overrides, target_selection):
        if "lever" in selected:
            sources.append(LeverSource(target["identifier"], company_name=target.get("company", "")))
    for target in _targets(config, "ashby", target_overrides, target_selection):
        if "ashby" in selected:
            sources.append(AshbySource(target["identifier"], company_name=target.get("company", "")))
    for target in _targets(config, "smartrecruiters", target_overrides, target_selection):
        if "smartrecruiters" in selected:
            sources.append(SmartRecruitersSource(target["identifier"], company_name=target.get("company", "")))
    return sources


def _parse_time(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            # Existing discovery-run timestamps are local wall-clock values.
            # Attach the machine's local timezone before comparing with UTC.
            parsed = parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)
        return parsed.astimezone(timezone.utc)
    except (ValueError, OSError, OverflowError):
        return None


def _recent_success(source_key: str) -> tuple[dict[str, Any] | None, float | None]:
    row = get_latest_successful_discovery_run(source_key)
    if not row:
        return None, None
    finished = _parse_time(row.get("finished_at"))
    if finished is None:
        return row, None
    return row, max(0.0, (datetime.now(timezone.utc) - finished).total_seconds() / 60.0)


def _can_reuse_recent_run(
    source: Any,
    recent_run: dict[str, Any] | None,
    age_minutes: float | None,
    spec: SearchSpec,
    *,
    min_interval: int,
    force_full_refresh: bool,
) -> bool:
    if force_full_refresh or min_interval <= 0 or age_minutes is None or age_minutes >= min_interval:
        return False
    if isinstance(source, (MyCareersFutureSource, CareersGovSource)):
        return (
            str((recent_run or {}).get("query") or "").strip().casefold()
            == spec.query.strip().casefold()
        )
    return True


def _emit(callback: ProgressCallback | None, **payload: Any) -> None:
    if callback is not None:
        callback(dict(payload))


def _fetch_one(
    source: Any,
    spec: SearchSpec,
    *,
    force_full_refresh: bool,
) -> list[Any]:
    if isinstance(source, SmartRecruitersSource):
        known_rows = list_discovered_jobs_by_scope(source.run_key)
        known_jobs = {
            str(row.get("source_job_id") or ""): row
            for row in known_rows
            if str(row.get("source_job_id") or "")
        }
        return source.fetch(
            spec,
            known_jobs=known_jobs,
            force_detail_refresh=force_full_refresh,
        )
    return source.fetch(spec)


def refresh_job_sources(
    *,
    query: str,
    selected_sources: list[str],
    max_pages: int = 3,
    target_overrides: dict[str, list[str]] | None = None,
    target_selection: dict[str, list[str]] | None = None,
    max_workers: int = 4,
    min_refresh_interval_minutes: int = 15,
    force_full_refresh: bool = False,
    progress_callback: ProgressCallback | None = None,
) -> list[dict[str, Any]]:
    spec = SearchSpec(
        query=str(query or "").strip(),
        singapore_only=True,
        max_pages=max(1, min(int(max_pages), 10)),
        page_size=100,
        limit_per_source=500,
    )
    sources = _build_sources(
        selected_sources,
        target_overrides=target_overrides,
        target_selection=target_selection,
    )
    summaries: list[dict[str, Any]] = []
    runnable: list[Any] = []
    min_interval = max(0, int(min_refresh_interval_minutes))

    for source in sources:
        recent_run, age = _recent_success(source.run_key)
        if _can_reuse_recent_run(
            source,
            recent_run,
            age,
            spec,
            min_interval=min_interval,
            force_full_refresh=force_full_refresh,
        ):
            reason = f"refreshed {age:.1f} min ago (< {min_interval} min)"
            summary = {
                "source_key": source.run_key,
                "display_name": source.display_name,
                "status": "skipped",
                "fetched_count": 0,
                "new": 0,
                "changed": 0,
                "unchanged": 0,
                "reactivated": 0,
                "removed": 0,
                "snapshot_complete": False,
                "detail_fetched": 0,
                "detail_reused": 0,
                "duration_seconds": 0.0,
                "error": reason,
            }
            record_discovery_run(
                source_key=source.run_key,
                query=spec.query,
                status="skipped",
                fetched_count=0,
                error_text=reason,
                started_at=_now(),
            )
            summaries.append(summary)
            _emit(progress_callback, phase="skipped", source_key=source.run_key, summary=summary)
            continue
        runnable.append(source)
        _emit(progress_callback, phase="queued", source_key=source.run_key, display_name=source.display_name)

    if runnable:
        worker_count = max(1, min(int(max_workers), 8, len(runnable)))
        with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="job-refresh") as executor:
            futures: dict[Any, tuple[Any, str, float]] = {}
            for source in runnable:
                started = _now()
                started_clock = perf_counter()
                future = executor.submit(
                    _fetch_one,
                    source,
                    spec,
                    force_full_refresh=force_full_refresh,
                )
                futures[future] = (source, started, started_clock)

            # HTTP work runs concurrently; SQLite lifecycle writes remain in this
            # main loop so independent fetches never fight over the DB writer lock.
            for future in as_completed(futures):
                source, started, started_clock = futures[future]
                try:
                    jobs = future.result()
                    stats = upsert_discovered_jobs(jobs, source_scope=source.run_key)
                    removed_count = 0
                    fetch_complete = bool(getattr(source, "fetch_complete", False))
                    if fetch_complete:
                        removed_count = mark_missing_jobs_removed(
                            source_scope=source.run_key,
                            seen_source_job_ids=[job.source_job_id for job in jobs],
                        )
                    duration = perf_counter() - started_clock
                    summary = {
                        "source_key": source.run_key,
                        "display_name": source.display_name,
                        "status": "ok",
                        "fetched_count": len(jobs),
                        **stats,
                        "removed": removed_count,
                        "snapshot_complete": fetch_complete,
                        "detail_fetched": int(getattr(source, "detail_fetched_count", 0) or 0),
                        "detail_reused": int(getattr(source, "detail_reused_count", 0) or 0),
                        "duration_seconds": duration,
                        "error": "",
                    }
                    record_discovery_run(
                        source_key=source.run_key,
                        query=spec.query,
                        status="ok",
                        fetched_count=len(jobs),
                        new_count=stats["new"],
                        changed_count=stats["changed"],
                        unchanged_count=stats["unchanged"],
                        reactivated_count=stats["reactivated"],
                        removed_count=removed_count,
                        started_at=started,
                    )
                    _emit(progress_callback, phase="completed", source_key=source.run_key, summary=summary)
                except Exception as exc:
                    duration = perf_counter() - started_clock
                    summary = {
                        "source_key": source.run_key,
                        "display_name": source.display_name,
                        "status": "error",
                        "fetched_count": 0,
                        "new": 0,
                        "changed": 0,
                        "unchanged": 0,
                        "reactivated": 0,
                        "removed": 0,
                        "snapshot_complete": False,
                        "detail_fetched": int(getattr(source, "detail_fetched_count", 0) or 0),
                        "detail_reused": int(getattr(source, "detail_reused_count", 0) or 0),
                        "duration_seconds": duration,
                        "error": str(exc),
                    }
                    record_discovery_run(
                        source_key=source.run_key,
                        query=spec.query,
                        status="error",
                        fetched_count=0,
                        error_text=str(exc),
                        started_at=started,
                    )
                    _emit(progress_callback, phase="error", source_key=source.run_key, summary=summary)
                summaries.append(summary)

    mark_expired_jobs()
    return summaries

"""Pure live-filter helpers for Job Finder faceted search."""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable


def _text(value: Any) -> str:
    return str(value or "").strip()


def filter_jobs_by_sources(
    jobs: Iterable[dict[str, Any]],
    selected_sources: Iterable[str],
) -> list[dict[str, Any]]:
    """No selected source means All sources."""
    selected = {_text(value).lower() for value in selected_sources if _text(value)}
    if not selected:
        return [dict(job) for job in jobs]
    return [
        dict(job)
        for job in jobs
        if _text(job.get("source")).lower() in selected
    ]


def source_counts(jobs: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for job in jobs:
        source = _text(job.get("source")).lower()
        if source:
            counts[source] += 1
    return dict(counts)


def company_counts(jobs: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for job in jobs:
        company = _text(job.get("company"))
        if company:
            counts[company] += 1
    return dict(counts)


def filter_jobs_by_companies(
    jobs: Iterable[dict[str, Any]],
    selected_companies: Iterable[str],
) -> list[dict[str, Any]]:
    """No selected company means All companies."""
    selected = {_text(value).casefold() for value in selected_companies if _text(value)}
    if not selected:
        return [dict(job) for job in jobs]
    return [
        dict(job)
        for job in jobs
        if _text(job.get("company")).casefold() in selected
    ]


def employment_type_counts(jobs: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for job in jobs:
        value = _text(job.get("employment_type"))
        if value:
            counts[value] += 1
    return dict(counts)


def filter_jobs_by_employment_types(
    jobs: Iterable[dict[str, Any]],
    selected_types: Iterable[str],
) -> list[dict[str, Any]]:
    """No selected employment type means All employment types."""
    selected = {_text(value).casefold() for value in selected_types if _text(value)}
    if not selected:
        return [dict(job) for job in jobs]
    output: list[dict[str, Any]] = []
    for job in jobs:
        value = _text(job.get("employment_type")).casefold()
        if value in selected:
            output.append(dict(job))
    return output


def filter_jobs_by_max_explicit_minimum_experience(
    jobs: Iterable[dict[str, Any]],
    max_years: float | None,
) -> list[dict[str, Any]]:
    """Hide only jobs whose parsed explicit minimum is above the ceiling.

    Unknown experience requirements pass. This is conservative: absence of a
    parsed requirement is not treated as evidence that a job is too senior.
    """
    if max_years is None:
        return [dict(job) for job in jobs]

    output: list[dict[str, Any]] = []
    for job in jobs:
        raw = job.get("experience_years_min")
        if raw is None or _text(raw) == "":
            output.append(dict(job))
            continue
        try:
            minimum = float(raw)
        except (TypeError, ValueError):
            output.append(dict(job))
            continue
        if minimum <= float(max_years):
            output.append(dict(job))
    return output

def filter_jobs_by_freshness(
    jobs: Iterable[dict[str, Any]],
    max_age_days: int | None,
    *,
    now_timestamp: float | None = None,
) -> list[dict[str, Any]]:
    """Filter by posted_at, falling back to first_seen_at when posting date is absent.

    No age selection means All jobs. A dated freshness selection excludes rows
    with neither a parseable posted_at nor first_seen_at timestamp.
    """
    if max_age_days is None:
        return [dict(job) for job in jobs]

    from datetime import datetime, timezone

    if now_timestamp is None:
        now_timestamp = datetime.now(timezone.utc).timestamp()
    cutoff = float(now_timestamp) - int(max_age_days) * 86400

    def _timestamp(value: Any) -> float:
        raw = _text(value)
        if not raw:
            return 0.0
        try:
            if raw.isdigit() and len(raw) >= 12:
                return float(raw) / 1000.0
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.timestamp()
        except (TypeError, ValueError, OSError, OverflowError):
            return 0.0

    output: list[dict[str, Any]] = []
    for job in jobs:
        timestamp = _timestamp(job.get("posted_at")) or _timestamp(job.get("first_seen_at"))
        if timestamp >= cutoff:
            output.append(dict(job))
    return output


def filter_jobs_by_lifecycle(
    jobs: Iterable[dict[str, Any]],
    selected_statuses: Iterable[str],
) -> list[dict[str, Any]]:
    """No selected availability status means All statuses."""
    selected = {_text(value).lower() for value in selected_statuses if _text(value)}
    if not selected:
        return [dict(job) for job in jobs]
    return [
        dict(job)
        for job in jobs
        if _text(job.get("lifecycle_status") or "active").lower() in selected
    ]


def filter_jobs_by_events(
    jobs: Iterable[dict[str, Any]],
    selected_events: Iterable[str],
) -> list[dict[str, Any]]:
    """No selected last-event value means All events.

    Unlike the V1.2.3 inline implementation, this is exact for active, removed,
    and expired rows alike; non-active rows do not bypass the event filter.
    """
    selected = {_text(value).lower() for value in selected_events if _text(value)}
    if not selected:
        return [dict(job) for job in jobs]
    return [
        dict(job)
        for job in jobs
        if _text(job.get("last_event") or "unchanged").lower() in selected
    ]


def is_entry_level_job(job: dict[str, Any]) -> bool:
    """Conservative deterministic entry/junior/graduate heuristic."""
    import re

    title_and_seniority = " ".join(
        _text(job.get(key)) for key in ("title", "seniority")
    ).casefold()

    senior_patterns = (
        r"\bsenior\b",
        r"\bsr\.?\b",
        r"\bstaff\b",
        r"\bprincipal\b",
        r"\bdirector\b",
        r"\bvice president\b",
        r"\bvp\b",
        r"\bhead of\b",
        r"\bengineering manager\b",
    )
    if any(re.search(pattern, title_and_seniority) for pattern in senior_patterns):
        return False

    minimum = job.get("experience_years_min")
    if minimum is not None and _text(minimum):
        try:
            if float(minimum) <= 2.0:
                return True
        except (TypeError, ValueError):
            pass

    text = " ".join(
        _text(job.get(key))
        for key in ("title", "seniority", "employment_type", "description")
    ).casefold()
    entry_patterns = (
        r"\bentry[- ]level\b",
        r"\bfresh graduate\b",
        r"\bfresh grad\b",
        r"\bgraduate programme\b",
        r"\bgraduate program\b",
        r"\bjunior\b",
        r"\bintern(?:ship)?\b",
        r"\b0\s*[-–]\s*2 years?\b",
        r"\b1\s*[-–]\s*2 years?\b",
    )
    return any(re.search(pattern, text) for pattern in entry_patterns)


def filter_jobs_by_entry_level(
    jobs: Iterable[dict[str, Any]],
    enabled: bool,
) -> list[dict[str, Any]]:
    if not enabled:
        return [dict(job) for job in jobs]
    return [dict(job) for job in jobs if is_entry_level_job(job)]


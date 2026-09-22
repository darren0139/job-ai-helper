"""SQLite persistence for raw and normalized discovered jobs."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

from job_discovery.models import NormalizedJob


DB_PATH = Path("data/applications.db")


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _ensure_column(
    connection: sqlite3.Connection,
    table: str,
    column: str,
    definition: str,
) -> None:
    columns = {
        str(row["name"])
        for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_job_discovery_schema() -> None:
    connection = _connect()
    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS discovered_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                source_job_id TEXT NOT NULL,
                source_platform TEXT,
                title TEXT NOT NULL,
                company TEXT,
                location TEXT,
                description TEXT NOT NULL,
                source_url TEXT,
                apply_url TEXT,
                posted_at TEXT,
                expires_at TEXT,
                salary_min REAL,
                salary_max REAL,
                salary_currency TEXT,
                salary_period TEXT,
                employment_type TEXT,
                seniority TEXT,
                experience_years_min REAL,
                experience_years_max REAL,
                content_hash TEXT NOT NULL,
                raw_payload_json TEXT NOT NULL,
                source_scope TEXT,
                lifecycle_status TEXT NOT NULL DEFAULT 'active',
                last_event TEXT NOT NULL DEFAULT 'unchanged',
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                last_changed_at TEXT,
                removed_at TEXT,
                updated_at TEXT NOT NULL,
                UNIQUE(source, source_job_id)
            );

            CREATE TABLE IF NOT EXISTS job_discovery_raw_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                source_job_id TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                UNIQUE(source, source_job_id, content_hash)
            );

            CREATE TABLE IF NOT EXISTS job_discovery_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_key TEXT NOT NULL,
                query TEXT,
                status TEXT NOT NULL,
                fetched_count INTEGER NOT NULL DEFAULT 0,
                new_count INTEGER NOT NULL DEFAULT 0,
                changed_count INTEGER NOT NULL DEFAULT 0,
                unchanged_count INTEGER NOT NULL DEFAULT 0,
                reactivated_count INTEGER NOT NULL DEFAULT 0,
                removed_count INTEGER NOT NULL DEFAULT 0,
                error_text TEXT,
                started_at TEXT NOT NULL,
                finished_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS job_discovery_target_companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT NOT NULL,
                ats_provider TEXT NOT NULL,
                ats_identifier TEXT NOT NULL,
                careers_url TEXT,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(ats_provider, ats_identifier)
            );

            CREATE TABLE IF NOT EXISTS job_discovery_hide_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_type TEXT NOT NULL,
                operator TEXT NOT NULL,
                value TEXT NOT NULL,
                normalized_value TEXT NOT NULL,
                label TEXT,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(rule_type, operator, normalized_value)
            );

            CREATE INDEX IF NOT EXISTS idx_job_discovery_targets_provider
            ON job_discovery_target_companies(ats_provider, enabled, company_name);

            CREATE INDEX IF NOT EXISTS idx_job_discovery_hide_rules
            ON job_discovery_hide_rules(enabled, rule_type, normalized_value);

            CREATE INDEX IF NOT EXISTS idx_discovered_jobs_last_seen
            ON discovered_jobs(last_seen_at DESC);
            CREATE INDEX IF NOT EXISTS idx_discovered_jobs_source
            ON discovered_jobs(source, last_seen_at DESC);
            CREATE INDEX IF NOT EXISTS idx_discovery_runs_finished
            ON job_discovery_runs(finished_at DESC);
            """
        )
        _ensure_column(connection, "discovered_jobs", "source_scope", "TEXT")
        _ensure_column(
            connection,
            "discovered_jobs",
            "lifecycle_status",
            "TEXT NOT NULL DEFAULT 'active'",
        )
        _ensure_column(
            connection,
            "discovered_jobs",
            "last_event",
            "TEXT NOT NULL DEFAULT 'unchanged'",
        )
        _ensure_column(connection, "discovered_jobs", "last_changed_at", "TEXT")
        _ensure_column(connection, "discovered_jobs", "removed_at", "TEXT")
        _ensure_column(
            connection,
            "job_discovery_runs",
            "reactivated_count",
            "INTEGER NOT NULL DEFAULT 0",
        )
        _ensure_column(
            connection,
            "job_discovery_runs",
            "removed_count",
            "INTEGER NOT NULL DEFAULT 0",
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_discovered_jobs_scope_status
            ON discovered_jobs(source_scope, lifecycle_status, last_seen_at DESC)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_discovered_jobs_lifecycle
            ON discovered_jobs(lifecycle_status, last_event, last_seen_at DESC)
            """
        )
        connection.commit()
    finally:
        connection.close()


def upsert_discovered_jobs(
    jobs: Iterable[NormalizedJob],
    *,
    source_scope: str = "",
) -> dict[str, int]:
    """Upsert normalized jobs while tracking lifecycle events.

    `source_scope` identifies an authoritative source slice such as
    ``greenhouse:company-board``. Existing V1/V1.1 rows are migrated lazily:
    they receive a scope the next time they are actually observed.
    """
    init_job_discovery_schema()
    now = _now()
    scope = str(source_scope or "").strip()
    stats = {"new": 0, "changed": 0, "unchanged": 0, "reactivated": 0}
    connection = _connect()
    try:
        for job in jobs:
            job.validate()
            existing = connection.execute(
                """
                SELECT id, content_hash, first_seen_at, lifecycle_status
                FROM discovered_jobs
                WHERE source = ? AND source_job_id = ?
                """,
                (job.source, job.source_job_id),
            ).fetchone()
            content_hash = job.content_hash
            raw_json = json.dumps(job.raw_payload, ensure_ascii=False, default=str)
            connection.execute(
                """
                INSERT OR IGNORE INTO job_discovery_raw_records (
                    source, source_job_id, content_hash, fetched_at, payload_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (job.source, job.source_job_id, content_hash, now, raw_json),
            )

            if existing is None:
                stats["new"] += 1
                first_seen = now
                last_event = "new"
                last_changed_at = now
            else:
                first_seen = str(existing["first_seen_at"] or now)
                previous_status = str(existing["lifecycle_status"] or "active").lower()
                if previous_status in {"removed", "expired"}:
                    stats["reactivated"] += 1
                    last_event = "reactivated"
                    last_changed_at = now
                elif str(existing["content_hash"] or "") == content_hash:
                    stats["unchanged"] += 1
                    last_event = "unchanged"
                    changed_row = connection.execute(
                        "SELECT last_changed_at FROM discovered_jobs WHERE id = ?",
                        (int(existing["id"]),),
                    ).fetchone()
                    last_changed_at = (
                        str(changed_row["last_changed_at"])
                        if changed_row is not None and changed_row["last_changed_at"]
                        else None
                    )
                else:
                    stats["changed"] += 1
                    last_event = "changed"
                    last_changed_at = now

            connection.execute(
                """
                INSERT INTO discovered_jobs (
                    source, source_job_id, source_platform, title, company,
                    location, description, source_url, apply_url, posted_at,
                    expires_at, salary_min, salary_max, salary_currency,
                    salary_period, employment_type, seniority,
                    experience_years_min, experience_years_max, content_hash,
                    raw_payload_json, source_scope, lifecycle_status, last_event,
                    first_seen_at, last_seen_at, last_changed_at, removed_at, updated_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, 'active', ?, ?, ?, ?, NULL, ?
                )
                ON CONFLICT(source, source_job_id) DO UPDATE SET
                    source_platform = excluded.source_platform,
                    title = excluded.title,
                    company = excluded.company,
                    location = excluded.location,
                    description = excluded.description,
                    source_url = excluded.source_url,
                    apply_url = excluded.apply_url,
                    posted_at = excluded.posted_at,
                    expires_at = excluded.expires_at,
                    salary_min = excluded.salary_min,
                    salary_max = excluded.salary_max,
                    salary_currency = excluded.salary_currency,
                    salary_period = excluded.salary_period,
                    employment_type = excluded.employment_type,
                    seniority = excluded.seniority,
                    experience_years_min = excluded.experience_years_min,
                    experience_years_max = excluded.experience_years_max,
                    content_hash = excluded.content_hash,
                    raw_payload_json = excluded.raw_payload_json,
                    source_scope = CASE
                        WHEN excluded.source_scope <> '' THEN excluded.source_scope
                        ELSE discovered_jobs.source_scope
                    END,
                    lifecycle_status = 'active',
                    last_event = excluded.last_event,
                    last_seen_at = excluded.last_seen_at,
                    last_changed_at = COALESCE(
                        excluded.last_changed_at,
                        discovered_jobs.last_changed_at
                    ),
                    removed_at = NULL,
                    updated_at = excluded.updated_at
                """,
                (
                    job.source,
                    job.source_job_id,
                    job.source_platform,
                    job.title,
                    job.company,
                    job.location,
                    job.description,
                    job.source_url,
                    job.apply_url,
                    job.posted_at,
                    job.expires_at,
                    job.salary_min,
                    job.salary_max,
                    job.salary_currency,
                    job.salary_period,
                    job.employment_type,
                    job.seniority,
                    job.experience_years_min,
                    job.experience_years_max,
                    content_hash,
                    raw_json,
                    scope,
                    last_event,
                    first_seen,
                    now,
                    last_changed_at,
                    now,
                ),
            )
        connection.commit()
        return stats
    finally:
        connection.close()

def record_discovery_run(
    *,
    source_key: str,
    query: str,
    status: str,
    fetched_count: int,
    new_count: int = 0,
    changed_count: int = 0,
    unchanged_count: int = 0,
    reactivated_count: int = 0,
    removed_count: int = 0,
    error_text: str = "",
    started_at: str,
    finished_at: str | None = None,
) -> None:
    init_job_discovery_schema()
    connection = _connect()
    try:
        connection.execute(
            """
            INSERT INTO job_discovery_runs (
                source_key, query, status, fetched_count, new_count,
                changed_count, unchanged_count, reactivated_count, removed_count,
                error_text, started_at, finished_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_key,
                query,
                status,
                int(fetched_count),
                int(new_count),
                int(changed_count),
                int(unchanged_count),
                int(reactivated_count),
                int(removed_count),
                str(error_text or ""),
                started_at,
                finished_at or _now(),
            ),
        )
        connection.commit()
    finally:
        connection.close()

def list_discovered_jobs(
    *,
    sources: list[str] | None = None,
    limit: int = 250,
) -> list[dict[str, Any]]:
    init_job_discovery_schema()
    connection = _connect()
    try:
        params: list[Any] = []
        where = ""
        if sources:
            placeholders = ",".join("?" for _ in sources)
            where = f"WHERE source IN ({placeholders})"
            params.extend(sources)
        params.append(max(1, int(limit)))
        rows = connection.execute(
            f"""
            SELECT *
            FROM discovered_jobs
            {where}
            ORDER BY last_seen_at DESC, id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()




def list_discovered_jobs_by_scope(source_scope: str) -> list[dict[str, Any]]:
    """Return every stored row for one authoritative source/company scope."""
    init_job_discovery_schema()
    scope = str(source_scope or "").strip()
    if not scope:
        return []
    connection = _connect()
    try:
        rows = connection.execute(
            """
            SELECT *
            FROM discovered_jobs
            WHERE source_scope = ?
            ORDER BY source_job_id
            """,
            (scope,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def get_latest_successful_discovery_run(source_key: str) -> dict[str, Any] | None:
    """Return the latest successful refresh for a concrete source scope."""
    init_job_discovery_schema()
    key = str(source_key or "").strip()
    if not key:
        return None
    connection = _connect()
    try:
        row = connection.execute(
            """
            SELECT *
            FROM job_discovery_runs
            WHERE source_key = ? AND status = 'ok'
            ORDER BY finished_at DESC, id DESC
            LIMIT 1
            """,
            (key,),
        ).fetchone()
        return dict(row) if row is not None else None
    finally:
        connection.close()

def get_discovered_job(job_id: int) -> dict[str, Any] | None:
    init_job_discovery_schema()
    connection = _connect()
    try:
        row = connection.execute(
            "SELECT * FROM discovered_jobs WHERE id = ?",
            (int(job_id),),
        ).fetchone()
        return dict(row) if row is not None else None
    finally:
        connection.close()


def get_job_discovery_source_counts() -> list[dict[str, Any]]:
    init_job_discovery_schema()
    connection = _connect()
    try:
        rows = connection.execute(
            """
            SELECT source, COUNT(*) AS job_count, MAX(last_seen_at) AS last_seen_at
            FROM discovered_jobs
            GROUP BY source
            ORDER BY source
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def get_recent_discovery_runs(limit: int = 25) -> list[dict[str, Any]]:
    init_job_discovery_schema()
    connection = _connect()
    try:
        rows = connection.execute(
            """
            SELECT *
            FROM job_discovery_runs
            ORDER BY finished_at DESC, id DESC
            LIMIT ?
            """,
            (max(1, int(limit)),),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def mark_missing_jobs_removed(
    *,
    source_scope: str,
    seen_source_job_ids: Iterable[str],
) -> int:
    """Mark scoped jobs as removed only after an authoritative complete snapshot.

    Rows from V1/V1.1 that do not yet have a source_scope are intentionally ignored
    until they are observed again, preventing a migration refresh from falsely
    removing historical records.
    """
    init_job_discovery_schema()
    scope = str(source_scope or "").strip()
    if not scope:
        return 0
    seen = {
        str(value or "").strip()
        for value in seen_source_job_ids
        if str(value or "").strip()
    }
    now = _now()
    connection = _connect()
    try:
        params: list[Any] = [now, now, scope]
        not_in = ""
        if seen:
            placeholders = ",".join("?" for _ in seen)
            not_in = f"AND source_job_id NOT IN ({placeholders})"
            params.extend(sorted(seen))
        cursor = connection.execute(
            f"""
            UPDATE discovered_jobs
            SET lifecycle_status = 'removed',
                last_event = 'removed',
                removed_at = ?,
                updated_at = ?
            WHERE source_scope = ?
              AND lifecycle_status <> 'removed'
              {not_in}
            """,
            params,
        )
        connection.commit()
        return max(0, int(cursor.rowcount or 0))
    finally:
        connection.close()


def _parse_datetime(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        if raw.isdigit() and len(raw) >= 12:
            return datetime.fromtimestamp(float(raw) / 1000.0, tz=timezone.utc)
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (ValueError, OSError, OverflowError):
        return None


def mark_expired_jobs(*, now: datetime | None = None) -> int:
    """Mark active jobs expired when their explicit expiry timestamp has passed."""
    init_job_discovery_schema()
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    connection = _connect()
    try:
        rows = connection.execute(
            """
            SELECT id, expires_at
            FROM discovered_jobs
            WHERE lifecycle_status = 'active'
              AND expires_at IS NOT NULL
              AND TRIM(expires_at) <> ''
            """
        ).fetchall()
        expired_ids = [
            int(row["id"])
            for row in rows
            if (_parse_datetime(row["expires_at"]) is not None)
            and _parse_datetime(row["expires_at"]) <= current
        ]
        if not expired_ids:
            return 0
        placeholders = ",".join("?" for _ in expired_ids)
        stamp = current.isoformat(timespec="seconds")
        cursor = connection.execute(
            f"""
            UPDATE discovered_jobs
            SET lifecycle_status = 'expired',
                last_event = 'expired',
                removed_at = COALESCE(removed_at, ?),
                updated_at = ?
            WHERE id IN ({placeholders})
            """,
            [stamp, stamp, *expired_ids],
        )
        connection.commit()
        return max(0, int(cursor.rowcount or 0))
    finally:
        connection.close()


def get_job_discovery_lifecycle_counts() -> list[dict[str, Any]]:
    init_job_discovery_schema()
    connection = _connect()
    try:
        rows = connection.execute(
            """
            SELECT lifecycle_status, last_event, COUNT(*) AS job_count
            FROM discovered_jobs
            GROUP BY lifecycle_status, last_event
            ORDER BY lifecycle_status, last_event
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


ATS_PROVIDERS = ("greenhouse", "lever", "ashby", "smartrecruiters")


def _validate_ats_provider(value: str) -> str:
    provider = str(value or "").strip().lower()
    if provider not in ATS_PROVIDERS:
        raise ValueError(
            "ats_provider must be one of: " + ", ".join(ATS_PROVIDERS)
        )
    return provider


def normalize_target_identifier(ats_provider: str, value: str) -> str:
    """Normalize a board/site identifier, accepting either a token or careers URL."""
    provider = _validate_ats_provider(ats_provider)
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("ats_identifier cannot be empty.")

    known_hosts = {
        "greenhouse": (
            "boards.greenhouse.io",
            "job-boards.greenhouse.io",
            "boards-api.greenhouse.io",
        ),
        "lever": ("jobs.lever.co", "api.lever.co"),
        "ashby": ("jobs.ashbyhq.com", "api.ashbyhq.com"),
        "smartrecruiters": (
            "careers.smartrecruiters.com",
            "api.smartrecruiters.com",
        ),
    }

    candidate = raw
    lowered = raw.lower()
    if "://" not in candidate and any(
        lowered.startswith(host + "/") for host in known_hosts[provider]
    ):
        candidate = "https://" + candidate

    if "://" in candidate:
        parsed = urlparse(candidate)
        host = (parsed.hostname or "").lower()
        parts = [part for part in parsed.path.split("/") if part]
        if not parts:
            raise ValueError("The careers URL does not contain a board/site identifier.")

        # Careers URLs use the first path segment.
        if host in {
            "boards.greenhouse.io",
            "job-boards.greenhouse.io",
            "jobs.lever.co",
            "jobs.ashbyhq.com",
            "careers.smartrecruiters.com",
        }:
            return parts[0]

        # Also accept the public API URL shapes when users paste those directly.
        if provider == "greenhouse" and len(parts) >= 3 and parts[:2] == ["v1", "boards"]:
            return parts[2]
        if provider == "lever" and len(parts) >= 3 and parts[:2] == ["v0", "postings"]:
            return parts[2]
        if (
            provider == "ashby"
            and len(parts) >= 3
            and parts[:2] == ["posting-api", "job-board"]
        ):
            return parts[2]
        if (
            provider == "smartrecruiters"
            and len(parts) >= 3
            and parts[:2] == ["v1", "companies"]
        ):
            return parts[2]

        raise ValueError(
            f"Could not extract a {provider} identifier from that URL. "
            "Paste the provider careers URL or enter the identifier directly."
        )

    return raw.strip("/")


def upsert_target_company(
    *,
    company_name: str,
    ats_provider: str,
    ats_identifier: str,
    careers_url: str = "",
    enabled: bool = True,
) -> int:
    """Create or update a persistent ATS target and return its row id."""
    init_job_discovery_schema()
    provider = _validate_ats_provider(ats_provider)
    identifier = normalize_target_identifier(provider, ats_identifier)
    company = str(company_name or "").strip() or identifier
    url = str(careers_url or "").strip()
    if not url and "://" in str(ats_identifier or ""):
        url = str(ats_identifier or "").strip()
    now = _now()

    connection = _connect()
    try:
        connection.execute(
            """
            INSERT INTO job_discovery_target_companies (
                company_name, ats_provider, ats_identifier, careers_url,
                enabled, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ats_provider, ats_identifier) DO UPDATE SET
                company_name = excluded.company_name,
                careers_url = excluded.careers_url,
                enabled = excluded.enabled,
                updated_at = excluded.updated_at
            """,
            (
                company,
                provider,
                identifier,
                url,
                1 if enabled else 0,
                now,
                now,
            ),
        )
        row = connection.execute(
            """
            SELECT id
            FROM job_discovery_target_companies
            WHERE ats_provider = ? AND ats_identifier = ?
            """,
            (provider, identifier),
        ).fetchone()
        connection.commit()
        if row is None:
            raise RuntimeError("Target company was saved but could not be reloaded.")
        return int(row["id"])
    finally:
        connection.close()


def list_target_companies(
    *,
    include_disabled: bool = False,
    provider: str | None = None,
) -> list[dict[str, Any]]:
    init_job_discovery_schema()
    params: list[Any] = []
    where_parts: list[str] = []
    if not include_disabled:
        where_parts.append("enabled = 1")
    if provider:
        where_parts.append("ats_provider = ?")
        params.append(_validate_ats_provider(provider))
    where = "WHERE " + " AND ".join(where_parts) if where_parts else ""

    connection = _connect()
    try:
        rows = connection.execute(
            f"""
            SELECT *
            FROM job_discovery_target_companies
            {where}
            ORDER BY company_name COLLATE NOCASE, ats_provider, ats_identifier
            """,
            params,
        ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["enabled"] = bool(item.get("enabled"))
            result.append(item)
        return result
    finally:
        connection.close()


def set_target_company_enabled(target_id: int, enabled: bool) -> None:
    init_job_discovery_schema()
    connection = _connect()
    try:
        connection.execute(
            """
            UPDATE job_discovery_target_companies
            SET enabled = ?, updated_at = ?
            WHERE id = ?
            """,
            (1 if enabled else 0, _now(), int(target_id)),
        )
        connection.commit()
    finally:
        connection.close()


def delete_target_company(target_id: int) -> None:
    init_job_discovery_schema()
    connection = _connect()
    try:
        connection.execute(
            "DELETE FROM job_discovery_target_companies WHERE id = ?",
            (int(target_id),),
        )
        connection.commit()
    finally:
        connection.close()

_HIDE_RULE_OPERATORS = {
    "job": "exact",
    "company": "exact",
    "title_keyword": "contains",
    "description_keyword": "contains",
    "seniority_keyword": "contains",
    "employment_type_keyword": "contains",
    "experience_min_above": "greater_than",
}


def _normalize_hide_rule_value(rule_type: str, value: Any) -> tuple[str, str]:
    rule = str(rule_type or "").strip().lower()
    if rule not in _HIDE_RULE_OPERATORS:
        raise ValueError(f"Unsupported hide rule type: {rule_type}")
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("Hide rule value cannot be blank.")
    if rule == "experience_min_above":
        try:
            number = float(raw)
        except ValueError as exc:
            raise ValueError("Experience threshold must be a number.") from exc
        if number < 0:
            raise ValueError("Experience threshold cannot be negative.")
        normalized = f"{number:g}"
    else:
        normalized = " ".join(raw.casefold().split())
    return raw, normalized


def upsert_hide_rule(
    *,
    rule_type: str,
    value: Any,
    label: str = "",
    enabled: bool = True,
) -> int:
    """Create or re-enable a deterministic Job Finder hide rule."""
    init_job_discovery_schema()
    rule = str(rule_type or "").strip().lower()
    operator = _HIDE_RULE_OPERATORS.get(rule)
    if operator is None:
        raise ValueError(f"Unsupported hide rule type: {rule_type}")
    raw, normalized = _normalize_hide_rule_value(rule, value)
    now = _now()
    connection = _connect()
    try:
        connection.execute(
            """
            INSERT INTO job_discovery_hide_rules (
                rule_type, operator, value, normalized_value, label,
                enabled, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(rule_type, operator, normalized_value) DO UPDATE SET
                value = excluded.value,
                label = CASE
                    WHEN excluded.label <> '' THEN excluded.label
                    ELSE job_discovery_hide_rules.label
                END,
                enabled = excluded.enabled,
                updated_at = excluded.updated_at
            """,
            (
                rule,
                operator,
                raw,
                normalized,
                str(label or "").strip(),
                1 if enabled else 0,
                now,
                now,
            ),
        )
        row = connection.execute(
            """
            SELECT id
            FROM job_discovery_hide_rules
            WHERE rule_type = ? AND operator = ? AND normalized_value = ?
            """,
            (rule, operator, normalized),
        ).fetchone()
        connection.commit()
        if row is None:
            raise RuntimeError("Hide rule was saved but could not be reloaded.")
        return int(row["id"])
    finally:
        connection.close()


def list_hide_rules(*, include_disabled: bool = False) -> list[dict[str, Any]]:
    init_job_discovery_schema()
    connection = _connect()
    try:
        where = "" if include_disabled else "WHERE enabled = 1"
        rows = connection.execute(
            f"""
            SELECT *
            FROM job_discovery_hide_rules
            {where}
            ORDER BY enabled DESC, rule_type, normalized_value, id
            """
        ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["enabled"] = bool(item.get("enabled"))
            result.append(item)
        return result
    finally:
        connection.close()


def set_hide_rule_enabled(rule_id: int, enabled: bool) -> None:
    init_job_discovery_schema()
    connection = _connect()
    try:
        connection.execute(
            """
            UPDATE job_discovery_hide_rules
            SET enabled = ?, updated_at = ?
            WHERE id = ?
            """,
            (1 if enabled else 0, _now(), int(rule_id)),
        )
        connection.commit()
    finally:
        connection.close()


def delete_hide_rule(rule_id: int) -> None:
    init_job_discovery_schema()
    connection = _connect()
    try:
        connection.execute(
            "DELETE FROM job_discovery_hide_rules WHERE id = ?",
            (int(rule_id),),
        )
        connection.commit()
    finally:
        connection.close()


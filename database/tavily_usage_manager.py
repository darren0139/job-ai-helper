"""Persistent local Tavily usage ledger for Job AI Helper.

This ledger is intentionally installation-local. It tracks only Tavily calls
made by this Job AI Helper checkout/process through the live adapter. It is not
an authoritative Tavily account balance and cannot see calls made elsewhere.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ENV_DB_PATH = "TAVILY_USAGE_DB"
_ENV_MONTHLY_BUDGET = "TAVILY_MONTHLY_CREDIT_BUDGET"


def _repo_identity() -> str:
    root = Path(__file__).resolve().parents[1]
    raw = str(root).replace("\\", "/").lower().encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:12]


def default_tavily_usage_db_path() -> Path:
    override = str(os.environ.get(_ENV_DB_PATH) or "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return (
        Path.home()
        / ".job-ai-helper"
        / f"tavily_usage_{_repo_identity()}.sqlite3"
    )


def _resolved_path(
    db_path: str | os.PathLike[str] | None = None,
) -> Path:
    return (
        Path(db_path).expanduser().resolve()
        if db_path is not None
        else default_tavily_usage_db_path()
    )


def _connect(
    db_path: str | os.PathLike[str] | None = None,
    *,
    create_parent: bool,
) -> sqlite3.Connection:
    path = _resolved_path(db_path)
    if create_parent:
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def init_tavily_usage_schema(
    db_path: str | os.PathLike[str] | None = None,
) -> Path:
    path = _resolved_path(db_path)
    with closing(_connect(path, create_parent=True)) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS tavily_usage_events (
                event_id TEXT PRIMARY KEY,
                provider_request_id TEXT NOT NULL DEFAULT '',
                recorded_at TEXT NOT NULL,
                billing_month TEXT NOT NULL,
                provider TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                target_id TEXT NOT NULL DEFAULT '',
                target_type TEXT NOT NULL DEFAULT '',
                target_key TEXT NOT NULL DEFAULT '',
                target_label TEXT NOT NULL DEFAULT '',
                credits REAL NOT NULL DEFAULT 0,
                search_depth TEXT NOT NULL DEFAULT '',
                source_count INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_tavily_usage_billing_month
            ON tavily_usage_events (billing_month);
            """
        )
        conn.commit()
    return path


def _credits_from_result(result: dict[str, Any]) -> float:
    usage = result.get("usage")
    if not isinstance(usage, dict):
        return 0.0
    raw = usage.get("credits", 0)
    if isinstance(raw, bool):
        return 0.0
    if isinstance(raw, (int, float)):
        return max(0.0, float(raw))
    try:
        return max(0.0, float(str(raw).strip()))
    except (TypeError, ValueError):
        return 0.0


def _event_id(result: dict[str, Any]) -> str:
    request_id = str(result.get("provider_request_id") or "").strip()
    if request_id:
        return f"tavily:{request_id}"

    fingerprint_parts = (
        str(result.get("endpoint") or ""),
        str(result.get("target_id") or ""),
        str(result.get("provider_query") or result.get("query") or ""),
        str(result.get("provider_response_time") or ""),
        str(result.get("answer") or ""),
        str(result.get("source_count") or 0),
        str(_credits_from_result(result)),
    )
    digest = hashlib.sha256(
        "\n".join(fingerprint_parts).encode("utf-8")
    ).hexdigest()
    return f"tavily-fallback:{digest}"


def record_tavily_usage(
    result: dict[str, Any],
    *,
    db_path: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise TypeError("result must be a dictionary")

    provider = str(result.get("provider") or "").strip().lower()
    if provider != "tavily":
        raise ValueError("Only Tavily results can be recorded")

    now_local = datetime.now().astimezone()
    recorded_at = datetime.now(timezone.utc).isoformat()
    billing_month = now_local.strftime("%Y-%m")
    credits = _credits_from_result(result)
    source_count = int(result.get("source_count") or 0)
    status = (
        "sources_returned"
        if source_count > 0
        else "no_usable_sources"
    )
    event_id = _event_id(result)

    path = init_tavily_usage_schema(db_path)
    with closing(_connect(path, create_parent=True)) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO tavily_usage_events (
                event_id,
                provider_request_id,
                recorded_at,
                billing_month,
                provider,
                endpoint,
                target_id,
                target_type,
                target_key,
                target_label,
                credits,
                search_depth,
                source_count,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                str(result.get("provider_request_id") or ""),
                recorded_at,
                billing_month,
                provider,
                str(result.get("endpoint") or ""),
                str(result.get("target_id") or ""),
                str(result.get("target_type") or ""),
                str(result.get("target_key") or ""),
                str(result.get("target_label") or ""),
                credits,
                str(
                    (
                        (result.get("request") or {}).get("search_depth")
                        or (result.get("request") or {}).get("model")
                        or ""
                    )
                    if isinstance(result.get("request"), dict)
                    else ""
                ),
                source_count,
                status,
            ),
        )
        conn.commit()

    return {
        "event_id": event_id,
        "billing_month": billing_month,
        "credits": credits,
        "status": status,
        "scope": "local_job_ai_helper_installation",
    }


def current_month_usage_summary(
    *,
    db_path: str | os.PathLike[str] | None = None,
    billing_month: str | None = None,
) -> dict[str, Any]:
    month = (
        str(billing_month).strip()
        if billing_month is not None
        else datetime.now().astimezone().strftime("%Y-%m")
    )
    path = _resolved_path(db_path)
    if not path.exists():
        return {
            "billing_month": month,
            "credits": 0.0,
            "call_count": 0,
            "zero_credit_call_count": 0,
            "source_returning_call_count": 0,
        }

    with closing(_connect(path, create_parent=False)) as conn:
        try:
            row = conn.execute(
                """
                SELECT
                    COALESCE(SUM(credits), 0) AS credits,
                    COUNT(*) AS call_count,
                    SUM(CASE WHEN credits = 0 THEN 1 ELSE 0 END)
                        AS zero_credit_call_count,
                    SUM(CASE WHEN source_count > 0 THEN 1 ELSE 0 END)
                        AS source_returning_call_count
                FROM tavily_usage_events
                WHERE billing_month = ?
                """,
                (month,),
            ).fetchone()
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower():
                return {
                    "billing_month": month,
                    "credits": 0.0,
                    "call_count": 0,
                    "zero_credit_call_count": 0,
                    "source_returning_call_count": 0,
                }
            raise

    return {
        "billing_month": month,
        "credits": float(row["credits"] or 0),
        "call_count": int(row["call_count"] or 0),
        "zero_credit_call_count": int(
            row["zero_credit_call_count"] or 0
        ),
        "source_returning_call_count": int(
            row["source_returning_call_count"] or 0
        ),
    }


def tavily_monthly_credit_budget() -> float | None:
    raw = str(os.environ.get(_ENV_MONTHLY_BUDGET) or "").strip()
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if value > 0 else None

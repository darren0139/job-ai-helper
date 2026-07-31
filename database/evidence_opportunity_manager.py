"""SQLite persistence for Phase 9A Evidence Opportunity Analysis."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from typing import Any

from database import tailoring_version_manager as base_manager


def _connect() -> sqlite3.Connection:
    connection = base_manager._connect()
    connection.row_factory = sqlite3.Row
    return connection


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def init_evidence_opportunity_analysis() -> None:
    connection = _connect()
    cursor = connection.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS application_evidence_opportunities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            opportunity_id TEXT NOT NULL,
            opportunity_fingerprint TEXT NOT NULL,
            result_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(application_id, opportunity_id)
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_evidence_opportunity_lookup
        ON application_evidence_opportunities (
            application_id,
            opportunity_fingerprint
        )
        """
    )
    connection.commit()
    connection.close()


def _row_result(row: sqlite3.Row) -> dict[str, Any]:
    result = json.loads(str(row["result_json"] or "{}"))
    result.setdefault(
        "opportunity_id",
        str(row["opportunity_id"]),
    )
    result.setdefault("created_at", str(row["created_at"]))
    return result


def save_evidence_opportunity(
    *,
    application_id: int,
    result: dict[str, Any],
) -> dict[str, Any]:
    init_evidence_opportunity_analysis()
    fingerprint = str(
        result.get("opportunity_fingerprint") or ""
    ).strip()
    if not fingerprint:
        raise ValueError("opportunity_fingerprint is required.")

    connection = _connect()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT *
        FROM application_evidence_opportunities
        WHERE application_id = ?
          AND opportunity_fingerprint = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (int(application_id), fingerprint),
    )
    existing = cursor.fetchone()
    if existing is not None:
        connection.close()
        saved = _row_result(existing)
        saved["cache_status"] = "hit"
        return saved

    opportunity_id = uuid.uuid4().hex
    created_at = _now()
    stored = {
        **result,
        "opportunity_id": opportunity_id,
        "created_at": created_at,
    }
    cursor.execute(
        """
        INSERT INTO application_evidence_opportunities (
            application_id,
            opportunity_id,
            opportunity_fingerprint,
            result_json,
            created_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            int(application_id),
            opportunity_id,
            fingerprint,
            json.dumps(
                stored,
                ensure_ascii=False,
                default=str,
            ),
            created_at,
        ),
    )
    connection.commit()
    connection.close()
    stored["cache_status"] = "miss"
    return stored


def get_latest_evidence_opportunity(
    application_id: int,
) -> dict[str, Any] | None:
    init_evidence_opportunity_analysis()
    connection = _connect()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT *
        FROM application_evidence_opportunities
        WHERE application_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (int(application_id),),
    )
    row = cursor.fetchone()
    connection.close()
    return _row_result(row) if row is not None else None


def delete_application_evidence_opportunities(
    application_id: int,
) -> int:
    init_evidence_opportunity_analysis()
    connection = _connect()
    cursor = connection.cursor()
    cursor.execute(
        """
        DELETE FROM application_evidence_opportunities
        WHERE application_id = ?
        """,
        (int(application_id),),
    )
    deleted = max(0, int(cursor.rowcount or 0))
    connection.commit()
    connection.close()
    return deleted

"""Persistence for Phase 8 before/after verification results."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from typing import Any

from database import tailoring_version_manager as base_manager
from tailoring.phase8_verification import PHASE8_VERIFICATION_VERSION


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    connection = base_manager._connect()
    connection.row_factory = sqlite3.Row
    return connection


def init_tailoring_verifications() -> None:
    connection = _connect()
    cursor = connection.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS application_tailoring_verifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            verification_id TEXT NOT NULL,
            generation_id TEXT NOT NULL,
            phase8_version TEXT NOT NULL,
            verification_mode TEXT NOT NULL,
            verification_fingerprint TEXT NOT NULL,
            result_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(application_id, verification_id)
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_tailoring_verification_generation
        ON application_tailoring_verifications (
            application_id,
            generation_id,
            created_at DESC
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_tailoring_verification_fingerprint
        ON application_tailoring_verifications (
            application_id,
            generation_id,
            verification_fingerprint
        )
        """
    )
    connection.commit()
    connection.close()


def _row_to_result(row: sqlite3.Row) -> dict[str, Any]:
    result = json.loads(str(row["result_json"] or "{}"))
    result.setdefault("verification_id", str(row["verification_id"]))
    result.setdefault("created_at", str(row["created_at"]))
    return result


def save_tailoring_verification(
    *,
    application_id: int,
    generation_id: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Save once per exact verification fingerprint."""
    init_tailoring_verifications()
    fingerprint = str(
        result.get("verification_fingerprint") or ""
    ).strip()
    if not fingerprint:
        raise ValueError("verification_fingerprint is required.")

    connection = _connect()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT *
        FROM application_tailoring_verifications
        WHERE application_id = ?
          AND generation_id = ?
          AND verification_fingerprint = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (
            int(application_id),
            str(generation_id),
            fingerprint,
        ),
    )
    existing = cursor.fetchone()
    if existing is not None:
        existing_result = _row_to_result(existing)
        stored = {
            **existing_result,
            **result,
            "verification_id": str(existing["verification_id"]),
            "created_at": str(existing["created_at"]),
        }

        comparable_existing = dict(existing_result)
        comparable_existing.pop("cache_status", None)
        comparable_stored = dict(stored)
        comparable_stored.pop("cache_status", None)
        changed = comparable_existing != comparable_stored

        if changed:
            cursor.execute(
                """
                UPDATE application_tailoring_verifications
                SET result_json = ?,
                    phase8_version = ?,
                    verification_mode = ?
                WHERE id = ?
                """,
                (
                    json.dumps(
                        stored,
                        ensure_ascii=False,
                        default=str,
                    ),
                    str(
                        stored.get("phase8_version")
                        or PHASE8_VERIFICATION_VERSION
                    ),
                    str(
                        stored.get("verification_mode")
                        or "zero_cost_deterministic"
                    ),
                    int(existing["id"]),
                ),
            )
            connection.commit()

        connection.close()
        stored["cache_status"] = (
            "hit_refreshed"
            if changed
            else "hit"
        )
        return stored

    verification_id = uuid.uuid4().hex
    created_at = _now()
    stored = {
        **result,
        "verification_id": verification_id,
        "created_at": created_at,
    }
    cursor.execute(
        """
        INSERT INTO application_tailoring_verifications (
            application_id,
            verification_id,
            generation_id,
            phase8_version,
            verification_mode,
            verification_fingerprint,
            result_json,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(application_id),
            verification_id,
            str(generation_id),
            str(
                result.get("phase8_version")
                or PHASE8_VERIFICATION_VERSION
            ),
            str(
                result.get("verification_mode")
                or "zero_cost_deterministic"
            ),
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


def get_latest_tailoring_verification(
    application_id: int,
    generation_id: str,
) -> dict[str, Any] | None:
    init_tailoring_verifications()
    connection = _connect()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT *
        FROM application_tailoring_verifications
        WHERE application_id = ?
          AND generation_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (int(application_id), str(generation_id)),
    )
    row = cursor.fetchone()
    connection.close()
    return _row_to_result(row) if row is not None else None


def list_tailoring_verifications(
    application_id: int,
) -> list[dict[str, Any]]:
    init_tailoring_verifications()
    connection = _connect()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT *
        FROM application_tailoring_verifications
        WHERE application_id = ?
        ORDER BY created_at DESC, id DESC
        """,
        (int(application_id),),
    )
    rows = cursor.fetchall()
    connection.close()
    return [_row_to_result(row) for row in rows]


def delete_application_tailoring_verifications(
    application_id: int,
) -> int:
    init_tailoring_verifications()
    connection = _connect()
    cursor = connection.cursor()
    cursor.execute(
        """
        DELETE FROM application_tailoring_verifications
        WHERE application_id = ?
        """,
        (int(application_id),),
    )
    deleted = max(0, int(cursor.rowcount or 0))
    connection.commit()
    connection.close()
    return deleted

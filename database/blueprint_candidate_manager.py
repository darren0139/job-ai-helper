"""Global Blueprint Candidate registry for Phase 9B."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from typing import Any

from database import tailoring_version_manager as base_manager


_MUTABLE_METADATA_FIELDS = (
    "candidate_name",
    "notes",
    "candidate_metadata",
)


def _connect() -> sqlite3.Connection:
    connection = base_manager._connect()
    connection.row_factory = sqlite3.Row
    return connection


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def init_blueprint_candidate_registry() -> None:
    connection = _connect()
    cursor = connection.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS global_blueprint_candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id TEXT NOT NULL UNIQUE,
            candidate_fingerprint TEXT NOT NULL UNIQUE,
            source_application_id INTEGER NOT NULL,
            source_generation_id TEXT NOT NULL,
            role_family TEXT NOT NULL,
            candidate_name TEXT NOT NULL,
            status TEXT NOT NULL,
            snapshot_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_blueprint_candidate_role
        ON global_blueprint_candidates (
            role_family,
            status,
            updated_at DESC
        )
        """
    )
    connection.commit()
    connection.close()


def _row_to_candidate(row: sqlite3.Row) -> dict[str, Any]:
    snapshot = json.loads(str(row["snapshot_json"] or "{}"))
    snapshot.setdefault(
        "candidate_id",
        str(row["candidate_id"]),
    )
    snapshot.setdefault("created_at", str(row["created_at"]))
    snapshot.setdefault("updated_at", str(row["updated_at"]))
    snapshot["status"] = str(row["status"])
    return snapshot


def _merge_mutable_metadata(
    existing: dict[str, Any],
    incoming: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    """Update human metadata without replacing immutable candidate content."""
    merged = dict(existing)
    changed = False
    for field in _MUTABLE_METADATA_FIELDS:
        if field not in incoming:
            continue
        incoming_value = incoming.get(field)
        if merged.get(field) != incoming_value:
            merged[field] = incoming_value
            changed = True
    return merged, changed


def save_blueprint_candidate(
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    init_blueprint_candidate_registry()
    fingerprint = str(
        snapshot.get("candidate_fingerprint") or ""
    ).strip()
    if not fingerprint:
        raise ValueError("candidate_fingerprint is required.")

    connection = _connect()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT *
        FROM global_blueprint_candidates
        WHERE candidate_fingerprint = ?
        LIMIT 1
        """,
        (fingerprint,),
    )
    existing = cursor.fetchone()
    if existing is not None:
        current = _row_to_candidate(existing)
        merged, metadata_changed = _merge_mutable_metadata(
            current,
            snapshot,
        )
        if metadata_changed:
            updated_at = _now()
            merged["candidate_id"] = str(existing["candidate_id"])
            merged["created_at"] = str(existing["created_at"])
            merged["updated_at"] = updated_at
            merged["status"] = str(existing["status"])
            cursor.execute(
                """
                UPDATE global_blueprint_candidates
                SET candidate_name = ?,
                    snapshot_json = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    str(merged.get("candidate_name") or ""),
                    json.dumps(
                        merged,
                        ensure_ascii=False,
                        default=str,
                    ),
                    updated_at,
                    int(existing["id"]),
                ),
            )
            connection.commit()
            connection.close()
            merged["cache_status"] = "hit_metadata_updated"
            return merged

        connection.close()
        current["cache_status"] = "hit"
        return current

    candidate_id = uuid.uuid4().hex
    created_at = _now()
    stored = {
        **snapshot,
        "candidate_id": candidate_id,
        "created_at": created_at,
        "updated_at": created_at,
    }
    cursor.execute(
        """
        INSERT INTO global_blueprint_candidates (
            candidate_id,
            candidate_fingerprint,
            source_application_id,
            source_generation_id,
            role_family,
            candidate_name,
            status,
            snapshot_json,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            candidate_id,
            fingerprint,
            int(snapshot["source_application_id"]),
            str(snapshot["source_generation_id"]),
            str(snapshot["role_family"]),
            str(snapshot["candidate_name"]),
            str(snapshot.get("status") or "candidate"),
            json.dumps(
                stored,
                ensure_ascii=False,
                default=str,
            ),
            created_at,
            created_at,
        ),
    )
    connection.commit()
    connection.close()
    stored["cache_status"] = "miss"
    return stored


def list_blueprint_candidates(
    *,
    role_family: str | None = None,
    include_archived: bool = False,
) -> list[dict[str, Any]]:
    init_blueprint_candidate_registry()
    connection = _connect()
    cursor = connection.cursor()

    clauses = []
    values: list[Any] = []
    if role_family and role_family.strip():
        clauses.append("role_family = ?")
        values.append(role_family.strip())
    if not include_archived:
        clauses.append("status != 'archived'")

    where = (
        "WHERE " + " AND ".join(clauses)
        if clauses
        else ""
    )
    cursor.execute(
        f"""
        SELECT *
        FROM global_blueprint_candidates
        {where}
        ORDER BY updated_at DESC, id DESC
        """,
        values,
    )
    rows = cursor.fetchall()
    connection.close()
    return [_row_to_candidate(row) for row in rows]


def get_blueprint_candidate(
    candidate_id: str,
) -> dict[str, Any] | None:
    init_blueprint_candidate_registry()
    connection = _connect()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT *
        FROM global_blueprint_candidates
        WHERE candidate_id = ?
        LIMIT 1
        """,
        (str(candidate_id),),
    )
    row = cursor.fetchone()
    connection.close()
    return _row_to_candidate(row) if row is not None else None


def archive_blueprint_candidate(candidate_id: str) -> bool:
    init_blueprint_candidate_registry()
    connection = _connect()
    cursor = connection.cursor()
    updated_at = _now()
    cursor.execute(
        """
        UPDATE global_blueprint_candidates
        SET status = 'archived',
            updated_at = ?
        WHERE candidate_id = ?
          AND status != 'archived'
        """,
        (updated_at, str(candidate_id)),
    )
    changed = int(cursor.rowcount or 0) > 0
    connection.commit()
    connection.close()
    return changed

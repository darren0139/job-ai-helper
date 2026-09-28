from __future__ import annotations

from contextlib import closing

import hashlib
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from taxonomy_discovery.triage import TRIAGE_STATUSES, TRIAGE_VERSION

_ENV_DB_PATH = "TAXONOMY_DISCOVERY_REVIEW_DB"


def _repo_identity() -> str:
    root = Path(__file__).resolve().parents[1]
    raw = str(root).replace("\\", "/").lower().encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:12]


def default_review_db_path() -> Path:
    override = str(os.environ.get(_ENV_DB_PATH) or "").strip()
    if override:
        return Path(override).expanduser().resolve()

    base = Path.home() / ".job-ai-helper"
    return base / f"taxonomy_discovery_reviews_{_repo_identity()}.sqlite3"


def _resolved_path(db_path: str | os.PathLike[str] | None = None) -> Path:
    return (
        Path(db_path).expanduser().resolve()
        if db_path is not None
        else default_review_db_path()
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


def init_review_schema(
    db_path: str | os.PathLike[str] | None = None,
) -> Path:
    path = _resolved_path(db_path)
    with closing(_connect(path, create_parent=True)) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS taxonomy_discovery_reviews (
                candidate_id TEXT NOT NULL,
                taxonomy_version TEXT NOT NULL,
                triage_version TEXT NOT NULL,
                triage_status TEXT NOT NULL,
                target_capability_id TEXT,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (candidate_id, taxonomy_version)
            )
            """
        )
        conn.commit()
    return path


def _decode(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "candidate_id": str(row["candidate_id"]),
        "taxonomy_version": str(row["taxonomy_version"]),
        "triage_version": str(row["triage_version"]),
        "triage_status": str(row["triage_status"]),
        "target_capability_id": (
            str(row["target_capability_id"])
            if row["target_capability_id"]
            else None
        ),
        "notes": str(row["notes"] or ""),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
    }


def list_reviews(
    *,
    taxonomy_version: str | None = None,
    db_path: str | os.PathLike[str] | None = None,
) -> list[dict[str, Any]]:
    path = _resolved_path(db_path)
    if not path.exists():
        return []

    sql = """
        SELECT
            candidate_id,
            taxonomy_version,
            triage_version,
            triage_status,
            target_capability_id,
            notes,
            created_at,
            updated_at
        FROM taxonomy_discovery_reviews
    """
    params: tuple[Any, ...] = ()
    if taxonomy_version:
        sql += " WHERE taxonomy_version = ?"
        params = (str(taxonomy_version),)
    sql += " ORDER BY candidate_id, taxonomy_version"

    with closing(_connect(path, create_parent=False)) as conn:
        try:
            rows = conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower():
                return []
            raise
    return [_decode(row) for row in rows]


def get_review(
    candidate_id: str,
    taxonomy_version: str,
    *,
    db_path: str | os.PathLike[str] | None = None,
) -> dict[str, Any] | None:
    path = _resolved_path(db_path)
    if not path.exists():
        return None

    with closing(_connect(path, create_parent=False)) as conn:
        try:
            row = conn.execute(
                """
                SELECT
                    candidate_id,
                    taxonomy_version,
                    triage_version,
                    triage_status,
                    target_capability_id,
                    notes,
                    created_at,
                    updated_at
                FROM taxonomy_discovery_reviews
                WHERE candidate_id = ? AND taxonomy_version = ?
                """,
                (str(candidate_id), str(taxonomy_version)),
            ).fetchone()
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower():
                return None
            raise
    return _decode(row) if row is not None else None


def save_review(
    *,
    candidate_id: str,
    taxonomy_version: str,
    triage_status: str,
    target_capability_id: str | None = None,
    notes: str = "",
    db_path: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    candidate_id = str(candidate_id or "").strip()
    taxonomy_version = str(taxonomy_version or "").strip()
    triage_status = str(triage_status or "").strip()
    target_capability_id = str(target_capability_id or "").strip() or None

    if not candidate_id:
        raise ValueError("candidate_id is required.")
    if not taxonomy_version:
        raise ValueError("taxonomy_version is required.")
    if triage_status not in TRIAGE_STATUSES:
        raise ValueError(
            f"Unsupported triage_status {triage_status!r}. "
            f"Expected one of: {', '.join(TRIAGE_STATUSES)}"
        )
    if (
        triage_status == "existing_taxonomy_near_miss"
        and not target_capability_id
    ):
        raise ValueError(
            "existing_taxonomy_near_miss requires target_capability_id."
        )

    path = init_review_schema(db_path)
    now = datetime.now(timezone.utc).isoformat()

    with closing(_connect(path, create_parent=True)) as conn:
        conn.execute(
            """
            INSERT INTO taxonomy_discovery_reviews (
                candidate_id,
                taxonomy_version,
                triage_version,
                triage_status,
                target_capability_id,
                notes,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(candidate_id, taxonomy_version)
            DO UPDATE SET
                triage_version = excluded.triage_version,
                triage_status = excluded.triage_status,
                target_capability_id = excluded.target_capability_id,
                notes = excluded.notes,
                updated_at = excluded.updated_at
            """,
            (
                candidate_id,
                taxonomy_version,
                TRIAGE_VERSION,
                triage_status,
                target_capability_id,
                str(notes or ""),
                now,
                now,
            ),
        )
        conn.commit()

    saved = get_review(
        candidate_id,
        taxonomy_version,
        db_path=path,
    )
    if saved is None:
        raise RuntimeError("Review was written but could not be reloaded.")
    return saved


def delete_review(
    candidate_id: str,
    taxonomy_version: str,
    *,
    db_path: str | os.PathLike[str] | None = None,
) -> bool:
    path = _resolved_path(db_path)
    if not path.exists():
        return False

    with closing(_connect(path, create_parent=False)) as conn:
        try:
            cursor = conn.execute(
                """
                DELETE FROM taxonomy_discovery_reviews
                WHERE candidate_id = ? AND taxonomy_version = ?
                """,
                (str(candidate_id), str(taxonomy_version)),
            )
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower():
                return False
            raise
        conn.commit()
        return bool(cursor.rowcount)

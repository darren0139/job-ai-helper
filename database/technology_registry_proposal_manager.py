"""Persistent imported research proposals and human decisions for TQ-D2.7."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from taxonomy_discovery.research_proposals import (
    PROPOSAL_REVIEW_DECISIONS,
    validate_proposal_bundle,
)

_ENV_DB_PATH = "TECHNOLOGY_REGISTRY_PROPOSAL_DB"


def _repo_identity() -> str:
    root = Path(__file__).resolve().parents[1]
    raw = str(root).replace("\\", "/").lower().encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:12]


def default_proposal_db_path() -> Path:
    override = str(os.environ.get(_ENV_DB_PATH) or "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return (
        Path.home()
        / ".job-ai-helper"
        / f"technology_registry_proposals_{_repo_identity()}.sqlite3"
    )


def _resolved_path(
    db_path: str | os.PathLike[str] | None = None,
) -> Path:
    return (
        Path(db_path).expanduser().resolve()
        if db_path is not None
        else default_proposal_db_path()
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


def init_proposal_schema(
    db_path: str | os.PathLike[str] | None = None,
) -> Path:
    path = _resolved_path(db_path)
    with closing(_connect(path, create_parent=True)) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS technology_registry_proposals (
                proposal_id TEXT NOT NULL,
                proposal_bundle_version TEXT NOT NULL,
                technology_id TEXT NOT NULL,
                label TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                source_fingerprint TEXT NOT NULL,
                imported_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (proposal_id, proposal_bundle_version)
            );

            CREATE TABLE IF NOT EXISTS technology_registry_proposal_reviews (
                proposal_id TEXT NOT NULL,
                proposal_bundle_version TEXT NOT NULL,
                decision TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (proposal_id, proposal_bundle_version)
            );
            """
        )
        conn.commit()
    return path


def import_proposal_bundle(
    bundle: dict[str, Any],
    *,
    db_path: str | os.PathLike[str] | None = None,
) -> int:
    cleaned = validate_proposal_bundle(bundle)
    path = init_proposal_schema(db_path)
    now = datetime.now(timezone.utc).isoformat()
    version = str(cleaned["proposal_bundle_version"])

    with closing(_connect(path, create_parent=True)) as conn:
        for proposal in cleaned["proposals"]:
            payload_json = json.dumps(
                proposal,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            fingerprint = hashlib.sha256(
                payload_json.encode("utf-8")
            ).hexdigest()

            existing = conn.execute(
                """
                SELECT source_fingerprint
                FROM technology_registry_proposals
                WHERE proposal_id = ?
                  AND proposal_bundle_version = ?
                """,
                (
                    proposal["proposal_id"],
                    version,
                ),
            ).fetchone()
            if (
                existing is not None
                and str(existing["source_fingerprint"])
                != fingerprint
            ):
                # A human decision is only valid for the exact researched
                # proposal content that was reviewed. Any changed source,
                # target, aliases, confidence, or summary invalidates the
                # previous decision and requires explicit re-review.
                conn.execute(
                    """
                    DELETE FROM technology_registry_proposal_reviews
                    WHERE proposal_id = ?
                      AND proposal_bundle_version = ?
                    """,
                    (
                        proposal["proposal_id"],
                        version,
                    ),
                )

            conn.execute(
                """
                INSERT INTO technology_registry_proposals (
                    proposal_id,
                    proposal_bundle_version,
                    technology_id,
                    label,
                    payload_json,
                    source_fingerprint,
                    imported_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (
                    proposal_id,
                    proposal_bundle_version
                ) DO UPDATE SET
                    technology_id = excluded.technology_id,
                    label = excluded.label,
                    payload_json = excluded.payload_json,
                    source_fingerprint = excluded.source_fingerprint,
                    updated_at = excluded.updated_at
                """,
                (
                    proposal["proposal_id"],
                    version,
                    proposal["technology_id"],
                    proposal["label"],
                    payload_json,
                    fingerprint,
                    now,
                    now,
                ),
            )
        conn.commit()

    return len(cleaned["proposals"])


def list_proposals(
    *,
    proposal_bundle_version: str | None = None,
    db_path: str | os.PathLike[str] | None = None,
) -> list[dict[str, Any]]:
    path = _resolved_path(db_path)
    if not path.exists():
        return []

    sql = """
        SELECT
            proposal_id,
            proposal_bundle_version,
            technology_id,
            label,
            payload_json,
            source_fingerprint,
            imported_at,
            updated_at
        FROM technology_registry_proposals
    """
    params: tuple[Any, ...] = ()
    if proposal_bundle_version:
        sql += " WHERE proposal_bundle_version = ?"
        params = (str(proposal_bundle_version),)
    sql += " ORDER BY label, proposal_id"

    with closing(_connect(path, create_parent=False)) as conn:
        try:
            rows = conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower():
                return []
            raise

    result: list[dict[str, Any]] = []
    for row in rows:
        payload = json.loads(str(row["payload_json"]))
        payload["proposal_bundle_version"] = str(
            row["proposal_bundle_version"]
        )
        payload["source_fingerprint"] = str(
            row["source_fingerprint"]
        )
        payload["imported_at"] = str(row["imported_at"])
        payload["updated_at"] = str(row["updated_at"])
        result.append(payload)
    return result


def list_proposal_reviews(
    *,
    proposal_bundle_version: str | None = None,
    db_path: str | os.PathLike[str] | None = None,
) -> list[dict[str, Any]]:
    path = _resolved_path(db_path)
    if not path.exists():
        return []

    sql = """
        SELECT
            proposal_id,
            proposal_bundle_version,
            decision,
            notes,
            created_at,
            updated_at
        FROM technology_registry_proposal_reviews
    """
    params: tuple[Any, ...] = ()
    if proposal_bundle_version:
        sql += " WHERE proposal_bundle_version = ?"
        params = (str(proposal_bundle_version),)
    sql += " ORDER BY proposal_id"

    with closing(_connect(path, create_parent=False)) as conn:
        try:
            rows = conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower():
                return []
            raise

    return [
        {
            "proposal_id": str(row["proposal_id"]),
            "proposal_bundle_version": str(
                row["proposal_bundle_version"]
            ),
            "decision": str(row["decision"]),
            "notes": str(row["notes"] or ""),
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
        }
        for row in rows
    ]


def save_proposal_review(
    *,
    proposal_id: str,
    proposal_bundle_version: str,
    decision: str,
    notes: str = "",
    db_path: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    decision = str(decision or "").strip()
    if decision not in PROPOSAL_REVIEW_DECISIONS:
        raise ValueError(
            f"Unsupported proposal review decision: {decision!r}"
        )

    path = init_proposal_schema(db_path)
    now = datetime.now(timezone.utc).isoformat()

    with closing(_connect(path, create_parent=True)) as conn:
        existing = conn.execute(
            """
            SELECT created_at
            FROM technology_registry_proposal_reviews
            WHERE proposal_id = ?
              AND proposal_bundle_version = ?
            """,
            (
                str(proposal_id),
                str(proposal_bundle_version),
            ),
        ).fetchone()
        created_at = (
            str(existing["created_at"])
            if existing is not None
            else now
        )

        conn.execute(
            """
            INSERT INTO technology_registry_proposal_reviews (
                proposal_id,
                proposal_bundle_version,
                decision,
                notes,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (
                proposal_id,
                proposal_bundle_version
            ) DO UPDATE SET
                decision = excluded.decision,
                notes = excluded.notes,
                updated_at = excluded.updated_at
            """,
            (
                str(proposal_id),
                str(proposal_bundle_version),
                decision,
                str(notes or ""),
                created_at,
                now,
            ),
        )
        conn.commit()

    return {
        "proposal_id": str(proposal_id),
        "proposal_bundle_version": str(
            proposal_bundle_version
        ),
        "decision": decision,
        "notes": str(notes or ""),
        "created_at": created_at,
        "updated_at": now,
    }

"""Additive immutable persistence for the Phase 9F global master resume."""

from __future__ import annotations

import json
import sqlite3
import uuid
from copy import deepcopy
from datetime import datetime
from typing import Any

from database import tailoring_version_manager as base_manager
from tailoring.phase9f_master_resume import (
    PHASE9F_MASTER_CONTENT_POLICY_VERSION,
    PHASE9F_MASTER_EVENT_VERSION,
    PHASE9F_MASTER_RESUME_VERSION,
    PHASE9F_MASTER_VERSION_POLICY_VERSION,
    Phase9FMasterResumeError,
    build_master_version_identity,
    canonical_json,
    fingerprint_value,
    sha256_bytes,
    sha256_text,
)


def _connect() -> sqlite3.Connection:
    connection = base_manager._connect()
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def init_global_master_resume_registry() -> None:
    """Create the additive Phase 9F-Master schema idempotently."""
    connection = _connect()
    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS global_master_resume_versions (
                master_version_id TEXT PRIMARY KEY,
                master_version_fingerprint TEXT NOT NULL UNIQUE,
                master_content_fingerprint TEXT NOT NULL,
                format_version TEXT NOT NULL,
                content_policy_version TEXT NOT NULL,
                version_policy_version TEXT NOT NULL,
                version_number INTEGER NOT NULL UNIQUE,
                predecessor_master_version_id TEXT,
                predecessor_master_version_fingerprint TEXT,
                artifact_sha256 TEXT NOT NULL,
                artifact_type TEXT NOT NULL,
                artifact_size_bytes INTEGER NOT NULL,
                original_filename TEXT NOT NULL,
                media_type TEXT NOT NULL,
                resume_text_sha256 TEXT NOT NULL,
                resume_text_char_count INTEGER NOT NULL,
                resume_text TEXT NOT NULL,
                structured_profile_fingerprint TEXT NOT NULL,
                structured_profile_json TEXT NOT NULL,
                semantic_identity_json TEXT NOT NULL,
                version_identity_json TEXT NOT NULL,
                extraction_provenance_json TEXT NOT NULL,
                master_snapshot_json TEXT NOT NULL,
                display_name TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_master_resume_artifact_sha
            ON global_master_resume_versions (artifact_sha256, version_number DESC);

            CREATE INDEX IF NOT EXISTS idx_master_resume_text_sha
            ON global_master_resume_versions (resume_text_sha256, version_number DESC);

            CREATE INDEX IF NOT EXISTS idx_master_resume_content_fingerprint
            ON global_master_resume_versions (
                master_content_fingerprint,
                version_number DESC
            );

            CREATE TABLE IF NOT EXISTS global_master_resume_artifacts (
                artifact_id TEXT PRIMARY KEY,
                master_version_id TEXT NOT NULL,
                artifact_kind TEXT NOT NULL CHECK (
                    artifact_kind IN ('original', 'preview_pdf')
                ),
                media_type TEXT NOT NULL,
                filename TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                byte_size INTEGER NOT NULL,
                authoritative INTEGER NOT NULL CHECK (authoritative IN (0, 1)),
                artifact_bytes BLOB NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE (master_version_id, artifact_kind),
                FOREIGN KEY (master_version_id)
                    REFERENCES global_master_resume_versions(master_version_id)
            );

            CREATE INDEX IF NOT EXISTS idx_master_resume_artifact_lookup
            ON global_master_resume_artifacts (sha256, artifact_kind);

            CREATE TABLE IF NOT EXISTS global_master_resume_state (
                singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
                current_master_version_id TEXT NOT NULL,
                current_master_version_fingerprint TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (current_master_version_id)
                    REFERENCES global_master_resume_versions(master_version_id)
            );

            CREATE TABLE IF NOT EXISTS global_master_resume_events (
                event_id TEXT PRIMARY KEY,
                event_fingerprint TEXT NOT NULL UNIQUE,
                event_version TEXT NOT NULL,
                event_type TEXT NOT NULL,
                master_version_id TEXT NOT NULL,
                master_version_fingerprint TEXT NOT NULL,
                previous_master_version_id TEXT,
                prepared_snapshot_fingerprint TEXT NOT NULL,
                actor_label TEXT NOT NULL,
                created_at TEXT NOT NULL,
                event_json TEXT NOT NULL,
                FOREIGN KEY (master_version_id)
                    REFERENCES global_master_resume_versions(master_version_id)
            );

            CREATE INDEX IF NOT EXISTS idx_master_resume_event_history
            ON global_master_resume_events (created_at DESC, event_id DESC);
            """
        )
        connection.commit()
    finally:
        connection.close()


def _safe_json(value: Any) -> dict[str, Any]:
    try:
        parsed = json.loads(str(value or "{}"))
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _row_to_master(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "master_version_id": str(row["master_version_id"]),
        "master_version_fingerprint": str(row["master_version_fingerprint"]),
        "master_content_fingerprint": str(row["master_content_fingerprint"]),
        "format_version": str(row["format_version"]),
        "content_policy_version": str(row["content_policy_version"]),
        "version_policy_version": str(row["version_policy_version"]),
        "version_number": int(row["version_number"]),
        "predecessor_master_version_id": str(
            row["predecessor_master_version_id"] or ""
        ),
        "predecessor_master_version_fingerprint": str(
            row["predecessor_master_version_fingerprint"] or ""
        ),
        "artifact_sha256": str(row["artifact_sha256"]),
        "artifact_type": str(row["artifact_type"]),
        "artifact_size_bytes": int(row["artifact_size_bytes"]),
        "original_filename": str(row["original_filename"]),
        "media_type": str(row["media_type"]),
        "resume_text_sha256": str(row["resume_text_sha256"]),
        "resume_text_char_count": int(row["resume_text_char_count"]),
        "resume_text": str(row["resume_text"]),
        "structured_profile_fingerprint": str(
            row["structured_profile_fingerprint"]
        ),
        "structured_profile": _safe_json(row["structured_profile_json"]),
        "semantic_identity": _safe_json(row["semantic_identity_json"]),
        "version_identity": _safe_json(row["version_identity_json"]),
        "extraction_provenance": _safe_json(
            row["extraction_provenance_json"]
        ),
        "master_snapshot": _safe_json(row["master_snapshot_json"]),
        "display_name": str(row["display_name"] or ""),
        "created_at": str(row["created_at"]),
    }


def _select_version(
    connection: sqlite3.Connection,
    master_version_id: str,
) -> dict[str, Any] | None:
    row = connection.execute(
        """
        SELECT * FROM global_master_resume_versions
        WHERE master_version_id = ?
        LIMIT 1
        """,
        (str(master_version_id),),
    ).fetchone()
    return _row_to_master(row) if row is not None else None


def get_current_global_master_resume() -> dict[str, Any] | None:
    """Return the authoritative current version without creating persistence."""
    connection = _connect()
    try:
        state = connection.execute(
            """
            SELECT current_master_version_id, current_master_version_fingerprint
            FROM global_master_resume_state
            WHERE singleton_id = 1
            LIMIT 1
            """
        ).fetchone()
        if state is None:
            return None
        row = connection.execute(
            """
            SELECT * FROM global_master_resume_versions
            WHERE master_version_id = ?
            LIMIT 1
            """,
            (str(state["current_master_version_id"]),),
        ).fetchone()
        if row is None:
            raise Phase9FMasterResumeError(
                "The global master-resume current pointer references a missing version."
            )
        master = _row_to_master(row)
        if str(master["master_version_fingerprint"]) != str(
            state["current_master_version_fingerprint"]
        ):
            raise Phase9FMasterResumeError(
                "The global master-resume current pointer is inconsistent."
            )
        return master
    finally:
        connection.close()


def get_global_master_resume(master_version_id: str) -> dict[str, Any] | None:
    connection = _connect()
    try:
        return _select_version(connection, master_version_id)
    finally:
        connection.close()


def list_global_master_resume_versions() -> list[dict[str, Any]]:
    connection = _connect()
    try:
        rows = connection.execute(
            """
            SELECT * FROM global_master_resume_versions
            ORDER BY version_number DESC
            """
        ).fetchall()
        return [_row_to_master(row) for row in rows]
    finally:
        connection.close()


def find_master_resume_by_artifact_sha256(
    artifact_sha256: str,
) -> dict[str, Any] | None:
    connection = _connect()
    try:
        row = connection.execute(
            """
            SELECT * FROM global_master_resume_versions
            WHERE artifact_sha256 = ?
            ORDER BY version_number DESC
            LIMIT 1
            """,
            (str(artifact_sha256 or ""),),
        ).fetchone()
        return _row_to_master(row) if row is not None else None
    finally:
        connection.close()


def find_master_resume_by_text_sha256(
    resume_text_sha256: str,
) -> dict[str, Any] | None:
    connection = _connect()
    try:
        row = connection.execute(
            """
            SELECT * FROM global_master_resume_versions
            WHERE resume_text_sha256 = ?
            ORDER BY version_number DESC
            LIMIT 1
            """,
            (str(resume_text_sha256 or ""),),
        ).fetchone()
        return _row_to_master(row) if row is not None else None
    finally:
        connection.close()


def get_global_master_resume_artifact(
    master_version_id: str,
    artifact_kind: str = "original",
) -> dict[str, Any] | None:
    if artifact_kind not in {"original", "preview_pdf"}:
        raise ValueError("Unknown master-resume artifact kind.")
    connection = _connect()
    try:
        row = connection.execute(
            """
            SELECT * FROM global_master_resume_artifacts
            WHERE master_version_id = ? AND artifact_kind = ?
            LIMIT 1
            """,
            (str(master_version_id), artifact_kind),
        ).fetchone()
        if row is None:
            return None
        content = bytes(row["artifact_bytes"])
        if len(content) != int(row["byte_size"]):
            raise Phase9FMasterResumeError(
                "The stored master-resume artifact size is inconsistent."
            )
        if sha256_bytes(content) != str(row["sha256"]):
            raise Phase9FMasterResumeError(
                "The stored master-resume artifact failed SHA-256 validation."
            )
        return {
            "artifact_id": str(row["artifact_id"]),
            "master_version_id": str(row["master_version_id"]),
            "artifact_kind": str(row["artifact_kind"]),
            "media_type": str(row["media_type"]),
            "filename": str(row["filename"]),
            "sha256": str(row["sha256"]),
            "byte_size": int(row["byte_size"]),
            "authoritative": bool(row["authoritative"]),
            "artifact_bytes": content,
            "created_at": str(row["created_at"]),
        }
    finally:
        connection.close()


def list_global_master_resume_events() -> list[dict[str, Any]]:
    connection = _connect()
    try:
        rows = connection.execute(
            """
            SELECT event_json FROM global_master_resume_events
            ORDER BY created_at DESC, event_id DESC
            """
        ).fetchall()
        return [_safe_json(row["event_json"]) for row in rows]
    finally:
        connection.close()


def _validate_prepared_snapshot(prepared: dict[str, Any]) -> None:
    if not isinstance(prepared, dict) or not prepared:
        raise Phase9FMasterResumeError("A prepared master-resume snapshot is required.")
    content = prepared.get("artifact_bytes")
    text = str(prepared.get("resume_text") or "")
    profile = prepared.get("structured_profile")
    semantic = prepared.get("semantic_identity")
    if not isinstance(content, bytes) or not content:
        raise Phase9FMasterResumeError("Prepared master-resume bytes are missing.")
    if sha256_bytes(content) != str(prepared.get("artifact_sha256") or ""):
        raise Phase9FMasterResumeError("Prepared artifact SHA-256 is inconsistent.")
    if sha256_text(text) != str(prepared.get("resume_text_sha256") or ""):
        raise Phase9FMasterResumeError("Prepared complete-text SHA-256 is inconsistent.")
    if not isinstance(profile, dict) or fingerprint_value(profile) != str(
        prepared.get("structured_profile_fingerprint") or ""
    ):
        raise Phase9FMasterResumeError("Prepared structured-profile identity is inconsistent.")
    if not isinstance(semantic, dict):
        raise Phase9FMasterResumeError("Prepared semantic identity is missing.")
    if canonical_json(semantic) != str(prepared.get("semantic_identity_json") or ""):
        raise Phase9FMasterResumeError("Prepared semantic JSON is not canonical.")
    if fingerprint_value(semantic) != str(
        prepared.get("master_content_fingerprint") or ""
    ):
        raise Phase9FMasterResumeError("Prepared master-content fingerprint is inconsistent.")
    provenance = prepared.get("extraction_provenance")
    if not isinstance(provenance, dict) or fingerprint_value(provenance) != str(
        prepared.get("extraction_provenance_fingerprint") or ""
    ):
        raise Phase9FMasterResumeError(
            "Prepared extraction-provenance fingerprint is inconsistent."
        )
    prepared_identity = {
        "preparation_version": str(prepared.get("preparation_version") or ""),
        "master_content_fingerprint": str(
            prepared.get("master_content_fingerprint") or ""
        ),
        "expected_current": deepcopy(prepared.get("expected_current") or {}),
        "preparation_mode": str(prepared.get("preparation_mode") or ""),
        "extraction_provenance_fingerprint": str(
            prepared.get("extraction_provenance_fingerprint") or ""
        ),
    }
    if fingerprint_value(prepared_identity) != str(
        prepared.get("prepared_snapshot_fingerprint") or ""
    ):
        raise Phase9FMasterResumeError(
            "Prepared snapshot fingerprint is inconsistent."
        )
    preview = prepared.get("preview_pdf_bytes")
    if preview is not None:
        if not isinstance(preview, bytes) or sha256_bytes(preview) != str(
            prepared.get("preview_pdf_sha256") or ""
        ):
            raise Phase9FMasterResumeError("Prepared preview PDF identity is inconsistent.")


def _insert_event(
    connection: sqlite3.Connection,
    *,
    event_type: str,
    master: dict[str, Any],
    previous_master_version_id: str,
    prepared_snapshot_fingerprint: str,
    actor_label: str,
    created_at: str,
) -> dict[str, Any]:
    event = {
        "event_id": uuid.uuid4().hex,
        "event_version": PHASE9F_MASTER_EVENT_VERSION,
        "event_type": event_type,
        "master_version_id": str(master["master_version_id"]),
        "master_version_fingerprint": str(master["master_version_fingerprint"]),
        "master_content_fingerprint": str(master["master_content_fingerprint"]),
        "version_number": int(master["version_number"]),
        "previous_master_version_id": str(previous_master_version_id or ""),
        "prepared_snapshot_fingerprint": str(prepared_snapshot_fingerprint or ""),
        "actor_label": str(actor_label or "Local user"),
        "created_at": created_at,
    }
    event["event_fingerprint"] = fingerprint_value(event)
    connection.execute(
        """
        INSERT INTO global_master_resume_events (
            event_id, event_fingerprint, event_version, event_type,
            master_version_id, master_version_fingerprint,
            previous_master_version_id, prepared_snapshot_fingerprint,
            actor_label, created_at, event_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event["event_id"],
            event["event_fingerprint"],
            PHASE9F_MASTER_EVENT_VERSION,
            event_type,
            master["master_version_id"],
            master["master_version_fingerprint"],
            previous_master_version_id or None,
            prepared_snapshot_fingerprint,
            event["actor_label"],
            created_at,
            canonical_json(event),
        ),
    )
    return event


def _insert_prepared_version(
    connection: sqlite3.Connection,
    *,
    prepared: dict[str, Any],
    display_name: str,
    version_number: int,
    predecessor: dict[str, Any] | None,
    created_at: str,
) -> dict[str, Any]:
    predecessor = predecessor or {}
    version_identity = build_master_version_identity(
        master_content_fingerprint=str(prepared["master_content_fingerprint"]),
        version_number=version_number,
        predecessor_master_version_id=str(
            predecessor.get("master_version_id") or ""
        ),
        predecessor_master_version_fingerprint=str(
            predecessor.get("master_version_fingerprint") or ""
        ),
    )
    version_fingerprint = fingerprint_value(version_identity)
    version_id = version_fingerprint[:32]
    snapshot = {
        "format_version": PHASE9F_MASTER_RESUME_VERSION,
        "master_version_id": version_id,
        "master_version_fingerprint": version_fingerprint,
        "master_content_fingerprint": str(prepared["master_content_fingerprint"]),
        "version_number": int(version_number),
        "predecessor": deepcopy(version_identity["predecessor"]),
        "artifact": {
            "artifact_sha256": str(prepared["artifact_sha256"]),
            "artifact_type": str(prepared["artifact_type"]),
            "artifact_size_bytes": int(prepared["artifact_size_bytes"]),
            "original_filename": str(prepared.get("original_filename") or ""),
            "media_type": str(prepared.get("media_type") or ""),
        },
        "resume_text": str(prepared["resume_text"]),
        "resume_text_sha256": str(prepared["resume_text_sha256"]),
        "resume_text_char_count": int(prepared["resume_text_char_count"]),
        "structured_profile": deepcopy(prepared["structured_profile"]),
        "structured_profile_fingerprint": str(
            prepared["structured_profile_fingerprint"]
        ),
        "semantic_identity": deepcopy(prepared["semantic_identity"]),
        "version_identity": deepcopy(version_identity),
        "extraction_provenance": deepcopy(prepared["extraction_provenance"]),
    }
    connection.execute(
        """
        INSERT INTO global_master_resume_versions (
            master_version_id, master_version_fingerprint,
            master_content_fingerprint, format_version,
            content_policy_version, version_policy_version, version_number,
            predecessor_master_version_id,
            predecessor_master_version_fingerprint, artifact_sha256,
            artifact_type, artifact_size_bytes, original_filename, media_type,
            resume_text_sha256, resume_text_char_count, resume_text,
            structured_profile_fingerprint, structured_profile_json,
            semantic_identity_json, version_identity_json,
            extraction_provenance_json, master_snapshot_json, display_name,
            created_at
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?
        )
        """,
        (
            version_id,
            version_fingerprint,
            prepared["master_content_fingerprint"],
            PHASE9F_MASTER_RESUME_VERSION,
            PHASE9F_MASTER_CONTENT_POLICY_VERSION,
            PHASE9F_MASTER_VERSION_POLICY_VERSION,
            version_number,
            version_identity["predecessor"]["master_version_id"] or None,
            version_identity["predecessor"]["master_version_fingerprint"] or None,
            prepared["artifact_sha256"],
            prepared["artifact_type"],
            int(prepared["artifact_size_bytes"]),
            str(prepared.get("original_filename") or ""),
            str(prepared.get("media_type") or ""),
            prepared["resume_text_sha256"],
            int(prepared["resume_text_char_count"]),
            prepared["resume_text"],
            prepared["structured_profile_fingerprint"],
            canonical_json(prepared["structured_profile"]),
            prepared["semantic_identity_json"],
            canonical_json(version_identity),
            canonical_json(prepared["extraction_provenance"]),
            canonical_json(snapshot),
            str(display_name or "Base Resume").strip() or "Base Resume",
            created_at,
        ),
    )

    artifacts = [
        {
            "kind": "original",
            "media_type": str(prepared.get("media_type") or ""),
            "filename": str(prepared.get("original_filename") or "master_resume"),
            "sha256": str(prepared["artifact_sha256"]),
            "bytes": prepared["artifact_bytes"],
            "authoritative": 1,
        }
    ]
    if prepared.get("preview_pdf_bytes") is not None:
        artifacts.append(
            {
                "kind": "preview_pdf",
                "media_type": "application/pdf",
                "filename": f"master_resume_v{version_number}_preview.pdf",
                "sha256": str(prepared["preview_pdf_sha256"]),
                "bytes": prepared["preview_pdf_bytes"],
                "authoritative": 0,
            }
        )
    for artifact in artifacts:
        artifact_id = fingerprint_value(
            {
                "master_version_id": version_id,
                "artifact_kind": artifact["kind"],
                "sha256": artifact["sha256"],
            }
        )[:32]
        connection.execute(
            """
            INSERT INTO global_master_resume_artifacts (
                artifact_id, master_version_id, artifact_kind, media_type,
                filename, sha256, byte_size, authoritative, artifact_bytes,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                artifact_id,
                version_id,
                artifact["kind"],
                artifact["media_type"],
                artifact["filename"],
                artifact["sha256"],
                len(artifact["bytes"]),
                artifact["authoritative"],
                sqlite3.Binary(artifact["bytes"]),
                created_at,
            ),
        )
    return {
        "master_version_id": version_id,
        "master_version_fingerprint": version_fingerprint,
        "master_content_fingerprint": str(prepared["master_content_fingerprint"]),
        "version_number": int(version_number),
    }


def commit_prepared_global_master_resume(
    prepared: dict[str, Any],
    *,
    display_name: str = "Base Resume",
    actor_label: str = "Local user",
) -> dict[str, Any]:
    """Atomically reuse current or append and activate one prepared version.

    Preparation is fully validated before ``BEGIN IMMEDIATE``. Inside the
    transaction only the expected current pointer is revalidated and rows are
    inserted/updated. A rollback leaves ``prepared`` reusable for a retry.
    """
    _validate_prepared_snapshot(prepared)
    expected = prepared.get("expected_current") or {}
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        state_row = connection.execute(
            """
            SELECT current_master_version_id, current_master_version_fingerprint
            FROM global_master_resume_state WHERE singleton_id = 1
            """
        ).fetchone()
        actual_id = str(state_row[0]) if state_row is not None else ""
        actual_fingerprint = str(state_row[1]) if state_row is not None else ""
        if actual_id != str(expected.get("master_version_id") or "") or (
            actual_fingerprint
            != str(expected.get("master_version_fingerprint") or "")
        ):
            raise Phase9FMasterResumeError(
                "The current global master resume changed after preparation. "
                "Review the prepared snapshot against the current version before retrying."
            )

        current = _select_version(connection, actual_id) if actual_id else None
        if actual_id and current is None:
            raise Phase9FMasterResumeError(
                "The global master-resume current pointer references a missing version."
            )
        if current is not None and str(current["artifact_sha256"]) == str(
            prepared["artifact_sha256"]
        ):
            exact_fields = (
                "resume_text_sha256",
                "structured_profile_fingerprint",
                "master_content_fingerprint",
            )
            if any(
                str(current[field]) != str(prepared[field])
                for field in exact_fields
            ):
                raise Phase9FMasterResumeError(
                    "Exact current artifact reuse produced mismatched semantic identity."
                )
            event = _insert_event(
                connection,
                event_type="exact_current_reused",
                master=current,
                previous_master_version_id=actual_id,
                prepared_snapshot_fingerprint=str(
                    prepared.get("prepared_snapshot_fingerprint") or ""
                ),
                actor_label=actor_label,
                created_at=_now(),
            )
            connection.commit()
            return {
                "outcome": "exact_current_reused",
                "created_new_version": False,
                "master": current,
                "event": event,
            }

        version_number = int(
            connection.execute(
                "SELECT COALESCE(MAX(version_number), 0) + 1 "
                "FROM global_master_resume_versions"
            ).fetchone()[0]
        )
        created_at = _now()
        inserted_identity = _insert_prepared_version(
            connection,
            prepared=prepared,
            display_name=display_name,
            version_number=version_number,
            predecessor=current,
            created_at=created_at,
        )
        connection.execute(
            """
            INSERT INTO global_master_resume_state (
                singleton_id, current_master_version_id,
                current_master_version_fingerprint, updated_at
            ) VALUES (1, ?, ?, ?)
            ON CONFLICT(singleton_id) DO UPDATE SET
                current_master_version_id=excluded.current_master_version_id,
                current_master_version_fingerprint=
                    excluded.current_master_version_fingerprint,
                updated_at=excluded.updated_at
            """,
            (
                inserted_identity["master_version_id"],
                inserted_identity["master_version_fingerprint"],
                created_at,
            ),
        )
        inserted = _select_version(
            connection,
            inserted_identity["master_version_id"],
        )
        if inserted is None:
            raise RuntimeError("The persisted master version could not be reloaded.")
        event = _insert_event(
            connection,
            event_type=("master_set" if current is None else "master_replaced"),
            master=inserted,
            previous_master_version_id=actual_id,
            prepared_snapshot_fingerprint=str(
                prepared.get("prepared_snapshot_fingerprint") or ""
            ),
            actor_label=actor_label,
            created_at=created_at,
        )
        connection.commit()
        return {
            "outcome": event["event_type"],
            "created_new_version": True,
            "master": inserted,
            "event": event,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def clear_current_global_master_resume(
    *,
    expected_master_version_id: str = "",
    expected_master_version_fingerprint: str = "",
    actor_label: str = "Local user",
) -> dict[str, Any]:
    """Remove the current pointer while preserving every immutable version.

    This is a local persistence-only lifecycle action. It never deletes a
    version or artifact and never invokes a model, embedding, or Chroma.
    """
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        state_row = connection.execute(
            """
            SELECT current_master_version_id, current_master_version_fingerprint
            FROM global_master_resume_state
            WHERE singleton_id = 1
            """
        ).fetchone()
        if state_row is None:
            if (
                str(expected_master_version_id or "")
                or str(expected_master_version_fingerprint or "")
            ):
                raise Phase9FMasterResumeError(
                    "The current base resume changed before removal. "
                    "Refresh the page and review the current version."
                )
            connection.commit()
            return {
                "outcome": "no_current_master",
                "removed_current": False,
                "master": None,
                "event": None,
            }

        actual_id = str(state_row["current_master_version_id"])
        actual_fingerprint = str(
            state_row["current_master_version_fingerprint"]
        )
        if (
            expected_master_version_id
            and actual_id != str(expected_master_version_id)
        ) or (
            expected_master_version_fingerprint
            and actual_fingerprint
            != str(expected_master_version_fingerprint)
        ):
            raise Phase9FMasterResumeError(
                "The current base resume changed before removal. "
                "Refresh the page and review the current version."
            )

        current = _select_version(connection, actual_id)
        if current is None:
            raise Phase9FMasterResumeError(
                "The base-resume current pointer references a missing version."
            )
        if str(current["master_version_fingerprint"]) != actual_fingerprint:
            raise Phase9FMasterResumeError(
                "The base-resume current pointer is inconsistent."
            )

        cursor = connection.execute(
            """
            DELETE FROM global_master_resume_state
            WHERE singleton_id = 1
              AND current_master_version_id = ?
              AND current_master_version_fingerprint = ?
            """,
            (actual_id, actual_fingerprint),
        )
        if int(cursor.rowcount or 0) != 1:
            raise Phase9FMasterResumeError(
                "The current base resume changed before removal. "
                "Refresh the page and try again."
            )

        created_at = _now()
        event = _insert_event(
            connection,
            event_type="current_master_removed",
            master=current,
            previous_master_version_id=actual_id,
            prepared_snapshot_fingerprint="",
            actor_label=actor_label,
            created_at=created_at,
        )
        connection.commit()
        return {
            "outcome": "current_master_removed",
            "removed_current": True,
            "master": current,
            "event": event,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_current_master_resume_snapshot(
    *,
    validate_artifacts: bool = True,
) -> dict[str, Any] | None:
    """Neutral future-consumer API for the complete immutable current snapshot."""
    current = get_current_global_master_resume()
    if current is None:
        return None
    result = deepcopy(current["master_snapshot"])
    result["display_name"] = current["display_name"]
    result["created_at"] = current["created_at"]
    if validate_artifacts:
        artifact = get_global_master_resume_artifact(
            current["master_version_id"],
            "original",
        )
        if artifact is None:
            raise Phase9FMasterResumeError(
                "The current global master resume has no authoritative artifact."
            )
        result["authoritative_artifact"] = artifact
    return result

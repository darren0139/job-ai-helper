"""Persistent approval, caching, locking, and restoration for tailoring versions."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from database import tailoring_version_manager as base_manager


PHASE7_PERSISTENCE_VERSION = "phase7-approved-generations-v1"
VALID_STATUSES = {"draft", "approved", "archived"}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    connection = base_manager._connect()
    connection.row_factory = sqlite3.Row
    return connection


def init_tailoring_generation_control() -> None:
    """Create Phase 7 metadata and per-application preference tables."""
    base_manager.init_application_tailoring_versions()
    connection = _connect()
    cursor = connection.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS application_tailoring_generation_meta (
            application_id INTEGER NOT NULL,
            generation_id TEXT NOT NULL,
            phase7_version TEXT NOT NULL,
            input_fingerprint TEXT,
            generation_kind TEXT NOT NULL DEFAULT 'manual',
            status TEXT NOT NULL DEFAULT 'draft',
            approved_at TEXT,
            archived_at TEXT,
            parent_generation_id TEXT,
            restored_from_generation_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (application_id, generation_id)
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_tailoring_generation_fingerprint
        ON application_tailoring_generation_meta (
            application_id,
            input_fingerprint,
            generation_kind,
            updated_at DESC
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_tailoring_generation_status
        ON application_tailoring_generation_meta (
            application_id,
            status,
            updated_at DESC
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS application_tailoring_preferences (
            application_id INTEGER PRIMARY KEY,
            approved_generation_id TEXT,
            lock_projects INTEGER NOT NULL DEFAULT 0,
            lock_skills INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.commit()
    connection.close()


def _generation_from_row(row: sqlite3.Row) -> dict[str, Any]:
    keys = set(row.keys())
    return {
        "id": int(row["id"]),
        "application_id": int(row["application_id"]),
        "generation_id": str(row["generation_id"]),
        "persistence_version": str(row["persistence_version"]),
        "candidate_pool": base_manager._load(row["candidate_pool_json"]),
        "project_inputs": base_manager._load(row["project_inputs_json"]),
        "fit_estimate": base_manager._load(row["fit_estimate_json"]),
        "projects": base_manager._load(row["projects_json"]),
        "skills": base_manager._load(row["skills_json"]),
        "fit_result": base_manager._load(row["fit_result_json"]),
        "generation_settings": base_manager._load(
            row["generation_settings_json"]
        ),
        "docx_path": base_manager._existing_path(row["docx_path"]),
        "pdf_path": base_manager._existing_path(row["pdf_path"]),
        "stored_docx_path": str(row["docx_path"] or ""),
        "stored_pdf_path": str(row["pdf_path"] or ""),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
        "phase7_version": (
            str(row["phase7_version"])
            if "phase7_version" in keys and row["phase7_version"]
            else PHASE7_PERSISTENCE_VERSION
        ),
        "input_fingerprint": (
            str(row["input_fingerprint"] or "")
            if "input_fingerprint" in keys
            else ""
        ),
        "generation_kind": (
            str(row["generation_kind"] or "manual")
            if "generation_kind" in keys
            else "manual"
        ),
        "status": (
            str(row["status"] or "draft")
            if "status" in keys
            else "draft"
        ),
        "approved_at": (
            str(row["approved_at"] or "")
            if "approved_at" in keys
            else ""
        ),
        "archived_at": (
            str(row["archived_at"] or "")
            if "archived_at" in keys
            else ""
        ),
        "parent_generation_id": (
            str(row["parent_generation_id"] or "")
            if "parent_generation_id" in keys
            else ""
        ),
        "restored_from_generation_id": (
            str(row["restored_from_generation_id"] or "")
            if "restored_from_generation_id" in keys
            else ""
        ),
    }


_JOIN_SQL = """
    SELECT
        versions.*,
        meta.phase7_version,
        meta.input_fingerprint,
        meta.generation_kind,
        COALESCE(meta.status, 'draft') AS status,
        meta.approved_at,
        meta.archived_at,
        meta.parent_generation_id,
        meta.restored_from_generation_id
    FROM application_tailoring_versions AS versions
    LEFT JOIN application_tailoring_generation_meta AS meta
      ON meta.application_id = versions.application_id
     AND meta.generation_id = versions.generation_id
"""


def record_generation_metadata(
    *,
    application_id: int,
    generation_id: str,
    input_fingerprint: str = "",
    generation_kind: str = "",
    parent_generation_id: str = "",
    restored_from_generation_id: str = "",
) -> None:
    """Create or update non-content metadata for a stored generation."""
    init_tailoring_generation_control()
    cleaned_id = str(generation_id or "").strip()
    if not cleaned_id:
        raise ValueError("generation_id is required.")

    now = _now()
    connection = _connect()
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT OR IGNORE INTO application_tailoring_generation_meta (
            application_id,
            generation_id,
            phase7_version,
            input_fingerprint,
            generation_kind,
            status,
            parent_generation_id,
            restored_from_generation_id,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?)
        """,
        (
            int(application_id),
            cleaned_id,
            PHASE7_PERSISTENCE_VERSION,
            str(input_fingerprint or ""),
            str(generation_kind or "manual"),
            str(parent_generation_id or ""),
            str(restored_from_generation_id or ""),
            now,
            now,
        ),
    )
    cursor.execute(
        """
        UPDATE application_tailoring_generation_meta
        SET phase7_version = ?,
            input_fingerprint = CASE
                WHEN ? <> '' THEN ?
                ELSE input_fingerprint
            END,
            generation_kind = CASE
                WHEN ? <> '' THEN ?
                ELSE generation_kind
            END,
            parent_generation_id = CASE
                WHEN ? <> '' THEN ?
                ELSE parent_generation_id
            END,
            restored_from_generation_id = CASE
                WHEN ? <> '' THEN ?
                ELSE restored_from_generation_id
            END,
            updated_at = ?
        WHERE application_id = ?
          AND generation_id = ?
        """,
        (
            PHASE7_PERSISTENCE_VERSION,
            str(input_fingerprint or ""),
            str(input_fingerprint or ""),
            str(generation_kind or ""),
            str(generation_kind or ""),
            str(parent_generation_id or ""),
            str(parent_generation_id or ""),
            str(restored_from_generation_id or ""),
            str(restored_from_generation_id or ""),
            now,
            int(application_id),
            cleaned_id,
        ),
    )
    connection.commit()
    connection.close()


def get_tailoring_generation(
    application_id: int,
    generation_id: str,
) -> dict[str, Any] | None:
    init_tailoring_generation_control()
    connection = _connect()
    cursor = connection.cursor()
    cursor.execute(
        _JOIN_SQL
        + """
        WHERE versions.application_id = ?
          AND versions.generation_id = ?
        LIMIT 1
        """,
        (int(application_id), str(generation_id)),
    )
    row = cursor.fetchone()
    connection.close()
    return _generation_from_row(row) if row is not None else None


def list_tailoring_generations(
    application_id: int,
) -> list[dict[str, Any]]:
    init_tailoring_generation_control()
    connection = _connect()
    cursor = connection.cursor()
    cursor.execute(
        _JOIN_SQL
        + """
        WHERE versions.application_id = ?
        ORDER BY versions.updated_at DESC, versions.id DESC
        """,
        (int(application_id),),
    )
    rows = cursor.fetchall()
    connection.close()
    return [_generation_from_row(row) for row in rows]


def find_cached_tailoring_generation(
    *,
    application_id: int,
    input_fingerprint: str,
    generation_kind: str,
) -> dict[str, Any] | None:
    """Return the most useful persisted generation for an exact fingerprint."""
    fingerprint = str(input_fingerprint or "").strip()
    if not fingerprint:
        return None

    init_tailoring_generation_control()
    connection = _connect()
    cursor = connection.cursor()
    cursor.execute(
        _JOIN_SQL
        + """
        WHERE versions.application_id = ?
          AND meta.input_fingerprint = ?
          AND meta.generation_kind = ?
          AND COALESCE(meta.status, 'draft') IN ('approved', 'draft')
        ORDER BY
            CASE COALESCE(meta.status, 'draft')
                WHEN 'approved' THEN 0
                WHEN 'draft' THEN 1
                ELSE 2
            END,
            versions.updated_at DESC,
            versions.id DESC
        LIMIT 1
        """,
        (
            int(application_id),
            fingerprint,
            str(generation_kind or "manual"),
        ),
    )
    row = cursor.fetchone()
    connection.close()
    return _generation_from_row(row) if row is not None else None


def approve_tailoring_generation(
    application_id: int,
    generation_id: str,
) -> dict[str, Any]:
    """Make one generation the active approval for an application."""
    state = get_tailoring_generation(application_id, generation_id)
    if state is None:
        raise ValueError("Tailoring generation was not found.")

    # Existing pre-Phase-7 generations may not have a metadata row yet.
    record_generation_metadata(
        application_id=application_id,
        generation_id=generation_id,
    )
    now = _now()
    connection = _connect()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE application_tailoring_generation_meta
        SET status = 'archived',
            archived_at = ?,
            updated_at = ?
        WHERE application_id = ?
          AND status = 'approved'
          AND generation_id <> ?
        """,
        (now, now, int(application_id), str(generation_id)),
    )
    cursor.execute(
        """
        UPDATE application_tailoring_generation_meta
        SET status = 'approved',
            approved_at = ?,
            archived_at = NULL,
            updated_at = ?
        WHERE application_id = ?
          AND generation_id = ?
        """,
        (now, now, int(application_id), str(generation_id)),
    )
    cursor.execute(
        """
        INSERT INTO application_tailoring_preferences (
            application_id,
            approved_generation_id,
            lock_projects,
            lock_skills,
            updated_at
        )
        VALUES (?, ?, 0, 0, ?)
        ON CONFLICT(application_id) DO UPDATE SET
            approved_generation_id = excluded.approved_generation_id,
            lock_projects = 0,
            lock_skills = 0,
            updated_at = excluded.updated_at
        """,
        (int(application_id), str(generation_id), now),
    )
    connection.commit()
    connection.close()
    approved = get_tailoring_generation(application_id, generation_id)
    if approved is None:
        raise RuntimeError("Approved generation could not be reloaded.")
    return approved


def archive_tailoring_generation(
    application_id: int,
    generation_id: str,
) -> None:
    state = get_tailoring_generation(application_id, generation_id)
    if state is None:
        raise ValueError("Tailoring generation was not found.")

    # Existing pre-Phase-7 generations may not have a metadata row yet.
    record_generation_metadata(
        application_id=application_id,
        generation_id=generation_id,
    )
    now = _now()
    connection = _connect()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE application_tailoring_generation_meta
        SET status = 'archived',
            archived_at = ?,
            updated_at = ?
        WHERE application_id = ?
          AND generation_id = ?
        """,
        (now, now, int(application_id), str(generation_id)),
    )
    cursor.execute(
        """
        UPDATE application_tailoring_preferences
        SET approved_generation_id = NULL,
            lock_projects = 0,
            lock_skills = 0,
            updated_at = ?
        WHERE application_id = ?
          AND approved_generation_id = ?
        """,
        (now, int(application_id), str(generation_id)),
    )
    connection.commit()
    connection.close()


def set_tailoring_section_locks(
    *,
    application_id: int,
    lock_projects: bool,
    lock_skills: bool,
) -> dict[str, Any]:
    control = get_application_generation_control(application_id)
    approved = control.get("approved_generation")
    if not isinstance(approved, dict):
        if lock_projects or lock_skills:
            raise ValueError("Approve a generation before locking sections.")
        return control

    now = _now()
    connection = _connect()
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO application_tailoring_preferences (
            application_id,
            approved_generation_id,
            lock_projects,
            lock_skills,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(application_id) DO UPDATE SET
            approved_generation_id = excluded.approved_generation_id,
            lock_projects = excluded.lock_projects,
            lock_skills = excluded.lock_skills,
            updated_at = excluded.updated_at
        """,
        (
            int(application_id),
            str(approved["generation_id"]),
            int(bool(lock_projects)),
            int(bool(lock_skills)),
            now,
        ),
    )
    connection.commit()
    connection.close()
    return get_application_generation_control(application_id)


def get_application_generation_control(
    application_id: int,
) -> dict[str, Any]:
    init_tailoring_generation_control()
    connection = _connect()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT *
        FROM application_tailoring_preferences
        WHERE application_id = ?
        """,
        (int(application_id),),
    )
    row = cursor.fetchone()
    connection.close()

    if row is None:
        return {
            "application_id": int(application_id),
            "approved_generation_id": "",
            "approved_generation": None,
            "lock_projects": False,
            "lock_skills": False,
            "updated_at": "",
        }

    approved_id = str(row["approved_generation_id"] or "")
    approved = (
        get_tailoring_generation(application_id, approved_id)
        if approved_id
        else None
    )
    if approved is None or approved.get("status") != "approved":
        approved_id = ""
        approved = None

    return {
        "application_id": int(application_id),
        "approved_generation_id": approved_id,
        "approved_generation": approved,
        "lock_projects": bool(row["lock_projects"]) if approved else False,
        "lock_skills": bool(row["lock_skills"]) if approved else False,
        "updated_at": str(row["updated_at"] or ""),
    }



def _delete_unreferenced_generation_files(
    paths: list[str],
) -> dict[str, list[str]]:
    """Delete tailored output files only when no generation still references them."""
    unique_paths = sorted(
        {
            str(path or "").strip()
            for path in paths
            if str(path or "").strip()
        }
    )
    if not unique_paths:
        return {"deleted": [], "kept": [], "missing": []}

    init_tailoring_generation_control()
    connection = _connect()
    cursor = connection.cursor()
    deleted: list[str] = []
    kept: list[str] = []
    missing: list[str] = []

    try:
        for value in unique_paths:
            cursor.execute(
                """
                SELECT COUNT(*) AS reference_count
                FROM application_tailoring_versions
                WHERE docx_path = ?
                   OR pdf_path = ?
                """,
                (value, value),
            )
            row = cursor.fetchone()
            reference_count = int(row["reference_count"] or 0) if row else 0
            if reference_count > 0:
                kept.append(value)
                continue

            path = Path(value)
            if not path.exists():
                missing.append(value)
                continue

            try:
                path.unlink()
                deleted.append(value)
            except OSError:
                kept.append(value)
    finally:
        connection.close()

    return {
        "deleted": deleted,
        "kept": kept,
        "missing": missing,
    }


def delete_tailoring_generation(
    *,
    application_id: int,
    generation_id: str,
    delete_unreferenced_files: bool = False,
) -> dict[str, Any]:
    """Permanently delete one Draft or Archived generation.

    Approved generations are deliberately protected. Approve another version or
    archive the approved version before deleting it.
    """
    state = get_tailoring_generation(application_id, generation_id)
    if state is None:
        raise ValueError("Tailoring generation was not found.")

    status = str(state.get("status") or "draft").lower()
    if status == "approved":
        raise ValueError(
            "The active approved generation cannot be deleted. "
            "Approve another version or archive it first."
        )
    if status not in {"draft", "archived"}:
        raise ValueError(f"Unsupported generation status: {status}")

    stored_paths = [
        str(state.get("stored_docx_path") or ""),
        str(state.get("stored_pdf_path") or ""),
    ]

    init_tailoring_generation_control()
    connection = _connect()
    cursor = connection.cursor()
    try:
        cursor.execute("BEGIN")
        cursor.execute(
            """
            DELETE FROM application_tailoring_generation_meta
            WHERE application_id = ?
              AND generation_id = ?
            """,
            (int(application_id), str(generation_id)),
        )
        metadata_deleted = max(0, int(cursor.rowcount or 0))
        cursor.execute(
            """
            DELETE FROM application_tailoring_versions
            WHERE application_id = ?
              AND generation_id = ?
            """,
            (int(application_id), str(generation_id)),
        )
        version_deleted = max(0, int(cursor.rowcount or 0))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    file_result = {"deleted": [], "kept": [], "missing": []}
    if delete_unreferenced_files:
        file_result = _delete_unreferenced_generation_files(stored_paths)

    return {
        "application_id": int(application_id),
        "generation_id": str(generation_id),
        "status": status,
        "version_deleted": version_deleted,
        "metadata_deleted": metadata_deleted,
        "files": file_result,
    }


def clear_tailoring_drafts(
    *,
    application_id: int,
    delete_unreferenced_files: bool = False,
    exclude_generation_ids: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Delete all Draft generations for one application.

    Approved and Archived versions are never removed by this operation.
    """
    excluded = {
        str(value or "").strip()
        for value in (exclude_generation_ids or [])
        if str(value or "").strip()
    }

    init_tailoring_generation_control()
    connection = _connect()
    cursor = connection.cursor()
    params: list[Any] = [int(application_id)]
    exclusion_sql = ""
    if excluded:
        placeholders = ", ".join("?" for _ in excluded)
        exclusion_sql = f" AND versions.generation_id NOT IN ({placeholders})"
        params.extend(sorted(excluded))

    cursor.execute(
        _JOIN_SQL
        + f"""
        WHERE versions.application_id = ?
          AND COALESCE(meta.status, 'draft') = 'draft'
          {exclusion_sql}
        ORDER BY versions.id
        """,
        tuple(params),
    )
    rows = cursor.fetchall()
    generation_ids = [str(row["generation_id"]) for row in rows]
    stored_paths: list[str] = []
    for row in rows:
        stored_paths.extend(
            [
                str(row["docx_path"] or ""),
                str(row["pdf_path"] or ""),
            ]
        )

    if not generation_ids:
        connection.close()
        return {
            "application_id": int(application_id),
            "deleted_count": 0,
            "deleted_generation_ids": [],
            "files": {"deleted": [], "kept": [], "missing": []},
        }

    placeholders = ", ".join("?" for _ in generation_ids)
    delete_params = (int(application_id), *generation_ids)
    try:
        cursor.execute("BEGIN")
        cursor.execute(
            f"""
            DELETE FROM application_tailoring_generation_meta
            WHERE application_id = ?
              AND generation_id IN ({placeholders})
            """,
            delete_params,
        )
        cursor.execute(
            f"""
            DELETE FROM application_tailoring_versions
            WHERE application_id = ?
              AND generation_id IN ({placeholders})
            """,
            delete_params,
        )
        deleted_count = max(0, int(cursor.rowcount or 0))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    file_result = {"deleted": [], "kept": [], "missing": []}
    if delete_unreferenced_files:
        file_result = _delete_unreferenced_generation_files(stored_paths)

    return {
        "application_id": int(application_id),
        "deleted_count": deleted_count,
        "deleted_generation_ids": generation_ids,
        "files": file_result,
    }

def delete_application_generation_control(
    application_id: int,
) -> dict[str, int]:
    """Delete Phase 7 metadata/preferences for a deleted application."""
    init_tailoring_generation_control()
    connection = _connect()
    cursor = connection.cursor()
    cursor.execute(
        """
        DELETE FROM application_tailoring_generation_meta
        WHERE application_id = ?
        """,
        (int(application_id),),
    )
    metadata_deleted = max(0, int(cursor.rowcount or 0))
    cursor.execute(
        """
        DELETE FROM application_tailoring_preferences
        WHERE application_id = ?
        """,
        (int(application_id),),
    )
    preferences_deleted = max(0, int(cursor.rowcount or 0))
    connection.commit()
    connection.close()
    return {
        "metadata_deleted": metadata_deleted,
        "preferences_deleted": preferences_deleted,
    }


def restore_tailoring_generation_as_draft(
    *,
    application_id: int,
    source_generation_id: str,
    new_generation_id: str | None = None,
) -> dict[str, Any]:
    """Clone a historical generation into a new mutable draft."""
    source = get_tailoring_generation(application_id, source_generation_id)
    if source is None:
        raise ValueError("Source tailoring generation was not found.")

    restored_id = str(new_generation_id or uuid.uuid4().hex)
    base_manager.save_application_tailoring_generation(
        application_id=int(application_id),
        generation_id=restored_id,
        candidate_pool=source.get("candidate_pool"),
        project_inputs=source.get("project_inputs"),
        fit_estimate=source.get("fit_estimate"),
        projects=source.get("projects"),
        skills=source.get("skills"),
        fit_result=source.get("fit_result"),
        generation_settings=source.get("generation_settings"),
        docx_path=source.get("stored_docx_path") or None,
        pdf_path=source.get("stored_pdf_path") or None,
    )
    record_generation_metadata(
        application_id=int(application_id),
        generation_id=restored_id,
        input_fingerprint=source.get("input_fingerprint", ""),
        generation_kind=source.get("generation_kind", "restored"),
        parent_generation_id=str(source_generation_id),
        restored_from_generation_id=str(source_generation_id),
    )
    restored = get_tailoring_generation(application_id, restored_id)
    if restored is None:
        raise RuntimeError("Restored draft could not be loaded.")
    return restored


def ensure_mutable_tailoring_generation(
    *,
    application_id: int,
    generation_id: str,
) -> dict[str, Any]:
    """Return the current draft or clone an approved/archived version."""
    state = get_tailoring_generation(application_id, generation_id)
    if state is None:
        raise ValueError("Tailoring generation was not found.")
    if state.get("status") == "draft":
        return state
    return restore_tailoring_generation_as_draft(
        application_id=application_id,
        source_generation_id=generation_id,
    )

"""Persistent approval, caching, locking, and restoration for tailoring versions."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from database import tailoring_version_manager as base_manager
from resume_builder.fitting_provenance import (
    normalise_fitting_search_algorithm_provenance,
)


PHASE7_PERSISTENCE_VERSION = "phase7-approved-generations-v1"
VALID_STATUSES = {"draft", "approved", "archived"}
PHASE9F_F_NORMAL_LIFECYCLE_VERSION = "phase9f-f-normal-generation-lifecycle-v1"


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
            source_application_result_id TEXT,
            base_content_fingerprint TEXT,
            content_fingerprint TEXT,
            content_changed INTEGER,
            phase9e_decision_fingerprint TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (application_id, generation_id)
        )
        """
    )
    existing_columns = {
        str(row[1])
        for row in cursor.execute(
            "PRAGMA table_info(application_tailoring_generation_meta)"
        ).fetchall()
    }
    for column, declaration in (
        ("source_application_result_id", "TEXT"),
        ("base_content_fingerprint", "TEXT"),
        ("content_fingerprint", "TEXT"),
        ("content_changed", "INTEGER"),
        ("phase9e_decision_fingerprint", "TEXT"),
    ):
        if column not in existing_columns:
            cursor.execute(
                "ALTER TABLE application_tailoring_generation_meta "
                f"ADD COLUMN {column} {declaration}"
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
        "fit_result": normalise_fitting_search_algorithm_provenance(
            base_manager._load(row["fit_result_json"])
        ),
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
        "source_application_result_id": (
            str(row["source_application_result_id"] or "")
            if "source_application_result_id" in keys
            else ""
        ),
        "base_content_fingerprint": (
            str(row["base_content_fingerprint"] or "")
            if "base_content_fingerprint" in keys
            else ""
        ),
        "content_fingerprint": (
            str(row["content_fingerprint"] or "")
            if "content_fingerprint" in keys
            else ""
        ),
        "content_changed": (
            bool(row["content_changed"])
            if "content_changed" in keys
            and row["content_changed"] is not None
            else None
        ),
        "phase9e_decision_fingerprint": (
            str(row["phase9e_decision_fingerprint"] or "")
            if "phase9e_decision_fingerprint" in keys
            else ""
        ),
    }


def get_phase9f_normal_generation_lifecycle(
    generation: dict[str, Any] | None,
) -> dict[str, Any]:
    """Read the additive F normal-lifecycle state from a version row."""
    settings = (generation or {}).get("generation_settings") or {}
    if not isinstance(settings, dict):
        return {}
    lifecycle = settings.get("phase9f_f_normal_lifecycle") or {}
    return lifecycle if isinstance(lifecycle, dict) else {}


def is_phase9f_normal_generation_incomplete(
    generation: dict[str, Any] | None,
) -> bool:
    lifecycle = get_phase9f_normal_generation_lifecycle(generation)
    return bool(
        lifecycle.get("lifecycle_version")
        == PHASE9F_F_NORMAL_LIFECYCLE_VERSION
        and lifecycle.get("generation_status") != "completed"
    )


def is_phase9f_normal_generation_approvable(
    generation: dict[str, Any] | None,
) -> bool:
    lifecycle = get_phase9f_normal_generation_lifecycle(generation)
    if lifecycle.get("lifecycle_version") != PHASE9F_F_NORMAL_LIFECYCLE_VERSION:
        return True
    fit = lifecycle.get("fit") or {}
    return bool(
        lifecycle.get("generation_status") == "completed"
        and isinstance(fit, dict)
        and fit.get("status") == "completed"
        and bool(((generation or {}).get("fit_result") or {}).get("fit_one_page"))
    )


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
        meta.restored_from_generation_id,
        meta.source_application_result_id,
        meta.base_content_fingerprint,
        meta.content_fingerprint,
        meta.content_changed,
        meta.phase9e_decision_fingerprint
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
    source_application_result_id: str = "",
    base_content_fingerprint: str = "",
    content_fingerprint: str = "",
    content_changed: bool | None = None,
    phase9e_decision_fingerprint: str = "",
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
            source_application_result_id,
            base_content_fingerprint,
            content_fingerprint,
            content_changed,
            phase9e_decision_fingerprint,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(application_id),
            cleaned_id,
            PHASE7_PERSISTENCE_VERSION,
            str(input_fingerprint or ""),
            str(generation_kind or "manual"),
            str(parent_generation_id or ""),
            str(restored_from_generation_id or ""),
            str(source_application_result_id or ""),
            str(base_content_fingerprint or ""),
            str(content_fingerprint or ""),
            (int(bool(content_changed)) if content_changed is not None else None),
            str(phase9e_decision_fingerprint or ""),
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
            source_application_result_id = CASE
                WHEN ? <> '' THEN ?
                ELSE source_application_result_id
            END,
            base_content_fingerprint = CASE
                WHEN ? <> '' THEN ?
                ELSE base_content_fingerprint
            END,
            content_fingerprint = CASE
                WHEN ? <> '' THEN ?
                ELSE content_fingerprint
            END,
            content_changed = CASE
                WHEN ? IS NOT NULL THEN ?
                ELSE content_changed
            END,
            phase9e_decision_fingerprint = CASE
                WHEN ? <> '' THEN ?
                ELSE phase9e_decision_fingerprint
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
            str(source_application_result_id or ""),
            str(source_application_result_id or ""),
            str(base_content_fingerprint or ""),
            str(base_content_fingerprint or ""),
            str(content_fingerprint or ""),
            str(content_fingerprint or ""),
            (int(bool(content_changed)) if content_changed is not None else None),
            (int(bool(content_changed)) if content_changed is not None else None),
            str(phase9e_decision_fingerprint or ""),
            str(phase9e_decision_fingerprint or ""),
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
        """,
        (
            int(application_id),
            fingerprint,
            str(generation_kind or "manual"),
        ),
    )
    rows = cursor.fetchall()
    connection.close()
    for row in rows:
        generation = _generation_from_row(row)
        # An F-managed partial paid attempt has normal draft metadata only so
        # it can be recovered, not because it is a complete cache result.
        if is_phase9f_normal_generation_incomplete(generation):
            continue
        return generation
    return None


def approve_tailoring_generation(
    application_id: int,
    generation_id: str,
) -> dict[str, Any]:
    """Make one generation the active approval for an application."""
    state = get_tailoring_generation(application_id, generation_id)
    if state is None:
        raise ValueError("Tailoring generation was not found.")
    if not is_phase9f_normal_generation_approvable(state):
        raise ValueError(
            "This Phase 9F generation is incomplete or has not produced a "
            "one-page deterministic fit, so it cannot be approved."
        )

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



def _table_exists(cursor: sqlite3.Cursor, table_name: str) -> bool:
    row = cursor.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        LIMIT 1
        """,
        (str(table_name),),
    ).fetchone()
    return row is not None


def get_tailoring_generation_delete_plan(
    *,
    application_id: int,
    generation_id: str,
) -> dict[str, Any]:
    """Return a fail-closed deletion plan for one saved generation."""
    state = get_tailoring_generation(application_id, generation_id)
    if state is None:
        raise ValueError("Tailoring generation was not found.")

    status = str(state.get("status") or "draft").lower()
    blockers: list[str] = []
    references: dict[str, int] = {}

    if status == "approved":
        blockers.append("Current approved résumé")
    elif status not in {"draft", "archived"}:
        blockers.append(f"Unsupported generation status: {status}")

    init_tailoring_generation_control()
    connection = _connect()
    cursor = connection.cursor()
    try:
        if _table_exists(cursor, "application_tailoring_preferences"):
            row = cursor.execute(
                """
                SELECT COUNT(*) AS reference_count
                FROM application_tailoring_preferences
                WHERE application_id = ?
                  AND approved_generation_id = ?
                """,
                (int(application_id), str(generation_id)),
            ).fetchone()
            count = int(row["reference_count"] or 0) if row else 0
            references["active_approval"] = count
            if count:
                blockers.append("Active approval pointer")

        if _table_exists(cursor, "application_tailoring_verifications"):
            row = cursor.execute(
                """
                SELECT COUNT(*) AS reference_count
                FROM application_tailoring_verifications
                WHERE application_id = ?
                  AND generation_id = ?
                """,
                (int(application_id), str(generation_id)),
            ).fetchone()
            count = int(row["reference_count"] or 0) if row else 0
            references["phase8_verifications"] = count
            if count:
                blockers.append(
                    f"Phase 8 verification reference ({count})"
                )

        if _table_exists(cursor, "global_blueprint_candidates"):
            row = cursor.execute(
                """
                SELECT COUNT(*) AS reference_count
                FROM global_blueprint_candidates
                WHERE source_application_id = ?
                  AND source_generation_id = ?
                """,
                (int(application_id), str(generation_id)),
            ).fetchone()
            count = int(row["reference_count"] or 0) if row else 0
            references["phase9b_candidates"] = count
            if count:
                blockers.append(
                    f"Phase 9B Blueprint candidate reference ({count})"
                )

        if _table_exists(cursor, "application_resume_results"):
            row = cursor.execute(
                """
                SELECT COUNT(*) AS reference_count
                FROM application_resume_results
                WHERE source_application_id = ?
                  AND source_generation_id = ?
                """,
                (int(application_id), str(generation_id)),
            ).fetchone()
            count = int(row["reference_count"] or 0) if row else 0
            references["application_results"] = count
            if count:
                blockers.append(
                    f"Immutable application-result reference ({count})"
                )

        if _table_exists(cursor, "application_resume_result_state"):
            row = cursor.execute(
                """
                SELECT COUNT(*) AS reference_count
                FROM application_resume_result_state
                WHERE application_id = ?
                  AND current_generation_id = ?
                """,
                (int(application_id), str(generation_id)),
            ).fetchone()
            count = int(row["reference_count"] or 0) if row else 0
            references["current_application_output"] = count
            if count:
                blockers.append("Current application-output pointer")

        if _table_exists(cursor, "application_cover_letter_results"):
            row = cursor.execute(
                """
                SELECT COUNT(*) AS reference_count
                FROM application_cover_letter_results
                WHERE application_id = ?
                  AND resume_output_id = ?
                """,
                (int(application_id), str(generation_id)),
            ).fetchone()
            count = int(row["reference_count"] or 0) if row else 0
            references["cover_letters"] = count
            if count:
                blockers.append(
                    f"Cover-letter provenance reference ({count})"
                )

        if _table_exists(
            cursor,
            "application_tailoring_generation_meta",
        ):
            row = cursor.execute(
                """
                SELECT COUNT(*) AS reference_count
                FROM application_tailoring_generation_meta
                WHERE application_id = ?
                  AND generation_id <> ?
                  AND (
                      parent_generation_id = ?
                      OR restored_from_generation_id = ?
                  )
                """,
                (
                    int(application_id),
                    str(generation_id),
                    str(generation_id),
                    str(generation_id),
                ),
            ).fetchone()
            count = int(row["reference_count"] or 0) if row else 0
            references["child_generations"] = count
            if count:
                blockers.append(
                    f"Child-generation lineage reference ({count})"
                )
    finally:
        connection.close()

    blockers = list(dict.fromkeys(blockers))
    return {
        "application_id": int(application_id),
        "generation_id": str(generation_id),
        "status": status,
        "generation": state,
        "references": references,
        "blockers": blockers,
        "deletable": bool(
            status in {"draft", "archived"} and not blockers
        ),
    }


def delete_tailoring_generation(
    *,
    application_id: int,
    generation_id: str,
    delete_unreferenced_files: bool = False,
) -> dict[str, Any]:
    """Permanently delete one unreferenced Draft or Archived generation."""
    plan = get_tailoring_generation_delete_plan(
        application_id=int(application_id),
        generation_id=str(generation_id),
    )
    if not plan["deletable"]:
        blockers = "; ".join(plan.get("blockers") or [])
        raise ValueError(
            "This saved résumé version is protected from deletion"
            + (f": {blockers}" if blockers else ".")
        )

    state = plan["generation"]
    status = str(plan["status"])
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
        "delete_plan": plan,
    }


def clear_tailoring_drafts(
    *,
    application_id: int,
    delete_unreferenced_files: bool = False,
    exclude_generation_ids: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Delete every unreferenced Draft for one application.

    Drafts that protect Phase 8, Blueprint, application-result, cover-letter,
    active-output, or child-generation lineage are skipped rather than removed.
    Approved and Archived versions are never removed by this operation.
    """
    excluded = {
        str(value or "").strip()
        for value in (exclude_generation_ids or [])
        if str(value or "").strip()
    }

    pending = [
        state
        for state in list_tailoring_generations(int(application_id))
        if str(state.get("status") or "draft").lower() == "draft"
        and str(state.get("generation_id") or "") not in excluded
    ]
    deleted_ids: list[str] = []
    skipped: dict[str, list[str]] = {}
    file_result = {"deleted": [], "kept": [], "missing": []}

    while pending:
        progress = False
        for state in list(pending):
            generation_id = str(state.get("generation_id") or "")
            plan = get_tailoring_generation_delete_plan(
                application_id=int(application_id),
                generation_id=generation_id,
            )
            if not plan["deletable"]:
                skipped[generation_id] = list(plan.get("blockers") or [])
                continue

            result = delete_tailoring_generation(
                application_id=int(application_id),
                generation_id=generation_id,
                delete_unreferenced_files=delete_unreferenced_files,
            )
            deleted_ids.append(generation_id)
            pending.remove(state)
            skipped.pop(generation_id, None)
            progress = True

            for key in ("deleted", "kept", "missing"):
                file_result[key].extend(
                    str(value)
                    for value in (result.get("files") or {}).get(key, [])
                )

        if not progress:
            break

    final_skipped: dict[str, list[str]] = {}
    for state in pending:
        generation_id = str(state.get("generation_id") or "")
        plan = get_tailoring_generation_delete_plan(
            application_id=int(application_id),
            generation_id=generation_id,
        )
        final_skipped[generation_id] = list(plan.get("blockers") or [])

    for key in file_result:
        file_result[key] = sorted(set(file_result[key]))

    return {
        "application_id": int(application_id),
        "deleted_count": len(deleted_ids),
        "deleted_generation_ids": deleted_ids,
        "skipped_generation_ids": sorted(final_skipped),
        "skipped": final_skipped,
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
        source_application_result_id=source.get(
            "source_application_result_id",
            "",
        ),
        base_content_fingerprint=source.get(
            "base_content_fingerprint",
            "",
        ),
        content_fingerprint=source.get(
            "content_fingerprint",
            "",
        ),
        content_changed=source.get("content_changed"),
        phase9e_decision_fingerprint=source.get(
            "phase9e_decision_fingerprint",
            "",
        ),
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

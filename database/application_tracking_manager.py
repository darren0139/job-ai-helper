"""Persistent real-world job application tracking for Application Sessions.

The existing ``applications`` table represents Job AI Helper work sessions.
This module stores the separate real-world lifecycle of the employer application:
whether the user actually applied, its current status, whether tracking is
complete, and optional notes.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from database import db_manager as base_manager


APPLICATION_TRACKING_STATUSES = (
    "not_applied",
    "applied",
    "screening",
    "interview",
    "offer",
    "rejected",
    "withdrawn",
)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    connection = base_manager._connect()
    connection.row_factory = sqlite3.Row
    return connection


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
            (str(table_name),),
        ).fetchone()
        is not None
    )


def init_application_tracking_schema() -> None:
    """Create the additive, idempotent application-tracking schema."""
    connection = _connect()
    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS application_tracking (
                application_id INTEGER PRIMARY KEY,
                applied INTEGER NOT NULL DEFAULT 0 CHECK (applied IN (0, 1)),
                applied_at TEXT,
                status TEXT NOT NULL DEFAULT 'not_applied' CHECK (
                    status IN (
                        'not_applied',
                        'applied',
                        'screening',
                        'interview',
                        'offer',
                        'rejected',
                        'withdrawn'
                    )
                ),
                completed INTEGER NOT NULL DEFAULT 0 CHECK (completed IN (0, 1)),
                completed_at TEXT,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_application_tracking_status
            ON application_tracking(status, updated_at DESC);

            CREATE INDEX IF NOT EXISTS idx_application_tracking_applied
            ON application_tracking(applied, completed, updated_at DESC);
            """
        )
        connection.commit()
    finally:
        connection.close()


def _normalise_status(status: Any) -> str:
    cleaned = str(status or "not_applied").strip().lower().replace(" ", "_")
    if cleaned not in APPLICATION_TRACKING_STATUSES:
        raise ValueError(
            "Invalid application status. Expected one of: "
            + ", ".join(APPLICATION_TRACKING_STATUSES)
        )
    return cleaned


def _row_to_tracking(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "application_id": int(row["application_id"]),
        "applied": bool(row["applied"]),
        "applied_at": str(row["applied_at"] or ""),
        "status": str(row["status"] or "not_applied"),
        "completed": bool(row["completed"]),
        "completed_at": str(row["completed_at"] or ""),
        "notes": str(row["notes"] or ""),
        "created_at": str(row["created_at"] or ""),
        "updated_at": str(row["updated_at"] or ""),
    }


def get_application_tracking(application_id: int) -> dict[str, Any] | None:
    """Return persisted lifecycle state for one Application Session."""
    connection = _connect()
    try:
        if not _table_exists(connection, "application_tracking"):
            return None
        row = connection.execute(
            "SELECT * FROM application_tracking WHERE application_id = ? LIMIT 1",
            (int(application_id),),
        ).fetchone()
        return _row_to_tracking(row)
    finally:
        connection.close()


def update_application_tracking(
    *,
    application_id: int,
    applied: bool,
    status: str,
    completed: bool,
    notes: str = "",
) -> dict[str, Any]:
    """Upsert one real-world application lifecycle record.

    Rules are intentionally conservative:
    - Any status beyond ``not_applied`` implies that the job was applied to.
    - Checking ``applied`` while status is ``not_applied`` promotes status to
      ``applied``.
    - ``completed`` is user-controlled and is not inferred from outcome status.
    - Applied/completed timestamps are created on the false->true transition and
      cleared when the corresponding checkbox is cleared.
    """
    resolved_status = _normalise_status(status)
    resolved_applied = bool(applied)
    resolved_completed = bool(completed)

    if resolved_status != "not_applied":
        resolved_applied = True
    elif resolved_applied:
        resolved_status = "applied"

    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        application = connection.execute(
            "SELECT id FROM applications WHERE id = ? LIMIT 1",
            (int(application_id),),
        ).fetchone()
        if application is None:
            raise ValueError(f"Application Session #{int(application_id)} does not exist.")

        existing = connection.execute(
            "SELECT * FROM application_tracking WHERE application_id = ? LIMIT 1",
            (int(application_id),),
        ).fetchone()
        now = _now()

        prior_applied_at = str(existing["applied_at"] or "") if existing else ""
        prior_completed_at = str(existing["completed_at"] or "") if existing else ""
        created_at = str(existing["created_at"] or now) if existing else now

        applied_at = prior_applied_at or now if resolved_applied else None
        completed_at = prior_completed_at or now if resolved_completed else None

        connection.execute(
            """
            INSERT INTO application_tracking (
                application_id,
                applied,
                applied_at,
                status,
                completed,
                completed_at,
                notes,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(application_id) DO UPDATE SET
                applied = excluded.applied,
                applied_at = excluded.applied_at,
                status = excluded.status,
                completed = excluded.completed,
                completed_at = excluded.completed_at,
                notes = excluded.notes,
                updated_at = excluded.updated_at
            """,
            (
                int(application_id),
                1 if resolved_applied else 0,
                applied_at,
                resolved_status,
                1 if resolved_completed else 0,
                completed_at,
                str(notes or "").strip(),
                created_at,
                now,
            ),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    saved = get_application_tracking(application_id)
    if saved is None:
        raise RuntimeError("Application tracking update did not persist.")
    return saved


def list_application_tracking_rows(
    *,
    include_drafts: bool = False,
) -> list[dict[str, Any]]:
    """Return the canonical tracker dataset used by UI, charts, and export."""
    connection = _connect()
    try:
        where_clause = ""
        if not include_drafts:
            where_clause = """
                WHERE
                    TRIM(COALESCE(app.job_title, '')) != ''
                    OR TRIM(COALESCE(app.company, '')) != ''
                    OR (
                        app.report_json IS NOT NULL
                        AND TRIM(app.report_json) != ''
                    )
            """

        has_jd_links = _table_exists(connection, "application_job_links")
        has_jd_rows = _table_exists(connection, "job_descriptions")
        if has_jd_links and has_jd_rows:
            location_expression = "COALESCE(jd.location, '')"
            jd_joins = """
            LEFT JOIN application_job_links AS app_link
              ON app_link.application_id = app.id
            LEFT JOIN job_descriptions AS jd
              ON jd.id = app_link.job_description_id
            """
        else:
            location_expression = "''"
            jd_joins = ""

        rows = connection.execute(
            f"""
            SELECT
                app.id AS application_id,
                COALESCE(app.session_name, '') AS session_name,
                COALESCE(app.job_title, '') AS job_title,
                COALESCE(app.company, '') AS company,
                {location_expression} AS location,
                app.overall_score AS overall_score,
                COALESCE(track.applied, 0) AS applied,
                COALESCE(track.applied_at, '') AS applied_at,
                COALESCE(track.status, 'not_applied') AS status,
                COALESCE(track.completed, 0) AS completed,
                COALESCE(track.completed_at, '') AS completed_at,
                COALESCE(track.notes, '') AS notes,
                COALESCE(app.created_at, '') AS session_created_at,
                COALESCE(app.updated_at, app.created_at, '') AS session_updated_at,
                COALESCE(track.updated_at, '') AS tracking_updated_at
            FROM applications AS app
            LEFT JOIN application_tracking AS track
              ON track.application_id = app.id
            {jd_joins}
            {where_clause}
            ORDER BY
                COALESCE(track.updated_at, app.updated_at, app.created_at) DESC,
                app.id DESC
            """
        ).fetchall()

        return [
            {
                "application_id": int(row["application_id"]),
                "session_name": str(row["session_name"] or ""),
                "job_title": str(row["job_title"] or ""),
                "company": str(row["company"] or ""),
                "location": str(row["location"] or ""),
                "overall_score": (
                    int(row["overall_score"])
                    if row["overall_score"] is not None
                    else None
                ),
                "applied": bool(row["applied"]),
                "applied_at": str(row["applied_at"] or ""),
                "status": str(row["status"] or "not_applied"),
                "completed": bool(row["completed"]),
                "completed_at": str(row["completed_at"] or ""),
                "notes": str(row["notes"] or ""),
                "session_created_at": str(row["session_created_at"] or ""),
                "session_updated_at": str(row["session_updated_at"] or ""),
                "tracking_updated_at": str(row["tracking_updated_at"] or ""),
            }
            for row in rows
        ]
    finally:
        connection.close()


def delete_application_tracking(application_id: int) -> int:
    """Delete tracking metadata when an Application Session is deleted."""
    connection = _connect()
    try:
        if not _table_exists(connection, "application_tracking"):
            return 0
        cursor = connection.execute(
            "DELETE FROM application_tracking WHERE application_id = ?",
            (int(application_id),),
        )
        connection.commit()
        return int(cursor.rowcount or 0)
    finally:
        connection.close()

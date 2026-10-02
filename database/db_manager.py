"""
database/db_manager.py — SQLite persistence for saved application sessions.

Each saved application session can begin as a draft, similar to a new chat.
After the user analyses a resume and job description, the same session is updated
with the report. The cover letter is also saved back into the same session.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


DB_PATH = Path("data/applications.db")


def _connect() -> sqlite3.Connection:
    """Open a SQLite connection after ensuring the parent data folder exists."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def _column_exists(cursor: sqlite3.Cursor, column_name: str) -> bool:
    """Return True if the applications table already has the given column."""
    cursor.execute("PRAGMA table_info(applications)")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns


def _add_column_if_missing(
    cursor: sqlite3.Cursor,
    column_name: str,
    column_definition: str,
) -> None:
    """Add a column to applications if it does not already exist."""
    if not _column_exists(cursor, column_name):
        cursor.execute(f"ALTER TABLE applications ADD COLUMN {column_name} {column_definition}")


def init_db() -> None:
    """Create or migrate the applications database table."""
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_name TEXT,
            resume_filename TEXT,
            job_title TEXT,
            company TEXT,
            degree TEXT,
            overall_score INTEGER,
            summary TEXT,
            report_json TEXT,
            cover_letter TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )

    # Safe migrations for older versions of this capstone database.
    _add_column_if_missing(cursor, "session_name", "TEXT")
    _add_column_if_missing(cursor, "resume_filename", "TEXT")
    _add_column_if_missing(cursor, "job_title", "TEXT")
    _add_column_if_missing(cursor, "company", "TEXT")
    _add_column_if_missing(cursor, "degree", "TEXT")
    _add_column_if_missing(cursor, "overall_score", "INTEGER")
    _add_column_if_missing(cursor, "summary", "TEXT")
    _add_column_if_missing(cursor, "report_json", "TEXT")
    _add_column_if_missing(cursor, "cover_letter", "TEXT")
    _add_column_if_missing(cursor, "created_at", "TEXT")
    _add_column_if_missing(cursor, "updated_at", "TEXT")

    conn.commit()
    conn.close()


def create_empty_application_session(
    *,
    degree: str = "",
    session_name: str | None = None,
) -> int:
    """
    Create a blank application session immediately.

    This makes the sidebar behave more like ChatGPT: the new session appears
    first, then the user fills it with a resume and job description.
    """
    now = datetime.now().isoformat(timespec="seconds")
    draft_name = session_name or "New Application"

    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO applications (
            session_name,
            resume_filename,
            job_title,
            company,
            degree,
            overall_score,
            summary,
            report_json,
            cover_letter,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            draft_name,
            "",
            "",
            "",
            degree,
            None,
            "",
            "",
            "",
            now,
            now,
        ),
    )

    application_id = int(cursor.lastrowid)

    if session_name is None:
        cursor.execute(
            """
            UPDATE applications
            SET session_name = ?
            WHERE id = ?
            """,
            (f"Application #{application_id}", application_id),
        )

    conn.commit()
    conn.close()

    return application_id


def insert_application_session_with_connection(
    connection: sqlite3.Connection,
    *,
    resume_filename: str,
    report: dict[str, Any],
    session_name: str = "",
    created_at: str,
) -> int:
    """Insert one populated session without committing the caller's transaction."""
    if not isinstance(report, dict) or not report:
        raise ValueError("A populated application report is required.")
    jd_profile = report.get("jd_profile") or {}
    meta = report.get("meta") or {}
    job_title = str(jd_profile.get("job_title") or "Unknown Role")
    company = str(jd_profile.get("company") or "Unknown Company")
    resolved_name = str(session_name or "").strip()
    if not resolved_name:
        resolved_name = (
            f"{job_title} @ {company}"
            if company and company != "Unknown Company"
            else job_title
        )
    cursor = connection.execute(
        """
        INSERT INTO applications (
            session_name, resume_filename, job_title, company, degree,
            overall_score, summary, report_json, cover_letter,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '', ?, ?)
        """,
        (
            resolved_name,
            str(resume_filename or ""),
            job_title,
            company,
            str(meta.get("degree") or ""),
            int(report.get("overall_score") or 0),
            str(report.get("summary") or ""),
            json.dumps(report, ensure_ascii=False, default=str),
            str(created_at),
            str(created_at),
        ),
    )
    return int(cursor.lastrowid)


def save_application(
    *,
    resume_filename: str,
    report: dict[str, Any],
    cover_letter: str = "",
) -> int:
    """
    Save one completed resume/job analysis session.

    This is used when the user analyzes without first clicking
    "New Application Session".
    """
    jd_profile = report.get("jd_profile", {})
    meta = report.get("meta", {})

    job_title = jd_profile.get("job_title", "Unknown Role") or "Unknown Role"
    company = jd_profile.get("company", "Unknown Company") or "Unknown Company"
    degree = meta.get("degree", "")
    overall_score = int(report.get("overall_score", 0))
    summary = report.get("summary", "")

    if company and company != "Unknown Company":
        session_name = f"{job_title} @ {company}"
    else:
        session_name = job_title

    now = datetime.now().isoformat(timespec="seconds")

    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO applications (
            session_name,
            resume_filename,
            job_title,
            company,
            degree,
            overall_score,
            summary,
            report_json,
            cover_letter,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session_name,
            resume_filename,
            job_title,
            company,
            degree,
            overall_score,
            summary,
            json.dumps(report, ensure_ascii=False),
            cover_letter,
            now,
            now,
        ),
    )

    application_id = int(cursor.lastrowid)

    conn.commit()
    conn.close()

    return application_id


def update_application_report(
    *,
    application_id: int,
    resume_filename: str,
    report: dict[str, Any],
) -> None:
    """Update an existing draft/current session with the analysis report."""
    jd_profile = report.get("jd_profile", {})
    meta = report.get("meta", {})

    job_title = jd_profile.get("job_title", "Unknown Role") or "Unknown Role"
    company = jd_profile.get("company", "Unknown Company") or "Unknown Company"
    degree = meta.get("degree", "")
    overall_score = int(report.get("overall_score", 0))
    summary = report.get("summary", "")

    if company and company != "Unknown Company":
        session_name = f"{job_title} @ {company}"
    else:
        session_name = job_title

    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE applications
        SET
            session_name = ?,
            resume_filename = ?,
            job_title = ?,
            company = ?,
            degree = ?,
            overall_score = ?,
            summary = ?,
            report_json = ?,
            cover_letter = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            session_name,
            resume_filename,
            job_title,
            company,
            degree,
            overall_score,
            summary,
            json.dumps(report, ensure_ascii=False),
            "",
            datetime.now().isoformat(timespec="seconds"),
            application_id,
        ),
    )

    conn.commit()
    conn.close()


def update_application_cover_letter(application_id: int, cover_letter: str) -> None:
    """Update the cover letter for an existing saved application session."""
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE applications
        SET
            cover_letter = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            cover_letter,
            datetime.now().isoformat(timespec="seconds"),
            application_id,
        ),
    )

    conn.commit()
    conn.close()


def rename_application_session(application_id: int, session_name: str) -> None:
    """Rename an existing application session."""
    cleaned_name = session_name.strip()

    if not cleaned_name:
        raise ValueError("Session name cannot be empty.")

    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE applications
        SET
            session_name = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            cleaned_name,
            datetime.now().isoformat(timespec="seconds"),
            application_id,
        ),
    )

    conn.commit()
    conn.close()


# FULL_APPLICATION_DELETE_V1
def _quote_sqlite_identifier(identifier: str) -> str:
    """Quote a SQLite identifier discovered from sqlite_master/PRAGMA."""
    return '"' + str(identifier).replace('"', '""') + '"'


def _application_delete_targets(cursor) -> list[tuple[str, tuple[str, ...]]]:
    """
    Return every non-root table containing an application lifecycle column.

    application_id is the canonical ownership/link column. The suffix match
    also covers relationship columns such as source_application_id or
    parent_application_id without hard-coding every future table name.
    """
    rows = cursor.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()

    targets: list[tuple[str, tuple[str, ...]]] = []
    for row in rows:
        table_name = str(row[0])
        if table_name == "applications":
            continue

        quoted_table = _quote_sqlite_identifier(table_name)
        columns = [
            str(info[1])
            for info in cursor.execute(
                f"PRAGMA table_info({quoted_table})"
            ).fetchall()
        ]
        application_columns = tuple(
            column
            for column in columns
            if column == "application_id" or column.endswith("_application_id")
        )
        if application_columns:
            targets.append((table_name, application_columns))

    return targets


def _application_delete_where(application_columns: tuple[str, ...]) -> str:
    return " OR ".join(
        f"{_quote_sqlite_identifier(column)} = ?"
        for column in application_columns
    )


def get_application_delete_impact(application_id: int) -> dict[str, int]:
    """Return a side-effect-free count of rows a full application delete removes."""
    application_id = int(application_id)
    if application_id <= 0:
        raise ValueError("application_id must be a positive integer.")

    conn = _connect()
    try:
        cursor = conn.cursor()
        impact: dict[str, int] = {}

        application_row = cursor.execute(
            "SELECT COUNT(*) FROM applications WHERE id = ?",
            (application_id,),
        ).fetchone()
        impact["applications"] = int(application_row[0] if application_row else 0)

        for table_name, application_columns in _application_delete_targets(cursor):
            where_sql = _application_delete_where(application_columns)
            parameters = (application_id,) * len(application_columns)
            row = cursor.execute(
                f"SELECT COUNT(*) FROM {_quote_sqlite_identifier(table_name)} "
                f"WHERE {where_sql}",
                parameters,
            ).fetchone()
            count = int(row[0] if row else 0)
            if count:
                impact[table_name] = count

        return impact
    finally:
        conn.close()


def delete_application_session(application_id: int) -> None:
    """
    Delete one application session and every SQLite row linked to it.

    Relationship/provenance rows, snapshots, histories, decisions, execution
    ledgers, tailoring state, chat rows, and future application-scoped tables
    are discovered from the schema instead of a brittle hand-maintained list.

    Shared/global rows are preserved because they do not carry this
    application's lifecycle key. The SQLite portion is atomic: any failure
    rolls back the entire operation.
    """
    application_id = int(application_id)
    if application_id <= 0:
        raise ValueError("application_id must be a positive integer.")

    conn = _connect()
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")

        # Delete application-owned/link rows first. This removes provenance
        # edges without deleting shared evidence objects they reference.
        for table_name, application_columns in _application_delete_targets(cursor):
            where_sql = _application_delete_where(application_columns)
            parameters = (application_id,) * len(application_columns)
            cursor.execute(
                f"DELETE FROM {_quote_sqlite_identifier(table_name)} "
                f"WHERE {where_sql}",
                parameters,
            )

        # Delete the application root last.
        cursor.execute(
            "DELETE FROM applications WHERE id = ?",
            (application_id,),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_recent_applications(limit: int = 15) -> list[tuple]:
    """
    Return recent saved application sessions for the sidebar.

    Returns tuples:
        (id, session_name, job_title, company, overall_score, has_report, updated_at)
    """
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            id,
            session_name,
            job_title,
            company,
            overall_score,
            CASE
                WHEN report_json IS NOT NULL AND TRIM(report_json) != '' THEN 1
                ELSE 0
            END AS has_report,
            COALESCE(updated_at, created_at)
        FROM applications
        ORDER BY COALESCE(updated_at, created_at) DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    )

    rows = cursor.fetchall()
    conn.close()

    return rows


def get_application_by_id(application_id: int) -> dict[str, Any] | None:
    """Return one saved application session by ID."""
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            session_name,
            resume_filename,
            job_title,
            company,
            degree,
            overall_score,
            summary,
            report_json,
            cover_letter,
            created_at,
            updated_at
        FROM applications
        WHERE id = ?
        """,
        (application_id,),
    )

    row = cursor.fetchone()
    conn.close()

    if row is None:
        return None

    report_json = row[7] or ""
    report = json.loads(report_json) if report_json.strip() else None

    return {
        "session_name": row[0],
        "resume_filename": row[1],
        "job_title": row[2],
        "company": row[3],
        "degree": row[4],
        "overall_score": row[5],
        "summary": row[6],
        "report": report,
        "cover_letter": row[8] or "",
        "created_at": row[9],
        "updated_at": row[10],
    }

"""
database/jd_library_manager.py — SQLite storage for analyzed job descriptions.

This is separate from application sessions, but each JD row can link back to
one application session through application_id.

This version is designed so the RAG library only comes from Analyze Resume.
There is no separate manual JD paste/upload library.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


DB_PATH = Path("data/applications.db")


def _connect() -> sqlite3.Connection:
    """Open SQLite and make sure the data folder exists."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def _column_exists(cursor: sqlite3.Cursor, table_name: str, column_name: str) -> bool:
    """Return True if the table has the given column."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns


def _add_column_if_missing(
    cursor: sqlite3.Cursor,
    table_name: str,
    column_name: str,
    column_definition: str,
) -> None:
    """Add a column if it does not already exist."""
    if not _column_exists(cursor, table_name, column_name):
        cursor.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
        )


def _index_exists(cursor: sqlite3.Cursor, index_name: str) -> bool:
    """Return True if an index exists."""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name = ?", (index_name,))
    return cursor.fetchone() is not None


def init_jd_library() -> None:
    """Create or migrate the job_descriptions table."""
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS job_descriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER,
            title TEXT,
            company TEXT,
            source_type TEXT,
            source_url TEXT,
            raw_text TEXT,
            jd_profile_json TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )

    _add_column_if_missing(cursor, "job_descriptions", "application_id", "INTEGER")
    _add_column_if_missing(cursor, "job_descriptions", "title", "TEXT")
    _add_column_if_missing(cursor, "job_descriptions", "company", "TEXT")
    _add_column_if_missing(cursor, "job_descriptions", "source_type", "TEXT")
    _add_column_if_missing(cursor, "job_descriptions", "source_url", "TEXT")
    _add_column_if_missing(cursor, "job_descriptions", "raw_text", "TEXT")
    _add_column_if_missing(cursor, "job_descriptions", "jd_profile_json", "TEXT")
    _add_column_if_missing(cursor, "job_descriptions", "created_at", "TEXT")
    _add_column_if_missing(cursor, "job_descriptions", "updated_at", "TEXT")

    # Create a unique index so each application session has at most one JD row.
    # SQLite allows multiple NULLs in a UNIQUE index, which is fine.
    if not _index_exists(cursor, "idx_job_descriptions_application_id_unique"):
        cursor.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_job_descriptions_application_id_unique
            ON job_descriptions(application_id)
            """
        )

    conn.commit()
    conn.close()


def save_or_update_job_description_for_application(
    *,
    application_id: int,
    raw_text: str,
    jd_profile: dict[str, Any],
    title: str = "",
    company: str = "",
    source_type: str = "application_session",
    source_url: str = "",
) -> int:
    """
    Save or update the JD linked to one application session.

    This prevents duplicate JD library rows when the same application session is
    analyzed multiple times.
    """
    cleaned_text = raw_text.strip()
    if not cleaned_text:
        raise ValueError("Job description text cannot be empty.")

    inferred_title = jd_profile.get("job_title", "") or "Untitled Job"
    inferred_company = jd_profile.get("company", "") or "Unknown Company"
    final_title = title.strip() or inferred_title
    final_company = company.strip() or inferred_company
    now = datetime.now().isoformat(timespec="seconds")

    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, created_at
        FROM job_descriptions
        WHERE application_id = ?
        """,
        (application_id,),
    )
    existing = cursor.fetchone()

    if existing:
        jd_id = int(existing[0])

        cursor.execute(
            """
            UPDATE job_descriptions
            SET
                title = ?,
                company = ?,
                source_type = ?,
                source_url = ?,
                raw_text = ?,
                jd_profile_json = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                final_title,
                final_company,
                source_type,
                source_url.strip(),
                cleaned_text,
                json.dumps(jd_profile, ensure_ascii=False),
                now,
                jd_id,
            ),
        )
    else:
        cursor.execute(
            """
            INSERT INTO job_descriptions (
                application_id,
                title,
                company,
                source_type,
                source_url,
                raw_text,
                jd_profile_json,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                application_id,
                final_title,
                final_company,
                source_type,
                source_url.strip(),
                cleaned_text,
                json.dumps(jd_profile, ensure_ascii=False),
                now,
                now,
            ),
        )
        jd_id = int(cursor.lastrowid)

    conn.commit()
    conn.close()

    return jd_id


def get_recent_job_descriptions(limit: int = 20) -> list[tuple]:
    """
    Return recent saved JDs.

    Returns tuples:
        (id, application_id, title, company, source_type, created_at)
    """
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, application_id, title, company, source_type, created_at
        FROM job_descriptions
        ORDER BY COALESCE(updated_at, created_at) DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    )

    rows = cursor.fetchall()
    conn.close()

    return rows


def get_job_description_by_id(jd_id: int) -> dict[str, Any] | None:
    """Return one saved JD by ID."""
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            application_id,
            title,
            company,
            source_type,
            source_url,
            raw_text,
            jd_profile_json,
            created_at,
            updated_at
        FROM job_descriptions
        WHERE id = ?
        """,
        (jd_id,),
    )

    row = cursor.fetchone()
    conn.close()

    if row is None:
        return None

    return {
        "id": jd_id,
        "application_id": row[0],
        "title": row[1],
        "company": row[2],
        "source_type": row[3],
        "source_url": row[4],
        "raw_text": row[5],
        "jd_profile": json.loads(row[6]) if row[6] else {},
        "created_at": row[7],
        "updated_at": row[8],
    }


def get_job_description_by_application_id(application_id: int) -> dict[str, Any] | None:
    """Return the JD linked to an application session."""
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id
        FROM job_descriptions
        WHERE application_id = ?
        """,
        (application_id,),
    )

    row = cursor.fetchone()
    conn.close()

    if row is None:
        return None

    return get_job_description_by_id(int(row[0]))


def get_all_job_descriptions(limit: int = 200) -> list[dict[str, Any]]:
    """Return saved JD records for vector indexing and RAG."""
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            id,
            application_id,
            title,
            company,
            source_type,
            source_url,
            raw_text,
            jd_profile_json,
            created_at,
            updated_at
        FROM job_descriptions
        ORDER BY COALESCE(updated_at, created_at) DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    )

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": row[0],
            "application_id": row[1],
            "title": row[2],
            "company": row[3],
            "source_type": row[4],
            "source_url": row[5],
            "raw_text": row[6],
            "jd_profile": json.loads(row[7]) if row[7] else {},
            "created_at": row[8],
            "updated_at": row[9],
        }
        for row in rows
    ]


def delete_job_description(jd_id: int) -> None:
    """Delete one JD from the library."""
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        DELETE FROM job_descriptions
        WHERE id = ?
        """,
        (jd_id,),
    )

    conn.commit()
    conn.close()


def delete_job_description_by_application_id(application_id: int) -> None:
    """Delete the JD linked to one application session."""
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        DELETE FROM job_descriptions
        WHERE application_id = ?
        """,
        (application_id,),
    )

    conn.commit()
    conn.close()

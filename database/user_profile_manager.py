"""
SQLite storage for a User Profile / Evidence Library.

Stores truthful evidence that may not appear in the current one-page resume,
such as projects, internship details, coursework, certifications, tools,
achievements, or portfolio notes.
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


def init_user_profile_library() -> None:
    """Create the user_evidence table if it does not already exist."""
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS user_evidence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            skills_json TEXT NOT NULL,
            tools_json TEXT NOT NULL,
            impact TEXT,
            source_type TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    conn.commit()
    conn.close()


def _json_list(values: list[str] | None) -> str:
    """Convert a list of strings into JSON text."""
    cleaned = [str(value).strip() for value in (values or []) if str(value).strip()]
    return json.dumps(cleaned, ensure_ascii=False)


def create_evidence_item(
    *,
    category: str,
    title: str,
    description: str,
    skills: list[str] | None = None,
    tools: list[str] | None = None,
    impact: str = "",
    source_type: str = "manual",
) -> int:
    """Add one item to the User Profile / Evidence Library."""
    cleaned_category = category.strip() or "Project"
    cleaned_title = title.strip()
    cleaned_description = description.strip()

    if not cleaned_title:
        raise ValueError("Evidence title cannot be empty.")

    if not cleaned_description:
        raise ValueError("Evidence description cannot be empty.")

    now = datetime.now().isoformat(timespec="seconds")

    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO user_evidence (
            category, title, description, skills_json, tools_json,
            impact, source_type, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            cleaned_category,
            cleaned_title,
            cleaned_description,
            _json_list(skills),
            _json_list(tools),
            impact.strip(),
            source_type.strip() or "manual",
            now,
            now,
        ),
    )

    item_id = int(cursor.lastrowid)
    conn.commit()
    conn.close()

    return item_id


def update_evidence_item(
    item_id: int,
    *,
    category: str,
    title: str,
    description: str,
    skills: list[str] | None = None,
    tools: list[str] | None = None,
    impact: str = "",
    source_type: str = "manual",
) -> None:
    """Update one evidence item."""
    if not title.strip():
        raise ValueError("Evidence title cannot be empty.")

    if not description.strip():
        raise ValueError("Evidence description cannot be empty.")

    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE user_evidence
        SET category = ?, title = ?, description = ?, skills_json = ?,
            tools_json = ?, impact = ?, source_type = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            category.strip() or "Project",
            title.strip(),
            description.strip(),
            _json_list(skills),
            _json_list(tools),
            impact.strip(),
            source_type.strip() or "manual",
            datetime.now().isoformat(timespec="seconds"),
            item_id,
        ),
    )

    conn.commit()
    conn.close()


def _row_to_dict(row: tuple[Any, ...]) -> dict[str, Any]:
    """Convert a SQLite row into a dictionary."""
    return {
        "id": row[0],
        "category": row[1],
        "title": row[2],
        "description": row[3],
        "skills": json.loads(row[4]) if row[4] else [],
        "tools": json.loads(row[5]) if row[5] else [],
        "impact": row[6] or "",
        "source_type": row[7] or "",
        "created_at": row[8],
        "updated_at": row[9],
    }


def get_evidence_items(*, category: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    """Return evidence items, newest first."""
    conn = _connect()
    cursor = conn.cursor()

    if category and category.strip() and category != "All":
        cursor.execute(
            """
            SELECT id, category, title, description, skills_json, tools_json,
                   impact, source_type, created_at, updated_at
            FROM user_evidence
            WHERE category = ?
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            (category.strip(), limit),
        )
    else:
        cursor.execute(
            """
            SELECT id, category, title, description, skills_json, tools_json,
                   impact, source_type, created_at, updated_at
            FROM user_evidence
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        )

    rows = cursor.fetchall()
    conn.close()

    return [_row_to_dict(row) for row in rows]


def get_evidence_item_by_id(item_id: int) -> dict[str, Any] | None:
    """Return one evidence item by ID."""
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, category, title, description, skills_json, tools_json,
               impact, source_type, created_at, updated_at
        FROM user_evidence
        WHERE id = ?
        """,
        (item_id,),
    )

    row = cursor.fetchone()
    conn.close()

    if row is None:
        return None

    return _row_to_dict(row)


def delete_evidence_item(item_id: int) -> None:
    """Delete one evidence item."""
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_evidence WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()


def clear_evidence_library() -> None:
    """Delete all user evidence items."""
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_evidence")
    conn.commit()
    conn.close()

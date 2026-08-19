"""
database/user_profile_manager.py

SQLite storage for a User Profile / Evidence Library.

Updated version:
- Adds optional period/date field.
- Keeps period optional.
- Supports sorting evidence items by period, so old/new projects can be ordered.
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from resume_builder.project_header_format import split_legacy_project_title


DB_PATH = Path("data/applications.db")

MONTH_MAP = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def _connect() -> sqlite3.Connection:
    """Open SQLite and make sure the data folder exists."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_user_profile_library() -> None:
    """Create or migrate the user_evidence table."""
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS user_evidence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            subtitle TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL,
            period TEXT,
            skills_json TEXT NOT NULL,
            tools_json TEXT NOT NULL,
            resume_header_tools_json TEXT NOT NULL DEFAULT '[]',
            resume_header_context_json TEXT NOT NULL DEFAULT '[]',
            impact TEXT,
            source_type TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    # Migration for users who already created the table before period existed.
    cursor.execute("PRAGMA table_info(user_evidence)")
    columns = [column[1] for column in cursor.fetchall()]

    if "period" not in columns:
        cursor.execute("ALTER TABLE user_evidence ADD COLUMN period TEXT")
    if "subtitle" not in columns:
        cursor.execute("ALTER TABLE user_evidence ADD COLUMN subtitle TEXT NOT NULL DEFAULT ''")
    if "resume_header_tools_json" not in columns:
        cursor.execute("ALTER TABLE user_evidence ADD COLUMN resume_header_tools_json TEXT NOT NULL DEFAULT '[]'")
    if "resume_header_context_json" not in columns:
        cursor.execute("ALTER TABLE user_evidence ADD COLUMN resume_header_context_json TEXT NOT NULL DEFAULT '[]'")

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS user_resume_format_preferences (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            project_header_layout TEXT NOT NULL DEFAULT 'auto',
            project_metadata_style TEXT NOT NULL DEFAULT 'pipes',
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


def _parse_period_start(period: str) -> tuple[int, int]:
    """
    Convert a loose period string to a sortable (year, month).

    Examples:
        "Jun 2024 - Jul 2024" -> (2024, 6)
        "2024" -> (2024, 1)
        "" -> (9999, 12), meaning unknown dates sort last by default.
    """
    text = str(period or "").strip().lower()

    if not text:
        return (9999, 12)

    # Prefer patterns like "Jun 2024".
    month_year = re.search(
        r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
        r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?|tember)?|oct(?:ober)?|"
        r"nov(?:ember)?|dec(?:ember)?)\s+((?:19|20)\d{2})\b",
        text,
    )

    if month_year:
        month_text = month_year.group(1)
        year = int(month_year.group(2))
        month = MONTH_MAP.get(month_text[:3], 1)
        return (year, month)

    year_match = re.search(r"\b((?:19|20)\d{2})\b", text)
    if year_match:
        return (int(year_match.group(1)), 1)

    return (9999, 12)


def create_evidence_item(
    *,
    category: str,
    title: str,
    description: str,
    period: str = "",
    skills: list[str] | None = None,
    tools: list[str] | None = None,
    impact: str = "",
    subtitle: str = "",
    resume_header_tools: list[str] | None = None,
    resume_header_context: list[str] | None = None,
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
            category,
            title,
            subtitle,
            description,
            period,
            skills_json,
            tools_json,
            resume_header_tools_json,
            resume_header_context_json,
            impact,
            source_type,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            cleaned_category,
            cleaned_title,
            subtitle.strip(),
            cleaned_description,
            period.strip(),
            _json_list(skills),
            _json_list(tools),
            _json_list(resume_header_tools),
            _json_list(resume_header_context),
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
    period: str = "",
    skills: list[str] | None = None,
    tools: list[str] | None = None,
    impact: str = "",
    subtitle: str = "",
    resume_header_tools: list[str] | None = None,
    resume_header_context: list[str] | None = None,
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
        SET
            category = ?,
            title = ?,
            subtitle = ?,
            description = ?,
            period = ?,
            skills_json = ?,
            tools_json = ?,
            resume_header_tools_json = ?,
            resume_header_context_json = ?,
            impact = ?,
            source_type = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            category.strip() or "Project",
            title.strip(),
            subtitle.strip(),
            description.strip(),
            period.strip(),
            _json_list(skills),
            _json_list(tools),
            _json_list(resume_header_tools),
            _json_list(resume_header_context),
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
        "subtitle": row[3] or "",
        "description": row[4],
        "period": row[5] or "",
        "skills": json.loads(row[6]) if row[6] else [],
        "tools": json.loads(row[7]) if row[7] else [],
        "resume_header_tools": json.loads(row[8]) if row[8] else [],
        "resume_header_context": json.loads(row[9]) if row[9] else [],
        "impact": row[10] or "",
        "source_type": row[11] or "",
        "created_at": row[12],
        "updated_at": row[13],
    }


def get_evidence_items(
    *,
    category: str | None = None,
    limit: int = 100,
    sort_by_period: bool = False,
    period_order: str = "earliest_first",
) -> list[dict[str, Any]]:
    """
    Return evidence items.

    Args:
        category: Optional category filter.
        limit: Maximum number of rows.
        sort_by_period: If True, sort using optional period/date.
        period_order: "earliest_first" or "newest_first".
    """
    conn = _connect()
    cursor = conn.cursor()

    if category and category.strip() and category != "All":
        cursor.execute(
            """
            SELECT id, category, title, subtitle, description, period, skills_json, tools_json,
                   resume_header_tools_json, resume_header_context_json,
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
            SELECT id, category, title, subtitle, description, period, skills_json, tools_json,
                   resume_header_tools_json, resume_header_context_json,
                   impact, source_type, created_at, updated_at
            FROM user_evidence
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        )

    rows = cursor.fetchall()
    conn.close()

    items = [_row_to_dict(row) for row in rows]

    if sort_by_period:
        reverse = period_order == "newest_first"
        items.sort(
            key=lambda item: (
                _parse_period_start(item.get("period", "")),
                item.get("title", "").lower(),
            ),
            reverse=reverse,
        )

    return items


def get_all_evidence_items_for_snapshot() -> list[dict[str, Any]]:
    """Return the complete mutable Evidence Library for immutable snapshots.

    This deliberately has no UI pagination limit.  Callers that need durable
    retry semantics must freeze the returned content rather than retain only
    the mutable row IDs.
    """
    conn = _connect()
    try:
        cursor = conn.cursor()
        exists = cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='user_evidence'"
        ).fetchone()
        if exists is None:
            return []
        cursor.execute(
            """
            SELECT id, category, title, subtitle, description, period, skills_json, tools_json,
                   resume_header_tools_json, resume_header_context_json,
                   impact, source_type, created_at, updated_at
            FROM user_evidence
            ORDER BY id ASC
            """
        )
        return [_row_to_dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_evidence_item_by_id(item_id: int) -> dict[str, Any] | None:
    """Return one evidence item by ID."""
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, category, title, subtitle, description, period, skills_json, tools_json,
               resume_header_tools_json, resume_header_context_json,
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



RESUME_FORMAT_DEFAULTS = {
    "project_header_layout": "auto",
    "project_metadata_style": "pipes",
}
_VALID_PROJECT_HEADER_LAYOUTS = {"auto", "stacked", "inline"}
_VALID_PROJECT_METADATA_STYLES = {"pipes", "parentheses"}


def get_resume_format_preferences() -> dict[str, str]:
    conn = _connect()
    try:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='user_resume_format_preferences'"
        ).fetchone()
        if exists is None:
            return dict(RESUME_FORMAT_DEFAULTS)
        row = conn.execute(
            "SELECT project_header_layout, project_metadata_style "
            "FROM user_resume_format_preferences WHERE id=1"
        ).fetchone()
        if row is None:
            return dict(RESUME_FORMAT_DEFAULTS)
        layout = str(row[0] or "").strip().lower()
        style = str(row[1] or "").strip().lower()
        return {
            "project_header_layout": layout if layout in _VALID_PROJECT_HEADER_LAYOUTS else "auto",
            "project_metadata_style": style if style in _VALID_PROJECT_METADATA_STYLES else "pipes",
        }
    finally:
        conn.close()


def update_resume_format_preferences(*, project_header_layout: str, project_metadata_style: str) -> None:
    layout = str(project_header_layout or "").strip().lower()
    style = str(project_metadata_style or "").strip().lower()
    if layout not in _VALID_PROJECT_HEADER_LAYOUTS:
        raise ValueError("Unsupported project header layout.")
    if style not in _VALID_PROJECT_METADATA_STYLES:
        raise ValueError("Unsupported project metadata style.")
    init_user_profile_library()
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO user_resume_format_preferences (
                id, project_header_layout, project_metadata_style, updated_at
            ) VALUES (1, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                project_header_layout=excluded.project_header_layout,
                project_metadata_style=excluded.project_metadata_style,
                updated_at=excluded.updated_at
            """,
            (layout, style, datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()
    finally:
        conn.close()


def migrate_legacy_project_titles_to_structured_metadata() -> int:
    """Move display metadata out of trailing Project-title parentheses only."""
    init_user_profile_library()
    conn = _connect()
    migrated = 0
    try:
        rows = conn.execute(
            """
            SELECT id, title, subtitle,
                   resume_header_tools_json, resume_header_context_json
            FROM user_evidence
            WHERE lower(trim(category))='project'
            ORDER BY id
            """
        ).fetchall()
        for row in rows:
            item_id = int(row[0])
            title = str(row[1] or "").strip()
            if str(row[2] or "").strip():
                continue
            header_tools = json.loads(row[3]) if row[3] else []
            header_context = json.loads(row[4]) if row[4] else []
            if header_tools or header_context:
                continue
            parsed = split_legacy_project_title(title)
            if not parsed.get("legacy_metadata_found"):
                continue
            clean_title = str(parsed.get("title") or "").strip()
            if not clean_title or clean_title == title:
                continue
            conn.execute(
                """
                UPDATE user_evidence
                SET title=?, resume_header_tools_json=?,
                    resume_header_context_json=?, updated_at=?
                WHERE id=?
                """,
                (
                    clean_title,
                    _json_list(parsed.get("resume_header_tools") or []),
                    _json_list(parsed.get("resume_header_context") or []),
                    datetime.now().isoformat(timespec="seconds"),
                    item_id,
                ),
            )
            migrated += 1
        conn.commit()
        return migrated
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

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

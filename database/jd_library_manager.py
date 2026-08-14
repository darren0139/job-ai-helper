"""
database/jd_library_manager.py — canonical JD storage for analyzed jobs.

A job description is stored once per logical company/title/location identity.
Application sessions link to that canonical row through application_job_links.
Exact/revised posting text is retained in job_description_versions.

The migration is automatic and preserves existing job_descriptions rows.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from rag.jd_identity import build_job_identity, normalize_field


DB_PATH = Path("data/applications.db")


def _connect() -> sqlite3.Connection:
    """Open SQLite and make sure the data folder exists."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _column_exists(cursor: sqlite3.Cursor, table_name: str, column_name: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table_name})")
    return column_name in {str(row[1]) for row in cursor.fetchall()}


def _add_column_if_missing(
    cursor: sqlite3.Cursor,
    table_name: str,
    column_name: str,
    column_definition: str,
) -> None:
    if not _column_exists(cursor, table_name, column_name):
        cursor.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
        )


def _safe_json_loads(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _json_dumps(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False)


def _extract_location(jd_profile: dict[str, Any], explicit_location: str = "") -> str:
    if explicit_location.strip():
        return explicit_location.strip()

    for key in ("location", "job_location", "work_location"):
        value = jd_profile.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    locations = jd_profile.get("locations")
    if isinstance(locations, list):
        values = [str(item).strip() for item in locations if str(item).strip()]
        if values:
            return ", ".join(values)

    return ""


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _create_schema(cursor: sqlite3.Cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS job_descriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER,
            title TEXT,
            company TEXT,
            location TEXT,
            source_type TEXT,
            source_url TEXT,
            raw_text TEXT,
            jd_profile_json TEXT,
            canonical_jd_id TEXT,
            source_version_id TEXT,
            company_normalized TEXT,
            title_normalized TEXT,
            location_normalized TEXT,
            first_seen_at TEXT,
            last_seen_at TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )

    legacy_columns = {
        "application_id": "INTEGER",
        "title": "TEXT",
        "company": "TEXT",
        "location": "TEXT",
        "source_type": "TEXT",
        "source_url": "TEXT",
        "raw_text": "TEXT",
        "jd_profile_json": "TEXT",
        "canonical_jd_id": "TEXT",
        "source_version_id": "TEXT",
        "company_normalized": "TEXT",
        "title_normalized": "TEXT",
        "location_normalized": "TEXT",
        "first_seen_at": "TEXT",
        "last_seen_at": "TEXT",
        "created_at": "TEXT",
        "updated_at": "TEXT",
    }
    for column_name, definition in legacy_columns.items():
        _add_column_if_missing(cursor, "job_descriptions", column_name, definition)

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS job_description_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_description_id INTEGER NOT NULL,
            source_version_id TEXT NOT NULL,
            raw_text TEXT NOT NULL,
            jd_profile_json TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(job_description_id, source_version_id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS application_job_links (
            application_id INTEGER PRIMARY KEY,
            job_description_id INTEGER NOT NULL,
            source_version_id TEXT NOT NULL,
            linked_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    # The old index encoded "one JD row per session". The link table owns that
    # constraint now, so retaining this index would misrepresent the new model.
    cursor.execute("DROP INDEX IF EXISTS idx_job_descriptions_application_id_unique")

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_application_job_links_job_id
        ON application_job_links(job_description_id)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_job_description_versions_job_id
        ON job_description_versions(job_description_id)
        """
    )


def _upsert_version(
    cursor: sqlite3.Cursor,
    *,
    job_description_id: int,
    source_version_id: str,
    raw_text: str,
    jd_profile_json: str,
    created_at: str,
) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM job_description_versions
        WHERE job_description_id = ? AND source_version_id = ?
        """,
        (job_description_id, source_version_id),
    )
    existed = cursor.fetchone() is not None

    cursor.execute(
        """
        INSERT OR IGNORE INTO job_description_versions (
            job_description_id,
            source_version_id,
            raw_text,
            jd_profile_json,
            created_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            job_description_id,
            source_version_id,
            raw_text,
            jd_profile_json,
            created_at,
        ),
    )
    return not existed


def _backfill_legacy_rows(cursor: sqlite3.Cursor) -> None:
    """Convert legacy one-row-per-session data into canonical rows and links."""
    cursor.execute(
        """
        SELECT *
        FROM job_descriptions
        ORDER BY id ASC
        """
    )
    rows = list(cursor.fetchall())

    canonical_owner: dict[str, int] = {}

    for row in rows:
        row_id = int(row["id"])
        raw_text = str(row["raw_text"] or "").strip()
        jd_profile = _safe_json_loads(row["jd_profile_json"])
        title = str(row["title"] or jd_profile.get("job_title") or "Untitled Job").strip()
        company = str(row["company"] or jd_profile.get("company") or "Unknown Company").strip()
        location = _extract_location(jd_profile, str(row["location"] or ""))

        identity = build_job_identity(
            company=company,
            title=title,
            location=location,
            raw_jd_text=raw_text,
        )
        canonical_id = identity.canonical_jd_id
        source_id = identity.source_version_id
        created_at = str(row["created_at"] or row["updated_at"] or _now())
        updated_at = str(row["updated_at"] or created_at)

        target_id = canonical_owner.get(canonical_id)
        if target_id is None:
            cursor.execute(
                """
                SELECT id
                FROM job_descriptions
                WHERE canonical_jd_id = ? AND id != ?
                ORDER BY id ASC
                LIMIT 1
                """,
                (canonical_id, row_id),
            )
            existing = cursor.fetchone()
            target_id = int(existing["id"]) if existing else row_id
            canonical_owner[canonical_id] = target_id

        _upsert_version(
            cursor,
            job_description_id=target_id,
            source_version_id=source_id,
            raw_text=raw_text,
            jd_profile_json=_json_dumps(jd_profile),
            created_at=created_at,
        )

        application_id = row["application_id"]
        if application_id is not None:
            cursor.execute(
                """
                INSERT INTO application_job_links (
                    application_id,
                    job_description_id,
                    source_version_id,
                    linked_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(application_id) DO UPDATE SET
                    job_description_id = excluded.job_description_id,
                    source_version_id = excluded.source_version_id,
                    updated_at = excluded.updated_at
                """,
                (int(application_id), target_id, source_id, created_at, updated_at),
            )

        if target_id == row_id:
            cursor.execute(
                """
                UPDATE job_descriptions
                SET
                    title = ?,
                    company = ?,
                    location = ?,
                    raw_text = ?,
                    jd_profile_json = ?,
                    canonical_jd_id = ?,
                    source_version_id = ?,
                    company_normalized = ?,
                    title_normalized = ?,
                    location_normalized = ?,
                    first_seen_at = COALESCE(first_seen_at, ?, created_at, ?),
                    last_seen_at = COALESCE(last_seen_at, updated_at, ?, ?),
                    created_at = COALESCE(created_at, ?),
                    updated_at = COALESCE(updated_at, ?)
                WHERE id = ?
                """,
                (
                    title,
                    company,
                    location,
                    raw_text,
                    _json_dumps(jd_profile),
                    canonical_id,
                    source_id,
                    identity.company_normalized,
                    identity.title_normalized,
                    identity.location_normalized,
                    created_at,
                    created_at,
                    updated_at,
                    updated_at,
                    created_at,
                    updated_at,
                    row_id,
                ),
            )
        else:
            cursor.execute(
                "DELETE FROM job_description_versions WHERE job_description_id = ?",
                (row_id,),
            )
            cursor.execute("DELETE FROM job_descriptions WHERE id = ?", (row_id,))

    # Re-point each canonical row's legacy application_id field to one current
    # link for backwards-compatible displays. The link table remains authoritative.
    cursor.execute("SELECT id FROM job_descriptions")
    for result in cursor.fetchall():
        job_id = int(result["id"])
        cursor.execute(
            """
            SELECT MIN(application_id) AS application_id
            FROM application_job_links
            WHERE job_description_id = ?
            """,
            (job_id,),
        )
        linked = cursor.fetchone()
        cursor.execute(
            "UPDATE job_descriptions SET application_id = ? WHERE id = ?",
            (linked["application_id"] if linked else None, job_id),
        )


def init_jd_library() -> None:
    """Create/migrate the canonical JD schema and backfill legacy rows."""
    connection = _connect()
    try:
        cursor = connection.cursor()
        _create_schema(cursor)
        _backfill_legacy_rows(cursor)
        cursor.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_job_descriptions_canonical_jd_id_unique
            ON job_descriptions(canonical_jd_id)
            WHERE canonical_jd_id IS NOT NULL
            """
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _find_compatible_canonical_row(
    cursor: sqlite3.Cursor,
    *,
    canonical_jd_id: str,
    company_normalized: str,
    title_normalized: str,
    location_normalized: str,
) -> sqlite3.Row | None:
    cursor.execute(
        "SELECT * FROM job_descriptions WHERE canonical_jd_id = ?",
        (canonical_jd_id,),
    )
    exact = cursor.fetchone()
    if exact is not None:
        return exact

    # Conservative fallback: allow a blank location on either side, but require
    # exact normalized company and title. This avoids duplicates caused only by
    # one extraction omitting a location.
    cursor.execute(
        """
        SELECT *
        FROM job_descriptions
        WHERE company_normalized = ?
          AND title_normalized = ?
          AND (
              location_normalized = ?
              OR location_normalized = ''
              OR ? = ''
          )
        ORDER BY id ASC
        LIMIT 1
        """,
        (
            company_normalized,
            title_normalized,
            location_normalized,
            location_normalized,
        ),
    )
    return cursor.fetchone()


def _delete_orphaned_job(cursor: sqlite3.Cursor, job_description_id: int) -> dict[str, Any]:
    cursor.execute(
        "SELECT canonical_jd_id, source_type FROM job_descriptions WHERE id = ?",
        (job_description_id,),
    )
    row = cursor.fetchone()
    canonical_id = str(row["canonical_jd_id"] or "") if row else ""
    source_type = str(row["source_type"] or "") if row else ""

    cursor.execute(
        "SELECT COUNT(*) AS count FROM application_job_links WHERE job_description_id = ?",
        (job_description_id,),
    )
    remaining_count = int(cursor.fetchone()["count"])

    if remaining_count == 0 and source_type != "jd_library":
        cursor.execute(
            "DELETE FROM job_description_versions WHERE job_description_id = ?",
            (job_description_id,),
        )
        cursor.execute(
            "DELETE FROM job_descriptions WHERE id = ?",
            (job_description_id,),
        )
        return {
            "deleted": True,
            "job_description_id": job_description_id,
            "canonical_jd_id": canonical_id,
            "remaining_link_count": 0,
        }

    if remaining_count == 0:
        cursor.execute(
            "UPDATE job_descriptions SET application_id = NULL WHERE id = ?",
            (job_description_id,),
        )
        return {
            "deleted": False,
            "job_description_id": job_description_id,
            "canonical_jd_id": canonical_id,
            "remaining_link_count": 0,
            "retained_as_saved_jd": True,
        }

    cursor.execute(
        """
        SELECT MIN(application_id) AS application_id
        FROM application_job_links
        WHERE job_description_id = ?
        """,
        (job_description_id,),
    )
    replacement = cursor.fetchone()
    cursor.execute(
        "UPDATE job_descriptions SET application_id = ? WHERE id = ?",
        (replacement["application_id"], job_description_id),
    )
    return {
        "deleted": False,
        "job_description_id": job_description_id,
        "canonical_jd_id": canonical_id,
        "remaining_link_count": remaining_count,
    }


def save_or_link_job_description_for_application(
    *,
    application_id: int,
    raw_text: str,
    jd_profile: dict[str, Any],
    title: str = "",
    company: str = "",
    location: str = "",
    source_type: str = "application_session",
    source_url: str = "",
) -> dict[str, Any]:
    """
    Save/link a JD without duplicating its canonical row or Chroma version.

    Returns flags used by app.py to decide whether embeddings must be created.
    """
    cleaned_text = raw_text.strip()
    if not cleaned_text:
        raise ValueError("Job description text cannot be empty.")

    final_title = (title.strip() or str(jd_profile.get("job_title") or "Untitled Job").strip())
    final_company = (company.strip() or str(jd_profile.get("company") or "Unknown Company").strip())
    final_location = _extract_location(jd_profile, location)
    now = _now()

    identity = build_job_identity(
        company=final_company,
        title=final_title,
        location=final_location,
        raw_jd_text=cleaned_text,
    )
    profile_json = _json_dumps(jd_profile)

    connection = _connect()
    try:
        cursor = connection.cursor()

        cursor.execute(
            "SELECT job_description_id FROM application_job_links WHERE application_id = ?",
            (application_id,),
        )
        existing_link = cursor.fetchone()
        previous_job_id = int(existing_link["job_description_id"]) if existing_link else None

        canonical_row = _find_compatible_canonical_row(
            cursor,
            canonical_jd_id=identity.canonical_jd_id,
            company_normalized=identity.company_normalized,
            title_normalized=identity.title_normalized,
            location_normalized=identity.location_normalized,
        )

        created_new_job = canonical_row is None
        if created_new_job:
            cursor.execute(
                """
                INSERT INTO job_descriptions (
                    application_id,
                    title,
                    company,
                    location,
                    source_type,
                    source_url,
                    raw_text,
                    jd_profile_json,
                    canonical_jd_id,
                    source_version_id,
                    company_normalized,
                    title_normalized,
                    location_normalized,
                    first_seen_at,
                    last_seen_at,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    application_id,
                    final_title,
                    final_company,
                    final_location,
                    source_type,
                    source_url.strip(),
                    cleaned_text,
                    profile_json,
                    identity.canonical_jd_id,
                    identity.source_version_id,
                    identity.company_normalized,
                    identity.title_normalized,
                    identity.location_normalized,
                    now,
                    now,
                    now,
                    now,
                ),
            )
            job_id = int(cursor.lastrowid)
            canonical_id = identity.canonical_jd_id
        else:
            job_id = int(canonical_row["id"])
            canonical_id = str(canonical_row["canonical_jd_id"])

        created_new_version = _upsert_version(
            cursor,
            job_description_id=job_id,
            source_version_id=identity.source_version_id,
            raw_text=cleaned_text,
            jd_profile_json=profile_json,
            created_at=now,
        )

        if not created_new_job:
            cursor.execute(
                """
                UPDATE job_descriptions
                SET
                    title = ?,
                    company = ?,
                    location = ?,
                    source_type = CASE
                        WHEN source_type = 'jd_library' THEN source_type
                        ELSE ?
                    END,
                    source_url = CASE
                        WHEN source_type = 'jd_library' AND source_url <> ''
                            THEN source_url
                        ELSE ?
                    END,
                    last_seen_at = ?,
                    updated_at = ?,
                    application_id = COALESCE(application_id, ?)
                WHERE id = ?
                """,
                (
                    final_title,
                    final_company,
                    final_location,
                    source_type,
                    source_url.strip(),
                    now,
                    now,
                    application_id,
                    job_id,
                ),
            )

        # A new source version becomes the latest canonical representation.
        if created_new_job or created_new_version:
            cursor.execute(
                """
                UPDATE job_descriptions
                SET
                    raw_text = ?,
                    jd_profile_json = ?,
                    source_version_id = ?,
                    last_seen_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    cleaned_text,
                    profile_json,
                    identity.source_version_id,
                    now,
                    now,
                    job_id,
                ),
            )

        created_new_link = existing_link is None or previous_job_id != job_id
        cursor.execute(
            """
            INSERT INTO application_job_links (
                application_id,
                job_description_id,
                source_version_id,
                linked_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(application_id) DO UPDATE SET
                job_description_id = excluded.job_description_id,
                source_version_id = excluded.source_version_id,
                updated_at = excluded.updated_at
            """,
            (
                application_id,
                job_id,
                identity.source_version_id,
                now,
                now,
            ),
        )

        orphaned = None
        if previous_job_id is not None and previous_job_id != job_id:
            orphaned = _delete_orphaned_job(cursor, previous_job_id)

        connection.commit()
        return {
            "job_description_id": job_id,
            "canonical_jd_id": canonical_id,
            "source_version_id": identity.source_version_id,
            "created_new_job": created_new_job,
            "created_new_version": created_new_version,
            "created_new_link": created_new_link,
            "needs_chroma_index": created_new_job or created_new_version,
            "orphaned_job_description_id": (
                orphaned["job_description_id"]
                if orphaned and orphaned["deleted"]
                else None
            ),
            "orphaned_canonical_jd_id": (
                orphaned["canonical_jd_id"]
                if orphaned and orphaned["deleted"]
                else None
            ),
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def save_or_update_job_description_for_application(**kwargs: Any) -> int:
    """Backward-compatible wrapper returning only the canonical JD row ID."""
    result = save_or_link_job_description_for_application(**kwargs)
    return int(result["job_description_id"])


def get_recent_job_descriptions(limit: int = 20) -> list[tuple]:
    """Return unique canonical JDs, not one row per application session."""
    connection = _connect()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT
                jd.id,
                MIN(link.application_id) AS application_id,
                jd.title,
                jd.company,
                jd.source_type,
                COALESCE(jd.last_seen_at, jd.updated_at, jd.created_at) AS seen_at
            FROM job_descriptions AS jd
            LEFT JOIN application_job_links AS link
                ON link.job_description_id = jd.id
            GROUP BY jd.id
            ORDER BY seen_at DESC, jd.id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [tuple(row) for row in cursor.fetchall()]
    finally:
        connection.close()


def get_job_description_by_id(jd_id: int) -> dict[str, Any] | None:
    connection = _connect()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM job_descriptions WHERE id = ?", (jd_id,))
        row = cursor.fetchone()
        if row is None:
            return None

        cursor.execute(
            """
            SELECT application_id
            FROM application_job_links
            WHERE job_description_id = ?
            ORDER BY application_id ASC
            """,
            (jd_id,),
        )
        application_ids = [int(item["application_id"]) for item in cursor.fetchall()]

        return {
            "id": jd_id,
            "application_id": application_ids[0] if application_ids else row["application_id"],
            "application_ids": application_ids,
            "application_count": len(application_ids),
            "title": row["title"],
            "company": row["company"],
            "location": row["location"] or "",
            "source_type": row["source_type"],
            "source_url": row["source_url"],
            "raw_text": row["raw_text"],
            "jd_profile": _safe_json_loads(row["jd_profile_json"]),
            "canonical_jd_id": row["canonical_jd_id"],
            "source_version_id": row["source_version_id"],
            "company_normalized": row["company_normalized"],
            "title_normalized": row["title_normalized"],
            "location_normalized": row["location_normalized"],
            "first_seen_at": row["first_seen_at"],
            "last_seen_at": row["last_seen_at"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
    finally:
        connection.close()


def save_job_description_to_library(
    *,
    raw_text: str,
    jd_profile: dict[str, Any],
    title: str = "",
    company: str = "",
    location: str = "",
    source_url: str = "",
) -> dict[str, Any]:
    """Persist/reuse one standalone JD without creating an application link."""
    cleaned_text = str(raw_text or "").strip()
    if not cleaned_text:
        raise ValueError("Job description text cannot be empty.")
    if not isinstance(jd_profile, dict) or not jd_profile:
        raise ValueError("A structured job-description profile is required.")

    final_title = str(title or jd_profile.get("job_title") or "").strip()
    final_company = str(company or jd_profile.get("company") or "").strip()
    final_location = _extract_location(jd_profile, location)
    if not final_title or not final_company:
        raise ValueError(
            "Saving to the JD Library requires a job title and company. "
            "Add the missing metadata rather than saving an ambiguous identity."
        )

    identity = build_job_identity(
        company=final_company,
        title=final_title,
        location=final_location,
        raw_jd_text=cleaned_text,
    )
    profile = dict(jd_profile)
    profile["job_title"] = final_title
    profile["company"] = final_company
    profile["location"] = final_location
    profile_json = _json_dumps(profile)
    now = _now()

    connection = _connect()
    try:
        cursor = connection.cursor()
        canonical_row = _find_compatible_canonical_row(
            cursor,
            canonical_jd_id=identity.canonical_jd_id,
            company_normalized=identity.company_normalized,
            title_normalized=identity.title_normalized,
            location_normalized=identity.location_normalized,
        )
        created_new_job = canonical_row is None
        if created_new_job:
            cursor.execute(
                """
                INSERT INTO job_descriptions (
                    application_id, title, company, location, source_type,
                    source_url, raw_text, jd_profile_json, canonical_jd_id,
                    source_version_id, company_normalized, title_normalized,
                    location_normalized, first_seen_at, last_seen_at,
                    created_at, updated_at
                ) VALUES (NULL, ?, ?, ?, 'jd_library', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    final_title,
                    final_company,
                    final_location,
                    str(source_url or "").strip(),
                    cleaned_text,
                    profile_json,
                    identity.canonical_jd_id,
                    identity.source_version_id,
                    identity.company_normalized,
                    identity.title_normalized,
                    identity.location_normalized,
                    now,
                    now,
                    now,
                    now,
                ),
            )
            job_id = int(cursor.lastrowid)
        else:
            job_id = int(canonical_row["id"])

        created_new_version = _upsert_version(
            cursor,
            job_description_id=job_id,
            source_version_id=identity.source_version_id,
            raw_text=cleaned_text,
            jd_profile_json=profile_json,
            created_at=now,
        )
        cursor.execute(
            """
            UPDATE job_descriptions
            SET title = ?, company = ?, location = ?, source_type = 'jd_library',
                source_url = CASE WHEN ? <> '' THEN ? ELSE source_url END,
                last_seen_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                final_title,
                final_company,
                final_location,
                str(source_url or "").strip(),
                str(source_url or "").strip(),
                now,
                now,
                job_id,
            ),
        )
        if created_new_job or created_new_version:
            cursor.execute(
                """
                UPDATE job_descriptions
                SET raw_text = ?, jd_profile_json = ?, source_version_id = ?,
                    last_seen_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    cleaned_text,
                    profile_json,
                    identity.source_version_id,
                    now,
                    now,
                    job_id,
                ),
            )
        connection.commit()
        return {
            "job_description_id": job_id,
            "canonical_jd_id": identity.canonical_jd_id,
            "source_version_id": identity.source_version_id,
            "created_new_job": created_new_job,
            "created_new_version": created_new_version,
            "created_new_link": False,
            "needs_chroma_index": created_new_job or created_new_version,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_job_description_by_application_id(application_id: int) -> dict[str, Any] | None:
    connection = _connect()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT job_description_id
            FROM application_job_links
            WHERE application_id = ?
            """,
            (application_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        job_id = int(row["job_description_id"])
    finally:
        connection.close()
    return get_job_description_by_id(job_id)


def get_exact_job_description_for_application(
    application_id: int,
) -> dict[str, Any] | None:
    """Return the exact JD version linked to one application.

    Unlike ``get_job_description_by_application_id``, this resolver joins the
    stored ``source_version_id`` to ``job_description_versions``.  All text,
    profile, hashes, and canonical requirements in the returned snapshot are
    therefore derived from that one immutable linked version.
    """
    from analysis_stability.stable_evidence_scoring import (
        canonicalise_requirements,
    )

    connection = _connect()
    try:
        row = connection.execute(
            """
            SELECT
                link.application_id,
                link.job_description_id,
                link.source_version_id AS linked_source_version_id,
                link.linked_at,
                link.updated_at AS link_updated_at,
                version.raw_text AS version_raw_text,
                version.jd_profile_json AS version_jd_profile_json,
                version.created_at AS version_created_at,
                jd.canonical_jd_id
            FROM application_job_links AS link
            JOIN job_descriptions AS jd
              ON jd.id = link.job_description_id
            JOIN job_description_versions AS version
              ON version.job_description_id = link.job_description_id
             AND version.source_version_id = link.source_version_id
            WHERE link.application_id = ?
            LIMIT 1
            """,
            (int(application_id),),
        ).fetchone()
    finally:
        connection.close()

    if row is None:
        return None

    raw_text = str(row["version_raw_text"] or "")
    profile = _safe_json_loads(row["version_jd_profile_json"])
    if not raw_text.strip() or not isinstance(profile, dict) or not profile:
        raise ValueError(
            "The linked JD version is missing its raw text or parsed profile."
        )

    title = str(profile.get("job_title") or profile.get("title") or "").strip()
    company = str(
        profile.get("company") or profile.get("company_name") or ""
    ).strip()
    location = _extract_location(profile, "")
    if not title or not company:
        raise ValueError(
            "The linked JD version lacks title/company identity in its profile."
        )

    identity = build_job_identity(
        company=company,
        title=title,
        location=location,
        raw_jd_text=raw_text,
    )
    linked_version = str(row["linked_source_version_id"] or "")
    stored_canonical_id = str(row["canonical_jd_id"] or "")
    if identity.source_version_id != linked_version:
        raise ValueError(
            "The linked JD source-version identity does not reproduce from its text."
        )
    if identity.canonical_jd_id != stored_canonical_id:
        raise ValueError(
            "The linked JD canonical identity does not reproduce from its profile."
        )

    canonical = canonicalise_requirements(
        jd_profile=profile,
        raw_jd_text=raw_text,
    )
    requirement_rows = [
        dict(requirement)
        for requirement in canonical.get("requirements", [])
        if isinstance(requirement, dict)
    ]
    compact_rows = [
        {
            "requirement_id": str(row.get("requirement_id") or ""),
            "text": " ".join(str(row.get("text") or "").split()),
            "importance": str(row.get("importance") or ""),
            "atomic_group_id": str(row.get("atomic_group_id") or ""),
            "group_weight_fraction": row.get("group_weight_fraction"),
        }
        for row in requirement_rows
    ]
    canonical_payload = json.dumps(
        compact_rows,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )

    return {
        "id": int(row["job_description_id"]),
        "library_jd_id": int(row["job_description_id"]),
        "application_id": int(row["application_id"]),
        "title": title,
        "company": company,
        "location": location,
        "raw_text": raw_text,
        "jd_profile": profile,
        "canonical_jd_id": stored_canonical_id,
        "source_version_id": linked_version,
        "raw_jd_sha256": hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
        "canonical_requirements": requirement_rows,
        "canonical_requirement_ids": sorted(
            str(requirement.get("requirement_id") or "")
            for requirement in requirement_rows
            if str(requirement.get("requirement_id") or "").strip()
        ),
        "canonical_requirement_fingerprint": hashlib.sha256(
            canonical_payload.encode("utf-8")
        ).hexdigest(),
        "canonicalisation": canonical,
        "source_application_link": {
            "application_id": int(row["application_id"]),
            "job_description_id": int(row["job_description_id"]),
            "source_version_id": linked_version,
            "linked_at": str(row["linked_at"] or ""),
            "updated_at": str(row["link_updated_at"] or ""),
        },
        "version_created_at": str(row["version_created_at"] or ""),
    }


def get_all_job_descriptions(limit: int = 200) -> list[dict[str, Any]]:
    connection = _connect()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT id
            FROM job_descriptions
            ORDER BY COALESCE(last_seen_at, updated_at, created_at) DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        )
        ids = [int(row["id"]) for row in cursor.fetchall()]
    finally:
        connection.close()

    return [job for job_id in ids if (job := get_job_description_by_id(job_id))]


def get_jd_library_stats() -> dict[str, int]:
    connection = _connect()
    try:
        cursor = connection.cursor()
        stats: dict[str, int] = {}
        for key, table in (
            ("canonical_jobs", "job_descriptions"),
            ("versions", "job_description_versions"),
            ("session_links", "application_job_links"),
        ):
            cursor.execute(f"SELECT COUNT(*) AS count FROM {table}")
            stats[key] = int(cursor.fetchone()["count"])
        return stats
    finally:
        connection.close()


def delete_job_description(jd_id: int) -> None:
    """Delete a canonical JD, all versions and all session links."""
    connection = _connect()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "DELETE FROM application_job_links WHERE job_description_id = ?",
            (jd_id,),
        )
        cursor.execute(
            "DELETE FROM job_description_versions WHERE job_description_id = ?",
            (jd_id,),
        )
        cursor.execute("DELETE FROM job_descriptions WHERE id = ?", (jd_id,))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def unlink_job_description_from_application(application_id: int) -> dict[str, Any]:
    """Unlink one session; delete the canonical JD only when no sessions remain."""
    connection = _connect()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT job_description_id FROM application_job_links WHERE application_id = ?",
            (application_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return {
                "job_description_id": None,
                "canonical_jd_id": None,
                "deleted_canonical_job": False,
                "remaining_link_count": 0,
            }

        job_id = int(row["job_description_id"])
        cursor.execute(
            "DELETE FROM application_job_links WHERE application_id = ?",
            (application_id,),
        )
        result = _delete_orphaned_job(cursor, job_id)
        connection.commit()
        return {
            "job_description_id": job_id,
            "canonical_jd_id": result["canonical_jd_id"],
            "deleted_canonical_job": bool(result["deleted"]),
            "remaining_link_count": int(result["remaining_link_count"]),
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def delete_job_description_by_application_id(application_id: int) -> None:
    """Backward-compatible wrapper around session unlinking."""
    unlink_job_description_from_application(application_id)


def get_job_description_versions(jd_id: int) -> list[dict[str, Any]]:
    """Return stored source versions for one canonical JD, newest first."""
    connection = _connect()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT source_version_id, raw_text, jd_profile_json, created_at
            FROM job_description_versions
            WHERE job_description_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (jd_id,),
        )
        return [
            {
                "source_version_id": row["source_version_id"],
                "raw_text": row["raw_text"],
                "jd_profile": _safe_json_loads(row["jd_profile_json"]),
                "created_at": row["created_at"],
            }
            for row in cursor.fetchall()
        ]
    finally:
        connection.close()


def get_exact_job_description_version(
    jd_id: int,
    source_version_id: str,
) -> dict[str, Any] | None:
    """Return and verify one exact authoritative saved JD version."""
    from analysis_stability.stable_evidence_scoring import (
        canonicalise_requirements,
    )

    connection = _connect()
    try:
        row = connection.execute(
            """
            SELECT
                jd.id AS job_description_id,
                jd.canonical_jd_id,
                jd.source_type,
                jd.source_url,
                version.source_version_id,
                version.raw_text,
                version.jd_profile_json,
                version.created_at
            FROM job_descriptions AS jd
            JOIN job_description_versions AS version
              ON version.job_description_id = jd.id
            WHERE jd.id = ? AND version.source_version_id = ?
            LIMIT 1
            """,
            (int(jd_id), str(source_version_id or "")),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        return None

    raw_text = str(row["raw_text"] or "")
    profile = _safe_json_loads(row["jd_profile_json"])
    if not raw_text.strip() or not profile:
        raise ValueError(
            "The saved JD version is missing its raw text or structured profile."
        )
    title = str(profile.get("job_title") or profile.get("title") or "").strip()
    company = str(
        profile.get("company") or profile.get("company_name") or ""
    ).strip()
    location = _extract_location(profile, "")
    if not title or not company:
        raise ValueError(
            "The saved JD version lacks title/company identity in its profile."
        )
    identity = build_job_identity(
        company=company,
        title=title,
        location=location,
        raw_jd_text=raw_text,
    )
    stored_version = str(row["source_version_id"] or "")
    stored_canonical = str(row["canonical_jd_id"] or "")
    if identity.source_version_id != stored_version:
        raise ValueError(
            "The saved JD source-version identity does not reproduce from its text."
        )
    if identity.canonical_jd_id != stored_canonical:
        raise ValueError(
            "The saved JD canonical identity does not reproduce from its profile."
        )

    canonical = canonicalise_requirements(
        jd_profile=profile,
        raw_jd_text=raw_text,
    )
    requirements = [
        dict(item)
        for item in canonical.get("requirements", []) or []
        if isinstance(item, dict)
    ]
    compact = [
        {
            "requirement_id": str(item.get("requirement_id") or ""),
            "text": " ".join(str(item.get("text") or "").split()),
            "importance": str(item.get("importance") or ""),
            "atomic_group_id": str(item.get("atomic_group_id") or ""),
            "group_weight_fraction": item.get("group_weight_fraction"),
        }
        for item in requirements
    ]
    payload = json.dumps(
        compact,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return {
        "id": int(row["job_description_id"]),
        "library_jd_id": int(row["job_description_id"]),
        "title": title,
        "company": company,
        "location": location,
        "source_type": str(row["source_type"] or ""),
        "source_url": str(row["source_url"] or ""),
        "raw_text": raw_text,
        "jd_profile": profile,
        "canonical_jd_id": stored_canonical,
        "source_version_id": stored_version,
        "raw_jd_sha256": hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
        "canonical_requirements": requirements,
        "canonical_requirement_ids": sorted(
            str(item.get("requirement_id") or "")
            for item in requirements
            if str(item.get("requirement_id") or "").strip()
        ),
        "canonical_requirement_fingerprint": hashlib.sha256(
            payload.encode("utf-8")
        ).hexdigest(),
        "canonicalisation": canonical,
        "version_created_at": str(row["created_at"] or ""),
    }


def get_application_job_links() -> list[dict[str, Any]]:
    """Return session-to-canonical-JD links for diagnostics/tests."""
    connection = _connect()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT application_id, job_description_id, source_version_id, linked_at, updated_at
            FROM application_job_links
            ORDER BY application_id ASC
            """
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        connection.close()

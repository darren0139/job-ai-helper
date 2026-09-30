from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

APPLICATION_TRACKER_VERSION = "application-tracker-v2.1"

DB_PATH = Path("data/applications.db")

STATUS_OPTIONS = (
    "not_applied",
    "applied",
    "screening",
    "interview",
    "offer",
    "rejected",
    "withdrawn",
)

STATUS_LABELS = {
    "not_applied": "Not Applied",
    "applied": "Applied",
    "screening": "Screening",
    "interview": "Interview",
    "offer": "Offer",
    "rejected": "Rejected",
    "withdrawn": "Withdrawn",
}

TERMINAL_STATUSES = {"rejected", "withdrawn"}


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _today() -> str:
    return date.today().isoformat()


def _table_exists(cursor: sqlite3.Cursor, table_name: str) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        LIMIT 1
        """,
        (table_name,),
    )
    return cursor.fetchone() is not None


def _columns(cursor: sqlite3.Cursor, table_name: str) -> set[str]:
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {str(row[1]) for row in cursor.fetchall()}


def _date_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if not text or text.lower() in {"nat", "none", "nan"}:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        try:
            return date.fromisoformat(text[:10]).isoformat()
        except ValueError as exc:
            raise ValueError(f"Invalid date value: {value!r}") from exc


def normalise_status(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "not_applied"
    lowered = text.lower().replace("-", "_").replace(" ", "_")
    if lowered in STATUS_OPTIONS:
        return lowered
    reverse = {label.lower(): key for key, label in STATUS_LABELS.items()}
    if text.lower() in reverse:
        return reverse[text.lower()]
    raise ValueError(
        f"Unknown application status {value!r}. "
        f"Expected one of: {', '.join(STATUS_LABELS.values())}."
    )


def status_label(value: Any) -> str:
    return STATUS_LABELS.get(normalise_status(value), str(value or ""))


def _create_v2_schema(cursor: sqlite3.Cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS tracked_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER UNIQUE,
            company TEXT NOT NULL DEFAULT '',
            job_title TEXT NOT NULL DEFAULT '',
            location TEXT NOT NULL DEFAULT '',
            job_url TEXT NOT NULL DEFAULT '',
            job_description TEXT NOT NULL DEFAULT '',
            overall_score INTEGER,
            source_type TEXT NOT NULL DEFAULT 'application_session',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_tracked_jobs_application_id
        ON tracked_jobs(application_id)
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS application_tracking (
            tracked_job_id INTEGER PRIMARY KEY,
            applied INTEGER NOT NULL DEFAULT 0,
            applied_at TEXT,
            status TEXT NOT NULL DEFAULT 'not_applied',
            completed INTEGER NOT NULL DEFAULT 0,
            completed_at TEXT,
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS application_status_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tracked_job_id INTEGER NOT NULL,
            application_id INTEGER,
            from_status TEXT,
            to_status TEXT NOT NULL,
            occurred_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_application_status_history_job
        ON application_status_history(tracked_job_id, occurred_at)
        """
    )


def _legacy_tracking_needs_migration(cursor: sqlite3.Cursor) -> bool:
    if not _table_exists(cursor, "application_tracking"):
        return False
    columns = _columns(cursor, "application_tracking")
    return "application_id" in columns and "tracked_job_id" not in columns


def _extract_session_location(
    cursor: sqlite3.Cursor,
    application_id: int,
) -> str:
    if not _table_exists(cursor, "application_job_links"):
        return ""
    if not _table_exists(cursor, "job_descriptions"):
        return ""
    try:
        row = cursor.execute(
            """
            SELECT COALESCE(jd.location, '')
            FROM application_job_links AS link
            JOIN job_descriptions AS jd
              ON jd.id = link.job_description_id
            WHERE link.application_id = ?
            LIMIT 1
            """,
            (application_id,),
        ).fetchone()
    except sqlite3.Error:
        return ""
    return str(row[0] or "") if row else ""


def _sync_application_sessions(
    cursor: sqlite3.Cursor,
    now: str,
) -> None:
    if not _table_exists(cursor, "applications"):
        return

    app_columns = _columns(cursor, "applications")
    required = {"id", "company", "job_title", "created_at", "updated_at"}
    if not required.issubset(app_columns):
        return

    score_expr = "overall_score" if "overall_score" in app_columns else "NULL"
    rows = cursor.execute(
        f"""
        SELECT
            id,
            COALESCE(company, ''),
            COALESCE(job_title, ''),
            {score_expr},
            COALESCE(created_at, ?),
            COALESCE(updated_at, created_at, ?)
        FROM applications
        """,
        (now, now),
    ).fetchall()

    for row in rows:
        application_id = int(row[0])
        location = _extract_session_location(cursor, application_id)
        cursor.execute(
            """
            INSERT OR IGNORE INTO tracked_jobs (
                application_id,
                company,
                job_title,
                location,
                job_url,
                job_description,
                overall_score,
                source_type,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, '', '', ?, 'application_session', ?, ?)
            """,
            (
                application_id,
                str(row[1] or ""),
                str(row[2] or ""),
                location,
                row[3],
                str(row[4] or now),
                str(row[5] or now),
            ),
        )
        cursor.execute(
            """
            UPDATE tracked_jobs
            SET
                company = ?,
                job_title = ?,
                location = CASE
                    WHEN TRIM(?) != '' THEN ?
                    ELSE location
                END,
                overall_score = ?,
                updated_at = ?
            WHERE application_id = ?
            """,
            (
                str(row[1] or ""),
                str(row[2] or ""),
                location,
                location,
                row[3],
                str(row[5] or now),
                application_id,
            ),
        )


def _migrate_v1_tracking(cursor: sqlite3.Cursor, now: str) -> None:
    if not _legacy_tracking_needs_migration(cursor):
        return

    cursor.execute(
        "ALTER TABLE application_tracking RENAME TO application_tracking_v1_backup"
    )
    _create_v2_schema(cursor)
    _sync_application_sessions(cursor, now)

    legacy_columns = _columns(cursor, "application_tracking_v1_backup")
    selectable = {
        "application_id",
        "applied",
        "applied_at",
        "status",
        "completed",
        "completed_at",
        "notes",
        "created_at",
        "updated_at",
    }
    if "application_id" not in legacy_columns:
        return

    column_order = [name for name in (
        "application_id",
        "applied",
        "applied_at",
        "status",
        "completed",
        "completed_at",
        "notes",
        "created_at",
        "updated_at",
    ) if name in legacy_columns]

    rows = cursor.execute(
        "SELECT " + ", ".join(column_order) + " FROM application_tracking_v1_backup"
    ).fetchall()

    for legacy_row in rows:
        values = dict(zip(column_order, legacy_row))
        application_id = int(values["application_id"])
        tracked = cursor.execute(
            "SELECT id FROM tracked_jobs WHERE application_id = ?",
            (application_id,),
        ).fetchone()
        if tracked is None:
            continue
        tracked_job_id = int(tracked[0])
        status = normalise_status(values.get("status") or "not_applied")
        applied = bool(values.get("applied")) or status != "not_applied"
        applied_at = _date_text(values.get("applied_at"))
        completed = bool(values.get("completed"))
        completed_at = _date_text(values.get("completed_at"))
        created_at = str(values.get("created_at") or now)
        updated_at = str(values.get("updated_at") or now)
        cursor.execute(
            """
            INSERT OR REPLACE INTO application_tracking (
                tracked_job_id,
                applied,
                applied_at,
                status,
                completed,
                completed_at,
                notes,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tracked_job_id,
                int(applied),
                applied_at,
                status,
                int(completed),
                completed_at,
                str(values.get("notes") or ""),
                created_at,
                updated_at,
            ),
        )
        if status != "not_applied":
            cursor.execute(
                """
                INSERT INTO application_status_history (
                    tracked_job_id,
                    application_id,
                    from_status,
                    to_status,
                    occurred_at,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    tracked_job_id,
                    application_id,
                    "not_applied",
                    status,
                    applied_at or updated_at,
                    now,
                ),
            )

    cursor.execute("DROP TABLE application_tracking_v1_backup")


def _ensure_tracking_rows(cursor: sqlite3.Cursor, now: str) -> None:
    cursor.execute(
        """
        INSERT OR IGNORE INTO application_tracking (
            tracked_job_id,
            applied,
            applied_at,
            status,
            completed,
            completed_at,
            notes,
            created_at,
            updated_at
        )
        SELECT
            id,
            0,
            NULL,
            'not_applied',
            0,
            NULL,
            '',
            ?,
            ?
        FROM tracked_jobs
        """,
        (now, now),
    )



def _repair_lifecycle_invariants(
    cursor: sqlite3.Cursor,
    now: str,
) -> None:
    # Repair contradictory V2 rows without inventing historical events.
    today = _today()

    cursor.execute(
        """
        UPDATE application_tracking
        SET
            status = 'applied',
            updated_at = ?
        WHERE applied = 1
          AND status = 'not_applied'
        """,
        (now,),
    )

    cursor.execute(
        """
        UPDATE application_tracking
        SET
            applied = 1,
            applied_at = COALESCE(
                NULLIF(applied_at, ''),
                SUBSTR(NULLIF(updated_at, ''), 1, 10),
                ?
            ),
            updated_at = ?
        WHERE status != 'not_applied'
          AND applied = 0
        """,
        (today, now),
    )

    cursor.execute(
        """
        UPDATE application_tracking
        SET
            applied_at = NULL,
            updated_at = ?
        WHERE applied = 0
          AND applied_at IS NOT NULL
        """,
        (now,),
    )


def init_application_tracking_schema() -> None:
    now = _now()
    connection = _connect()
    try:
        cursor = connection.cursor()
        if _legacy_tracking_needs_migration(cursor):
            _migrate_v1_tracking(cursor, now)
        else:
            _create_v2_schema(cursor)
        _sync_application_sessions(cursor, now)
        _ensure_tracking_rows(cursor, now)
        _repair_lifecycle_invariants(cursor, now)
        connection.commit()
    finally:
        connection.close()


def list_application_tracking_rows() -> list[dict[str, Any]]:
    init_application_tracking_schema()
    connection = _connect()
    try:
        rows = connection.execute(
            """
            SELECT
                jobs.id AS tracked_job_id,
                jobs.application_id,
                jobs.company,
                jobs.job_title,
                jobs.location,
                jobs.job_url,
                jobs.job_description,
                jobs.overall_score,
                jobs.source_type,
                tracking.applied,
                tracking.applied_at,
                tracking.status,
                tracking.completed,
                tracking.completed_at,
                tracking.notes,
                jobs.created_at,
                tracking.updated_at
            FROM tracked_jobs AS jobs
            JOIN application_tracking AS tracking
              ON tracking.tracked_job_id = jobs.id
            ORDER BY
                COALESCE(tracking.applied_at, jobs.created_at) DESC,
                jobs.id DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def list_application_status_history(
    tracked_job_ids: Iterable[int] | None = None,
) -> list[dict[str, Any]]:
    init_application_tracking_schema()
    connection = _connect()
    try:
        sql = """
            SELECT
                history.id,
                history.tracked_job_id,
                history.application_id,
                jobs.company,
                jobs.job_title,
                history.from_status,
                history.to_status,
                history.occurred_at,
                history.created_at
            FROM application_status_history AS history
            JOIN tracked_jobs AS jobs
              ON jobs.id = history.tracked_job_id
        """
        params: list[Any] = []
        if tracked_job_ids is not None:
            ids = [int(value) for value in tracked_job_ids]
            if not ids:
                return []
            placeholders = ",".join("?" for _ in ids)
            sql += f" WHERE history.tracked_job_id IN ({placeholders})"
            params.extend(ids)
        sql += " ORDER BY history.occurred_at ASC, history.id ASC"
        rows = connection.execute(sql, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def add_manual_tracked_job(
    *,
    company: str,
    job_title: str,
    location: str = "",
    job_url: str = "",
    job_description: str = "",
    applied: bool = False,
    applied_at: Any = None,
    status: str = "not_applied",
    completed: bool = False,
    completed_at: Any = None,
    notes: str = "",
) -> int:
    cleaned_company = str(company or "").strip()
    cleaned_title = str(job_title or "").strip()
    if not cleaned_company:
        raise ValueError("Company is required.")
    if not cleaned_title:
        raise ValueError("Role is required.")

    init_application_tracking_schema()
    now = _now()
    connection = _connect()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO tracked_jobs (
                application_id,
                company,
                job_title,
                location,
                job_url,
                job_description,
                overall_score,
                source_type,
                created_at,
                updated_at
            ) VALUES (
                NULL, ?, ?, ?, ?, ?, NULL, 'manual', ?, ?
            )
            """,
            (
                cleaned_company,
                cleaned_title,
                str(location or "").strip(),
                str(job_url or "").strip(),
                str(job_description or "").strip(),
                now,
                now,
            ),
        )
        tracked_job_id = int(cursor.lastrowid)
        connection.commit()
    finally:
        connection.close()

    update_application_tracking(
        tracked_job_id=tracked_job_id,
        applied=applied,
        applied_at=applied_at,
        status=status,
        completed=completed,
        completed_at=completed_at,
        notes=notes,
    )
    return tracked_job_id


def _resolve_tracked_job_id(
    cursor: sqlite3.Cursor,
    *,
    tracked_job_id: int | None,
    application_id: int | None,
) -> int:
    if tracked_job_id is not None:
        row = cursor.execute(
            "SELECT id FROM tracked_jobs WHERE id = ?",
            (int(tracked_job_id),),
        ).fetchone()
        if row is None:
            raise ValueError(f"Unknown tracked job #{tracked_job_id}.")
        return int(row[0])

    if application_id is None:
        raise ValueError("tracked_job_id or application_id is required.")

    row = cursor.execute(
        "SELECT id FROM tracked_jobs WHERE application_id = ?",
        (int(application_id),),
    ).fetchone()
    if row is None:
        raise ValueError(
            f"Application session #{application_id} is not available in the tracker."
        )
    return int(row[0])


def update_application_tracking(
    *,
    tracked_job_id: int | None = None,
    application_id: int | None = None,
    applied: bool,
    applied_at: Any = None,
    status: str,
    completed: bool,
    completed_at: Any = None,
    notes: str = "",
) -> dict[str, Any]:
    init_application_tracking_schema()
    normalized_status = normalise_status(status)
    applied_value = bool(applied)
    completed_value = bool(completed)

    if normalized_status != "not_applied":
        applied_value = True
    elif applied_value:
        normalized_status = "applied"
    if not applied_value:
        normalized_status = "not_applied"

    applied_date = _date_text(applied_at)
    completed_date = _date_text(completed_at)

    if applied_value and applied_date is None:
        applied_date = _today()
    if not applied_value:
        applied_date = None

    if completed_value and completed_date is None:
        completed_date = _today()
    if not completed_value:
        completed_date = None

    now = _now()
    connection = _connect()
    try:
        cursor = connection.cursor()
        resolved_id = _resolve_tracked_job_id(
            cursor,
            tracked_job_id=tracked_job_id,
            application_id=application_id,
        )
        job_row = cursor.execute(
            """
            SELECT application_id
            FROM tracked_jobs
            WHERE id = ?
            """,
            (resolved_id,),
        ).fetchone()
        app_id = job_row[0] if job_row else None

        previous = cursor.execute(
            """
            SELECT status
            FROM application_tracking
            WHERE tracked_job_id = ?
            """,
            (resolved_id,),
        ).fetchone()
        previous_status = normalise_status(previous[0] if previous else "not_applied")

        cursor.execute(
            """
            INSERT INTO application_tracking (
                tracked_job_id,
                applied,
                applied_at,
                status,
                completed,
                completed_at,
                notes,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(tracked_job_id) DO UPDATE SET
                applied = excluded.applied,
                applied_at = excluded.applied_at,
                status = excluded.status,
                completed = excluded.completed,
                completed_at = excluded.completed_at,
                notes = excluded.notes,
                updated_at = excluded.updated_at
            """,
            (
                resolved_id,
                int(applied_value),
                applied_date,
                normalized_status,
                int(completed_value),
                completed_date,
                str(notes or ""),
                now,
                now,
            ),
        )

        if previous_status != normalized_status:
            occurred_at = (
                applied_date
                if previous_status == "not_applied"
                and normalized_status != "not_applied"
                and applied_date
                else now
            )
            cursor.execute(
                """
                INSERT INTO application_status_history (
                    tracked_job_id,
                    application_id,
                    from_status,
                    to_status,
                    occurred_at,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    resolved_id,
                    app_id,
                    previous_status,
                    normalized_status,
                    occurred_at,
                    now,
                ),
            )

        connection.commit()
        row = cursor.execute(
            """
            SELECT
                tracked_job_id,
                applied,
                applied_at,
                status,
                completed,
                completed_at,
                notes,
                created_at,
                updated_at
            FROM application_tracking
            WHERE tracked_job_id = ?
            """,
            (resolved_id,),
        ).fetchone()
        return dict(row) if row else {}
    finally:
        connection.close()


def delete_application_tracking(application_id: int) -> int:
    init_application_tracking_schema()
    connection = _connect()
    try:
        cursor = connection.cursor()
        row = cursor.execute(
            "SELECT id FROM tracked_jobs WHERE application_id = ?",
            (int(application_id),),
        ).fetchone()
        if row is None:
            return 0
        tracked_job_id = int(row[0])
        cursor.execute(
            "DELETE FROM application_status_history WHERE tracked_job_id = ?",
            (tracked_job_id,),
        )
        cursor.execute(
            "DELETE FROM application_tracking WHERE tracked_job_id = ?",
            (tracked_job_id,),
        )
        cursor.execute(
            "DELETE FROM tracked_jobs WHERE id = ?",
            (tracked_job_id,),
        )
        connection.commit()
        return 1
    finally:
        connection.close()

# V1 compatibility aliases
# Older Application Tracker wiring used this shorter initializer name.
init_application_tracking = init_application_tracking_schema


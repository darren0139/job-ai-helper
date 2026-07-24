"""
Persistent tailored résumé generations for application sessions.

A generation stores the structured Projects/Skills inputs and the latest fitted
DOCX/PDF result. The source uploaded résumé remains managed separately.
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


DB_PATH = Path("data/applications.db")
TAILORED_RESUME_DIR = Path("outputs/tailored_resumes")
PREVIEW_DIR = Path("outputs/resume_previews")
TAILORING_PERSISTENCE_VERSION = "tailored-session-persistence-v1"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _dump(value: Any) -> str:
    if value is None:
        return ""
    return json.dumps(
        value,
        ensure_ascii=False,
        default=str,
    )


def _load(value: Any) -> Any:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _existing_path(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    path = Path(text)
    return str(path) if path.exists() else ""


def init_application_tailoring_versions() -> None:
    """Create the tailored-generation table and indexes."""
    connection = _connect()
    cursor = connection.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS application_tailoring_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            generation_id TEXT NOT NULL,
            persistence_version TEXT NOT NULL,
            candidate_pool_json TEXT,
            project_inputs_json TEXT,
            fit_estimate_json TEXT,
            projects_json TEXT,
            skills_json TEXT,
            fit_result_json TEXT,
            generation_settings_json TEXT,
            docx_path TEXT,
            pdf_path TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(application_id, generation_id)
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
            idx_application_tailoring_versions_latest
        ON application_tailoring_versions (
            application_id,
            updated_at DESC,
            id DESC
        )
        """
    )
    connection.commit()
    connection.close()


def save_application_tailoring_generation(
    *,
    application_id: int,
    generation_id: str,
    candidate_pool: Any = None,
    project_inputs: Any = None,
    fit_estimate: Any = None,
    projects: Any = None,
    skills: Any = None,
    fit_result: Any = None,
    generation_settings: Any = None,
    docx_path: str | Path | None = None,
    pdf_path: str | Path | None = None,
) -> int:
    """
    Insert or update one generation.

    Arguments left as ``None`` preserve the stored value. Empty dictionaries and
    lists are saved deliberately.
    """
    if int(application_id) <= 0:
        raise ValueError("application_id must be a positive integer.")

    cleaned_generation_id = str(generation_id or "").strip()
    if not cleaned_generation_id:
        raise ValueError("generation_id is required.")

    init_application_tailoring_versions()
    now = datetime.now().isoformat(timespec="seconds")
    connection = _connect()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT OR IGNORE INTO application_tailoring_versions (
            application_id,
            generation_id,
            persistence_version,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            int(application_id),
            cleaned_generation_id,
            TAILORING_PERSISTENCE_VERSION,
            now,
            now,
        ),
    )

    updates: dict[str, Any] = {
        "persistence_version": TAILORING_PERSISTENCE_VERSION,
        "updated_at": now,
    }

    json_values = {
        "candidate_pool_json": candidate_pool,
        "project_inputs_json": project_inputs,
        "fit_estimate_json": fit_estimate,
        "projects_json": projects,
        "skills_json": skills,
        "fit_result_json": fit_result,
        "generation_settings_json": generation_settings,
    }
    for column, value in json_values.items():
        if value is not None:
            updates[column] = _dump(value)

    if docx_path is not None:
        updates["docx_path"] = str(docx_path)
    if pdf_path is not None:
        updates["pdf_path"] = str(pdf_path)

    if isinstance(fit_result, dict):
        if docx_path is None and fit_result.get("docx_path"):
            updates["docx_path"] = str(fit_result["docx_path"])
        if pdf_path is None and fit_result.get("pdf_path"):
            updates["pdf_path"] = str(fit_result["pdf_path"])

    assignment_sql = ", ".join(
        f"{column} = ?"
        for column in updates
    )
    cursor.execute(
        f"""
        UPDATE application_tailoring_versions
        SET {assignment_sql}
        WHERE application_id = ?
          AND generation_id = ?
        """,
        (
            *updates.values(),
            int(application_id),
            cleaned_generation_id,
        ),
    )

    cursor.execute(
        """
        SELECT id
        FROM application_tailoring_versions
        WHERE application_id = ?
          AND generation_id = ?
        """,
        (
            int(application_id),
            cleaned_generation_id,
        ),
    )
    row = cursor.fetchone()
    connection.commit()
    connection.close()

    if row is None:
        raise RuntimeError("Failed to persist tailored résumé generation.")
    return int(row["id"])


def get_latest_application_tailoring(
    application_id: int,
) -> dict[str, Any] | None:
    """Load the most recently updated generation for one application."""
    init_application_tailoring_versions()
    connection = _connect()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT *
        FROM application_tailoring_versions
        WHERE application_id = ?
        ORDER BY updated_at DESC, id DESC
        LIMIT 1
        """,
        (int(application_id),),
    )
    row = cursor.fetchone()
    connection.close()

    if row is None:
        return None

    return {
        "id": int(row["id"]),
        "application_id": int(row["application_id"]),
        "generation_id": row["generation_id"],
        "persistence_version": row["persistence_version"],
        "candidate_pool": _load(row["candidate_pool_json"]),
        "project_inputs": _load(row["project_inputs_json"]),
        "fit_estimate": _load(row["fit_estimate_json"]),
        "projects": _load(row["projects_json"]),
        "skills": _load(row["skills_json"]),
        "fit_result": _load(row["fit_result_json"]),
        "generation_settings": _load(row["generation_settings_json"]),
        "docx_path": _existing_path(row["docx_path"]),
        "pdf_path": _existing_path(row["pdf_path"]),
        "stored_docx_path": str(row["docx_path"] or ""),
        "stored_pdf_path": str(row["pdf_path"] or ""),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }



_TAILORED_RESUME_TIMESTAMP_RE = re.compile(
    r"_tailored_resume_"
    r"(?P<timestamp>\d{8}_\d{6}(?:_\d{6})?)"
    r"\.docx$",
    re.IGNORECASE,
)


def _legacy_tailored_resume_sort_key(
    path: Path,
) -> tuple[int, str, int, str]:
    """
    Prefer the timestamp embedded in standard generated filenames.

    Standard names use:
        app_<id>_tailored_resume_YYYYMMDD_HHMMSS_microseconds.docx

    Lexicographic ordering of that timestamp is chronological. Modification time
    remains a fallback for older or manually renamed files.
    """
    match = _TAILORED_RESUME_TIMESTAMP_RE.search(path.name)

    try:
        modified_ns = int(path.stat().st_mtime_ns)
    except OSError:
        modified_ns = 0

    if match:
        return (
            1,
            match.group("timestamp"),
            modified_ns,
            path.name.lower(),
        )

    return (
        0,
        "",
        modified_ns,
        path.name.lower(),
    )


def discover_latest_tailored_resume(
    application_id: int,
) -> dict[str, str] | None:
    """
    Recover the latest generated DOCX/PDF for a pre-persistence session.

    Structured Projects and Skills cannot be reconstructed from the DOCX alone,
    but the existing file can still be previewed and downloaded.
    """
    if int(application_id) <= 0:
        return None
    if not TAILORED_RESUME_DIR.exists():
        return None

    matches = sorted(
        TAILORED_RESUME_DIR.glob(
            f"app_{int(application_id)}_tailored_resume_*.docx"
        ),
        key=_legacy_tailored_resume_sort_key,
        reverse=True,
    )
    if not matches:
        return None

    docx_path = matches[0]
    pdf_path = PREVIEW_DIR / f"{docx_path.stem}.pdf"
    return {
        "docx_path": str(docx_path),
        "pdf_path": (
            str(pdf_path)
            if pdf_path.exists()
            else ""
        ),
    }


def get_restorable_application_tailoring(
    application_id: int,
) -> dict[str, Any] | None:
    """
    Load the persisted generation, falling back to legacy generated files.
    """
    stored = get_latest_application_tailoring(application_id)
    legacy = discover_latest_tailored_resume(application_id)

    if stored is None:
        if legacy is None:
            return None
        return {
            "application_id": int(application_id),
            "generation_id": "",
            "persistence_version": "legacy-file-recovery",
            "candidate_pool": None,
            "project_inputs": None,
            "fit_estimate": None,
            "projects": None,
            "skills": None,
            "fit_result": {
                "docx_path": legacy["docx_path"],
                "pdf_path": legacy["pdf_path"],
                "fit_one_page": None,
                "page_count": None,
                "restored_from_legacy_files": True,
                "note": (
                    "Recovered the latest generated tailored résumé file. "
                    "Structured Projects/Skills were not saved by this older "
                    "application version."
                ),
            },
            "generation_settings": None,
            **legacy,
        }

    if not stored.get("docx_path") and legacy is not None:
        stored["docx_path"] = legacy["docx_path"]
        if not stored.get("pdf_path"):
            stored["pdf_path"] = legacy["pdf_path"]

    fit_result = stored.get("fit_result")
    if isinstance(fit_result, dict):
        fit_result = dict(fit_result)
        if stored.get("docx_path"):
            fit_result["docx_path"] = stored["docx_path"]
        if stored.get("pdf_path"):
            fit_result["pdf_path"] = stored["pdf_path"]
        stored["fit_result"] = fit_result

    return stored


def delete_application_tailoring_generations(
    application_id: int,
) -> int:
    """Delete structured tailoring records for one application."""
    init_application_tailoring_versions()
    connection = _connect()
    cursor = connection.cursor()
    cursor.execute(
        """
        DELETE FROM application_tailoring_versions
        WHERE application_id = ?
        """,
        (int(application_id),),
    )
    deleted = max(0, int(cursor.rowcount or 0))
    connection.commit()
    connection.close()
    return deleted

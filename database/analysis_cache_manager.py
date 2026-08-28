"""Persistent exact-input cache and history for résumé-to-JD analyses."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
import json
import sqlite3
import uuid
from typing import Any

from database import db_manager as base_manager


ANALYSIS_CACHE_VERSION = "analysis-cache-v1"
ANALYSIS_PIPELINE_CONTRACT_VERSION = (
    "analysis-pipeline-v2-title-stability-phase6d6"
)
PHASE9F_D_BASELINE_PIPELINE_CONTRACT_VERSION = (
    "phase9f-d-existing-application-baseline-v1"
)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    connection = base_manager._connect()
    connection.row_factory = sqlite3.Row
    return connection


def _normalise_source_text(value: Any) -> str:
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [
        " ".join(line.replace("\u00a0", " ").split())
        for line in text.split("\n")
    ]
    return "\n".join(lines).strip()


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def build_analysis_input_fingerprint(
    *,
    resume_text: str,
    jd_text: str,
    degree: str,
    actual_page_count: int | None,
    model_id: str,
    retrieval_config: dict[str, Any] | None = None,
    pipeline_contract_version: str = ANALYSIS_PIPELINE_CONTRACT_VERSION,
) -> str:
    """Hash stable raw inputs before any AI output is produced."""
    payload = {
        "analysis_cache_version": ANALYSIS_CACHE_VERSION,
        "pipeline_contract_version": pipeline_contract_version,
        "resume_text_sha256": _sha(_normalise_source_text(resume_text)),
        "jd_text_sha256": _sha(_normalise_source_text(jd_text)),
        "degree": " ".join(str(degree or "").split()),
        "actual_page_count": actual_page_count,
        "model_id": str(model_id or "").strip(),
        "retrieval_config": retrieval_config or {},
    }
    canonical = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    return _sha(canonical)


def init_analysis_cache() -> None:
    connection = _connect()
    cursor = connection.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS application_analysis_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            analysis_id TEXT NOT NULL,
            input_fingerprint TEXT NOT NULL,
            cache_version TEXT NOT NULL,
            pipeline_contract_version TEXT NOT NULL,
            analysis_model TEXT NOT NULL,
            resume_filename TEXT,
            report_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(application_id, analysis_id)
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_analysis_cache_fingerprint
        ON application_analysis_versions (
            application_id,
            input_fingerprint,
            updated_at DESC
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_analysis_cache_global_fingerprint
        ON application_analysis_versions (
            input_fingerprint,
            updated_at DESC,
            id DESC
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_analysis_cache_status
        ON application_analysis_versions (
            application_id,
            status,
            updated_at DESC
        )
        """
    )
    connection.commit()
    connection.close()


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    report_text = str(row["report_json"] or "")
    try:
        report = json.loads(report_text) if report_text else {}
    except json.JSONDecodeError:
        report = {}
    return {
        "id": int(row["id"]),
        "application_id": int(row["application_id"]),
        "analysis_id": str(row["analysis_id"]),
        "input_fingerprint": str(row["input_fingerprint"]),
        "cache_version": str(row["cache_version"]),
        "pipeline_contract_version": str(
            row["pipeline_contract_version"]
        ),
        "analysis_model": str(row["analysis_model"]),
        "resume_filename": str(row["resume_filename"] or ""),
        "report": report,
        "status": str(row["status"]),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
    }


def find_cached_analysis(
    *,
    application_id: int,
    input_fingerprint: str,
) -> dict[str, Any] | None:
    fingerprint = str(input_fingerprint or "").strip()
    if not fingerprint:
        return None
    init_analysis_cache()
    connection = _connect()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT *
        FROM application_analysis_versions
        WHERE application_id = ?
          AND input_fingerprint = ?
        ORDER BY
            CASE status WHEN 'active' THEN 0 ELSE 1 END,
            updated_at DESC,
            id DESC
        LIMIT 1
        """,
        (int(application_id), fingerprint),
    )
    row = cursor.fetchone()
    connection.close()
    return _row_to_dict(row) if row is not None else None


def find_reusable_analysis(
    *,
    input_fingerprint: str,
    exclude_application_id: int | None = None,
) -> dict[str, Any] | None:
    """Find an exact cached analysis owned by another Application Session."""
    fingerprint = str(input_fingerprint or "").strip()
    if not fingerprint:
        return None

    excluded_id = (
        int(exclude_application_id)
        if exclude_application_id is not None
        else None
    )

    init_analysis_cache()
    connection = _connect()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT *
        FROM application_analysis_versions
        WHERE input_fingerprint = ?
          AND (? IS NULL OR application_id <> ?)
        ORDER BY
            CASE status WHEN 'active' THEN 0 ELSE 1 END,
            updated_at DESC,
            id DESC
        LIMIT 1
        """,
        (fingerprint, excluded_id, excluded_id),
    )
    row = cursor.fetchone()
    connection.close()
    return _row_to_dict(row) if row is not None else None


def prepare_reusable_analysis_report(
    snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    """Copy reusable analysis content without source-session usage/cache metadata."""
    report = deepcopy((snapshot or {}).get("report") or {})
    report.pop("api_cost_summary", None)

    meta = report.get("meta")
    if isinstance(meta, dict):
        meta.pop("analysis_cache", None)

    return report


def save_analysis_snapshot(
    *,
    application_id: int,
    input_fingerprint: str,
    report: dict[str, Any],
    analysis_model: str,
    resume_filename: str = "",
    analysis_id: str | None = None,
    pipeline_contract_version: str = ANALYSIS_PIPELINE_CONTRACT_VERSION,
) -> dict[str, Any]:
    if int(application_id) <= 0:
        raise ValueError("application_id must be positive.")
    fingerprint = str(input_fingerprint or "").strip()
    if not fingerprint:
        raise ValueError("input_fingerprint is required.")
    if not isinstance(report, dict) or not report:
        raise ValueError("report is required.")

    init_analysis_cache()
    now = _now()
    resolved_id = str(analysis_id or uuid.uuid4().hex)

    connection = _connect()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE application_analysis_versions
        SET status = 'archived',
            updated_at = ?
        WHERE application_id = ?
          AND status = 'active'
        """,
        (now, int(application_id)),
    )
    cursor.execute(
        """
        INSERT INTO application_analysis_versions (
            application_id,
            analysis_id,
            input_fingerprint,
            cache_version,
            pipeline_contract_version,
            analysis_model,
            resume_filename,
            report_json,
            status,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
        ON CONFLICT(application_id, analysis_id) DO UPDATE SET
            input_fingerprint = excluded.input_fingerprint,
            cache_version = excluded.cache_version,
            pipeline_contract_version = excluded.pipeline_contract_version,
            analysis_model = excluded.analysis_model,
            resume_filename = excluded.resume_filename,
            report_json = excluded.report_json,
            status = 'active',
            updated_at = excluded.updated_at
        """,
        (
            int(application_id),
            resolved_id,
            fingerprint,
            ANALYSIS_CACHE_VERSION,
            pipeline_contract_version,
            str(analysis_model or ""),
            str(resume_filename or ""),
            json.dumps(report, ensure_ascii=False, default=str),
            now,
            now,
        ),
    )
    connection.commit()
    cursor.execute(
        """
        SELECT *
        FROM application_analysis_versions
        WHERE application_id = ? AND analysis_id = ?
        """,
        (int(application_id), resolved_id),
    )
    row = cursor.fetchone()
    connection.close()
    if row is None:
        raise RuntimeError("Analysis snapshot could not be reloaded.")
    return _row_to_dict(row)


def insert_analysis_snapshot_with_connection(
    connection: sqlite3.Connection,
    *,
    application_id: int,
    input_fingerprint: str,
    report: dict[str, Any],
    analysis_model: str,
    resume_filename: str,
    analysis_id: str,
    created_at: str,
    pipeline_contract_version: str = (
        PHASE9F_D_BASELINE_PIPELINE_CONTRACT_VERSION
    ),
) -> None:
    """Insert one initial analysis without committing the caller's transaction."""
    if not str(input_fingerprint or "").strip() or not isinstance(report, dict):
        raise ValueError("A complete analysis snapshot is required.")
    connection.execute(
        """
        INSERT INTO application_analysis_versions (
            application_id, analysis_id, input_fingerprint, cache_version,
            pipeline_contract_version, analysis_model, resume_filename,
            report_json, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
        """,
        (
            int(application_id),
            str(analysis_id),
            str(input_fingerprint),
            ANALYSIS_CACHE_VERSION,
            str(pipeline_contract_version),
            str(analysis_model),
            str(resume_filename or ""),
            json.dumps(report, ensure_ascii=False, default=str),
            str(created_at),
            str(created_at),
        ),
    )


def activate_analysis_snapshot(
    *,
    application_id: int,
    analysis_id: str,
) -> dict[str, Any]:
    init_analysis_cache()
    now = _now()
    connection = _connect()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE application_analysis_versions
        SET status = 'archived',
            updated_at = ?
        WHERE application_id = ?
          AND status = 'active'
        """,
        (now, int(application_id)),
    )
    cursor.execute(
        """
        UPDATE application_analysis_versions
        SET status = 'active',
            updated_at = ?
        WHERE application_id = ?
          AND analysis_id = ?
        """,
        (now, int(application_id), str(analysis_id)),
    )
    if cursor.rowcount != 1:
        connection.rollback()
        connection.close()
        raise ValueError("Analysis snapshot was not found.")
    connection.commit()
    cursor.execute(
        """
        SELECT *
        FROM application_analysis_versions
        WHERE application_id = ? AND analysis_id = ?
        """,
        (int(application_id), str(analysis_id)),
    )
    row = cursor.fetchone()
    connection.close()
    if row is None:
        raise RuntimeError("Active analysis snapshot could not be reloaded.")
    return _row_to_dict(row)


def list_analysis_snapshots(
    application_id: int,
) -> list[dict[str, Any]]:
    init_analysis_cache()
    connection = _connect()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT *
        FROM application_analysis_versions
        WHERE application_id = ?
        ORDER BY updated_at DESC, id DESC
        """,
        (int(application_id),),
    )
    rows = cursor.fetchall()
    connection.close()
    return [_row_to_dict(row) for row in rows]


def clear_active_analysis(application_id: int) -> None:
    init_analysis_cache()
    connection = _connect()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE application_analysis_versions
        SET status = 'archived',
            updated_at = ?
        WHERE application_id = ?
          AND status = 'active'
        """,
        (_now(), int(application_id)),
    )
    connection.commit()
    connection.close()


def delete_application_analysis_versions(application_id: int) -> None:
    init_analysis_cache()
    connection = _connect()
    cursor = connection.cursor()
    cursor.execute(
        """
        DELETE FROM application_analysis_versions
        WHERE application_id = ?
        """,
        (int(application_id),),
    )
    connection.commit()
    connection.close()

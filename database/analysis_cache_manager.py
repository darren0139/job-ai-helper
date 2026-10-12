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


def persist_explicit_application_analysis(
    *, application_id: int, input_fingerprint: str, report: dict[str, Any],
    analysis_model: str, resume_filename: str, raw_jd_text: str,
    reused_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Save an explicit Analyze Resume result and freeze its first receipt atomically.

    Reuse is validated against the persisted source, then attached locally using
    the existing cache format. Historical initial receipts are never rewritten.
    This function is deliberately not called by cache reads/currentness refresh.
    """
    from tailoring.phase9f_starting_source_ranking import canonical_requirement_scope_fingerprint
    from tailoring.job_match_ab_analysis import current_ab_identity
    from tailoring.phase9e_blueprint_selection import fingerprint_value

    if not input_fingerprint or not raw_jd_text or report.get("raw_jd_text") != raw_jd_text:
        raise ValueError("Analysis/application JD identity mismatch")
    stable = report.get("stable_analysis") or {}
    rows = stable.get("canonical_requirements") or []
    if not rows or len({r.get("requirement_id") for r in rows}) != len(rows) or any(not r.get("requirement_id") for r in rows):
        raise ValueError("Canonical requirement identity unavailable or ambiguous")
    scope = canonical_requirement_scope_fingerprint(rows)
    identity = current_ab_identity(raw_jd_text)
    document_authority = None
    if (report.get("meta") or {}).get("document_analysis"):
        from tailoring.document_grounded_analysis import validate_document_report
        document_authority = validate_document_report(report)
    for field, key in (("scoring_version", "scoring_version"),
                       ("capability_taxonomy_version", "taxonomy_version"),
                       ("technology_registry_version", "registry_version")):
        if stable.get(field) != identity[key]:
            raise ValueError("Analysis is stale; refresh explicitly before binding")
    base_manager.init_db()
    init_analysis_cache()
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        application = connection.execute("SELECT * FROM applications WHERE id=?", (int(application_id),)).fetchone()
        if application is None:
            raise ValueError("Application unavailable")
        entry = json.loads(application["entry_binding_json"] or "{}")
        confirmation = None
        if connection.execute("SELECT 1 FROM sqlite_master WHERE name='phase9f_application_confirmations'").fetchone():
            confirmation = connection.execute("SELECT 1 FROM phase9f_application_confirmations WHERE application_id=?", (application_id,)).fetchone()
        already_bound = bool(application["initial_analysis_id"] or entry or confirmation)
        previous = json.loads(application["report_json"] or "{}")
        bound_jd = entry.get("raw_jd_text") or previous.get("raw_jd_text")
        if not already_bound and bound_jd and " ".join(bound_jd.split()) != " ".join(raw_jd_text.split()):
            raise ValueError("Application JD differs from the proposed initial receipt")
        snapshot = None
        if reused_snapshot is not None:
            source = connection.execute("SELECT * FROM application_analysis_versions WHERE application_id=? AND analysis_id=?",
                (reused_snapshot.get("application_id"), reused_snapshot.get("analysis_id"))).fetchone()
            if source is None or _row_to_dict(source) != reused_snapshot:
                raise ValueError("Exact saved analysis changed or is unavailable")
            snapshot = _row_to_dict(source)
            source_report = snapshot["report"]
            source_rows = (source_report.get("stable_analysis") or {}).get("canonical_requirements") or []
            if (snapshot["input_fingerprint"] != input_fingerprint
                or snapshot["cache_version"] != ANALYSIS_CACHE_VERSION
                or snapshot["pipeline_contract_version"] != ANALYSIS_PIPELINE_CONTRACT_VERSION
                # Historical normal-session receipts stored collapsed whitespace.
                # Their exact cache input fingerprint still proves input identity.
                or " ".join(str(source_report.get("raw_jd_text") or "").split()) != " ".join(raw_jd_text.split())
                or canonical_requirement_scope_fingerprint(source_rows) != scope
                or source_report.get("stable_analysis") != stable):
                raise ValueError("Saved analysis JD/input/canonical scope is incompatible")
        owned_reuse = snapshot is not None and snapshot["application_id"] == int(application_id)
        analysis_id = snapshot["analysis_id"] if owned_reuse else uuid.uuid4().hex
        persisted_report = deepcopy(report)
        persisted_report.setdefault("meta", {}).setdefault("analysis_cache", {})["analysis_id"] = analysis_id
        origin = "EXACT_SAVED_REUSE" if snapshot is not None else "FRESH_ANALYSIS"
        # Binding metadata references the existing native receipt, never a new
        # analysis format. Owned cache hits need no receipt rewrite.
        reference = {"origin": origin, "initial_analysis_id": analysis_id,
                "raw_jd_text": raw_jd_text,
                "raw_jd_sha256": _sha(raw_jd_text), "canonical_requirement_fingerprint": scope,
                "input_fingerprint": input_fingerprint, "identity": identity,
                "source_application_id": snapshot["application_id"] if snapshot else application_id,
                "source_analysis_id": snapshot["analysis_id"] if snapshot else analysis_id,
                "source_snapshot_id": snapshot["id"] if snapshot else None}
        reference["binding_fingerprint"] = fingerprint_value(reference)
        if not owned_reuse:
            insert_analysis_snapshot_with_connection(connection, application_id=application_id,
                input_fingerprint=input_fingerprint, report=persisted_report, analysis_model=analysis_model,
                resume_filename=resume_filename, analysis_id=analysis_id, created_at=_now(),
                pipeline_contract_version=ANALYSIS_PIPELINE_CONTRACT_VERSION)
        connection.execute("UPDATE application_analysis_versions SET status=CASE WHEN analysis_id=? THEN 'active' ELSE 'archived' END WHERE application_id=?",
                           (analysis_id, application_id))
        if not already_bound:
            connection.execute("UPDATE applications SET initial_analysis_id=?, initial_analysis_binding_json=? WHERE id=? AND initial_analysis_id IS NULL",
                               (analysis_id, json.dumps(reference, ensure_ascii=False), application_id))
        if document_authority and not application["initial_resume_analysis_id"]:
            reference["document_analysis"] = document_authority
            reference.pop("binding_fingerprint", None)
            reference["binding_fingerprint"] = fingerprint_value(reference)
            connection.execute("UPDATE applications SET initial_resume_analysis_id=?, initial_resume_analysis_binding_json=? WHERE id=? AND initial_resume_analysis_id IS NULL",
                               (analysis_id, json.dumps(reference, ensure_ascii=False), application_id))
        base_manager.update_application_report(application_id=application_id, resume_filename=resume_filename,
                                               report=persisted_report, connection=connection)
        saved = connection.execute("SELECT * FROM application_analysis_versions WHERE application_id=? AND analysis_id=?",
                                   (application_id, analysis_id)).fetchone()
        connection.commit()
        return _row_to_dict(saved)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


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
    connection.execute("BEGIN IMMEDIATE")
    cursor = connection.cursor()
    # Cache activation may change, but a frozen application receipt may not.
    if connection.execute("SELECT 1 FROM sqlite_master WHERE name='applications'").fetchone():
        columns = {r[1] for r in connection.execute("PRAGMA table_info(applications)")}
        if "initial_analysis_id" in columns:
            owner = connection.execute("SELECT * FROM applications WHERE id=?", (int(application_id),)).fetchone()
            if owner:
                initial_id = owner["initial_analysis_id"] or json.loads(owner["entry_binding_json"] or "{}").get("initial_analysis_id")
                if initial_id == resolved_id or ("initial_resume_analysis_id" in owner.keys() and owner["initial_resume_analysis_id"] == resolved_id):
                    connection.close()
                    raise ValueError("Frozen Initial Analysis cannot be overwritten")
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

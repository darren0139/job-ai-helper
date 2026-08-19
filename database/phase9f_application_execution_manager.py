"""Durable Phase 9F-E Reuse orchestration and immutable-result persistence."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import uuid
from copy import deepcopy
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from analysis_stability.stable_evidence_scoring import SCORING_VERSION
from database import db_manager
from database import tailoring_version_manager as base_manager
from database.application_blueprint_manager import (
    get_current_application_blueprint_decision,
)
from database.application_resume_result_manager import (
    APPLICATION_RESULT_ARTIFACT_DIR,
    get_application_resume_result,
    init_application_resume_results,
)
from database.global_blueprint_manager import get_global_blueprint
from database.global_master_resume_manager import (
    get_global_master_resume,
    get_global_master_resume_artifact,
)
from database.jd_library_manager import (
    get_exact_job_description_for_application,
)
from database.phase9f_application_confirmation_manager import (
    get_phase9f_application_confirmation,
    init_phase9f_application_confirmation_schema,
)
from database.phase9f_exact_verified_reuse_manager import (
    prove_exact_verified_reuse,
    resolve_blueprint_owned_artifacts,
)
from tailoring.phase9f_exact_verified_reuse import Phase9FExactVerifiedReuseError
from database.tailoring_generation_control import get_tailoring_generation
from database.tailoring_verification_manager import (
    list_tailoring_verifications,
)
from tailoring.phase8_verification import (
    PHASE8_VERIFICATION_VERSION,
    build_phase8_verification,
)
from tailoring.phase9e_application_result import (
    canonical_json,
    verify_application_result_integrity,
)
from tailoring.phase9e_blueprint_selection import (
    fingerprint_value,
    materialise_phase9e_starting_sections,
)
from tailoring.phase9f_application_execution import (
    PHASE9F_E_EVENT_VERSION,
    PHASE9F_E_GENERATION_MODE,
    PHASE9F_E_IDENTITY_POLICY_VERSION,
    PHASE9F_E_PHASE8_BINDING_VERSION,
    PHASE9F_E_RESULT_FORMAT_VERSION,
    PHASE9F_E_RESULT_IDENTITY_POLICY_VERSION,
    PHASE9F_E_RESULT_STATUS,
    PHASE9F_E_VERSION,
    PHASE9F_E_WORKFLOW_ACTION,
    Phase9FEExecutionError,
    build_phase8_generation_adapter,
    build_result_identity,
    exact_jd_identity,
    prepare_execution,
    prepare_result,
    validate_reuse_execution_scope,
    zero_cost_diagnostics,
)
from tailoring.phase9f_starting_source_artifacts import (
    Phase9FBArtifactError,
    resolve_starting_source_artifacts,
)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    connection = base_manager._connect()
    connection.row_factory = sqlite3.Row
    return connection


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def _load(value: Any) -> Any:
    try:
        return json.loads(str(value or "{}"))
    except (TypeError, json.JSONDecodeError):
        return {}


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _table_exists(connection: sqlite3.Connection, name: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone() is not None


def init_phase9f_application_execution_schema() -> None:
    """Apply the additive, idempotent Phase 9F-E execution ledger."""
    init_phase9f_application_confirmation_schema()
    init_application_resume_results()
    connection = _connect()
    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS phase9f_application_executions (
                execution_id TEXT PRIMARY KEY,
                execution_fingerprint TEXT NOT NULL UNIQUE,
                application_id INTEGER NOT NULL UNIQUE,
                execution_version TEXT NOT NULL,
                identity_policy_version TEXT NOT NULL,
                confirmation_id TEXT NOT NULL,
                confirmation_fingerprint TEXT NOT NULL,
                phase9e_decision_id TEXT NOT NULL,
                phase9e_decision_fingerprint TEXT NOT NULL,
                confirmed_intensity TEXT NOT NULL CHECK (
                    confirmed_intensity IN ('reuse', 'minor', 'full')
                ),
                source_type TEXT NOT NULL,
                source_id TEXT NOT NULL,
                starting_snapshot_fingerprint TEXT NOT NULL,
                exact_jd_identity_fingerprint TEXT NOT NULL,
                status TEXT NOT NULL,
                current_stage TEXT NOT NULL,
                attempt_count INTEGER NOT NULL,
                application_result_id TEXT,
                application_result_fingerprint TEXT,
                phase8_verification_id TEXT,
                phase8_verification_fingerprint TEXT,
                phase8_mode TEXT,
                last_error_code TEXT,
                last_error_message TEXT,
                semantic_identity_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_phase9f_e_execution_status
            ON phase9f_application_executions (
                status, current_stage, updated_at DESC
            );

            CREATE TABLE IF NOT EXISTS phase9f_application_execution_events (
                event_id TEXT PRIMARY KEY,
                event_fingerprint TEXT NOT NULL UNIQUE,
                event_version TEXT NOT NULL,
                event_type TEXT NOT NULL,
                execution_id TEXT NOT NULL,
                application_id INTEGER NOT NULL,
                attempt_number INTEGER NOT NULL,
                status TEXT NOT NULL,
                current_stage TEXT NOT NULL,
                actor_label TEXT NOT NULL,
                event_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_phase9f_e_execution_events
            ON phase9f_application_execution_events (
                application_id, created_at DESC, event_id DESC
            );
            """
        )
        connection.commit()
    finally:
        connection.close()


def _row_to_execution(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "execution_id": str(row["execution_id"]),
        "execution_fingerprint": str(row["execution_fingerprint"]),
        "application_id": int(row["application_id"]),
        "execution_version": str(row["execution_version"]),
        "identity_policy_version": str(row["identity_policy_version"]),
        "confirmation_id": str(row["confirmation_id"]),
        "confirmation_fingerprint": str(row["confirmation_fingerprint"]),
        "phase9e_decision_id": str(row["phase9e_decision_id"]),
        "phase9e_decision_fingerprint": str(
            row["phase9e_decision_fingerprint"]
        ),
        "confirmed_intensity": str(row["confirmed_intensity"]),
        "source_type": str(row["source_type"]),
        "source_id": str(row["source_id"]),
        "starting_snapshot_fingerprint": str(
            row["starting_snapshot_fingerprint"]
        ),
        "exact_jd_identity_fingerprint": str(
            row["exact_jd_identity_fingerprint"]
        ),
        "status": str(row["status"]),
        "current_stage": str(row["current_stage"]),
        "attempt_count": int(row["attempt_count"]),
        "application_result_id": str(row["application_result_id"] or ""),
        "application_result_fingerprint": str(
            row["application_result_fingerprint"] or ""
        ),
        "phase8_verification_id": str(
            row["phase8_verification_id"] or ""
        ),
        "phase8_verification_fingerprint": str(
            row["phase8_verification_fingerprint"] or ""
        ),
        "phase8_mode": str(row["phase8_mode"] or ""),
        "last_error_code": str(row["last_error_code"] or ""),
        "last_error_message": str(row["last_error_message"] or ""),
        "semantic_identity": _load(row["semantic_identity_json"]),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
        "completed_at": str(row["completed_at"] or ""),
    }


def get_phase9f_application_execution(
    application_id: int,
) -> dict[str, Any] | None:
    """Read execution state without applying migrations or writing rows."""
    connection = _connect()
    try:
        if not _table_exists(connection, "phase9f_application_executions"):
            return None
        row = connection.execute(
            """
            SELECT * FROM phase9f_application_executions
            WHERE application_id = ? LIMIT 1
            """,
            (int(application_id),),
        ).fetchone()
        return _row_to_execution(row) if row is not None else None
    finally:
        connection.close()


def list_phase9f_application_execution_events(
    application_id: int,
) -> list[dict[str, Any]]:
    connection = _connect()
    try:
        if not _table_exists(
            connection, "phase9f_application_execution_events"
        ):
            return []
        rows = connection.execute(
            """
            SELECT event_json FROM phase9f_application_execution_events
            WHERE application_id = ? ORDER BY created_at, event_id
            """,
            (int(application_id),),
        ).fetchall()
        return [_load(row["event_json"]) for row in rows]
    finally:
        connection.close()


def _insert_execution_event(
    connection: sqlite3.Connection,
    *,
    execution_id: str,
    application_id: int,
    attempt_number: int,
    event_type: str,
    status: str,
    current_stage: str,
    actor_label: str,
    details: dict[str, Any],
    created_at: str,
) -> dict[str, Any]:
    event = {
        "event_id": uuid.uuid4().hex,
        "event_version": PHASE9F_E_EVENT_VERSION,
        "event_type": str(event_type),
        "execution_id": str(execution_id),
        "application_id": int(application_id),
        "attempt_number": int(attempt_number),
        "status": str(status),
        "current_stage": str(current_stage),
        "actor_label": str(actor_label or "Local user"),
        "details": deepcopy(details),
        "created_at": str(created_at),
    }
    event["event_fingerprint"] = fingerprint_value(event)
    connection.execute(
        """
        INSERT INTO phase9f_application_execution_events (
            event_id, event_fingerprint, event_version, event_type,
            execution_id, application_id, attempt_number, status,
            current_stage, actor_label, event_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event["event_id"],
            event["event_fingerprint"],
            event["event_version"],
            event["event_type"],
            execution_id,
            int(application_id),
            int(attempt_number),
            status,
            current_stage,
            event["actor_label"],
            canonical_json(event),
            created_at,
        ),
    )
    return event


def _validated_scope(application_id: int) -> tuple[dict[str, Any], ...]:
    confirmation = get_phase9f_application_confirmation(application_id)
    decision = get_current_application_blueprint_decision(application_id)
    exact_jd = get_exact_job_description_for_application(application_id)
    if decision is None:
        raise Phase9FEExecutionError(
            "The exact Phase 9E binding is missing.",
            code="phase9e_d_binding_missing",
        )
    if decision.get("scope_activation_status") != "active" or decision.get(
        "current_scope_status"
    ) != "current":
        raise Phase9FEExecutionError(
            "The exact Phase 9F-D source/JD scope is stale or inactive.",
            code="phase9f_d_scope_stale",
        )
    if exact_jd is None:
        raise Phase9FEExecutionError(
            "The exact linked JD is missing.",
            code="exact_jd_missing",
        )
    scope = validate_reuse_execution_scope(
        application_id=application_id,
        confirmation=confirmation or {},
        decision=decision,
        exact_jd=exact_jd,
    )
    prepared = prepare_execution(scope)
    return prepared, scope, confirmation or {}, decision, exact_jd


def _start_or_resume_execution(
    *,
    prepared: dict[str, Any],
    actor_label: str,
) -> dict[str, Any]:
    identity = prepared["semantic_identity"]
    application_id = int(identity["application_id"])
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            """
            SELECT * FROM phase9f_application_executions
            WHERE application_id = ? LIMIT 1
            """,
            (application_id,),
        ).fetchone()
        now = _now()
        if existing is not None:
            current = _row_to_execution(existing)
            if current["execution_fingerprint"] != prepared[
                "execution_fingerprint"
            ]:
                raise Phase9FEExecutionError(
                    "This Application Session is bound to a different Phase 9F-E execution identity.",
                    code="execution_identity_conflict",
                )
            if current["status"] == "completed":
                connection.rollback()
                return {**current, "cache_status": "completed_reused"}
            if current["status"] in {"preparing", "running"}:
                connection.rollback()
                return {**current, "cache_status": "in_progress_reused"}
            attempt = current["attempt_count"] + 1
            stage = (
                "phase8"
                if current["current_stage"] == "phase8"
                and current["application_result_id"]
                else "source_preparation"
            )
            connection.execute(
                """
                UPDATE phase9f_application_executions
                SET status='preparing', current_stage=?, attempt_count=?,
                    last_error_code=NULL, last_error_message=NULL,
                    updated_at=?
                WHERE execution_id=?
                """,
                (stage, attempt, now, current["execution_id"]),
            )
            _insert_execution_event(
                connection,
                execution_id=current["execution_id"],
                application_id=application_id,
                attempt_number=attempt,
                event_type="reuse_execution_retried",
                status="preparing",
                current_stage=stage,
                actor_label=actor_label,
                details={"prior_stage": current["current_stage"]},
                created_at=now,
            )
            connection.commit()
            row = connection.execute(
                "SELECT * FROM phase9f_application_executions WHERE execution_id=?",
                (current["execution_id"],),
            ).fetchone()
            return {**_row_to_execution(row), "cache_status": "retry"}

        attempt = 1
        connection.execute(
            """
            INSERT INTO phase9f_application_executions (
                execution_id, execution_fingerprint, application_id,
                execution_version, identity_policy_version,
                confirmation_id, confirmation_fingerprint,
                phase9e_decision_id, phase9e_decision_fingerprint,
                confirmed_intensity, source_type, source_id,
                starting_snapshot_fingerprint,
                exact_jd_identity_fingerprint, status, current_stage,
                attempt_count, semantic_identity_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'reuse', ?, ?, ?, ?,
                      'preparing', 'source_preparation', ?, ?, ?, ?)
            """,
            (
                prepared["execution_id"],
                prepared["execution_fingerprint"],
                application_id,
                PHASE9F_E_VERSION,
                PHASE9F_E_IDENTITY_POLICY_VERSION,
                identity["phase9f_d"]["confirmation_id"],
                identity["phase9f_d"]["confirmation_fingerprint"],
                identity["phase9e_exact_binding"]["decision_id"],
                identity["phase9e_exact_binding"]["decision_fingerprint"],
                prepared["source_type"],
                prepared["source_id"],
                identity["phase9e_exact_binding"][
                    "starting_snapshot_fingerprint"
                ],
                identity["exact_jd"]["jd_identity_fingerprint"],
                attempt,
                canonical_json(identity),
                now,
                now,
            ),
        )
        _insert_execution_event(
            connection,
            execution_id=prepared["execution_id"],
            application_id=application_id,
            attempt_number=attempt,
            event_type="reuse_execution_started",
            status="preparing",
            current_stage="source_preparation",
            actor_label=actor_label,
            details={"confirmed_intensity": "reuse"},
            created_at=now,
        )
        connection.commit()
        row = connection.execute(
            "SELECT * FROM phase9f_application_executions WHERE execution_id=?",
            (prepared["execution_id"],),
        ).fetchone()
        return {**_row_to_execution(row), "cache_status": "created"}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _artifact_hash_records(
    *,
    blueprint: dict[str, Any],
    candidate: dict[str, Any],
) -> list[dict[str, Any]]:
    connection = _connect()
    try:
        required = {
            "application_resume_results",
            "application_resume_result_artifacts",
        }
        if not all(_table_exists(connection, table) for table in required):
            return []
        rows = connection.execute(
            """
            SELECT artifact.artifact_kind, artifact.artifact_sha256,
                   artifact.artifact_size
            FROM application_resume_results AS result
            JOIN application_resume_result_artifacts AS artifact
              ON artifact.application_result_id = result.application_result_id
            WHERE result.blueprint_id = ?
              AND result.blueprint_fingerprint = ?
              AND result.blueprint_version = ?
              AND result.source_application_id = ?
              AND result.source_generation_id = ?
              AND artifact.is_original_approved_artifact = 1
            ORDER BY artifact.artifact_kind
            """,
            (
                _clean(blueprint.get("blueprint_id")),
                _clean(blueprint.get("blueprint_fingerprint")),
                int(blueprint.get("version_number") or 0),
                int(candidate.get("source_application_id") or 0),
                _clean(candidate.get("source_generation_id")),
            ),
        ).fetchall()
        return [
            {
                "artifact_kind": str(row["artifact_kind"]),
                "artifact_sha256": str(row["artifact_sha256"]),
                "artifact_size": int(row["artifact_size"]),
            }
            for row in rows
        ]
    finally:
        connection.close()


def _resolve_blueprint_source(
    *,
    decision: dict[str, Any],
    confirmation: dict[str, Any],
) -> dict[str, Any]:
    starting = decision["starting_snapshot"]
    source_identity = starting["source_identity"]
    blueprint = get_global_blueprint(source_identity["source_id"])
    if blueprint is None:
        raise Phase9FEExecutionError(
            "The exact historical Global Blueprint is missing.",
            code="global_blueprint_missing",
        )
    if (
        _clean(blueprint.get("blueprint_fingerprint"))
        != _clean(source_identity.get("source_fingerprint"))
        or int(blueprint.get("version_number") or 0)
        != int(source_identity.get("source_version") or 0)
        or blueprint.get("blueprint_snapshot")
        != starting.get("phase9d_blueprint_snapshot")
    ):
        raise Phase9FEExecutionError(
            "The exact historical Global Blueprint provenance is inconsistent.",
            code="global_blueprint_identity_mismatch",
        )
    snapshot = blueprint.get("blueprint_snapshot") or {}
    candidate = snapshot.get("phase9b_candidate_semantic_snapshot") or {}
    source_application_id = int(candidate.get("source_application_id") or 0)
    source_generation_id = _clean(candidate.get("source_generation_id"))
    source_verification_id = _clean(candidate.get("source_verification_id"))
    source_verification_fingerprint = _clean(
        candidate.get("source_verification_fingerprint")
    )
    fit = candidate.get("fit_result") or {}
    if (
        source_application_id <= 0
        or not source_generation_id
        or not source_verification_id
        or not source_verification_fingerprint
        or fit.get("fit_one_page") is not True
        or int(fit.get("page_count") or 0) != 1
    ):
        raise Phase9FEExecutionError(
            "The Global Blueprint's approved source/fit provenance is incomplete.",
            code="global_blueprint_source_provenance_incomplete",
        )
    generation = get_tailoring_generation(
        source_application_id, source_generation_id
    )
    if generation is None or not (
        _clean(generation.get("status")) == "approved"
        or _clean(generation.get("approved_at"))
    ):
        raise Phase9FEExecutionError(
            "The Global Blueprint's exact approved source generation is unavailable.",
            code="global_blueprint_source_generation_unavailable",
        )
    generation_fit = generation.get("fit_result") or {}
    if (
        generation_fit.get("fit_one_page") is not True
        or int(generation_fit.get("page_count") or 0) != 1
        or _clean(generation_fit.get("generation_id"))
        != _clean(fit.get("generation_id"))
        or str(generation.get("docx_path") or "")
        != str(fit.get("docx_path") or "")
        or str(generation.get("pdf_path") or "")
        != str(fit.get("pdf_path") or "")
    ):
        raise Phase9FEExecutionError(
            "The Global Blueprint's exact one-page fit identity is inconsistent.",
            code="global_blueprint_fit_identity_mismatch",
        )
    verification_rows = [
        row
        for row in list_tailoring_verifications(source_application_id)
        if _clean(row.get("verification_id")) == source_verification_id
        and _clean(row.get("generation_id")) == source_generation_id
        and _clean(row.get("verification_fingerprint"))
        == source_verification_fingerprint
    ]
    if len(verification_rows) != 1 or verification_rows[0].get(
        "blueprint_ready"
    ) is not True:
        raise Phase9FEExecutionError(
            "The Global Blueprint's exact Phase 8 verification is unavailable.",
            code="global_blueprint_phase8_unavailable",
        )
    source_verification = verification_rows[0]
    selected_candidate = deepcopy(
        (confirmation.get("confirmation_snapshot") or {}).get(
            "selected_candidate"
        )
        or {}
    )
    normalized = {
        "source_type": "global_blueprint",
        "source_id": source_identity["source_id"],
        "source_content_fingerprint": source_identity[
            "source_content_fingerprint"
        ],
        "normalized_source_fingerprint": source_identity[
            "normalized_source_fingerprint"
        ],
    }
    declared_owned_manifest = isinstance(
        (blueprint.get("semantic_identity") or {}).get(
            "artifact_provenance"
        ),
        dict,
    )
    try:
        owned_artifacts = resolve_blueprint_owned_artifacts(blueprint)
    except Phase9FExactVerifiedReuseError as exc:
        if declared_owned_manifest:
            raise Phase9FEExecutionError(
                "The Blueprint-owned immutable artifact failed verification.",
                code="blueprint_owned_artifact_invalid",
            ) from exc
        owned_artifacts = []
    if owned_artifacts:
        return {
            "source_type": "global_blueprint",
            "source": blueprint,
            "source_generation": generation,
            "source_verification": source_verification,
            "artifacts": owned_artifacts,
            "page_count": 1,
            "fit_identity": deepcopy(fit),
        }
    authoritative_hashes = _artifact_hash_records(
        blueprint=blueprint,
        candidate=candidate,
    )
    if not authoritative_hashes:
        raise Phase9FEExecutionError(
            "The Global Blueprint has no immutable approved-artifact hash provenance.",
            code="global_blueprint_artifact_hash_provenance_missing",
        )
    provenance = {
        "chain_status": "resolved",
        "source_resume_result_or_generation": {
            "source_generation": {
                "resolved": True,
                "approval_resolved": True,
                "fit_identity_match": True,
                "generation_id": source_generation_id,
            },
            "immutable_artifact_hash_records": authoritative_hashes,
        },
        "phase8_verification": {
            "resolved": True,
            "blueprint_ready": True,
        },
    }
    try:
        resolution = resolve_starting_source_artifacts(
            ranked_candidate=selected_candidate,
            normalized_source=normalized,
            current_base_artifact=None,
            current_base_preview_artifact=None,
            global_blueprints=[blueprint],
            blueprint_provenance=provenance,
        )
    except (OSError, ValueError, Phase9FBArtifactError) as exc:
        raise Phase9FEExecutionError(
            f"The exact Global Blueprint artifact failed closed: {exc}",
            code="global_blueprint_artifact_invalid",
        ) from exc
    expected_kinds = {
        _clean(row.get("artifact_kind")) for row in authoritative_hashes
    }
    resolved_by_kind = {
        _clean(row.get("artifact_type")): row
        for row in resolution.get("artifacts", []) or []
        if _clean(row.get("verification_method"))
        == "authoritative_immutable_application_result_sha256"
    }
    if set(resolved_by_kind) != expected_kinds:
        raise Phase9FEExecutionError(
            "The Global Blueprint's exact hash-bound approved artifact set is missing or inconsistent.",
            code="global_blueprint_artifact_hash_scope_mismatch",
        )
    resolution["artifacts"] = [
        resolved_by_kind[kind] for kind in sorted(expected_kinds)
    ]
    return {
        "source_type": "global_blueprint",
        "source": blueprint,
        "source_generation": generation,
        "source_verification": source_verification,
        "artifacts": resolution["artifacts"],
        "page_count": 1,
        "fit_identity": deepcopy(fit),
    }


def _pdf_page_count(content: bytes) -> int:
    try:
        return len(PdfReader(BytesIO(content)).pages)
    except Exception as exc:
        raise Phase9FEExecutionError(
            "The immutable Base Resume PDF page count could not be verified.",
            code="base_resume_page_count_unavailable",
        ) from exc


def _resolve_base_source(decision: dict[str, Any]) -> dict[str, Any]:
    starting = decision["starting_snapshot"]
    source_identity = starting["source_identity"]
    master = get_global_master_resume(source_identity["source_id"])
    if master is None:
        raise Phase9FEExecutionError(
            "The exact immutable Base Resume version is missing.",
            code="base_resume_missing",
        )
    if (
        _clean(master.get("master_version_fingerprint"))
        != _clean(source_identity.get("source_fingerprint"))
        or _clean(master.get("master_content_fingerprint"))
        != _clean(source_identity.get("source_content_fingerprint"))
        or int(master.get("version_number") or 0)
        != int(source_identity.get("source_version") or 0)
        or master.get("master_snapshot")
        != starting.get("phase9f_master_resume_snapshot")
    ):
        raise Phase9FEExecutionError(
            "The exact immutable Base Resume provenance is inconsistent.",
            code="base_resume_identity_mismatch",
        )
    original = get_global_master_resume_artifact(
        master["master_version_id"], "original"
    )
    if original is None:
        raise Phase9FEExecutionError(
            "The exact authoritative Base Resume artifact is missing.",
            code="base_resume_artifact_missing",
        )
    preview = get_global_master_resume_artifact(
        master["master_version_id"], "preview_pdf"
    )
    selected_candidate = {
        "source_type": "base_resume",
        "source_id": source_identity["source_id"],
        "normalized_source_fingerprint": source_identity[
            "normalized_source_fingerprint"
        ],
    }
    normalized = {
        **selected_candidate,
        "source_content_fingerprint": source_identity[
            "source_content_fingerprint"
        ],
    }
    try:
        resolution = resolve_starting_source_artifacts(
            ranked_candidate=selected_candidate,
            normalized_source=normalized,
            current_base_artifact=original,
            current_base_preview_artifact=preview,
            global_blueprints=[],
        )
    except (OSError, ValueError, Phase9FBArtifactError) as exc:
        raise Phase9FEExecutionError(
            f"The exact Base Resume artifact failed closed: {exc}",
            code="base_resume_artifact_invalid",
        ) from exc
    proof_pdf = (
        original
        if _clean(original.get("media_type")) == "application/pdf"
        else preview
    )
    if proof_pdf is None:
        raise Phase9FEExecutionError(
            "Reuse requires an exact one-page artifact; this Base Resume has no immutable PDF page-count proof.",
            code="base_resume_page_count_unavailable",
        )
    page_count = _pdf_page_count(proof_pdf["artifact_bytes"])
    if page_count != 1:
        raise Phase9FEExecutionError(
            "The exact unchanged Base Resume is not one page. Reuse stopped without fitting or changing content.",
            code="base_resume_not_one_page",
        )
    return {
        "source_type": "base_resume",
        "source": master,
        "source_generation": {},
        "source_verification": {},
        "artifacts": resolution["artifacts"],
        "page_count": page_count,
        "fit_identity": {
            "fit_one_page": True,
            "page_count": page_count,
            "proof": "exact_immutable_pdf_artifact",
        },
    }


def _resolve_exact_source(
    *,
    decision: dict[str, Any],
    confirmation: dict[str, Any],
) -> dict[str, Any]:
    source_type = _clean(
        (decision.get("starting_snapshot") or {}).get("source_type")
    )
    if source_type == "global_blueprint":
        return _resolve_blueprint_source(
            decision=decision,
            confirmation=confirmation,
        )
    if source_type == "base_resume":
        return _resolve_base_source(decision)
    raise Phase9FEExecutionError(
        "The exact Phase 9F-D source type is unsupported by Reuse.",
        code="reuse_source_type_unsupported",
    )


def _revalidate_bound_exact_verified_reuse(
    *,
    scope: dict[str, Any],
    confirmation: dict[str, Any],
    exact_jd: dict[str, Any],
) -> None:
    """Recheck a D-bound exact proof before Phase 9F-E creates an execution.

    Legacy Reuse confirmations have no exact proof and retain their existing
    Phase 9F-E validation path. A new exact-proof confirmation must instead
    still resolve from authoritative Blueprint, JD, Phase 8, and artifact
    state; a Streamlit/session annotation is never enough.
    """
    selected = (
        (confirmation.get("confirmation_snapshot") or {}).get(
            "selected_candidate"
        )
        or {}
    )
    bound_proof = selected.get("exact_verified_reuse") or {}
    if bound_proof.get("eligible") is not True:
        return
    source = scope.get("source") or {}
    if _clean(source.get("source_type")) != "global_blueprint":
        raise Phase9FEExecutionError(
            "The exact-reuse proof is bound to a different starting source.",
            code="exact_verified_reuse_source_mismatch",
        )
    blueprint = get_global_blueprint(_clean(source.get("source_id")))
    if blueprint is None:
        raise Phase9FEExecutionError(
            "The exact-reuse Blueprint is no longer available.",
            code="exact_verified_reuse_blueprint_missing",
        )
    current = prove_exact_verified_reuse(
        blueprint=blueprint,
        current_exact_jd=exact_jd,
    )
    if (
        current.get("eligible") is not True
        or _clean(current.get("proof_fingerprint"))
        != _clean(bound_proof.get("proof_fingerprint"))
    ):
        raise Phase9FEExecutionError(
            "The exact verified-reuse proof is stale or no longer authoritative.",
            code="exact_verified_reuse_proof_stale",
        )


def resolve_exact_phase9f_d_source(
    *,
    decision: dict[str, Any],
    confirmation: dict[str, Any],
) -> dict[str, Any]:
    """Resolve the immutable D-bound source for a compatible executor.

    Phase 9F-F uses this public adapter rather than reaching into the private
    Reuse implementation.  The underlying resolution and hash checks remain
    the established Phase 9F-E behavior.
    """
    return _resolve_exact_source(
        decision=decision,
        confirmation=confirmation,
    )


def _final_artifact_rows(
    *,
    prepared_result: dict[str, Any],
    source_bundle: dict[str, Any],
    artifact_root: str | Path | None,
) -> list[dict[str, Any]]:
    destination_dir = Path(
        artifact_root or APPLICATION_RESULT_ARTIFACT_DIR
    ) / prepared_result["application_result_id"]
    destination_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for artifact in source_bundle["artifacts"]:
        kind = _clean(artifact.get("artifact_type"))
        if kind not in {"docx", "pdf"}:
            raise Phase9FEExecutionError(
                "The exact Reuse artifact type is unsupported.",
                code="authoritative_artifact_type_unsupported",
            )
        content = artifact.get("artifact_bytes")
        if not isinstance(content, bytes) or not content:
            raise Phase9FEExecutionError(
                "The exact authoritative Reuse artifact bytes are missing.",
                code="authoritative_artifact_missing",
            )
        expected_hash = _clean(artifact.get("sha256"))
        expected_size = int(artifact.get("byte_size") or -1)
        if _sha256_bytes(content) != expected_hash or len(content) != expected_size:
            raise Phase9FEExecutionError(
                "The exact authoritative Reuse artifact failed SHA-256 validation.",
                code="authoritative_artifact_integrity_failed",
            )
        destination = destination_dir / f"resume.{kind}"
        if destination.exists():
            existing = destination.read_bytes()
            if _sha256_bytes(existing) != expected_hash or len(existing) != expected_size:
                raise Phase9FEExecutionError(
                    "A staged Reuse artifact conflicts with the exact execution identity.",
                    code="staged_artifact_identity_conflict",
                )
        else:
            with tempfile.NamedTemporaryFile(
                prefix="phase9f_e_",
                suffix=f".{kind}",
                dir=destination_dir,
                delete=False,
            ) as handle:
                handle.write(content)
                temporary_path = Path(handle.name)
            try:
                if (
                    _sha256_bytes(temporary_path.read_bytes()) != expected_hash
                    or temporary_path.stat().st_size != expected_size
                ):
                    raise Phase9FEExecutionError(
                        "The deterministic Reuse artifact copy failed SHA-256 validation.",
                        code="artifact_copy_integrity_failed",
                    )
                temporary_path.replace(destination)
            finally:
                if temporary_path.exists():
                    temporary_path.unlink()
        rows.append(
            {
                "artifact_kind": kind,
                "artifact_sha256": expected_hash,
                "artifact_size": expected_size,
                "mime_type": _clean(
                    artifact.get("media_type")
                    or artifact.get("mime_type")
                ),
                "provenance_mode": "phase9f_e_exact_authoritative_copy",
                "provenance_label": _clean(
                    artifact.get("provenance_label")
                )
                or "Exact authoritative Reuse artifact",
                "original_bytes_available": True,
                "is_original_approved_artifact": bool(
                    source_bundle["source_type"] == "global_blueprint"
                    or _clean(artifact.get("artifact_kind")) == "original"
                ),
                "source_path": str(artifact.get("source_path") or ""),
                "materialized_path": str(destination),
                "verification_method": _clean(
                    artifact.get("verification_method")
                )
                or "authoritative_sha256_and_size",
            }
        )
    return sorted(rows, key=lambda row: row["artifact_kind"])


def _result_workflow_fingerprint(execution_fingerprint: str) -> str:
    return fingerprint_value(
        {
            "phase9f_e_version": PHASE9F_E_VERSION,
            "execution_fingerprint": execution_fingerprint,
            "workflow_action": PHASE9F_E_WORKFLOW_ACTION,
        }
    )


def _persist_result(
    *,
    execution: dict[str, Any],
    scope: dict[str, Any],
    confirmation: dict[str, Any],
    decision: dict[str, Any],
    source_bundle: dict[str, Any],
    actor_label: str,
    artifact_root: str | Path | None,
) -> dict[str, Any]:
    identity = build_result_identity(
        execution=execution,
        validated_scope=scope,
        artifacts=source_bundle["artifacts"],
    )
    source_generation = source_bundle.get("source_generation") or {}
    source_verification = source_bundle.get("source_verification") or {}
    snapshot = {
        "phase9f_e_execution": deepcopy(execution),
        "phase9f_d_confirmation": deepcopy(confirmation),
        "phase9e_decision": deepcopy(decision),
        "starting_snapshot": deepcopy(decision.get("starting_snapshot") or {}),
        "exact_jd_identity": deepcopy(scope["exact_jd"]),
        "exact_source": deepcopy(source_bundle.get("source") or {}),
        "source_generation": deepcopy(source_generation),
        "inherited_phase8_verification": deepcopy(source_verification),
        "fit_identity": deepcopy(source_bundle.get("fit_identity") or {}),
        "artifact_provenance": deepcopy(identity["artifacts"]),
        "zero_cost_diagnostics": zero_cost_diagnostics(),
    }
    prepared = prepare_result(identity=identity, snapshot=snapshot)
    verify_application_result_integrity(prepared)
    final_artifacts = _final_artifact_rows(
        prepared_result=prepared,
        source_bundle=source_bundle,
        artifact_root=artifact_root,
    )
    action_fingerprint = _result_workflow_fingerprint(
        execution["execution_fingerprint"]
    )
    source_type = scope["source"]["source_type"]
    blueprint = (
        source_bundle.get("source") or {}
        if source_type == "global_blueprint"
        else {}
    )

    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        execution_row = connection.execute(
            "SELECT * FROM phase9f_application_executions WHERE execution_id=?",
            (execution["execution_id"],),
        ).fetchone()
        if execution_row is None:
            raise Phase9FEExecutionError(
                "The durable Phase 9F-E execution row disappeared.",
                code="execution_row_missing",
                stage="application_result",
            )
        existing = connection.execute(
            "SELECT * FROM application_resume_results WHERE application_result_id=?",
            (prepared["application_result_id"],),
        ).fetchone()
        now = _now()
        if existing is None:
            connection.execute(
                """
                INSERT INTO application_resume_results (
                    application_result_id, application_id, format_version,
                    identity_policy_version, result_fingerprint,
                    generation_mode, initial_status, content_changed,
                    editable, phase9e_decision_id,
                    phase9e_decision_fingerprint, workflow_action,
                    workflow_action_fingerprint, blueprint_id,
                    blueprint_fingerprint, blueprint_version,
                    starting_snapshot_fingerprint, source_application_id,
                    source_generation_id, source_verification_id,
                    source_verification_fingerprint, semantic_identity_json,
                    result_snapshot_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    prepared["application_result_id"],
                    int(scope["application_id"]),
                    PHASE9F_E_RESULT_FORMAT_VERSION,
                    PHASE9F_E_RESULT_IDENTITY_POLICY_VERSION,
                    prepared["result_fingerprint"],
                    PHASE9F_E_GENERATION_MODE,
                    PHASE9F_E_RESULT_STATUS,
                    scope["phase9e_decision_id"],
                    scope["phase9e_decision_fingerprint"],
                    PHASE9F_E_WORKFLOW_ACTION,
                    action_fingerprint,
                    _clean(blueprint.get("blueprint_id")),
                    _clean(blueprint.get("blueprint_fingerprint")),
                    int(blueprint.get("version_number") or 0),
                    scope["starting_snapshot_fingerprint"],
                    int(source_generation.get("application_id") or 0),
                    _clean(
                        source_generation.get("generation_id")
                        or scope["source"]["source_id"]
                    ),
                    _clean(source_verification.get("verification_id")),
                    _clean(
                        source_verification.get("verification_fingerprint")
                    ),
                    canonical_json(identity),
                    canonical_json(snapshot),
                    now,
                ),
            )
            for artifact in final_artifacts:
                connection.execute(
                    """
                    INSERT INTO application_resume_result_artifacts (
                        application_result_id, artifact_kind,
                        artifact_sha256, artifact_size, mime_type,
                        provenance_mode, provenance_label,
                        original_bytes_available,
                        is_original_approved_artifact, source_path,
                        materialized_path, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        prepared["application_result_id"],
                        artifact["artifact_kind"],
                        artifact["artifact_sha256"],
                        artifact["artifact_size"],
                        artifact["mime_type"],
                        artifact["provenance_mode"],
                        artifact["provenance_label"],
                        1,
                        int(artifact["is_original_approved_artifact"]),
                        artifact["source_path"],
                        artifact["materialized_path"],
                        now,
                    ),
                )
            event_type = "phase9f_e_reuse_result_created"
        else:
            if (
                str(existing["result_fingerprint"])
                != prepared["result_fingerprint"]
                or _load(existing["semantic_identity_json"]) != identity
            ):
                raise Phase9FEExecutionError(
                    "An existing application result conflicts with this exact Reuse identity.",
                    code="application_result_identity_conflict",
                    stage="application_result",
                )
            event_type = "phase9f_e_reuse_result_reused"
        connection.execute(
            """
            INSERT INTO application_resume_result_state (
                application_id, current_result_id,
                current_result_fingerprint, active_output_mode,
                current_generation_id, current_verification_id,
                acceptance_status, updated_at
            ) VALUES (?, ?, ?, 'immutable_result', NULL, NULL,
                      'pending_phase8_verification', ?)
            ON CONFLICT(application_id) DO UPDATE SET
                current_result_id=excluded.current_result_id,
                current_result_fingerprint=excluded.current_result_fingerprint,
                active_output_mode='immutable_result',
                current_generation_id=NULL,
                current_verification_id=NULL,
                acceptance_status='pending_phase8_verification',
                updated_at=excluded.updated_at
            """,
            (
                int(scope["application_id"]),
                prepared["application_result_id"],
                prepared["result_fingerprint"],
                now,
            ),
        )
        event = {
            "event_id": uuid.uuid4().hex,
            "event_version": PHASE9F_E_EVENT_VERSION,
            "event_type": event_type,
            "application_id": int(scope["application_id"]),
            "application_result_id": prepared["application_result_id"],
            "actor_label": str(actor_label or "Local user"),
            "details": {
                "execution_id": execution["execution_id"],
                "content_changed": False,
                "artifact_rematerialized": False,
            },
            "created_at": now,
        }
        event["event_fingerprint"] = fingerprint_value(event)
        connection.execute(
            """
            INSERT INTO application_resume_result_events (
                event_id, event_version, event_type, application_id,
                application_result_id, event_fingerprint, actor_label,
                event_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event["event_id"],
                event["event_version"],
                event["event_type"],
                int(scope["application_id"]),
                prepared["application_result_id"],
                event["event_fingerprint"],
                event["actor_label"],
                canonical_json(event),
                now,
            ),
        )
        connection.execute(
            """
            UPDATE phase9f_application_executions
            SET status='running', current_stage='phase8',
                application_result_id=?,
                application_result_fingerprint=?, updated_at=?
            WHERE execution_id=?
            """,
            (
                prepared["application_result_id"],
                prepared["result_fingerprint"],
                now,
                execution["execution_id"],
            ),
        )
        _insert_execution_event(
            connection,
            execution_id=execution["execution_id"],
            application_id=int(scope["application_id"]),
            attempt_number=int(execution["attempt_count"]),
            event_type="reuse_result_ready",
            status="running",
            current_stage="phase8",
            actor_label=actor_label,
            details={
                "application_result_id": prepared["application_result_id"],
                "result_fingerprint": prepared["result_fingerprint"],
            },
            created_at=now,
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    stored = get_application_resume_result(prepared["application_result_id"])
    if stored is None:
        raise RuntimeError("The Phase 9F-E application result could not be reloaded.")
    return stored


def _jd_semantics_match(left: dict[str, Any], right: dict[str, Any]) -> bool:
    fields = (
        "canonical_jd_id",
        "source_version_id",
        "raw_jd_sha256",
        "canonical_requirement_fingerprint",
    )
    return all(_clean(left.get(field)) == _clean(right.get(field)) for field in fields) and list(
        left.get("canonical_requirement_ids") or []
    ) == list(right.get("canonical_requirement_ids") or [])


def _strict_inherited_phase8(
    *,
    scope: dict[str, Any],
    decision: dict[str, Any],
    source_bundle: dict[str, Any],
) -> dict[str, Any] | None:
    if source_bundle["source_type"] != "global_blueprint":
        return None
    verification = source_bundle.get("source_verification") or {}
    generation = source_bundle.get("source_generation") or {}
    source_jd = get_exact_job_description_for_application(
        int(generation.get("application_id") or 0)
    )
    if source_jd is None:
        return None
    try:
        source_jd_identity = exact_jd_identity(source_jd)
    except Phase9FEExecutionError:
        return None
    if not _jd_semantics_match(source_jd_identity, scope["exact_jd"]):
        return None
    after = verification.get("after_stable_analysis") or {}
    decision_scoring = (
        (decision.get("semantic_identity") or {}).get("scoring") or {}
    )
    after_ids = [
        _clean(row.get("requirement_id"))
        for row in after.get("canonical_requirements", []) or []
        if isinstance(row, dict) and _clean(row.get("requirement_id"))
    ]
    if (
        _clean(verification.get("phase8_version"))
        != PHASE8_VERIFICATION_VERSION
        or _clean(verification.get("generation_id"))
        != _clean(generation.get("generation_id"))
        or _clean(after.get("scoring_version")) != SCORING_VERSION
        or _clean(after.get("capability_taxonomy_version"))
        != _clean(decision_scoring.get("capability_taxonomy_version"))
        or sorted(after_ids)
        != sorted(scope["exact_jd"]["canonical_requirement_ids"])
        or verification.get("comparison_valid") is not True
        or verification.get("fit_one_page") is not True
        or int(verification.get("page_count") or 0) != 1
    ):
        return None
    return deepcopy(verification)


def _phase8_binding(
    *,
    result: dict[str, Any],
    phase8_result: dict[str, Any],
    mode: str,
    source_verification: dict[str, Any],
) -> dict[str, Any]:
    identity = {
        "binding_version": PHASE9F_E_PHASE8_BINDING_VERSION,
        "application_result_id": result["application_result_id"],
        "result_fingerprint": result["result_fingerprint"],
        "mode": mode,
        "phase8_version": _clean(phase8_result.get("phase8_version")),
        "phase8_verification_fingerprint": _clean(
            phase8_result.get("verification_fingerprint")
        ),
        "source_verification_id": _clean(
            source_verification.get("verification_id")
        ),
        "source_verification_fingerprint": _clean(
            source_verification.get("verification_fingerprint")
        ),
        "canonical_requirement_ids": [
            _clean(row.get("requirement_id"))
            for row in (
                phase8_result.get("after_stable_analysis") or {}
            ).get("canonical_requirements", []) or []
            if isinstance(row, dict) and _clean(row.get("requirement_id"))
        ],
        "scoring_version": _clean(
            (phase8_result.get("after_stable_analysis") or {}).get(
                "scoring_version"
            )
        ),
        "taxonomy_version": _clean(
            (phase8_result.get("after_stable_analysis") or {}).get(
                "capability_taxonomy_version"
            )
        ),
    }
    fingerprint = fingerprint_value(identity)
    return {
        "verification_id": fingerprint[:32],
        "verification_fingerprint": fingerprint,
        "verification_version": PHASE9F_E_PHASE8_BINDING_VERSION,
        "status": "verified",
        "mode": mode,
        "semantic_identity": identity,
        "phase8_result": deepcopy(phase8_result),
        "model_call_count": 0,
        "embedding_call_count": 0,
        "chroma_read_count": 0,
        "chroma_write_count": 0,
    }


def _run_or_reuse_phase8(
    *,
    application_id: int,
    result: dict[str, Any],
    scope: dict[str, Any],
    decision: dict[str, Any],
    exact_jd: dict[str, Any],
    source_bundle: dict[str, Any],
) -> dict[str, Any]:
    inherited = _strict_inherited_phase8(
        scope=scope,
        decision=decision,
        source_bundle=source_bundle,
    )
    if inherited is not None:
        return _phase8_binding(
            result=result,
            phase8_result=inherited,
            mode="strict_inherited_source_phase8",
            source_verification=source_bundle.get("source_verification") or {},
        )

    application = db_manager.get_application_by_id(application_id) or {}
    baseline = deepcopy(application.get("report") or {})
    starting = decision.get("starting_snapshot") or {}
    if baseline.get("resume_profile") != starting.get(
        "resume_profile_snapshot"
    ) or _clean(baseline.get("raw_resume_text")) != _clean(
        starting.get("resume_text_snapshot")
    ):
        raise Phase9FEExecutionError(
            "The Phase 9F-D baseline no longer matches the immutable starting snapshot.",
            code="phase9f_d_baseline_mismatch",
            stage="phase8",
        )
    sections = materialise_phase9e_starting_sections(decision)
    artifact_paths = {
        f"{artifact['artifact_kind']}_path": artifact["materialized_path"]
        for artifact in result.get("artifacts", []) or []
        if artifact.get("artifact_kind") in {"docx", "pdf"}
    }
    adapter = build_phase8_generation_adapter(
        application_id=application_id,
        result=result,
        projects=sections["projects"],
        skills=sections["skills"],
        artifact_paths=artifact_paths,
    )
    phase8_result = build_phase8_verification(
        baseline_report=baseline,
        generation_state=adapter,
        raw_jd_text=str(exact_jd.get("raw_text") or ""),
    )
    if (
        phase8_result.get("comparison_valid") is not True
        or phase8_result.get("fit_one_page") is not True
        or int(phase8_result.get("page_count") or 0) != 1
    ):
        raise Phase9FEExecutionError(
            "Authoritative Phase 8 did not validate the unchanged one-page Reuse result.",
            code="phase8_reuse_verification_failed",
            stage="phase8",
        )
    return _phase8_binding(
        result=result,
        phase8_result=phase8_result,
        mode="executed_current_jd_phase8",
        source_verification=source_bundle.get("source_verification") or {},
    )


def _persist_phase8_and_complete(
    *,
    execution: dict[str, Any],
    result: dict[str, Any],
    binding: dict[str, Any],
    actor_label: str,
) -> dict[str, Any]:
    application_id = int(execution["application_id"])
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            """
            SELECT verification_json
            FROM application_resume_result_verifications
            WHERE verification_fingerprint=?
            """,
            (binding["verification_fingerprint"],),
        ).fetchone()
        now = _now()
        if existing is None:
            connection.execute(
                """
                INSERT INTO application_resume_result_verifications (
                    verification_id, application_id,
                    application_result_id, verification_fingerprint,
                    verification_version, status, verification_json,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    binding["verification_id"],
                    application_id,
                    result["application_result_id"],
                    binding["verification_fingerprint"],
                    binding["verification_version"],
                    binding["status"],
                    canonical_json(binding),
                    now,
                ),
            )
        elif _load(existing["verification_json"]) != binding:
            raise Phase9FEExecutionError(
                "A persisted Phase 8 binding conflicts with this Reuse result.",
                code="phase8_binding_conflict",
                stage="phase8",
            )
        connection.execute(
            """
            UPDATE application_resume_result_state
            SET current_verification_id=?,
                acceptance_status='phase9f_e_reuse_verified',
                updated_at=?
            WHERE application_id=? AND current_result_id=?
            """,
            (
                binding["verification_id"],
                now,
                application_id,
                result["application_result_id"],
            ),
        )
        connection.execute(
            """
            UPDATE phase9f_application_executions
            SET status='completed', current_stage='completed',
                phase8_verification_id=?,
                phase8_verification_fingerprint=?, phase8_mode=?,
                last_error_code=NULL, last_error_message=NULL,
                updated_at=?, completed_at=?
            WHERE execution_id=?
            """,
            (
                binding["verification_id"],
                binding["verification_fingerprint"],
                binding["mode"],
                now,
                now,
                execution["execution_id"],
            ),
        )
        _insert_execution_event(
            connection,
            execution_id=execution["execution_id"],
            application_id=application_id,
            attempt_number=int(execution["attempt_count"]),
            event_type="reuse_execution_completed",
            status="completed",
            current_stage="completed",
            actor_label=actor_label,
            details={
                "application_result_id": result["application_result_id"],
                "phase8_verification_id": binding["verification_id"],
                "phase8_mode": binding["mode"],
                **zero_cost_diagnostics(),
            },
            created_at=now,
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    completed = get_phase9f_application_execution(application_id)
    if completed is None:
        raise RuntimeError("The completed Phase 9F-E execution could not be reloaded.")
    return completed


def _record_failure(
    *,
    execution: dict[str, Any],
    error: Exception,
    actor_label: str,
) -> None:
    stage = (
        error.stage
        if isinstance(error, Phase9FEExecutionError)
        else execution.get("current_stage") or "source_preparation"
    )
    code = (
        error.code
        if isinstance(error, Phase9FEExecutionError)
        else "phase9f_e_execution_error"
    )
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        now = _now()
        connection.execute(
            """
            UPDATE phase9f_application_executions
            SET status='failed', current_stage=?, last_error_code=?,
                last_error_message=?, updated_at=?
            WHERE execution_id=?
            """,
            (stage, code, str(error), now, execution["execution_id"]),
        )
        _insert_execution_event(
            connection,
            execution_id=execution["execution_id"],
            application_id=int(execution["application_id"]),
            attempt_number=int(execution["attempt_count"]),
            event_type="reuse_execution_failed",
            status="failed",
            current_stage=stage,
            actor_label=actor_label,
            details={"error_code": code, "error_message": str(error)},
            created_at=now,
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def execute_phase9f_reuse(
    *,
    application_id: int,
    actor_label: str = "Local user",
    artifact_root: str | Path | None = None,
) -> dict[str, Any]:
    """Execute or retry one exact, unchanged, idempotent Phase 9F-E Reuse."""
    init_phase9f_application_execution_schema()
    prepared, scope, confirmation, decision, exact_jd = _validated_scope(
        int(application_id)
    )
    _revalidate_bound_exact_verified_reuse(
        scope=scope,
        confirmation=confirmation,
        exact_jd=exact_jd,
    )
    execution = _start_or_resume_execution(
        prepared=prepared,
        actor_label=actor_label,
    )
    if execution["status"] == "completed":
        result = get_application_resume_result(
            execution["application_result_id"]
        )
        return {
            "cache_status": execution.get("cache_status"),
            "execution": execution,
            "application_result": result,
            "zero_cost_diagnostics": zero_cost_diagnostics(),
        }
    if execution.get("cache_status") == "in_progress_reused":
        return {
            "cache_status": "in_progress_reused",
            "execution": execution,
            "application_result": None,
            "zero_cost_diagnostics": zero_cost_diagnostics(),
        }

    source_bundle: dict[str, Any] | None = None
    try:
        if execution["application_result_id"]:
            result = get_application_resume_result(
                execution["application_result_id"]
            )
            if result is None:
                raise Phase9FEExecutionError(
                    "The retry's immutable application result is missing.",
                    code="application_result_missing_on_retry",
                    stage="phase8",
                )
            result_snapshot = result.get("result_snapshot") or {}
            source_bundle = {
                "source_type": scope["source"]["source_type"],
                "source": deepcopy(result_snapshot.get("exact_source") or {}),
                "source_generation": deepcopy(
                    result_snapshot.get("source_generation") or {}
                ),
                "source_verification": deepcopy(
                    result_snapshot.get("inherited_phase8_verification") or {}
                ),
                "artifacts": [],
                "page_count": 1,
                "fit_identity": deepcopy(
                    result_snapshot.get("fit_identity") or {}
                ),
            }
        else:
            source_bundle = _resolve_exact_source(
                decision=decision,
                confirmation=confirmation,
            )
            result = _persist_result(
                execution=execution,
                scope=scope,
                confirmation=confirmation,
                decision=decision,
                source_bundle=source_bundle,
                actor_label=actor_label,
                artifact_root=artifact_root,
            )
            reloaded = get_phase9f_application_execution(application_id)
            if reloaded is None:
                raise RuntimeError("The running Phase 9F-E execution disappeared.")
            execution = reloaded
        binding = _run_or_reuse_phase8(
            application_id=application_id,
            result=result,
            scope=scope,
            decision=decision,
            exact_jd=exact_jd,
            source_bundle=source_bundle,
        )
        completed = _persist_phase8_and_complete(
            execution=execution,
            result=result,
            binding=binding,
            actor_label=actor_label,
        )
        return {
            "cache_status": (
                "result_reused" if execution["attempt_count"] > 1 else "created"
            ),
            "execution": completed,
            "application_result": get_application_resume_result(
                result["application_result_id"]
            ),
            "phase8_binding": binding,
            "zero_cost_diagnostics": zero_cost_diagnostics(),
        }
    except Exception as exc:
        _record_failure(
            execution=execution,
            error=exc,
            actor_label=actor_label,
        )
        raise


def delete_phase9f_application_execution(application_id: int) -> None:
    """Delete execution rows only during explicit parent-session deletion."""
    connection = _connect()
    try:
        if not _table_exists(connection, "phase9f_application_executions"):
            return
        connection.execute("BEGIN IMMEDIATE")
        if _table_exists(
            connection, "phase9f_application_execution_events"
        ):
            connection.execute(
                "DELETE FROM phase9f_application_execution_events WHERE application_id=?",
                (int(application_id),),
            )
        connection.execute(
            "DELETE FROM phase9f_application_executions WHERE application_id=?",
            (int(application_id),),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

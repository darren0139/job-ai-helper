"""Durable Phase 9F-F orchestration for confirmed Minor/Full tailoring.

The manager owns only the private orchestration ledger.  User-visible changed
content remains an ordinary Phase 7 draft, and the existing fit, approval,
and Phase 8 engines remain authoritative.
"""

from __future__ import annotations

import hashlib
import json
import inspect
import sqlite3
import tempfile
import uuid
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from database import db_manager
from database import tailoring_version_manager as base_manager
from database.application_blueprint_manager import (
    get_current_application_blueprint_decision,
)
from database.jd_library_manager import get_exact_job_description_for_application
from database.phase9f_application_confirmation_manager import (
    get_phase9f_application_confirmation,
    init_phase9f_application_confirmation_schema,
)
from database.phase9f_application_execution_manager import (
    resolve_exact_phase9f_d_source,
)
from database.tailoring_generation_control import (
    find_cached_tailoring_generation,
    get_tailoring_generation,
    list_tailoring_generations,
    record_generation_metadata,
    restore_tailoring_generation_as_draft,
)
from database.tailoring_verification_manager import (
    save_tailoring_verification,
)
from database.tailoring_version_manager import save_application_tailoring_generation
from database.user_profile_manager import get_all_evidence_items_for_snapshot
from llm import drain_call_ledger, get_active_model, reset_call_ledger, summarise_call_usage
from resume_builder.docx_projects_skills_replacer import (
    generate_tailored_resume_copy_fit_one_page,
    resolve_effective_fitting_bullet_ceiling,
    resolve_fitting_bullet_allocation_mode,
)
from tailoring.phase8_verification import build_phase8_verification
from tailoring.phase8_verification import (
    PHASE8_VERIFICATION_VERSION,
    build_final_resume_profile,
)
from tailoring.phase9e_blueprint_selection import (
    build_effective_tailoring_report,
    fingerprint_value,
    materialise_phase9e_starting_sections,
)
from tailoring.phase9f_tailoring_execution import (
    PHASE9F_F_EVENT_VERSION,
    PHASE9F_F_CONTENT_CHANGE_POLICY_VERSION,
    PHASE9F_F_IDENTITY_POLICY_VERSION,
    PHASE9F_F_FIT_SETTINGS_POLICY_VERSION,
    PHASE9F_F_GENERATION_SETTINGS_POLICY_VERSION,
    PHASE9F_F_MODEL_BINDING_POLICY_VERSION,
    PHASE9F_F_SECTION_SCOPE_POLICY_VERSION,
    PHASE9F_F_SOURCE_ARTIFACT_POLICY_VERSION,
    PHASE9F_F_STAGE_OUTPUT_POLICY_VERSION,
    PHASE9F_F_VERSION,
    Phase9FFExecutionError,
    VALID_INTENSITIES,
    build_execution_identity,
    build_frozen_evidence_snapshot,
    build_section_scope,
    prepare_execution,
    validate_minor_full_execution_scope,
)
from tailoring.project_section_tailor import (
    build_project_candidate_pool,
    estimate_project_section_length,
    tailor_projects_section,
)
from tailoring.skills_section_tailor import tailor_skills_section
from tailoring.tailoring_generation_fingerprint import (
    build_tailoring_input_fingerprint,
)


EXECUTION_STATUSES = {
    "not_started",
    "preparing",
    "running",
    "blocked",
    "waiting_for_approval",
    "waiting_for_phase8",
    "completed",
    "failed",
}


# New F sessions use the ordinary Application Session version table for each
# generated résumé.  The F row remains only the immutable session context and
# append-only audit ledger.  Do not use this marker to reinterpret the older
# private-stage-output contract.
PHASE9F_F_NORMAL_LIFECYCLE_VERSION = "phase9f-f-normal-generation-lifecycle-v1"
PHASE9F_F_NORMAL_GENERATION_KIND = "phase9f_f_normal_projects_skills"
PHASE9F_F_NORMAL_FIT_KIND = "phase9f_f_normal_fit"
PHASE9F_F_NORMAL_EVIDENCE_POOL_POLICY_VERSION = (
    "phase9f-f-normal-evidence-pool-v1"
)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    connection = base_manager._connect()
    connection.row_factory = sqlite3.Row
    return connection


def _connect_read_only() -> sqlite3.Connection | None:
    """Open an existing database without creating files during passive reads."""
    path = Path(base_manager.DB_PATH)
    if not path.is_file():
        return None
    connection = sqlite3.connect(
        f"{path.resolve().as_uri()}?mode=ro",
        uri=True,
    )
    connection.row_factory = sqlite3.Row
    return connection


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str, sort_keys=True)


def _load(value: Any, fallback: Any) -> Any:
    try:
        parsed = json.loads(str(value or ""))
    except (TypeError, json.JSONDecodeError):
        return deepcopy(fallback)
    return parsed if isinstance(parsed, type(fallback)) else deepcopy(fallback)


def _table_exists(connection: sqlite3.Connection, name: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def init_phase9f_tailoring_execution_schema() -> None:
    """Apply additive, idempotent Phase 9F-F private execution storage."""
    init_phase9f_application_confirmation_schema()
    connection = _connect()
    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS phase9f_tailoring_executions (
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
                    confirmed_intensity IN ('minor', 'full')
                ),
                source_type TEXT NOT NULL,
                source_id TEXT NOT NULL,
                starting_snapshot_fingerprint TEXT NOT NULL,
                exact_jd_identity_fingerprint TEXT NOT NULL,
                evidence_snapshot_fingerprint TEXT NOT NULL,
                opportunity_fingerprint TEXT NOT NULL,
                section_scope_fingerprint TEXT NOT NULL,
                status TEXT NOT NULL,
                current_stage TEXT NOT NULL,
                attempt_count INTEGER NOT NULL,
                generation_id TEXT,
                phase8_verification_id TEXT,
                phase8_verification_fingerprint TEXT,
                terminal_reason TEXT,
                last_error_code TEXT,
                last_error_message TEXT,
                semantic_identity_json TEXT NOT NULL,
                source_artifact_json TEXT NOT NULL DEFAULT '{}',
                evidence_snapshot_json TEXT NOT NULL,
                section_scope_json TEXT NOT NULL,
                stage_outputs_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_phase9f_f_execution_status
            ON phase9f_tailoring_executions (
                status, current_stage, updated_at DESC
            );

            CREATE TABLE IF NOT EXISTS phase9f_tailoring_execution_events (
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

            CREATE INDEX IF NOT EXISTS idx_phase9f_f_execution_events
            ON phase9f_tailoring_execution_events (
                application_id, created_at DESC, event_id DESC
            );
            """
        )
        columns = {
            str(row[1])
            for row in connection.execute(
                "PRAGMA table_info(phase9f_tailoring_executions)"
            ).fetchall()
        }
        if "source_artifact_json" not in columns:
            connection.execute(
                "ALTER TABLE phase9f_tailoring_executions "
                "ADD COLUMN source_artifact_json TEXT NOT NULL DEFAULT '{}'"
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _event_id(payload: dict[str, Any]) -> tuple[str, str]:
    fingerprint = fingerprint_value(payload)
    return fingerprint[:32], fingerprint


def _insert_event(
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
    created_at: str | None = None,
) -> None:
    created = created_at or _now()
    event_id, event_fingerprint = _event_id(
        {
            "event_version": PHASE9F_F_EVENT_VERSION,
            "event_type": event_type,
            "execution_id": execution_id,
            "application_id": int(application_id),
            "attempt_number": int(attempt_number),
            "status": status,
            "current_stage": current_stage,
            "details": details,
            "created_at": created,
        }
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO phase9f_tailoring_execution_events (
            event_id, event_fingerprint, event_version, event_type,
            execution_id, application_id, attempt_number, status,
            current_stage, actor_label, event_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            event_fingerprint,
            PHASE9F_F_EVENT_VERSION,
            event_type,
            execution_id,
            int(application_id),
            int(attempt_number),
            status,
            current_stage,
            _clean(actor_label) or "Local user",
            _dump(details),
            created,
        ),
    )


def _row_to_execution(row: sqlite3.Row) -> dict[str, Any]:
    keys = set(row.keys())
    return {
        "execution_id": str(row["execution_id"]),
        "execution_fingerprint": str(row["execution_fingerprint"]),
        "application_id": int(row["application_id"]),
        "execution_version": str(row["execution_version"]),
        "identity_policy_version": str(row["identity_policy_version"]),
        "confirmation_id": str(row["confirmation_id"]),
        "confirmation_fingerprint": str(row["confirmation_fingerprint"]),
        "phase9e_decision_id": str(row["phase9e_decision_id"]),
        "phase9e_decision_fingerprint": str(row["phase9e_decision_fingerprint"]),
        "confirmed_intensity": str(row["confirmed_intensity"]),
        "source_type": str(row["source_type"]),
        "source_id": str(row["source_id"]),
        "starting_snapshot_fingerprint": str(row["starting_snapshot_fingerprint"]),
        "exact_jd_identity_fingerprint": str(row["exact_jd_identity_fingerprint"]),
        "evidence_snapshot_fingerprint": str(row["evidence_snapshot_fingerprint"]),
        "opportunity_fingerprint": str(row["opportunity_fingerprint"]),
        "section_scope_fingerprint": str(row["section_scope_fingerprint"]),
        "status": str(row["status"]),
        "current_stage": str(row["current_stage"]),
        "attempt_count": int(row["attempt_count"]),
        "generation_id": str(row["generation_id"] or ""),
        "phase8_verification_id": str(row["phase8_verification_id"] or ""),
        "phase8_verification_fingerprint": str(row["phase8_verification_fingerprint"] or ""),
        "terminal_reason": str(row["terminal_reason"] or ""),
        "last_error_code": str(row["last_error_code"] or ""),
        "last_error_message": str(row["last_error_message"] or ""),
        "semantic_identity": _load(row["semantic_identity_json"], {}),
        "source_artifact": _load(
            row["source_artifact_json"] if "source_artifact_json" in keys else "{}",
            {},
        ),
        "evidence_snapshot": _load(row["evidence_snapshot_json"], {}),
        "section_scope": _load(row["section_scope_json"], {}),
        "stage_outputs": _load(row["stage_outputs_json"], {}),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
        "completed_at": str(row["completed_at"] or ""),
    }


def get_phase9f_tailoring_execution(application_id: int) -> dict[str, Any] | None:
    """Read F state without applying migrations or writing rows."""
    connection = _connect_read_only()
    if connection is None:
        return None
    try:
        if not _table_exists(connection, "phase9f_tailoring_executions"):
            return None
        row = connection.execute(
            "SELECT * FROM phase9f_tailoring_executions WHERE application_id=?",
            (int(application_id),),
        ).fetchone()
        if row is None:
            return None
        execution = _row_to_execution(row)
        uncertain_stage = _requested_stage_without_result(execution)
        if uncertain_stage:
            execution["recovery_state"] = "model_attempt_uncertain"
            execution["uncertain_stage"] = uncertain_stage
        return execution
    finally:
        connection.close()


def list_phase9f_tailoring_execution_events(application_id: int) -> list[dict[str, Any]]:
    connection = _connect_read_only()
    if connection is None:
        return []
    try:
        if not _table_exists(connection, "phase9f_tailoring_execution_events"):
            return []
        rows = connection.execute(
            """
            SELECT * FROM phase9f_tailoring_execution_events
            WHERE application_id=? ORDER BY created_at, event_id
            """,
            (int(application_id),),
        ).fetchall()
        return [
            {
                "event_id": str(row["event_id"]),
                "event_type": str(row["event_type"]),
                "status": str(row["status"]),
                "current_stage": str(row["current_stage"]),
                "attempt_number": int(row["attempt_number"]),
                "details": _load(row["event_json"], {}),
                "created_at": str(row["created_at"]),
            }
            for row in rows
        ]
    finally:
        connection.close()


def delete_phase9f_tailoring_execution(application_id: int) -> None:
    """Delete only F orchestration rows during whole-session deletion."""
    connection = _connect()
    try:
        if not _table_exists(connection, "phase9f_tailoring_executions"):
            return
        connection.execute("BEGIN IMMEDIATE")
        if _table_exists(connection, "phase9f_tailoring_execution_events"):
            connection.execute(
                "DELETE FROM phase9f_tailoring_execution_events WHERE application_id=?",
                (int(application_id),),
            )
        connection.execute(
            "DELETE FROM phase9f_tailoring_executions WHERE application_id=?",
            (int(application_id),),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _load_execution_inputs(application_id: int) -> tuple[
    dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]
]:
    confirmation = get_phase9f_application_confirmation(application_id)
    decision = get_current_application_blueprint_decision(application_id)
    exact_jd = get_exact_job_description_for_application(application_id)
    application = db_manager.get_application_by_id(application_id)
    if not isinstance(application, dict) or not isinstance(application.get("report"), dict):
        raise Phase9FFExecutionError(
            "The Phase 9F-D Application Session baseline report is unavailable.",
            code="application_baseline_missing",
        )
    if confirmation is None or decision is None or exact_jd is None:
        raise Phase9FFExecutionError(
            "The current Phase 9F-D confirmation, binding, or exact JD is missing.",
            code="phase9f_d_scope_missing",
        )
    return confirmation, decision, exact_jd, application, application["report"]


def _source_artifact_identity(artifact: dict[str, Any]) -> dict[str, Any]:
    """Return the immutable identity for one already-resolved DOCX artifact."""
    content = artifact.get("artifact_bytes")
    artifact_type = _clean(artifact.get("artifact_type")).lower()
    expected_hash = _clean(artifact.get("sha256"))
    try:
        expected_size = int(artifact.get("byte_size") or -1)
    except (TypeError, ValueError):
        expected_size = -1
    actual_hash = hashlib.sha256(content).hexdigest() if isinstance(content, bytes) else ""
    if (
        artifact_type != "docx"
        or not isinstance(content, bytes)
        or not content
        or not expected_hash
        or expected_size < 0
        or len(content) != expected_size
        or actual_hash != expected_hash
    ):
        raise Phase9FFExecutionError(
            "The exact immutable DOCX artifact failed hash or size validation.",
            code="source_docx_artifact_invalid",
            stage="source_preparation",
        )
    return {
        "policy_version": PHASE9F_F_SOURCE_ARTIFACT_POLICY_VERSION,
        "artifact_type": "docx",
        "sha256": expected_hash,
        "byte_size": expected_size,
    }


def _exact_docx_artifact(
    source_bundle: dict[str, Any],
    *,
    expected_identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve one exact immutable DOCX without trusting a path as authority."""
    candidates = [
        artifact
        for artifact in source_bundle.get("artifacts") or []
        if isinstance(artifact, dict)
        and _clean(artifact.get("artifact_type")).lower() == "docx"
    ]
    if len(candidates) != 1:
        raise Phase9FFExecutionError(
            "The exact immutable D-bound DOCX source artifact is unavailable.",
            code="source_docx_missing",
            stage="source_preparation",
        )
    artifact = deepcopy(candidates[0])
    identity = _source_artifact_identity(artifact)
    if expected_identity:
        comparable = {
            key: identity.get(key)
            for key in ("policy_version", "artifact_type", "sha256", "byte_size")
        }
        expected = {
            key: expected_identity.get(key)
            for key in ("policy_version", "artifact_type", "sha256", "byte_size")
        }
        if comparable != expected:
            raise Phase9FFExecutionError(
                "The exact immutable DOCX source changed after Phase 9F-F preparation.",
                code="source_docx_identity_mismatch",
                stage="fitting",
            )
    return {
        **identity,
        "source_path": _clean(artifact.get("source_path")),
        "artifact_bytes": bytes(artifact["artifact_bytes"]),
    }


def _resolve_prepared_source_artifact(
    *,
    decision: dict[str, Any],
    confirmation: dict[str, Any],
    expected_identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source_bundle = resolve_exact_phase9f_d_source(
        decision=decision,
        confirmation=confirmation,
        require_reuse_page_proof=False,
    )
    return _exact_docx_artifact(
        source_bundle,
        expected_identity=expected_identity,
    )


def prepare_phase9f_tailoring_execution(
    application_id: int,
    *,
    frozen_evidence_snapshot: dict[str, Any] | None = None,
    frozen_section_scope: dict[str, Any] | None = None,
    frozen_source_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one F identity from current D-bound facts without persistence."""
    confirmation, decision, exact_jd, application, application_report = _load_execution_inputs(
        int(application_id)
    )
    scope = validate_minor_full_execution_scope(
        application_id=int(application_id),
        confirmation=confirmation,
        decision=decision,
        exact_jd=exact_jd,
    )
    # All generation-facing baseline values come from the exact immutable
    # Phase 9E snapshot and its exact linked JD.  The mutable application
    # report supplies only the enclosing session context.
    baseline_report = build_effective_tailoring_report(
        application_report,
        decision,
    )
    evidence_snapshot = (
        deepcopy(frozen_evidence_snapshot)
        if isinstance(frozen_evidence_snapshot, dict)
        and isinstance(frozen_evidence_snapshot.get("rows"), list)
        else build_frozen_evidence_snapshot(get_all_evidence_items_for_snapshot())
    )
    if isinstance(frozen_section_scope, dict) and frozen_section_scope:
        section_scope = deepcopy(frozen_section_scope)
        if (
            section_scope.get("policy_version")
            != PHASE9F_F_SECTION_SCOPE_POLICY_VERSION
            or section_scope.get("confirmed_intensity")
            != scope["confirmed_intensity"]
        ):
            raise Phase9FFExecutionError(
                "The stored Phase 9F-F section scope is no longer supported.",
                code="section_scope_policy_unsupported",
            )
        snapshot_rows = {
            int(row.get("id") or 0): row
            for row in evidence_snapshot.get("rows") or []
            if isinstance(row, dict)
        }
        selected_rows = section_scope.get("selected_evidence") or []
        if any(
            not isinstance(row, dict)
            or snapshot_rows.get(int(row.get("id") or 0)) != row
            for row in selected_rows
        ):
            raise Phase9FFExecutionError(
                "The stored Phase 9F-F selected evidence does not match its frozen snapshot.",
                code="section_scope_evidence_mismatch",
            )
    else:
        section_scope = build_section_scope(
            application_id=int(application_id),
            baseline_report=baseline_report,
            evidence_snapshot=evidence_snapshot,
            confirmed_intensity=scope["confirmed_intensity"],
        )
    if section_scope.get("enabled_sections"):
        if isinstance(frozen_source_artifact, dict) and frozen_source_artifact:
            source_artifact = deepcopy(frozen_source_artifact)
            source_identity = {
                key: source_artifact.get(key)
                for key in ("policy_version", "artifact_type", "sha256", "byte_size")
            }
            try:
                valid_size = int(source_identity.get("byte_size") or -1) >= 0
            except (TypeError, ValueError):
                valid_size = False
            if (
                source_identity.get("policy_version")
                != PHASE9F_F_SOURCE_ARTIFACT_POLICY_VERSION
                or source_identity.get("artifact_type") != "docx"
                or len(_clean(source_identity.get("sha256"))) != 64
                or not valid_size
            ):
                raise Phase9FFExecutionError(
                    "The stored Phase 9F-F DOCX artifact identity is unsupported.",
                    code="source_docx_identity_unsupported",
                )
        else:
            resolved_source_artifact = _resolve_prepared_source_artifact(
                decision=decision,
                confirmation=confirmation,
            )
            source_artifact = {
                key: resolved_source_artifact.get(key)
                for key in (
                    "policy_version",
                    "artifact_type",
                    "sha256",
                    "byte_size",
                    "source_path",
                )
            }
        source_artifact_identity = {
            key: source_artifact.get(key)
            for key in ("policy_version", "artifact_type", "sha256", "byte_size")
        }
    else:
        source_artifact = {}
        source_artifact_identity = {}
    # Model selection belongs to the explicit Projects/Skills action.  The
    # durable execution identity freezes only the binding contract so opening
    # or initializing F cannot prematurely select a paid-generation model.
    model_policy = {
        "policy_version": PHASE9F_F_MODEL_BINDING_POLICY_VERSION,
        "binding_boundary": "first_explicit_projects_skills_action",
        "model_execution": "existing_projects_and_skills_engines",
        "temperature": 0.0,
    }
    identity = build_execution_identity(
        validated_scope=scope,
        evidence_snapshot=evidence_snapshot,
        section_scope=section_scope,
        model_policy=model_policy,
        source_artifact_identity=source_artifact_identity,
    )
    return {
        **prepare_execution(identity=identity),
        "scope": scope,
        "confirmation": confirmation,
        "decision": decision,
        "exact_jd": exact_jd,
        "application": application,
        "baseline_report": baseline_report,
        "evidence_snapshot": evidence_snapshot,
        "section_scope": section_scope,
        "model_policy": model_policy,
        "source_artifact": source_artifact,
    }


def _start_or_reuse_execution(
    *, prepared: dict[str, Any], actor_label: str
) -> dict[str, Any]:
    identity = prepared["semantic_identity"]
    application_id = int(identity["application_id"])
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            "SELECT * FROM phase9f_tailoring_executions WHERE application_id=?",
            (application_id,),
        ).fetchone()
        now = _now()
        if existing is not None:
            execution = _row_to_execution(existing)
            if execution["execution_fingerprint"] != prepared["execution_fingerprint"]:
                raise Phase9FFExecutionError(
                    "This Application Session is already bound to a different Phase 9F-F execution identity.",
                    code="execution_identity_conflict",
                )
            connection.rollback()
            return {**execution, "cache_status": "reused"}

        scope = prepared["scope"]
        section_scope = prepared["section_scope"]
        connection.execute(
            """
            INSERT INTO phase9f_tailoring_executions (
                execution_id, execution_fingerprint, application_id,
                execution_version, identity_policy_version,
                confirmation_id, confirmation_fingerprint,
                phase9e_decision_id, phase9e_decision_fingerprint,
                confirmed_intensity, source_type, source_id,
                starting_snapshot_fingerprint, exact_jd_identity_fingerprint,
                evidence_snapshot_fingerprint, opportunity_fingerprint,
                section_scope_fingerprint, status, current_stage, attempt_count,
                semantic_identity_json, source_artifact_json, evidence_snapshot_json, section_scope_json,
                stage_outputs_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      'preparing', 'source_preparation', 1, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                prepared["execution_id"],
                prepared["execution_fingerprint"],
                application_id,
                PHASE9F_F_VERSION,
                PHASE9F_F_IDENTITY_POLICY_VERSION,
                scope["confirmation_id"],
                scope["confirmation_fingerprint"],
                scope["phase9e_decision_id"],
                scope["phase9e_decision_fingerprint"],
                scope["confirmed_intensity"],
                scope["source"]["source_type"],
                scope["source"]["source_id"],
                scope["starting_snapshot_fingerprint"],
                scope["exact_jd"]["jd_identity_fingerprint"],
                prepared["evidence_snapshot"]["snapshot_fingerprint"],
                section_scope["opportunity_fingerprint"],
                section_scope["scope_fingerprint"],
                _dump(prepared["semantic_identity"]),
                _dump(prepared["source_artifact"]),
                _dump(prepared["evidence_snapshot"]),
                _dump(section_scope),
                _dump(
                    {
                        "policy_version": PHASE9F_F_STAGE_OUTPUT_POLICY_VERSION,
                        "normal_lifecycle_adapter_version": (
                            PHASE9F_F_NORMAL_LIFECYCLE_VERSION
                        ),
                    }
                ),
                now,
                now,
            ),
        )
        _insert_event(
            connection,
            execution_id=prepared["execution_id"],
            application_id=application_id,
            attempt_number=1,
            event_type="tailoring_execution_prepared",
            status="preparing",
            current_stage="source_preparation",
            actor_label=actor_label,
            details={
                "confirmed_intensity": scope["confirmed_intensity"],
                "enabled_sections": section_scope["enabled_sections"],
                "evidence_snapshot_fingerprint": prepared["evidence_snapshot"][
                    "snapshot_fingerprint"
                ],
            },
            created_at=now,
        )
        connection.commit()
        row = connection.execute(
            "SELECT * FROM phase9f_tailoring_executions WHERE execution_id=?",
            (prepared["execution_id"],),
        ).fetchone()
        return {**_row_to_execution(row), "cache_status": "created"}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _can_reuse_legacy_pre_stage_execution(
    *, existing: dict[str, Any], prepared: dict[str, Any]
) -> bool:
    """Permit an unspent older F initialization without rewriting its identity.

    This narrow bridge exists only for pre-stage rows from the uncommitted F
    contract.  Any requested/finished paid stage remains fail-closed: its old
    stage input may have bound settings under the previous policy.
    """
    if _clean(existing.get("identity_policy_version")) == PHASE9F_F_IDENTITY_POLICY_VERSION:
        return False
    if _clean(existing.get("status")) != "preparing":
        return False
    outputs = existing.get("stage_outputs") or {}
    if any(
        key in outputs
        for key in ("generation_settings", "projects", "skills", "fitting", "fitting_attempts")
    ):
        return False
    scope = prepared["scope"]
    section_scope = prepared["section_scope"]
    comparisons = (
        (_clean(existing.get("confirmation_fingerprint")), _clean(scope.get("confirmation_fingerprint"))),
        (_clean(existing.get("phase9e_decision_fingerprint")), _clean(scope.get("phase9e_decision_fingerprint"))),
        (_clean(existing.get("starting_snapshot_fingerprint")), _clean(scope.get("starting_snapshot_fingerprint"))),
        (_clean(existing.get("exact_jd_identity_fingerprint")), _clean((scope.get("exact_jd") or {}).get("jd_identity_fingerprint"))),
        (_clean(existing.get("evidence_snapshot_fingerprint")), _clean((prepared.get("evidence_snapshot") or {}).get("snapshot_fingerprint"))),
        (_clean(existing.get("section_scope_fingerprint")), _clean(section_scope.get("scope_fingerprint"))),
    )
    return all(left and left == right for left, right in comparisons)


def prepare_or_reuse_phase9f_tailoring_execution(
    *, application_id: int, actor_label: str = "Local user"
) -> dict[str, Any]:
    """Persist deterministic F preparation before any paid stage starts."""
    existing = get_phase9f_tailoring_execution(int(application_id))
    init_phase9f_tailoring_execution_schema()
    prepared = prepare_phase9f_tailoring_execution(
        int(application_id),
        frozen_evidence_snapshot=(existing or {}).get("evidence_snapshot"),
        frozen_section_scope=(existing or {}).get("section_scope"),
        frozen_source_artifact=(existing or {}).get("source_artifact"),
    )
    if existing is not None and _can_reuse_legacy_pre_stage_execution(
        existing=existing,
        prepared=prepared,
    ):
        execution = {**existing, "cache_status": "legacy_pre_stage_reused"}
    else:
        execution = _start_or_reuse_execution(prepared=prepared, actor_label=actor_label)
    if execution["status"] == "preparing" and not execution["section_scope"].get(
        "enabled_sections"
    ):
        execution = _update_execution(
            execution_id=execution["execution_id"],
            status="blocked",
            current_stage="no_addressable_changes",
            terminal_reason="no_addressable_changes",
            event_type="no_addressable_changes",
            actor_label=actor_label,
            details={
                "projects_addressable": False,
                "skills_addressable": False,
                "model_call_count": 0,
            },
        )
    return {"execution": execution, "prepared": prepared}


def _update_execution(
    *,
    execution_id: str,
    status: str,
    current_stage: str,
    stage_outputs: dict[str, Any] | None = None,
    generation_id: str | None = None,
    phase8_verification: dict[str, Any] | None = None,
    terminal_reason: str | None = None,
    last_error: Phase9FFExecutionError | Exception | None = None,
    event_type: str,
    actor_label: str,
    details: dict[str, Any],
) -> dict[str, Any]:
    if status not in EXECUTION_STATUSES:
        raise ValueError(f"Unsupported Phase 9F-F status: {status}")
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT * FROM phase9f_tailoring_executions WHERE execution_id=?",
            (execution_id,),
        ).fetchone()
        if row is None:
            raise Phase9FFExecutionError(
                "The Phase 9F-F execution disappeared during persistence.",
                code="execution_missing",
            )
        current = _row_to_execution(row)
        now = _now()
        error_code = getattr(last_error, "code", "") if last_error else ""
        error_message = str(last_error) if last_error else ""
        verification = phase8_verification or {}
        connection.execute(
            """
            UPDATE phase9f_tailoring_executions
            SET status=?, current_stage=?, stage_outputs_json=COALESCE(?, stage_outputs_json),
                generation_id=COALESCE(?, generation_id),
                phase8_verification_id=COALESCE(?, phase8_verification_id),
                phase8_verification_fingerprint=COALESCE(?, phase8_verification_fingerprint),
                terminal_reason=COALESCE(?, terminal_reason),
                last_error_code=?, last_error_message=?, updated_at=?,
                completed_at=CASE WHEN ?='completed' THEN ? ELSE completed_at END
            WHERE execution_id=?
            """,
            (
                status,
                current_stage,
                _dump(stage_outputs) if stage_outputs is not None else None,
                generation_id,
                _clean(verification.get("verification_id")) or None,
                _clean(verification.get("verification_fingerprint")) or None,
                terminal_reason,
                error_code or None,
                error_message or None,
                now,
                status,
                now,
                execution_id,
            ),
        )
        _insert_event(
            connection,
            execution_id=execution_id,
            application_id=current["application_id"],
            attempt_number=current["attempt_count"],
            event_type=event_type,
            status=status,
            current_stage=current_stage,
            actor_label=actor_label,
            details=details,
            created_at=now,
        )
        connection.commit()
        updated = connection.execute(
            "SELECT * FROM phase9f_tailoring_executions WHERE execution_id=?",
            (execution_id,),
        ).fetchone()
        return _row_to_execution(updated)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _stage_input_fingerprint(
    *, execution: dict[str, Any], stage: str, payload: dict[str, Any]
) -> str:
    return fingerprint_value(
        {
            "execution_fingerprint": execution["execution_fingerprint"],
            "stage": stage,
            "payload": payload,
        }
    )


_GENERATION_ALLOCATION_MODES = {
    "adaptive",
    "prefer_available_evidence",
    "all_canonical_before_fitting",
}


def _integer_setting(
    value: Any,
    *,
    name: str,
    minimum: int,
    maximum: int,
) -> int:
    try:
        normalised = int(value)
    except (TypeError, ValueError) as exc:
        raise Phase9FFExecutionError(
            f"The Phase 9F-F {name} setting is invalid.",
            code=f"{name}_invalid",
            stage="generation_settings",
        ) from exc
    if normalised < minimum or normalised > maximum:
        raise Phase9FFExecutionError(
            f"The Phase 9F-F {name} setting is outside the supported range.",
            code=f"{name}_invalid",
            stage="generation_settings",
        )
    return normalised


def _canonical_generation_settings(settings: dict[str, Any] | None) -> dict[str, Any]:
    """Canonicalise the existing normal Projects/Skills controls at action time."""
    source = settings if isinstance(settings, dict) else {}
    mode = _clean(source.get("bullet_allocation_mode") or "prefer_available_evidence").lower()
    if mode not in _GENERATION_ALLOCATION_MODES:
        raise Phase9FFExecutionError(
            "The selected bullet allocation mode is unsupported.",
            code="bullet_allocation_mode_invalid",
            stage="generation_settings",
        )
    return {
        "policy_version": PHASE9F_F_GENERATION_SETTINGS_POLICY_VERSION,
        "max_projects": _integer_setting(
            source.get("max_projects", 3),
            name="max_projects",
            minimum=1,
            maximum=8,
        ),
        "max_bullets": _integer_setting(
            source.get("max_bullets", 3),
            name="max_bullets",
            minimum=1,
            maximum=4,
        ),
        "bullet_allocation_mode": mode,
    }


def _canonical_fit_settings(settings: dict[str, Any] | None) -> dict[str, Any]:
    """Canonicalise normal Build/Fit controls without changing fitter semantics."""
    source = settings if isinstance(settings, dict) else {}
    spacing_mode = _clean(source.get("spacing_mode") or "paragraph_spacing").lower()
    if spacing_mode not in {"paragraph_spacing", "blank_line"}:
        raise Phase9FFExecutionError(
            "The selected spacing mode is unsupported.",
            code="spacing_mode_invalid",
            stage="fitting",
        )
    density = _clean(source.get("page_density_mode") or "balanced").lower()
    if density not in {"none", "balanced", "maximize"}:
        raise Phase9FFExecutionError(
            "The selected page density mode is unsupported.",
            code="page_density_mode_invalid",
            stage="fitting",
        )
    project_header_layout = _clean(
        source.get("project_header_layout") or "auto"
    ).lower()
    if project_header_layout not in {"auto", "stacked", "inline"}:
        raise Phase9FFExecutionError(
            "The selected project header layout is unsupported.",
            code="project_header_layout_invalid",
            stage="fitting",
        )
    project_metadata_style = _clean(
        source.get("project_metadata_style") or "pipes"
    ).lower()
    if project_metadata_style not in {"pipes", "parentheses"}:
        raise Phase9FFExecutionError(
            "The selected project metadata style is unsupported.",
            code="project_metadata_style_invalid",
            stage="fitting",
        )
    return {
        "policy_version": PHASE9F_F_FIT_SETTINGS_POLICY_VERSION,
        "use_compact_before_delete": bool(source.get("use_compact_before_delete", True)),
        "prefer_balanced_bullets": bool(source.get("prefer_balanced_bullets", False)),
        "allow_skills_compaction": bool(source.get("allow_skills_compaction", False)),
        "page_density_mode": density,
        "allow_margin_compaction": bool(source.get("allow_margin_compaction", False)),
        "project_header_layout": project_header_layout,
        "project_metadata_style": project_metadata_style,
        "spacing_mode": spacing_mode,
        "add_spacing_before_first_project": bool(
            source.get("add_spacing_before_first_project", False)
        ),
        "project_spacing_pt": _integer_setting(
            source.get("project_spacing_pt", 10),
            name="project_spacing_pt",
            minimum=0,
            maximum=20,
        ),
        "after_projects_spacing_pt": _integer_setting(
            source.get("after_projects_spacing_pt", 10),
            name="after_projects_spacing_pt",
            minimum=0,
            maximum=20,
        ),
        "blank_lines_between_projects": _integer_setting(
            source.get("blank_lines_between_projects", 1),
            name="blank_lines_between_projects",
            minimum=0,
            maximum=3,
        ),
        "blank_lines_after_projects": _integer_setting(
            source.get("blank_lines_after_projects", 1),
            name="blank_lines_after_projects",
            minimum=0,
            maximum=3,
        ),
    }


def _generation_settings_snapshot(execution: dict[str, Any]) -> dict[str, Any] | None:
    state = (execution.get("stage_outputs") or {}).get("generation_settings") or {}
    if (
        state.get("status") == "frozen"
        and isinstance(state.get("settings"), dict)
        and _clean(state.get("settings_fingerprint"))
        and _clean(state.get("model"))
    ):
        return deepcopy(state)
    return None


def _freeze_or_reuse_generation_settings(
    *,
    execution: dict[str, Any],
    generation_settings: dict[str, Any] | None,
    selected_model: str | None,
    actor_label: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Persist the normal generation controls immediately before paid work."""
    existing = _generation_settings_snapshot(execution)
    if existing is not None:
        return execution, existing
    model = _clean(selected_model) or _clean(get_active_model("analysis"))
    if not model:
        raise Phase9FFExecutionError(
            "A Projects/Skills generation model must be selected before paid work.",
            code="generation_model_missing",
            stage="generation_settings",
        )
    settings = _canonical_generation_settings(generation_settings)
    snapshot = {
        "status": "frozen",
        "policy_version": PHASE9F_F_GENERATION_SETTINGS_POLICY_VERSION,
        "settings": settings,
        "settings_fingerprint": fingerprint_value(settings),
        "model": model,
        "model_policy_version": PHASE9F_F_MODEL_BINDING_POLICY_VERSION,
        "binding_boundary": "first_explicit_projects_skills_action",
        "frozen_reason": "first_paid_generation_request",
    }
    outputs = deepcopy(execution.get("stage_outputs") or {})
    outputs["generation_settings"] = snapshot
    updated = _update_execution(
        execution_id=execution["execution_id"],
        status="running",
        current_stage="generation_settings",
        stage_outputs=outputs,
        event_type="generation_settings_frozen",
        actor_label=actor_label,
        details={
            "settings_fingerprint": snapshot["settings_fingerprint"],
            "model": model,
            "bullet_allocation_mode": settings["bullet_allocation_mode"],
            "max_projects": settings["max_projects"],
            "max_bullets": settings["max_bullets"],
        },
    )
    return updated, snapshot


def _mark_stage_requested(
    *,
    execution: dict[str, Any],
    stage: str,
    input_fingerprint: str,
    actor_label: str,
    settings_snapshot: dict[str, Any],
) -> dict[str, Any]:
    outputs = deepcopy(execution.get("stage_outputs") or {})
    outputs[stage] = {
        **(outputs.get(stage) or {}),
        "status": "requested",
        "input_fingerprint": input_fingerprint,
        "attempt_number": int(execution["attempt_count"]),
        "generation_settings_fingerprint": settings_snapshot["settings_fingerprint"],
        "generation_settings": deepcopy(settings_snapshot["settings"]),
        "model": settings_snapshot["model"],
        "model_policy_version": settings_snapshot["model_policy_version"],
    }
    return _update_execution(
        execution_id=execution["execution_id"],
        status="running",
        current_stage=stage,
        stage_outputs=outputs,
        event_type="model_stage_requested",
        actor_label=actor_label,
        details={
            "stage": stage,
            "input_fingerprint": input_fingerprint,
            "generation_settings_fingerprint": settings_snapshot["settings_fingerprint"],
            "model": settings_snapshot["model"],
        },
    )


def _persist_stage_result(
    *,
    execution: dict[str, Any],
    stage: str,
    input_fingerprint: str,
    result: dict[str, Any],
    usage: dict[str, Any],
    actor_label: str,
) -> dict[str, Any]:
    outputs = deepcopy(execution.get("stage_outputs") or {})
    prior = deepcopy(outputs.get(stage) or {})
    outputs[stage] = {
        **{
            key: prior[key]
            for key in (
                "generation_settings_fingerprint",
                "generation_settings",
                "model",
                "model_policy_version",
            )
            if key in prior
        },
        "status": "completed",
        "input_fingerprint": input_fingerprint,
        "result": deepcopy(result),
        "result_fingerprint": fingerprint_value(result),
        "usage": deepcopy(usage),
        "attempt_number": int(execution["attempt_count"]),
    }
    return _update_execution(
        execution_id=execution["execution_id"],
        status="running",
        current_stage=stage,
        stage_outputs=outputs,
        event_type="model_stage_completed",
        actor_label=actor_label,
        details={
            "stage": stage,
            "input_fingerprint": input_fingerprint,
            "result_fingerprint": outputs[stage]["result_fingerprint"],
            "usage": usage,
        },
    )


def _persist_stage_result_with_retry(**kwargs: Any) -> dict[str, Any]:
    try:
        return _persist_stage_result(**kwargs)
    except Exception as first_error:
        try:
            return _persist_stage_result(**kwargs)
        except Exception as second_error:
            raise Phase9FFExecutionError(
                "The successful model response could not be made durable. "
                "It will not be automatically repeated.",
                code="model_response_unrecoverable",
                stage=str(kwargs.get("stage") or "unknown"),
            ) from second_error


def _completed_stage(execution: dict[str, Any], stage: str) -> dict[str, Any] | None:
    state = (execution.get("stage_outputs") or {}).get(stage) or {}
    if state.get("status") == "completed" and isinstance(state.get("result"), dict):
        return deepcopy(state)
    return None


def _materialise_exact_source_docx(
    artifact: dict[str, Any],
) -> tuple[str, tempfile.TemporaryDirectory[str]]:
    """Write only freshly hash-validated immutable bytes for deterministic fit."""
    temporary = tempfile.TemporaryDirectory(prefix="phase9f_f_source_")
    path = Path(temporary.name) / "source.docx"
    path.write_bytes(bytes(artifact["artifact_bytes"]))
    if (
        hashlib.sha256(path.read_bytes()).hexdigest() != artifact["sha256"]
        or path.stat().st_size != int(artifact["byte_size"])
    ):
        temporary.cleanup()
        raise Phase9FFExecutionError(
            "The exact immutable DOCX could not be materialized for fitting.",
            code="source_docx_materialization_invalid",
            stage="fitting",
        )
    return str(path), temporary


def _visible_resume_content_identity(
    *,
    prepared: dict[str, Any],
    projects: dict[str, Any],
    skills: dict[str, Any],
) -> dict[str, Any]:
    """Compare user-visible final résumé content, not generation/debug JSON."""
    baseline_profile = deepcopy(
        (prepared.get("baseline_report") or {}).get("resume_profile") or {}
    )
    if not baseline_profile:
        raise Phase9FFExecutionError(
            "The exact immutable résumé profile is unavailable for content comparison.",
            code="baseline_profile_missing",
            stage="materialise_draft",
        )
    source_sections = materialise_phase9e_starting_sections(prepared["decision"])
    source_profile = build_final_resume_profile(
        baseline_profile,
        {
            "projects": source_sections["projects"],
            "skills": source_sections["skills"],
        },
    )
    changed_profile = build_final_resume_profile(
        baseline_profile,
        {"projects": projects, "skills": skills},
    )
    source_fingerprint = fingerprint_value(source_profile)
    content_fingerprint = fingerprint_value(changed_profile)
    return {
        "policy_version": PHASE9F_F_CONTENT_CHANGE_POLICY_VERSION,
        "base_content_fingerprint": source_fingerprint,
        "content_fingerprint": content_fingerprint,
        "content_changed": content_fingerprint != source_fingerprint,
    }


def _materialise_changed_draft(
    *,
    execution: dict[str, Any],
    prepared: dict[str, Any],
    projects: dict[str, Any],
    skills: dict[str, Any],
    fit_result: dict[str, Any],
    content_identity: dict[str, Any],
) -> dict[str, Any]:
    application_id = int(execution["application_id"])
    generation_id = execution["execution_id"]
    base_fingerprint = _clean(content_identity.get("base_content_fingerprint"))
    content_fingerprint = _clean(content_identity.get("content_fingerprint"))
    if not content_identity.get("content_changed"):
        raise Phase9FFExecutionError(
            "The completed tailored sections do not visibly differ from the frozen source.",
            code="no_semantic_content_change",
            stage="materialise_draft",
        )
    stage_outputs = execution.get("stage_outputs") or {}
    generation_snapshot = _generation_settings_snapshot(execution)
    fit_stage = _completed_stage(execution, "fitting") or {}
    fit_snapshot = fit_stage.get("fit_settings") or {}
    if generation_snapshot is None or not isinstance(fit_snapshot, dict):
        raise Phase9FFExecutionError(
            "The completed Phase 9F-F draft is missing its frozen stage settings.",
            code="draft_stage_settings_missing",
            stage="materialise_draft",
        )
    settings = {
        "phase9f_f_execution_id": execution["execution_id"],
        "phase9f_f_execution_fingerprint": execution["execution_fingerprint"],
        "phase9f_d_confirmation_fingerprint": execution["confirmation_fingerprint"],
        "phase9e_binding": {
            "decision_fingerprint": execution["phase9e_decision_fingerprint"],
        },
        "phase9e_base_content_fingerprint": base_fingerprint,
        "phase9f_f_evidence_snapshot_fingerprint": execution[
            "evidence_snapshot_fingerprint"
        ],
        "phase9f_f_section_scope_fingerprint": execution["section_scope_fingerprint"],
        "phase9f_f_content_change_policy_version": content_identity["policy_version"],
        "generation_settings": deepcopy(generation_snapshot["settings"]),
        "generation_settings_fingerprint": generation_snapshot["settings_fingerprint"],
        "generation_model": generation_snapshot["model"],
        "fit_settings": deepcopy(fit_snapshot.get("settings") or {}),
        "fit_settings_fingerprint": _clean(fit_snapshot.get("settings_fingerprint")),
        "fit_input_fingerprint": _clean(fit_stage.get("input_fingerprint")),
        "bullet_allocation_mode": generation_snapshot["settings"]["bullet_allocation_mode"],
        "max_projects": generation_snapshot["settings"]["max_projects"],
        "max_bullets": generation_snapshot["settings"]["max_bullets"],
        "stage_outputs_fingerprint": fingerprint_value(stage_outputs),
    }
    cached = find_cached_tailoring_generation(
        application_id=application_id,
        input_fingerprint=execution["execution_fingerprint"],
        generation_kind="phase9f_f_tailoring",
    )
    if cached is not None:
        cached_settings = cached.get("generation_settings") or {}
        if (
            _clean(cached.get("generation_id")) != generation_id
            or _clean(cached_settings.get("phase9f_f_execution_fingerprint"))
            != execution["execution_fingerprint"]
            or cached.get("content_changed") is not True
        ):
            raise Phase9FFExecutionError(
                "A cached tailored draft conflicts with the exact Phase 9F-F execution.",
                code="draft_identity_conflict",
                stage="materialise_draft",
            )
        return cached
    save_application_tailoring_generation(
        application_id=application_id,
        generation_id=generation_id,
        candidate_pool=(projects.get("candidate_project_ranking") if isinstance(projects, dict) else None),
        project_inputs={
            "phase9f_f_execution_fingerprint": execution["execution_fingerprint"],
            "stage_outputs_fingerprint": fingerprint_value(stage_outputs),
        },
        projects=projects,
        skills=skills,
        fit_result=fit_result,
        generation_settings=settings,
        docx_path=fit_result.get("docx_path"),
        pdf_path=fit_result.get("pdf_path"),
    )
    record_generation_metadata(
        application_id=application_id,
        generation_id=generation_id,
        input_fingerprint=execution["execution_fingerprint"],
        generation_kind="phase9f_f_tailoring",
        base_content_fingerprint=base_fingerprint,
        content_fingerprint=content_fingerprint,
        content_changed=True,
        phase9e_decision_fingerprint=execution["phase9e_decision_fingerprint"],
    )
    generation = get_tailoring_generation(application_id, generation_id)
    if generation is None:
        raise Phase9FFExecutionError(
            "The complete Phase 9F-F draft could not be reloaded.",
            code="draft_persistence_failed",
            stage="materialise_draft",
        )
    return generation


def _mark_failure(
    execution: dict[str, Any], error: Exception, actor_label: str) -> dict[str, Any]:
    return _update_execution(
        execution_id=execution["execution_id"],
        status="failed",
        current_stage=str(getattr(error, "stage", execution.get("current_stage") or "unknown")),
        last_error=error,
        event_type="tailoring_execution_failed",
        actor_label=actor_label,
        details={"error_code": str(getattr(error, "code", "unexpected_error"))},
    )


def _prepare_frozen_phase8_context(
    execution: dict[str, Any],
) -> dict[str, Any]:
    """Revalidate D/Phase 9E/JD facts without rereading mutable evidence."""
    (
        confirmation,
        decision,
        exact_jd,
        _application,
        application_report,
    ) = _load_execution_inputs(int(execution["application_id"]))
    scope = validate_minor_full_execution_scope(
        application_id=int(execution["application_id"]),
        confirmation=confirmation,
        decision=decision,
        exact_jd=exact_jd,
    )
    identity = execution.get("semantic_identity") or {}
    expected = {
        "confirmation_fingerprint": scope["confirmation_fingerprint"],
        "phase9e_decision_fingerprint": scope["phase9e_decision_fingerprint"],
        "starting_snapshot_fingerprint": scope["starting_snapshot_fingerprint"],
        "source": scope["source"],
        "exact_jd": scope["exact_jd"],
        "frozen_content": scope["frozen_content"],
    }
    actual = {
        "confirmation_fingerprint": _clean(execution.get("confirmation_fingerprint")),
        "phase9e_decision_fingerprint": _clean(
            execution.get("phase9e_decision_fingerprint")
        ),
        "starting_snapshot_fingerprint": _clean(
            execution.get("starting_snapshot_fingerprint")
        ),
        "source": identity.get("source"),
        "exact_jd": identity.get("exact_jd"),
        "frozen_content": identity.get("frozen_content"),
    }
    if actual != expected:
        raise Phase9FFExecutionError(
            "The current Phase 9F-D scope no longer matches the frozen Phase 9F-F execution.",
            code="phase8_execution_scope_mismatch",
            stage="phase8",
        )
    return {
        "decision": decision,
        "scope": scope,
        "baseline_report": build_effective_tailoring_report(
            application_report,
            decision,
        ),
    }


def _phase8_validity_issues(
    *,
    verification: dict[str, Any],
    expected: dict[str, Any],
    execution: dict[str, Any],
) -> list[str]:
    """Require the existing Phase 8 success contract before F can complete."""
    issues: list[str] = []
    if _clean(verification.get("phase8_version")) != PHASE8_VERIFICATION_VERSION:
        issues.append("phase8_version_mismatch")
    if _clean(verification.get("verification_fingerprint")) != _clean(
        expected.get("verification_fingerprint")
    ):
        issues.append("verification_fingerprint_mismatch")
    if int(verification.get("application_id") or 0) != int(execution["application_id"]):
        issues.append("verification_application_mismatch")
    if _clean(verification.get("generation_id")) != _clean(execution.get("generation_id")):
        issues.append("verification_generation_mismatch")
    if _clean(verification.get("generation_status")).lower() != "approved":
        issues.append("verification_generation_not_approved")
    if verification.get("comparison_valid") is not True:
        issues.append("verification_canonical_scope_invalid")
    if verification.get("fit_one_page") is not True or int(
        verification.get("page_count") or 0
    ) != 1:
        issues.append("verification_fit_invalid")
    if verification.get("blueprint_ready") is not True:
        issues.append("verification_readiness_failed")
    if _clean(verification.get("verdict")) not in {"improved", "maintained"}:
        issues.append("verification_verdict_invalid")

    expected_before = expected.get("before_stable_analysis") or {}
    actual_before = verification.get("before_stable_analysis") or {}
    for field in (
        "input_fingerprint",
        "scoring_version",
        "capability_taxonomy_version",
    ):
        if _clean(actual_before.get(field)) != _clean(expected_before.get(field)):
            issues.append(f"verification_baseline_{field}_mismatch")
    expected_ids = sorted(
        _clean(row.get("requirement_id"))
        for row in expected_before.get("canonical_requirements", []) or []
        if isinstance(row, dict) and _clean(row.get("requirement_id"))
    )
    actual_ids = sorted(
        _clean(row.get("requirement_id"))
        for row in actual_before.get("canonical_requirements", []) or []
        if isinstance(row, dict) and _clean(row.get("requirement_id"))
    )
    if actual_ids != expected_ids:
        issues.append("verification_baseline_requirement_scope_mismatch")
    return issues


def _requested_stage_without_result(execution: dict[str, Any]) -> str:
    """Return a durable paid stage whose response may have been lost."""
    if _clean(execution.get("status")) not in {"running", "failed"}:
        return ""
    current_stage = _clean(execution.get("current_stage"))
    if current_stage not in {"projects", "skills"}:
        return ""
    stage = (execution.get("stage_outputs") or {}).get(current_stage) or {}
    if stage.get("status") == "requested" and not isinstance(stage.get("result"), dict):
        return current_stage
    return ""


def _begin_retry_attempt(
    *, execution: dict[str, Any], actor_label: str, acknowledged: bool
) -> dict[str, Any]:
    """Append one durable retry attempt before any resumed stage work."""
    uncertain_stage = _requested_stage_without_result(execution)
    if execution.get("status") != "failed" and not uncertain_stage:
        return execution
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT * FROM phase9f_tailoring_executions WHERE execution_id=?",
            (execution["execution_id"],),
        ).fetchone()
        if row is None:
            raise Phase9FFExecutionError(
                "The Phase 9F-F execution disappeared before retry.",
                code="execution_missing",
            )
        current = _row_to_execution(row)
        attempt = int(current["attempt_count"]) + 1
        now = _now()
        connection.execute(
            """
            UPDATE phase9f_tailoring_executions
            SET status='preparing', current_stage='source_preparation',
                attempt_count=?, last_error_code=NULL, last_error_message=NULL,
                updated_at=?
            WHERE execution_id=?
            """,
            (attempt, now, current["execution_id"]),
        )
        _insert_event(
            connection,
            execution_id=current["execution_id"],
            application_id=current["application_id"],
            attempt_number=attempt,
            event_type="tailoring_execution_retry_started",
            status="preparing",
            current_stage="source_preparation",
            actor_label=actor_label,
            details={
                "prior_error_code": current["last_error_code"],
                "prior_uncertain_stage": uncertain_stage,
                "uncertain_model_retry_acknowledged": bool(acknowledged),
            },
            created_at=now,
        )
        connection.commit()
        updated = connection.execute(
            "SELECT * FROM phase9f_tailoring_executions WHERE execution_id=?",
            (current["execution_id"],),
        ).fetchone()
        return _row_to_execution(updated)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _legacy_private_stage_execution(execution: dict[str, Any]) -> bool:
    """Return whether an old F row owns private paid-stage state.

    Those rows remain historical/fail-closed.  New lifecycle work must never
    silently reinterpret private model or fitter output as a normal draft.
    """
    outputs = execution.get("stage_outputs") or {}
    if not isinstance(outputs, dict):
        return True
    if any(
        key in outputs
        for key in (
            "generation_settings",
            "projects",
            "skills",
            "fitting",
            "fitting_attempts",
        )
    ):
        return True
    if outputs.get("normal_lifecycle_adapter_version") == (
        PHASE9F_F_NORMAL_LIFECYCLE_VERSION
    ):
        return False
    return bool(
        _clean(execution.get("generation_id"))
    )


def is_phase9f_normal_lifecycle_execution(
    execution: dict[str, Any] | None,
) -> bool:
    """Identify an F context that delegates outputs to normal generations."""
    return bool(
        isinstance(execution, dict)
        and not _legacy_private_stage_execution(execution)
        and _clean(execution.get("confirmed_intensity")).lower()
        in VALID_INTENSITIES
    )


def _normal_generation_provenance(
    *,
    execution: dict[str, Any],
    prepared: dict[str, Any],
) -> dict[str, Any]:
    """Return immutable F facts copied into each normal generation."""
    identity = execution.get("semantic_identity") or {}
    return {
        "lifecycle_version": PHASE9F_F_NORMAL_LIFECYCLE_VERSION,
        "execution_id": _clean(execution.get("execution_id")),
        "execution_fingerprint": _clean(execution.get("execution_fingerprint")),
        "confirmation_id": _clean(execution.get("confirmation_id")),
        "confirmation_fingerprint": _clean(execution.get("confirmation_fingerprint")),
        "phase9e_decision_id": _clean(execution.get("phase9e_decision_id")),
        "phase9e_decision_fingerprint": _clean(
            execution.get("phase9e_decision_fingerprint")
        ),
        "starting_snapshot_fingerprint": _clean(
            execution.get("starting_snapshot_fingerprint")
        ),
        "exact_jd_identity_fingerprint": _clean(
            execution.get("exact_jd_identity_fingerprint")
        ),
        "evidence_snapshot_fingerprint": _clean(
            execution.get("evidence_snapshot_fingerprint")
        ),
        "section_scope_fingerprint": _clean(
            execution.get("section_scope_fingerprint")
        ),
        "source_artifact": {
            key: deepcopy((execution.get("source_artifact") or {}).get(key))
            for key in ("policy_version", "artifact_type", "sha256", "byte_size")
        },
        "confirmed_intensity": _clean(execution.get("confirmed_intensity")),
        "enabled_sections": list(
            (execution.get("section_scope") or {}).get("enabled_sections") or []
        ),
        "source": deepcopy(identity.get("source") or {}),
        "exact_jd": deepcopy(identity.get("exact_jd") or {}),
        "frozen_content": deepcopy(identity.get("frozen_content") or {}),
        "model_policy": deepcopy(prepared.get("model_policy") or {}),
    }


def _normal_generation_identity_settings(
    *,
    execution: dict[str, Any],
    prepared: dict[str, Any],
    settings: dict[str, Any],
    model: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build the immutable normal-generation inputs for one explicit action."""
    source_sections = materialise_phase9e_starting_sections(prepared["decision"])
    base_content_fingerprint = fingerprint_value(
        {
            "projects": source_sections["projects"],
            "skills": source_sections["skills"],
        }
    )
    phase9e_binding = {
        "decision_id": _clean(execution.get("phase9e_decision_id")),
        "decision_fingerprint": _clean(
            execution.get("phase9e_decision_fingerprint")
        ),
        "starting_snapshot_fingerprint": _clean(
            execution.get("starting_snapshot_fingerprint")
        ),
    }
    provenance = _normal_generation_provenance(
        execution=execution,
        prepared=prepared,
    )
    fingerprint_settings = {
        "max_projects": settings["max_projects"],
        "max_bullets": settings["max_bullets"],
        "bullet_allocation_mode": settings["bullet_allocation_mode"],
        "phase9e_binding": deepcopy(phase9e_binding),
        "phase9e_base_content_fingerprint": base_content_fingerprint,
        "phase9f_f_provenance": provenance,
        "generation_model": model,
    }
    return fingerprint_settings, {
        "phase9e_binding": phase9e_binding,
        "phase9e_base_content_fingerprint": base_content_fingerprint,
        "provenance": provenance,
    }


def _normal_lifecycle_state(generation: dict[str, Any]) -> dict[str, Any]:
    settings = generation.get("generation_settings") or {}
    if not isinstance(settings, dict):
        return {}
    state = settings.get("phase9f_f_normal_lifecycle") or {}
    return deepcopy(state) if isinstance(state, dict) else {}


def _normal_generation_is_complete(generation: dict[str, Any]) -> bool:
    state = _normal_lifecycle_state(generation)
    return bool(
        state.get("lifecycle_version") == PHASE9F_F_NORMAL_LIFECYCLE_VERSION
        and state.get("generation_status") == "completed"
    )


def _normal_generation_is_approvable(generation: dict[str, Any]) -> bool:
    state = _normal_lifecycle_state(generation)
    fit = state.get("fit") or {}
    return bool(
        _normal_generation_is_complete(generation)
        and isinstance(fit, dict)
        and fit.get("status") == "completed"
        and bool((generation.get("fit_result") or {}).get("fit_one_page"))
    )


def _normal_generation_matches_context(
    *, execution: dict[str, Any], generation: dict[str, Any]
) -> bool:
    state = _normal_lifecycle_state(generation)
    provenance = state.get("provenance") or {}
    return bool(
        provenance.get("execution_fingerprint")
        == execution.get("execution_fingerprint")
        and provenance.get("confirmation_fingerprint")
        == execution.get("confirmation_fingerprint")
        and provenance.get("phase9e_decision_fingerprint")
        == execution.get("phase9e_decision_fingerprint")
        and provenance.get("exact_jd_identity_fingerprint")
        == execution.get("exact_jd_identity_fingerprint")
        and provenance.get("evidence_snapshot_fingerprint")
        == execution.get("evidence_snapshot_fingerprint")
        and provenance.get("section_scope_fingerprint")
        == execution.get("section_scope_fingerprint")
    )


def _find_normal_generation(
    *,
    application_id: int,
    execution: dict[str, Any],
    input_fingerprint: str,
) -> dict[str, Any] | None:
    """Find a normal F generation, including an incomplete recoverable one."""
    cached = find_cached_tailoring_generation(
        application_id=int(application_id),
        input_fingerprint=str(input_fingerprint),
        generation_kind=PHASE9F_F_NORMAL_GENERATION_KIND,
    )
    if (
        cached is not None
        and _normal_generation_matches_context(
            execution=execution,
            generation=cached,
        )
    ):
        return cached
    # The normal cache deliberately excludes incomplete rows.  Scan the
    # ordinary version history only to recover the same durable partial paid
    # attempt, never to surface it as a complete cache hit.
    for generation in list_tailoring_generations(int(application_id)):
        state = _normal_lifecycle_state(generation)
        if (
            state.get("lifecycle_version") == PHASE9F_F_NORMAL_LIFECYCLE_VERSION
            and state.get("generation_input_fingerprint") == input_fingerprint
            and _normal_generation_matches_context(
                execution=execution,
                generation=generation,
            )
        ):
            return generation
    return None


def _record_normal_generation_event(
    *,
    execution: dict[str, Any],
    event_type: str,
    actor_label: str,
    details: dict[str, Any],
) -> None:
    """Append F audit evidence without turning the F row into a stage store."""
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        _insert_event(
            connection,
            execution_id=str(execution["execution_id"]),
            application_id=int(execution["application_id"]),
            attempt_number=1,
            event_type=event_type,
            status=str(execution.get("status") or "preparing"),
            current_stage="normal_application_generation",
            actor_label=actor_label,
            details=details,
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _save_normal_generation(
    *,
    application_id: int,
    generation_id: str,
    settings: dict[str, Any],
    generation_input_fingerprint: str,
    candidate_pool: Any = None,
    project_inputs: Any = None,
    fit_estimate: Any = None,
    projects: Any = None,
    skills: Any = None,
    fit_result: Any = None,
    base_content_fingerprint: str = "",
    content_fingerprint: str = "",
    content_changed: bool | None = None,
) -> dict[str, Any]:
    """Persist normal generation state; results never live in the F row."""
    save_application_tailoring_generation(
        application_id=int(application_id),
        generation_id=str(generation_id),
        candidate_pool=candidate_pool,
        project_inputs=project_inputs,
        fit_estimate=fit_estimate,
        projects=projects,
        skills=skills,
        fit_result=fit_result,
        generation_settings=settings,
        docx_path=(fit_result or {}).get("docx_path") if isinstance(fit_result, dict) else None,
        pdf_path=(fit_result or {}).get("pdf_path") if isinstance(fit_result, dict) else None,
    )
    record_generation_metadata(
        application_id=int(application_id),
        generation_id=str(generation_id),
        input_fingerprint=generation_input_fingerprint,
        generation_kind=PHASE9F_F_NORMAL_GENERATION_KIND,
        base_content_fingerprint=base_content_fingerprint,
        content_fingerprint=content_fingerprint,
        content_changed=content_changed,
        phase9e_decision_fingerprint=str(
            (settings.get("phase9e_binding") or {}).get("decision_fingerprint")
            or ""
        ),
    )
    saved = get_tailoring_generation(int(application_id), str(generation_id))
    if saved is None:
        raise Phase9FFExecutionError(
            "The normal Application Session generation could not be reloaded.",
            code="normal_generation_persistence_failed",
            stage="normal_generation",
        )
    return saved


def _persist_normal_generation_with_retry(**kwargs: Any) -> dict[str, Any]:
    try:
        return _save_normal_generation(**kwargs)
    except Exception as first_error:
        try:
            return _save_normal_generation(**kwargs)
        except Exception as second_error:
            raise Phase9FFExecutionError(
                "The successful model response could not be made durable. "
                "It will not be automatically repeated.",
                code="model_response_unrecoverable",
                stage="normal_generation",
            ) from second_error


def _normal_generation_evidence_pool(
    *,
    execution: dict[str, Any],
) -> dict[str, Any]:
    """Resolve the exact frozen evidence rows supplied to normal generation.

    Full tailoring keeps Phase 9A as the addressability/diagnostic gate but
    lets the normal Projects/Skills ranking pipeline see the complete immutable
    F Evidence Library snapshot. Minor remains deliberately bounded to the
    positive-gain Phase 9A subset.
    """
    intensity = _clean(execution.get("confirmed_intensity")).lower()
    scope = execution.get("section_scope") or {}

    if intensity == "full":
        snapshot = execution.get("evidence_snapshot") or {}
        rows = snapshot.get("rows")
        if not isinstance(rows, list):
            raise Phase9FFExecutionError(
                "The frozen Phase 9F-F Evidence Library snapshot is unavailable.",
                code="normal_generation_evidence_snapshot_missing",
                stage="normal_generation",
            )
        if _clean(snapshot.get("snapshot_fingerprint")) != _clean(
            execution.get("evidence_snapshot_fingerprint")
        ):
            raise Phase9FFExecutionError(
                "The frozen Phase 9F-F Evidence Library snapshot identity is inconsistent.",
                code="normal_generation_evidence_snapshot_mismatch",
                stage="normal_generation",
            )
        mode = "complete_frozen_snapshot"
    elif intensity == "minor":
        rows = scope.get("selected_evidence")
        if not isinstance(rows, list):
            raise Phase9FFExecutionError(
                "The frozen Phase 9F-F selected evidence subset is unavailable.",
                code="normal_generation_selected_evidence_missing",
                stage="normal_generation",
            )
        mode = "phase9a_selected_evidence"
    else:
        raise Phase9FFExecutionError(
            "The Phase 9F-F normal generation intensity is unsupported.",
            code="normal_generation_intensity_invalid",
            stage="normal_generation",
        )

    if any(not isinstance(row, dict) for row in rows):
        raise Phase9FFExecutionError(
            "The frozen Phase 9F-F evidence pool contains an invalid row.",
            code="normal_generation_evidence_row_invalid",
            stage="normal_generation",
        )

    resolved_rows = deepcopy(rows)
    return {
        "policy_version": PHASE9F_F_NORMAL_EVIDENCE_POOL_POLICY_VERSION,
        "mode": mode,
        "row_ids": [int(row.get("id") or 0) for row in resolved_rows],
        "rows_fingerprint": fingerprint_value(resolved_rows),
        "rows": resolved_rows,
    }


def _stage_input_for_normal_generation(
    *,
    execution: dict[str, Any],
    generation_input_fingerprint: str,
    stage: str,
    payload: dict[str, Any],
) -> str:
    return fingerprint_value(
        {
            "execution_fingerprint": execution["execution_fingerprint"],
            "generation_input_fingerprint": generation_input_fingerprint,
            "stage": stage,
            "payload": payload,
        }
    )


def _prepare_normal_generation(
    *,
    application_id: int,
    actor_label: str,
    generation_settings: dict[str, Any] | None,
    generation_model: str | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str, dict[str, Any]]:
    prepared_result = prepare_or_reuse_phase9f_tailoring_execution(
        application_id=int(application_id), actor_label=actor_label
    )
    execution = prepared_result["execution"]
    outputs = deepcopy(execution.get("stage_outputs") or {})
    if outputs.get("normal_lifecycle_adapter_version") != (
        PHASE9F_F_NORMAL_LIFECYCLE_VERSION
    ) and not _legacy_private_stage_execution(execution):
        outputs["normal_lifecycle_adapter_version"] = (
            PHASE9F_F_NORMAL_LIFECYCLE_VERSION
        )
        execution = _update_execution(
            execution_id=execution["execution_id"],
            status=str(execution.get("status") or "preparing"),
            current_stage="normal_lifecycle_ready",
            stage_outputs=outputs,
            event_type="normal_lifecycle_context_adopted",
            actor_label=actor_label,
            details={
                "normal_lifecycle_version": PHASE9F_F_NORMAL_LIFECYCLE_VERSION,
            },
        )
    if not is_phase9f_normal_lifecycle_execution(execution):
        raise Phase9FFExecutionError(
            "This historical Phase 9F-F execution owns private paid-stage state "
            "and cannot be silently adopted into the normal multi-generation lifecycle.",
            code="legacy_private_execution_not_adoptable",
            stage="normal_generation",
        )
    if execution.get("status") == "blocked":
        raise Phase9FFExecutionError(
            "The frozen Phase 9F-F scope has no addressable Projects or Skills change.",
            code="no_addressable_changes",
            stage="normal_generation",
        )
    settings = _canonical_generation_settings(generation_settings)
    model = _clean(generation_model) or _clean(get_active_model("analysis"))
    if not model:
        raise Phase9FFExecutionError(
            "A Projects/Skills generation model must be selected before paid work.",
            code="generation_model_missing",
            stage="normal_generation",
        )
    fingerprint_settings, persisted_context = _normal_generation_identity_settings(
        execution=execution,
        prepared=prepared_result["prepared"],
        settings=settings,
        model=model,
    )
    scope = execution.get("section_scope") or {}
    evidence_pool = _normal_generation_evidence_pool(execution=execution)
    fingerprint_settings["phase9f_f_evidence_pool"] = {
        key: deepcopy(evidence_pool[key])
        for key in (
            "policy_version",
            "mode",
            "row_ids",
            "rows_fingerprint",
        )
    }
    generation_input_fingerprint = build_tailoring_input_fingerprint(
        report=deepcopy(prepared_result["prepared"]["baseline_report"]),
        evidence_items=deepcopy(evidence_pool["rows"]),
        generation_settings=deepcopy(fingerprint_settings),
        generation_kind=PHASE9F_F_NORMAL_GENERATION_KIND,
        model_id=model,
        lock_projects=not bool(scope.get("projects_addressable")),
        lock_skills=not bool(scope.get("skills_addressable")),
        phase9e_binding=deepcopy(persisted_context["phase9e_binding"]),
    )
    return (
        execution,
        prepared_result["prepared"],
        settings,
        model,
        {
            "fingerprint_settings": fingerprint_settings,
            "persisted_context": persisted_context,
            "generation_input_fingerprint": generation_input_fingerprint,
            "evidence_pool": {
                key: deepcopy(evidence_pool[key])
                for key in (
                    "policy_version",
                    "mode",
                    "row_ids",
                    "rows_fingerprint",
                )
            },
            "evidence_rows": deepcopy(evidence_pool["rows"]),
        },
    )


def _new_normal_generation_settings(
    *,
    execution: dict[str, Any],
    settings: dict[str, Any],
    model: str,
    inputs: dict[str, Any],
) -> dict[str, Any]:
    scope = execution.get("section_scope") or {}
    lifecycle = {
        "lifecycle_version": PHASE9F_F_NORMAL_LIFECYCLE_VERSION,
        "generation_status": "incomplete",
        "generation_input_fingerprint": inputs["generation_input_fingerprint"],
        "model": model,
        "settings": deepcopy(settings),
        "provenance": deepcopy(inputs["persisted_context"]["provenance"]),
        "evidence_pool": deepcopy(inputs["evidence_pool"]),
        "stages": {
            "projects": {
                "status": "pending" if scope.get("projects_addressable") else "not_required"
            },
            "skills": {
                "status": "pending" if scope.get("skills_addressable") else "not_required"
            },
        },
        "fit": {"status": "not_started"},
    }
    return {
        **deepcopy(inputs["fingerprint_settings"]),
        "phase9f_f_normal_lifecycle": lifecycle,
    }


def _normal_stage_needs_acknowledgement(state: dict[str, Any]) -> str:
    for stage in ("projects", "skills"):
        row = (state.get("stages") or {}).get(stage) or {}
        if row.get("status") == "requested":
            return stage
    return ""


def run_phase9f_normal_generation(
    *,
    application_id: int,
    actor_label: str = "Local user",
    projects_writer: Callable[..., dict[str, Any]] = tailor_projects_section,
    skills_writer: Callable[..., dict[str, Any]] = tailor_skills_section,
    acknowledge_uncertain_model_retry: bool = False,
    generation_settings: dict[str, Any] | None = None,
    generation_model: str | None = None,
) -> dict[str, Any]:
    """Run/resume one normal Application Session generation under frozen F truth."""
    execution, prepared, settings, model, inputs = _prepare_normal_generation(
        application_id=application_id,
        actor_label=actor_label,
        generation_settings=generation_settings,
        generation_model=generation_model,
    )
    generation_input_fingerprint = inputs["generation_input_fingerprint"]
    generation = _find_normal_generation(
        application_id=application_id,
        execution=execution,
        input_fingerprint=generation_input_fingerprint,
    )
    if generation is not None and _normal_generation_is_complete(generation):
        return {
            "execution": execution,
            "generation": generation,
            "projects": deepcopy(generation.get("projects") or {}),
            "skills": deepcopy(generation.get("skills") or {}),
            "cache_status": "exact_normal_generation_reused",
        }

    if generation is None:
        generation_id = uuid.uuid4().hex
        persisted_settings = _new_normal_generation_settings(
            execution=execution,
            settings=settings,
            model=model,
            inputs=inputs,
        )
        generation = _save_normal_generation(
            application_id=application_id,
            generation_id=generation_id,
            settings=persisted_settings,
            generation_input_fingerprint=generation_input_fingerprint,
            base_content_fingerprint=inputs["persisted_context"]["phase9e_base_content_fingerprint"],
        )
    else:
        generation_id = str(generation["generation_id"])
        persisted_settings = deepcopy(generation.get("generation_settings") or {})

    lifecycle = _normal_lifecycle_state(generation)
    uncertain_stage = _normal_stage_needs_acknowledgement(lifecycle)
    if uncertain_stage and not acknowledge_uncertain_model_retry:
        raise Phase9FFExecutionError(
            "A prior paid model stage was interrupted before its response was proven durable. "
            "Explicit acknowledgement is required before retrying that exact request.",
            code="uncertain_model_retry_acknowledgement_required",
            stage=uncertain_stage,
        )

    scope = execution.get("section_scope") or {}
    baseline = prepared["baseline_report"]
    source_sections = materialise_phase9e_starting_sections(prepared["decision"])
    # Use the exact pool that was fingerprinted in _prepare_normal_generation.
    # Never re-read live Evidence Library state here.
    evidence_rows = deepcopy(inputs["evidence_rows"])
    projects = deepcopy(generation.get("projects") or source_sections["projects"])
    skills = deepcopy(generation.get("skills") or source_sections["skills"])
    lifecycle = _normal_lifecycle_state(generation)

    # Re-resolve and hash-check before a paid stage.  The normal generation
    # stores only identity/provenance; the immutable artifact resolver remains
    # the authority for the actual source bytes.
    _resolve_prepared_source_artifact(
        decision=prepared["decision"],
        confirmation=prepared["confirmation"],
        expected_identity=execution.get("source_artifact") or {},
    )

    def persist_current(
        *,
        candidate_pool: Any = None,
        project_inputs: Any = None,
        fit_estimate: Any = None,
        stage_result_projects: Any = None,
        stage_result_skills: Any = None,
        changed: bool | None = None,
        content_fingerprint: str = "",
    ) -> dict[str, Any]:
        return _persist_normal_generation_with_retry(
            application_id=application_id,
            generation_id=generation_id,
            settings=persisted_settings,
            generation_input_fingerprint=generation_input_fingerprint,
            candidate_pool=candidate_pool,
            project_inputs=project_inputs,
            fit_estimate=fit_estimate,
            projects=stage_result_projects,
            skills=stage_result_skills,
            base_content_fingerprint=inputs["persisted_context"]["phase9e_base_content_fingerprint"],
            content_fingerprint=content_fingerprint,
            content_changed=changed,
        )

    project_state = (lifecycle.get("stages") or {}).get("projects") or {}
    if scope.get("projects_addressable") and project_state.get("status") != "completed":
        project_input_fingerprint = _stage_input_for_normal_generation(
            execution=execution,
            generation_input_fingerprint=generation_input_fingerprint,
            stage="projects",
            payload={
                "resume_profile": baseline.get("resume_profile") or {},
                "jd_profile": baseline.get("jd_profile") or {},
                "stable_analysis": baseline.get("stable_analysis") or {},
                "evidence_fingerprint": fingerprint_value(evidence_rows),
                "settings": settings,
                "model": model,
            },
        )
        lifecycle["stages"]["projects"] = {
            "status": "requested",
            "input_fingerprint": project_input_fingerprint,
            "model": model,
        }
        persisted_settings["phase9f_f_normal_lifecycle"] = lifecycle
        persist_current()
        _record_normal_generation_event(
            execution=execution,
            event_type="normal_generation_stage_requested",
            actor_label=actor_label,
            details={
                "generation_id": generation_id,
                "generation_input_fingerprint": generation_input_fingerprint,
                "stage": "projects",
                "stage_input_fingerprint": project_input_fingerprint,
            },
        )
        reset_call_ledger()
        projects = projects_writer(
            **_writer_kwargs(
                projects_writer,
                {
                    "resume_profile": deepcopy(baseline.get("resume_profile") or {}),
                    "jd_profile": deepcopy(baseline.get("jd_profile") or {}),
                    "evidence_items": deepcopy(evidence_rows),
                    "max_projects": settings["max_projects"],
                    "max_bullets_per_project": settings["max_bullets"],
                    "bullet_allocation_mode": settings["bullet_allocation_mode"],
                    "keyword_match": deepcopy(baseline.get("keyword_match") or {}),
                    "raw_jd_text": str(baseline.get("raw_jd_text") or ""),
                    "stable_analysis": deepcopy(baseline.get("stable_analysis") or {}),
                },
                model,
            )
        )
        lifecycle["stages"]["projects"] = {
            "status": "completed",
            "input_fingerprint": project_input_fingerprint,
            "result_fingerprint": fingerprint_value(projects),
            "usage": summarise_call_usage(drain_call_ledger()),
            "model": model,
        }
        persisted_settings["phase9f_f_normal_lifecycle"] = lifecycle
        candidate_pool = build_project_candidate_pool(
            resume_profile=deepcopy(baseline.get("resume_profile") or {}),
            evidence_items=deepcopy(evidence_rows),
        )
        generation = persist_current(
            candidate_pool=candidate_pool,
            project_inputs={
                "resume_projects": deepcopy(
                    (baseline.get("resume_profile") or {}).get("projects") or []
                ),
                "evidence_items": deepcopy(evidence_rows),
            },
            stage_result_projects=projects,
        )
        _record_normal_generation_event(
            execution=execution,
            event_type="normal_generation_stage_completed",
            actor_label=actor_label,
            details={
                "generation_id": generation_id,
                "stage": "projects",
                "result_fingerprint": lifecycle["stages"]["projects"]["result_fingerprint"],
            },
        )

    lifecycle = _normal_lifecycle_state(generation)
    skills_state = (lifecycle.get("stages") or {}).get("skills") or {}
    if scope.get("skills_addressable") and skills_state.get("status") != "completed":
        skills_input_fingerprint = _stage_input_for_normal_generation(
            execution=execution,
            generation_input_fingerprint=generation_input_fingerprint,
            stage="skills",
            payload={
                "resume_profile": baseline.get("resume_profile") or {},
                "jd_profile": baseline.get("jd_profile") or {},
                "stable_analysis": baseline.get("stable_analysis") or {},
                "evidence_fingerprint": fingerprint_value(evidence_rows),
                "projects_fingerprint": fingerprint_value(projects),
                "settings": settings,
                "model": model,
            },
        )
        lifecycle["stages"]["skills"] = {
            "status": "requested",
            "input_fingerprint": skills_input_fingerprint,
            "model": model,
        }
        persisted_settings["phase9f_f_normal_lifecycle"] = lifecycle
        persist_current(stage_result_projects=projects)
        _record_normal_generation_event(
            execution=execution,
            event_type="normal_generation_stage_requested",
            actor_label=actor_label,
            details={
                "generation_id": generation_id,
                "generation_input_fingerprint": generation_input_fingerprint,
                "stage": "skills",
                "stage_input_fingerprint": skills_input_fingerprint,
            },
        )
        reset_call_ledger()
        skills = skills_writer(
            **_writer_kwargs(
                skills_writer,
                {
                    "resume_profile": deepcopy(baseline.get("resume_profile") or {}),
                    "jd_profile": deepcopy(baseline.get("jd_profile") or {}),
                    "evidence_items": deepcopy(evidence_rows),
                    "stable_analysis": deepcopy(baseline.get("stable_analysis") or {}),
                    "selected_projects_result": deepcopy(projects),
                },
                model,
            )
        )
        lifecycle["stages"]["skills"] = {
            "status": "completed",
            "input_fingerprint": skills_input_fingerprint,
            "result_fingerprint": fingerprint_value(skills),
            "usage": summarise_call_usage(drain_call_ledger()),
            "model": model,
        }
        persisted_settings["phase9f_f_normal_lifecycle"] = lifecycle
        generation = persist_current(
            stage_result_projects=projects,
            stage_result_skills=skills,
            fit_estimate=estimate_project_section_length(
                projects,
                max_projects=max(1, len(projects.get("recommended_projects") or [])),
                max_total_bullets=max(
                    1,
                    sum(
                        len(project.get("draft_bullets") or [])
                        for project in (projects.get("recommended_projects") or [])
                        if isinstance(project, dict)
                    ),
                ),
            ),
        )
        _record_normal_generation_event(
            execution=execution,
            event_type="normal_generation_stage_completed",
            actor_label=actor_label,
            details={
                "generation_id": generation_id,
                "stage": "skills",
                "result_fingerprint": lifecycle["stages"]["skills"]["result_fingerprint"],
            },
        )

    content_identity = _visible_resume_content_identity(
        prepared=prepared,
        projects=projects,
        skills=skills,
    )
    lifecycle = _normal_lifecycle_state(generation)
    lifecycle["generation_status"] = (
        "completed" if content_identity["content_changed"] else "blocked_no_semantic_content_change"
    )
    lifecycle["content_identity"] = deepcopy(content_identity)
    persisted_settings["phase9f_f_normal_lifecycle"] = lifecycle
    generation = persist_current(
        stage_result_projects=projects,
        stage_result_skills=skills,
        fit_estimate=estimate_project_section_length(
            projects,
            max_projects=max(1, len(projects.get("recommended_projects") or [])),
            max_total_bullets=max(
                1,
                sum(
                    len(project.get("draft_bullets") or [])
                    for project in (projects.get("recommended_projects") or [])
                    if isinstance(project, dict)
                ),
            ),
        ),
        changed=bool(content_identity["content_changed"]),
        content_fingerprint=str(content_identity["content_fingerprint"]),
    )
    _record_normal_generation_event(
        execution=execution,
        event_type="normal_generation_completed",
        actor_label=actor_label,
        details={
            "generation_id": generation_id,
            "generation_input_fingerprint": generation_input_fingerprint,
            "content_changed": bool(content_identity["content_changed"]),
            "content_fingerprint": content_identity["content_fingerprint"],
        },
    )
    if not content_identity["content_changed"]:
        raise Phase9FFExecutionError(
            "The completed tailored sections do not visibly differ from the frozen source.",
            code="no_semantic_content_change",
            stage="normal_generation",
        )
    return {
        "execution": execution,
        "generation": generation,
        "projects": projects,
        "skills": skills,
        "cache_status": "normal_generation_completed",
    }


def run_phase9f_normal_fit(
    *,
    application_id: int,
    generation_id: str,
    actor_label: str = "Local user",
    fit_writer: Callable[..., dict[str, Any]] = generate_tailored_resume_copy_fit_one_page,
    fit_settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fit one completed normal F generation without rerunning paid stages."""
    prepared_result = prepare_or_reuse_phase9f_tailoring_execution(
        application_id=int(application_id), actor_label=actor_label
    )
    execution = prepared_result["execution"]
    if not is_phase9f_normal_lifecycle_execution(execution):
        raise Phase9FFExecutionError(
            "This historical Phase 9F-F execution cannot use the new normal fit lifecycle.",
            code="legacy_private_execution_not_adoptable",
            stage="normal_fit",
        )
    generation = get_tailoring_generation(int(application_id), str(generation_id))
    if generation is None or not _normal_generation_matches_context(
        execution=execution, generation=generation
    ):
        raise Phase9FFExecutionError(
            "The selected normal résumé generation does not belong to this frozen Phase 9F-F context.",
            code="normal_generation_context_mismatch",
            stage="normal_fit",
        )
    if not _normal_generation_is_complete(generation):
        raise Phase9FFExecutionError(
            "Projects and Skills must complete before Build and Fit.",
            code="normal_generation_incomplete",
            stage="normal_fit",
        )
    projects = deepcopy(generation.get("projects") or {})
    skills = deepcopy(generation.get("skills") or {})
    if not projects or not skills:
        raise Phase9FFExecutionError(
            "The completed normal generation is missing Projects or Skills output.",
            code="normal_generation_output_missing",
            stage="normal_fit",
        )
    canonical_fit = _canonical_fit_settings(fit_settings)
    lifecycle = _normal_lifecycle_state(generation)
    fit_input_fingerprint = fingerprint_value(
        {
            "lifecycle_version": PHASE9F_F_NORMAL_LIFECYCLE_VERSION,
            "generation_input_fingerprint": lifecycle.get("generation_input_fingerprint"),
            "projects_fingerprint": fingerprint_value(projects),
            "skills_fingerprint": fingerprint_value(skills),
            "fit_settings": canonical_fit,
            "source_artifact": (execution.get("source_artifact") or {}),
            "section_scope_fingerprint": execution.get("section_scope_fingerprint"),
        }
    )
    prior_fit = lifecycle.get("fit") or {}
    if (
        prior_fit.get("status") == "completed"
        and prior_fit.get("input_fingerprint") == fit_input_fingerprint
        and isinstance(generation.get("fit_result"), dict)
    ):
        return {
            "execution": execution,
            "generation": generation,
            "fit_result": deepcopy(generation["fit_result"]),
            "cache_status": "exact_normal_fit_reused",
        }

    target = generation
    if isinstance(generation.get("fit_result"), dict):
        target = restore_tailoring_generation_as_draft(
            application_id=int(application_id),
            source_generation_id=str(generation["generation_id"]),
            new_generation_id=uuid.uuid4().hex,
        )
        lifecycle = _normal_lifecycle_state(target)
        lifecycle["fit"] = {
            "status": "not_started",
            "cloned_from_generation_id": str(generation["generation_id"]),
        }
    target_settings = deepcopy(target.get("generation_settings") or {})
    lifecycle = _normal_lifecycle_state(target)
    lifecycle["fit"] = {
        "status": "requested",
        "input_fingerprint": fit_input_fingerprint,
        "settings": deepcopy(canonical_fit),
    }
    target_settings["phase9f_f_normal_lifecycle"] = lifecycle
    generation_input_fingerprint = str(lifecycle.get("generation_input_fingerprint") or "")
    _save_normal_generation(
        application_id=application_id,
        generation_id=str(target["generation_id"]),
        settings=target_settings,
        generation_input_fingerprint=generation_input_fingerprint,
        projects=projects,
        skills=skills,
        base_content_fingerprint=str(
            (lifecycle.get("content_identity") or {}).get("base_content_fingerprint") or ""
        ),
        content_fingerprint=str(
            (lifecycle.get("content_identity") or {}).get("content_fingerprint") or ""
        ),
        content_changed=True,
    )
    _record_normal_generation_event(
        execution=execution,
        event_type="normal_fit_requested",
        actor_label=actor_label,
        details={
            "generation_id": str(target["generation_id"]),
            "fit_input_fingerprint": fit_input_fingerprint,
        },
    )
    prepared = prepared_result["prepared"]
    artifact = _resolve_prepared_source_artifact(
        decision=prepared["decision"],
        confirmation=prepared["confirmation"],
        expected_identity=execution.get("source_artifact") or {},
    )
    source_path, temporary = _materialise_exact_source_docx(artifact)
    try:
        generation_values = lifecycle.get("settings") or {}
        fit_max_bullets = resolve_effective_fitting_bullet_ceiling(
            projects,
            configured_max_bullets_per_project=int(generation_values.get("max_bullets") or 1),
        )
        if generation_values.get("bullet_allocation_mode") == "all_canonical_before_fitting":
            fit_max_bullets = max(
                fit_max_bullets,
                *[
                    len(project.get("draft_bullets") or [])
                    for project in (projects.get("recommended_projects") or [])
                    if isinstance(project, dict)
                ],
            )
        fit_result = fit_writer(
            saved_resume_docx_path=source_path,
            tailored_projects=deepcopy(projects),
            tailored_skills=deepcopy(skills),
            application_id=int(application_id),
            max_projects=int(generation_values.get("max_projects") or 1),
            max_bullets_per_project=fit_max_bullets,
            spacing_mode=canonical_fit["spacing_mode"],
            project_spacing_pt=canonical_fit["project_spacing_pt"],
            after_projects_spacing_pt=canonical_fit["after_projects_spacing_pt"],
            blank_lines_between_projects=canonical_fit["blank_lines_between_projects"],
            blank_lines_after_projects=canonical_fit["blank_lines_after_projects"],
            add_spacing_before_first_project=canonical_fit["add_spacing_before_first_project"],
            use_compact_before_delete=canonical_fit["use_compact_before_delete"],
            prefer_balanced_bullets=canonical_fit["prefer_balanced_bullets"],
            allow_skills_compaction=canonical_fit["allow_skills_compaction"],
            lock_projects=not bool((execution.get("section_scope") or {}).get("projects_addressable")),
            lock_skills=not bool((execution.get("section_scope") or {}).get("skills_addressable")),
            page_density_mode=canonical_fit["page_density_mode"],
            allow_margin_compaction=canonical_fit["allow_margin_compaction"],
            project_header_layout=canonical_fit["project_header_layout"],
            project_metadata_style=canonical_fit["project_metadata_style"],
            generation_id=str(target["generation_id"]),
        )
    finally:
        temporary.cleanup()
    if not bool(fit_result.get("fit_one_page")):
        lifecycle["fit"] = {
            "status": "failed",
            "input_fingerprint": fit_input_fingerprint,
            "settings": deepcopy(canonical_fit),
        }
        target_settings["phase9f_f_normal_lifecycle"] = lifecycle
        _save_normal_generation(
            application_id=application_id,
            generation_id=str(target["generation_id"]),
            settings=target_settings,
            generation_input_fingerprint=generation_input_fingerprint,
            projects=projects,
            skills=skills,
            fit_result=fit_result,
            base_content_fingerprint=str((lifecycle.get("content_identity") or {}).get("base_content_fingerprint") or ""),
            content_fingerprint=str((lifecycle.get("content_identity") or {}).get("content_fingerprint") or ""),
            content_changed=True,
        )
        raise Phase9FFExecutionError(
            "The deterministic fitter did not produce a one-page résumé.",
            code="fit_one_page_failed",
            stage="normal_fit",
        )
    lifecycle["fit"] = {
        "status": "completed",
        "input_fingerprint": fit_input_fingerprint,
        "settings": deepcopy(canonical_fit),
        "result_fingerprint": fingerprint_value(fit_result),
    }
    target_settings["phase9f_f_normal_lifecycle"] = lifecycle
    saved = _save_normal_generation(
        application_id=application_id,
        generation_id=str(target["generation_id"]),
        settings=target_settings,
        generation_input_fingerprint=generation_input_fingerprint,
        projects=projects,
        skills=skills,
        fit_result=fit_result,
        base_content_fingerprint=str((lifecycle.get("content_identity") or {}).get("base_content_fingerprint") or ""),
        content_fingerprint=str((lifecycle.get("content_identity") or {}).get("content_fingerprint") or ""),
        content_changed=True,
    )
    _record_normal_generation_event(
        execution=execution,
        event_type="normal_fit_completed",
        actor_label=actor_label,
        details={
            "generation_id": str(target["generation_id"]),
            "fit_input_fingerprint": fit_input_fingerprint,
            "fit_result_fingerprint": lifecycle["fit"]["result_fingerprint"],
        },
    )
    return {
        "execution": execution,
        "generation": saved,
        "fit_result": fit_result,
        "cache_status": "normal_fit_completed",
    }


def _writer_kwargs(
    writer: Callable[..., dict[str, Any]],
    payload: dict[str, Any],
    model: str,
) -> dict[str, Any]:
    """Pass frozen model identity without breaking legacy test writers."""
    try:
        parameters = inspect.signature(writer).parameters.values()
        supports_model = any(
            parameter.name == "model"
            or parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in parameters
        )
    except (TypeError, ValueError):
        supports_model = True
    if supports_model:
        payload["model"] = model
    return payload


def execute_phase9f_tailoring(
    *,
    application_id: int,
    actor_label: str = "Local user",
    projects_writer: Callable[..., dict[str, Any]] = tailor_projects_section,
    skills_writer: Callable[..., dict[str, Any]] = tailor_skills_section,
    fit_writer: Callable[..., dict[str, Any]] = generate_tailored_resume_copy_fit_one_page,
    acknowledge_uncertain_model_retry: bool = False,
    generation_settings: dict[str, Any] | None = None,
    generation_model: str | None = None,
    fit_settings: dict[str, Any] | None = None,
    stop_after_sections: bool = False,
    require_completed_sections: bool = False,
) -> dict[str, Any]:
    """Begin or resume one Minor/Full F execution without duplicating durable work."""
    prepared_result = prepare_or_reuse_phase9f_tailoring_execution(
        application_id=int(application_id), actor_label=actor_label
    )
    prepared = prepared_result["prepared"]
    execution = prepared_result["execution"]
    if execution["status"] in {"completed", "blocked", "waiting_for_approval", "waiting_for_phase8"}:
        return {"execution": execution, "cache_status": execution.get("cache_status", "reused")}
    uncertain_stage = _requested_stage_without_result(execution)
    if (
        execution["status"] == "failed"
        and execution.get("last_error_code") == "model_response_unrecoverable"
        and not acknowledge_uncertain_model_retry
    ):
        raise Phase9FFExecutionError(
            "A prior model response was not durably persisted. Explicit acknowledgement is required before another paid attempt.",
            code="uncertain_model_retry_acknowledgement_required",
            stage=execution.get("current_stage") or "unknown",
        )
    if uncertain_stage and not acknowledge_uncertain_model_retry:
        raise Phase9FFExecutionError(
            "A prior paid model stage was interrupted before its response was proven durable. Explicit acknowledgement is required before another paid attempt.",
            code="uncertain_model_retry_acknowledgement_required",
            stage=uncertain_stage,
        )
    execution = _begin_retry_attempt(
        execution=execution,
        actor_label=actor_label,
        acknowledged=acknowledge_uncertain_model_retry,
    )

    section_scope = execution["section_scope"]
    if not section_scope.get("enabled_sections"):
        blocked = _update_execution(
            execution_id=execution["execution_id"],
            status="blocked",
            current_stage="no_addressable_changes",
            terminal_reason="no_addressable_changes",
            event_type="no_addressable_changes",
            actor_label=actor_label,
            details={
                "projects_addressable": False,
                "skills_addressable": False,
                "model_call_count": 0,
            },
        )
        return {"execution": blocked, "cache_status": "blocked"}

    completed_projects = _completed_stage(execution, "projects")
    completed_skills = _completed_stage(execution, "skills")
    generation_needed = bool(
        (section_scope.get("projects_addressable") and completed_projects is None)
        or (section_scope.get("skills_addressable") and completed_skills is None)
    )
    generation_snapshot = _generation_settings_snapshot(execution)
    if generation_needed:
        execution, generation_snapshot = _freeze_or_reuse_generation_settings(
            execution=execution,
            generation_settings=generation_settings,
            selected_model=generation_model,
            actor_label=actor_label,
        )
    elif generation_snapshot is None:
        raise Phase9FFExecutionError(
            "Completed Phase 9F-F section outputs are missing their frozen generation settings.",
            code="generation_settings_missing",
            stage="generation_settings",
        )

    starting_sections = materialise_phase9e_starting_sections(prepared["decision"])
    evidence_rows = deepcopy(section_scope.get("selected_evidence") or [])
    baseline = prepared["baseline_report"]
    projects = deepcopy(starting_sections["projects"])
    skills = deepcopy(starting_sections["skills"])
    source_temporary: tempfile.TemporaryDirectory[str] | None = None
    try:
        # Revalidate the exact immutable DOCX before a paid stage. The persisted
        # source artifact identity remains authoritative; a path is only a
        # location used by the resolver, never an input to fitting.
        source_identity = execution.get("source_artifact") or {}
        if not source_identity:
            raise Phase9FFExecutionError(
                "The frozen Phase 9F-F DOCX artifact identity is unavailable.",
                code="source_docx_identity_missing",
                stage="source_preparation",
            )
        _resolve_prepared_source_artifact(
            decision=prepared["decision"],
            confirmation=prepared["confirmation"],
            expected_identity=source_identity,
        )
        prior_projects = _completed_stage(execution, "projects")
        if section_scope.get("projects_addressable"):
            project_input = {
                "resume_profile": baseline["resume_profile"],
                "jd_profile": baseline.get("jd_profile") or {},
                "stable_analysis": baseline.get("stable_analysis") or {},
                "evidence_fingerprint": fingerprint_value(evidence_rows),
                "generation_settings": deepcopy(generation_snapshot["settings"]),
                "generation_settings_fingerprint": generation_snapshot[
                    "settings_fingerprint"
                ],
                "model": generation_snapshot["model"],
            }
            project_input_fp = _stage_input_fingerprint(
                execution=execution, stage="projects", payload=project_input
            )
            if prior_projects and prior_projects.get("input_fingerprint") == project_input_fp:
                projects = deepcopy(prior_projects["result"])
            else:
                if require_completed_sections:
                    raise Phase9FFExecutionError(
                        "Projects must complete through the normal Projects and Skills stage before fitting.",
                        code="projects_stage_incomplete",
                        stage="projects",
                    )
                execution = _mark_stage_requested(
                    execution=execution,
                    stage="projects",
                    input_fingerprint=project_input_fp,
                    actor_label=actor_label,
                    settings_snapshot=generation_snapshot,
                )
                reset_call_ledger()
                projects = projects_writer(**_writer_kwargs(
                    projects_writer,
                    {
                        "resume_profile": deepcopy(baseline["resume_profile"]),
                        "jd_profile": deepcopy(baseline.get("jd_profile") or {}),
                        "evidence_items": deepcopy(evidence_rows),
                        "max_projects": generation_snapshot["settings"]["max_projects"],
                        "max_bullets_per_project": generation_snapshot["settings"]["max_bullets"],
                        "bullet_allocation_mode": generation_snapshot["settings"]["bullet_allocation_mode"],
                        "keyword_match": deepcopy(baseline.get("keyword_match") or {}),
                        "raw_jd_text": str(baseline.get("raw_jd_text") or ""),
                        "stable_analysis": deepcopy(baseline.get("stable_analysis") or {}),
                    },
                    str(project_input["model"] or ""),
                ))
                usage = summarise_call_usage(drain_call_ledger())
                execution = _persist_stage_result_with_retry(
                    execution=execution,
                    stage="projects",
                    input_fingerprint=project_input_fp,
                    result=projects,
                    usage=usage,
                    actor_label=actor_label,
                )

        prior_skills = _completed_stage(execution, "skills")
        if section_scope.get("skills_addressable"):
            skills_input = {
                "resume_profile": baseline["resume_profile"],
                "jd_profile": baseline.get("jd_profile") or {},
                "stable_analysis": baseline.get("stable_analysis") or {},
                "evidence_fingerprint": fingerprint_value(evidence_rows),
                "projects_fingerprint": fingerprint_value(projects),
                "generation_settings": deepcopy(generation_snapshot["settings"]),
                "generation_settings_fingerprint": generation_snapshot[
                    "settings_fingerprint"
                ],
                "model": generation_snapshot["model"],
            }
            skills_input_fp = _stage_input_fingerprint(
                execution=execution, stage="skills", payload=skills_input
            )
            if prior_skills and prior_skills.get("input_fingerprint") == skills_input_fp:
                skills = deepcopy(prior_skills["result"])
            else:
                if require_completed_sections:
                    raise Phase9FFExecutionError(
                        "Skills must complete through the normal Projects and Skills stage before fitting.",
                        code="skills_stage_incomplete",
                        stage="skills",
                    )
                execution = _mark_stage_requested(
                    execution=execution,
                    stage="skills",
                    input_fingerprint=skills_input_fp,
                    actor_label=actor_label,
                    settings_snapshot=generation_snapshot,
                )
                reset_call_ledger()
                skills = skills_writer(**_writer_kwargs(
                    skills_writer,
                    {
                        "resume_profile": deepcopy(baseline["resume_profile"]),
                        "jd_profile": deepcopy(baseline.get("jd_profile") or {}),
                        "evidence_items": deepcopy(evidence_rows),
                        "stable_analysis": deepcopy(baseline.get("stable_analysis") or {}),
                        "selected_projects_result": deepcopy(projects),
                    },
                    str(skills_input["model"] or ""),
                ))
                usage = summarise_call_usage(drain_call_ledger())
                execution = _persist_stage_result_with_retry(
                    execution=execution,
                    stage="skills",
                    input_fingerprint=skills_input_fp,
                    result=skills,
                    usage=usage,
                    actor_label=actor_label,
                )

        content_identity = _visible_resume_content_identity(
            prepared=prepared,
            projects=projects,
            skills=skills,
        )
        if not content_identity["content_changed"]:
            blocked = _update_execution(
                execution_id=execution["execution_id"],
                status="blocked",
                current_stage="no_semantic_content_change",
                terminal_reason="no_semantic_content_change",
                event_type="no_semantic_content_change",
                actor_label=actor_label,
                details={
                    "content_change_policy_version": content_identity[
                        "policy_version"
                    ],
                    "base_content_fingerprint": content_identity[
                        "base_content_fingerprint"
                    ],
                    "content_fingerprint": content_identity["content_fingerprint"],
                },
            )
            return {"execution": blocked, "cache_status": "blocked"}

        if stop_after_sections:
            ready = _update_execution(
                execution_id=execution["execution_id"],
                status="running",
                current_stage="build_fit_pending",
                event_type="projects_skills_ready_for_existing_build_fit",
                actor_label=actor_label,
                details={
                    "projects_fingerprint": fingerprint_value(projects),
                    "skills_fingerprint": fingerprint_value(skills),
                    "content_fingerprint": content_identity["content_fingerprint"],
                },
            )
            return {
                "execution": ready,
                "projects": projects,
                "skills": skills,
                "cache_status": "sections_ready_for_build_fit",
            }

        fit_stage = _completed_stage(execution, "fitting")
        if fit_stage:
            fit_result = deepcopy(fit_stage["result"])
        else:
            canonical_fit_settings = _canonical_fit_settings(fit_settings)
            generation_values = generation_snapshot["settings"]
            fit_max_bullets = resolve_effective_fitting_bullet_ceiling(
                projects,
                configured_max_bullets_per_project=generation_values["max_bullets"],
            )
            if (
                generation_values["bullet_allocation_mode"]
                == "all_canonical_before_fitting"
            ):
                fit_max_bullets = max(
                    generation_values["max_bullets"],
                    *[
                        len(project.get("draft_bullets") or [])
                        for project in (
                            projects.get("recommended_projects") or []
                        )
                        if isinstance(project, dict)
                    ],
                )
            fit_allocation_mode = resolve_fitting_bullet_allocation_mode(
                projects,
                fallback_mode=generation_values["bullet_allocation_mode"],
            )
            fit_snapshot = {
                "policy_version": PHASE9F_F_FIT_SETTINGS_POLICY_VERSION,
                "settings": canonical_fit_settings,
                "settings_fingerprint": fingerprint_value(canonical_fit_settings),
                "generation_settings_fingerprint": generation_snapshot[
                    "settings_fingerprint"
                ],
                "effective_max_projects": generation_values["max_projects"],
                "effective_max_bullets_per_project": fit_max_bullets,
                "effective_bullet_allocation_mode": fit_allocation_mode,
                "frozen_reason": "explicit_build_and_fit_action",
            }
            fit_input = {
                "fit_snapshot": deepcopy(fit_snapshot),
                "projects_fingerprint": fingerprint_value(projects),
                "skills_fingerprint": fingerprint_value(skills),
                "source_artifact": deepcopy(source_identity),
                "section_scope_fingerprint": execution["section_scope_fingerprint"],
            }
            fit_input_fp = _stage_input_fingerprint(
                execution=execution,
                stage="fitting",
                payload=fit_input,
            )
            # Resolve and hash-check again immediately before fitting. This
            # catches source replacement after durable model stages without
            # repeating those paid calls on the later retry.
            fitting_artifact = _resolve_prepared_source_artifact(
                decision=prepared["decision"],
                confirmation=prepared["confirmation"],
                expected_identity=source_identity,
            )
            source_path, source_temporary = _materialise_exact_source_docx(
                fitting_artifact
            )
            outputs = deepcopy(execution.get("stage_outputs") or {})
            attempts = list(outputs.get("fitting_attempts") or [])
            attempt = {
                "status": "requested",
                "attempt_number": int(execution["attempt_count"]),
                "input_fingerprint": fit_input_fp,
                "fit_settings": deepcopy(fit_snapshot),
            }
            attempts.append(attempt)
            outputs["fitting_attempts"] = attempts
            outputs["fitting"] = {
                "status": "requested",
                "input_fingerprint": fit_input_fp,
                "fit_settings": deepcopy(fit_snapshot),
                "attempt_number": int(execution["attempt_count"]),
            }
            execution = _update_execution(
                execution_id=execution["execution_id"],
                status="running",
                current_stage="fitting",
                stage_outputs=outputs,
                event_type="deterministic_fitting_started",
                actor_label=actor_label,
                details={
                    "input_fingerprint": fit_input_fp,
                    "fit_settings_fingerprint": fit_snapshot["settings_fingerprint"],
                    "projects_fingerprint": fit_input["projects_fingerprint"],
                    "skills_fingerprint": fit_input["skills_fingerprint"],
                },
            )
            fit_result = fit_writer(
                saved_resume_docx_path=source_path,
                tailored_projects=deepcopy(projects),
                tailored_skills=deepcopy(skills),
                application_id=int(application_id),
                max_projects=generation_values["max_projects"],
                max_bullets_per_project=fit_max_bullets,
                spacing_mode=canonical_fit_settings["spacing_mode"],
                project_spacing_pt=canonical_fit_settings["project_spacing_pt"],
                after_projects_spacing_pt=canonical_fit_settings[
                    "after_projects_spacing_pt"
                ],
                blank_lines_between_projects=canonical_fit_settings[
                    "blank_lines_between_projects"
                ],
                blank_lines_after_projects=canonical_fit_settings[
                    "blank_lines_after_projects"
                ],
                add_spacing_before_first_project=canonical_fit_settings[
                    "add_spacing_before_first_project"
                ],
                use_compact_before_delete=canonical_fit_settings[
                    "use_compact_before_delete"
                ],
                prefer_balanced_bullets=canonical_fit_settings[
                    "prefer_balanced_bullets"
                ],
                allow_skills_compaction=canonical_fit_settings[
                    "allow_skills_compaction"
                ],
                lock_projects=not bool(section_scope.get("projects_addressable")),
                lock_skills=not bool(section_scope.get("skills_addressable")),
                page_density_mode=canonical_fit_settings["page_density_mode"],
                allow_margin_compaction=canonical_fit_settings[
                    "allow_margin_compaction"
                ],
                project_header_layout=canonical_fit_settings[
                    "project_header_layout"
                ],
                project_metadata_style=canonical_fit_settings[
                    "project_metadata_style"
                ],
                generation_id=execution["execution_id"],
            )
            if not bool(fit_result.get("fit_one_page")):
                raise Phase9FFExecutionError(
                    "The deterministic fitter did not produce a one-page résumé.",
                    code="fit_one_page_failed",
                    stage="fitting",
                )
            outputs = deepcopy(execution.get("stage_outputs") or {})
            outputs["fitting"] = {
                "status": "completed",
                "input_fingerprint": fit_input_fp,
                "fit_settings": deepcopy(fit_snapshot),
                "result": deepcopy(fit_result),
                "result_fingerprint": fingerprint_value(fit_result),
                "attempt_number": int(execution["attempt_count"]),
            }
            attempts = list(outputs.get("fitting_attempts") or [])
            if attempts:
                attempts[-1] = {
                    **attempts[-1],
                    "status": "completed",
                    "result_fingerprint": outputs["fitting"]["result_fingerprint"],
                }
                outputs["fitting_attempts"] = attempts
            execution = _update_execution(
                execution_id=execution["execution_id"],
                status="running",
                current_stage="fitting",
                stage_outputs=outputs,
                event_type="deterministic_fitting_completed",
                actor_label=actor_label,
                details={
                    "input_fingerprint": fit_input_fp,
                    "fit_settings_fingerprint": fit_snapshot["settings_fingerprint"],
                    "fit_result_fingerprint": outputs["fitting"]["result_fingerprint"],
                },
            )

        draft = _materialise_changed_draft(
            execution=execution,
            prepared=prepared,
            projects=projects,
            skills=skills,
            fit_result=fit_result,
            content_identity=content_identity,
        )
        execution = _update_execution(
            execution_id=execution["execution_id"],
            status="waiting_for_approval",
            current_stage="changed_content_ready",
            generation_id=draft["generation_id"],
            event_type="complete_changed_draft_materialised",
            actor_label=actor_label,
            details={"generation_id": draft["generation_id"], "content_changed": True},
        )
        return {"execution": execution, "draft": draft, "cache_status": "draft_ready"}
    except Exception as exc:
        try:
            failed = _mark_failure(execution, exc, actor_label)
        except Exception:
            raise exc
        return {"execution": failed, "cache_status": "failed", "error": str(exc)}
    finally:
        if source_temporary is not None:
            source_temporary.cleanup()


def run_phase9f_tailoring_projects_skills(
    *,
    application_id: int,
    actor_label: str = "Local user",
    projects_writer: Callable[..., dict[str, Any]] = tailor_projects_section,
    skills_writer: Callable[..., dict[str, Any]] = tailor_skills_section,
    acknowledge_uncertain_model_retry: bool = False,
    generation_settings: dict[str, Any] | None = None,
    generation_model: str | None = None,
) -> dict[str, Any]:
    """Run only F's durable Projects/Skills stage for the normal UI."""
    return execute_phase9f_tailoring(
        application_id=application_id,
        actor_label=actor_label,
        projects_writer=projects_writer,
        skills_writer=skills_writer,
        acknowledge_uncertain_model_retry=acknowledge_uncertain_model_retry,
        generation_settings=generation_settings,
        generation_model=generation_model,
        stop_after_sections=True,
    )


def run_phase9f_tailoring_fit(
    *,
    application_id: int,
    actor_label: str = "Local user",
    fit_writer: Callable[..., dict[str, Any]] = generate_tailored_resume_copy_fit_one_page,
    fit_settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run only deterministic fitting after durable F sections are complete."""
    prepared_result = prepare_or_reuse_phase9f_tailoring_execution(
        application_id=int(application_id), actor_label=actor_label
    )
    execution = prepared_result["execution"]
    if execution["status"] in {
        "completed",
        "blocked",
        "waiting_for_approval",
        "waiting_for_phase8",
    }:
        return {"execution": execution, "cache_status": "reused"}
    for stage in execution.get("section_scope", {}).get("enabled_sections") or []:
        if _completed_stage(execution, str(stage)) is None:
            raise Phase9FFExecutionError(
                "Complete the normal Projects and Skills stage before Build and Fit.",
                code="projects_skills_stage_incomplete",
                stage=str(stage),
            )
    return execute_phase9f_tailoring(
        application_id=application_id,
        actor_label=actor_label,
        fit_writer=fit_writer,
        fit_settings=fit_settings,
        require_completed_sections=True,
    )


def reconcile_phase9f_tailoring_approval(
    *, application_id: int, actor_label: str = "Local user"
) -> dict[str, Any] | None:
    """Observe the existing approval lifecycle; do not approve on F's behalf."""
    execution = get_phase9f_tailoring_execution(application_id)
    if execution is None or not execution.get("generation_id"):
        return execution
    generation = get_tailoring_generation(application_id, execution["generation_id"])
    if generation is None or generation.get("status") != "approved":
        return execution
    if execution["status"] in {"waiting_for_phase8", "completed"}:
        return execution
    return _update_execution(
        execution_id=execution["execution_id"],
        status="waiting_for_phase8",
        current_stage="approved_changed_output",
        event_type="existing_approval_observed",
        actor_label=actor_label,
        details={"generation_id": execution["generation_id"]},
    )


def run_or_reuse_phase9f_tailoring_phase8(
    *, application_id: int, actor_label: str = "Local user"
) -> dict[str, Any]:
    """Run existing authoritative Phase 8 only after matching approval."""
    execution = reconcile_phase9f_tailoring_approval(
        application_id=application_id, actor_label=actor_label
    )
    if execution is None or execution.get("status") != "waiting_for_phase8":
        raise Phase9FFExecutionError(
            "Phase 9F-F requires the exact changed draft to be approved before Phase 8.",
            code="phase8_approval_required",
            stage="phase8",
        )
    generation = get_tailoring_generation(application_id, execution["generation_id"])
    if generation is None or generation.get("status") != "approved":
        raise Phase9FFExecutionError(
            "The exact Phase 9F-F draft is no longer approved.",
            code="phase8_generation_not_approved",
            stage="phase8",
        )
    prepared = _prepare_frozen_phase8_context(execution)
    result = build_phase8_verification(
        baseline_report=prepared["baseline_report"],
        generation_state=generation,
        raw_jd_text=str(prepared["baseline_report"].get("raw_jd_text") or ""),
    )
    latest = save_tailoring_verification(
        application_id=application_id,
        generation_id=execution["generation_id"],
        result=result,
    )
    issues = _phase8_validity_issues(
        verification=latest,
        expected=result,
        execution=execution,
    )
    if issues:
        retryable = _update_execution(
            execution_id=execution["execution_id"],
            status="waiting_for_phase8",
            current_stage="phase8_verification_invalid",
            event_type="phase8_verification_rejected",
            actor_label=actor_label,
            details={
                "generation_id": execution["generation_id"],
                "verification_fingerprint": latest.get("verification_fingerprint"),
                "issues": issues,
            },
        )
        return {
            "execution": retryable,
            "verification": latest,
            "cache_status": "phase8_retry_required",
            "issues": issues,
        }
    return {
        "execution": _update_execution(
            execution_id=execution["execution_id"],
            status="completed",
            current_stage="phase8_verified",
            phase8_verification=latest,
            event_type="existing_phase8_completed",
            actor_label=actor_label,
            details={
                "generation_id": execution["generation_id"],
                "verification_fingerprint": latest.get("verification_fingerprint"),
            },
        ),
        "verification": latest,
    }


def run_or_reuse_phase9f_normal_generation_phase8(
    *,
    application_id: int,
    generation_id: str,
    actor_label: str = "Local user",
) -> dict[str, Any]:
    """Run existing Phase 8 for the selected approved normal F generation."""
    execution = get_phase9f_tailoring_execution(int(application_id))
    generation = get_tailoring_generation(int(application_id), str(generation_id))
    if (
        not is_phase9f_normal_lifecycle_execution(execution)
        or generation is None
        or not _normal_generation_matches_context(
            execution=execution or {}, generation=generation
        )
        or not _normal_generation_is_approvable(generation)
        or generation.get("status") != "approved"
    ):
        raise Phase9FFExecutionError(
            "Phase 8 requires the exact approved, completed normal generation "
            "for this frozen Phase 9F-F context.",
            code="normal_phase8_generation_invalid",
            stage="phase8",
        )
    prepared = _prepare_frozen_phase8_context(execution)
    result = build_phase8_verification(
        baseline_report=prepared["baseline_report"],
        generation_state=generation,
        raw_jd_text=str(prepared["baseline_report"].get("raw_jd_text") or ""),
    )
    latest = save_tailoring_verification(
        application_id=int(application_id),
        generation_id=str(generation_id),
        result=result,
    )
    issues = [
        issue
        for issue in _phase8_validity_issues(
            verification=latest,
            expected=result,
            execution={**execution, "generation_id": str(generation_id)},
        )
        if issue != "verification_generation_mismatch"
    ]
    if issues:
        _record_normal_generation_event(
            execution=execution,
            event_type="normal_phase8_verification_rejected",
            actor_label=actor_label,
            details={
                "generation_id": str(generation_id),
                "verification_fingerprint": latest.get("verification_fingerprint"),
                "issues": issues,
            },
        )
        return {
            "execution": execution,
            "verification": latest,
            "cache_status": "phase8_retry_required",
            "issues": issues,
        }
    # F records the final selected generation as provenance only.  The normal
    # workspace must continue to show every current-scope normal generation.
    outputs = deepcopy(execution.get("stage_outputs") or {})
    outputs["normal_lifecycle_adapter_version"] = (
        PHASE9F_F_NORMAL_LIFECYCLE_VERSION
    )
    outputs["normal_phase8"] = {
        "generation_id": str(generation_id),
        "verification_id": latest.get("verification_id"),
        "verification_fingerprint": latest.get("verification_fingerprint"),
    }
    updated = _update_execution(
        execution_id=execution["execution_id"],
        status="completed",
        current_stage="normal_phase8_verified",
        stage_outputs=outputs,
        generation_id=str(generation_id),
        phase8_verification=latest,
        event_type="normal_phase8_completed",
        actor_label=actor_label,
        details={
            "generation_id": str(generation_id),
            "verification_fingerprint": latest.get("verification_fingerprint"),
        },
    )
    return {
        "execution": updated,
        "verification": latest,
        "cache_status": "normal_phase8_completed",
    }

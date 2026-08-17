"""Atomic Phase 9F-D Application Session confirmation persistence."""

from __future__ import annotations

import json
import sqlite3
import uuid
from copy import deepcopy
from datetime import datetime
from typing import Any

from database import db_manager
from database.analysis_cache_manager import (
    insert_analysis_snapshot_with_connection,
)
from database.application_blueprint_manager import (
    init_application_blueprint_decisions,
    persist_exact_phase9f_d_binding_with_connection,
)
from database.global_blueprint_manager import (
    active_global_blueprints_with_connection,
    init_global_blueprint_registry,
)
from database.global_master_resume_manager import (
    current_global_master_resume_with_connection,
    global_master_resume_artifact_with_connection,
    init_global_master_resume_registry,
)
from database.jd_library_manager import (
    init_jd_library,
    link_exact_job_description_with_connection,
)
from tailoring.phase9e_blueprint_selection import (
    canonical_json,
    fingerprint_value,
)
from tailoring.phase9f_application_confirmation import (
    PHASE9F_D_EVENT_VERSION,
    PHASE9F_D_IDENTITY_POLICY_VERSION,
    PHASE9F_D_VERSION,
    Phase9FDConfirmationError,
    build_application_baseline_report,
    build_confirmation_operation_key,
    build_exact_phase9e_decision,
    prepare_phase9f_d_confirmation,
    zero_cost_diagnostics,
)
from tailoring.phase9f_starting_source_ranking import (
    prepare_ranking_context,
)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    connection = db_manager._connect()
    connection.row_factory = sqlite3.Row
    return connection


def _safe_json(value: Any) -> dict[str, Any]:
    try:
        parsed = json.loads(str(value or "{}"))
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def init_phase9f_application_confirmation_schema() -> None:
    """Create the additive Phase 9F-D schema idempotently."""
    db_manager.init_db()
    init_jd_library()
    from database.analysis_cache_manager import init_analysis_cache

    init_analysis_cache()
    init_global_master_resume_registry()
    init_global_blueprint_registry()
    init_application_blueprint_decisions()
    connection = _connect()
    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS phase9f_application_confirmations (
                confirmation_id TEXT PRIMARY KEY,
                confirmation_fingerprint TEXT NOT NULL UNIQUE,
                application_id INTEGER NOT NULL UNIQUE,
                phase9f_d_version TEXT NOT NULL,
                identity_policy_version TEXT NOT NULL,
                confirmation_content_fingerprint TEXT NOT NULL,
                application_intent_id TEXT NOT NULL,
                confirmation_operation_key TEXT NOT NULL UNIQUE,
                phase9f_a_snapshot_fingerprint TEXT NOT NULL,
                canonical_jd_id TEXT NOT NULL,
                library_jd_id INTEGER NOT NULL,
                source_version_id TEXT NOT NULL,
                raw_jd_sha256 TEXT NOT NULL,
                canonical_requirement_fingerprint TEXT NOT NULL,
                ranking_input_fingerprint TEXT NOT NULL,
                ranking_fingerprint TEXT NOT NULL,
                recommended_source_fingerprint TEXT NOT NULL,
                confirmed_source_fingerprint TEXT NOT NULL,
                selected_candidate_analysis_fingerprint TEXT NOT NULL,
                phase9f_c_recommendation_fingerprint TEXT NOT NULL,
                recommended_intensity TEXT NOT NULL,
                confirmed_intensity TEXT NOT NULL,
                override_classification TEXT NOT NULL,
                phase9e_decision_id TEXT NOT NULL,
                phase9e_decision_fingerprint TEXT NOT NULL,
                starting_snapshot_fingerprint TEXT NOT NULL,
                semantic_identity_json TEXT NOT NULL,
                confirmation_snapshot_json TEXT NOT NULL,
                actor_label TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_phase9f_d_content_history
            ON phase9f_application_confirmations (
                confirmation_content_fingerprint,
                created_at DESC,
                confirmation_id DESC
            );

            CREATE TABLE IF NOT EXISTS phase9f_application_confirmation_events (
                event_id TEXT PRIMARY KEY,
                event_fingerprint TEXT NOT NULL UNIQUE,
                event_version TEXT NOT NULL,
                event_type TEXT NOT NULL,
                confirmation_id TEXT NOT NULL,
                application_id INTEGER NOT NULL,
                confirmation_operation_key TEXT NOT NULL,
                actor_label TEXT NOT NULL,
                created_at TEXT NOT NULL,
                event_json TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_phase9f_d_event_history
            ON phase9f_application_confirmation_events (
                application_id,
                created_at DESC,
                event_id DESC
            );
            """
        )
        connection.commit()
    finally:
        connection.close()


def _row_to_confirmation(row: sqlite3.Row) -> dict[str, Any]:
    snapshot = _safe_json(row["confirmation_snapshot_json"])
    return {
        "confirmation_id": str(row["confirmation_id"]),
        "confirmation_fingerprint": str(row["confirmation_fingerprint"]),
        "application_id": int(row["application_id"]),
        "phase9f_d_version": str(row["phase9f_d_version"]),
        "identity_policy_version": str(row["identity_policy_version"]),
        "confirmation_content_fingerprint": str(
            row["confirmation_content_fingerprint"]
        ),
        "application_intent_id": str(row["application_intent_id"]),
        "confirmation_operation_key": str(
            row["confirmation_operation_key"]
        ),
        "recommended_intensity": str(row["recommended_intensity"]),
        "confirmed_intensity": str(row["confirmed_intensity"]),
        "override_classification": str(row["override_classification"]),
        "phase9e_decision_id": str(row["phase9e_decision_id"]),
        "phase9e_decision_fingerprint": str(
            row["phase9e_decision_fingerprint"]
        ),
        "starting_snapshot_fingerprint": str(
            row["starting_snapshot_fingerprint"]
        ),
        "semantic_identity": _safe_json(row["semantic_identity_json"]),
        "confirmation_snapshot": snapshot,
        "actor_label": str(row["actor_label"]),
        "created_at": str(row["created_at"]),
    }


def get_phase9f_application_confirmation(
    application_id: int,
) -> dict[str, Any] | None:
    connection = _connect()
    try:
        table_exists = connection.execute(
            """
            SELECT 1 FROM sqlite_master
            WHERE type = 'table'
              AND name = 'phase9f_application_confirmations'
            LIMIT 1
            """
        ).fetchone()
        if table_exists is None:
            return None
        row = connection.execute(
            """
            SELECT * FROM phase9f_application_confirmations
            WHERE application_id = ?
            LIMIT 1
            """,
            (int(application_id),),
        ).fetchone()
        return _row_to_confirmation(row) if row is not None else None
    finally:
        connection.close()


def _current_source_scope_with_connection(
    connection: sqlite3.Connection,
    *,
    exact_jd: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, Any] | None, list[dict[str, Any]]]:
    base = current_global_master_resume_with_connection(connection)
    artifact = None
    if base is not None:
        artifact = global_master_resume_artifact_with_connection(
            connection,
            master_version_id=base["master_version_id"],
            artifact_kind="original",
        )
    blueprints = active_global_blueprints_with_connection(connection)
    context = prepare_ranking_context(
        exact_jd=deepcopy(exact_jd),
        current_base_resume=deepcopy(base),
        current_base_artifact=deepcopy(artifact),
        global_blueprints=deepcopy(blueprints),
    )
    return context, base, artifact, blueprints


def _authoritative_selected_source(
    prepared: dict[str, Any],
    *,
    context: dict[str, Any],
    base: dict[str, Any] | None,
    blueprints: list[dict[str, Any]],
) -> dict[str, Any]:
    selected = prepared["selected_candidate"]
    normalized_fingerprint = str(
        selected.get("normalized_source_fingerprint") or ""
    )
    current = [
        row
        for row in context.get("_normalized_sources", [])
        if str(row.get("normalized_source_fingerprint") or "")
        == normalized_fingerprint
    ]
    if len(current) != 1 or current[0].get("semantic_identity") != (
        selected.get("candidate_analysis_snapshot") or {}
    ).get("source_identity"):
        raise Phase9FDConfirmationError(
            "The confirmed source is no longer the exact eligible Phase 9F-B source.",
            code="confirmed_source_stale",
        )
    source_type = str(selected.get("source_type") or "")
    source_id = str(selected.get("source_id") or "")
    if source_type == "base_resume":
        if base is None or str(base.get("master_version_id") or "") != source_id:
            raise Phase9FDConfirmationError(
                "The selected Base Resume is no longer current.",
                code="selected_base_resume_stale",
            )
        return base
    matches = [
        row
        for row in blueprints
        if str(row.get("blueprint_id") or "") == source_id
        and str(row.get("status") or "") == "active"
        and str(row.get("availability_status") or "available") == "available"
    ]
    if len(matches) != 1:
        raise Phase9FDConfirmationError(
            "The selected Global Blueprint is no longer active and available.",
            code="selected_blueprint_stale",
        )
    return matches[0]


def _insert_confirmation_event(
    connection: sqlite3.Connection,
    *,
    confirmation_id: str,
    application_id: int,
    operation_key: str,
    actor_label: str,
    created_at: str,
) -> dict[str, Any]:
    event = {
        "event_version": PHASE9F_D_EVENT_VERSION,
        "event_id": uuid.uuid4().hex,
        "event_type": "application_session_confirmed",
        "confirmation_id": confirmation_id,
        "application_id": int(application_id),
        "confirmation_operation_key": operation_key,
        "actor_label": str(actor_label or "Local user"),
        "created_at": str(created_at),
        "tailoring_execution_started": False,
    }
    event["event_fingerprint"] = fingerprint_value(event)
    connection.execute(
        """
        INSERT INTO phase9f_application_confirmation_events (
            event_id, event_fingerprint, event_version, event_type,
            confirmation_id, application_id, confirmation_operation_key,
            actor_label, created_at, event_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event["event_id"],
            event["event_fingerprint"],
            event["event_version"],
            event["event_type"],
            confirmation_id,
            int(application_id),
            operation_key,
            event["actor_label"],
            str(created_at),
            canonical_json(event),
        ),
    )
    return event


def confirm_phase9f_application_session(
    *,
    phase9f_a_snapshot: dict[str, Any],
    persisted_exact_jd_snapshot: dict[str, Any],
    ranking_result: dict[str, Any],
    phase9f_c_recommendation: dict[str, Any],
    confirmed_normalized_source_fingerprint: str,
    confirmed_intensity: str,
    application_intent_id: str,
    actor_label: str = "Local user",
) -> dict[str, Any]:
    """Atomically create and exactly configure one existing Application Session."""
    prepared = prepare_phase9f_d_confirmation(
        phase9f_a_snapshot=phase9f_a_snapshot,
        persisted_exact_jd_snapshot=persisted_exact_jd_snapshot,
        ranking_result=ranking_result,
        phase9f_c_recommendation=phase9f_c_recommendation,
        confirmed_normalized_source_fingerprint=(
            confirmed_normalized_source_fingerprint
        ),
        confirmed_intensity=confirmed_intensity,
    )
    operation_key = build_confirmation_operation_key(
        confirmation_content_fingerprint=prepared[
            "confirmation_content_fingerprint"
        ],
        application_intent_id=application_intent_id,
    )
    baseline = build_application_baseline_report(prepared)
    init_phase9f_application_confirmation_schema()
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            """
            SELECT * FROM phase9f_application_confirmations
            WHERE confirmation_operation_key = ?
            LIMIT 1
            """,
            (operation_key,),
        ).fetchone()
        if existing is not None:
            connection.rollback()
            return {
                "cache_status": "exact_operation_reused",
                "confirmation": _row_to_confirmation(existing),
                "zero_cost_diagnostics": zero_cost_diagnostics(),
            }

        context, base, _artifact, blueprints = (
            _current_source_scope_with_connection(
                connection,
                exact_jd=phase9f_a_snapshot,
            )
        )
        if context.get("status") != "ready" or str(
            context.get("ranking_input_fingerprint") or ""
        ) != str(ranking_result.get("ranking_input_fingerprint") or ""):
            raise Phase9FDConfirmationError(
                "The Phase 9F-B source scope changed before confirmation.",
                code="phase9f_b_scope_stale",
            )
        authoritative_source = _authoritative_selected_source(
            prepared,
            context=context,
            base=base,
            blueprints=blueprints,
        )

        now = _now()
        confirmation_id = fingerprint_value(
            {
                "phase9f_d_version": PHASE9F_D_VERSION,
                "confirmation_operation_key": operation_key,
            }
        )[:32]
        selected = prepared["selected_candidate"]
        resume_filename = str(
            authoritative_source.get("original_filename")
            or authoritative_source.get("display_name")
            or selected.get("source_display_name")
            or "Immutable starting source"
        )
        application_id = db_manager.insert_application_session_with_connection(
            connection,
            resume_filename=resume_filename,
            report=baseline,
            created_at=now,
        )
        linked_exact_jd = deepcopy(persisted_exact_jd_snapshot)
        linked_exact_jd["source_application_link"] = {
            "application_id": application_id,
            "job_description_id": int(
                persisted_exact_jd_snapshot.get("library_jd_id") or 0
            ),
            "source_version_id": str(
                persisted_exact_jd_snapshot.get("source_version_id") or ""
            ),
            "linked_at": now,
            "updated_at": now,
        }
        link_exact_job_description_with_connection(
            connection,
            application_id=application_id,
            persisted_exact_jd=persisted_exact_jd_snapshot,
            linked_at=now,
        )
        phase9e_decision = build_exact_phase9e_decision(
            application_id=application_id,
            linked_exact_jd=linked_exact_jd,
            prepared=prepared,
            authoritative_source=authoritative_source,
        )
        analysis_id = fingerprint_value(
            {
                "confirmation_operation_key": operation_key,
                "candidate_analysis_snapshot_fingerprint": selected[
                    "candidate_analysis_snapshot_fingerprint"
                ],
            }
        )[:32]
        baseline.setdefault("meta", {})["created_at"] = now
        baseline["meta"]["analysis_cache"] = {
            "analysis_id": analysis_id,
            "input_fingerprint": selected[
                "candidate_analysis_snapshot_fingerprint"
            ],
        }
        baseline["meta"]["phase9f_d_confirmation"] = {
            "confirmation_id": confirmation_id,
            "confirmation_content_fingerprint": prepared[
                "confirmation_content_fingerprint"
            ],
            "confirmation_operation_key": operation_key,
            "phase9e_decision_id": phase9e_decision["decision_id"],
            "phase9e_decision_fingerprint": phase9e_decision[
                "decision_fingerprint"
            ],
            "confirmed_intensity": prepared["confirmed_intensity"],
            "execution_status": "not_started",
        }
        connection.execute(
            """
            UPDATE applications
            SET report_json = ?, overall_score = ?, summary = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                json.dumps(baseline, ensure_ascii=False, default=str),
                int(baseline.get("overall_score") or 0),
                str(baseline.get("summary") or ""),
                now,
                application_id,
            ),
        )
        insert_analysis_snapshot_with_connection(
            connection,
            application_id=application_id,
            input_fingerprint=selected[
                "candidate_analysis_snapshot_fingerprint"
            ],
            report=baseline,
            analysis_model="deterministic-phase9f-b-baseline",
            resume_filename=resume_filename,
            analysis_id=analysis_id,
            created_at=now,
        )
        phase9e_event = persist_exact_phase9f_d_binding_with_connection(
            connection,
            decision=phase9e_decision,
            actor_label=actor_label,
            created_at=now,
        )

        semantic_identity = {
            "format_version": PHASE9F_D_VERSION,
            "identity_policy_version": PHASE9F_D_IDENTITY_POLICY_VERSION,
            "application_id": application_id,
            "application_intent_id": str(application_intent_id),
            "confirmation_operation_key": operation_key,
            "confirmation_content_identity": deepcopy(
                prepared["confirmation_content_identity"]
            ),
            "phase9e_exact_binding": {
                "decision_id": phase9e_decision["decision_id"],
                "decision_fingerprint": phase9e_decision[
                    "decision_fingerprint"
                ],
                "starting_snapshot_fingerprint": phase9e_decision[
                    "starting_snapshot"
                ]["starting_snapshot_fingerprint"],
            },
        }
        confirmation_fingerprint = fingerprint_value(semantic_identity)
        confirmation_snapshot = {
            "semantic_identity": semantic_identity,
            "phase9f_a_snapshot": deepcopy(phase9f_a_snapshot),
            "persisted_exact_jd_snapshot": deepcopy(
                persisted_exact_jd_snapshot
            ),
            "phase9f_b_ranking_result": deepcopy(ranking_result),
            "selected_candidate": deepcopy(selected),
            "phase9f_c_recommendation": deepcopy(
                prepared["phase9f_c_recommendation"]
            ),
            "phase9e_exact_decision": deepcopy(phase9e_decision),
            "initial_analysis": {
                "analysis_id": analysis_id,
                "candidate_analysis_snapshot_fingerprint": selected[
                    "candidate_analysis_snapshot_fingerprint"
                ],
                "baseline_adapter_version": baseline["meta"][
                    "phase9f_d_baseline"
                ]["adapter_version"],
            },
            "execution_status": "not_started",
            "zero_cost_diagnostics": zero_cost_diagnostics(),
        }
        persisted_jd = prepared["persisted_exact_jd"]
        connection.execute(
            """
            INSERT INTO phase9f_application_confirmations (
                confirmation_id, confirmation_fingerprint, application_id,
                phase9f_d_version, identity_policy_version,
                confirmation_content_fingerprint, application_intent_id,
                confirmation_operation_key, phase9f_a_snapshot_fingerprint,
                canonical_jd_id, library_jd_id, source_version_id,
                raw_jd_sha256, canonical_requirement_fingerprint,
                ranking_input_fingerprint, ranking_fingerprint,
                recommended_source_fingerprint, confirmed_source_fingerprint,
                selected_candidate_analysis_fingerprint,
                phase9f_c_recommendation_fingerprint,
                recommended_intensity, confirmed_intensity,
                override_classification, phase9e_decision_id,
                phase9e_decision_fingerprint, starting_snapshot_fingerprint,
                semantic_identity_json, confirmation_snapshot_json,
                actor_label, created_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                confirmation_id,
                confirmation_fingerprint,
                application_id,
                PHASE9F_D_VERSION,
                PHASE9F_D_IDENTITY_POLICY_VERSION,
                prepared["confirmation_content_fingerprint"],
                str(application_intent_id),
                operation_key,
                str(phase9f_a_snapshot.get("snapshot_fingerprint") or ""),
                str(persisted_exact_jd_snapshot.get("canonical_jd_id") or ""),
                int(persisted_exact_jd_snapshot.get("library_jd_id") or 0),
                str(persisted_exact_jd_snapshot.get("source_version_id") or ""),
                persisted_jd["semantic_identity"]["raw_jd_sha256"],
                persisted_jd["semantic_identity"][
                    "canonical_requirement_fingerprint"
                ],
                ranking_result["ranking_input_fingerprint"],
                prepared["validated_ranking"]["ranking_fingerprint"],
                prepared["recommended_source"][
                    "normalized_source_fingerprint"
                ],
                prepared["confirmed_source"][
                    "normalized_source_fingerprint"
                ],
                selected["candidate_analysis_snapshot_fingerprint"],
                prepared["phase9f_c_recommendation"][
                    "recommendation_fingerprint"
                ],
                prepared["recommended_intensity_for_recommended_source"],
                prepared["confirmed_intensity"],
                prepared["override_classification"],
                phase9e_decision["decision_id"],
                phase9e_decision["decision_fingerprint"],
                phase9e_decision["starting_snapshot"][
                    "starting_snapshot_fingerprint"
                ],
                canonical_json(semantic_identity),
                canonical_json(confirmation_snapshot),
                str(actor_label or "Local user"),
                now,
            ),
        )
        confirmation_event = _insert_confirmation_event(
            connection,
            confirmation_id=confirmation_id,
            application_id=application_id,
            operation_key=operation_key,
            actor_label=actor_label,
            created_at=now,
        )
        connection.commit()
        row = connection.execute(
            """
            SELECT * FROM phase9f_application_confirmations
            WHERE confirmation_id = ?
            """,
            (confirmation_id,),
        ).fetchone()
        if row is None:
            raise RuntimeError("The committed Phase 9F-D row could not be reloaded.")
        return {
            "cache_status": "created",
            "confirmation": _row_to_confirmation(row),
            "phase9e_decision": phase9e_decision,
            "phase9e_binding_event": phase9e_event,
            "confirmation_event": confirmation_event,
            "zero_cost_diagnostics": zero_cost_diagnostics(),
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def delete_phase9f_application_confirmation(application_id: int) -> None:
    """Delete Phase 9F-D rows only as part of explicit session deletion."""
    init_phase9f_application_confirmation_schema()
    connection = _connect()
    try:
        connection.execute(
            "DELETE FROM phase9f_application_confirmation_events WHERE application_id = ?",
            (int(application_id),),
        )
        connection.execute(
            "DELETE FROM phase9f_application_confirmations WHERE application_id = ?",
            (int(application_id),),
        )
        connection.commit()
    finally:
        connection.close()

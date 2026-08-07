"""Persistence for immutable Phase 9E application-blueprint decisions."""

from __future__ import annotations

import json
import sqlite3
import uuid
from copy import deepcopy
from datetime import datetime
from typing import Any

from database import db_manager as base_manager
from database.global_blueprint_manager import (
    init_global_blueprint_registry,
    list_global_blueprints,
)
from database.jd_library_manager import (
    get_exact_job_description_for_application,
)
from tailoring.phase9e_blueprint_selection import (
    PHASE9E_BINDING_EVENT_VERSION,
    PHASE9E_DECISION_POLICY_VERSION,
    PHASE9E_IDENTITY_POLICY_VERSION,
    PHASE9E_RECOMMENDATION_POLICY_VERSION,
    PHASE9E_VERSION,
    PHASE9E_WORKFLOW_ACTION_POLICY_VERSION,
    Phase9EDecisionError,
    build_effective_tailoring_report,
    build_phase9e_decision,
    canonical_json,
    fingerprint_value,
    generation_binding_identity,
    materialise_phase9e_starting_sections,
    resolve_workflow_action,
    verify_decision_integrity,
)


PHASE9E_LEGACY_COMPATIBILITY_VERSION = (
    "phase9e-legacy-session-compatibility-v1"
)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    connection = base_manager._connect()
    connection.row_factory = sqlite3.Row
    return connection


def _safe_json(value: Any) -> dict[str, Any]:
    try:
        parsed = json.loads(str(value or "{}"))
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def init_application_blueprint_decisions() -> None:
    connection = _connect()
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS application_blueprint_decisions (
                decision_id TEXT PRIMARY KEY,
                decision_fingerprint TEXT NOT NULL UNIQUE,
                application_id INTEGER NOT NULL,
                phase9e_version TEXT NOT NULL,
                identity_policy_version TEXT NOT NULL,
                recommendation_policy_version TEXT NOT NULL,
                decision_policy_version TEXT NOT NULL,
                selected_source TEXT NOT NULL,
                selection_mode TEXT NOT NULL,
                selected_blueprint_id TEXT,
                selected_blueprint_fingerprint TEXT,
                selected_blueprint_version INTEGER,
                classified_role_family_id TEXT NOT NULL,
                classified_role_family_label TEXT NOT NULL,
                canonical_jd_id TEXT NOT NULL,
                source_version_id TEXT NOT NULL,
                raw_jd_sha256 TEXT NOT NULL,
                stable_input_fingerprint TEXT NOT NULL,
                scoring_version TEXT NOT NULL,
                taxonomy_version TEXT NOT NULL,
                recommended_tailoring TEXT NOT NULL,
                starting_snapshot_fingerprint TEXT NOT NULL,
                semantic_identity_json TEXT NOT NULL,
                starting_snapshot_json TEXT NOT NULL,
                decision_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_phase9e_application_history
            ON application_blueprint_decisions (
                application_id,
                created_at DESC,
                decision_id DESC
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS application_blueprint_binding_state (
                application_id INTEGER PRIMARY KEY,
                current_decision_id TEXT NOT NULL,
                current_decision_fingerprint TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS application_blueprint_binding_events (
                event_id TEXT PRIMARY KEY,
                event_fingerprint TEXT NOT NULL UNIQUE,
                event_version TEXT NOT NULL,
                event_type TEXT NOT NULL,
                application_id INTEGER NOT NULL,
                decision_id TEXT NOT NULL,
                decision_fingerprint TEXT NOT NULL,
                previous_decision_id TEXT,
                actor_label TEXT NOT NULL,
                created_at TEXT NOT NULL,
                event_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_phase9e_binding_events
            ON application_blueprint_binding_events (
                application_id,
                created_at DESC,
                event_id DESC
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS application_blueprint_workflow_state (
                application_id INTEGER NOT NULL,
                decision_id TEXT NOT NULL,
                workflow_action TEXT NOT NULL,
                workflow_action_fingerprint TEXT NOT NULL,
                action_event_id TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (application_id, decision_id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS application_blueprint_scope_activation_state (
                application_id INTEGER PRIMARY KEY,
                active_decision_id TEXT NOT NULL,
                active_decision_fingerprint TEXT NOT NULL,
                confirmation_event_id TEXT NOT NULL,
                compatibility_policy_version TEXT NOT NULL,
                activated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS application_blueprint_legacy_sessions (
                application_id INTEGER PRIMARY KEY,
                compatibility_policy_version TEXT NOT NULL,
                marked_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS application_blueprint_compatibility_migrations (
                compatibility_policy_version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
            """
        )
        migration = connection.execute(
            """
            SELECT compatibility_policy_version
            FROM application_blueprint_compatibility_migrations
            WHERE compatibility_policy_version = ?
            LIMIT 1
            """,
            (PHASE9E_LEGACY_COMPATIBILITY_VERSION,),
        ).fetchone()
        if migration is None:
            applications_table = connection.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type = 'table' AND name = 'applications'
                LIMIT 1
                """
            ).fetchone()
            marked_at = _now()
            if applications_table is not None:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO application_blueprint_legacy_sessions (
                        application_id,
                        compatibility_policy_version,
                        marked_at
                    )
                    SELECT id, ?, ? FROM applications
                    """,
                    (PHASE9E_LEGACY_COMPATIBILITY_VERSION, marked_at),
                )
            connection.execute(
                """
                INSERT INTO application_blueprint_compatibility_migrations (
                    compatibility_policy_version,
                    applied_at
                ) VALUES (?, ?)
                """,
                (PHASE9E_LEGACY_COMPATIBILITY_VERSION, marked_at),
            )
        connection.commit()
    finally:
        connection.close()


def _application_report(application_id: int) -> dict[str, Any]:
    application = base_manager.get_application_by_id(int(application_id))
    if not isinstance(application, dict):
        raise Phase9EDecisionError("The application session does not exist.")
    report = application.get("report")
    if not isinstance(report, dict) or not report:
        raise Phase9EDecisionError(
            "Analyze and persist the application before selecting a blueprint."
        )
    return deepcopy(report)


def _active_blueprints() -> list[dict[str, Any]]:
    return list_global_blueprints(include_superseded=False)


def preview_application_blueprint_decision(
    *,
    application_id: int,
    selected_source: str,
    selected_blueprint_id: str = "",
    selection_mode: str = "recommended",
    mismatch_acknowledged: bool = False,
) -> dict[str, Any]:
    report = _application_report(application_id)
    exact_jd = get_exact_job_description_for_application(application_id)
    if exact_jd is None:
        raise Phase9EDecisionError(
            "The application has no exact persisted JD version link."
        )
    return build_phase9e_decision(
        application_id=application_id,
        application_report=report,
        exact_jd=exact_jd,
        active_blueprints=_active_blueprints(),
        selected_source=selected_source,
        selected_blueprint_id=selected_blueprint_id,
        selection_mode=selection_mode,
        mismatch_acknowledged=mismatch_acknowledged,
    )


def _database_context_signature(
    connection: sqlite3.Connection,
    application_id: int,
) -> str:
    application = connection.execute(
        "SELECT report_json FROM applications WHERE id = ?",
        (int(application_id),),
    ).fetchone()
    if application is None or not str(application["report_json"] or "").strip():
        raise Phase9EDecisionError("The persisted application report is missing.")
    jd = connection.execute(
        """
        SELECT
            link.job_description_id,
            link.source_version_id,
            version.raw_text,
            version.jd_profile_json,
            job.canonical_jd_id
        FROM application_job_links AS link
        JOIN job_descriptions AS job
          ON job.id = link.job_description_id
        JOIN job_description_versions AS version
          ON version.job_description_id = link.job_description_id
         AND version.source_version_id = link.source_version_id
        WHERE link.application_id = ?
        LIMIT 1
        """,
        (int(application_id),),
    ).fetchone()
    if jd is None:
        raise Phase9EDecisionError(
            "The application's exact linked JD version is missing."
        )
    active = connection.execute(
        """
        SELECT
            blueprint_id,
            blueprint_fingerprint,
            version_number,
            role_family_id,
            blueprint_snapshot_json
        FROM global_blueprint_versions
        WHERE status = 'active'
        ORDER BY role_family_id, blueprint_id
        """
    ).fetchall()
    return fingerprint_value(
        {
            "application_id": int(application_id),
            "report_json": str(application["report_json"]),
            "exact_jd": dict(jd),
            "active_blueprints": [dict(row) for row in active],
        }
    )


def _row_to_decision(row: sqlite3.Row) -> dict[str, Any]:
    decision = _safe_json(row["decision_json"])
    decision.setdefault("decision_id", str(row["decision_id"]))
    decision.setdefault(
        "decision_fingerprint", str(row["decision_fingerprint"])
    )
    decision["created_at"] = str(row["created_at"])
    return decision


def _get_decision_with_connection(
    connection: sqlite3.Connection,
    decision_id: str,
) -> dict[str, Any] | None:
    row = connection.execute(
        """
        SELECT * FROM application_blueprint_decisions
        WHERE decision_id = ? LIMIT 1
        """,
        (str(decision_id),),
    ).fetchone()
    return _row_to_decision(row) if row is not None else None


def _insert_binding_event(
    connection: sqlite3.Connection,
    *,
    event_type: str,
    application_id: int,
    decision: dict[str, Any],
    previous_decision_id: str,
    actor_label: str,
    created_at: str,
    event_details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event_id = uuid.uuid4().hex
    event = {
        "event_version": PHASE9E_BINDING_EVENT_VERSION,
        "event_id": event_id,
        "event_type": event_type,
        "application_id": int(application_id),
        "decision_id": decision["decision_id"],
        "decision_fingerprint": decision["decision_fingerprint"],
        "previous_decision_id": str(previous_decision_id or ""),
        "actor_label": str(actor_label or "Local user"),
        "created_at": created_at,
        "event_details": deepcopy(event_details or {}),
    }
    event["event_fingerprint"] = fingerprint_value(event)
    connection.execute(
        """
        INSERT INTO application_blueprint_binding_events (
            event_id,
            event_fingerprint,
            event_version,
            event_type,
            application_id,
            decision_id,
            decision_fingerprint,
            previous_decision_id,
            actor_label,
            created_at,
            event_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            event["event_fingerprint"],
            PHASE9E_BINDING_EVENT_VERSION,
            event_type,
            int(application_id),
            decision["decision_id"],
            decision["decision_fingerprint"],
            str(previous_decision_id or ""),
            str(actor_label or "Local user"),
            created_at,
            canonical_json(event),
        ),
    )
    return event


def _workflow_action_with_connection(
    connection: sqlite3.Connection,
    *,
    application_id: int,
    decision_id: str,
) -> dict[str, Any] | None:
    row = connection.execute(
        """
        SELECT * FROM application_blueprint_workflow_state
        WHERE application_id = ? AND decision_id = ?
        LIMIT 1
        """,
        (int(application_id), str(decision_id)),
    ).fetchone()
    return dict(row) if row is not None else None


def _scope_activation_with_connection(
    connection: sqlite3.Connection,
    *,
    application_id: int,
) -> dict[str, Any] | None:
    row = connection.execute(
        """
        SELECT * FROM application_blueprint_scope_activation_state
        WHERE application_id = ?
        LIMIT 1
        """,
        (int(application_id),),
    ).fetchone()
    return dict(row) if row is not None else None


def _is_legacy_session_with_connection(
    connection: sqlite3.Connection,
    *,
    application_id: int,
) -> bool:
    row = connection.execute(
        """
        SELECT application_id FROM application_blueprint_legacy_sessions
        WHERE application_id = ? AND compatibility_policy_version = ?
        LIMIT 1
        """,
        (int(application_id), PHASE9E_LEGACY_COMPATIBILITY_VERSION),
    ).fetchone()
    return row is not None


def evaluate_and_bind_application_blueprint(
    *,
    application_id: int,
    scope_replacement_confirmed: bool,
    selected_source: str,
    selected_blueprint_id: str = "",
    selection_mode: str = "recommended",
    mismatch_acknowledged: bool = False,
    actor_label: str = "Local user",
) -> dict[str, Any]:
    """Revalidate, persist/reuse, bind, and audit in one transaction."""
    if scope_replacement_confirmed is not True:
        raise Phase9EDecisionError(
            "Replacing the current application scope requires explicit confirmation."
        )
    init_global_blueprint_registry()
    init_application_blueprint_decisions()
    signature_connection = _connect()
    try:
        before_signature = _database_context_signature(
            signature_connection, application_id
        )
    finally:
        signature_connection.close()
    prepared = preview_application_blueprint_decision(
        application_id=application_id,
        selected_source=selected_source,
        selected_blueprint_id=selected_blueprint_id,
        selection_mode=selection_mode,
        mismatch_acknowledged=mismatch_acknowledged,
    )
    verify_decision_integrity(prepared)

    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        after_signature = _database_context_signature(connection, application_id)
        if before_signature != after_signature:
            raise Phase9EDecisionError(
                "The application, linked JD, or active blueprint changed during binding."
            )

        existing = connection.execute(
            """
            SELECT * FROM application_blueprint_decisions
            WHERE decision_fingerprint = ? LIMIT 1
            """,
            (prepared["decision_fingerprint"],),
        ).fetchone()
        now = _now()
        if existing is None:
            semantic = prepared["semantic_identity"]
            selection = prepared["selection"]
            selected = selection.get("selected_blueprint") or {}
            comparison = prepared["comparison"]
            jd = semantic["current_jd"]
            role = semantic["role_family_classification"]
            connection.execute(
                """
                INSERT INTO application_blueprint_decisions (
                    decision_id,
                    decision_fingerprint,
                    application_id,
                    phase9e_version,
                    identity_policy_version,
                    recommendation_policy_version,
                    decision_policy_version,
                    selected_source,
                    selection_mode,
                    selected_blueprint_id,
                    selected_blueprint_fingerprint,
                    selected_blueprint_version,
                    classified_role_family_id,
                    classified_role_family_label,
                    canonical_jd_id,
                    source_version_id,
                    raw_jd_sha256,
                    stable_input_fingerprint,
                    scoring_version,
                    taxonomy_version,
                    recommended_tailoring,
                    starting_snapshot_fingerprint,
                    semantic_identity_json,
                    starting_snapshot_json,
                    decision_json,
                    created_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    prepared["decision_id"],
                    prepared["decision_fingerprint"],
                    int(application_id),
                    PHASE9E_VERSION,
                    PHASE9E_IDENTITY_POLICY_VERSION,
                    PHASE9E_RECOMMENDATION_POLICY_VERSION,
                    PHASE9E_DECISION_POLICY_VERSION,
                    selection["selected_source"],
                    selection["selection_mode"],
                    str(selected.get("blueprint_id") or "") or None,
                    str(selected.get("blueprint_fingerprint") or "") or None,
                    int(selected.get("version_number", 0) or 0) or None,
                    role["role_family_id"],
                    role["role_family_label"],
                    jd["canonical_jd_id"],
                    jd["source_version_id"],
                    jd["raw_jd_sha256"],
                    jd["stable_input_fingerprint"],
                    comparison["scoring_version"],
                    comparison["capability_taxonomy_version"],
                    prepared["recommended_tailoring"],
                    prepared["starting_snapshot"][
                        "starting_snapshot_fingerprint"
                    ],
                    canonical_json(prepared["semantic_identity"]),
                    canonical_json(prepared["starting_snapshot"]),
                    canonical_json(prepared),
                    now,
                ),
            )
            decision = deepcopy(prepared)
            decision["created_at"] = now
            cache_status = "miss"
        else:
            decision = _row_to_decision(existing)
            verify_decision_integrity(decision)
            cache_status = "hit"

        current = connection.execute(
            """
            SELECT current_decision_id
            FROM application_blueprint_binding_state
            WHERE application_id = ?
            """,
            (int(application_id),),
        ).fetchone()
        previous_id = str(current["current_decision_id"] or "") if current else ""
        if previous_id == decision["decision_id"]:
            event_type = "decision_reused"
            cache_status = "hit_current"
        else:
            event_type = "decision_bound" if not previous_id else "decision_replaced"
            if cache_status == "hit":
                cache_status = "hit_rebound"

        connection.execute(
            """
            INSERT INTO application_blueprint_binding_state (
                application_id,
                current_decision_id,
                current_decision_fingerprint,
                updated_at
            ) VALUES (?, ?, ?, ?)
            ON CONFLICT(application_id) DO UPDATE SET
                current_decision_id = excluded.current_decision_id,
                current_decision_fingerprint = excluded.current_decision_fingerprint,
                updated_at = excluded.updated_at
            """,
            (
                int(application_id),
                decision["decision_id"],
                decision["decision_fingerprint"],
                now,
            ),
        )
        event = _insert_binding_event(
            connection,
            event_type=event_type,
            application_id=application_id,
            decision=decision,
            previous_decision_id=previous_id,
            actor_label=actor_label,
            created_at=now,
            event_details={
                "compatibility_policy_version": (
                    PHASE9E_LEGACY_COMPATIBILITY_VERSION
                ),
                "scope_replacement_confirmed": True,
                "prior_approved_generation_disposition": (
                    "historical_and_inspectable"
                ),
            },
        )
        connection.execute(
            """
            INSERT INTO application_blueprint_scope_activation_state (
                application_id,
                active_decision_id,
                active_decision_fingerprint,
                confirmation_event_id,
                compatibility_policy_version,
                activated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(application_id) DO UPDATE SET
                active_decision_id = excluded.active_decision_id,
                active_decision_fingerprint = excluded.active_decision_fingerprint,
                confirmation_event_id = excluded.confirmation_event_id,
                compatibility_policy_version = excluded.compatibility_policy_version,
                activated_at = excluded.activated_at
            """,
            (
                int(application_id),
                decision["decision_id"],
                decision["decision_fingerprint"],
                event["event_id"],
                PHASE9E_LEGACY_COMPATIBILITY_VERSION,
                now,
            ),
        )
        connection.commit()
        return {
            "cache_status": cache_status,
            "decision": decision,
            "audit_event": event,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def set_application_blueprint_workflow_action(
    *,
    application_id: int,
    workflow_action: str,
    acknowledgement: bool = False,
    reason: str = "",
    actor_label: str = "Local user",
) -> dict[str, Any]:
    """Persist one audited workflow action for the current immutable decision."""
    init_application_blueprint_decisions()
    current = get_current_application_blueprint_decision(application_id)
    if (
        current is None
        or current.get("scope_activation_status") != "active"
        or current.get("current_scope_status") != "current"
    ):
        raise Phase9EDecisionError(
            "An explicitly confirmed, current, reproducible Phase 9E decision is required."
        )
    action = str(workflow_action or "").strip()
    available = list(
        (current.get("workflow_action_policy") or {}).get(
            "available_actions"
        )
        or []
    )
    if action not in available:
        raise Phase9EDecisionError(
            "The requested workflow action is not valid for this decision."
        )
    clean_reason = " ".join(str(reason or "").split()).strip()
    if action == "use_blueprint_unchanged_override":
        if acknowledgement is not True:
            raise Phase9EDecisionError(
                "Using a targeted-retargeting blueprint unchanged requires acknowledgement."
            )
        if len(clean_reason) < 24 or len(clean_reason.split()) < 5:
            raise Phase9EDecisionError(
                "The unchanged-use override requires a substantive audit reason of at least 24 characters and five words."
            )

    action_identity = {
        "policy_version": PHASE9E_WORKFLOW_ACTION_POLICY_VERSION,
        "decision_fingerprint": current["decision_fingerprint"],
        "workflow_action": action,
    }
    action_fingerprint = fingerprint_value(action_identity)
    signature_connection = _connect()
    try:
        before_signature = _database_context_signature(
            signature_connection, application_id
        )
    finally:
        signature_connection.close()

    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        if before_signature != _database_context_signature(
            connection, application_id
        ):
            raise Phase9EDecisionError(
                "The application, linked JD, or active blueprint changed during the workflow action."
            )
        state = connection.execute(
            """
            SELECT current_decision_id, current_decision_fingerprint
            FROM application_blueprint_binding_state
            WHERE application_id = ?
            """,
            (int(application_id),),
        ).fetchone()
        if (
            state is None
            or str(state["current_decision_id"]) != current["decision_id"]
            or str(state["current_decision_fingerprint"])
            != current["decision_fingerprint"]
        ):
            raise Phase9EDecisionError(
                "The current Phase 9E decision changed during the workflow action."
            )
        now = _now()
        previous = _workflow_action_with_connection(
            connection,
            application_id=application_id,
            decision_id=current["decision_id"],
        )
        event = _insert_binding_event(
            connection,
            event_type="workflow_action_selected",
            application_id=application_id,
            decision=current,
            previous_decision_id=current["decision_id"],
            actor_label=actor_label,
            created_at=now,
            event_details={
                "workflow_action_policy_version": (
                    PHASE9E_WORKFLOW_ACTION_POLICY_VERSION
                ),
                "workflow_action": action,
                "workflow_action_fingerprint": action_fingerprint,
                "previous_workflow_action": str(
                    (previous or {}).get("workflow_action") or ""
                ),
                "acknowledgement": bool(acknowledgement),
                "reason": clean_reason,
            },
        )
        connection.execute(
            """
            INSERT INTO application_blueprint_workflow_state (
                application_id,
                decision_id,
                workflow_action,
                workflow_action_fingerprint,
                action_event_id,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(application_id, decision_id) DO UPDATE SET
                workflow_action = excluded.workflow_action,
                workflow_action_fingerprint = excluded.workflow_action_fingerprint,
                action_event_id = excluded.action_event_id,
                updated_at = excluded.updated_at
            """,
            (
                int(application_id),
                current["decision_id"],
                action,
                action_fingerprint,
                event["event_id"],
                now,
            ),
        )
        connection.commit()
        return {
            "decision": current,
            "workflow_action": action,
            "workflow_action_fingerprint": action_fingerprint,
            "audit_event": event,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_application_blueprint_decision(
    decision_id: str,
) -> dict[str, Any] | None:
    init_application_blueprint_decisions()
    connection = _connect()
    try:
        return _get_decision_with_connection(connection, decision_id)
    finally:
        connection.close()


def list_application_blueprint_decisions(
    application_id: int,
) -> list[dict[str, Any]]:
    init_application_blueprint_decisions()
    connection = _connect()
    try:
        pending = connection.execute(
            """
            SELECT current_decision_id
            FROM application_blueprint_binding_state
            WHERE application_id = ?
            """,
            (int(application_id),),
        ).fetchone()
        pending_id = (
            str(pending["current_decision_id"] or "") if pending else ""
        )
        activation = _scope_activation_with_connection(
            connection, application_id=application_id
        )
        active_id = str((activation or {}).get("active_decision_id") or "")
        rows = connection.execute(
            """
            SELECT * FROM application_blueprint_decisions
            WHERE application_id = ?
            ORDER BY created_at DESC, decision_id DESC
            """,
            (int(application_id),),
        ).fetchall()
        decisions = [_row_to_decision(row) for row in rows]
        for decision in decisions:
            if decision["decision_id"] == active_id:
                decision["binding_status"] = "current"
            elif decision["decision_id"] == pending_id:
                decision["binding_status"] = "pending_confirmation"
            else:
                decision["binding_status"] = "historical"
        return decisions
    finally:
        connection.close()


def list_application_blueprint_binding_events(
    application_id: int,
) -> list[dict[str, Any]]:
    init_application_blueprint_decisions()
    connection = _connect()
    try:
        rows = connection.execute(
            """
            SELECT event_json
            FROM application_blueprint_binding_events
            WHERE application_id = ?
            ORDER BY created_at DESC, event_id DESC
            """,
            (int(application_id),),
        ).fetchall()
        return [_safe_json(row["event_json"]) for row in rows]
    finally:
        connection.close()


def _stale_reasons(
    decision: dict[str, Any],
    rebuilt: dict[str, Any] | None,
    error: Exception | None,
) -> list[str]:
    if error is not None:
        return [str(error)]
    if rebuilt is None:
        return ["The current Phase 9E scope could not be reproduced."]
    if rebuilt["decision_fingerprint"] == decision["decision_fingerprint"]:
        return []
    old = decision.get("semantic_identity") or {}
    new = rebuilt.get("semantic_identity") or {}
    reasons: list[str] = []
    for field, label in (
        ("current_jd", "The application's exact JD changed."),
        ("recommendation", "The relevant active blueprint changed."),
        (
            "selection",
            "The selected starting-source content or identity changed.",
        ),
        ("scoring", "The scorer, taxonomy, or score-derived result changed."),
        (
            "source_approval",
            "The immutable exact-source approval identity changed.",
        ),
        ("decision", "The decision policy or section-lock scope changed."),
    ):
        if old.get(field) != new.get(field):
            reasons.append(label)
    return reasons or ["The current semantic scope no longer matches this decision."]


def get_current_application_blueprint_decision(
    application_id: int,
    *,
    validate_current_scope: bool = True,
) -> dict[str, Any] | None:
    init_application_blueprint_decisions()
    connection = _connect()
    try:
        state = connection.execute(
            """
            SELECT current_decision_id
            FROM application_blueprint_binding_state
            WHERE application_id = ?
            """,
            (int(application_id),),
        ).fetchone()
        if state is None:
            return None
        decision = _get_decision_with_connection(
            connection, str(state["current_decision_id"])
        )
        activation = _scope_activation_with_connection(
            connection, application_id=application_id
        )
    finally:
        connection.close()
    if decision is None:
        raise Phase9EDecisionError("The current Phase 9E decision row is missing.")
    verify_decision_integrity(decision)
    activation_matches = bool(
        activation
        and str(activation.get("active_decision_id") or "")
        == decision["decision_id"]
        and str(activation.get("active_decision_fingerprint") or "")
        == decision["decision_fingerprint"]
        and str(activation.get("compatibility_policy_version") or "")
        == PHASE9E_LEGACY_COMPATIBILITY_VERSION
    )
    decision["scope_activation_status"] = (
        "active" if activation_matches else "pending_confirmation"
    )
    decision["scope_activation"] = deepcopy(activation or {})
    if not validate_current_scope:
        decision["current_scope_status"] = "unchecked"
        decision["stale_reasons"] = []
        return decision

    selection = decision.get("selection") or {}
    rebuilt: dict[str, Any] | None = None
    error: Exception | None = None
    try:
        rebuilt = preview_application_blueprint_decision(
            application_id=application_id,
            selected_source=str(selection.get("selected_source") or ""),
            selected_blueprint_id=str(
                (selection.get("selected_blueprint") or {}).get(
                    "blueprint_id"
                )
                or ""
            ),
            selection_mode=str(selection.get("selection_mode") or ""),
            mismatch_acknowledged=bool(
                selection.get("mismatch_acknowledged")
            ),
        )
    except Exception as exc:  # reported as a fail-closed stale reason
        error = exc
    reasons = _stale_reasons(decision, rebuilt, error)
    decision["current_scope_status"] = "stale" if reasons else "current"
    decision["stale_reasons"] = reasons
    return decision


def resolve_current_phase9e_generation_context(
    application_id: int,
) -> dict[str, Any]:
    decision = get_current_application_blueprint_decision(application_id)
    connection = _connect()
    try:
        legacy_session = _is_legacy_session_with_connection(
            connection, application_id=application_id
        )
    finally:
        connection.close()
    if decision is None and legacy_session:
        return {
            "status": "legacy",
            "can_generate": True,
            "phase9e_enforced": False,
            "effective_report": _application_report(application_id),
            "binding_identity": {},
            "section_lock_scope": {
                "education": False,
                "work_experience": False,
                "projects": False,
                "skills": False,
            },
            "reasons": [],
            "legacy_notice": (
                "Phase 9E is optional for this legacy session. Its existing "
                "generation scope remains current until a new starting source "
                "is explicitly confirmed."
            ),
        }
    if decision is None:
        return {
            "status": "unbound",
            "can_generate": False,
            "phase9e_enforced": True,
            "reasons": [
                "Evaluate and explicitly confirm a Phase 9E starting source before generation."
            ],
        }
    if (
        decision.get("scope_activation_status") != "active"
        and legacy_session
    ):
        return {
            "status": "legacy",
            "can_generate": True,
            "phase9e_enforced": False,
            "decision": decision,
            "effective_report": _application_report(application_id),
            "binding_identity": {},
            "section_lock_scope": {
                "education": False,
                "work_experience": False,
                "projects": False,
                "skills": False,
            },
            "reasons": [],
            "legacy_notice": (
                "The saved Phase 9E decision is awaiting explicit scope "
                "replacement confirmation. The legacy generation scope remains current."
            ),
        }
    if decision.get("scope_activation_status") != "active":
        return {
            "status": "awaiting_scope_confirmation",
            "can_generate": False,
            "phase9e_enforced": True,
            "decision": decision,
            "reasons": [
                "Explicit scope replacement confirmation is required before generation."
            ],
        }
    if decision.get("current_scope_status") != "current":
        return {
            "status": "stale",
            "can_generate": False,
            "phase9e_enforced": True,
            "decision": decision,
            "reasons": list(decision.get("stale_reasons") or []),
        }
    connection = _connect()
    try:
        persisted_action = _workflow_action_with_connection(
            connection,
            application_id=application_id,
            decision_id=decision["decision_id"],
        )
    finally:
        connection.close()
    workflow = resolve_workflow_action(decision, persisted_action)
    if not workflow["can_generate"]:
        return {
            "status": workflow["status"],
            "can_generate": False,
            "phase9e_enforced": True,
            "decision": decision,
            "workflow_action": workflow,
            "section_lock_scope": workflow["section_lock_scope"],
            "reasons": list(workflow.get("reasons") or []),
        }
    report = _application_report(application_id)
    effective_report = build_effective_tailoring_report(report, decision)
    effective_report.setdefault("meta", {}).setdefault(
        "phase9e_starting_context", {}
    )["workflow_action"] = workflow["workflow_action"]
    return {
        "status": "current",
        "can_generate": True,
        "phase9e_enforced": True,
        "decision": decision,
        "effective_report": effective_report,
        "binding_identity": generation_binding_identity(decision, workflow),
        "starting_sections": materialise_phase9e_starting_sections(decision),
        "workflow_action": workflow,
        "section_lock_scope": workflow["section_lock_scope"],
        "reasons": [],
    }


def export_application_blueprint_decision(decision_id: str) -> dict[str, Any]:
    decision = get_application_blueprint_decision(decision_id)
    if decision is None:
        raise Phase9EDecisionError("The Phase 9E decision was not found.")
    connection = _connect()
    try:
        workflow_state = _workflow_action_with_connection(
            connection,
            application_id=int(decision["application_id"]),
            decision_id=decision["decision_id"],
        )
        activation_state = _scope_activation_with_connection(
            connection,
            application_id=int(decision["application_id"]),
        )
    finally:
        connection.close()
    return {
        "decision": decision,
        "workflow_action_state": workflow_state,
        "scope_activation_state": activation_state,
        "binding_events": list_application_blueprint_binding_events(
            int(decision["application_id"])
        ),
    }


def delete_application_blueprint_decisions(application_id: int) -> None:
    """Delete Phase 9E rows only when their parent application is deleted."""
    init_application_blueprint_decisions()
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "DELETE FROM application_blueprint_scope_activation_state WHERE application_id = ?",
            (int(application_id),),
        )
        connection.execute(
            "DELETE FROM application_blueprint_legacy_sessions WHERE application_id = ?",
            (int(application_id),),
        )
        connection.execute(
            "DELETE FROM application_blueprint_workflow_state WHERE application_id = ?",
            (int(application_id),),
        )
        connection.execute(
            "DELETE FROM application_blueprint_binding_events WHERE application_id = ?",
            (int(application_id),),
        )
        connection.execute(
            "DELETE FROM application_blueprint_binding_state WHERE application_id = ?",
            (int(application_id),),
        )
        connection.execute(
            "DELETE FROM application_blueprint_decisions WHERE application_id = ?",
            (int(application_id),),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

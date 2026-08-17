"""Transactional persistence for Phase 9D global blueprints."""

from __future__ import annotations

import json
import sqlite3
import uuid
from copy import deepcopy
from datetime import datetime
from typing import Any

from database import tailoring_version_manager as base_manager
from tailoring.phase9d_global_blueprint import (
    PHASE9D_AUDIT_EVENT_VERSION,
    PHASE9D_FINGERPRINT_POLICY_VERSION,
    PHASE9D_VERSION,
    Phase9DApprovalError,
    canonical_json,
    fingerprint_value,
    prepare_global_blueprint_approval,
)


PHASE9D_AVAILABILITY_POLICY_VERSION = (
    "phase9d-global-blueprint-availability-v1"
)
PHASE9D_AVAILABILITY_EVENT_VERSION = (
    "phase9d-global-blueprint-availability-event-v1"
)
BLUEPRINT_AVAILABLE = "available"
BLUEPRINT_REMOVED = "removed"


def _connect() -> sqlite3.Connection:
    connection = base_manager._connect()
    connection.row_factory = sqlite3.Row
    return connection


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def init_global_blueprint_registry() -> None:
    connection = _connect()
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS global_blueprint_versions (
                blueprint_id TEXT PRIMARY KEY,
                blueprint_fingerprint TEXT NOT NULL UNIQUE,
                phase9d_version TEXT NOT NULL,
                fingerprint_policy_version TEXT NOT NULL,
                role_family_id TEXT NOT NULL,
                role_family_label TEXT NOT NULL,
                version_number INTEGER NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('active', 'superseded')),
                candidate_id TEXT NOT NULL,
                candidate_fingerprint TEXT NOT NULL,
                evaluation_id TEXT NOT NULL,
                evaluation_fingerprint TEXT NOT NULL,
                phase9b_version TEXT NOT NULL,
                phase9c_version TEXT NOT NULL,
                phase9c_policy_version TEXT NOT NULL,
                evidence_link_version TEXT NOT NULL,
                scoring_version TEXT NOT NULL,
                taxonomy_version TEXT NOT NULL,
                semantic_identity_json TEXT NOT NULL,
                blueprint_snapshot_json TEXT NOT NULL,
                display_name TEXT NOT NULL,
                notes TEXT NOT NULL,
                created_at TEXT NOT NULL,
                activated_at TEXT NOT NULL,
                superseded_at TEXT,
                superseded_by_blueprint_id TEXT,
                metadata_updated_at TEXT NOT NULL,
                UNIQUE (role_family_id, version_number)
            )
            """
        )
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_global_blueprint_one_active
            ON global_blueprint_versions (role_family_id)
            WHERE status = 'active'
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_global_blueprint_family_history
            ON global_blueprint_versions (
                role_family_id,
                version_number DESC
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS global_blueprint_audit_events (
                event_id TEXT PRIMARY KEY,
                event_fingerprint TEXT NOT NULL UNIQUE,
                event_version TEXT NOT NULL,
                event_type TEXT NOT NULL,
                role_family_id TEXT NOT NULL,
                blueprint_id TEXT NOT NULL,
                previous_active_blueprint_id TEXT,
                candidate_id TEXT,
                candidate_fingerprint TEXT,
                evaluation_id TEXT,
                evaluation_fingerprint TEXT,
                provisional_override_json TEXT NOT NULL,
                validation_json TEXT NOT NULL,
                metadata_change_json TEXT NOT NULL,
                actor_label TEXT NOT NULL,
                created_at TEXT NOT NULL,
                event_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_global_blueprint_audit_history
            ON global_blueprint_audit_events (
                role_family_id,
                created_at DESC,
                event_id DESC
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS global_blueprint_availability (
                blueprint_id TEXT PRIMARY KEY,
                availability_status TEXT NOT NULL
                    CHECK (availability_status IN ('available', 'removed')),
                availability_policy_version TEXT NOT NULL,
                transition_number INTEGER NOT NULL CHECK (transition_number >= 1),
                last_event_id TEXT NOT NULL,
                removed_at TEXT,
                removed_by TEXT,
                removal_reason TEXT NOT NULL,
                restored_at TEXT,
                restored_by TEXT,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (blueprint_id)
                    REFERENCES global_blueprint_versions (blueprint_id)
                    ON DELETE RESTRICT
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_global_blueprint_availability_status
            ON global_blueprint_availability (
                availability_status,
                updated_at DESC
            )
            """
        )
        connection.commit()
    finally:
        connection.close()


def _safe_json(value: Any) -> dict[str, Any]:
    try:
        parsed = json.loads(str(value or "{}"))
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _row_to_blueprint(row: sqlite3.Row) -> dict[str, Any]:
    keys = set(row.keys())
    availability_status = (
        str(row["availability_status"] or BLUEPRINT_AVAILABLE)
        if "availability_status" in keys
        else BLUEPRINT_AVAILABLE
    )
    availability = {
        "availability_status": availability_status,
        "availability_policy_version": (
            str(row["availability_policy_version"] or "")
            if "availability_policy_version" in keys
            else ""
        ),
        "transition_number": (
            int(row["availability_transition_number"] or 0)
            if "availability_transition_number" in keys
            else 0
        ),
        "last_event_id": (
            str(row["availability_last_event_id"] or "")
            if "availability_last_event_id" in keys
            else ""
        ),
        "removed_at": (
            str(row["availability_removed_at"] or "")
            if "availability_removed_at" in keys
            else ""
        ),
        "removed_by": (
            str(row["availability_removed_by"] or "")
            if "availability_removed_by" in keys
            else ""
        ),
        "removal_reason": (
            str(row["availability_removal_reason"] or "")
            if "availability_removal_reason" in keys
            else ""
        ),
        "restored_at": (
            str(row["availability_restored_at"] or "")
            if "availability_restored_at" in keys
            else ""
        ),
        "restored_by": (
            str(row["availability_restored_by"] or "")
            if "availability_restored_by" in keys
            else ""
        ),
        "updated_at": (
            str(row["availability_updated_at"] or "")
            if "availability_updated_at" in keys
            else ""
        ),
    }
    lifecycle_status = str(row["status"])
    return {
        "blueprint_id": str(row["blueprint_id"]),
        "blueprint_fingerprint": str(row["blueprint_fingerprint"]),
        "phase9d_version": str(row["phase9d_version"]),
        "fingerprint_policy_version": str(
            row["fingerprint_policy_version"]
        ),
        "role_family_id": str(row["role_family_id"]),
        "role_family_label": str(row["role_family_label"]),
        "version_number": int(row["version_number"]),
        "status": lifecycle_status,
        "lifecycle_status": lifecycle_status,
        "availability_status": availability_status,
        "availability": availability,
        "is_reusable": (
            lifecycle_status == "active"
            and availability_status == BLUEPRINT_AVAILABLE
        ),
        "candidate_id": str(row["candidate_id"]),
        "candidate_fingerprint": str(row["candidate_fingerprint"]),
        "evaluation_id": str(row["evaluation_id"]),
        "evaluation_fingerprint": str(row["evaluation_fingerprint"]),
        "semantic_identity": _safe_json(row["semantic_identity_json"]),
        "blueprint_snapshot": _safe_json(row["blueprint_snapshot_json"]),
        "display_name": str(row["display_name"] or ""),
        "notes": str(row["notes"] or ""),
        "created_at": str(row["created_at"]),
        "activated_at": str(row["activated_at"]),
        "superseded_at": str(row["superseded_at"] or ""),
        "superseded_by_blueprint_id": str(
            row["superseded_by_blueprint_id"] or ""
        ),
        "metadata_updated_at": str(row["metadata_updated_at"]),
    }


def _row_to_audit_event(row: sqlite3.Row) -> dict[str, Any]:
    event = _safe_json(row["event_json"])
    event.setdefault("event_id", str(row["event_id"]))
    event.setdefault("event_fingerprint", str(row["event_fingerprint"]))
    return event


_BLUEPRINT_WITH_AVAILABILITY_SELECT = """
    SELECT
        blueprint.*,
        COALESCE(availability.availability_status, 'available')
            AS availability_status,
        COALESCE(availability.availability_policy_version, '')
            AS availability_policy_version,
        COALESCE(availability.transition_number, 0)
            AS availability_transition_number,
        COALESCE(availability.last_event_id, '')
            AS availability_last_event_id,
        COALESCE(availability.removed_at, '')
            AS availability_removed_at,
        COALESCE(availability.removed_by, '')
            AS availability_removed_by,
        COALESCE(availability.removal_reason, '')
            AS availability_removal_reason,
        COALESCE(availability.restored_at, '')
            AS availability_restored_at,
        COALESCE(availability.restored_by, '')
            AS availability_restored_by,
        COALESCE(availability.updated_at, '')
            AS availability_updated_at
    FROM global_blueprint_versions AS blueprint
    LEFT JOIN global_blueprint_availability AS availability
      ON availability.blueprint_id = blueprint.blueprint_id
"""


def _availability_table_exists(connection: sqlite3.Connection) -> bool:
    return connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = 'global_blueprint_availability'
        LIMIT 1
        """
    ).fetchone() is not None


def _availability_state_with_connection(
    connection: sqlite3.Connection,
    blueprint_id: str,
) -> dict[str, Any]:
    row = connection.execute(
        """
        SELECT *
        FROM global_blueprint_availability
        WHERE blueprint_id = ?
        LIMIT 1
        """,
        (str(blueprint_id),),
    ).fetchone()
    if row is None:
        return {
            "availability_status": BLUEPRINT_AVAILABLE,
            "availability_policy_version": "",
            "transition_number": 0,
            "last_event_id": "",
            "removed_at": "",
            "removed_by": "",
            "removal_reason": "",
            "restored_at": "",
            "restored_by": "",
            "updated_at": "",
        }
    return {
        "availability_status": str(row["availability_status"]),
        "availability_policy_version": str(
            row["availability_policy_version"] or ""
        ),
        "transition_number": int(row["transition_number"]),
        "last_event_id": str(row["last_event_id"] or ""),
        "removed_at": str(row["removed_at"] or ""),
        "removed_by": str(row["removed_by"] or ""),
        "removal_reason": str(row["removal_reason"] or ""),
        "restored_at": str(row["restored_at"] or ""),
        "restored_by": str(row["restored_by"] or ""),
        "updated_at": str(row["updated_at"] or ""),
    }


def _blueprint_with_availability_with_connection(
    connection: sqlite3.Connection,
    blueprint_id: str,
) -> dict[str, Any] | None:
    row = connection.execute(
        _BLUEPRINT_WITH_AVAILABILITY_SELECT
        + " WHERE blueprint.blueprint_id = ? LIMIT 1",
        (str(blueprint_id),),
    ).fetchone()
    return _row_to_blueprint(row) if row is not None else None


def active_global_blueprints_with_connection(
    connection: sqlite3.Connection,
) -> list[dict[str, Any]]:
    """Load the reusable active scope inside a caller transaction."""
    rows = connection.execute(
        _BLUEPRINT_WITH_AVAILABILITY_SELECT
        + """
        WHERE blueprint.status = 'active'
          AND COALESCE(availability.availability_status, 'available')
              = 'available'
        ORDER BY blueprint.role_family_label ASC,
                 blueprint.version_number DESC
        """
    ).fetchall()
    return [_row_to_blueprint(row) for row in rows]


def _load_candidate(
    connection: sqlite3.Connection,
    candidate_id: str,
) -> dict[str, Any]:
    row = connection.execute(
        """
        SELECT *
        FROM global_blueprint_candidates
        WHERE candidate_id = ?
        LIMIT 1
        """,
        (candidate_id,),
    ).fetchone()
    if row is None:
        raise Phase9DApprovalError("The persisted Phase 9B candidate is missing.")
    candidate = _safe_json(row["snapshot_json"])
    candidate["candidate_id"] = str(row["candidate_id"])
    candidate["candidate_fingerprint"] = str(row["candidate_fingerprint"])
    candidate["status"] = str(row["status"])
    candidate.setdefault("created_at", str(row["created_at"]))
    candidate.setdefault("updated_at", str(row["updated_at"]))
    return candidate


def _load_evaluation(
    connection: sqlite3.Connection,
    evaluation_id: str,
    evaluation_fingerprint: str,
) -> dict[str, Any]:
    row = connection.execute(
        """
        SELECT *
        FROM blueprint_cross_jd_evaluations
        WHERE evaluation_id = ?
          AND evaluation_fingerprint = ?
        LIMIT 1
        """,
        (evaluation_id, evaluation_fingerprint),
    ).fetchone()
    if row is None:
        raise Phase9DApprovalError(
            "Only an exactly persisted Phase 9C evaluation may be approved."
        )
    evaluation = _safe_json(row["evaluation_json"])
    semantic = evaluation.get("semantic_identity")
    if not isinstance(semantic, dict):
        raise Phase9DApprovalError("The persisted evaluation identity is missing.")
    if canonical_json(semantic) != str(row["semantic_identity_json"]):
        raise Phase9DApprovalError(
            "The Phase 9C row and stored semantic identity do not match."
        )
    column_checks = {
        "evaluation_id": evaluation_id,
        "evaluation_fingerprint": evaluation_fingerprint,
        "phase9c_version": str(row["phase9c_version"]),
    }
    mismatched = [
        key
        for key, value in column_checks.items()
        if str(evaluation.get(key) or "") != value
    ]
    if mismatched:
        raise Phase9DApprovalError(
            "The Phase 9C row columns and evaluation JSON differ: "
            + ", ".join(mismatched)
        )
    candidate_scope = evaluation.get("candidate_scope") or {}
    if str(row["candidate_id"]) != str(candidate_scope.get("candidate_id") or ""):
        raise Phase9DApprovalError("The Phase 9C candidate row is mismatched.")
    if str(row["role_family_id"]) != str(
        candidate_scope.get("role_family_id") or ""
    ):
        raise Phase9DApprovalError("The Phase 9C role-family row is mismatched.")
    return evaluation


def _load_current_jds(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    table = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = 'job_descriptions'
        """
    ).fetchone()
    links_table = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = 'application_job_links'
        """
    ).fetchone()
    if table is None or links_table is None:
        raise Phase9DApprovalError("The current saved-JD library is missing.")
    rows = connection.execute(
        """
        SELECT *
        FROM job_descriptions
        ORDER BY id ASC
        """
    ).fetchall()
    output: list[dict[str, Any]] = []
    for row in rows:
        application_ids = [
            int(item["application_id"])
            for item in connection.execute(
                """
                SELECT application_id
                FROM application_job_links
                WHERE job_description_id = ?
                ORDER BY application_id ASC
                """,
                (int(row["id"]),),
            ).fetchall()
        ]
        output.append(
            {
                "id": int(row["id"]),
                "application_id": (
                    application_ids[0]
                    if application_ids
                    else row["application_id"]
                ),
                "application_ids": application_ids,
                "application_count": len(application_ids),
                "title": row["title"],
                "company": row["company"],
                "location": row["location"] or "",
                "source_type": row["source_type"],
                "source_url": row["source_url"],
                "raw_text": row["raw_text"],
                "jd_profile": _safe_json(row["jd_profile_json"]),
                "canonical_jd_id": row["canonical_jd_id"],
                "source_version_id": row["source_version_id"],
            }
        )
    return output


def _insert_audit_event(
    connection: sqlite3.Connection,
    *,
    event_type: str,
    blueprint: dict[str, Any],
    previous_active_blueprint_id: str,
    provisional_override: dict[str, Any],
    validation: dict[str, Any],
    metadata_change: dict[str, Any] | None,
    actor_label: str,
    created_at: str,
    event_version: str = PHASE9D_AUDIT_EVENT_VERSION,
    lifecycle_change: dict[str, Any] | None = None,
) -> dict[str, Any]:
    identity = blueprint.get("semantic_identity") or {}
    candidate = identity.get("candidate") or {}
    evaluation = identity.get("evaluation") or {}
    event_id = uuid.uuid4().hex
    event = {
        "event_id": event_id,
        "event_version": event_version,
        "event_type": event_type,
        "role_family_id": blueprint["role_family_id"],
        "blueprint_id": blueprint["blueprint_id"],
        "blueprint_fingerprint": blueprint["blueprint_fingerprint"],
        "version_number": int(blueprint["version_number"]),
        "previous_active_blueprint_id": previous_active_blueprint_id,
        "candidate_id": str(candidate.get("candidate_id") or ""),
        "candidate_fingerprint": str(
            candidate.get("candidate_fingerprint") or ""
        ),
        "evaluation_id": str(evaluation.get("evaluation_id") or ""),
        "evaluation_fingerprint": str(
            evaluation.get("evaluation_fingerprint") or ""
        ),
        "provisional_override": deepcopy(provisional_override),
        "validation": deepcopy(validation),
        "metadata_change": deepcopy(metadata_change or {}),
        "actor_label": str(actor_label or "Local user"),
        "created_at": created_at,
    }
    if lifecycle_change is not None:
        event["lifecycle_change"] = deepcopy(lifecycle_change)
    event_fingerprint = fingerprint_value(event)
    event["event_fingerprint"] = event_fingerprint
    connection.execute(
        """
        INSERT INTO global_blueprint_audit_events (
            event_id,
            event_fingerprint,
            event_version,
            event_type,
            role_family_id,
            blueprint_id,
            previous_active_blueprint_id,
            candidate_id,
            candidate_fingerprint,
            evaluation_id,
            evaluation_fingerprint,
            provisional_override_json,
            validation_json,
            metadata_change_json,
            actor_label,
            created_at,
            event_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            event_fingerprint,
            event_version,
            event_type,
            blueprint["role_family_id"],
            blueprint["blueprint_id"],
            previous_active_blueprint_id or None,
            event["candidate_id"] or None,
            event["candidate_fingerprint"] or None,
            event["evaluation_id"] or None,
            event["evaluation_fingerprint"] or None,
            canonical_json(provisional_override),
            canonical_json(validation),
            canonical_json(metadata_change or {}),
            event["actor_label"],
            created_at,
            canonical_json(event),
        ),
    )
    return event


def approve_persisted_phase9c_evaluation(
    *,
    evaluation_id: str,
    evaluation_fingerprint: str,
    provisional_override: dict[str, Any] | None = None,
    display_name: str = "",
    notes: str = "",
    actor_label: str = "Local user",
) -> dict[str, Any]:
    """Atomically approve, exactly reuse, or reactivate a blueprint."""
    evaluation_id = str(evaluation_id or "").strip()
    evaluation_fingerprint = str(evaluation_fingerprint or "").strip()
    if not evaluation_id or not evaluation_fingerprint:
        raise Phase9DApprovalError(
            "Both persisted evaluation ID and fingerprint are required."
        )
    init_global_blueprint_registry()
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        approved_at = _now()
        evaluation = _load_evaluation(
            connection,
            evaluation_id,
            evaluation_fingerprint,
        )
        candidate_scope = evaluation.get("candidate_scope") or {}
        candidate = _load_candidate(
            connection,
            str(candidate_scope.get("candidate_id") or ""),
        )
        if str(candidate.get("candidate_fingerprint") or "") != str(
            candidate_scope.get("candidate_fingerprint") or ""
        ):
            raise Phase9DApprovalError(
                "The persisted candidate fingerprint is mismatched."
            )
        all_saved_jds = _load_current_jds(connection)
        scope = (evaluation.get("semantic_identity") or {}).get(
            "selected_jd_scope"
        ) or []
        selected_ids = {
            int(row["library_jd_id"])
            for row in scope
            if row.get("library_jd_id") is not None
        }
        selected_jds = [
            row for row in all_saved_jds if int(row["id"]) in selected_ids
        ]
        prepared = prepare_global_blueprint_approval(
            candidate=candidate,
            evaluation=evaluation,
            selected_jds=selected_jds,
            all_saved_jds=all_saved_jds,
            provisional_override=provisional_override,
            actor_label=actor_label,
            accepted_at=approved_at,
        )
        identity = prepared["semantic_identity"]
        identity_json = canonical_json(identity)
        existing = connection.execute(
            """
            SELECT *
            FROM global_blueprint_versions
            WHERE blueprint_fingerprint = ?
            LIMIT 1
            """,
            (prepared["blueprint_fingerprint"],),
        ).fetchone()
        if existing is not None and str(existing["semantic_identity_json"]) != identity_json:
            raise RuntimeError(
                "Phase 9D fingerprint collision: semantic identities differ."
            )
        if existing is not None:
            existing_availability = _availability_state_with_connection(
                connection,
                str(existing["blueprint_id"]),
            )
            if (
                existing_availability["availability_status"]
                == BLUEPRINT_REMOVED
            ):
                raise Phase9DApprovalError(
                    "This exact immutable Blueprint was removed from reuse. "
                    "Use the explicit Restore Blueprint lifecycle action; "
                    "approval cannot silently restore or reactivate it."
                )

        active = connection.execute(
            """
            SELECT *
            FROM global_blueprint_versions
            WHERE role_family_id = ? AND status = 'active'
            LIMIT 1
            """,
            (prepared["role_family_id"],),
        ).fetchone()
        previous_active_id = str(active["blueprint_id"]) if active else ""

        if existing is None:
            next_version = int(
                connection.execute(
                    """
                    SELECT COALESCE(MAX(version_number), 0) + 1
                    FROM global_blueprint_versions
                    WHERE role_family_id = ?
                    """,
                    (prepared["role_family_id"],),
                ).fetchone()[0]
            )
            if active is not None:
                connection.execute(
                    """
                    UPDATE global_blueprint_versions
                    SET status = 'superseded',
                        superseded_at = ?,
                        superseded_by_blueprint_id = ?
                    WHERE blueprint_id = ? AND status = 'active'
                    """,
                    (
                        approved_at,
                        prepared["blueprint_id"],
                        previous_active_id,
                    ),
                )
            snapshot = deepcopy(prepared["blueprint_snapshot"])
            snapshot["version_number"] = next_version
            snapshot["status_at_creation"] = "active"
            evaluation_identity = identity["evaluation"]
            candidate_identity = identity["candidate"]
            connection.execute(
                """
                INSERT INTO global_blueprint_versions (
                    blueprint_id,
                    blueprint_fingerprint,
                    phase9d_version,
                    fingerprint_policy_version,
                    role_family_id,
                    role_family_label,
                    version_number,
                    status,
                    candidate_id,
                    candidate_fingerprint,
                    evaluation_id,
                    evaluation_fingerprint,
                    phase9b_version,
                    phase9c_version,
                    phase9c_policy_version,
                    evidence_link_version,
                    scoring_version,
                    taxonomy_version,
                    semantic_identity_json,
                    blueprint_snapshot_json,
                    display_name,
                    notes,
                    created_at,
                    activated_at,
                    superseded_at,
                    superseded_by_blueprint_id,
                    metadata_updated_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?
                )
                """,
                (
                    prepared["blueprint_id"],
                    prepared["blueprint_fingerprint"],
                    PHASE9D_VERSION,
                    PHASE9D_FINGERPRINT_POLICY_VERSION,
                    prepared["role_family_id"],
                    prepared["role_family_label"],
                    next_version,
                    candidate_identity["candidate_id"],
                    candidate_identity["candidate_fingerprint"],
                    evaluation_identity["evaluation_id"],
                    evaluation_identity["evaluation_fingerprint"],
                    candidate_identity["phase9b_version"],
                    evaluation_identity["phase9c_version"],
                    evaluation_identity["policy_version"],
                    evaluation_identity["evidence_link_version"],
                    evaluation_identity["scoring_version"],
                    evaluation_identity["taxonomy_version"],
                    identity_json,
                    canonical_json(snapshot),
                    str(display_name or prepared["role_family_label"]),
                    str(notes or ""),
                    approved_at,
                    approved_at,
                    approved_at,
                ),
            )
            event_type = "approved_new"
            cache_status = "miss"
            stored = connection.execute(
                "SELECT * FROM global_blueprint_versions WHERE blueprint_id = ?",
                (prepared["blueprint_id"],),
            ).fetchone()
        else:
            existing_id = str(existing["blueprint_id"])
            if str(existing["status"]) == "active":
                event_type = "exact_reuse"
                cache_status = "hit_active"
            else:
                if active is not None and previous_active_id != existing_id:
                    connection.execute(
                        """
                        UPDATE global_blueprint_versions
                        SET status = 'superseded',
                            superseded_at = ?,
                            superseded_by_blueprint_id = ?
                        WHERE blueprint_id = ? AND status = 'active'
                        """,
                        (approved_at, existing_id, previous_active_id),
                    )
                connection.execute(
                    """
                    UPDATE global_blueprint_versions
                    SET status = 'active',
                        activated_at = ?,
                        superseded_at = NULL,
                        superseded_by_blueprint_id = NULL
                    WHERE blueprint_id = ?
                    """,
                    (approved_at, existing_id),
                )
                event_type = "reactivated_exact_version"
                cache_status = "hit_reactivated"
            stored = connection.execute(
                "SELECT * FROM global_blueprint_versions WHERE blueprint_id = ?",
                (existing_id,),
            ).fetchone()

        if stored is None:
            raise RuntimeError("The approved Phase 9D blueprint could not be reloaded.")
        blueprint = _row_to_blueprint(stored)
        event = _insert_audit_event(
            connection,
            event_type=event_type,
            blueprint=blueprint,
            previous_active_blueprint_id=previous_active_id,
            provisional_override=prepared["provisional_override"],
            validation=prepared["validation"],
            metadata_change=None,
            actor_label=str(actor_label or "Local user"),
            created_at=approved_at,
        )
        connection.commit()
        return {
            "cache_status": cache_status,
            "blueprint": blueprint,
            "audit_event": event,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def remove_global_blueprint_from_reuse(
    *,
    blueprint_id: str,
    blueprint_fingerprint: str,
    acknowledged: bool,
    actor_label: str = "Local user",
    reason: str = "",
) -> dict[str, Any]:
    """Remove one exact lifecycle-active Blueprint from future reuse."""
    blueprint_id = str(blueprint_id or "").strip()
    blueprint_fingerprint = str(blueprint_fingerprint or "").strip()
    if not blueprint_id or not blueprint_fingerprint:
        raise Phase9DApprovalError(
            "Both Blueprint ID and fingerprint are required for removal."
        )
    if acknowledged is not True:
        raise Phase9DApprovalError(
            "Explicit acknowledgement is required before removing a Blueprint."
        )
    init_global_blueprint_registry()
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT * FROM global_blueprint_versions WHERE blueprint_id = ?",
            (blueprint_id,),
        ).fetchone()
        if row is None:
            raise Phase9DApprovalError("The exact Blueprint was not found.")
        if str(row["blueprint_fingerprint"]) != blueprint_fingerprint:
            raise Phase9DApprovalError(
                "The Blueprint changed since it was displayed. Refresh and try again."
            )
        state = _availability_state_with_connection(connection, blueprint_id)
        if state["availability_status"] == BLUEPRINT_REMOVED:
            connection.rollback()
            current = _blueprint_with_availability_with_connection(
                connection, blueprint_id
            )
            return {
                "cache_status": "hit_removed",
                "blueprint": current,
                "audit_event": None,
            }
        if str(row["status"]) != "active":
            raise Phase9DApprovalError(
                "Only a lifecycle-active Blueprint can be removed from reuse. "
                "Superseded versions already remain in version history."
            )
        active = connection.execute(
            """
            SELECT blueprint_id
            FROM global_blueprint_versions
            WHERE role_family_id = ? AND status = 'active'
            LIMIT 1
            """,
            (str(row["role_family_id"]),),
        ).fetchone()
        if active is None or str(active["blueprint_id"]) != blueprint_id:
            raise Phase9DApprovalError(
                "The role-family activation state changed. Removal failed closed."
            )

        changed_at = _now()
        transition_number = int(state["transition_number"]) + 1
        blueprint = _row_to_blueprint(row)
        lifecycle_change = {
            "availability_policy_version": (
                PHASE9D_AVAILABILITY_POLICY_VERSION
            ),
            "transition_number": transition_number,
            "before": {
                "lifecycle_status": "active",
                "availability_status": BLUEPRINT_AVAILABLE,
            },
            "after": {
                "lifecycle_status": "active",
                "availability_status": BLUEPRINT_REMOVED,
            },
            "acknowledged": True,
            "reason": str(reason or "").strip(),
        }
        event = _insert_audit_event(
            connection,
            event_type="removed_from_reuse",
            blueprint=blueprint,
            previous_active_blueprint_id=blueprint_id,
            provisional_override={},
            validation={
                "exact_blueprint_identity": True,
                "lifecycle_active": True,
                "same_family_active_blueprint_id": blueprint_id,
                "availability_before": BLUEPRINT_AVAILABLE,
            },
            metadata_change=None,
            actor_label=str(actor_label or "Local user"),
            created_at=changed_at,
            event_version=PHASE9D_AVAILABILITY_EVENT_VERSION,
            lifecycle_change=lifecycle_change,
        )
        connection.execute(
            """
            INSERT INTO global_blueprint_availability (
                blueprint_id,
                availability_status,
                availability_policy_version,
                transition_number,
                last_event_id,
                removed_at,
                removed_by,
                removal_reason,
                restored_at,
                restored_by,
                updated_at
            ) VALUES (?, 'removed', ?, ?, ?, ?, ?, ?, NULL, NULL, ?)
            ON CONFLICT(blueprint_id) DO UPDATE SET
                availability_status = excluded.availability_status,
                availability_policy_version = excluded.availability_policy_version,
                transition_number = excluded.transition_number,
                last_event_id = excluded.last_event_id,
                removed_at = excluded.removed_at,
                removed_by = excluded.removed_by,
                removal_reason = excluded.removal_reason,
                restored_at = NULL,
                restored_by = NULL,
                updated_at = excluded.updated_at
            """,
            (
                blueprint_id,
                PHASE9D_AVAILABILITY_POLICY_VERSION,
                transition_number,
                event["event_id"],
                changed_at,
                str(actor_label or "Local user"),
                str(reason or "").strip(),
                changed_at,
            ),
        )
        connection.commit()
        stored = _blueprint_with_availability_with_connection(
            connection, blueprint_id
        )
        if stored is None:
            raise RuntimeError("The removed Blueprint could not be reloaded.")
        return {
            "cache_status": "removed",
            "blueprint": stored,
            "audit_event": event,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def restore_global_blueprint_to_reuse(
    *,
    blueprint_id: str,
    blueprint_fingerprint: str,
    actor_label: str = "Local user",
) -> dict[str, Any]:
    """Restore availability only when the exact underlying version is active."""
    blueprint_id = str(blueprint_id or "").strip()
    blueprint_fingerprint = str(blueprint_fingerprint or "").strip()
    if not blueprint_id or not blueprint_fingerprint:
        raise Phase9DApprovalError(
            "Both Blueprint ID and fingerprint are required for restoration."
        )
    init_global_blueprint_registry()
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT * FROM global_blueprint_versions WHERE blueprint_id = ?",
            (blueprint_id,),
        ).fetchone()
        if row is None:
            raise Phase9DApprovalError("The exact Blueprint was not found.")
        if str(row["blueprint_fingerprint"]) != blueprint_fingerprint:
            raise Phase9DApprovalError(
                "The Blueprint changed since it was displayed. Refresh and try again."
            )
        state = _availability_state_with_connection(connection, blueprint_id)
        if state["availability_status"] == BLUEPRINT_AVAILABLE:
            if str(row["status"]) != "active":
                raise Phase9DApprovalError(
                    "This version is superseded, not removed. It cannot be restored "
                    "through the availability lifecycle."
                )
            connection.rollback()
            current = _blueprint_with_availability_with_connection(
                connection, blueprint_id
            )
            return {
                "cache_status": "hit_available",
                "blueprint": current,
                "audit_event": None,
            }
        if str(row["status"]) != "active":
            replacement = str(row["superseded_by_blueprint_id"] or "")
            suffix = f" by Blueprint {replacement}" if replacement else ""
            raise Phase9DApprovalError(
                "This removed Blueprint has since been superseded"
                f"{suffix}. Restore cannot reactivate or supersede versions."
            )
        active = connection.execute(
            """
            SELECT blueprint_id
            FROM global_blueprint_versions
            WHERE role_family_id = ? AND status = 'active'
            LIMIT 1
            """,
            (str(row["role_family_id"]),),
        ).fetchone()
        if active is None or str(active["blueprint_id"]) != blueprint_id:
            active_id = str(active["blueprint_id"]) if active else "none"
            raise Phase9DApprovalError(
                "Restore conflicts with the role family's current active "
                f"Blueprint ({active_id}). No activation was changed."
            )

        changed_at = _now()
        transition_number = int(state["transition_number"]) + 1
        blueprint = _row_to_blueprint(row)
        lifecycle_change = {
            "availability_policy_version": (
                PHASE9D_AVAILABILITY_POLICY_VERSION
            ),
            "transition_number": transition_number,
            "before": {
                "lifecycle_status": "active",
                "availability_status": BLUEPRINT_REMOVED,
            },
            "after": {
                "lifecycle_status": "active",
                "availability_status": BLUEPRINT_AVAILABLE,
            },
        }
        event = _insert_audit_event(
            connection,
            event_type="restored_to_reuse",
            blueprint=blueprint,
            previous_active_blueprint_id=blueprint_id,
            provisional_override={},
            validation={
                "exact_blueprint_identity": True,
                "lifecycle_active": True,
                "same_family_active_blueprint_id": blueprint_id,
                "availability_before": BLUEPRINT_REMOVED,
            },
            metadata_change=None,
            actor_label=str(actor_label or "Local user"),
            created_at=changed_at,
            event_version=PHASE9D_AVAILABILITY_EVENT_VERSION,
            lifecycle_change=lifecycle_change,
        )
        connection.execute(
            """
            UPDATE global_blueprint_availability
            SET availability_status = 'available',
                availability_policy_version = ?,
                transition_number = ?,
                last_event_id = ?,
                restored_at = ?,
                restored_by = ?,
                updated_at = ?
            WHERE blueprint_id = ? AND availability_status = 'removed'
            """,
            (
                PHASE9D_AVAILABILITY_POLICY_VERSION,
                transition_number,
                event["event_id"],
                changed_at,
                str(actor_label or "Local user"),
                changed_at,
                blueprint_id,
            ),
        )
        connection.commit()
        stored = _blueprint_with_availability_with_connection(
            connection, blueprint_id
        )
        if stored is None:
            raise RuntimeError("The restored Blueprint could not be reloaded.")
        return {
            "cache_status": "restored",
            "blueprint": stored,
            "audit_event": event,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_global_blueprint(blueprint_id: str) -> dict[str, Any] | None:
    init_global_blueprint_registry()
    connection = _connect()
    try:
        row = connection.execute(
            _BLUEPRINT_WITH_AVAILABILITY_SELECT
            + " WHERE blueprint.blueprint_id = ? LIMIT 1",
            (str(blueprint_id),),
        ).fetchone()
        return _row_to_blueprint(row) if row is not None else None
    finally:
        connection.close()


def get_global_blueprint_by_fingerprint(
    blueprint_fingerprint: str,
) -> dict[str, Any] | None:
    init_global_blueprint_registry()
    connection = _connect()
    try:
        row = connection.execute(
            _BLUEPRINT_WITH_AVAILABILITY_SELECT
            + " WHERE blueprint.blueprint_fingerprint = ? LIMIT 1",
            (str(blueprint_fingerprint),),
        ).fetchone()
        return _row_to_blueprint(row) if row is not None else None
    finally:
        connection.close()


def get_active_global_blueprint(
    role_family_id: str,
) -> dict[str, Any] | None:
    init_global_blueprint_registry()
    connection = _connect()
    try:
        row = connection.execute(
            _BLUEPRINT_WITH_AVAILABILITY_SELECT
            + """
            WHERE blueprint.role_family_id = ?
              AND blueprint.status = 'active'
              AND COALESCE(
                    availability.availability_status,
                    'available'
                  ) = 'available'
            LIMIT 1
            """,
            (str(role_family_id),),
        ).fetchone()
        return _row_to_blueprint(row) if row is not None else None
    finally:
        connection.close()


def list_global_blueprints(
    *,
    role_family_id: str | None = None,
    include_superseded: bool = True,
    include_removed: bool = True,
) -> list[dict[str, Any]]:
    init_global_blueprint_registry()
    connection = _connect()
    try:
        clauses: list[str] = []
        values: list[Any] = []
        if role_family_id:
            clauses.append("blueprint.role_family_id = ?")
            values.append(str(role_family_id))
        if not include_superseded:
            clauses.append("blueprint.status = 'active'")
        if not include_removed:
            clauses.append(
                "COALESCE(availability.availability_status, 'available') "
                "= 'available'"
            )
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        rows = connection.execute(
            _BLUEPRINT_WITH_AVAILABILITY_SELECT
            + f"""
            {where}
            ORDER BY blueprint.role_family_label ASC,
                     blueprint.version_number DESC
            """,
            values,
        ).fetchall()
        return [_row_to_blueprint(row) for row in rows]
    finally:
        connection.close()


def list_reusable_global_blueprints(
    *,
    role_family_id: str | None = None,
) -> list[dict[str, Any]]:
    return list_global_blueprints(
        role_family_id=role_family_id,
        include_superseded=False,
        include_removed=False,
    )


def list_removed_global_blueprints() -> list[dict[str, Any]]:
    init_global_blueprint_registry()
    connection = _connect()
    try:
        rows = connection.execute(
            _BLUEPRINT_WITH_AVAILABILITY_SELECT
            + """
            WHERE availability.availability_status = 'removed'
            ORDER BY blueprint.role_family_label ASC,
                     blueprint.version_number DESC
            """
        ).fetchall()
        return [_row_to_blueprint(row) for row in rows]
    finally:
        connection.close()


def list_active_global_blueprints_read_only() -> list[dict[str, Any]]:
    """Return reusable Phase 9D scope without schema or lifecycle writes."""
    connection = _connect()
    try:
        if _availability_table_exists(connection):
            rows = connection.execute(
                _BLUEPRINT_WITH_AVAILABILITY_SELECT
                + """
                WHERE blueprint.status = 'active'
                  AND COALESCE(
                        availability.availability_status,
                        'available'
                      ) = 'available'
                ORDER BY blueprint.role_family_label ASC,
                         blueprint.version_number DESC
                """
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT * FROM global_blueprint_versions
                WHERE status = 'active'
                ORDER BY role_family_label ASC, version_number DESC
                """
            ).fetchall()
        return [_row_to_blueprint(row) for row in rows]
    finally:
        connection.close()


def list_global_blueprint_audit_events(
    *,
    blueprint_id: str | None = None,
    role_family_id: str | None = None,
) -> list[dict[str, Any]]:
    init_global_blueprint_registry()
    connection = _connect()
    try:
        clauses: list[str] = []
        values: list[Any] = []
        if blueprint_id:
            clauses.append("blueprint_id = ?")
            values.append(str(blueprint_id))
        if role_family_id:
            clauses.append("role_family_id = ?")
            values.append(str(role_family_id))
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        rows = connection.execute(
            f"""
            SELECT * FROM global_blueprint_audit_events
            {where}
            ORDER BY created_at DESC, event_id DESC
            """,
            values,
        ).fetchall()
        return [_row_to_audit_event(row) for row in rows]
    finally:
        connection.close()


def update_global_blueprint_display_metadata(
    *,
    blueprint_id: str,
    display_name: str,
    notes: str,
    actor_label: str = "Local user",
) -> dict[str, Any]:
    init_global_blueprint_registry()
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT * FROM global_blueprint_versions WHERE blueprint_id = ?",
            (str(blueprint_id),),
        ).fetchone()
        if row is None:
            raise ValueError("Global blueprint was not found.")
        before = {
            "display_name": str(row["display_name"] or ""),
            "notes": str(row["notes"] or ""),
        }
        after = {
            "display_name": str(display_name or ""),
            "notes": str(notes or ""),
        }
        changed_at = _now()
        connection.execute(
            """
            UPDATE global_blueprint_versions
            SET display_name = ?, notes = ?, metadata_updated_at = ?
            WHERE blueprint_id = ?
            """,
            (after["display_name"], after["notes"], changed_at, blueprint_id),
        )
        updated_row = connection.execute(
            "SELECT * FROM global_blueprint_versions WHERE blueprint_id = ?",
            (str(blueprint_id),),
        ).fetchone()
        if updated_row is None:
            raise RuntimeError("Updated blueprint could not be reloaded.")
        blueprint = _row_to_blueprint(updated_row)
        event = _insert_audit_event(
            connection,
            event_type="display_metadata_updated",
            blueprint=blueprint,
            previous_active_blueprint_id="",
            provisional_override={},
            validation={"identity_unchanged": True},
            metadata_change={"before": before, "after": after},
            actor_label=actor_label,
            created_at=changed_at,
        )
        connection.commit()
        return {"blueprint": blueprint, "audit_event": event}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

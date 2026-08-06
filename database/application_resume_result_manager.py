"""Persistence for immutable application-scoped Phase 9E reuse results."""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import tempfile
import uuid
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from database import tailoring_version_manager as base_manager
from database.application_blueprint_manager import (
    export_application_blueprint_decision,
    resolve_current_phase9e_generation_context,
)
from database.tailoring_generation_control import (
    get_tailoring_generation,
    record_generation_metadata,
)
from database.tailoring_verification_manager import (
    list_tailoring_verifications,
)
from database.tailoring_version_manager import (
    save_application_tailoring_generation,
)
from resume_builder.immutable_snapshot_docx import (
    materialise_immutable_snapshot_docx,
)
from tailoring.phase9e_application_result import (
    APPLICATION_RESULT_FORMAT_VERSION,
    APPLICATION_RESULT_IDENTITY_POLICY_VERSION,
    MODE_APPROVED_SNAPSHOT_REUSE,
    STATUS_REUSED_APPROVED,
    STATUS_REUSED_UNCHANGED_PENDING,
    Phase9EApplicationResultError,
    build_application_result_identity,
    build_application_result_verification,
    canonical_json,
    frozen_content_identity,
    prepare_application_result,
    source_generation_identity,
    verify_application_result_integrity,
)
from tailoring.phase9e_blueprint_selection import (
    fingerprint_value,
    materialise_phase9e_starting_sections,
)
from tailoring.tailoring_generation_fingerprint import (
    stable_content_fingerprint,
)


APPLICATION_RESULT_ARTIFACT_DIR = Path("outputs/application_results")
APPLICATION_RESULT_EVENT_VERSION = "phase9e-application-result-event-v1"
APPLICATION_RESULT_DEBUG_BUNDLE_VERSION = (
    "phase9e-application-result-debug-bundle-v1"
)
EDITABLE_ACTION_DRAFT_VERSION = "phase9e-editable-action-draft-v1"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    connection = base_manager._connect()
    connection.row_factory = sqlite3.Row
    return connection


def _load(value: Any) -> Any:
    text = str(value or "").strip()
    return json.loads(text) if text else {}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def init_application_resume_results() -> None:
    """Apply the additive, idempotent immutable-result schema."""
    connection = _connect()
    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS application_resume_results (
                application_result_id TEXT PRIMARY KEY,
                application_id INTEGER NOT NULL,
                format_version TEXT NOT NULL,
                identity_policy_version TEXT NOT NULL,
                result_fingerprint TEXT NOT NULL UNIQUE,
                generation_mode TEXT NOT NULL,
                initial_status TEXT NOT NULL,
                content_changed INTEGER NOT NULL CHECK(content_changed = 0),
                editable INTEGER NOT NULL CHECK(editable = 0),
                phase9e_decision_id TEXT NOT NULL,
                phase9e_decision_fingerprint TEXT NOT NULL,
                workflow_action TEXT NOT NULL,
                workflow_action_fingerprint TEXT NOT NULL,
                blueprint_id TEXT NOT NULL,
                blueprint_fingerprint TEXT NOT NULL,
                blueprint_version INTEGER NOT NULL,
                starting_snapshot_fingerprint TEXT NOT NULL,
                source_application_id INTEGER NOT NULL,
                source_generation_id TEXT NOT NULL,
                source_verification_id TEXT NOT NULL,
                source_verification_fingerprint TEXT NOT NULL,
                semantic_identity_json TEXT NOT NULL,
                result_snapshot_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(application_id, workflow_action_fingerprint)
            );
            CREATE INDEX IF NOT EXISTS idx_application_resume_results_app
            ON application_resume_results(application_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS application_resume_result_state (
                application_id INTEGER PRIMARY KEY,
                current_result_id TEXT NOT NULL,
                current_result_fingerprint TEXT NOT NULL,
                active_output_mode TEXT NOT NULL,
                current_generation_id TEXT,
                current_verification_id TEXT,
                acceptance_status TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS application_resume_result_artifacts (
                application_result_id TEXT NOT NULL,
                artifact_kind TEXT NOT NULL,
                artifact_sha256 TEXT NOT NULL,
                artifact_size INTEGER NOT NULL,
                mime_type TEXT NOT NULL,
                provenance_mode TEXT NOT NULL,
                provenance_label TEXT NOT NULL,
                original_bytes_available INTEGER NOT NULL,
                is_original_approved_artifact INTEGER NOT NULL,
                source_path TEXT,
                materialized_path TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY(application_result_id, artifact_kind)
            );

            CREATE TABLE IF NOT EXISTS application_resume_result_verifications (
                verification_id TEXT PRIMARY KEY,
                application_id INTEGER NOT NULL,
                application_result_id TEXT NOT NULL,
                verification_fingerprint TEXT NOT NULL UNIQUE,
                verification_version TEXT NOT NULL,
                status TEXT NOT NULL,
                verification_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS application_resume_result_events (
                event_id TEXT PRIMARY KEY,
                event_version TEXT NOT NULL,
                event_type TEXT NOT NULL,
                application_id INTEGER NOT NULL,
                application_result_id TEXT NOT NULL,
                event_fingerprint TEXT NOT NULL,
                actor_label TEXT NOT NULL,
                event_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_application_resume_result_events
            ON application_resume_result_events(application_id, created_at DESC);
            """
        )
        connection.commit()
    finally:
        connection.close()


def _artifact_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "artifact_kind": str(row["artifact_kind"]),
        "artifact_sha256": str(row["artifact_sha256"]),
        "artifact_size": int(row["artifact_size"]),
        "mime_type": str(row["mime_type"]),
        "provenance_mode": str(row["provenance_mode"]),
        "provenance_label": str(row["provenance_label"]),
        "original_bytes_available": bool(row["original_bytes_available"]),
        "is_original_approved_artifact": bool(
            row["is_original_approved_artifact"]
        ),
        "source_path": str(row["source_path"] or ""),
        "materialized_path": str(row["materialized_path"]),
        "created_at": str(row["created_at"]),
    }


def _result_from_row(
    connection: sqlite3.Connection,
    row: sqlite3.Row,
    *,
    validate_artifacts: bool,
) -> dict[str, Any]:
    artifacts = [
        _artifact_from_row(item)
        for item in connection.execute(
            """
            SELECT * FROM application_resume_result_artifacts
            WHERE application_result_id = ? ORDER BY artifact_kind
            """,
            (str(row["application_result_id"]),),
        ).fetchall()
    ]
    result = {
        "application_result_id": str(row["application_result_id"]),
        "application_id": int(row["application_id"]),
        "format_version": str(row["format_version"]),
        "identity_policy_version": str(row["identity_policy_version"]),
        "result_fingerprint": str(row["result_fingerprint"]),
        "generation_mode": str(row["generation_mode"]),
        "initial_status": str(row["initial_status"]),
        "content_changed": bool(row["content_changed"]),
        "editable": bool(row["editable"]),
        "phase9e_decision_id": str(row["phase9e_decision_id"]),
        "phase9e_decision_fingerprint": str(
            row["phase9e_decision_fingerprint"]
        ),
        "workflow_action": str(row["workflow_action"]),
        "workflow_action_fingerprint": str(
            row["workflow_action_fingerprint"]
        ),
        "blueprint_id": str(row["blueprint_id"]),
        "blueprint_fingerprint": str(row["blueprint_fingerprint"]),
        "blueprint_version": int(row["blueprint_version"]),
        "starting_snapshot_fingerprint": str(
            row["starting_snapshot_fingerprint"]
        ),
        "source_application_id": int(row["source_application_id"]),
        "source_generation_id": str(row["source_generation_id"]),
        "source_verification_id": str(row["source_verification_id"]),
        "source_verification_fingerprint": str(
            row["source_verification_fingerprint"]
        ),
        "semantic_identity": _load(row["semantic_identity_json"]),
        "result_snapshot": _load(row["result_snapshot_json"]),
        "artifacts": artifacts,
        "created_at": str(row["created_at"]),
    }
    verify_application_result_integrity(result)
    if validate_artifacts:
        if not artifacts:
            raise Phase9EApplicationResultError(
                "The immutable application result has no persisted artifact."
            )
        for artifact in artifacts:
            path = Path(artifact["materialized_path"])
            if not path.is_file() or _sha256(path) != artifact["artifact_sha256"]:
                raise Phase9EApplicationResultError(
                    "An immutable application-result artifact is missing or corrupt."
                )
    return result


def get_application_resume_result(
    application_result_id: str,
    *,
    validate_artifacts: bool = True,
) -> dict[str, Any] | None:
    init_application_resume_results()
    connection = _connect()
    try:
        row = connection.execute(
            "SELECT * FROM application_resume_results WHERE application_result_id = ?",
            (str(application_result_id),),
        ).fetchone()
        return (
            _result_from_row(
                connection, row, validate_artifacts=validate_artifacts
            )
            if row is not None
            else None
        )
    finally:
        connection.close()


def list_application_resume_results(
    application_id: int,
    *,
    validate_artifacts: bool = False,
) -> list[dict[str, Any]]:
    init_application_resume_results()
    connection = _connect()
    try:
        rows = connection.execute(
            """
            SELECT * FROM application_resume_results
            WHERE application_id = ? ORDER BY created_at DESC, application_result_id
            """,
            (int(application_id),),
        ).fetchall()
        return [
            _result_from_row(
                connection, row, validate_artifacts=validate_artifacts
            )
            for row in rows
        ]
    finally:
        connection.close()


def _state_with_connection(
    connection: sqlite3.Connection, application_id: int
) -> dict[str, Any] | None:
    row = connection.execute(
        "SELECT * FROM application_resume_result_state WHERE application_id = ?",
        (int(application_id),),
    ).fetchone()
    return dict(row) if row is not None else None


def get_current_application_resume_result(
    application_id: int,
    *,
    validate_artifacts: bool = True,
) -> dict[str, Any] | None:
    init_application_resume_results()
    connection = _connect()
    try:
        state = _state_with_connection(connection, application_id)
        if state is None:
            return None
        row = connection.execute(
            "SELECT * FROM application_resume_results WHERE application_result_id = ?",
            (str(state["current_result_id"]),),
        ).fetchone()
        if row is None:
            raise Phase9EApplicationResultError(
                "The current immutable application-result row is missing."
            )
        result = _result_from_row(
            connection, row, validate_artifacts=validate_artifacts
        )
        if result["result_fingerprint"] != str(
            state["current_result_fingerprint"]
        ):
            raise Phase9EApplicationResultError(
                "The current application-result state fingerprint is mismatched."
            )
        result["state"] = state
        return result
    finally:
        connection.close()


def list_application_resume_result_events(
    application_id: int,
) -> list[dict[str, Any]]:
    init_application_resume_results()
    connection = _connect()
    try:
        rows = connection.execute(
            """
            SELECT event_json FROM application_resume_result_events
            WHERE application_id = ? ORDER BY rowid DESC
            """,
            (int(application_id),),
        ).fetchall()
        return [_load(row["event_json"]) for row in rows]
    finally:
        connection.close()


def list_application_result_verifications(
    application_result_id: str,
) -> list[dict[str, Any]]:
    init_application_resume_results()
    connection = _connect()
    try:
        rows = connection.execute(
            """
            SELECT verification_json
            FROM application_resume_result_verifications
            WHERE application_result_id = ?
            ORDER BY created_at ASC, verification_id ASC
            """,
            (str(application_result_id),),
        ).fetchall()
        return [_load(row["verification_json"]) for row in rows]
    finally:
        connection.close()


def _application_result_cover_letters(
    application_result_id: str,
) -> list[dict[str, Any]]:
    """Read related cover letters without making them a result dependency."""
    connection = _connect()
    try:
        table = connection.execute(
            """
            SELECT 1 FROM sqlite_master
            WHERE type = 'table' AND name = 'application_cover_letter_results'
            """
        ).fetchone()
        if table is None:
            return []
        rows = connection.execute(
            """
            SELECT * FROM application_cover_letter_results
            WHERE resume_output_kind = 'immutable_application_result'
              AND resume_output_id = ?
            ORDER BY created_at ASC, cover_letter_id ASC
            """,
            (str(application_result_id),),
        ).fetchall()
        return [
            {
                "cover_letter_id": str(row["cover_letter_id"]),
                "input_fingerprint": str(row["input_fingerprint"]),
                "cover_letter_fingerprint": str(
                    row["cover_letter_fingerprint"]
                ),
                "exact_jd_identity_fingerprint": str(
                    row["exact_jd_identity_fingerprint"]
                ),
                "policy_version": str(row["cover_letter_policy_version"]),
                "prompt_version": str(row["prompt_version"]),
                "model_id": str(row["model_id"]),
                "semantic_identity": _load(row["semantic_identity_json"]),
                "cover_letter_text": str(row["cover_letter_text"]),
                "model_provenance": _load(row["model_provenance_json"]),
                "created_at": str(row["created_at"]),
            }
            for row in rows
        ]
    finally:
        connection.close()


def build_application_result_debug_bundle(
    application_result_id: str,
) -> dict[str, Any]:
    """Build a complete in-memory debug export without mutable session state."""
    result = get_application_resume_result(application_result_id)
    if result is None:
        raise Phase9EApplicationResultError(
            "The immutable application result was not found."
        )
    current = get_current_application_resume_result(
        int(result["application_id"]), validate_artifacts=False
    )
    snapshot = deepcopy(result.get("result_snapshot") or {})
    decision = deepcopy(snapshot.get("phase9e_decision") or {})
    starting = deepcopy(snapshot.get("starting_snapshot") or {})
    blueprint_snapshot = deepcopy(
        starting.get("phase9d_blueprint_snapshot") or {}
    )
    inherited_phase8 = deepcopy(
        snapshot.get("inherited_phase8_verification") or {}
    )
    verifications = list_application_result_verifications(
        application_result_id
    )
    cover_letters = _application_result_cover_letters(application_result_id)
    events = list_application_resume_result_events(
        int(result["application_id"])
    )
    result_events = [
        event for event in events
        if str(event.get("application_result_id") or "")
        == application_result_id
    ]
    acceptance_records = [
        event for event in result_events
        if event.get("event_type")
        == "current_jd_unchanged_result_accepted"
    ]
    workflow_audit = export_application_blueprint_decision(
        result["phase9e_decision_id"]
    )
    phase9e_calls = int(
        (decision.get("mutation_policy") or {}).get("model_calls", 0) or 0
    )
    phase9e_embeddings = int(
        (decision.get("mutation_policy") or {}).get("embedding_calls", 0)
        or 0
    )
    phase8_calls = int(inherited_phase8.get("model_calls", 0) or 0)
    phase8_embeddings = int(
        inherited_phase8.get("embedding_calls", 0) or 0
    )
    result_calls = sum(
        int(row.get("model_calls", 0) or 0) for row in verifications
    )
    result_embeddings = sum(
        int(row.get("embedding_calls", 0) or 0) for row in verifications
    )
    cover_letter_calls = sum(
        int((row.get("model_provenance") or {}).get("model_calls", 0) or 0)
        for row in cover_letters
    )
    cover_letter_embeddings = sum(
        int(
            (row.get("model_provenance") or {}).get("embedding_calls", 0)
            or 0
        )
        for row in cover_letters
    )
    semantic = deepcopy(result.get("semantic_identity") or {})
    return {
        "debug_bundle_version": APPLICATION_RESULT_DEBUG_BUNDLE_VERSION,
        "application_result": {
            "application_result_id": result["application_result_id"],
            "result_fingerprint": result["result_fingerprint"],
            "generation_mode": result["generation_mode"],
            "status": result["initial_status"],
            "content_changed": result["content_changed"],
            "editable": result["editable"],
            "state": deepcopy(
                (current or {}).get("state")
                if current
                and current.get("application_result_id")
                == application_result_id
                else {}
            ),
            "semantic_identity": semantic,
            "complete_snapshot": snapshot,
        },
        "phase9e": {
            "decision": decision,
            "semantic_identity": deepcopy(
                decision.get("semantic_identity") or {}
            ),
            "workflow_action": deepcopy(semantic.get("phase9e") or {}),
            "workflow_audit": workflow_audit,
        },
        "phase9d_blueprint": {
            "blueprint_id": result["blueprint_id"],
            "blueprint_fingerprint": result["blueprint_fingerprint"],
            "version_number": result["blueprint_version"],
            "complete_frozen_snapshot": blueprint_snapshot,
        },
        "frozen_resume": {
            "resume_profile_snapshot": deepcopy(
                starting.get("resume_profile_snapshot") or {}
            ),
            "resume_text_snapshot": str(
                starting.get("resume_text_snapshot") or ""
            ),
            "frozen_content_identity": deepcopy(
                semantic.get("frozen_content") or {}
            ),
        },
        "source_approved_generation": deepcopy(
            snapshot.get("source_generation") or {}
        ),
        "inherited_fit_identity": deepcopy(
            semantic.get("inherited_fit") or {}
        ),
        "inherited_phase8_verification": inherited_phase8,
        "current_jd": {
            "identity": deepcopy(semantic.get("current_jd") or {}),
            "stable_input_provenance": deepcopy(
                (decision.get("semantic_identity") or {}).get("current_jd")
                or {}
            ),
        },
        "artifacts": deepcopy(result.get("artifacts") or []),
        "result_verifications": verifications,
        "acceptance_records": acceptance_records,
        "append_only_application_result_events": result_events,
        "application_result_cover_letters": cover_letters,
        "call_totals": {
            "phase9e_model_calls": phase9e_calls,
            "phase9e_embedding_calls": phase9e_embeddings,
            "inherited_phase8_model_calls": phase8_calls,
            "inherited_phase8_embedding_calls": phase8_embeddings,
            "result_verification_model_calls": result_calls,
            "result_verification_embedding_calls": result_embeddings,
            "cover_letter_model_calls": cover_letter_calls,
            "cover_letter_embedding_calls": cover_letter_embeddings,
            "model_calls": (
                phase9e_calls
                + phase8_calls
                + result_calls
                + cover_letter_calls
            ),
            "embedding_calls": (
                phase9e_embeddings
                + phase8_embeddings
                + result_embeddings
                + cover_letter_embeddings
            ),
        },
        "authority_policy": {
            "mutable_session_state_included": False,
            "resume_authority": "immutable_application_result_snapshot",
            "jd_authority": "persisted_phase9e_exact_jd_identity",
        },
    }


def _insert_event(
    connection: sqlite3.Connection,
    *,
    event_type: str,
    application_id: int,
    application_result_id: str,
    actor_label: str,
    details: dict[str, Any],
    created_at: str,
) -> dict[str, Any]:
    event = {
        "event_id": uuid.uuid4().hex,
        "event_version": APPLICATION_RESULT_EVENT_VERSION,
        "event_type": event_type,
        "application_id": int(application_id),
        "application_result_id": application_result_id,
        "actor_label": str(actor_label or "Local user"),
        "details": deepcopy(details),
        "created_at": created_at,
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
            event["event_id"], APPLICATION_RESULT_EVENT_VERSION, event_type,
            int(application_id), application_result_id,
            event["event_fingerprint"], event["actor_label"],
            canonical_json(event), created_at,
        ),
    )
    return event


def _source_records(decision: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    starting = decision.get("starting_snapshot") or {}
    phase9d = starting.get("phase9d_blueprint_snapshot") or {}
    candidate = phase9d.get("phase9b_candidate_semantic_snapshot") or {}
    source_application_id = int(candidate.get("source_application_id", 0) or 0)
    source_generation_id = str(candidate.get("source_generation_id") or "").strip()
    expected_verification = str(
        candidate.get("source_verification_fingerprint")
        or (phase9d.get("provenance") or {}).get(
            "source_verification_fingerprint"
        )
        or ""
    ).strip()
    if source_application_id <= 0 or not source_generation_id or not expected_verification:
        raise Phase9EApplicationResultError(
            "The immutable Phase 9D source generation or Phase 8 identity is incomplete."
        )
    generation = get_tailoring_generation(
        source_application_id, source_generation_id
    )
    if generation is None:
        raise Phase9EApplicationResultError(
            "The immutable blueprint's source generation is unavailable."
        )
    if (
        str(generation.get("status") or "") != "approved"
        and not str(generation.get("approved_at") or "").strip()
    ):
        raise Phase9EApplicationResultError(
            "The immutable blueprint's source generation has no persisted approval provenance."
        )
    matches = [
        row for row in list_tailoring_verifications(source_application_id)
        if str(row.get("generation_id") or "") == source_generation_id
        and str(row.get("verification_fingerprint") or "")
        == expected_verification
    ]
    if len(matches) != 1:
        raise Phase9EApplicationResultError(
            "The immutable blueprint's exact Phase 8 verification cannot be resolved uniquely."
        )
    verification = matches[0]
    if verification.get("blueprint_ready") is not True:
        raise Phase9EApplicationResultError(
            "The inherited Phase 8 verification is not blueprint-ready."
        )
    return generation, verification


def _existing_for_action(
    application_id: int, workflow_action_fingerprint: str
) -> dict[str, Any] | None:
    init_application_resume_results()
    connection = _connect()
    try:
        row = connection.execute(
            """
            SELECT * FROM application_resume_results
            WHERE application_id = ? AND workflow_action_fingerprint = ?
            """,
            (int(application_id), workflow_action_fingerprint),
        ).fetchone()
        return (
            _result_from_row(connection, row, validate_artifacts=True)
            if row is not None else None
        )
    finally:
        connection.close()


def _stage_artifacts(
    *,
    generation: dict[str, Any],
    starting_snapshot: dict[str, Any],
    temporary_dir: Path,
) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    candidates = (
        (
            "docx",
            generation.get("docx_path") or generation.get("stored_docx_path"),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        (
            "pdf",
            generation.get("pdf_path") or generation.get("stored_pdf_path"),
            "application/pdf",
        ),
    )
    for kind, raw_path, mime in candidates:
        source = Path(str(raw_path or ""))
        if not raw_path or not source.is_file():
            continue
        staged = temporary_dir / f"artifact.{kind}"
        source_sha256 = _sha256(source)
        shutil.copyfile(source, staged)
        staged_sha256 = _sha256(staged)
        if staged_sha256 != source_sha256:
            raise Phase9EApplicationResultError(
                "The approved source artifact copy failed SHA-256 verification."
            )
        artifacts.append(
            {
                "artifact_kind": kind,
                "artifact_sha256": staged_sha256,
                "artifact_size": staged.stat().st_size,
                "mime_type": mime,
                "provenance_mode": "original_approved_artifact",
                "provenance_label": "Original approved artifact",
                "original_bytes_available": True,
                "is_original_approved_artifact": True,
                "source_path": str(source),
                "staged_path": str(staged),
            }
        )
    if not any(row["artifact_kind"] == "docx" for row in artifacts):
        staged = temporary_dir / "artifact.docx"
        materialise_immutable_snapshot_docx(
            resume_text=str(starting_snapshot.get("resume_text_snapshot") or ""),
            output_path=staged,
        )
        artifacts.append(
            {
                "artifact_kind": "docx",
                "artifact_sha256": _sha256(staged),
                "artifact_size": staged.stat().st_size,
                "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "provenance_mode": "rematerialized_immutable_blueprint_snapshot",
                "provenance_label": "Re-materialized from immutable blueprint snapshot",
                "original_bytes_available": False,
                "is_original_approved_artifact": False,
                "source_path": "",
                "staged_path": str(staged),
            }
        )
    return sorted(artifacts, key=lambda row: row["artifact_kind"])


def create_or_reuse_current_application_result(
    *,
    application_id: int,
    actor_label: str = "Local user",
    artifact_root: str | Path | None = None,
) -> dict[str, Any]:
    """Persist one unchanged immutable result; never create a draft or rerun fit."""
    context = resolve_current_phase9e_generation_context(application_id)
    if context.get("status") != "current" or not context.get("can_generate"):
        raise Phase9EApplicationResultError(
            "A current, explicitly activated Phase 9E scope is required."
        )
    decision = context.get("decision") or {}
    workflow = context.get("workflow_action") or {}
    explicit = workflow.get("explicit_action_event") or {}
    if not explicit:
        raise Phase9EApplicationResultError(
            "A persisted append-only Phase 9E workflow action is required."
        )
    action_fingerprint = str(
        workflow.get("workflow_action_fingerprint") or ""
    )
    existing = _existing_for_action(application_id, action_fingerprint)
    if existing is not None:
        if existing["phase9e_decision_fingerprint"] != decision.get(
            "decision_fingerprint"
        ):
            raise Phase9EApplicationResultError(
                "The stored workflow-action result is bound to a different decision."
            )
        connection = _connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            now = _now()
            prior_state = _state_with_connection(connection, application_id)
            current_verification_id = ""
            acceptance_status = (
                "inherited_source_approval"
                if existing["initial_status"] == STATUS_REUSED_APPROVED
                else "pending_application_verification"
            )
            if (
                prior_state is not None
                and str(prior_state.get("current_result_id") or "")
                == existing["application_result_id"]
            ):
                current_verification_id = str(
                    prior_state.get("current_verification_id") or ""
                )
                acceptance_status = str(
                    prior_state.get("acceptance_status") or acceptance_status
                )
            elif existing["initial_status"] != STATUS_REUSED_APPROVED:
                verification_row = connection.execute(
                    """
                    SELECT verification_id
                    FROM application_resume_result_verifications
                    WHERE application_result_id = ?
                    ORDER BY created_at DESC, verification_id DESC LIMIT 1
                    """,
                    (existing["application_result_id"],),
                ).fetchone()
                if verification_row is not None:
                    current_verification_id = str(
                        verification_row["verification_id"]
                    )
                    acceptance_status = "verified_pending_user_acceptance"
                    accepted = connection.execute(
                        """
                        SELECT 1 FROM application_resume_result_events
                        WHERE application_result_id = ?
                          AND event_type = 'current_jd_unchanged_result_accepted'
                        LIMIT 1
                        """,
                        (existing["application_result_id"],),
                    ).fetchone()
                    if accepted is not None:
                        acceptance_status = "accepted_for_current_application"
            connection.execute(
                """
                INSERT INTO application_resume_result_state (
                    application_id, current_result_id, current_result_fingerprint,
                    active_output_mode, current_generation_id,
                    current_verification_id, acceptance_status, updated_at
                ) VALUES (?, ?, ?, 'immutable_result', NULL, ?, ?, ?)
                ON CONFLICT(application_id) DO UPDATE SET
                    current_result_id=excluded.current_result_id,
                    current_result_fingerprint=excluded.current_result_fingerprint,
                    active_output_mode='immutable_result',
                    current_generation_id=NULL,
                    current_verification_id=excluded.current_verification_id,
                    acceptance_status=excluded.acceptance_status,
                    updated_at=excluded.updated_at
                """,
                (
                    int(application_id), existing["application_result_id"],
                    existing["result_fingerprint"],
                    current_verification_id or None,
                    acceptance_status,
                    now,
                ),
            )
            _insert_event(
                connection, event_type="immutable_result_reused",
                application_id=application_id,
                application_result_id=existing["application_result_id"],
                actor_label=actor_label,
                details={"cache_status": "hit"}, created_at=now,
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return {"cache_status": "hit", "application_result": existing}

    generation, verification = _source_records(decision)
    starting = decision.get("starting_snapshot") or {}
    sections = materialise_phase9e_starting_sections(decision)
    source_identity = source_generation_identity(
        generation, effective_sections=sections
    )
    with tempfile.TemporaryDirectory(prefix="phase9e_result_") as temp_name:
        staged = _stage_artifacts(
            generation=generation,
            starting_snapshot=starting,
            temporary_dir=Path(temp_name),
        )
        artifact_identity = {
            "artifacts": [
                {
                    key: value for key, value in row.items()
                    if key not in {"staged_path", "source_path"}
                }
                for row in staged
            ],
            "frozen_content_fingerprint": frozen_content_identity(starting)[
                "frozen_content_fingerprint"
            ],
        }
        identity = build_application_result_identity(
            application_id=application_id,
            decision=decision,
            workflow_action={
                "workflow_action": workflow.get("workflow_action"),
                "workflow_action_fingerprint": action_fingerprint,
            },
            source_generation=source_identity,
            source_verification=verification,
            artifact_identity=artifact_identity,
        )
        snapshot = {
            "starting_snapshot": deepcopy(starting),
            "phase9e_decision": deepcopy(decision),
            "source_generation": deepcopy(generation),
            "inherited_phase8_verification": deepcopy(verification),
            "artifact_provenance": deepcopy(artifact_identity),
        }
        prepared = prepare_application_result(identity=identity, snapshot=snapshot)
        root = Path(artifact_root or APPLICATION_RESULT_ARTIFACT_DIR)
        destination_dir = root / prepared["application_result_id"]
        destination_dir.mkdir(parents=True, exist_ok=True)
        final_artifacts: list[dict[str, Any]] = []
        for row in staged:
            destination = destination_dir / f"resume.{row['artifact_kind']}"
            shutil.copyfile(Path(row["staged_path"]), destination)
            final_artifacts.append({**row, "materialized_path": str(destination)})

        connection = _connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            now = _now()
            phase9e = identity["phase9e"]
            blueprint = identity["blueprint"]
            source = identity["source_generation"]
            inherited = identity["inherited_phase8"]
            connection.execute(
                """
                INSERT INTO application_resume_results (
                    application_result_id, application_id, format_version,
                    identity_policy_version, result_fingerprint, generation_mode,
                    initial_status, content_changed, editable, phase9e_decision_id,
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
                    prepared["application_result_id"], int(application_id),
                    APPLICATION_RESULT_FORMAT_VERSION,
                    APPLICATION_RESULT_IDENTITY_POLICY_VERSION,
                    prepared["result_fingerprint"], prepared["generation_mode"],
                    prepared["initial_status"], phase9e["decision_id"],
                    phase9e["decision_fingerprint"], phase9e["workflow_action"],
                    phase9e["workflow_action_fingerprint"], blueprint["blueprint_id"],
                    blueprint["blueprint_fingerprint"], blueprint["version_number"],
                    identity["starting_snapshot_fingerprint"],
                    source["source_application_id"], source["source_generation_id"],
                    inherited["verification_id"], inherited["verification_fingerprint"],
                    canonical_json(identity), canonical_json(snapshot), now,
                ),
            )
            for artifact in final_artifacts:
                connection.execute(
                    """
                    INSERT INTO application_resume_result_artifacts (
                        application_result_id, artifact_kind, artifact_sha256,
                        artifact_size, mime_type, provenance_mode,
                        provenance_label, original_bytes_available,
                        is_original_approved_artifact, source_path,
                        materialized_path, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        prepared["application_result_id"], artifact["artifact_kind"],
                        artifact["artifact_sha256"], artifact["artifact_size"],
                        artifact["mime_type"], artifact["provenance_mode"],
                        artifact["provenance_label"],
                        int(artifact["original_bytes_available"]),
                        int(artifact["is_original_approved_artifact"]),
                        artifact["source_path"], artifact["materialized_path"], now,
                    ),
                )
            acceptance = (
                "inherited_source_approval"
                if prepared["initial_status"] == STATUS_REUSED_APPROVED
                else "pending_application_verification"
            )
            connection.execute(
                """
                INSERT INTO application_resume_result_state (
                    application_id, current_result_id, current_result_fingerprint,
                    active_output_mode, current_generation_id,
                    current_verification_id, acceptance_status, updated_at
                ) VALUES (?, ?, ?, 'immutable_result', NULL, NULL, ?, ?)
                ON CONFLICT(application_id) DO UPDATE SET
                    current_result_id=excluded.current_result_id,
                    current_result_fingerprint=excluded.current_result_fingerprint,
                    active_output_mode='immutable_result',
                    current_generation_id=NULL,
                    current_verification_id=NULL,
                    acceptance_status=excluded.acceptance_status,
                    updated_at=excluded.updated_at
                """,
                (int(application_id), prepared["application_result_id"],
                 prepared["result_fingerprint"], acceptance, now),
            )
            _insert_event(
                connection, event_type="immutable_result_created",
                application_id=application_id,
                application_result_id=prepared["application_result_id"],
                actor_label=actor_label,
                details={"cache_status": "miss", "generation_mode": prepared["generation_mode"]},
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
        raise RuntimeError("The immutable application result could not be reloaded.")
    return {"cache_status": "miss", "application_result": stored}


def verify_current_application_result(
    *, application_id: int, actor_label: str = "Local user"
) -> dict[str, Any]:
    result = get_current_application_resume_result(application_id)
    if result is None:
        raise Phase9EApplicationResultError("No immutable application result is current.")
    if result["initial_status"] != STATUS_REUSED_UNCHANGED_PENDING:
        raise Phase9EApplicationResultError(
            "Exact approved-source reuse inherits Phase 8 and needs no current-JD verification."
        )
    context = resolve_current_phase9e_generation_context(application_id)
    decision = context.get("decision") or {}
    verification = build_application_result_verification(
        result=result, decision=decision
    )
    init_application_resume_results()
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            "SELECT verification_json FROM application_resume_result_verifications WHERE verification_fingerprint = ?",
            (verification["verification_fingerprint"],),
        ).fetchone()
        now = _now()
        if existing is None:
            connection.execute(
                """
                INSERT INTO application_resume_result_verifications (
                    verification_id, application_id, application_result_id,
                    verification_fingerprint, verification_version, status,
                    verification_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (verification["verification_id"], int(application_id),
                 result["application_result_id"], verification["verification_fingerprint"],
                 verification["verification_version"], verification["status"],
                 canonical_json(verification), now),
            )
            cache_status = "miss"
        else:
            cache_status = "hit"
            verification = _load(existing["verification_json"])
        connection.execute(
            """
            UPDATE application_resume_result_state
            SET current_verification_id = ?, acceptance_status = ?, updated_at = ?
            WHERE application_id = ? AND current_result_id = ?
            """,
            (verification["verification_id"], "verified_pending_user_acceptance",
             now, int(application_id), result["application_result_id"]),
        )
        _insert_event(
            connection, event_type="current_jd_verification_recorded",
            application_id=application_id,
            application_result_id=result["application_result_id"],
            actor_label=actor_label,
            details={"verification_id": verification["verification_id"],
                     "cache_status": cache_status}, created_at=now,
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return {"cache_status": cache_status, "verification": verification}


def accept_current_application_result(
    *, application_id: int, acknowledgement: bool, reason: str,
    actor_label: str = "Local user"
) -> dict[str, Any]:
    if acknowledgement is not True:
        raise Phase9EApplicationResultError(
            "Explicit current-JD unchanged-result acceptance is required."
        )
    clean_reason = " ".join(str(reason or "").split())
    if len(clean_reason) < 12:
        raise Phase9EApplicationResultError(
            "Provide a substantive acceptance reason of at least 12 characters."
        )
    result = get_current_application_resume_result(application_id)
    if result is None or result["initial_status"] != STATUS_REUSED_UNCHANGED_PENDING:
        raise Phase9EApplicationResultError(
            "A pending different-JD unchanged result is required."
        )
    state = result["state"]
    verification_id = str(state.get("current_verification_id") or "")
    if not verification_id:
        raise Phase9EApplicationResultError(
            "Record the separate current-JD verification before acceptance."
        )
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT verification_json FROM application_resume_result_verifications WHERE verification_id = ?",
            (verification_id,),
        ).fetchone()
        if row is None:
            raise Phase9EApplicationResultError(
                "The current-JD verification row is missing."
            )
        now = _now()
        connection.execute(
            """
            UPDATE application_resume_result_state
            SET acceptance_status='accepted_for_current_application', updated_at=?
            WHERE application_id=? AND current_result_id=?
            """,
            (now, int(application_id), result["application_result_id"]),
        )
        event = _insert_event(
            connection, event_type="current_jd_unchanged_result_accepted",
            application_id=application_id,
            application_result_id=result["application_result_id"],
            actor_label=actor_label,
            details={"verification_id": verification_id,
                     "acknowledgement": True, "reason": clean_reason},
            created_at=now,
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return {"application_result": get_current_application_resume_result(application_id),
            "audit_event": event}


def create_editable_copy_from_current_application_result(
    *, application_id: int, actor_label: str = "Local user"
) -> dict[str, Any]:
    result = get_current_application_resume_result(application_id)
    if result is None:
        raise Phase9EApplicationResultError("No immutable application result is current.")
    starting = (result.get("result_snapshot") or {}).get("starting_snapshot") or {}
    decision = (result.get("result_snapshot") or {}).get("phase9e_decision") or {}
    if frozen_content_identity(starting)["frozen_content_fingerprint"] != (
        (result.get("semantic_identity") or {}).get("frozen_content") or {}
    ).get("frozen_content_fingerprint"):
        raise Phase9EApplicationResultError(
            "The immutable starting content does not match the result identity."
        )
    sections = materialise_phase9e_starting_sections(decision)
    generation_id = uuid.uuid4().hex
    settings = {
        "generation_kind": "phase9e_editable_fork",
        "source_application_result_id": result["application_result_id"],
        "phase9e_decision_fingerprint": result["phase9e_decision_fingerprint"],
        "base_content_fingerprint": stable_content_fingerprint(sections),
        "content_changed": False,
    }
    save_application_tailoring_generation(
        application_id=application_id, generation_id=generation_id,
        projects=sections["projects"], skills=sections["skills"],
        generation_settings=settings,
    )
    record_generation_metadata(
        application_id=application_id, generation_id=generation_id,
        generation_kind="phase9e_editable_fork",
        source_application_result_id=result["application_result_id"],
        base_content_fingerprint=settings["base_content_fingerprint"],
        content_fingerprint=settings["base_content_fingerprint"],
        content_changed=False,
        phase9e_decision_fingerprint=result["phase9e_decision_fingerprint"],
    )
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        now = _now()
        connection.execute(
            """
            UPDATE application_resume_result_state
            SET active_output_mode='editable', current_generation_id=?, updated_at=?
            WHERE application_id=? AND current_result_id=?
            """,
            (generation_id, now, int(application_id), result["application_result_id"]),
        )
        event = _insert_event(
            connection, event_type="editable_copy_created",
            application_id=application_id,
            application_result_id=result["application_result_id"],
            actor_label=actor_label,
            details={"generation_id": generation_id,
                     "content_changed": False}, created_at=now,
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return {"generation_id": generation_id, "audit_event": event}


def create_or_reuse_phase9e_editable_action_draft(
    *, application_id: int
) -> dict[str, Any]:
    """Create a draft only after a workflow action explicitly permits changes."""
    context = resolve_current_phase9e_generation_context(application_id)
    if context.get("status") != "current" or not context.get("can_generate"):
        raise Phase9EApplicationResultError(
            "A current Phase 9E workflow action is required for an editable draft."
        )
    workflow = context.get("workflow_action") or {}
    action = str(workflow.get("workflow_action") or "")
    if action not in {
        "apply_optional_polish",
        "apply_targeted_retargeting",
        "regenerate_from_original_resume",
    }:
        raise Phase9EApplicationResultError(
            "This Phase 9E action does not permit an editable draft."
        )
    if not workflow.get("explicit_action_event"):
        raise Phase9EApplicationResultError(
            "The editable workflow action must be persisted before draft creation."
        )
    action_fingerprint = str(
        workflow.get("workflow_action_fingerprint") or ""
    )
    generation_id = fingerprint_value(
        {
            "version": EDITABLE_ACTION_DRAFT_VERSION,
            "application_id": int(application_id),
            "workflow_action_fingerprint": action_fingerprint,
        }
    )[:32]
    existing = get_tailoring_generation(application_id, generation_id)
    if existing is not None:
        if str(existing.get("phase9e_decision_fingerprint") or "") != str(
            (context.get("decision") or {}).get("decision_fingerprint") or ""
        ):
            raise Phase9EApplicationResultError(
                "The editable action-draft identity collided with another Phase 9E scope."
            )
        return {"cache_status": "hit", "generation": existing}

    decision = context.get("decision") or {}
    sections = materialise_phase9e_starting_sections(decision)
    base_fingerprint = stable_content_fingerprint(sections)
    settings = {
        "generation_kind": "phase9e_editable_action_draft",
        "editable_action_draft_version": EDITABLE_ACTION_DRAFT_VERSION,
        "phase9e_binding": deepcopy(context.get("binding_identity") or {}),
        "phase9e_base_content_fingerprint": base_fingerprint,
        "workflow_action": action,
        "content_changed": False,
    }
    save_application_tailoring_generation(
        application_id=application_id,
        generation_id=generation_id,
        projects=sections["projects"],
        skills=sections["skills"],
        generation_settings=settings,
    )
    record_generation_metadata(
        application_id=application_id,
        generation_id=generation_id,
        input_fingerprint=action_fingerprint,
        generation_kind="phase9e_editable_action_draft",
        base_content_fingerprint=base_fingerprint,
        content_fingerprint=base_fingerprint,
        content_changed=False,
        phase9e_decision_fingerprint=str(
            decision.get("decision_fingerprint") or ""
        ),
    )
    created = get_tailoring_generation(application_id, generation_id)
    if created is None:
        raise RuntimeError("The Phase 9E editable action draft could not be reloaded.")
    return {"cache_status": "miss", "generation": created}


def delete_application_resume_results(application_id: int) -> None:
    """Delete result rows only as part of deleting the parent application."""
    init_application_resume_results()
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        result_ids = [
            str(row[0]) for row in connection.execute(
                "SELECT application_result_id FROM application_resume_results WHERE application_id=?",
                (int(application_id),),
            ).fetchall()
        ]
        for table in (
            "application_resume_result_events",
            "application_resume_result_verifications",
        ):
            connection.execute(
                f"DELETE FROM {table} WHERE application_id = ?", (int(application_id),)
            )
        for result_id in result_ids:
            connection.execute(
                "DELETE FROM application_resume_result_artifacts WHERE application_result_id=?",
                (result_id,),
            )
        connection.execute(
            "DELETE FROM application_resume_result_state WHERE application_id=?",
            (int(application_id),),
        )
        connection.execute(
            "DELETE FROM application_resume_results WHERE application_id=?",
            (int(application_id),),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

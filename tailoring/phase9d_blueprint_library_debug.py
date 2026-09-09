"""Read-only Blueprint Library debug snapshot builder.

This module gathers the data that drives the Phase 9D Blueprint Library page
without executing model, embedding, Chroma, approval, removal, restore, or
metadata-write actions.
"""

from __future__ import annotations

import json
from typing import Any

from database.application_resume_result_manager import (
    get_current_application_resume_result,
)
from database.blueprint_evaluation_manager import list_blueprint_evaluations
from database.global_blueprint_manager import (
    get_persisted_blueprint_candidate,
    list_global_blueprint_audit_events,
    list_global_blueprints,
    list_reusable_global_blueprints,
)
from database.global_blueprint_tag_manager import (
    get_blueprint_lane_tags,
    init_global_blueprint_tag_registry,
    list_blueprint_lane_tag_usage,
    list_blueprint_tags,
)
from tailoring.phase9d_variant_tags import (
    AVAILABLE_VARIANT_TAGS,
    derive_candidate_variant_tag_scores,
    derive_candidate_variant_tags,
    suggest_blueprint_variant_lane,
    variant_tags_from_label,
)
from tailoring.phase9f_starting_source_provenance import (
    Phase9FBProvenanceError,
    load_blueprint_provenance_read_only,
)


BLUEPRINT_LIBRARY_DEBUG_VERSION = "phase9d-blueprint-library-debug-v1"


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _selected_evaluation(
    evaluations: list[dict[str, Any]],
    evaluation_id: str,
) -> dict[str, Any] | None:
    requested = _clean(evaluation_id)
    if requested:
        for row in evaluations:
            if _clean(row.get("evaluation_id")) == requested:
                return row
    return evaluations[0] if evaluations else None


def _selected_blueprint(
    blueprints: list[dict[str, Any]],
    blueprint_id: str,
) -> dict[str, Any] | None:
    requested = _clean(blueprint_id)
    if requested:
        for row in blueprints:
            if _clean(row.get("blueprint_id")) == requested:
                return row
    return None


def _safe_current_application_result(
    current_application_id: int | None,
) -> dict[str, Any] | None:
    if current_application_id is None:
        return None
    try:
        return get_current_application_resume_result(
            int(current_application_id),
            validate_artifacts=False,
        )
    except (TypeError, ValueError, RuntimeError, OSError):
        return None


def build_blueprint_library_debug_payload(
    *,
    current_application_id: int | None,
    page_state: dict[str, Any],
) -> dict[str, Any]:
    """Build one complete read-only snapshot of Blueprint Library page inputs."""
    init_global_blueprint_tag_registry()
    evaluations = list_blueprint_evaluations()
    blueprints = list_global_blueprints(include_superseded=True)
    reusable = list_reusable_global_blueprints()
    audit_events = list_global_blueprint_audit_events()

    selected_evaluation = _selected_evaluation(
        evaluations,
        _clean(page_state.get("evaluation_id")),
    )
    selected_blueprint = _selected_blueprint(
        blueprints,
        _clean(page_state.get("inspect_blueprint_id")),
    )

    selected_candidate: dict[str, Any] | None = None
    selected_tag_debug: dict[str, Any] | None = None
    active_family_lanes: list[dict[str, Any]] = []

    if selected_evaluation is not None:
        semantic = selected_evaluation.get("semantic_identity") or {}
        candidate_scope = (
            selected_evaluation.get("candidate_scope")
            or semantic.get("candidate")
            or {}
        )
        candidate_id = _clean(candidate_scope.get("candidate_id"))
        role_family_id = _clean(candidate_scope.get("role_family_id"))

        if candidate_id:
            try:
                selected_candidate = get_persisted_blueprint_candidate(
                    candidate_id
                )
            except (ValueError, RuntimeError):
                selected_candidate = None

        if role_family_id:
            active_family_lanes = [
                dict(row)
                for row in blueprints
                if _clean(row.get("role_family_id")) == role_family_id
                and _clean(row.get("status")) == "active"
            ]
            for lane in active_family_lanes:
                lane["persisted_tags"] = [
                    row["label"]
                    for row in get_blueprint_lane_tags(
                        role_family_id=_clean(lane.get("role_family_id")),
                        variant_id=_clean(lane.get("variant_id")),
                    )
                ]

        if selected_candidate is not None:
            confirmed_tags = [
                _clean(value)
                for value in page_state.get("confirmed_variant_tags") or []
                if _clean(value) in set(AVAILABLE_VARIANT_TAGS)
            ]
            automatic_suggestion = suggest_blueprint_variant_lane(
                candidate=selected_candidate,
                active_family_lanes=active_family_lanes,
            )
            confirmed_suggestion = suggest_blueprint_variant_lane(
                candidate=selected_candidate,
                active_family_lanes=active_family_lanes,
                selected_tags=confirmed_tags,
            )
            selected_tag_debug = {
                "available_tags": [
                    row["label"]
                    for row in list_blueprint_tags(include_inactive=False)
                    if row["tag_id"] != "generalist"
                ],
                "tag_scores": derive_candidate_variant_tag_scores(
                    selected_candidate
                ),
                "automatic_tags": derive_candidate_variant_tags(
                    selected_candidate
                ),
                "confirmed_tags": confirmed_tags,
                "automatic_suggestion": automatic_suggestion,
                "confirmed_suggestion": confirmed_suggestion,
                "active_family_lane_projection": [
                    {
                        "blueprint_id": row.get("blueprint_id"),
                        "variant_id": row.get("variant_id"),
                        "variant_label": row.get("variant_label"),
                        "persisted_lane_tags": list(
                            row.get("persisted_tags") or []
                        ),
                        "legacy_inferred_lane_tags": variant_tags_from_label(
                            row.get("variant_label")
                        ),
                        "version_number": row.get("version_number"),
                        "lifecycle_status": row.get("status"),
                        "availability_status": row.get(
                            "availability_status"
                        ),
                    }
                    for row in active_family_lanes
                ],
            }

    selected_provenance: dict[str, Any] | None = None
    selected_provenance_error = ""
    selected_blueprint_audit_events: list[dict[str, Any]] = []
    if selected_blueprint is not None:
        selected_blueprint_audit_events = list_global_blueprint_audit_events(
            blueprint_id=_clean(selected_blueprint.get("blueprint_id"))
        )
        try:
            selected_provenance = load_blueprint_provenance_read_only(
                selected_blueprint
            )
        except (
            Phase9FBProvenanceError,
            OSError,
            ValueError,
            RuntimeError,
        ) as exc:
            selected_provenance_error = str(exc)

    show_history = bool(page_state.get("show_history"))
    inspection_rows = (
        blueprints
        if show_history
        else [row for row in blueprints if row.get("is_reusable")]
    )

    return {
        "debug_version": BLUEPRINT_LIBRARY_DEBUG_VERSION,
        "safety": {
            "read_only": True,
            "model_calls": False,
            "embedding_calls": False,
            "chroma_calls": False,
            "lifecycle_writes": False,
            "metadata_writes": False,
            "session_state_scope": (
                "Blueprint-Library-specific whitelist only; full Streamlit "
                "session state is intentionally not exported."
            ),
        },
        "page_state": dict(page_state),
        "current_application_id": current_application_id,
        "current_application_resume_result": (
            _safe_current_application_result(current_application_id)
        ),
        "counts": {
            "persisted_phase9c_evaluations": len(evaluations),
            "all_blueprint_versions": len(blueprints),
            "reusable_blueprints": len(reusable),
            "audit_events": len(audit_events),
            "inspection_rows": len(inspection_rows),
        },
        "display_projections": {
            "reusable_role_family_blueprints": [
                {
                    "role_family": row.get("role_family_label"),
                    "variant": row.get("variant_label", "Primary"),
                    "version": row.get("version_number"),
                    "display_name": row.get("display_name"),
                    "blueprint_id": row.get("blueprint_id"),
                    "activated_at": row.get("activated_at"),
                }
                for row in reusable
            ],
            "blueprint_inspection": [
                {
                    "role_family": row.get("role_family_label"),
                    "variant": row.get("variant_label", "Primary"),
                    "version": row.get("version_number"),
                    "lifecycle": row.get("status"),
                    "availability": row.get("availability_status"),
                    "blueprint_id": row.get("blueprint_id"),
                    "evaluation_id": row.get("evaluation_id"),
                    "activated_at": row.get("activated_at"),
                }
                for row in inspection_rows
            ],
        },
        "selected_evaluation": selected_evaluation,
        "selected_candidate": selected_candidate,
        "selected_variant_tag_debug": selected_tag_debug,
        "selected_blueprint": selected_blueprint,
        "selected_blueprint_audit_events": selected_blueprint_audit_events,
        "selected_blueprint_provenance": selected_provenance,
        "selected_blueprint_provenance_error": selected_provenance_error,
        "all_persisted_phase9c_evaluations": evaluations,
        "all_blueprint_versions": blueprints,
        "all_reusable_blueprints": reusable,
        "all_blueprint_audit_events": audit_events,
        "tag_library": list_blueprint_tags(include_inactive=True),
        "lane_tag_usage": list_blueprint_lane_tag_usage(),
    }


def blueprint_library_debug_json(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        default=str,
        sort_keys=True,
    )

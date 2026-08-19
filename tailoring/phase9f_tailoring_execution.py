"""Pure Phase 9F-F Minor/Full execution identities and scope policy.

This module deliberately performs no persistence, model, fitting, rendering,
embedding, or Chroma work.  It freezes the deterministic facts consumed by the
durable Phase 9F-F manager.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from tailoring.phase9a_evidence_opportunity import (
    PHASE9A_VERSION,
    build_evidence_opportunity_analysis,
)
from tailoring.phase9e_blueprint_selection import fingerprint_value
from tailoring.phase9f_application_execution import (
    Phase9FEExecutionError,
    validate_phase9f_d_execution_scope,
)


PHASE9F_F_VERSION = "phase9f-tailoring-execution-v1"
PHASE9F_F_IDENTITY_POLICY_VERSION = "phase9f-tailoring-execution-identity-v3"
PHASE9F_F_EVENT_VERSION = "phase9f-tailoring-execution-event-v1"
PHASE9F_F_STAGE_OUTPUT_POLICY_VERSION = "phase9f-f-stage-output-v2"
PHASE9F_F_SECTION_SCOPE_POLICY_VERSION = (
    "phase9f-f-addressable-section-scope-v1"
)
PHASE9F_F_EVIDENCE_SNAPSHOT_POLICY_VERSION = (
    "phase9f-f-frozen-evidence-snapshot-v2"
)
PHASE9F_F_FITTING_POLICY_VERSION = "phase9f-f-existing-fit-adapter-v2"
PHASE9F_F_GENERATION_SETTINGS_POLICY_VERSION = (
    "phase9f-f-generation-settings-stage-v1"
)
PHASE9F_F_FIT_SETTINGS_POLICY_VERSION = "phase9f-f-fit-settings-stage-v2"
PHASE9F_F_MODEL_BINDING_POLICY_VERSION = "phase9f-f-model-binding-stage-v1"
PHASE9F_F_SOURCE_ARTIFACT_POLICY_VERSION = (
    "phase9f-f-exact-source-artifact-v1"
)
PHASE9F_F_CONTENT_CHANGE_POLICY_VERSION = (
    "phase9f-f-visible-resume-content-change-v1"
)

VALID_INTENSITIES = {"minor", "full"}


class Phase9FFExecutionError(ValueError):
    """Fail-closed Phase 9F-F execution error."""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        stage: str = "source_preparation",
    ) -> None:
        super().__init__(message)
        self.code = str(code)
        self.stage = str(stage)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def _normalise_list(values: Any) -> list[str]:
    if isinstance(values, str):
        values = [values]
    return [_clean(value) for value in values or [] if _clean(value)]


def _evidence_row(item: dict[str, Any]) -> dict[str, Any]:
    row = {
        "id": int(item.get("id") or 0),
        "category": _clean(item.get("category")),
        "title": _clean(item.get("title")),
        "subtitle": _clean(item.get("subtitle")),
        "description": str(item.get("description") or "").replace("\r\n", "\n"),
        "period": _clean(item.get("period")),
        "skills": _normalise_list(item.get("skills")),
        "tools": _normalise_list(item.get("tools")),
        "resume_header_tools": _normalise_list(
            item.get("resume_header_tools")
        ),
        "resume_header_context": _normalise_list(
            item.get("resume_header_context")
        ),
        "impact": _clean(item.get("impact")),
        "source_type": _clean(item.get("source_type")),
        "created_at": _clean(item.get("created_at")),
        "updated_at": _clean(item.get("updated_at")),
    }
    if row["id"] <= 0 or not row["title"] or not _clean(row["description"]):
        raise Phase9FFExecutionError(
            "The Evidence Library contains an incomplete canonical row.",
            code="evidence_snapshot_row_incomplete",
        )
    row["content_fingerprint"] = fingerprint_value(row)
    return row


def build_frozen_evidence_snapshot(
    evidence_items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Freeze allowlisted mutable Evidence Library content for F retries."""
    rows = [_evidence_row(item) for item in evidence_items if isinstance(item, dict)]
    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise Phase9FFExecutionError(
            "The Evidence Library snapshot contains duplicate row IDs.",
            code="evidence_snapshot_duplicate_ids",
        )
    rows.sort(key=lambda row: (int(row["id"]), row["content_fingerprint"]))
    return {
        "policy_version": PHASE9F_F_EVIDENCE_SNAPSHOT_POLICY_VERSION,
        "rows": rows,
        "snapshot_fingerprint": fingerprint_value(
            {
                "policy_version": PHASE9F_F_EVIDENCE_SNAPSHOT_POLICY_VERSION,
                "rows": rows,
            }
        ),
    }


def validate_minor_full_execution_scope(
    *,
    application_id: int,
    confirmation: dict[str, Any],
    decision: dict[str, Any],
    exact_jd: dict[str, Any],
) -> dict[str, Any]:
    """Validate the common exact D scope and apply F-only intensity rules."""
    try:
        return validate_phase9f_d_execution_scope(
            application_id=application_id,
            confirmation=confirmation,
            decision=decision,
            exact_jd=exact_jd,
            allowed_intensities=VALID_INTENSITIES,
            intensity_error_code="confirmed_intensity_not_minor_or_full",
            intensity_error_message=(
                "Phase 9F-F executes only confirmed Minor or Full tailoring."
            ),
        )
    except Phase9FEExecutionError as exc:
        raise Phase9FFExecutionError(
            str(exc), code=exc.code, stage=exc.stage
        ) from exc


def _skills_fingerprint(profile: dict[str, Any]) -> str:
    return fingerprint_value({"skills": deepcopy(profile.get("skills") or {})})


def build_section_scope(
    *,
    application_id: int,
    baseline_report: dict[str, Any],
    evidence_snapshot: dict[str, Any],
    confirmed_intensity: str,
) -> dict[str, Any]:
    """Use Phase 9A's existing selection to choose truthful F sections."""
    intensity = _clean(confirmed_intensity).lower()
    if intensity not in VALID_INTENSITIES:
        raise Phase9FFExecutionError(
            "Phase 9F-F requires a confirmed Minor or Full intensity.",
            code="confirmed_intensity_invalid",
        )
    rows = deepcopy(evidence_snapshot.get("rows") or [])
    if not isinstance(baseline_report.get("resume_profile"), dict):
        raise Phase9FFExecutionError(
            "The exact D-bound résumé profile is unavailable.",
            code="baseline_profile_missing",
        )
    raw_jd = str(baseline_report.get("raw_jd_text") or "")
    if not _clean(raw_jd):
        raise Phase9FFExecutionError(
            "The exact D-bound job-description text is unavailable.",
            code="baseline_jd_text_missing",
        )

    # Minor preserves the existing bounded Phase 9A behavior. Full uses the
    # same selection algorithm with capacity for every frozen row, still
    # stopping at zero incremental canonical gain.
    max_projects = 3 if intensity == "minor" else max(1, len(rows))
    opportunity = build_evidence_opportunity_analysis(
        application_id=int(application_id),
        baseline_report=deepcopy(baseline_report),
        raw_jd_text=raw_jd,
        evidence_items=rows,
        max_projects=max_projects,
        max_bullets_per_project=2,
        max_skills=20,
    )
    selected = [
        row
        for row in opportunity.get("selected_evidence", []) or []
        if isinstance(row, dict) and float(row.get("incremental_points") or 0) > 0
    ]
    selected_ids = {
        int(row.get("evidence_item_id") or 0)
        for row in selected
        if int(row.get("evidence_item_id") or 0) > 0
    }
    selected_rows = [row for row in rows if int(row["id"]) in selected_ids]
    selected_rows.sort(key=lambda row: int(row["id"]))

    source_profile = baseline_report["resume_profile"]
    potential_profile = opportunity.get("opportunity_resume_profile") or {}
    skills_addressable = (
        _skills_fingerprint(source_profile) != _skills_fingerprint(potential_profile)
    )
    projects_addressable = bool(selected_rows)
    scope = {
        "policy_version": PHASE9F_F_SECTION_SCOPE_POLICY_VERSION,
        "phase9a_version": PHASE9A_VERSION,
        "confirmed_intensity": intensity,
        "opportunity_fingerprint": _clean(opportunity.get("opportunity_fingerprint")),
        "selected_evidence_ids": [int(row["id"]) for row in selected_rows],
        "selected_evidence_fingerprint": fingerprint_value(selected_rows),
        "projects_addressable": projects_addressable,
        "skills_addressable": skills_addressable,
        "enabled_sections": [
            section
            for section, enabled in (
                ("projects", projects_addressable),
                ("skills", skills_addressable),
            )
            if enabled
        ],
        "selected_evidence": selected_rows,
        "opportunity": opportunity,
    }
    scope["scope_fingerprint"] = fingerprint_value(
        {
            key: value
            for key, value in scope.items()
            if key not in {"opportunity", "selected_evidence"}
        }
    )
    return scope


def build_execution_identity(
    *,
    validated_scope: dict[str, Any],
    evidence_snapshot: dict[str, Any],
    section_scope: dict[str, Any],
    model_policy: dict[str, Any],
    source_artifact_identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the immutable F semantic execution identity."""
    return {
        "format_version": PHASE9F_F_VERSION,
        "identity_policy_version": PHASE9F_F_IDENTITY_POLICY_VERSION,
        "application_id": int(validated_scope["application_id"]),
        "phase9f_d": {
            "confirmation_id": validated_scope["confirmation_id"],
            "confirmation_fingerprint": validated_scope["confirmation_fingerprint"],
            "confirmation_content_fingerprint": validated_scope[
                "confirmation_content_fingerprint"
            ],
            "confirmed_intensity": validated_scope["confirmed_intensity"],
        },
        "phase9e_exact_binding": {
            "decision_id": validated_scope["phase9e_decision_id"],
            "decision_fingerprint": validated_scope["phase9e_decision_fingerprint"],
            "starting_snapshot_fingerprint": validated_scope[
                "starting_snapshot_fingerprint"
            ],
        },
        "source": deepcopy(validated_scope["source"]),
        "source_artifact": deepcopy(source_artifact_identity or {}),
        "exact_jd": deepcopy(validated_scope["exact_jd"]),
        "frozen_content": deepcopy(validated_scope["frozen_content"]),
        "evidence_snapshot": {
            "policy_version": evidence_snapshot["policy_version"],
            "snapshot_fingerprint": evidence_snapshot["snapshot_fingerprint"],
        },
        "section_scope": {
            "policy_version": section_scope["policy_version"],
            "phase9a_version": section_scope["phase9a_version"],
            "opportunity_fingerprint": section_scope["opportunity_fingerprint"],
            "scope_fingerprint": section_scope["scope_fingerprint"],
            "selected_evidence_fingerprint": section_scope[
                "selected_evidence_fingerprint"
            ],
            "enabled_sections": list(section_scope["enabled_sections"]),
        },
        "stage_output_policy_version": PHASE9F_F_STAGE_OUTPUT_POLICY_VERSION,
        "fitting_policy_version": PHASE9F_F_FITTING_POLICY_VERSION,
        "content_change_policy_version": PHASE9F_F_CONTENT_CHANGE_POLICY_VERSION,
        # The execution freezes the *contract* for later model binding, not a
        # model selected before the user expressly starts paid generation.
        # Each requested Projects/Skills stage persists its own model identity.
        "model_policy": deepcopy(model_policy),
        "execution_policy": {
            "content_changed": True,
            "editable": True,
            "tailorable_sections": ["projects", "skills"],
            "protected_sections": ["education", "work_experience"],
            "phase8_owner": "existing_phase8",
        },
    }


def prepare_execution(
    *,
    identity: dict[str, Any],
) -> dict[str, Any]:
    fingerprint = fingerprint_value(identity)
    return {
        "execution_id": fingerprint[:32],
        "execution_fingerprint": fingerprint,
        "execution_version": PHASE9F_F_VERSION,
        "identity_policy_version": PHASE9F_F_IDENTITY_POLICY_VERSION,
        "semantic_identity": deepcopy(identity),
    }


def has_durable_generation_settings_binding(execution: dict[str, Any]) -> bool:
    """Return whether F must keep normal Projects/Skills settings immutable.

    Initialising an F execution freezes the source, JD, evidence, and truthful
    section scope only.  The ordinary generation tuning remains editable until
    the user expressly begins the paid Projects/Skills stage.  A valid v3
    settings snapshot is the normal durable boundary.  Any legacy or corrupt
    row that records paid-stage activity without that snapshot remains locked
    fail-closed, rather than allowing a retry to change unknown prior inputs.
    """
    if not isinstance(execution, dict):
        return False
    outputs = execution.get("stage_outputs") or {}
    if not isinstance(outputs, dict):
        return False

    snapshot = outputs.get("generation_settings")
    if isinstance(snapshot, dict) and snapshot:
        return True

    paid_stage_statuses = {
        "requested",
        "running",
        "completed",
        "failed",
        "uncertain",
    }
    for stage_name in ("projects", "skills"):
        stage = outputs.get(stage_name)
        if (
            isinstance(stage, dict)
            and _clean(stage.get("status")).lower() in paid_stage_statuses
        ):
            return True
    return False


def generation_controls_are_locked(
    *,
    phase9f_execution_active: bool,
    workspace_edit_required: bool,
    projects_addressable: bool,
    phase9e_projects_locked: bool,
    update_scope_dirty: bool,
    generation_settings_durably_bound: bool,
) -> bool:
    """Resolve normal Projects/Skills tuning ownership without writing state.

    Legacy Application Session controls obey their saved section lock.  An
    active F execution replaces that legacy scope with its own frozen truth
    scope: if Projects are addressable, tuning stays editable until a durable
    paid-stage settings/request binding exists.  This avoids treating F
    initialization itself as a paid-stage request.
    """
    if workspace_edit_required or update_scope_dirty:
        return True
    if phase9f_execution_active:
        return not projects_addressable or generation_settings_durably_bound
    return not projects_addressable or phase9e_projects_locked


def build_execution_debug_summary(execution: dict[str, Any]) -> dict[str, Any]:
    """Return an allowlisted, read-only F settings/provenance debug summary.

    This deliberately omits source artifacts, frozen evidence rows, prompts,
    resume text, and provider payloads.  It exists so normal Application
    Session diagnostics can show the settings that actually governed each
    stage without exposing private source content.
    """
    outputs = execution.get("stage_outputs") or {}
    generation_snapshot = outputs.get("generation_settings") or {}
    fitting = outputs.get("fitting") or {}
    fit_attempts = outputs.get("fitting_attempts") or []

    def stage_summary(name: str) -> dict[str, Any]:
        stage = outputs.get(name) or {}
        return {
            "status": _clean(stage.get("status")),
            "input_fingerprint": _clean(stage.get("input_fingerprint")),
            "generation_settings_fingerprint": _clean(
                stage.get("generation_settings_fingerprint")
            ),
            "model": _clean(stage.get("model")),
            "model_policy_version": _clean(stage.get("model_policy_version")),
            "result_fingerprint": _clean(stage.get("result_fingerprint")),
        }

    fit_snapshot = fitting.get("fit_settings") or {}
    return {
        "execution_id": _clean(execution.get("execution_id")),
        "execution_fingerprint": _clean(execution.get("execution_fingerprint")),
        "identity_policy_version": _clean(execution.get("identity_policy_version")),
        "status": _clean(execution.get("status")),
        "current_stage": _clean(execution.get("current_stage")),
        "frozen_truth_scope": {
            "confirmed_intensity": _clean(execution.get("confirmed_intensity")),
            "section_scope_fingerprint": _clean(
                execution.get("section_scope_fingerprint")
            ),
            "enabled_sections": list(
                (execution.get("section_scope") or {}).get("enabled_sections") or []
            ),
        },
        "generation_settings": {
            "status": _clean(generation_snapshot.get("status")),
            "settings": deepcopy(generation_snapshot.get("settings") or {}),
            "settings_fingerprint": _clean(
                generation_snapshot.get("settings_fingerprint")
            ),
            "model": _clean(generation_snapshot.get("model")),
            "editable": generation_snapshot.get("status") != "frozen",
            "frozen_reason": _clean(generation_snapshot.get("frozen_reason")),
        },
        "projects_stage": stage_summary("projects"),
        "skills_stage": stage_summary("skills"),
        "fitting": {
            "status": _clean(fitting.get("status")),
            "input_fingerprint": _clean(fitting.get("input_fingerprint")),
            "fit_settings": deepcopy(fit_snapshot.get("settings") or {}),
            "fit_settings_fingerprint": _clean(
                fit_snapshot.get("settings_fingerprint")
            ),
            "successful_fit_settings_fingerprint": (
                _clean(fit_snapshot.get("settings_fingerprint"))
                if fitting.get("status") == "completed"
                else ""
            ),
            "effective_max_projects": fit_snapshot.get("effective_max_projects"),
            "effective_max_bullets_per_project": fit_snapshot.get(
                "effective_max_bullets_per_project"
            ),
            "effective_bullet_allocation_mode": _clean(
                fit_snapshot.get("effective_bullet_allocation_mode")
            ),
            "editable": fitting.get("status") != "completed",
            "frozen_reason": _clean(fit_snapshot.get("frozen_reason")),
            "attempt_count": len(fit_attempts) if isinstance(fit_attempts, list) else 0,
        },
    }

"""Phase 9E.1 state-aware application workflow overview UI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from database.application_blueprint_manager import (
    get_current_application_blueprint_decision,
)
from database.application_resume_result_manager import (
    get_current_application_resume_result,
)
from database.db_manager import get_application_by_id
from database.jd_library_manager import (
    get_exact_job_description_for_application,
)
from database.tailoring_generation_control import (
    get_application_generation_control,
)
from database.tailoring_verification_manager import (
    get_latest_tailoring_verification,
)
from tailoring.phase9e_application_result import (
    STATUS_REUSED_APPROVED,
    STATUS_REUSED_UNCHANGED_PENDING,
)
from tailoring.phase9e1_resume_workspace_ui import (
    render_resume_workspace,
)
from tailoring.phase9e_blueprint_selection import DECISION_LABELS


PHASE9E1_WORKFLOW_UI_VERSION = "phase9e1-application-workflow-ui-v4"


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _first(*values: Any, fallback: str = "") -> str:
    for value in values:
        cleaned = _clean(value)
        if cleaned:
            return cleaned
    return fallback


def _page_label(generation: dict[str, Any]) -> str:
    fit_result = generation.get("fit_result") or {}
    page_count = fit_result.get("page_count")
    if page_count in (None, ""):
        return "Fit unavailable"
    try:
        pages = int(page_count)
    except (TypeError, ValueError):
        return f"{page_count} pages"
    return "1 page" if pages == 1 else f"{pages} pages"


def _decision_source_label(
    decision: dict[str, Any],
) -> tuple[str, str]:
    selection = decision.get("selection") or {}
    blueprint = selection.get("selected_blueprint") or {}
    selected_source = _clean(selection.get("selected_source"))

    if selected_source == "global_blueprint":
        label = _first(
            selection.get("selected_blueprint_display_name"),
            blueprint.get("display_name"),
            blueprint.get("role_family_label"),
            fallback="Global Blueprint",
        )
        version = int(blueprint.get("version_number", 0) or 0)
        return label, f"Global Blueprint v{version}"

    if selected_source == "original_resume":
        fidelity = _clean(
            (decision.get("starting_snapshot") or {}).get(
                "source_fidelity"
            )
        )
        detail = (
            "Persisted structured profile; original raw text unavailable"
            if fidelity == "persisted_profile_only"
            else "Application résumé snapshot"
        )
        return "Original résumé", detail

    return "Not selected", "Choose a starting résumé"


def build_application_workflow_overview(
    *,
    application_id: int,
    application_record: dict[str, Any] | None,
    baseline_report: dict[str, Any] | None,
    exact_jd: dict[str, Any] | None,
    current_decision: dict[str, Any] | None,
    current_result: dict[str, Any] | None,
    legacy_approved_generation: dict[str, Any] | None = None,
    legacy_verification: dict[str, Any] | None = None,
    load_error: str = "",
) -> dict[str, Any]:
    """Build a read-only, state-aware application workflow summary."""
    application = application_record or {}
    report = baseline_report or {}
    jd = exact_jd or {}
    decision = current_decision or {}
    result = current_result or {}
    legacy_generation = legacy_approved_generation or {}
    verification = legacy_verification or {}

    selection = decision.get("selection") or {}
    blueprint = selection.get("selected_blueprint") or {}
    semantic = decision.get("semantic_identity") or {}
    classification = semantic.get("role_family_classification") or {}
    jd_profile = jd.get("jd_profile") or report.get("jd_profile") or {}

    activation = _clean(decision.get("scope_activation_status"))
    scope = _clean(decision.get("current_scope_status"))
    phase9e_active = activation == "active" and scope == "current"
    phase9e_pending = bool(decision) and not phase9e_active
    proposed_source, proposed_source_detail = _decision_source_label(
        decision
    )

    initial_status = _clean(result.get("initial_status"))
    result_state = result.get("state") or {}
    has_immutable_result = initial_status in {
        STATUS_REUSED_APPROVED,
        STATUS_REUSED_UNCHANGED_PENDING,
    }
    has_legacy_approved = bool(
        legacy_generation
        and _clean(legacy_generation.get("status")) == "approved"
    )

    current_phase9e_fingerprint = _clean(
        decision.get("decision_fingerprint")
    )
    approved_phase9e_fingerprint = _clean(
        legacy_generation.get("phase9e_decision_fingerprint")
    )
    previous_scope_approved = bool(
        phase9e_active
        and has_legacy_approved
        and current_phase9e_fingerprint
        and approved_phase9e_fingerprint
        and approved_phase9e_fingerprint != current_phase9e_fingerprint
    )

    if phase9e_active:
        source_label = proposed_source
        source_detail = proposed_source_detail
    elif has_legacy_approved:
        source_label = "Legacy approved résumé"
        source_detail = (
            f"Approved generation "
            f"{_clean(legacy_generation.get('generation_id'))[:12]}"
        )
    elif phase9e_pending:
        source_label = "Legacy generation scope"
        source_detail = (
            f"Proposed Phase 9E source: {proposed_source}"
        )
    else:
        source_label = "Not selected"
        source_detail = "Choose a starting résumé"

    if initial_status == STATUS_REUSED_APPROVED:
        workflow_mode = "Phase 9E immutable reuse"
        result_label = "Reused approved blueprint"
        phase9e_status = "Active"
        next_action = (
            "Review or download the immutable résumé result. Create an "
            "editable copy only when content must change."
        )
    elif initial_status == STATUS_REUSED_UNCHANGED_PENDING:
        workflow_mode = "Phase 9E unchanged reuse"
        result_label = "Reuse pending application verification"
        phase9e_status = "Active"
        if not _clean(result_state.get("current_verification_id")):
            next_action = (
                "Run deterministic current-JD verification for the "
                "unchanged application result."
            )
        else:
            next_action = (
                "Review the verification and explicitly accept the "
                "unchanged résumé for this application."
            )
    elif previous_scope_approved:
        workflow_mode = "Phase 9E tailored workflow"
        result_label = (
            f"Approved · {_page_label(legacy_generation)} · "
            "Previous Tailoring Base"
        )
        phase9e_status = "Active · replacement not started"
        next_action = (
            "Keep the existing approved application result as-is, or "
            "Start a new résumé from the current Tailoring Base. The old "
            "Phase 8 / Blueprint lineage remains preserved as history."
        )
    elif phase9e_active and has_legacy_approved:
        workflow_mode = "Phase 9E tailored workflow"
        verified = bool(verification)
        verification_label = (
            "Phase 8 verified" if verified else "verification pending"
        )
        result_label = (
            f"Approved · {_page_label(legacy_generation)} · "
            f"{verification_label}"
        )
        phase9e_status = "Active"
        next_action = (
            "Review or download the approved résumé, continue the "
            "current working draft, or advance the Blueprint Lifecycle."
        )
    elif has_legacy_approved:
        workflow_mode = "Legacy approved workflow"
        verified = bool(verification)
        verification_label = (
            "Phase 8 verified" if verified else "verification pending"
        )
        result_label = (
            f"Approved · {_page_label(legacy_generation)} · "
            f"{verification_label}"
        )
        phase9e_status = (
            "Waiting for confirmation"
            if phase9e_pending
            else "Optional — not selected"
        )
        if phase9e_pending:
            next_action = (
                "Review or download the current approved résumé, or "
                "confirm the proposed Phase 9E source to replace its scope."
            )
        else:
            next_action = (
                "Review or download the approved résumé. Phase 9E "
                "migration is optional."
            )
    elif scope == "stale":
        workflow_mode = "Phase 9E source stale"
        result_label = "Starting source is stale"
        phase9e_status = "Stale"
        next_action = (
            "Re-evaluate and bind a current starting résumé before "
            "continuing."
        )
    elif activation == "pending_confirmation" or phase9e_pending:
        workflow_mode = "Legacy workflow with proposed Phase 9E source"
        result_label = "No current approved résumé result"
        phase9e_status = "Waiting for confirmation"
        next_action = "Confirm the proposed starting-source change."
    elif phase9e_active:
        workflow_mode = "Phase 9E source bound"
        result_label = "Starting source bound"
        phase9e_status = "Active"
        decision_name = _clean(
            decision.get("recommended_tailoring")
        )
        decision_label = _first(
            decision.get("recommended_tailoring_label"),
            DECISION_LABELS.get(decision_name),
            decision_name.replace("_", " ").title(),
            fallback="selected workflow",
        )
        next_action = f"Choose how to continue: {decision_label}."
    else:
        workflow_mode = "Unbound application workflow"
        result_label = "No current application result"
        phase9e_status = "Not selected"
        next_action = "Choose and confirm a starting résumé."

    return {
        "ui_version": PHASE9E1_WORKFLOW_UI_VERSION,
        "application_id": int(application_id),
        "session_name": _first(
            application.get("session_name"),
            fallback=f"Application #{application_id}",
        ),
        "job_title": _first(
            application.get("job_title"),
            jd.get("title"),
            jd_profile.get("job_title"),
            fallback="Untitled role",
        ),
        "company": _first(
            application.get("company"),
            jd.get("company"),
            jd_profile.get("company"),
            fallback="Unknown company",
        ),
        "source_version_id": _clean(jd.get("source_version_id")),
        "role_family": _first(
            classification.get("role_family_label"),
            blueprint.get("role_family_label"),
            fallback="Not classified",
        ),
        "role_family_confidence": _first(
            classification.get("confidence"),
            classification.get("confidence_label"),
        ),
        "workflow_mode": workflow_mode,
        "current_source": source_label,
        "current_source_detail": source_detail,
        "proposed_source": (
            proposed_source if phase9e_pending else ""
        ),
        "proposed_source_detail": (
            proposed_source_detail if phase9e_pending else ""
        ),
        "current_result": result_label,
        "phase9e_status": phase9e_status,
        "next_action": next_action,
        "decision_id": _clean(decision.get("decision_id")),
        "decision_fingerprint": _clean(
            decision.get("decision_fingerprint")
        ),
        "application_result_id": _clean(
            result.get("application_result_id")
        ),
        "application_result_fingerprint": _clean(
            result.get("result_fingerprint")
        ),
        "legacy_generation_id": _clean(
            legacy_generation.get("generation_id")
        ),
        "legacy_verification_id": _clean(
            verification.get("verification_id")
        ),
        "has_immutable_result": has_immutable_result,
        "previous_scope_approved": previous_scope_approved,
        "has_legacy_approved_result": has_legacy_approved,
        "load_error": _clean(load_error),
    }


def _load_state(
    application_id: int,
) -> tuple[
    dict[str, Any] | None,
    dict[str, Any] | None,
    dict[str, Any] | None,
    dict[str, Any] | None,
    list[str],
]:
    errors: list[str] = []
    decision = None
    result = None
    approved = None
    verification = None

    try:
        decision = get_current_application_blueprint_decision(
            application_id
        )
    except (ValueError, RuntimeError) as exc:
        errors.append(str(exc))

    try:
        result = get_current_application_resume_result(
            application_id,
            validate_artifacts=False,
        )
    except (ValueError, RuntimeError) as exc:
        errors.append(str(exc))

    try:
        control = get_application_generation_control(application_id)
        candidate = control.get("approved_generation")
        if isinstance(candidate, dict):
            approved = candidate
            generation_id = _clean(candidate.get("generation_id"))
            if generation_id:
                verification = get_latest_tailoring_verification(
                    application_id,
                    generation_id,
                )
    except (ValueError, RuntimeError) as exc:
        errors.append(str(exc))

    return decision, result, approved, verification, errors


def render_application_workflow_overview(
    *,
    application_id: int,
    baseline_report: dict[str, Any],
) -> dict[str, Any]:
    decision, result, approved, verification, errors = _load_state(
        application_id
    )
    from tailoring.phase9e1_resume_workspace_ui import (
        get_resume_workspace_context,
    )

    overview = build_application_workflow_overview(
        application_id=application_id,
        application_record=get_application_by_id(application_id) or {},
        baseline_report=baseline_report,
        exact_jd=(
            get_exact_job_description_for_application(application_id)
            or {}
        ),
        current_decision=decision,
        current_result=result,
        legacy_approved_generation=approved,
        legacy_verification=verification,
        load_error=" ".join(errors),
    )

    workspace_state = get_resume_workspace_context(
        int(application_id)
    )
    working_generation = (
        workspace_state.get("loaded_generation")
        if workspace_state.get("loaded_mode") == "working_draft"
        else None
    )
    if isinstance(working_generation, dict):
        working_id = _clean(working_generation.get("generation_id"))
        working_pages = _page_label(working_generation)
        fit_result = working_generation.get("fit_result") or {}
        page_count_raw = fit_result.get("page_count")
        try:
            working_page_count = (
                int(page_count_raw)
                if page_count_raw not in (None, "")
                else None
            )
        except (TypeError, ValueError):
            working_page_count = None

        overview = dict(overview)

        if working_page_count == 1:
            overview["current_result"] = (
                f"Working draft {working_id[:8]} · {working_pages} · "
                "approval + Phase 8 required"
            )
            overview["next_action"] = (
                "Review and approve fitted working draft "
                f"{working_id[:8]}. After approval, run Phase 8 "
                "verification before advancing the Blueprint Lifecycle."
            )
        elif working_page_count is not None:
            overview["current_result"] = (
                f"Working draft {working_id[:8]} · {working_pages} · "
                "one-page fit + approval + Phase 8 required"
            )
            overview["next_action"] = (
                "Continue fitting working draft "
                f"{working_id[:8]} to one page, then approve it and run "
                "Phase 8 verification."
            )
        else:
            overview["current_result"] = (
                f"Working draft {working_id[:8]} · {working_pages} · "
                "fit + approval + Phase 8 required"
            )
            overview["next_action"] = (
                "Finish editing and build/fit working draft "
                f"{working_id[:8]}, then approve it and run Phase 8 "
                "verification."
            )

    st.subheader("Application workflow")
    with st.container(border=True):
        st.write(
            f"### {overview['job_title']} @ {overview['company']}"
        )
        st.caption(
            f"{overview['session_name']} · Application "
            f"#{application_id}"
        )

        left, right = st.columns(2)
        with left:
            st.caption("Current workflow")
            st.write(f"**{overview['workflow_mode']}**")
            st.caption("Current résumé result")
            st.write(f"**{overview['current_result']}**")
        with right:
            st.caption("Current starting source")
            st.write(f"**{overview['current_source']}**")
            st.caption(overview["current_source_detail"])
            st.caption("Phase 9E status")
            st.write(f"**{overview['phase9e_status']}**")

        st.caption(
            f"Role family: {overview['role_family']}"
            + (
                f" · confidence "
                f"{overview['role_family_confidence']}"
                if overview["role_family_confidence"]
                else ""
            )
            + (
                f" · JD {overview['source_version_id'][:12]}"
                if overview["source_version_id"]
                else ""
            )
        )

        if overview["proposed_source"]:
            st.info(
                "**Proposed Phase 9E source:** "
                f"{overview['proposed_source']} — "
                f"{overview['proposed_source_detail']}"
            )

        st.info(
            "**Next recommended action:** "
            f"{overview['next_action']}"
        )
        if overview["load_error"]:
            st.warning(
                "Some workflow status could not be loaded: "
                f"{overview['load_error']}"
            )
        with st.expander(
            "Application workflow technical details",
            expanded=False,
        ):
            st.json(overview)
    return overview


def _artifact_path(
    generation: dict[str, Any],
    field: str,
) -> Path | None:
    value = generation.get(field)
    if not value:
        return None
    path = Path(value)
    return path if path.is_file() else None


def render_current_legacy_resume_result(
    *,
    application_id: int,
) -> bool:
    """Render the approved legacy output before optional Phase 9E migration."""
    try:
        current_result = get_current_application_resume_result(
            application_id,
            validate_artifacts=False,
        )
        if isinstance(current_result, dict):
            state = current_result.get("state") or {}
            if state.get("active_output_mode") == "immutable_result":
                return False

        control = get_application_generation_control(application_id)
        approved = control.get("approved_generation")
        if not isinstance(approved, dict):
            return False

        generation_id = _clean(approved.get("generation_id"))
        verification = (
            get_latest_tailoring_verification(
                application_id,
                generation_id,
            )
            if generation_id
            else None
        )
    except (ValueError, RuntimeError):
        return False

    st.subheader("Current Résumé Result")
    with st.container(border=True):
        current_decision = (
            get_current_application_blueprint_decision(application_id)
            or {}
        )
        active_phase9e = bool(
            _clean(current_decision.get("scope_activation_status"))
            == "active"
            and _clean(current_decision.get("current_scope_status"))
            == "current"
        )
        current_phase9e_fingerprint = _clean(
            current_decision.get("decision_fingerprint")
        )
        approved_phase9e_fingerprint = _clean(
            approved.get("phase9e_decision_fingerprint")
        )
        previous_scope_approved = bool(
            active_phase9e
            and current_phase9e_fingerprint
            and approved_phase9e_fingerprint
            and approved_phase9e_fingerprint != current_phase9e_fingerprint
        )
        if previous_scope_approved:
            st.warning(
                "This is still the approved application result, but it belongs to a previous Tailoring Base."
            )
        elif active_phase9e:
            st.success(
                "This approved résumé is the current Phase 9E "
                "application output."
            )
        else:
            st.success(
                "This approved legacy résumé remains the current "
                "application output. Phase 9E migration is optional."
            )
        status_col, fit_col, verification_col = st.columns(3)
        status_col.metric("Status", "Approved")
        fit_col.metric("Fit", _page_label(approved))
        verification_col.metric(
            "Phase 8",
            (
                "Previously verified"
                if previous_scope_approved and verification
                else "Verified"
                if verification
                else "Pending"
            ),
        )

        docx_path = _artifact_path(approved, "docx_path")
        pdf_path = _artifact_path(approved, "pdf_path")
        if docx_path or pdf_path:
            download_columns = st.columns(2)
            if docx_path:
                download_columns[0].download_button(
                    "Download approved résumé DOCX",
                    data=docx_path.read_bytes(),
                    file_name=docx_path.name,
                    mime=(
                        "application/vnd.openxmlformats-officedocument."
                        "wordprocessingml.document"
                    ),
                    key=(
                        "phase9e1_legacy_result_docx_"
                        f"{application_id}_{generation_id}"
                    ),
                    width="stretch",
                )
            if pdf_path:
                download_columns[1].download_button(
                    "Download approved résumé PDF",
                    data=pdf_path.read_bytes(),
                    file_name=pdf_path.name,
                    mime="application/pdf",
                    key=(
                        "phase9e1_legacy_result_pdf_"
                        f"{application_id}_{generation_id}"
                    ),
                    width="stretch",
                )
        else:
            st.caption(
                "The approved content is persisted, but no current DOCX/PDF "
                "artifact path is available for a top-level download."
            )

        if previous_scope_approved:
            st.caption(
                "Current-scope tailoring and fitting stay blocked until you "
                "start a new résumé from the current Tailoring Base. The "
                "existing approval and its earlier Phase 8 / Blueprint lineage "
                "remain preserved."
            )
        else:
            st.caption(
                "Tailoring, fitting, approval, and detailed verification "
                "controls remain available below."
            )
        with st.expander(
            "Current résumé result technical details",
            expanded=False,
        ):
            st.json(
                {
                    "generation_id": generation_id,
                    "status": approved.get("status"),
                    "fit_result": approved.get("fit_result") or {},
                    "verification_id": (
                        (verification or {}).get("verification_id")
                    ),
                    "blueprint_ready": (
                        (verification or {}).get("blueprint_ready")
                    ),
                    "lock_projects": control.get("lock_projects"),
                    "lock_skills": control.get("lock_skills"),
                }
            )
    render_resume_workspace(
        application_id=application_id,
    )
    return True

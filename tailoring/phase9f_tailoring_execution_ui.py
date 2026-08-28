"""Minimal Phase 9F-F setup surface for the normal Application Session flow."""

from __future__ import annotations

from typing import Any

import streamlit as st

from database.phase9f_tailoring_execution_manager import (
    get_phase9f_tailoring_execution,
    prepare_or_reuse_phase9f_tailoring_execution,
)


PHASE9F_F_UI_VERSION = "phase9f-tailoring-execution-ui-v2"


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _short_identifier(value: Any) -> str:
    identifier = _clean(value)
    return identifier[:12] if identifier else "—"


def render_phase9f_tailoring_execution_status(
    *, application_id: int
) -> dict[str, Any] | None:
    """Render the allowlisted, read-only Phase 9F-F ledger status."""
    execution = get_phase9f_tailoring_execution(int(application_id))
    st.subheader("Phase 9F-F execution")
    if execution is None:
        st.info("No Phase 9F-F execution record exists for this application.")
        return None

    status_value = _clean(execution.get("status"))
    stage_value = _clean(execution.get("current_stage"))
    status_column, stage_column, attempt_column, generation_column = st.columns(4)
    status_column.metric("Status", status_value or "Unknown")
    stage_column.metric("Stage", stage_value or "Unknown")
    attempt_column.metric("Attempt", str(execution.get("attempt_count") or 0))
    generation_column.metric(
        "Generation",
        _short_identifier(execution.get("generation_id")),
    )
    st.caption(
        "Execution "
        f"{_short_identifier(execution.get('execution_id'))} · "
        f"Intensity {_clean(execution.get('confirmed_intensity')).title() or 'Unknown'} · "
        f"Updated {_clean(execution.get('updated_at')) or 'Unavailable'}"
    )

    completed_at = _clean(execution.get("completed_at"))
    if completed_at:
        st.caption(f"Completed {completed_at}")

    recovery_state = _clean(execution.get("recovery_state"))
    uncertain_stage = _clean(execution.get("uncertain_stage"))
    if recovery_state == "model_attempt_uncertain":
        st.warning(
            "Recovery state: model attempt uncertain"
            f"{f' at {uncertain_stage}' if uncertain_stage else ''}. "
            "A prior paid model response was not proven durable."
        )
    elif recovery_state:
        st.caption(f"Recovery state: {recovery_state}")

    error_code = _clean(execution.get("last_error_code"))
    error_message = _clean(execution.get("last_error_message"))
    if status_value == "failed" or error_code or error_message:
        error_details = " · ".join(
            value for value in (error_code, error_message) if value
        )
        st.error(
            "Persisted execution error"
            f"{f' at {stage_value}' if stage_value else ''}"
            f": {error_details or 'No error details were persisted.'}"
        )
    return execution


def render_phase9f_tailoring_execution(
    *, application_id: int, phase9e_context: dict[str, Any]
) -> None:
    """Initialize F only; all later work uses normal Application Session stages."""
    intensity = _clean(phase9e_context.get("confirmed_intensity")).lower()
    if intensity not in {"minor", "full"}:
        return
    label = intensity.title()
    st.divider()
    execution = render_phase9f_tailoring_execution_status(
        application_id=int(application_id)
    )
    st.subheader("Tailoring Base")
    st.caption(
        "The exact Phase 9F-D source and JD are bound. Initialization freezes "
        "the truthful Minor/Full scope; Projects & Skills, Build/Fit, Preview, "
        "Approval, and Phase 8 remain the normal Application Session stages."
    )
    if execution is None:
        st.info(
            f"{label} tailoring is confirmed. Initialize its deterministic "
            "scope before continuing through the Application Session workflow."
        )
        if st.button(
            f"Begin {label} tailoring",
            type="primary",
            width="stretch",
            key=f"phase9f_f_prepare_{application_id}",
        ):
            try:
                prepared = prepare_or_reuse_phase9f_tailoring_execution(
                    application_id=int(application_id)
                )["execution"]
                if prepared.get("status") == "blocked":
                    st.warning(
                        "No truthful Projects or Skills change is addressable. "
                        "No model call, fit, or draft was created."
                    )
                st.rerun()
            except (ValueError, RuntimeError) as exc:
                st.error(str(exc))
        return

    if execution.get("status") == "blocked":
        st.warning(
            "No truthful Projects or Skills change is addressable. Return "
            "through Phase 9F confirmation to choose another source or intensity."
        )
        return
    if execution.get("recovery_state") == "model_attempt_uncertain":
        st.error(
            "A prior paid model attempt was not proven durable. Continue to "
            "the normal Projects & Skills stage and explicitly acknowledge any "
            "retry there; initialization will not repeat it."
        )
        return
    st.success(
        "Tailoring is initialized. Continue through Tailoring Opportunities "
        "and the normal Projects & Skills stage."
    )

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


def render_phase9f_tailoring_execution(
    *, application_id: int, phase9e_context: dict[str, Any]
) -> None:
    """Initialize F only; all later work uses normal Application Session stages."""
    intensity = _clean(phase9e_context.get("confirmed_intensity")).lower()
    if intensity not in {"minor", "full"}:
        return
    label = intensity.title()
    execution = get_phase9f_tailoring_execution(int(application_id))
    st.divider()
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

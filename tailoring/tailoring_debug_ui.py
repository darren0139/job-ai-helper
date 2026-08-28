"""Lazy technical-debug controls for the Tailor Resume surface."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

import streamlit as st


DebugBundleBuilder = Callable[..., tuple[bytes, str]]


def _prepared_bundle_key(application_id: int | None) -> str:
    app_label = str(application_id) if application_id is not None else "unsaved"
    return f"tailor_resume_full_debug_bundle_{app_label}"


def render_lazy_full_debug_bundle(
    *,
    application_id: int | None,
    has_debug_content: bool,
    create_full_debug_bundle: DebugBundleBuilder,
    bundle_kwargs: dict[str, Any],
) -> None:
    """Prepare the complete debug export only after an explicit request."""
    if not has_debug_content:
        return

    state_key = _prepared_bundle_key(application_id)
    prepared = st.session_state.get(state_key)
    has_prepared_bundle = isinstance(prepared, dict) and isinstance(
        prepared.get("bytes"), bytes
    )
    action_label = (
        "Refresh Full Debug Bundle"
        if has_prepared_bundle
        else "Prepare Full Debug Bundle"
    )
    if st.button(action_label, width="stretch", key=f"{state_key}_prepare"):
        debug_bytes, debug_filename = create_full_debug_bundle(**bundle_kwargs)
        prepared = {
            "bytes": debug_bytes,
            "filename": debug_filename,
            "prepared_at": datetime.now().isoformat(timespec="seconds"),
        }
        st.session_state[state_key] = prepared
        has_prepared_bundle = True

    if not has_prepared_bundle:
        return
    if not isinstance(prepared, dict):
        return
    debug_bytes = prepared.get("bytes")
    debug_filename = str(prepared.get("filename") or "debug_bundle.json")
    prepared_at = str(prepared.get("prepared_at") or "Unavailable")
    if not isinstance(debug_bytes, bytes):
        return
    st.caption(
        "Full Debug Bundle prepared "
        f"{prepared_at}. This is a saved snapshot, not live state."
    )
    st.download_button(
        "Download Full Debug Bundle JSON",
        data=debug_bytes,
        file_name=debug_filename,
        mime="application/json",
        width="stretch",
        key=f"{state_key}_download",
    )


def render_lazy_fitting_debug(
    *, application_id: int | None, fit_result: dict[str, Any] | None
) -> None:
    """Render large fitting payloads only after an explicit opt-in."""
    if not isinstance(fit_result, dict):
        return
    app_label = str(application_id) if application_id is not None else "unsaved"
    show_technical_debug = st.checkbox(
        "Show technical fitting debug",
        value=False,
        key=f"tailor_resume_technical_fitting_debug_{app_label}",
    )
    if not show_technical_debug:
        return

    with st.expander("One-page fitting attempts"):
        st.json(fit_result.get("attempts", []) or [])

    with st.expander("Debug: Final projects used in DOCX"):
        final_projects_used = fit_result.get("tailored_projects_used")
        if not isinstance(final_projects_used, dict):
            final_projects_used = {}
        st.json(final_projects_used.get("recommended_projects", []) or [])

    with st.expander("Debug: Final skills used in DOCX"):
        final_skills_used = fit_result.get("tailored_skills_used")
        if not isinstance(final_skills_used, dict):
            final_skills_used = {}
        st.json(final_skills_used.get("skill_lines", []) or [])

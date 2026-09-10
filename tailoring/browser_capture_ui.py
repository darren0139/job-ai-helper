"""Streamlit display and handoff controls for browser JD captures."""

from __future__ import annotations

import streamlit as st

from browser_integration.streamlit_runtime import (
    ensure_streamlit_browser_bridge,
    rotate_streamlit_browser_bridge_token,
)
from browser_integration.tailor_resume_handoff import (
    apply_browser_capture_tailor_resume_handoff,
)
from database.browser_capture_manager import list_browser_job_captures


def _capture_label(item: dict) -> str:
    title = str(item.get("job_title") or "Untitled job").strip()
    company = str(item.get("company") or "Unknown company").strip()
    return f"#{item.get('id')} — {title} — {company}"


def _render_browser_bridge_status() -> None:
    st.subheader("Browser Integration")
    resource = ensure_streamlit_browser_bridge()

    if not resource.running or resource.runtime is None:
        st.error(resource.error or "Local browser bridge is not running.")
        st.caption(
            "If port 8765 is already occupied by the old manual bridge, stop "
            "that terminal process and restart Streamlit."
        )
        return

    runtime = resource.runtime
    st.success("Local browser bridge is running automatically.")
    status_col, address_col = st.columns(2)
    status_col.write("**Status:** running")
    address_col.write(f"**Bridge:** {runtime.url}")

    with st.expander("Extension pairing", expanded=False):
        st.caption(
            "Pair once by copying this local token into the Chrome extension. "
            "The token remains stable across Streamlit restarts."
        )
        st.code(runtime.token)
        st.warning(
            "Regenerating the token disconnects the currently paired extension "
            "until the new token is pasted into it."
        )
        if st.button(
            "Regenerate pairing token",
            key="browser_bridge_rotate_pairing_token",
        ):
            try:
                rotate_streamlit_browser_bridge_token()
            except Exception as exc:
                st.error(f"Could not regenerate the pairing token: {exc}")
            else:
                st.success("Pairing token regenerated.")
                st.rerun()


def render_browser_capture_inbox() -> None:
    _render_browser_bridge_status()

    st.subheader("Browser JD Capture Inbox")
    st.caption(
        "JD text captured by the local browser extension. These entries are "
        "pending browser source artifacts until you analyse them through the "
        "existing Tailor Resume JD workflow."
    )

    captures = list_browser_job_captures(limit=20, status="pending")
    if not captures:
        st.info(
            "No browser JD captures yet. Extract a job page with the Chrome "
            "extension, then choose 'Save JD to Job AI Helper'."
        )
        return

    by_id = {int(item["id"]): item for item in captures}
    selected_id = st.selectbox(
        "Captured job",
        options=list(by_id),
        format_func=lambda capture_id: _capture_label(by_id[capture_id]),
        key="browser_jd_capture_inbox_selection",
    )
    item = by_id[int(selected_id)]

    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Status:** {item.get('status') or 'pending'}")
        st.write(
            f"**Extraction:** {item.get('extraction_strategy') or 'unknown'}"
        )
    with col2:
        st.write(
            f"**Captured:** {item.get('captured_at') or item.get('last_received_at') or ''}"
        )
        st.write(
            f"**Site adapter:** {item.get('site_adapter') or 'generic'}"
        )

    source_url = str(item.get("source_url") or "").strip()
    if source_url:
        st.write(f"**Source URL:** {source_url}")

    st.text_area(
        "Clean JD text",
        value=str(item.get("jd_text") or ""),
        height=340,
        key=f"browser_jd_clean_text_{selected_id}",
        disabled=True,
    )

    st.button(
        "Use in Tailor Resume",
        type="primary",
        width="stretch",
        key=f"browser_jd_use_in_tailor_resume_{selected_id}",
        on_click=apply_browser_capture_tailor_resume_handoff,
        args=(st.session_state, int(selected_id)),
    )
    st.caption(
        "This switches Tailor Resume to the browser-capture source and preselects "
        "this exact capture. It does not call a model or create an application session."
    )

    posting_notes_json = str(item.get("posting_notes_json") or "").strip()
    if posting_notes_json and posting_notes_json != "[]":
        with st.expander("Posting/application notes excluded from JD matching"):
            st.code(posting_notes_json, language="json")

    tracking_tags_json = str(
        item.get("discarded_tracking_tags_json") or ""
    ).strip()
    if tracking_tags_json and tracking_tags_json != "[]":
        with st.expander("Discarded recruiting/tracking tags"):
            st.code(tracking_tags_json, language="json")

    raw_page = str(item.get("raw_page_text") or "")
    if raw_page:
        with st.expander("Raw browser page capture"):
            st.text_area(
                "Raw visible text",
                value=raw_page,
                height=260,
                key=f"browser_jd_raw_text_{selected_id}",
                disabled=True,
            )

"""Streamlit integrations for persisted résumé outputs and cover letters."""

from __future__ import annotations

import json
from typing import Any, Callable

import streamlit as st

from database.application_cover_letter_manager import (
    ApplicationCoverLetterError,
    generate_or_reuse_application_cover_letter,
    get_current_application_cover_letter,
    list_application_cover_letters,
)
from database.application_resume_output_manager import (
    ApplicationResumeOutputError,
)
from database.db_manager import get_application_by_id


def render_application_output_cover_letter(
    *,
    application_id: int,
    model_id: str,
    generator: Callable[[str, str, str], Any] | None = None,
    key_prefix: str = "application_output",
) -> None:
    """Generate or download a cover letter bound to a persisted résumé output."""
    st.subheader("Generate/download cover letter")
    st.caption(
        "The cover letter uses the persisted résumé output and exact linked JD. "
        "It never changes the résumé or creates an editable résumé draft."
    )
    try:
        current = get_current_application_cover_letter(
            application_id, model_id=model_id
        )
    except (ApplicationCoverLetterError, ApplicationResumeOutputError, ValueError) as exc:
        current = None
        st.warning(str(exc))

    if current is not None and current.get("scope_status") == "stale":
        st.warning(
            "The previously generated cover letter is historical because its "
            "résumé output, JD, model, prompt, or policy scope changed."
        )
        current = None

    if st.button(
        "Generate or reuse cover letter",
        type="primary",
        key=f"{key_prefix}_cover_letter_generate_{application_id}",
    ):
        try:
            with st.spinner("Generating or resolving the cover letter..."):
                response = generate_or_reuse_application_cover_letter(
                    application_id=application_id,
                    model_id=model_id,
                    generator=generator,
                )
            current = response["cover_letter"]
            current["scope_status"] = "current"
            if response["cache_status"] == "hit":
                st.success("Reused the exact persisted cover letter.")
            else:
                st.success("Generated and persisted a cover letter for this exact scope.")
        except (
            ApplicationCoverLetterError,
            ApplicationResumeOutputError,
            ValueError,
            RuntimeError,
        ) as exc:
            st.error(str(exc))

    if current is not None and current.get("scope_status") == "current":
        text = str(current.get("cover_letter_text") or "")
        st.text_area(
            "Current cover letter",
            value=text,
            height=320,
            disabled=True,
            key=f"{key_prefix}_cover_letter_text_{application_id}_{current['cover_letter_id']}",
        )
        st.caption(
            f"Cover letter `{current['cover_letter_id']}` · input fingerprint "
            f"`{current['input_fingerprint']}` · model `{current['model_id']}`"
        )
        st.download_button(
            "Download cover letter (.txt)",
            data=text,
            file_name=f"cover_letter_{application_id}_{current['cover_letter_id']}.txt",
            mime="text/plain",
            key=f"{key_prefix}_cover_letter_download_{application_id}_{current['cover_letter_id']}",
        )

    historical = [
        row
        for row in list_application_cover_letters(application_id)
        if current is None or row["cover_letter_id"] != current.get("cover_letter_id")
    ]
    if historical:
        with st.expander("Historical cover letters", expanded=False):
            selected_id = st.selectbox(
                "Explicitly select a historical cover letter",
                options=[row["cover_letter_id"] for row in historical],
                format_func=lambda value: next(
                    (
                        f"{row['created_at']} · {row['model_id']} · {value[:12]}"
                        for row in historical
                        if row["cover_letter_id"] == value
                    ),
                    value,
                ),
                key=f"{key_prefix}_historical_cover_letter_{application_id}",
            )
            selected = next(
                row for row in historical if row["cover_letter_id"] == selected_id
            )
            st.download_button(
                "Download selected historical cover letter (.txt)",
                data=str(selected.get("cover_letter_text") or ""),
                file_name=f"historical_cover_letter_{application_id}_{selected_id}.txt",
                mime="text/plain",
                key=f"{key_prefix}_historical_cover_letter_download_{application_id}",
            )

    application = get_application_by_id(application_id) or {}
    legacy_text = str(application.get("cover_letter") or "").strip()
    if legacy_text:
        with st.expander("Legacy unbound cover letter", expanded=False):
            st.warning(
                "This older session cover letter predates persisted résumé-output "
                "identity. It remains available for inspection but is not treated "
                "as current or eligible for exact semantic reuse."
            )
            st.download_button(
                "Download legacy unbound cover letter (.txt)",
                data=legacy_text,
                file_name=f"legacy_cover_letter_{application_id}.txt",
                mime="text/plain",
                key=f"{key_prefix}_legacy_cover_letter_download_{application_id}",
            )


def debug_bundle_json(bundle: dict[str, Any]) -> str:
    """Serialize a debug bundle in memory; callers decide how to download it."""
    return json.dumps(bundle, indent=2, ensure_ascii=False, default=str)

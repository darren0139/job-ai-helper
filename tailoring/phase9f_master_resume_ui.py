"""Dedicated Streamlit UI for Phase 9F-Master only."""

from __future__ import annotations

import tempfile
import sqlite3
from copy import deepcopy
from pathlib import Path
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

from analyzer import extract_resume_profile
from database.global_master_resume_manager import (
    clear_current_global_master_resume,
    commit_prepared_global_master_resume,
    find_master_resume_by_artifact_sha256,
    find_master_resume_by_text_sha256,
    get_current_global_master_resume,
    get_global_master_resume_artifact,
    list_global_master_resume_events,
    list_global_master_resume_versions,
)
from llm import get_active_model
from resume_builder.docx_projects_skills_replacer import (
    convert_docx_to_pdf_if_possible,
    pdf_to_preview_html,
)
from tailoring.phase9f_master_resume import (
    Phase9FMasterResumeError,
    analyse_and_prepare_master_resume,
    attach_preview_pdf,
    configured_artifact_size_limit,
    inspect_master_resume_upload,
    prepare_master_resume_from_reusable_profile,
    canonical_json,
)


_PREPARED_KEY = "phase9f_master_prepared_snapshot"
_COMMIT_RECEIPT_KEY = "phase9f_master_commit_receipt"


def _render_pdf_bytes(content: bytes, *, label: str) -> None:
    with tempfile.TemporaryDirectory(prefix="phase9f_master_preview_") as name:
        path = Path(name) / "preview.pdf"
        path.write_bytes(content)
        try:
            html = pdf_to_preview_html(
                path,
                max_width=820,
                max_pages=5,
                include_download=False,
            )
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            st.info(f"{label} preview is unavailable: {exc}")
            return
        components.html(html, height=1120, scrolling=True)


def _master_summary(master: dict[str, Any]) -> None:
    st.success(
        "Current Base Resume: "
        f"{master.get('display_name') or 'Base Resume'} · "
        f"Version {int(master.get('version_number') or 0)}"
    )
    identity_col, artifact_col, profile_col = st.columns(3)
    identity_col.metric(
        "Base Resume version ID",
        str(master.get("master_version_id") or "")[:16],
    )
    artifact_col.metric(
        "Artifact",
        str(master.get("artifact_type") or "").upper(),
        f"{int(master.get('artifact_size_bytes') or 0):,} bytes",
    )
    profile_col.metric(
        "Complete text",
        f"{int(master.get('resume_text_char_count') or 0):,} chars",
    )

    artifact = get_global_master_resume_artifact(
        str(master["master_version_id"]),
        "original",
    )
    if artifact is None:
        st.error("The authoritative original Base Resume artifact is missing.")
        return
    st.download_button(
        f"Download original {str(master.get('artifact_type') or '').upper()}",
        data=artifact["artifact_bytes"],
        file_name=artifact["filename"],
        mime=artifact["media_type"],
        key=f"phase9f_master_download_{master['master_version_id']}",
    )

    with st.expander("Inspect current Base Resume", expanded=False):
        st.caption(
            "Read-only immutable profile, complete extracted text, identity, and "
            "safe extraction provenance. This view makes no model or embedding calls."
        )
        st.json(
            {
                "master_version_id": master["master_version_id"],
                "master_version_fingerprint": master[
                    "master_version_fingerprint"
                ],
                "master_content_fingerprint": master[
                    "master_content_fingerprint"
                ],
                "version_number": master["version_number"],
                "artifact_sha256": master["artifact_sha256"],
                "resume_text_sha256": master["resume_text_sha256"],
                "structured_profile_fingerprint": master[
                    "structured_profile_fingerprint"
                ],
                "semantic_identity": master["semantic_identity"],
                "version_identity": master["version_identity"],
                "extraction_provenance": master["extraction_provenance"],
            }
        )
        st.write("**Frozen structured profile**")
        st.json(master["structured_profile"])
        st.write("**Complete extracted resume text**")
        st.code(master["resume_text"], language=None)
        export_snapshot = deepcopy(master["master_snapshot"])
        export_snapshot["display_name"] = master["display_name"]
        export_snapshot["created_at"] = master["created_at"]
        st.download_button(
            "Download immutable Base Resume snapshot JSON",
            data=canonical_json(export_snapshot),
            file_name=(
                "base_resume_"
                f"v{int(master['version_number'])}_"
                f"{str(master['master_version_id'])[:12]}.json"
            ),
            mime="application/json",
            key=f"phase9f_master_snapshot_json_{master['master_version_id']}",
        )

    preview = (
        artifact
        if master.get("artifact_type") == "pdf"
        else get_global_master_resume_artifact(
            str(master["master_version_id"]),
            "preview_pdf",
        )
    )
    if preview is not None:
        with st.expander("Preview current Base Resume", expanded=False):
            _render_pdf_bytes(
                preview["artifact_bytes"],
                label="Base Resume",
            )
    elif master.get("artifact_type") == "docx":
        st.caption(
            "A derived PDF preview was not stored. The authoritative DOCX remains "
            "available for download."
        )


def _render_remove_current_base_resume(
    current: dict[str, Any],
) -> None:
    with st.expander("Remove current Base Resume", expanded=False):
        st.warning(
            "This removes the current Base Resume selection only. The immutable "
            "version, original artifact, profile, fingerprints, and version history "
            "remain preserved in immutable version history."
        )
        confirmed = st.checkbox(
            "I understand the current Base Resume will be removed but its history "
            "will be preserved",
            value=False,
            key="phase9f_master_remove_confirmation",
        )
        actor_label = st.text_input(
            "Removal actor label",
            value="Local user",
            key="phase9f_master_remove_actor_label",
        )
        if st.button(
            "Remove Current Base Resume",
            disabled=not confirmed,
            key="phase9f_master_remove_current",
        ):
            try:
                receipt = clear_current_global_master_resume(
                    expected_master_version_id=str(
                        current.get("master_version_id") or ""
                    ),
                    expected_master_version_fingerprint=str(
                        current.get("master_version_fingerprint") or ""
                    ),
                    actor_label=actor_label,
                )
            except (Phase9FMasterResumeError, sqlite3.Error) as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"Could not remove the current Base Resume: {exc}")
            else:
                st.session_state[_COMMIT_RECEIPT_KEY] = receipt
                st.session_state.pop(_PREPARED_KEY, None)
                st.success(
                    "Current Base Resume removed. Immutable version history "
                    "and stored artifacts were preserved in history."
                )
                st.rerun()


def _prepared_matches_inspection(
    prepared: Any,
    inspection: dict[str, Any],
) -> bool:
    return bool(
        isinstance(prepared, dict)
        and str(prepared.get("artifact_sha256") or "")
        == str(inspection.get("artifact_sha256") or "")
        and str(prepared.get("resume_text_sha256") or "")
        == str(inspection.get("resume_text_sha256") or "")
    )


def _generate_docx_preview(prepared: dict[str, Any]) -> dict[str, Any] | None:
    with tempfile.TemporaryDirectory(prefix="phase9f_master_docx_preview_") as name:
        path = Path(name) / "master_resume.docx"
        path.write_bytes(prepared["artifact_bytes"])
        pdf_path = convert_docx_to_pdf_if_possible(path)
        if pdf_path is None or not Path(pdf_path).is_file():
            return None
        return attach_preview_pdf(prepared, Path(pdf_path).read_bytes())


def _render_prepared(
    prepared: dict[str, Any],
    *,
    current: dict[str, Any] | None,
    display_name: str,
) -> None:
    st.subheader("Prepared immutable Base Resume snapshot")
    mode = str(prepared.get("preparation_mode") or "")
    if "reuse" in mode:
        st.success(
            "An exact frozen profile was safely reused. Profile-extraction model "
            "calls: 0. Embedding calls: 0."
        )
    else:
        usage = (prepared.get("extraction_provenance") or {}).get(
            "api_usage"
        ) or {}
        cost = usage.get("estimated_cost_usd")
        cost_text = (
            "estimated cost unavailable"
            if cost is None
            else f"estimated cost ${float(cost):.6f} USD"
        )
        st.success(
            "Profile prepared successfully · "
            f"{int(usage.get('call_count') or 0)} model call · {cost_text}. "
            "Provider billing is authoritative."
        )

    st.json(
        {
            "prepared_snapshot_fingerprint": prepared[
                "prepared_snapshot_fingerprint"
            ],
            "master_content_fingerprint": prepared[
                "master_content_fingerprint"
            ],
            "artifact_sha256": prepared["artifact_sha256"],
            "resume_text_sha256": prepared["resume_text_sha256"],
            "structured_profile_fingerprint": prepared[
                "structured_profile_fingerprint"
            ],
            "preparation_mode": mode,
            "extraction_provenance": prepared["extraction_provenance"],
        }
    )

    if prepared.get("artifact_type") == "pdf":
        with st.expander("Preview prepared PDF", expanded=False):
            _render_pdf_bytes(
                prepared["artifact_bytes"],
                label="Prepared Base Resume",
            )
    elif prepared.get("preview_pdf_bytes") is not None:
        with st.expander("Preview prepared DOCX conversion", expanded=False):
            _render_pdf_bytes(
                prepared["preview_pdf_bytes"],
                label="Prepared Base Resume",
            )
    elif st.button(
        "Generate optional PDF preview",
        key="phase9f_master_generate_preview",
    ):
        with st.spinner("Generating a local PDF preview..."):
            with_preview = _generate_docx_preview(prepared)
        if with_preview is None:
            st.info(
                "LibreOffice is unavailable, so no derived preview was created. "
                "The complete authoritative DOCX can still be persisted."
            )
        else:
            st.session_state[_PREPARED_KEY] = with_preview
            st.rerun()

    exact_current = bool(
        current
        and str(current.get("artifact_sha256") or "")
        == str(prepared.get("artifact_sha256") or "")
        and str(current.get("master_content_fingerprint") or "")
        == str(prepared.get("master_content_fingerprint") or "")
    )
    if exact_current:
        st.info(
            "This is the exact current Base Resume. Completing the action will "
            "reuse the current immutable version and append an audit event."
        )
        confirmation_label = "Confirm exact current Base Resume reuse"
        button_label = "Confirm current Base Resume"
    elif current is None:
        confirmation_label = "Set this prepared snapshot as the first Base Resume"
        button_label = "Set as Base Resume"
    else:
        st.warning(
            "Replacing the current Base Resume creates the next immutable version. "
            "The previous version remains historical and inspectable."
        )
        confirmation_label = "Replace the current Base Resume with this snapshot"
        button_label = "Replace Base Resume"

    confirmed = st.checkbox(
        confirmation_label,
        value=False,
        key="phase9f_master_commit_confirmation",
    )
    actor_label = st.text_input(
        "Actor label",
        value="Local user",
        key="phase9f_master_actor_label",
    )
    if st.button(
        button_label,
        type="primary",
        disabled=not confirmed,
        key="phase9f_master_commit",
    ):
        try:
            receipt = commit_prepared_global_master_resume(
                deepcopy(prepared),
                display_name=display_name,
                actor_label=actor_label,
            )
        except (Phase9FMasterResumeError, sqlite3.Error) as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Could not persist the Base Resume: {exc}")
        else:
            st.session_state[_COMMIT_RECEIPT_KEY] = receipt
            st.session_state.pop(_PREPARED_KEY, None)
            st.success(
                "Base Resume saved. "
                f"Outcome: {receipt.get('outcome')}."
            )
            st.rerun()


def render_phase9f_master_resume() -> None:
    """Render the Phase 9F-Master registry without Phase 9F-B behavior."""
    st.subheader("Base Resume")
    st.caption(
        "Your broad, general-purpose technical resume used as a neutral starting "
        "option alongside specialized Blueprints. It does not replace the Profile "
        "& Evidence Library, and this registry itself does not score jobs or create "
        "Application Sessions."
    )

    current = get_current_global_master_resume()
    if current is None:
        st.info("No Base Resume has been set yet.")
    else:
        _master_summary(current)
        _render_remove_current_base_resume(current)

    st.divider()
    st.write("**Prepare a Base Resume**")
    st.caption(
        "Uploading performs local complete-text extraction and SHA-256 preflight "
        "only. It makes no model call, embedding call, persistence write, or "
        "Chroma index operation."
    )
    uploaded = st.file_uploader(
        "Upload PDF or DOCX",
        type=["pdf", "docx"],
        key="phase9f_master_upload",
    )
    if uploaded is None:
        with st.expander("Base Resume version history", expanded=False):
            versions = list_global_master_resume_versions()
            if not versions:
                st.caption("No immutable Base Resume versions exist.")
            else:
                st.dataframe(
                    [
                        {
                            "Version": row["version_number"],
                            "Display name": row["display_name"],
                            "Base Resume version ID": row["master_version_id"],
                            "Artifact SHA-256": row["artifact_sha256"],
                            "Created": row["created_at"],
                        }
                        for row in versions
                    ],
                    width="stretch",
                    hide_index=True,
                )
            st.json(list_global_master_resume_events())
        return

    try:
        inspection = inspect_master_resume_upload(
            filename=uploaded.name,
            content=uploaded.getvalue(),
            artifact_size_limit_bytes=configured_artifact_size_limit(),
        )
    except Phase9FMasterResumeError as exc:
        st.error(str(exc))
        return

    st.success(
        "Local preflight complete · "
        f"{inspection['artifact_size_bytes']:,} bytes · "
        f"{inspection['resume_text_char_count']:,} complete text characters · "
        "0 model calls · 0 embedding calls · 0 writes."
    )
    st.json(
        {
            "artifact_sha256": inspection["artifact_sha256"],
            "resume_text_sha256": inspection["resume_text_sha256"],
            "artifact_type": inspection["artifact_type"],
            "resume_text_char_count": inspection["resume_text_char_count"],
            "inspection_fingerprint": inspection["inspection_fingerprint"],
        }
    )
    display_name = st.text_input(
        "Base Resume display name",
        value=(
            str(current.get("display_name") or "Base Resume")
            if current
            else "Base Resume"
        ),
        key="phase9f_master_display_name",
    )

    prepared = st.session_state.get(_PREPARED_KEY)
    if not _prepared_matches_inspection(prepared, inspection):
        prepared = None
        st.session_state.pop(_PREPARED_KEY, None)

    reusable = None
    if current and str(current.get("artifact_sha256") or "") == str(
        inspection["artifact_sha256"]
    ):
        reusable = current
    if reusable is None:
        reusable = find_master_resume_by_artifact_sha256(
            inspection["artifact_sha256"]
        )
    if reusable is None:
        reusable = find_master_resume_by_text_sha256(
            inspection["resume_text_sha256"]
        )

    if prepared is None and reusable is not None:
        try:
            prepared = prepare_master_resume_from_reusable_profile(
                inspection=inspection,
                reusable_master=reusable,
                current_master=current,
            )
        except Phase9FMasterResumeError as exc:
            st.error(str(exc))
            return
        st.session_state[_PREPARED_KEY] = prepared

    if prepared is None:
        selected_model = get_active_model("analysis")
        st.warning(
            "This complete resume text is novel. Profile extraction will use one "
            f"model request with {selected_model}. API charges may apply. Uploading "
            "alone has not made that call."
        )
        if st.button(
            "Analyse & Prepare Base Resume",
            type="primary",
            key="phase9f_master_analyse",
        ):
            try:
                with st.spinner("Extracting one structured resume profile..."):
                    prepared = analyse_and_prepare_master_resume(
                        inspection=inspection,
                        current_master=current,
                        extract_profile_fn=extract_resume_profile,
                        requested_model=selected_model,
                    )
            except (Phase9FMasterResumeError, RuntimeError, ValueError) as exc:
                st.error(str(exc))
                return
            st.session_state[_PREPARED_KEY] = prepared
            st.rerun()
        return

    _render_prepared(
        prepared,
        current=current,
        display_name=display_name,
    )

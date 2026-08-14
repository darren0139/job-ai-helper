"""Read-only Streamlit presentation for immutable Phase 9E results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

from database.application_resume_result_manager import (
    accept_current_application_result,
    build_application_result_debug_bundle,
    create_editable_copy_from_current_application_result,
    list_application_resume_result_events,
    verify_current_application_result,
)
from llm import get_active_model
from tailoring.application_output_integrations_ui import (
    debug_bundle_json,
    render_application_output_cover_letter,
)
from database.tailoring_generation_control import list_tailoring_generations
from database.tailoring_generation_control import get_tailoring_generation
from tailoring.generation_controls_ui import restore_generation_to_session
from tailoring.phase9e_application_result import (
    STATUS_REUSED_APPROVED,
    Phase9EApplicationResultError,
)


def _artifact_download(
    *, application_id: int, result_id: str, artifact: dict[str, Any]
) -> None:
    path = Path(str(artifact.get("materialized_path") or ""))
    if not path.is_file():
        st.error("This immutable artifact is unavailable or failed validation.")
        return
    kind = str(artifact.get("artifact_kind") or "file")
    st.download_button(
        f"Download résumé {kind.upper()}",
        data=path.read_bytes(),
        file_name=path.name,
        mime=str(artifact.get("mime_type") or "application/octet-stream"),
        key=f"phase9e_result_download_{application_id}_{result_id}_{kind}",
    )


def render_phase9e_application_result(
    *,
    application_id: int,
    result: dict[str, Any],
    cover_letter_generator=None,
) -> None:
    """Render immutable reuse without draft approval, fit, or promotion controls."""
    state = result.get("state") or {}
    snapshot = result.get("result_snapshot") or {}
    starting = snapshot.get("starting_snapshot") or {}
    source_generation = snapshot.get("source_generation") or {}
    source_verification = snapshot.get("inherited_phase8_verification") or {}
    decision = snapshot.get("phase9e_decision") or {}
    selected_blueprint = (
        (decision.get("selection") or {}).get("selected_blueprint") or {}
    )

    st.divider()
    st.header("Application Résumé Result")
    if result.get("initial_status") == STATUS_REUSED_APPROVED:
        st.success(
            "Reused the approved Global Blueprint unchanged. No draft, fitting, "
            "or second content approval was created."
        )
        status_label = "Reused approved"
    else:
        st.warning(
            "This unchanged blueprint result is pending separate current-JD "
            "verification and explicit application acceptance."
        )
        status_label = "Pending application verification"

    st.caption("Current résumé state")
    st.write(f"**{status_label}**")
    summary = st.columns(3)
    summary[0].metric("Blueprint version", result.get("blueprint_version"))
    summary[1].metric("One-page fit", "Inherited")
    summary[2].metric("Content changed", "No")
    st.caption(
        f"Immutable result `{result['application_result_id']}` · "
        f"fingerprint `{result['result_fingerprint']}`"
    )

    st.subheader("Approved Global Blueprint source")
    st.write(
        f"**{selected_blueprint.get('display_name') or selected_blueprint.get('role_family_label') or 'Global Blueprint'}** "
        f"· version {result.get('blueprint_version')}"
    )
    st.caption(
        f"Blueprint `{result.get('blueprint_id')}` · "
        f"fingerprint `{result.get('blueprint_fingerprint')}`"
    )
    if st.button(
        "Open Global Blueprint",
        key=f"phase9e_open_global_blueprint_{application_id}",
    ):
        st.session_state["phase9d_inspect_blueprint_id"] = result[
            "blueprint_id"
        ]
        st.session_state["_pending_navigation_page"] = "Blueprint Library"
        st.rerun()

    provenance = st.columns(3)
    provenance[0].metric(
        "Approved source generation",
        str(result.get("source_generation_id") or "")[:12],
    )
    provenance[1].metric(
        "Inherited fit",
        "1 page" if (result.get("semantic_identity") or {}).get(
            "inherited_fit", {}
        ).get("fit_one_page") else "Unavailable",
    )
    provenance[2].metric(
        "Inherited Phase 8",
        str(result.get("source_verification_id") or "")[:12],
    )

    st.subheader("Download résumé DOCX/PDF")
    artifacts = result.get("artifacts") or []
    if not artifacts:
        st.error("No verified immutable résumé artifact is available.")
    for artifact in artifacts:
        st.write(f"**{artifact.get('provenance_label')}**")
        if not artifact.get("is_original_approved_artifact"):
            st.info(
                "The original approved file bytes were unavailable. This "
                "artifact was deterministically rendered from the immutable "
                "blueprint snapshot and is not the original fitted document."
            )
        st.caption(
            f"SHA-256 `{artifact.get('artifact_sha256')}` · "
            f"{artifact.get('artifact_size')} bytes"
        )
        _artifact_download(
            application_id=application_id,
            result_id=result["application_result_id"],
            artifact=artifact,
        )

    with st.expander("View Source Résumé", expanded=False):
        for artifact in artifacts:
            st.write(f"**{artifact.get('provenance_label')}**")
            if not artifact.get("is_original_approved_artifact"):
                st.info(
                    "The original approved file bytes were unavailable. This "
                    "artifact was deterministically rendered from the immutable "
                    "blueprint snapshot and is not the original fitted document."
                )
            st.caption(
                f"SHA-256 `{artifact.get('artifact_sha256')}` · "
                f"{artifact.get('artifact_size')} bytes"
            )
        st.text_area(
            "Frozen résumé text",
            value=str(starting.get("resume_text_snapshot") or ""),
            height=240,
            disabled=True,
            key=f"phase9e_frozen_text_{application_id}_{result['application_result_id']}",
        )
        st.json(starting.get("resume_profile_snapshot") or {})

    st.subheader("Download application-result debug bundle")
    try:
        debug_bundle = build_application_result_debug_bundle(
            result["application_result_id"]
        )
        st.download_button(
            "Download Application Result Debug Bundle",
            data=debug_bundle_json(debug_bundle),
            file_name=(
                f"application_result_{result['application_result_id']}_debug.json"
            ),
            mime="application/json",
            key=f"phase9e_result_debug_{application_id}_{result['application_result_id']}",
        )
        st.caption(
            "Contains persisted immutable provenance and may include personal résumé data."
        )
    except (Phase9EApplicationResultError, ValueError, RuntimeError) as exc:
        st.error(f"The application-result debug bundle is unavailable: {exc}")

    render_application_output_cover_letter(
        application_id=application_id,
        model_id=get_active_model("analysis"),
        generator=cover_letter_generator,
        key_prefix="phase9e_result",
    )

    with st.expander("View Verification"):
        st.info(
            "This is inherited source Phase 8 provenance. It was not rerun for "
            "the unchanged application result."
        )
        st.json(source_verification)

    with st.expander("View source generation provenance"):
        st.json(source_generation)

    if result.get("initial_status") != STATUS_REUSED_APPROVED:
        st.subheader("Current-JD application verification")
        if st.button(
            "Run deterministic current-JD verification",
            key=f"phase9e_verify_result_{application_id}",
        ):
            try:
                verify_current_application_result(
                    application_id=application_id, actor_label="Local user"
                )
                st.rerun()
            except (Phase9EApplicationResultError, ValueError, RuntimeError) as exc:
                st.error(str(exc))
        if state.get("current_verification_id"):
            acknowledgement = st.checkbox(
                "I accept this unchanged blueprint for the current application.",
                value=False,
                key=f"phase9e_accept_result_ack_{application_id}",
            )
            reason = st.text_area(
                "Acceptance reason",
                key=f"phase9e_accept_result_reason_{application_id}",
            )
            if st.button(
                "Accept unchanged application result",
                disabled=not acknowledgement,
                key=f"phase9e_accept_result_{application_id}",
            ):
                try:
                    accept_current_application_result(
                        application_id=application_id,
                        acknowledgement=acknowledgement,
                        reason=reason,
                        actor_label="Local user",
                    )
                    st.rerun()
                except (Phase9EApplicationResultError, ValueError, RuntimeError) as exc:
                    st.error(str(exc))

    st.subheader("Modify this content")
    st.info(
        "The Global Blueprint and this reuse result remain immutable. Create an "
        "editable application copy only when content may change."
    )
    if st.button(
        "Create editable copy",
        key=f"phase9e_create_editable_copy_{application_id}",
    ):
        try:
            created = create_editable_copy_from_current_application_result(
                application_id=application_id, actor_label="Local user"
            )
            editable = get_tailoring_generation(
                application_id, created["generation_id"]
            )
            if editable is None:
                raise RuntimeError("The editable copy could not be reloaded.")
            restore_generation_to_session(application_id, editable)
            st.session_state[
                f"tailored_generation_id_{application_id}"
            ] = created["generation_id"]
            st.rerun()
        except (Phase9EApplicationResultError, ValueError, RuntimeError) as exc:
            st.error(str(exc))

    legacy = [
        row for row in list_tailoring_generations(application_id)
        if str(row.get("generation_kind") or "") == "phase9e_reuse_snapshot"
    ]
    if legacy:
        with st.expander(
            "Legacy Phase 9E reuse drafts (historical only)", expanded=False
        ):
            st.warning(
                "These pre-migration draft rows are preserved unchanged. They are "
                "not the current application result and cannot be promoted here."
            )
            st.dataframe(
                [
                    {
                        "Generation": row.get("generation_id"),
                        "Status": row.get("status"),
                        "Created": row.get("created_at"),
                        "Updated": row.get("updated_at"),
                    }
                    for row in legacy
                ],
                hide_index=True,
                width="stretch",
            )

    with st.expander("Application result identity and audit history"):
        st.json(result)
        events = list_application_resume_result_events(application_id)
        st.json(events)

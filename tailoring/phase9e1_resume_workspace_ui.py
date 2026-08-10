"""Top-level résumé version browser and revision workspace."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import streamlit as st
from streamlit.errors import StreamlitAPIException

from database.application_blueprint_manager import (
    get_current_application_blueprint_decision,
)
from database.tailoring_generation_control import (
    archive_tailoring_generation,
    delete_tailoring_generation,
    get_application_generation_control,
    get_tailoring_generation_delete_plan,
    list_tailoring_generations,
    record_generation_metadata,
    restore_tailoring_generation_as_draft,
)
from tailoring.generation_controls_ui import restore_generation_to_session
from tailoring.tailoring_generation_fingerprint import (
    generation_matches_phase9e_binding,
)


PHASE9E1_RESUME_WORKSPACE_UI_VERSION = "phase9e1-resume-workspace-v8"


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _is_active_binding(decision: dict[str, Any] | None) -> bool:
    state = decision or {}
    return bool(
        _clean(state.get("scope_activation_status")) == "active"
        and _clean(state.get("current_scope_status")) == "current"
        and _clean(state.get("decision_fingerprint"))
    )


def _belongs_to_current_scope(
    generation: dict[str, Any],
    binding: dict[str, Any] | None,
) -> bool:
    if not binding:
        return True

    expected_decision = _clean(binding.get("decision_fingerprint"))
    stored_decision = _clean(
        generation.get("phase9e_decision_fingerprint")
    )
    if stored_decision:
        return bool(
            expected_decision
            and stored_decision == expected_decision
        )

    return generation_matches_phase9e_binding(generation, binding)


def _generation_id(state: dict[str, Any] | None) -> str:
    return _clean((state or {}).get("generation_id"))


def _status(state: dict[str, Any] | None) -> str:
    return _clean((state or {}).get("status")).lower()


def _page_count(state: dict[str, Any] | None) -> int | None:
    value = (
        (state or {}).get("fit_result") or {}
    ).get("page_count")
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _artifact_path(
    state: dict[str, Any] | None,
    field: str,
) -> Path | None:
    value = (state or {}).get(field)
    if not value:
        return None
    path = Path(str(value))
    return path if path.is_file() else None


def _is_previously_approved(state: dict[str, Any]) -> bool:
    return bool(
        _status(state) == "archived"
        and _clean(state.get("approved_at"))
    )


def _revision_draft_for_approved(
    *,
    approved_generation: dict[str, Any] | None,
    drafts: list[dict[str, Any]],
) -> dict[str, Any] | None:
    approved_id = _generation_id(approved_generation)
    if not approved_id:
        return None

    candidates = [
        draft
        for draft in drafts
        if _clean(draft.get("generation_kind")) == "approved_revision"
        and (
            _clean(draft.get("parent_generation_id")) == approved_id
            or _clean(draft.get("restored_from_generation_id"))
            == approved_id
        )
    ]
    if not candidates:
        return None

    return sorted(
        candidates,
        key=lambda item: (
            _clean(item.get("updated_at")),
            int(item.get("id") or 0),
        ),
        reverse=True,
    )[0]


def build_resume_workspace_state(
    *,
    generations: list[dict[str, Any]],
    approved_generation: dict[str, Any] | None,
    loaded_generation_id: str,
    phase9e_binding: dict[str, Any] | None,
) -> dict[str, Any]:
    current_scope = [
        state
        for state in generations
        if isinstance(state, dict)
        and _clean(state.get("generation_kind"))
        != "phase9e_reuse_snapshot"
        and _belongs_to_current_scope(state, phase9e_binding)
    ]
    other_scope = [
        state
        for state in generations
        if isinstance(state, dict)
        and _clean(state.get("generation_kind"))
        != "phase9e_reuse_snapshot"
        and state not in current_scope
    ]

    current_drafts = [
        state
        for state in current_scope
        if _status(state) == "draft"
    ]
    current_approved = (
        approved_generation
        if isinstance(approved_generation, dict)
        and _belongs_to_current_scope(
            approved_generation,
            phase9e_binding,
        )
        else None
    )

    current_versions: list[dict[str, Any]] = []
    approved_id = _generation_id(current_approved)
    if current_approved is not None:
        current_versions.append(current_approved)
    current_versions.extend(
        state
        for state in current_scope
        if _generation_id(state) != approved_id
        and _status(state) in {"draft", "approved"}
    )

    historical_versions = [
        state
        for state in current_scope
        if _status(state) == "archived"
    ] + other_scope

    browsable_versions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for state in current_versions + historical_versions:
        generation_id = _generation_id(state)
        if generation_id and generation_id not in seen:
            browsable_versions.append(state)
            seen.add(generation_id)

    by_id = {
        _generation_id(state): state
        for state in current_versions
        if _generation_id(state)
    }
    loaded = by_id.get(_clean(loaded_generation_id))
    loaded_mode = "none"
    if isinstance(loaded, dict):
        loaded_mode = (
            "working_draft"
            if _status(loaded) == "draft"
            else "approved_read_only"
            if _status(loaded) == "approved"
            else "other"
        )

    return {
        "ui_version": PHASE9E1_RESUME_WORKSPACE_UI_VERSION,
        "approved_generation": current_approved,
        "loaded_generation": loaded,
        "loaded_mode": loaded_mode,
        "current_versions": current_versions,
        "current_drafts": current_drafts,
        "historical_versions": historical_versions,
        "browsable_versions": browsable_versions,
        "revision_draft": _revision_draft_for_approved(
            approved_generation=current_approved,
            drafts=current_drafts,
        ),
        "has_active_phase9e_binding": bool(phase9e_binding),
    }


def get_resume_workspace_context(
    application_id: int,
) -> dict[str, Any]:
    decision = get_current_application_blueprint_decision(
        int(application_id)
    )
    binding = decision if _is_active_binding(decision) else None
    control = get_application_generation_control(int(application_id))
    generations = list_tailoring_generations(int(application_id))
    loaded_id = _clean(
        st.session_state.get(
            f"tailored_generation_id_{application_id}",
            "",
        )
    )
    state = build_resume_workspace_state(
        generations=generations,
        approved_generation=control.get("approved_generation"),
        loaded_generation_id=loaded_id,
        phase9e_binding=binding,
    )
    state["phase9e_binding"] = binding
    return state


def should_clear_phase9e_session_state(
    *,
    previous_marker: str | None,
    binding_marker: str,
    phase9e_enforced: bool,
) -> bool:
    """Clear generation state only on a real Phase 9E binding transition."""
    previous = _clean(previous_marker)
    current = _clean(binding_marker)
    return bool(
        phase9e_enforced
        and previous
        and current
        and previous != current
    )


def workspace_requires_edit_draft(application_id: int) -> bool:
    state = get_resume_workspace_context(int(application_id))
    return bool(
        state.get("approved_generation")
        and state.get("loaded_mode") != "working_draft"
    )


def _version_label(
    state: dict[str, Any],
    *,
    current_approved_id: str,
    current_ids: set[str],
) -> str:
    generation_id = _generation_id(state)
    status = _status(state)
    pages = _page_count(state)
    page_label = (
        "not fitted"
        if pages is None
        else "1 page"
        if pages == 1
        else f"{pages} pages"
    )

    if generation_id == current_approved_id:
        prefix = "CURRENT APPROVED"
    elif generation_id not in current_ids:
        if _is_previously_approved(state):
            prefix = "HISTORY · PREVIOUSLY APPROVED"
        else:
            prefix = f"HISTORY · {status.upper() or 'VERSION'}"
    elif status == "draft":
        kind = _clean(state.get("generation_kind"))
        prefix = (
            "REVISION DRAFT"
            if kind == "approved_revision"
            else "ALTERNATIVE DRAFT"
            if kind == "alternative_copy"
            else "DRAFT"
        )
    else:
        prefix = status.upper() or "VERSION"

    return f"{prefix} · {generation_id[:8]} · {page_label}"


def _render_pdf_preview(state: dict[str, Any]) -> None:
    pdf_path = _artifact_path(state, "pdf_path")
    if pdf_path is None:
        st.info(
            "A visual preview will appear after this version has a fitted PDF."
        )
        return

    data = pdf_path.read_bytes()
    pdf_renderer = getattr(st, "pdf", None)
    if callable(pdf_renderer):
        try:
            pdf_renderer(data, height=720)
            return
        except StreamlitAPIException:
            # st.pdf exists in core Streamlit even when the optional
            # streamlit-pdf component is not installed. Fall through to the
            # dependency-free embedded PDF preview below.
            pass

    encoded = base64.b64encode(data).decode("ascii")
    st.iframe(
        "data:application/pdf;base64," + encoded,
        height=720,
    )


def _download_button(
    *,
    state: dict[str, Any],
    field: str,
    label: str,
    mime: str,
    key: str,
) -> None:
    path = _artifact_path(state, field)
    if path is None:
        st.button(
            label,
            key=key,
            disabled=True,
            width="stretch",
        )
        return

    st.download_button(
        label,
        data=path.read_bytes(),
        file_name=path.name,
        mime=mime,
        key=key,
        width="stretch",
    )


def _open_generation(
    *,
    application_id: int,
    state: dict[str, Any],
    flash_key: str,
    message: str,
) -> None:
    restore_generation_to_session(int(application_id), state)
    st.session_state[flash_key] = message
    st.rerun()


def _clear_generation_session_state(application_id: int) -> None:
    keys = (
        f"project_candidate_pool_{application_id}",
        f"debug_project_tailor_inputs_{application_id}",
        f"tailored_projects_fit_{application_id}",
        f"tailored_projects_result_{application_id}",
        f"tailored_skills_result_{application_id}",
        f"tailored_resume_fit_result_{application_id}",
        f"tailored_generation_id_{application_id}",
        f"tailored_resume_copy_path_{application_id}",
        f"restored_tailoring_settings_{application_id}",
    )
    for key in keys:
        st.session_state.pop(key, None)


def _delete_generation_and_recover(
    *,
    application_id: int,
    generation_id: str,
    loaded_generation_id: str,
    delete_files: bool,
) -> None:
    delete_tailoring_generation(
        application_id=int(application_id),
        generation_id=generation_id,
        delete_unreferenced_files=delete_files,
    )
    if generation_id == loaded_generation_id:
        _clear_generation_session_state(int(application_id))


def _render_delete_blockers(plan: dict[str, Any]) -> None:
    blockers = [
        _clean(value)
        for value in plan.get("blockers") or []
        if _clean(value)
    ]
    if blockers:
        st.caption(
            "Protected from deletion: " + " · ".join(blockers)
        )


def _history_label(state: dict[str, Any]) -> str:
    generation_id = _generation_id(state)
    status = _status(state)
    if _is_previously_approved(state):
        prefix = "PREVIOUS APPROVED"
    elif status == "draft":
        prefix = "PREVIOUS SOURCE DRAFT"
    elif status == "archived":
        prefix = "ARCHIVED"
    else:
        prefix = status.upper() or "HISTORICAL"

    pages = _page_count(state)
    page_label = (
        "not fitted"
        if pages is None
        else "1 page"
        if pages == 1
        else f"{pages} pages"
    )
    return f"{prefix} · {generation_id[:8]} · {page_label}"


def _create_tagged_copy(
    *,
    application_id: int,
    source_generation_id: str,
    generation_kind: str,
) -> dict[str, Any]:
    draft = restore_tailoring_generation_as_draft(
        application_id=int(application_id),
        source_generation_id=source_generation_id,
    )
    record_generation_metadata(
        application_id=int(application_id),
        generation_id=_generation_id(draft),
        input_fingerprint=_clean(draft.get("input_fingerprint")),
        generation_kind=generation_kind,
        parent_generation_id=source_generation_id,
        restored_from_generation_id=source_generation_id,
        source_application_result_id=_clean(
            draft.get("source_application_result_id")
        ),
        base_content_fingerprint=_clean(
            draft.get("base_content_fingerprint")
        ),
        content_fingerprint=_clean(
            draft.get("content_fingerprint")
        ),
        content_changed=draft.get("content_changed"),
        phase9e_decision_fingerprint=_clean(
            draft.get("phase9e_decision_fingerprint")
        ),
    )
    refreshed = [
        state
        for state in list_tailoring_generations(int(application_id))
        if _generation_id(state) == _generation_id(draft)
    ]
    return refreshed[0] if refreshed else draft


def _begin_approved_revision(
    *,
    application_id: int,
    approved: dict[str, Any],
    existing_revision: dict[str, Any] | None,
) -> dict[str, Any]:
    approved_id = _generation_id(approved)
    if not approved_id:
        raise ValueError("Approved generation identity is missing.")

    revision = existing_revision
    if revision is None:
        revision = _create_tagged_copy(
            application_id=int(application_id),
            source_generation_id=approved_id,
            generation_kind="approved_revision",
        )

    # Archive only after a usable revision exists. This clears the active
    # approved pointer and section locks while preserving the previously
    # approved record and its Phase 8 verification as historical evidence.
    archive_tailoring_generation(
        int(application_id),
        approved_id,
    )
    return revision


def render_resume_workspace(*, application_id: int) -> dict[str, Any]:
    state = get_resume_workspace_context(int(application_id))
    approved = state["approved_generation"]
    loaded = state["loaded_generation"]
    current_versions = state["current_versions"]
    historical_versions = state["historical_versions"]
    revision_draft = state["revision_draft"]

    st.write("#### Résumé Workspace")
    st.caption(
        "Work with the current approved résumé and current-scope drafts here. "
        "Older or source-mismatched versions are kept separately under "
        "Version history and recovery so they do not look editable."
    )

    flash_key = f"phase9e1_workspace_flash_{application_id}"
    revise_confirm_key = (
        f"phase9e1_workspace_confirm_revise_{application_id}"
    )
    copy_confirm_key = (
        f"phase9e1_workspace_confirm_copy_{application_id}"
    )
    delete_confirm_key = (
        f"phase9e1_workspace_confirm_delete_{application_id}"
    )

    flash = st.session_state.pop(flash_key, "")
    if flash:
        st.success(flash)

    if approved is None and state["loaded_mode"] == "working_draft":
        st.warning(
            "Revision in progress. There is no current approved résumé. "
            "Finish the working draft, fit it, approve it, and run Phase 8 "
            "verification again."
        )

    approved_id = _generation_id(approved)
    loaded_id = _generation_id(loaded)
    current_ids = {
        _generation_id(version)
        for version in current_versions
        if _generation_id(version)
    }

    if current_versions:
        current_by_id = {
            _generation_id(version): version
            for version in current_versions
            if _generation_id(version)
        }
        options = list(current_by_id)
        default_id = (
            loaded_id
            if loaded_id in current_by_id
            else approved_id
            if approved_id in current_by_id
            else options[0]
        )

        selected_id = st.selectbox(
            "Current résumé version",
            options=options,
            index=options.index(default_id),
            format_func=lambda value: _version_label(
                current_by_id[value],
                current_approved_id=approved_id,
                current_ids=current_ids,
            ),
            key=f"phase9e1_workspace_version_{application_id}",
        )
        selected = current_by_id[selected_id]
        selected_status = _status(selected)
        selected_is_current_approved = bool(
            approved is not None and selected_id == approved_id
        )

        if (
            selected_status == "draft"
            and approved_id
            and selected_id != approved_id
        ):
            st.info(
                f"Working draft {selected_id[:8]} is the active workflow "
                "target. It still needs approval and Phase 8 verification, so "
                "Phase 9B–9E below will remain waiting for this draft. The "
                f"previous approved résumé {approved_id[:8]} and its Blueprint "
                "lineage remain preserved in history."
            )

        st.caption(
            "Only current-scope versions appear in this dropdown. "
            "Selecting a version changes the preview; a draft must be loaded "
            "before tailoring or fitting can edit it."
        )

        with st.container(border=True):
            cols = st.columns(4)
            cols[0].caption("Selected version")
            cols[0].write(f"**{selected_id[:8]}**")

            cols[1].caption("Status")
            cols[1].write(
                f"**{selected_status.title() or 'Version'}**"
            )

            cols[2].caption("Fit")
            pages = _page_count(selected)
            cols[2].write(
                "**Not fitted**"
                if pages is None
                else f"**{pages} page{'s' if pages != 1 else ''}**"
            )

            cols[3].caption("Workspace")
            if selected_id == loaded_id:
                cols[3].write("**Open now**")
            elif selected_is_current_approved:
                cols[3].write("**Trusted result**")
            elif selected_status == "draft":
                cols[3].write("**Available draft**")
            else:
                cols[3].write("**Available**")

            with st.expander("Preview selected résumé", expanded=False):
                _render_pdf_preview(selected)

            docx_col, pdf_col = st.columns(2)
            with docx_col:
                _download_button(
                    state=selected,
                    field="docx_path",
                    label="Download selected DOCX",
                    mime=(
                        "application/vnd.openxmlformats-officedocument."
                        "wordprocessingml.document"
                    ),
                    key=(
                        f"phase9e1_workspace_docx_{application_id}_"
                        f"{selected_id}"
                    ),
                )
            with pdf_col:
                _download_button(
                    state=selected,
                    field="pdf_path",
                    label="Download selected PDF",
                    mime="application/pdf",
                    key=(
                        f"phase9e1_workspace_pdf_{application_id}_"
                        f"{selected_id}"
                    ),
                )

            if selected_is_current_approved:
                read_col, revise_col, copy_col = st.columns(3)
                with read_col:
                    if st.button(
                        "Open read-only",
                        key=(
                            f"phase9e1_workspace_open_"
                            f"{application_id}_{selected_id}"
                        ),
                        disabled=selected_id == loaded_id,
                        width="stretch",
                    ):
                        _open_generation(
                            application_id=int(application_id),
                            state=selected,
                            flash_key=flash_key,
                            message=(
                                "Opened the approved résumé read-only. "
                                "Its approval was not changed."
                            ),
                        )

                with revise_col:
                    if st.button(
                        "Revise approved résumé",
                        key=(
                            f"phase9e1_workspace_revise_"
                            f"{application_id}_{selected_id}"
                        ),
                        type="primary",
                        width="stretch",
                    ):
                        st.session_state[revise_confirm_key] = selected_id
                        st.rerun()

                with copy_col:
                    if st.button(
                        "Create alternative copy",
                        key=(
                            f"phase9e1_workspace_copy_"
                            f"{application_id}_{selected_id}"
                        ),
                        width="stretch",
                    ):
                        st.session_state[copy_confirm_key] = selected_id
                        st.rerun()

                if st.session_state.get(revise_confirm_key) == selected_id:
                    st.warning(
                        "Revising removes this résumé as the current approved "
                        "result. Its Phase 8 verification and any Blueprint "
                        "candidate derived from it become historical for the "
                        "current workflow. The previous approved record itself "
                        "is preserved and can still be previewed/downloaded."
                    )
                    if revision_draft is not None:
                        st.info(
                            "A revision draft already exists, so continuing "
                            "will reuse it rather than create another draft."
                        )
                    confirm_col, cancel_col = st.columns(2)
                    with confirm_col:
                        if st.button(
                            "Remove approval and continue editing",
                            key=(
                                f"phase9e1_workspace_revise_confirm_"
                                f"{application_id}_{selected_id}"
                            ),
                            type="primary",
                            width="stretch",
                        ):
                            revision = _begin_approved_revision(
                                application_id=int(application_id),
                                approved=selected,
                                existing_revision=revision_draft,
                            )
                            st.session_state.pop(
                                revise_confirm_key,
                                None,
                            )
                            _open_generation(
                                application_id=int(application_id),
                                state=revision,
                                flash_key=flash_key,
                                message=(
                                    "Revision started. Current approval was "
                                    "removed; re-approve and run Phase 8 after "
                                    "finishing the revised résumé."
                                ),
                            )
                    with cancel_col:
                        if st.button(
                            "Cancel",
                            key=(
                                f"phase9e1_workspace_revise_cancel_"
                                f"{application_id}_{selected_id}"
                            ),
                            width="stretch",
                        ):
                            st.session_state.pop(
                                revise_confirm_key,
                                None,
                            )
                            st.rerun()

                if st.session_state.get(copy_confirm_key) == selected_id:
                    st.warning(
                        "This creates a separate alternative draft while "
                        "keeping the current approved résumé and Phase 8 "
                        "verification active. Use this for experimentation, "
                        "not normal revision."
                    )
                    confirm_col, cancel_col = st.columns(2)
                    with confirm_col:
                        if st.button(
                            "Create alternative draft",
                            key=(
                                f"phase9e1_workspace_copy_confirm_"
                                f"{application_id}_{selected_id}"
                            ),
                            width="stretch",
                        ):
                            draft = _create_tagged_copy(
                                application_id=int(application_id),
                                source_generation_id=selected_id,
                                generation_kind="alternative_copy",
                            )
                            st.session_state.pop(copy_confirm_key, None)
                            _open_generation(
                                application_id=int(application_id),
                                state=draft,
                                flash_key=flash_key,
                                message=(
                                    "Alternative draft created. The approved "
                                    "résumé remains current and verified."
                                ),
                            )
                    with cancel_col:
                        if st.button(
                            "Cancel",
                            key=(
                                f"phase9e1_workspace_copy_cancel_"
                                f"{application_id}_{selected_id}"
                            ),
                            width="stretch",
                        ):
                            st.session_state.pop(copy_confirm_key, None)
                            st.rerun()

            elif selected_status == "draft":
                delete_plan = get_tailoring_generation_delete_plan(
                    application_id=int(application_id),
                    generation_id=selected_id,
                )
                load_col, delete_col = st.columns(2)
                with load_col:
                    if st.button(
                        "Load selected working draft",
                        key=(
                            f"phase9e1_workspace_load_"
                            f"{application_id}_{selected_id}"
                        ),
                        type="primary",
                        width="stretch",
                        disabled=selected_id == loaded_id,
                    ):
                        _open_generation(
                            application_id=int(application_id),
                            state=selected,
                            flash_key=flash_key,
                            message="Loaded the selected working draft.",
                        )

                with delete_col:
                    if st.button(
                        "Delete draft",
                        key=(
                            f"phase9e1_workspace_delete_"
                            f"{application_id}_{selected_id}"
                        ),
                        width="stretch",
                        disabled=not bool(delete_plan.get("deletable")),
                    ):
                        st.session_state[delete_confirm_key] = selected_id
                        st.rerun()

                if not delete_plan.get("deletable"):
                    _render_delete_blockers(delete_plan)

                if (
                    st.session_state.get(delete_confirm_key)
                    == selected_id
                    and delete_plan.get("deletable")
                ):
                    st.warning(
                        "Delete this draft permanently? The current approved "
                        "résumé is not changed. This action cannot be undone."
                    )
                    remove_files = st.checkbox(
                        "Also remove unreferenced generated DOCX/PDF files",
                        value=False,
                        key=(
                            f"phase9e1_workspace_delete_files_"
                            f"{application_id}_{selected_id}"
                        ),
                    )
                    confirm_col, cancel_col = st.columns(2)
                    with confirm_col:
                        if st.button(
                            "Delete draft permanently",
                            key=(
                                f"phase9e1_workspace_delete_confirm_"
                                f"{application_id}_{selected_id}"
                            ),
                            type="primary",
                            width="stretch",
                        ):
                            _delete_generation_and_recover(
                                application_id=int(application_id),
                                generation_id=selected_id,
                                loaded_generation_id=loaded_id,
                                delete_files=remove_files,
                            )
                            st.session_state.pop(
                                delete_confirm_key,
                                None,
                            )
                            st.session_state[flash_key] = (
                                "Deleted the draft permanently."
                            )
                            st.rerun()
                    with cancel_col:
                        if st.button(
                            "Cancel",
                            key=(
                                f"phase9e1_workspace_delete_cancel_"
                                f"{application_id}_{selected_id}"
                            ),
                            width="stretch",
                        ):
                            st.session_state.pop(
                                delete_confirm_key,
                                None,
                            )
                            st.rerun()
    else:
        st.info(
            "No current-scope résumé version is available. Historical "
            "versions, when present, remain available below for recovery "
            "and cleanup."
        )

    if historical_versions:
        with st.expander(
            f"Version history and recovery ({len(historical_versions)})",
            expanded=False,
        ):
            st.caption(
                "Historical versions are intentionally excluded from the "
                "normal résumé dropdown because they are not current editable "
                "workspace versions. Preview/download them here, and remove "
                "unreferenced test or obsolete versions when appropriate."
            )

            history_by_id = {
                _generation_id(version): version
                for version in historical_versions
                if _generation_id(version)
            }
            history_ids = list(history_by_id)
            history_id = st.selectbox(
                "Historical résumé version",
                options=history_ids,
                format_func=lambda value: _history_label(
                    history_by_id[value]
                ),
                key=f"phase9e1_workspace_history_{application_id}",
            )
            historical = history_by_id[history_id]
            history_plan = get_tailoring_generation_delete_plan(
                application_id=int(application_id),
                generation_id=history_id,
            )

            history_cols = st.columns(3)
            history_cols[0].caption("Version")
            history_cols[0].write(f"**{history_id[:8]}**")
            history_cols[1].caption("Status")
            history_cols[1].write(
                f"**{_status(historical).title() or 'Historical'}**"
            )
            history_cols[2].caption("Access")
            history_cols[2].write("**Preview / recovery only**")

            with st.expander(
                "Preview historical résumé",
                expanded=False,
            ):
                _render_pdf_preview(historical)

            docx_col, pdf_col = st.columns(2)
            with docx_col:
                _download_button(
                    state=historical,
                    field="docx_path",
                    label="Download historical DOCX",
                    mime=(
                        "application/vnd.openxmlformats-officedocument."
                        "wordprocessingml.document"
                    ),
                    key=(
                        f"phase9e1_history_docx_"
                        f"{application_id}_{history_id}"
                    ),
                )
            with pdf_col:
                _download_button(
                    state=historical,
                    field="pdf_path",
                    label="Download historical PDF",
                    mime="application/pdf",
                    key=(
                        f"phase9e1_history_pdf_"
                        f"{application_id}_{history_id}"
                    ),
                )

            if history_plan.get("deletable"):
                history_delete_key = (
                    f"phase9e1_history_delete_confirm_"
                    f"{application_id}_{history_id}"
                )
                if st.button(
                    "Delete this historical version",
                    key=(
                        f"phase9e1_history_delete_"
                        f"{application_id}_{history_id}"
                    ),
                    width="stretch",
                ):
                    st.session_state[history_delete_key] = True
                    st.rerun()

                if st.session_state.get(history_delete_key):
                    st.warning(
                        "This historical version is not referenced by an "
                        "approval, Phase 8 verification, Blueprint candidate, "
                        "application result, cover letter, or child generation. "
                        "Deleting it is permanent."
                    )
                    remove_history_files = st.checkbox(
                        "Also remove its unreferenced generated DOCX/PDF files",
                        value=False,
                        key=(
                            f"phase9e1_history_delete_files_"
                            f"{application_id}_{history_id}"
                        ),
                    )
                    confirm_col, cancel_col = st.columns(2)
                    with confirm_col:
                        if st.button(
                            "Delete historical version permanently",
                            key=(
                                f"phase9e1_history_delete_yes_"
                                f"{application_id}_{history_id}"
                            ),
                            type="primary",
                            width="stretch",
                        ):
                            _delete_generation_and_recover(
                                application_id=int(application_id),
                                generation_id=history_id,
                                loaded_generation_id=loaded_id,
                                delete_files=remove_history_files,
                            )
                            st.session_state.pop(
                                history_delete_key,
                                None,
                            )
                            st.session_state[flash_key] = (
                                "Deleted the unreferenced historical version."
                            )
                            st.rerun()
                    with cancel_col:
                        if st.button(
                            "Cancel",
                            key=(
                                f"phase9e1_history_delete_no_"
                                f"{application_id}_{history_id}"
                            ),
                            width="stretch",
                        ):
                            st.session_state.pop(
                                history_delete_key,
                                None,
                            )
                            st.rerun()
            else:
                _render_delete_blockers(history_plan)

            with st.expander(
                "Development cleanup",
                expanded=False,
            ):
                plans = {
                    generation_id: get_tailoring_generation_delete_plan(
                        application_id=int(application_id),
                        generation_id=generation_id,
                    )
                    for generation_id in history_ids
                }
                removable_ids = [
                    generation_id
                    for generation_id in history_ids
                    if plans[generation_id].get("deletable")
                ]
                protected_ids = [
                    generation_id
                    for generation_id in history_ids
                    if generation_id not in removable_ids
                ]

                metric_col1, metric_col2 = st.columns(2)
                metric_col1.metric(
                    "Removable history",
                    len(removable_ids),
                )
                metric_col2.metric(
                    "Protected lineage",
                    len(protected_ids),
                )

                st.caption(
                    "Use this to clean development/test history. Protected "
                    "versions are never offered for deletion."
                )

                if removable_ids:
                    cleanup_ids = st.multiselect(
                        "Historical versions to remove",
                        options=removable_ids,
                        format_func=lambda value: _history_label(
                            history_by_id[value]
                        ),
                        key=(
                            f"phase9e1_history_cleanup_"
                            f"{application_id}"
                        ),
                    )
                    cleanup_files = st.checkbox(
                        "Also remove unreferenced generated files",
                        value=False,
                        key=(
                            f"phase9e1_history_cleanup_files_"
                            f"{application_id}"
                        ),
                    )
                    cleanup_confirm = st.checkbox(
                        (
                            "I understand that selected historical versions "
                            "will be permanently deleted"
                        ),
                        value=False,
                        key=(
                            f"phase9e1_history_cleanup_confirm_"
                            f"{application_id}"
                        ),
                    )
                    if st.button(
                        f"Delete {len(cleanup_ids)} selected history version(s)",
                        key=(
                            f"phase9e1_history_cleanup_delete_"
                            f"{application_id}"
                        ),
                        disabled=not (
                            cleanup_ids and cleanup_confirm
                        ),
                        width="stretch",
                    ):
                        deleted_count = 0
                        for generation_id in cleanup_ids:
                            plan = get_tailoring_generation_delete_plan(
                                application_id=int(application_id),
                                generation_id=generation_id,
                            )
                            if not plan.get("deletable"):
                                continue
                            _delete_generation_and_recover(
                                application_id=int(application_id),
                                generation_id=generation_id,
                                loaded_generation_id=loaded_id,
                                delete_files=cleanup_files,
                            )
                            deleted_count += 1
                        st.session_state[flash_key] = (
                            f"Deleted {deleted_count} unreferenced "
                            "historical version(s)."
                        )
                        st.rerun()
                else:
                    st.info(
                        "No historical version is currently safe to delete. "
                        "The remaining records are protecting workflow lineage."
                    )

                if protected_ids:
                    with st.expander(
                        "Why some history is protected",
                        expanded=False,
                    ):
                        for generation_id in protected_ids:
                            blockers = plans[generation_id].get(
                                "blockers"
                            ) or []
                            st.write(
                                f"**{generation_id[:8]}** — "
                                + "; ".join(
                                    _clean(value)
                                    for value in blockers
                                    if _clean(value)
                                )
                            )

    return state


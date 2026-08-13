"""Clear Streamlit controls for tailoring history, approval, and fitted locks."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import streamlit as st

from database.tailoring_generation_control import (
    approve_tailoring_generation,
    archive_tailoring_generation,
    clear_tailoring_drafts,
    delete_tailoring_generation,
    get_application_generation_control,
    list_tailoring_generations,
    restore_tailoring_generation_as_draft,
    set_tailoring_section_locks,
)
from tailoring.generation_cleanup_ui_model import (
    CLEANUP_FILTER_OPTIONS,
    build_cleanup_rows,
    cleanup_option_label,
    filter_cleanup_versions,
    selected_cleanup_versions,
)
from tailoring.tailoring_generation_fingerprint import (
    compare_tailoring_generations,
    constrain_generation_control_to_phase9e,
    generation_matches_phase9e_binding,
    materialise_generation_for_display,
)
from database.tailoring_verification_manager import (
    get_latest_tailoring_verification,
)


def restore_generation_to_session(
    application_id: int,
    state: dict[str, Any],
) -> None:
    """Load the final fitted representation when one exists."""
    display_state = materialise_generation_for_display(state)
    values = {
        f"project_candidate_pool_{application_id}": state.get(
            "candidate_pool"
        ),
        f"debug_project_tailor_inputs_{application_id}": state.get(
            "project_inputs"
        ),
        f"tailored_projects_fit_{application_id}": state.get(
            "fit_estimate"
        ),
        f"tailored_projects_result_{application_id}": display_state.get(
            "projects"
        ),
        f"tailored_skills_result_{application_id}": display_state.get(
            "skills"
        ),
        f"tailored_resume_fit_result_{application_id}": state.get(
            "fit_result"
        ),
    }
    for key, value in values.items():
        if value is not None:
            st.session_state[key] = value
        else:
            st.session_state.pop(key, None)

    generation_id = str(state.get("generation_id") or "")
    if generation_id:
        st.session_state[
            f"tailored_generation_id_{application_id}"
        ] = generation_id

    docx_path = str(state.get("docx_path") or "")
    if docx_path and Path(docx_path).exists():
        st.session_state[
            f"tailored_resume_copy_path_{application_id}"
        ] = docx_path
    else:
        st.session_state.pop(
            f"tailored_resume_copy_path_{application_id}",
            None,
        )

    settings = state.get("generation_settings")
    st.session_state[
        f"restored_tailoring_settings_{application_id}"
    ] = dict(settings) if isinstance(settings, dict) else {}


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


def _recover_after_generation_deletion(
    *,
    application_id: int,
    deleted_generation_ids: list[str],
    approved_generation: dict[str, Any] | None,
) -> None:
    current_id = str(
        st.session_state.get(
            f"tailored_generation_id_{application_id}",
            "",
        )
    )
    if current_id not in set(deleted_generation_ids):
        return

    if isinstance(approved_generation, dict):
        restore_generation_to_session(application_id, approved_generation)
    else:
        _clear_generation_session_state(application_id)


def _lock_state_text(lock_projects: bool, lock_skills: bool) -> str:
    return (
        f"Projects: {'Locked' if lock_projects else 'Unlocked'} · "
        f"Skills: {'Locked' if lock_skills else 'Unlocked'}"
    )


def _label(state: dict[str, Any]) -> str:
    short_id = str(state.get("generation_id") or "")[:8]
    status = str(state.get("status") or "draft").title()
    updated = str(state.get("updated_at") or "")
    kind = str(state.get("generation_kind") or "manual")
    return f"{status} · {kind} · {short_id} · {updated}"


def _revision(versions: list[dict[str, Any]]) -> str:
    text = "|".join(
        f"{state.get('generation_id')}:{state.get('status')}:{state.get('updated_at')}"
        for state in versions
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _short_state(state: dict[str, Any] | None) -> str:
    if not isinstance(state, dict):
        return "None"
    return (
        f"{str(state.get('generation_id') or '')[:8]} "
        f"({str(state.get('status') or 'draft').title()})"
    )


def render_tailoring_section_update_scope(
    *,
    application_id: int,
    required_phase9e_binding: dict[str, Any] | None = None,
    disabled: bool = False,
) -> tuple[bool, bool, bool]:
    """Render generation-time section scope using existing persisted locks.

    Returns the persisted ``(lock_projects, lock_skills, dirty)`` state.
    Generation should fail closed while ``dirty`` is true so an unsaved UI
    choice cannot disagree with the lock provenance used by generation/fitting.
    """
    control = get_application_generation_control(application_id)
    if required_phase9e_binding:
        control = constrain_generation_control_to_phase9e(
            control,
            required_phase9e_binding,
        )

    approved = control.get("approved_generation")
    saved_lock_projects = bool(control.get("lock_projects"))
    saved_lock_skills = bool(control.get("lock_skills"))
    approved_key = (
        str(approved.get("generation_id") or "none")[:12]
        if isinstance(approved, dict)
        else "none"
    )

    st.write("#### Section update scope")
    st.caption(
        "Choose what the next tailoring generation may change. "
        "An unchecked section reuses the section from the current approved "
        "final fitted résumé."
    )

    if not isinstance(approved, dict):
        scope_col1, scope_col2 = st.columns(2)
        scope_col1.checkbox(
            "Update Projects",
            value=True,
            disabled=True,
            key=f"tailor_scope_projects_{application_id}_{approved_key}",
            help=(
                "There is no approved fitted Projects section to reuse yet."
            ),
        )
        scope_col2.checkbox(
            "Update Skills",
            value=True,
            disabled=True,
            key=f"tailor_scope_skills_{application_id}_{approved_key}",
            help=(
                "There is no approved fitted Skills section to reuse yet."
            ),
        )
        st.caption(
            "No approved fitted résumé is available to reuse yet, "
            "so both sections must be updated."
        )
        return False, False, False

    scope_col1, scope_col2 = st.columns(2)
    update_projects = scope_col1.checkbox(
        "Update Projects",
        value=not saved_lock_projects,
        disabled=disabled,
        key=f"tailor_scope_projects_{application_id}_{approved_key}",
        help=(
            "If unchecked, reuse Projects exactly from the current approved "
            "final fitted résumé. The fitter cannot compact or remove that "
            "reused Projects content."
        ),
    )
    update_skills = scope_col2.checkbox(
        "Update Skills",
        value=not saved_lock_skills,
        disabled=disabled,
        key=f"tailor_scope_skills_{application_id}_{approved_key}",
        help=(
            "If unchecked, reuse Skills exactly from the current approved "
            "final fitted résumé. The fitter cannot compact that reused "
            "Skills content."
        ),
    )

    proposed_lock_projects = not bool(update_projects)
    proposed_lock_skills = not bool(update_skills)
    dirty = (
        proposed_lock_projects != saved_lock_projects
        or proposed_lock_skills != saved_lock_skills
    )

    if dirty:
        st.warning(
            "The displayed update scope differs from the saved generation "
            "scope. Save it before generating or fitting."
        )
    else:
        st.caption(
            "Saved scope: "
            + (
                "Projects update"
                if not saved_lock_projects
                else "Projects reuse approved"
            )
            + " · "
            + (
                "Skills update"
                if not saved_lock_skills
                else "Skills reuse approved"
            )
        )

    if st.button(
        "Save Update Scope",
        key=f"tailor_scope_save_{application_id}_{approved_key}",
        disabled=disabled or not dirty,
        width="stretch",
    ):
        saved_control = set_tailoring_section_locks(
            application_id=application_id,
            lock_projects=proposed_lock_projects,
            lock_skills=proposed_lock_skills,
        )
        st.session_state[
            f"phase7_flash_{application_id}"
        ] = (
            "Saved section update scope. "
            + _lock_state_text(
                bool(saved_control.get("lock_projects")),
                bool(saved_control.get("lock_skills")),
            )
        )
        st.rerun()

    if (
        proposed_lock_projects
        and proposed_lock_skills
        and not dirty
    ):
        st.info(
            "Both sections will reuse the approved final fitted output. "
            "The combined action can load them without model calls."
        )

    return saved_lock_projects, saved_lock_skills, dirty


def render_tailoring_generation_controls(
    *,
    application_id: int,
    required_phase9e_binding: dict[str, Any] | None = None,
    workspace_managed: bool = False,
) -> None:
    all_versions = list_tailoring_generations(application_id)
    legacy_reuse_drafts = [
        state for state in all_versions
        if str(state.get("generation_kind") or "")
        == "phase9e_reuse_snapshot"
    ]
    all_versions = [
        state for state in all_versions if state not in legacy_reuse_drafts
    ]
    if required_phase9e_binding:
        versions = [
            state
            for state in all_versions
            if generation_matches_phase9e_binding(
                state, required_phase9e_binding
            )
        ]
        incompatible = [
            state for state in all_versions if state not in versions
        ]
    else:
        versions = all_versions
        incompatible = []
    st.divider()
    st.subheader(
        "Approval"
        if workspace_managed
        else "Versions and Approval"
    )

    if legacy_reuse_drafts and not workspace_managed:
        st.info(
            f"{len(legacy_reuse_drafts)} legacy Phase 9E unchanged-reuse "
            "draft(s) are preserved as historical records. They are not the "
            "current application result and are excluded from approval and "
            "promotion controls."
        )
        with st.expander("Legacy Phase 9E reuse drafts (historical only)"):
            st.dataframe(
                [
                    {
                        "Generation": state.get("generation_id"),
                        "Status": state.get("status"),
                        "Kind": state.get("generation_kind"),
                        "Updated": state.get("updated_at"),
                    }
                    for state in legacy_reuse_drafts
                ],
                hide_index=True,
                width="stretch",
            )

    if incompatible and not workspace_managed:
        st.info(
            f"{len(incompatible)} saved generation(s) belong to another "
            "Phase 9E starting source. They remain historical and inspectable "
            "below, but cannot be loaded, approved, regenerated, or modified "
            "under the current binding. Existing fitted exports remain downloadable."
        )
        with st.expander("Historical generations from other starting sources"):
            st.dataframe(
                [
                    {
                        "Generation": state.get("generation_id"),
                        "Status": state.get("status"),
                        "Kind": state.get("generation_kind"),
                        "Updated": state.get("updated_at"),
                    }
                    for state in incompatible
                ],
                hide_index=True,
                width="stretch",
            )
            historical_by_id = {
                str(state["generation_id"]): state for state in incompatible
            }
            historical_id = st.selectbox(
                "Inspect historical generation",
                options=list(historical_by_id),
                format_func=lambda value: _label(historical_by_id[value]),
                key=f"phase9e_historical_generation_{application_id}",
            )
            historical = historical_by_id[historical_id]
            st.json(materialise_generation_for_display(historical))
            historical_verification = get_latest_tailoring_verification(
                application_id, historical_id
            )
            if historical_verification is not None:
                st.write("**Historical Phase 8 verification**")
                st.json(historical_verification)
            for field, label, mime in (
                (
                    "docx_path",
                    "Download historical fitted DOCX",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ),
                ("pdf_path", "Download historical fitted PDF", "application/pdf"),
            ):
                historical_path = Path(str(historical.get(field) or ""))
                if historical_path.is_file():
                    st.download_button(
                        label,
                        data=historical_path.read_bytes(),
                        file_name=historical_path.name,
                        mime=mime,
                        key=(
                            f"phase9e_historical_{field}_{application_id}_"
                            f"{historical_id}"
                        ),
                    )

    if not versions:
        st.caption(
            "Generate Projects or Skills to create the first saved version."
        )
        return

    control = get_application_generation_control(application_id)
    if required_phase9e_binding:
        control = constrain_generation_control_to_phase9e(
            control, required_phase9e_binding
        )
    approved = control.get("approved_generation")
    by_id = {
        str(state["generation_id"]): state
        for state in versions
    }
    current_id = str(
        st.session_state.get(
            f"tailored_generation_id_{application_id}",
            "",
        )
    )
    loaded = by_id.get(current_id)

    if workspace_managed:
        st.write("#### Approval")
        if isinstance(loaded, dict):
            loaded_status = str(
                loaded.get("status") or "draft"
            ).lower()
            loaded_pages = (
                loaded.get("fit_result") or {}
            ).get("page_count")
            approval_cols = st.columns(3)
            approval_cols[0].caption("Working version")
            approval_cols[0].write(
                f"**{str(loaded.get('generation_id') or '')[:8]}**"
            )
            approval_cols[1].caption("Status")
            approval_cols[1].write(
                f"**{loaded_status.title()}**"
            )
            approval_cols[2].caption("Fit")
            approval_cols[2].write(
                "**Not fitted**"
                if loaded_pages in (None, "")
                else f"**{loaded_pages} page(s)**"
            )

            if loaded_status == "draft":
                if st.button(
                    "Approve current working draft",
                    key=f"phase7_approve_loaded_{application_id}",
                    type="primary",
                    width="stretch",
                ):
                    approve_tailoring_generation(
                        application_id,
                        str(loaded.get("generation_id") or ""),
                    )
                    st.session_state[
                        f"phase7_flash_{application_id}"
                    ] = (
                        "Approved the current working draft. Run Phase 8 "
                        "verification on the approved fitted résumé next."
                    )
                    st.rerun()
            elif (
                isinstance(approved, dict)
                and str(approved.get("generation_id") or "")
                == str(loaded.get("generation_id") or "")
            ):
                st.success(
                    "The résumé open in the workspace is already the active "
                    "approved result. No approval action is required."
                )
            else:
                st.info(
                    "The open version is not an editable current-scope draft. "
                    "Use the Résumé Workspace above to open a working draft."
                )
        elif isinstance(approved, dict):
            st.success(
                "An approved résumé is active, but no editable working draft "
                "is open. Use the Résumé Workspace above to revise it, create "
                "an alternative copy, or load a current-scope draft."
            )
        else:
            st.info(
                "No editable working draft is open. Use the Résumé Workspace "
                "above to load a current-scope draft before approval."
            )

    if not workspace_managed:
        st.write("#### Current state")
        state_col1, state_col2, state_col3 = st.columns(3)
        state_col1.info(
            "**Currently loaded**\n\n"
            + _short_state(loaded)
        )
        state_col2.success(
            "**Active approved**\n\n"
            + _short_state(approved)
        )
        lock_text = []
        if control.get("lock_projects"):
            lock_text.append("Projects")
        if control.get("lock_skills"):
            lock_text.append("Skills")
        state_col3.warning(
            "**Locked from approved final output**\n\n"
            + (", ".join(lock_text) if lock_text else "Nothing")
        )

        st.caption(
            "Loaded controls what is currently shown. Approved controls the trusted "
            "source for locks. A lock uses the final fitted Projects/Skills that "
            "appeared in the approved DOCX when available."
        )

        default_index = next(
            (
                index
                for index, state in enumerate(versions)
                if str(state["generation_id"]) == current_id
            ),
            0,
        )
        selected_id = st.selectbox(
            "Generation history",
            options=[str(state["generation_id"]) for state in versions],
            index=default_index,
            format_func=lambda value: _label(by_id[value]),
            key=(
                f"phase7_generation_history_{application_id}_"
                f"{_revision(versions)}"
            ),
        )
        selected = by_id[selected_id]

        status_col, fit_col, fingerprint_col = st.columns(3)
        status_col.metric(
            "Selected status",
            str(selected.get("status", "draft")).title(),
        )
        fit_col.metric(
            "Final pages",
            (selected.get("fit_result") or {}).get("page_count", "—"),
        )
        fingerprint_col.metric(
            "Fingerprint",
            "Stored" if selected.get("input_fingerprint") else "Not stored",
        )
        st.caption(
            "Fingerprint Stored means this version can be reused for an exact "
            "generation input. It does not mean the most recent click was a cache hit."
        )

        action_col1, action_col2, action_col3, action_col4 = st.columns(4)
        if action_col1.button(
            "Load Selected",
            key=f"phase7_load_{application_id}",
            width="stretch",
        ):
            restore_generation_to_session(application_id, selected)
            st.session_state[
                f"phase7_flash_{application_id}"
            ] = (
                "Loaded the selected version. Final fitted content is displayed "
                "when available."
            )
            st.rerun()

        if action_col2.button(
            "Approve Selected",
            key=f"phase7_approve_{application_id}",
            width="stretch",
            disabled=selected.get("status") == "approved",
        ):
            approve_tailoring_generation(application_id, selected_id)
            st.session_state[
                f"phase7_flash_{application_id}"
            ] = (
                "Approved the selected version. The previous approval was archived "
                "and locks were reset."
            )
            st.rerun()

        if action_col3.button(
            "Archive Selected",
            key=f"phase7_archive_{application_id}",
            width="stretch",
            disabled=selected.get("status") == "archived",
        ):
            archive_tailoring_generation(application_id, selected_id)
            st.session_state[
                f"phase7_flash_{application_id}"
            ] = "Archived the selected version; it remains in history."
            st.rerun()

        if action_col4.button(
            "Copy as Draft",
            key=f"phase7_restore_{application_id}",
            width="stretch",
        ):
            restored = restore_tailoring_generation_as_draft(
                application_id=application_id,
                source_generation_id=selected_id,
            )
            restore_generation_to_session(application_id, restored)
            st.session_state[
                f"phase7_flash_{application_id}"
            ] = "Copied the selected version into a new editable draft."
            st.rerun()

    st.write("#### Section update scope")
    saved_lock_projects = bool(control.get("lock_projects"))
    saved_lock_skills = bool(control.get("lock_skills"))
    scope_status_col1, scope_status_col2 = st.columns(2)
    scope_status_col1.metric(
        "Projects",
        (
            "Reuse approved final"
            if saved_lock_projects
            else "Update"
        ),
    )
    scope_status_col2.metric(
        "Skills",
        (
            "Reuse approved final"
            if saved_lock_skills
            else "Update"
        ),
    )
    if isinstance(approved, dict):
        st.caption(
            "Change this scope in Tailor Résumé Content before generating."
        )
    else:
        st.caption(
            "No approved fitted result is available to reuse yet."
        )

    if not workspace_managed:
        draft_versions = [
            state
            for state in versions
            if str(state.get("status") or "draft").lower() == "draft"
        ]
        archived_versions = [
            state
            for state in versions
            if str(state.get("status") or "").lower() == "archived"
        ]
        with st.expander("Cleanup saved versions", expanded=False):
            cleanup_col1, cleanup_col2 = st.columns(2)
            cleanup_col1.metric("Drafts", len(draft_versions))
            cleanup_col2.metric("Archived", len(archived_versions))
            st.caption(
                "Delete is permanent. Approved versions are protected. "
                "Use the list below to choose exactly which Draft or Archived "
                "versions to remove."
            )

            remove_files = st.checkbox(
                "Also remove unreferenced generated DOCX/PDF files",
                value=False,
                key=f"phase7_cleanup_files_{application_id}",
                help=(
                    "A file is deleted only when no remaining generation references "
                    "the same path. The uploaded source résumé is never deleted."
                ),
            )

            selected_tab, clear_tab = st.tabs(
                ["Delete selected versions", "Clear all Drafts"]
            )

            with selected_tab:
                status_filter = st.radio(
                    "Show versions",
                    options=CLEANUP_FILTER_OPTIONS,
                    horizontal=True,
                    key=f"phase7_cleanup_filter_{application_id}",
                )
                visible_cleanup_versions = filter_cleanup_versions(
                    versions,
                    status_filter,
                )
                visible_cleanup_by_id = {
                    str(state.get("generation_id") or ""): state
                    for state in visible_cleanup_versions
                }
                visible_cleanup_ids = list(visible_cleanup_by_id)

                if not visible_cleanup_versions:
                    st.info(
                        f"No {status_filter.lower()} versions are available "
                        "for deletion."
                    )
                else:
                    st.dataframe(
                        build_cleanup_rows(
                            visible_cleanup_versions,
                            loaded_generation_id=current_id,
                        ),
                        width="stretch",
                        hide_index=True,
                    )

                    selection_key = (
                        f"phase7_cleanup_selected_{application_id}_"
                        f"{_revision(versions)}"
                    )
                    select_all_col, clear_selection_col = st.columns(2)
                    if select_all_col.button(
                        "Select all visible",
                        key=f"phase7_cleanup_select_all_{application_id}",
                        width="stretch",
                    ):
                        st.session_state[selection_key] = visible_cleanup_ids
                        st.rerun()

                    if clear_selection_col.button(
                        "Clear selection",
                        key=f"phase7_cleanup_clear_selection_{application_id}",
                        width="stretch",
                    ):
                        st.session_state[selection_key] = []
                        st.rerun()

                    selected_cleanup_ids = st.multiselect(
                        "Versions to permanently delete",
                        options=visible_cleanup_ids,
                        format_func=lambda value: cleanup_option_label(
                            visible_cleanup_by_id[value]
                        ),
                        key=selection_key,
                        placeholder="Choose one or more saved versions",
                    )
                    selected_cleanup_states = selected_cleanup_versions(
                        visible_cleanup_versions,
                        selected_cleanup_ids,
                    )

                    if selected_cleanup_states:
                        st.write("**Deletion preview**")
                        st.dataframe(
                            build_cleanup_rows(
                                selected_cleanup_states,
                                loaded_generation_id=current_id,
                            ),
                            width="stretch",
                            hide_index=True,
                        )
                        selected_count = len(selected_cleanup_states)
                        selected_confirm = st.checkbox(
                            (
                                f"I understand that these {selected_count} "
                                "version(s) cannot be restored after deletion"
                            ),
                            value=False,
                            key=(
                                f"phase7_cleanup_confirm_selected_"
                                f"{application_id}_{_revision(versions)}"
                            ),
                        )
                        if st.button(
                            f"Delete {selected_count} Selected Version(s)",
                            type="secondary",
                            disabled=not selected_confirm,
                            key=(
                                f"phase7_cleanup_delete_selected_"
                                f"{application_id}_{_revision(versions)}"
                            ),
                        ):
                            deleted_ids: list[str] = []
                            for state in selected_cleanup_states:
                                generation_id = str(
                                    state.get("generation_id") or ""
                                )
                                delete_tailoring_generation(
                                    application_id=application_id,
                                    generation_id=generation_id,
                                    delete_unreferenced_files=remove_files,
                                )
                                deleted_ids.append(generation_id)

                            _recover_after_generation_deletion(
                                application_id=application_id,
                                deleted_generation_ids=deleted_ids,
                                approved_generation=approved,
                            )
                            st.session_state[
                                f"phase7_flash_{application_id}"
                            ] = (
                                f"Deleted {len(deleted_ids)} selected saved "
                                "version(s) permanently."
                            )
                            st.rerun()
                    else:
                        st.caption(
                            "Select at least one Draft or Archived version to "
                            "enable permanent deletion."
                        )

            with clear_tab:
                st.warning(
                    "This removes every Draft for this application in one action. "
                    "Approved and Archived versions are retained."
                )
                if draft_versions:
                    st.dataframe(
                        build_cleanup_rows(
                            draft_versions,
                            loaded_generation_id=current_id,
                        ),
                        width="stretch",
                        hide_index=True,
                    )
                else:
                    st.info("There are no Draft versions to clear.")

                clear_confirm = st.checkbox(
                    (
                        f"I understand that all {len(draft_versions)} Draft "
                        "version(s) will be permanently deleted"
                    ),
                    value=False,
                    disabled=not draft_versions,
                    key=f"phase7_clear_drafts_confirm_{application_id}",
                )
                if st.button(
                    "Clear All Drafts",
                    type="secondary",
                    disabled=not (draft_versions and clear_confirm),
                    key=f"phase7_clear_drafts_{application_id}",
                ):
                    result = clear_tailoring_drafts(
                        application_id=application_id,
                        delete_unreferenced_files=remove_files,
                    )
                    deleted_ids = [
                        str(value)
                        for value in result.get("deleted_generation_ids", [])
                    ]
                    _recover_after_generation_deletion(
                        application_id=application_id,
                        deleted_generation_ids=deleted_ids,
                        approved_generation=approved,
                    )
                    st.session_state[
                        f"phase7_flash_{application_id}"
                    ] = (
                        f"Deleted {int(result.get('deleted_count', 0))} Draft "
                        "version(s). Approved and Archived versions were retained."
                    )
                    st.rerun()

        if len(versions) >= 2:
            with st.expander("Compare two final outputs", expanded=False):
                compare_col1, compare_col2 = st.columns(2)
                left_id = compare_col1.selectbox(
                    "Older/base generation",
                    options=list(by_id),
                    index=min(1, len(by_id) - 1),
                    format_func=lambda value: _label(by_id[value]),
                    key=f"phase7_compare_left_{application_id}",
                )
                right_id = compare_col2.selectbox(
                    "Newer/target generation",
                    options=list(by_id),
                    index=0,
                    format_func=lambda value: _label(by_id[value]),
                    key=f"phase7_compare_right_{application_id}",
                )
                if left_id == right_id:
                    st.info("Choose two different generations.")
                else:
                    st.json(
                        compare_tailoring_generations(
                            by_id[left_id],
                            by_id[right_id],
                        )
                    )

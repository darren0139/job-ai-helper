"""Clear Streamlit controls for tailoring history, approval, and fitted locks."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import streamlit as st

from database.tailoring_generation_control import (
    approve_tailoring_generation,
    archive_tailoring_generation,
    get_application_generation_control,
    list_tailoring_generations,
    restore_tailoring_generation_as_draft,
    set_tailoring_section_locks,
)
from tailoring.tailoring_generation_fingerprint import (
    compare_tailoring_generations,
    materialise_generation_for_display,
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


def render_tailoring_generation_controls(
    *,
    application_id: int,
) -> None:
    versions = list_tailoring_generations(application_id)
    st.divider()
    st.subheader("Versions, Approval, and Section Locks")

    if not versions:
        st.caption(
            "Generate Projects or Skills to create the first saved version."
        )
        return

    control = get_application_generation_control(application_id)
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

    st.write("#### Lock approved final sections")
    approved_key = (
        str(approved.get("generation_id") or "none")[:12]
        if isinstance(approved, dict)
        else "none"
    )
    lock_projects = st.checkbox(
        "Lock approved Projects",
        value=bool(control.get("lock_projects")),
        disabled=not isinstance(approved, dict),
        key=f"phase7_lock_projects_{application_id}_{approved_key}",
        help=(
            "Reuses the Projects that appeared in the approved fitted DOCX. "
            "The fitter cannot compact, remove bullets from, or remove them."
        ),
    )
    lock_skills = st.checkbox(
        "Lock approved Skills",
        value=bool(control.get("lock_skills")),
        disabled=not isinstance(approved, dict),
        key=f"phase7_lock_skills_{application_id}_{approved_key}",
        help=(
            "Reuses the Skills that appeared in the approved fitted DOCX. "
            "The fitter cannot compact them."
        ),
    )
    if st.button(
        "Save Section Locks",
        key=f"phase7_save_locks_{application_id}",
        disabled=not isinstance(approved, dict),
    ):
        set_tailoring_section_locks(
            application_id=application_id,
            lock_projects=lock_projects,
            lock_skills=lock_skills,
        )
        st.session_state[
            f"phase7_flash_{application_id}"
        ] = "Saved the approved final-section locks."
        st.rerun()

    if lock_projects and lock_skills:
        st.info(
            "Both sections are locked. The main action should load the approved "
            "final content at no AI cost instead of creating a duplicate draft."
        )

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

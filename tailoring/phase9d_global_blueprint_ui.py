"""Streamlit page for Phase 9D global-blueprint approval and inspection."""

from __future__ import annotations

import json
from typing import Any

import streamlit as st

from database.blueprint_evaluation_manager import list_blueprint_evaluations
from database.global_blueprint_manager import (
    approve_persisted_phase9c_evaluation,
    list_global_blueprint_audit_events,
    list_global_blueprints,
    list_reusable_global_blueprints,
    remove_global_blueprint_from_reuse,
    restore_global_blueprint_to_reuse,
    update_global_blueprint_display_metadata,
)
from database.application_resume_result_manager import (
    create_editable_copy_from_current_application_result,
    get_current_application_resume_result,
)
from database.tailoring_generation_control import get_tailoring_generation
from tailoring.generation_controls_ui import restore_generation_to_session
from tailoring.phase9d_global_blueprint import (
    Phase9DApprovalError,
    evaluation_policy_status,
)
from tailoring.phase9f_starting_source_provenance import (
    Phase9FBProvenanceError,
    load_blueprint_provenance_read_only,
)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _evaluation_label(evaluation: dict[str, Any]) -> str:
    status = evaluation_policy_status(evaluation)
    semantic = evaluation.get("semantic_identity") or {}
    candidate = semantic.get("candidate") or {}
    policy = semantic.get("policy") or {}
    aggregate = evaluation.get("aggregate_result") or {}
    state = "Current" if status["approvable_policy"] else "Historical"
    provisional = "provisional" if aggregate.get("provisional") else "complete"
    return (
        f"[{state}] {candidate.get('role_family', 'Role family')} · "
        f"{provisional} · {policy.get('policy_version', 'unknown policy')} · "
        f"{str(evaluation.get('evaluation_id') or '')[:10]}"
    )


@st.dialog("Remove Blueprint from reuse")
def _confirm_blueprint_removal(blueprint: dict[str, Any]) -> None:
    st.warning(
        "This Blueprint will no longer be available for future recommendations "
        "or new starting-source selections, and it will be hidden from the "
        "normal Blueprint Library. Its immutable history, source Application, "
        "and provenance will be preserved."
    )
    st.write(
        f"**{_clean(blueprint.get('display_name')) or 'Global Blueprint'}** · "
        f"version {int(blueprint.get('version_number') or 0)}"
    )
    actor_label = st.text_input(
        "Removal actor label",
        value="Local user",
        key=f"phase9d_remove_actor_{blueprint['blueprint_id']}",
    )
    reason = st.text_area(
        "Removal reason (optional)",
        key=f"phase9d_remove_reason_{blueprint['blueprint_id']}",
    )
    acknowledgement = st.checkbox(
        "I understand that this removes the Blueprint from future reusable choices.",
        value=False,
        key=f"phase9d_remove_ack_{blueprint['blueprint_id']}",
    )
    if st.button(
        "Cancel",
        key=f"phase9d_cancel_remove_{blueprint['blueprint_id']}",
        width="stretch",
    ):
        st.session_state.pop("phase9d_pending_remove", None)
        st.rerun()
    if st.button(
        "Confirm removal",
        type="primary",
        disabled=not acknowledgement,
        key=f"phase9d_confirm_remove_{blueprint['blueprint_id']}",
        width="stretch",
    ):
        try:
            result = remove_global_blueprint_from_reuse(
                blueprint_id=blueprint["blueprint_id"],
                blueprint_fingerprint=blueprint["blueprint_fingerprint"],
                acknowledged=acknowledgement,
                actor_label=actor_label,
                reason=reason,
            )
        except (Phase9DApprovalError, ValueError, RuntimeError) as exc:
            st.error(str(exc))
            return
        st.session_state["phase9d_lifecycle_flash"] = (
            "Blueprint removed from future reuse. Historical provenance was preserved."
            if result["cache_status"] == "removed"
            else "This Blueprint was already removed; no duplicate event was created."
        )
        st.session_state.pop("phase9d_pending_remove", None)
        st.session_state["phase9d_force_show_history"] = True
        st.rerun()


@st.dialog("Restore Blueprint to reuse")
def _confirm_blueprint_restore(blueprint: dict[str, Any]) -> None:
    st.info(
        "Restore makes this exact immutable Blueprint eligible for future "
        "recommendations again. It does not create a version, alter content, "
        "or change Phase 9D activation/supersession history."
    )
    actor_label = st.text_input(
        "Restore actor label",
        value="Local user",
        key=f"phase9d_restore_actor_{blueprint['blueprint_id']}",
    )
    if st.button(
        "Cancel",
        key=f"phase9d_cancel_restore_{blueprint['blueprint_id']}",
        width="stretch",
    ):
        st.session_state.pop("phase9d_pending_restore", None)
        st.rerun()
    if st.button(
        "Confirm restore",
        type="primary",
        key=f"phase9d_confirm_restore_{blueprint['blueprint_id']}",
        width="stretch",
    ):
        try:
            result = restore_global_blueprint_to_reuse(
                blueprint_id=blueprint["blueprint_id"],
                blueprint_fingerprint=blueprint["blueprint_fingerprint"],
                actor_label=actor_label,
            )
        except (Phase9DApprovalError, ValueError, RuntimeError) as exc:
            st.error(str(exc))
            return
        st.session_state["phase9d_lifecycle_flash"] = (
            "Blueprint restored to future reusable choices."
            if result["cache_status"] == "restored"
            else "This Blueprint was already available; no duplicate event was created."
        )
        st.session_state.pop("phase9d_pending_restore", None)
        st.rerun()


def render_phase9d_global_blueprints(
    *, current_application_id: int | None = None
) -> None:
    st.header("Global Blueprints")
    st.caption(
        "Approve one exactly persisted Phase 9C evaluation as the reusable "
        "global blueprint for its role family. Approval never changes the "
        "candidate, evaluation, frozen résumé, or saved JD library."
    )
    lifecycle_flash = st.session_state.pop("phase9d_lifecycle_flash", "")
    if lifecycle_flash:
        st.success(lifecycle_flash)

    blueprints = list_global_blueprints(include_superseded=True)
    active = list_reusable_global_blueprints()
    st.subheader("Reusable role-family blueprints")
    if active:
        st.dataframe(
            [
                {
                    "Role family": row["role_family_label"],
                    "Version": row["version_number"],
                    "Display name": row["display_name"],
                    "Blueprint": row["blueprint_id"],
                    "Activated": row["activated_at"],
                }
                for row in active
            ],
            hide_index=True,
            width="stretch",
        )
    else:
        st.info("No reusable global blueprints are currently available.")

    st.divider()
    st.subheader("Approve a persisted Phase 9C evaluation")
    evaluations = list_blueprint_evaluations()
    if not evaluations:
        st.info("No persisted Phase 9C evaluations are available.")
    else:
        by_id = {
            str(evaluation.get("evaluation_id") or ""): evaluation
            for evaluation in evaluations
            if _clean(evaluation.get("evaluation_id"))
        }
        evaluation_id = st.selectbox(
            "Persisted Phase 9C evaluation",
            options=list(by_id),
            format_func=lambda value: _evaluation_label(by_id[value]),
            key="phase9d_evaluation_id",
        )
        evaluation = by_id[evaluation_id]
        policy_status = evaluation_policy_status(evaluation)
        aggregate = evaluation.get("aggregate_result") or {}
        semantic = evaluation.get("semantic_identity") or {}
        candidate_scope = semantic.get("candidate") or {}
        policy = semantic.get("policy") or {}

        summary = st.columns(4)
        summary[0].metric("Mean score", aggregate.get("mean_score", "—"))
        summary[1].metric(
            "Evaluated JDs", aggregate.get("evaluated_jd_count", 0)
        )
        summary[2].metric(
            "Status",
            "Provisional" if aggregate.get("provisional") else "Non-provisional",
        )
        summary[3].metric("Policy", policy.get("policy_version", "Unknown"))
        st.caption(
            f"Candidate {candidate_scope.get('candidate_id', '')} · "
            f"{candidate_scope.get('role_family', '')}"
        )

        if not policy_status["approvable_policy"]:
            st.warning(
                "This historical evaluation remains available for inspection "
                "but approval is disabled. "
                + "; ".join(policy_status["reasons"])
            )

        actor_label = st.text_input(
            "Approval actor label",
            value="Local user",
            key="phase9d_actor_label",
            help="Audit label only; this local app has no authenticated user identity.",
        )
        display_name = st.text_input(
            "Blueprint display name",
            value=_clean(candidate_scope.get("role_family")),
            key="phase9d_display_name",
            help="Editable display metadata; excluded from blueprint identity.",
        )
        notes = st.text_area(
            "Blueprint notes",
            value="",
            key="phase9d_notes",
            help="Editable display metadata; excluded from blueprint identity.",
        )

        provisional = aggregate.get("provisional") is True
        acknowledgement = False
        override_reason = ""
        if provisional:
            st.error(
                "This Phase 9C evaluation is provisional because its evaluated "
                "JD sample is below the non-provisional minimum."
            )
            acknowledgement = st.checkbox(
                "I understand that this approval uses a provisional Phase 9C scope.",
                value=False,
                key="phase9d_provisional_acknowledgement",
            )
            if acknowledgement:
                override_reason = (
                    "User explicitly acknowledged approval with a provisional "
                    "Phase 9C evaluated-JD scope."
                )

        approval_disabled = not policy_status["approvable_policy"] or (
            provisional and not acknowledgement
        )
        if st.button(
            "Approve or exactly reuse global blueprint",
            type="primary",
            key="phase9d_approve",
            disabled=approval_disabled,
        ):
            try:
                result = approve_persisted_phase9c_evaluation(
                    evaluation_id=evaluation_id,
                    evaluation_fingerprint=str(
                        evaluation.get("evaluation_fingerprint") or ""
                    ),
                    provisional_override={
                        "accepted": acknowledgement,
                        "reason": override_reason,
                    },
                    display_name=display_name,
                    notes=notes,
                    actor_label=actor_label,
                )
                st.session_state["phase9d_last_approval"] = result
                blueprint = result["blueprint"]
                status_messages = {
                    "miss": "Created and activated a new immutable blueprint version.",
                    "hit_active": "Exactly reused the already-active blueprint version.",
                    "hit_reactivated": (
                        "Reactivated the original exact blueprint version and "
                        "superseded the previously active version."
                    ),
                }
                st.success(status_messages[result["cache_status"]])
                st.write(
                    f"Blueprint `{blueprint['blueprint_id']}` · "
                    f"version {blueprint['version_number']}"
                )
                blueprints = list_global_blueprints(include_superseded=True)
            except (Phase9DApprovalError, ValueError, RuntimeError) as exc:
                st.error(str(exc))

        with st.expander("Inspect selected Phase 9C evaluation JSON"):
            st.json(evaluation)

    st.divider()
    st.subheader("Blueprint inspection")
    blueprints = list_global_blueprints(include_superseded=True)
    if not blueprints:
        st.caption("No Phase 9D versions are stored.")
        return
    reusable_ids = {
        row["blueprint_id"] for row in blueprints if row.get("is_reusable")
    }
    requested_id = _clean(
        st.session_state.get("phase9d_inspect_blueprint_id")
    )
    force_show_history = bool(
        st.session_state.pop("phase9d_force_show_history", False)
    )
    if force_show_history or (
        requested_id and requested_id not in reusable_ids
    ):
        st.session_state["phase9d_show_history"] = True
    show_history = st.toggle(
        "Show removed Blueprints and version history",
        key="phase9d_show_history",
    )
    inspection_rows = (
        blueprints
        if show_history
        else [row for row in blueprints if row.get("is_reusable")]
    )
    if not inspection_rows:
        st.info(
            "No reusable Blueprint is available in the normal library. "
            "Use the history toggle to inspect removed or superseded versions."
        )
        return
    st.dataframe(
        [
            {
                "Role family": row["role_family_label"],
                "Version": row["version_number"],
                "Lifecycle": row["status"],
                "Availability": row["availability_status"],
                "Blueprint": row["blueprint_id"],
                "Evaluation": row["evaluation_id"],
                "Activated": row["activated_at"],
            }
            for row in inspection_rows
        ],
        hide_index=True,
        width="stretch",
    )
    by_blueprint_id = {
        row["blueprint_id"]: row for row in inspection_rows
    }
    selected_blueprint_id = st.selectbox(
        "Inspect blueprint version",
        options=list(by_blueprint_id),
        format_func=lambda value: (
            f"{by_blueprint_id[value]['role_family_label']} · "
            f"v{by_blueprint_id[value]['version_number']} · "
            f"{by_blueprint_id[value]['status']} / "
            f"{by_blueprint_id[value]['availability_status']}"
        ),
        key="phase9d_inspect_blueprint_id",
    )
    selected = by_blueprint_id[selected_blueprint_id]
    if selected.get("is_reusable"):
        if st.button(
            "Remove Blueprint",
            key=f"phase9d_remove_{selected_blueprint_id}",
        ):
            st.session_state["phase9d_pending_remove"] = selected_blueprint_id
        if (
            st.session_state.get("phase9d_pending_remove")
            == selected_blueprint_id
        ):
            _confirm_blueprint_removal(selected)
    elif selected.get("availability_status") == "removed":
        if selected.get("status") == "active":
            if st.button(
                "Restore Blueprint",
                key=f"phase9d_restore_{selected_blueprint_id}",
            ):
                st.session_state["phase9d_pending_restore"] = (
                    selected_blueprint_id
                )
            if (
                st.session_state.get("phase9d_pending_restore")
                == selected_blueprint_id
            ):
                _confirm_blueprint_restore(selected)
        else:
            st.warning(
                "Restore is unavailable because this removed version has since "
                "been superseded. Restore never reactivates or supersedes versions."
            )
            st.button(
                "Restore Blueprint",
                disabled=True,
                key=f"phase9d_restore_disabled_{selected_blueprint_id}",
            )
    st.info(
        "Global Blueprint content is immutable. Content changes require an "
        "explicit editable application copy, a materially changed fitted and "
        "verified output, and a new Phase 9B–9D version workflow."
    )
    current_result = (
        get_current_application_resume_result(
            int(current_application_id), validate_artifacts=False
        )
        if current_application_id is not None
        else None
    )
    if (
        current_result is not None
        and current_result.get("blueprint_id") == selected_blueprint_id
    ):
        if st.button(
            "Create editable copy for the open application",
            key=f"phase9d_editable_copy_{selected_blueprint_id}",
        ):
            created = create_editable_copy_from_current_application_result(
                application_id=int(current_application_id),
                actor_label="Local user",
            )
            editable = get_tailoring_generation(
                int(current_application_id), created["generation_id"]
            )
            if editable is None:
                raise RuntimeError("The editable copy could not be reloaded.")
            restore_generation_to_session(
                int(current_application_id), editable
            )
            st.session_state["navigation_page"] = "Application Sessions"
            st.rerun()
    export = {
        "blueprint": selected,
        "audit_events": list_global_blueprint_audit_events(
            blueprint_id=selected_blueprint_id
        ),
    }
    with st.expander("Standalone blueprint JSON", expanded=False):
        st.json(export)
    with st.expander("View immutable source provenance", expanded=False):
        try:
            st.json(load_blueprint_provenance_read_only(selected))
        except (Phase9FBProvenanceError, OSError, ValueError) as exc:
            st.warning(
                "The immutable Blueprint remains inspectable, but one or more "
                f"source provenance links could not be resolved: {exc}"
            )
    st.download_button(
        "Download Phase 9D blueprint JSON",
        data=json.dumps(export, ensure_ascii=False, indent=2, default=str),
        file_name=f"phase9d_{selected_blueprint_id[:12]}.json",
        mime="application/json",
        key="phase9d_download",
    )

    if selected.get("availability_status") == "removed":
        st.caption(
            "Removed Blueprint provenance is read-only. Restore it before "
            "changing display metadata."
        )
        return

    st.write("**Editable display metadata**")
    edited_name = st.text_input(
        "Display name",
        value=selected["display_name"],
        key=f"phase9d_edit_name_{selected_blueprint_id}",
    )
    edited_notes = st.text_area(
        "Notes",
        value=selected["notes"],
        key=f"phase9d_edit_notes_{selected_blueprint_id}",
    )
    metadata_actor = st.text_input(
        "Metadata editor label",
        value="Local user",
        key=f"phase9d_metadata_actor_{selected_blueprint_id}",
    )
    if st.button(
        "Save display metadata",
        key=f"phase9d_save_metadata_{selected_blueprint_id}",
    ):
        updated = update_global_blueprint_display_metadata(
            blueprint_id=selected_blueprint_id,
            display_name=edited_name,
            notes=edited_notes,
            actor_label=metadata_actor,
        )
        st.success("Updated display metadata without changing blueprint identity.")
        st.session_state["phase9d_last_metadata_update"] = updated

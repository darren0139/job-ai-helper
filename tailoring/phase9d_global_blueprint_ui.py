"""Streamlit page for Phase 9D global-blueprint approval and inspection."""

from __future__ import annotations

import json
from typing import Any

import streamlit as st

from database.blueprint_evaluation_manager import list_blueprint_evaluations
from database.global_blueprint_manager import (
    PRIMARY_BLUEPRINT_VARIANT_ID,
    PRIMARY_BLUEPRINT_VARIANT_LABEL,
    VARIANT_INTENT_CREATE_NEW,
    VARIANT_INTENT_INITIAL_PRIMARY,
    VARIANT_INTENT_UPDATE_EXISTING,
    approve_persisted_phase9c_evaluation,
    get_persisted_blueprint_candidate,
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
from tailoring.phase9d_variant_tags import (
    AVAILABLE_VARIANT_TAGS,
    derive_candidate_variant_tag_scores,
    suggest_blueprint_variant_lane,
    variant_tags_from_label,
)
from database.global_blueprint_tag_manager import (
    GENERALIST_TAG_ID,
    get_blueprint_lane_tags,
    init_global_blueprint_tag_registry,
    list_blueprint_tags,
    resolve_blueprint_tag_ids,
    set_blueprint_lane_tags,
)
from tailoring.phase9d_blueprint_library_debug import (
    blueprint_library_debug_json,
    build_blueprint_library_debug_payload,
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
    aggregate = evaluation.get("aggregate_result") or {}
    state = (
        "Approvable"
        if status["approvable_policy"]
        else "Legacy · read-only"
    )
    provisional = "provisional" if aggregate.get("provisional") else "complete"
    evaluated_count = int(aggregate.get("evaluated_jd_count") or 0)
    target_word = "target JD" if evaluated_count == 1 else "target JDs"
    return (
        f"[{state}] {candidate.get('role_family', 'Role family')} · "
        f"{provisional} · {evaluated_count} {target_word} · "
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


def _render_blueprint_library_debug_panel(
    *, current_application_id: int | None
) -> None:
    with st.expander("Blueprint Library debug", expanded=False):
        st.caption(
            "Generate one read-only JSON snapshot of the data driving this "
            "Blueprint Library page: Phase 9C evaluations, Blueprint versions, "
            "reusable lanes, audit events, selected candidate/tag diagnostics, "
            "selected Blueprint provenance, and Blueprint-specific UI state."
        )
        st.caption(
            "The export intentionally does not dump the complete Streamlit "
            "session state, so unrelated app state or secrets are not included."
        )
        if st.button(
            "Generate Blueprint Library debug",
            key="phase9d_generate_blueprint_library_debug",
        ):
            debug_page_state = {
                "evaluation_id": st.session_state.get(
                    "phase9d_evaluation_id", ""
                ),
                "show_nonpending_evaluations": bool(
                    st.session_state.get(
                        "phase9d_show_nonpending_evaluations", False
                    )
                ),
                "review_evaluation_id": st.session_state.get(
                    "phase9d_review_evaluation_id", ""
                ),
                "confirmed_variant_tags": list(
                    st.session_state.get("phase9d_variant_tags", []) or []
                ),
                "variant_intent": st.session_state.get(
                    "phase9d_variant_intent", ""
                ),
                "existing_variant_id": st.session_state.get(
                    "phase9d_existing_variant_id", ""
                ),
                "new_variant_label": st.session_state.get(
                    "phase9d_new_variant_label", ""
                ),
                "provisional_acknowledgement": bool(
                    st.session_state.get(
                        "phase9d_provisional_acknowledgement",
                        False,
                    )
                ),
                "show_history": bool(
                    st.session_state.get("phase9d_show_history", False)
                ),
                "inspect_blueprint_id": st.session_state.get(
                    "phase9d_inspect_blueprint_id", ""
                ),
                "lane_metadata_edit_context": st.session_state.get(
                    "phase9d_edit_lane_context", ""
                ),
                "display_metadata_edit_blueprint_id": st.session_state.get(
                    "phase9d_edit_display_blueprint_id", ""
                ),
            }
            debug_payload = build_blueprint_library_debug_payload(
                current_application_id=current_application_id,
                page_state=debug_page_state,
            )
            st.session_state[
                "phase9d_blueprint_library_debug_json"
            ] = blueprint_library_debug_json(debug_payload)
            st.success(
                "Blueprint Library debug snapshot generated. "
                "Regenerate it after changing the page state."
            )

        debug_json = st.session_state.get(
            "phase9d_blueprint_library_debug_json", ""
        )
        if debug_json:
            st.download_button(
                "Download Blueprint Library debug JSON",
                data=debug_json,
                file_name="blueprint_library_debug.json",
                mime="application/json",
                key="phase9d_download_blueprint_library_debug",
            )
            st.caption(
                f"Generated debug size: "
                f"{len(debug_json.encode('utf-8')):,} bytes"
            )
            show_debug_preview = st.checkbox(
                "Show generated debug preview",
                value=False,
                key="phase9d_show_blueprint_library_debug_preview",
            )
            if show_debug_preview:
                try:
                    st.json(json.loads(debug_json))
                except json.JSONDecodeError:
                    st.error(
                        "The generated debug snapshot could not be decoded. "
                        "Regenerate it."
                    )



def _clear_phase9d_approval_review_state() -> None:
    """Clear transient approval-review widgets without touching library state."""
    for key in (
        "phase9d_review_evaluation_id",
        "phase9d_variant_intent",
        "phase9d_existing_variant_id",
        "phase9d_new_variant_label",
        "phase9d_new_variant_label_context",
        "phase9d_variant_tags",
        "phase9d_variant_tag_context",
        "phase9d_actor_label",
        "phase9d_display_name",
        "phase9d_notes",
        "phase9d_provisional_acknowledgement",
    ):
        st.session_state.pop(key, None)


def render_phase9d_global_blueprints(
    *, current_application_id: int | None = None
) -> None:
    init_global_blueprint_tag_registry()
    st.header("Global Blueprints")
    st.caption(
        "Approve persisted Phase 9C evaluations as reusable Blueprint "
        "variants. A role family may have multiple active variant lanes, "
        "while each lane supersedes independently. Removal/restoration "
        "availability remains separate from lifecycle activation. Approval "
        "never changes the candidate, evaluation, frozen résumé, or saved "
        "JD library."
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
                    "Variant": row.get("variant_label", "Primary"),
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
    st.subheader("Blueprint approval")
    evaluations = list_blueprint_evaluations()

    approved_by_evaluation: dict[str, list[dict[str, Any]]] = {}
    for blueprint_row in blueprints:
        blueprint_evaluation_id = _clean(blueprint_row.get("evaluation_id"))
        if blueprint_evaluation_id:
            approved_by_evaluation.setdefault(
                blueprint_evaluation_id,
                [],
            ).append(dict(blueprint_row))

    ready_evaluations = [
        evaluation_row
        for evaluation_row in evaluations
        if evaluation_policy_status(evaluation_row)["approvable_policy"]
        and _clean(evaluation_row.get("evaluation_id"))
        not in approved_by_evaluation
    ]

    if ready_evaluations:
        st.caption(
            f"{len(ready_evaluations)} Phase 9C evaluation"
            f"{'' if len(ready_evaluations) == 1 else 's'} ready for review."
        )
    else:
        st.info(
            "No Phase 9C evaluations currently need approval. Previously "
            "approved and legacy evaluations remain available for inspection."
        )

    show_nonpending_evaluations = st.checkbox(
        "Show previously approved and legacy evaluations",
        value=False,
        key="phase9d_show_nonpending_evaluations",
        help=(
            "Legacy evaluations are read-only. Previously approved evaluations "
            "can be inspected and deliberately reopened from Advanced controls."
        ),
    )
    visible_evaluations = (
        list(evaluations)
        if show_nonpending_evaluations
        else list(ready_evaluations)
    )

    if not evaluations:
        st.info("No persisted Phase 9C evaluations are available.")
    elif visible_evaluations:
        by_id = {
            _clean(evaluation.get("evaluation_id")): evaluation
            for evaluation in visible_evaluations
            if _clean(evaluation.get("evaluation_id"))
        }
        current_evaluation_id = _clean(
            st.session_state.get("phase9d_evaluation_id")
        )
        if current_evaluation_id not in by_id:
            st.session_state["phase9d_evaluation_id"] = next(iter(by_id))

        def _visible_evaluation_label(value: str) -> str:
            evaluation_row = by_id[value]
            approved_rows = approved_by_evaluation.get(value) or []
            if not approved_rows:
                return _evaluation_label(evaluation_row)
            newest = sorted(
                approved_rows,
                key=lambda row: (
                    int(row.get("version_number", 0) or 0),
                    _clean(row.get("activated_at")),
                ),
                reverse=True,
            )[0]
            semantic_row = evaluation_row.get("semantic_identity") or {}
            candidate_row = semantic_row.get("candidate") or {}
            aggregate_row = evaluation_row.get("aggregate_result") or {}
            provisional_label = (
                "provisional"
                if aggregate_row.get("provisional")
                else "complete"
            )
            return (
                f"[Approved] {candidate_row.get('role_family', 'Role family')} · "
                f"{newest.get('variant_label', 'Primary')} "
                f"v{newest.get('version_number', 0)} · {provisional_label}"
            )

        evaluation_id = st.selectbox(
            "Phase 9C evaluation",
            options=list(by_id),
            format_func=_visible_evaluation_label,
            key="phase9d_evaluation_id",
            help=(
                "Approvable means the evaluation uses the current Phase 9C "
                "approval contract. Legacy means it is preserved for read-only "
                "inspection and cannot be newly approved."
            ),
        )
        evaluation = by_id[evaluation_id]
        policy_status = evaluation_policy_status(evaluation)
        aggregate = evaluation.get("aggregate_result") or {}
        semantic = evaluation.get("semantic_identity") or {}
        candidate_scope = semantic.get("candidate") or {}
        policy = semantic.get("policy") or {}
        approved_for_evaluation = sorted(
            approved_by_evaluation.get(evaluation_id) or [],
            key=lambda row: (
                int(row.get("version_number", 0) or 0),
                _clean(row.get("activated_at")),
            ),
            reverse=True,
        )
        selected_approved_blueprint = (
            approved_for_evaluation[0]
            if approved_for_evaluation
            else None
        )

        summary = st.columns(3)
        summary[0].metric("Phase 9C score", aggregate.get("mean_score", "—"))
        summary[1].metric(
            "Target sample",
            aggregate.get("evaluated_jd_count", 0),
        )
        summary[2].metric(
            "Status",
            "Provisional"
            if aggregate.get("provisional")
            else "Non-provisional",
        )
        st.caption(
            f"{candidate_scope.get('role_family', 'Role family')} · "
            f"Candidate {str(candidate_scope.get('candidate_id') or '')[:12]}"
        )

        role_family_id = _clean(candidate_scope.get("role_family_id"))
        active_family_lanes = sorted(
            [
                dict(row)
                for row in blueprints
                if _clean(row.get("role_family_id")) == role_family_id
                and _clean(row.get("status")) == "active"
            ],
            key=lambda row: (
                _clean(row.get("variant_id")),
                int(row.get("version_number", 0) or 0),
            ),
        )
        active_tag_library = list_blueprint_tags(include_inactive=False)
        candidate_tag_options = [
            row["label"]
            for row in active_tag_library
            if row["tag_id"] != GENERALIST_TAG_ID
        ]
        for lane in active_family_lanes:
            persisted = get_blueprint_lane_tags(
                role_family_id=_clean(lane.get("role_family_id")),
                variant_id=_clean(lane.get("variant_id")),
            )
            lane["persisted_tags"] = [row["label"] for row in persisted]

        candidate_snapshot: dict[str, Any] | None = None
        automatic_suggestion: dict[str, Any] | None = None
        automatic_tag_names: list[str] = []
        candidate_error = ""
        try:
            candidate_snapshot = get_persisted_blueprint_candidate(
                _clean(candidate_scope.get("candidate_id"))
            )
            automatic_suggestion = suggest_blueprint_variant_lane(
                candidate=candidate_snapshot,
                active_family_lanes=active_family_lanes,
            )
            automatic_tag_names = [
                str(row.get("tag") or "")
                for row in automatic_suggestion.get("automatic_tags") or []
                if _clean(row.get("tag"))
                and str(row.get("tag") or "") in candidate_tag_options
            ]
        except (Phase9DApprovalError, ValueError, RuntimeError) as exc:
            candidate_error = str(exc)

        review_open = (
            policy_status["approvable_policy"]
            and st.session_state.get("phase9d_review_evaluation_id")
            == evaluation_id
        )

        if not policy_status["approvable_policy"]:
            if st.session_state.get("phase9d_review_evaluation_id") == evaluation_id:
                _clear_phase9d_approval_review_state()
            st.warning(
                "Legacy · read-only. This evaluation is preserved for "
                "inspection but cannot be newly approved under the current "
                "Phase 9C contract."
            )
            if policy_status["reasons"]:
                st.caption("; ".join(policy_status["reasons"]))
        elif selected_approved_blueprint is not None and not review_open:
            st.success(
                "Already approved → "
                f"{selected_approved_blueprint.get('variant_label', 'Primary')} "
                f"· v{selected_approved_blueprint.get('version_number', 0)} · "
                f"{selected_approved_blueprint.get('status', 'unknown')} / "
                f"{selected_approved_blueprint.get('availability_status', 'unknown')}"
            )
            st.caption(
                "The normal approval form stays closed because this exact "
                "Phase 9C evaluation has already produced a Blueprint."
            )
            if st.button(
                "Select approved Blueprint in inspection",
                key="phase9d_select_approved_blueprint",
            ):
                st.session_state["phase9d_inspect_blueprint_id"] = (
                    selected_approved_blueprint["blueprint_id"]
                )
                st.rerun()
            with st.expander("Advanced", expanded=False):
                st.warning(
                    "Reusing an already-approved evaluation is an advanced "
                    "lifecycle action. Continue only when you intentionally "
                    "want another explicit Blueprint action from the same "
                    "immutable evaluation."
                )
                if st.button(
                    "Use this evaluation again...",
                    key="phase9d_use_evaluation_again",
                ):
                    _clear_phase9d_approval_review_state()
                    st.session_state["phase9d_review_evaluation_id"] = (
                        evaluation_id
                    )
                    st.rerun()
        elif not review_open:
            if candidate_error:
                st.warning(
                    "Variant recommendation is unavailable: " + candidate_error
                )
            else:
                st.write(
                    "**Detected specialization:** "
                    + (
                        " · ".join(automatic_tag_names)
                        if automatic_tag_names
                        else "Generalist / unclear"
                    )
                )
                recommendation = (
                    automatic_suggestion.get("recommendation") or {}
                    if automatic_suggestion is not None
                    else {}
                )
                recommended_intent = _clean(recommendation.get("intent"))
                recommended_lane = (
                    _clean(recommendation.get("variant_label"))
                    or _clean(
                        automatic_suggestion.get("suggested_label")
                        if automatic_suggestion is not None
                        else ""
                    )
                    or "Primary"
                )
                if recommended_intent == VARIANT_INTENT_UPDATE_EXISTING:
                    recommended_action = "Update existing lane"
                elif recommended_intent == VARIANT_INTENT_CREATE_NEW:
                    recommended_action = "Create new variant"
                else:
                    recommended_action = "Create initial Primary lane"
                st.write(f"**Recommended lane:** {recommended_lane}")
                st.write(f"**Recommended action:** {recommended_action}")

            if st.button(
                "Review approval",
                type="primary",
                key="phase9d_review_approval",
            ):
                _clear_phase9d_approval_review_state()
                st.session_state["phase9d_review_evaluation_id"] = evaluation_id
                st.rerun()

        if review_open:
            if selected_approved_blueprint is not None:
                st.warning(
                    "This evaluation was already approved. Continue only if "
                    "you intentionally want to reuse it for another explicit "
                    "Blueprint lifecycle action."
                )

            st.markdown("#### Review Blueprint approval")
            actor_label = st.text_input(
                "Approval actor label",
                value="Local user",
                key="phase9d_actor_label",
                help=(
                    "Audit label only; this local app has no authenticated "
                    "user identity."
                ),
            )
            display_name = st.text_input(
                "Blueprint display name",
                value=_clean(candidate_scope.get("role_family")),
                key="phase9d_display_name",
                help="Editable display metadata; excluded from Blueprint identity.",
            )

            variant_suggestion: dict[str, Any] | None = None
            confirmed_variant_tags: list[str] = []
            if candidate_snapshot is not None:
                st.write("**Variant specialization**")
                st.caption(
                    "Automatically detected: "
                    + (
                        " · ".join(automatic_tag_names)
                        if automatic_tag_names
                        else "Generalist / unclear"
                    )
                )
                with st.expander("Why these tags?", expanded=False):
                    scored_rows = derive_candidate_variant_tag_scores(
                        candidate_snapshot
                    )
                    st.dataframe(
                        [
                            {
                                "Tag": row.get("tag"),
                                "Score": row.get("score"),
                                "Auto selected": (
                                    "Yes"
                                    if row.get("tag") in automatic_tag_names
                                    else "No"
                                ),
                                "Signals": ", ".join(
                                    str(value)
                                    for value in row.get("signals") or []
                                ),
                            }
                            for row in scored_rows
                        ],
                        hide_index=True,
                        width="stretch",
                    )

                tag_context = (
                    f"{evaluation_id}:"
                    f"{_clean(candidate_scope.get('candidate_id'))}"
                )
                if (
                    st.session_state.get("phase9d_variant_tag_context")
                    != tag_context
                    or "phase9d_variant_tags" not in st.session_state
                ):
                    st.session_state["phase9d_variant_tags"] = list(
                        automatic_tag_names
                    )
                    st.session_state["phase9d_variant_tag_context"] = tag_context

                confirmed_variant_tags = st.multiselect(
                    "Confirmed variant tags",
                    options=candidate_tag_options,
                    key="phase9d_variant_tags",
                    help=(
                        "These tags drive the lane recommendation. Add or remove "
                        "tags before choosing a lifecycle action."
                    ),
                )
                variant_suggestion = suggest_blueprint_variant_lane(
                    candidate=candidate_snapshot,
                    active_family_lanes=active_family_lanes,
                    selected_tags=confirmed_variant_tags,
                )

            st.write("**Existing active Blueprint lanes**")
            if active_family_lanes:
                st.dataframe(
                    [
                        {
                            "Lane": row.get(
                                "variant_label",
                                PRIMARY_BLUEPRINT_VARIANT_LABEL,
                            ),
                            "Tags": ", ".join(row.get("persisted_tags") or [])
                            or (
                                "Generalist"
                                if _clean(row.get("variant_id")) == "primary"
                                else "Unclassified"
                            ),
                            "Version": row.get("version_number"),
                            "Blueprint": row.get("blueprint_id"),
                            "Availability": row.get("availability_status"),
                        }
                        for row in active_family_lanes
                    ],
                    hide_index=True,
                    width="stretch",
                )
            else:
                st.info(
                    "No active Blueprint lane exists for this role family. "
                    "Approval will create the initial Primary lane."
                )

            recommendation = (
                variant_suggestion.get("recommendation") or {}
                if variant_suggestion is not None
                else (
                    automatic_suggestion.get("recommendation") or {}
                    if automatic_suggestion is not None
                    else {}
                )
            )
            recommended_intent = _clean(recommendation.get("intent"))
            recommended_lane = (
                _clean(recommendation.get("variant_label"))
                or _clean(
                    variant_suggestion.get("suggested_label")
                    if variant_suggestion is not None
                    else (
                        automatic_suggestion.get("suggested_label")
                        if automatic_suggestion is not None
                        else ""
                    )
                )
                or "Primary"
            )
            reason = _clean(recommendation.get("reason"))
            if recommended_intent == VARIANT_INTENT_UPDATE_EXISTING:
                st.info(f"Recommended: **Update {recommended_lane}**. {reason}")
            elif recommended_intent == VARIANT_INTENT_CREATE_NEW:
                st.info(
                    f"Recommended: **Create new variant {recommended_lane}**. "
                    f"{reason}"
                )
            elif reason:
                st.info(reason)

            variant_intent = VARIANT_INTENT_INITIAL_PRIMARY
            variant_id = PRIMARY_BLUEPRINT_VARIANT_ID
            variant_label = PRIMARY_BLUEPRINT_VARIANT_LABEL
            selected_intent: str | None = None

            if active_family_lanes:
                selected_intent = st.radio(
                    "Choose lifecycle action",
                    options=(
                        VARIANT_INTENT_CREATE_NEW,
                        VARIANT_INTENT_UPDATE_EXISTING,
                    ),
                    index=None,
                    format_func=lambda value: (
                        "Create new variant"
                        if value == VARIANT_INTENT_CREATE_NEW
                        else "Update existing variant lane"
                    ),
                    key="phase9d_variant_intent",
                    horizontal=True,
                    help=(
                        "No action is preselected. The recommendation above is "
                        "advisory; choose explicitly before approval."
                    ),
                )
                variant_intent = selected_intent or ""

                if selected_intent == VARIANT_INTENT_CREATE_NEW:
                    suggested_new_label = ""
                    if (
                        variant_suggestion is not None
                        and recommended_intent == VARIANT_INTENT_CREATE_NEW
                    ):
                        suggested_new_label = _clean(
                            variant_suggestion.get("suggested_label")
                        )
                    label_context = (
                        f"{evaluation_id}:" + ",".join(confirmed_variant_tags)
                    )
                    if (
                        st.session_state.get(
                            "phase9d_new_variant_label_context"
                        )
                        != label_context
                        or "phase9d_new_variant_label" not in st.session_state
                    ):
                        st.session_state["phase9d_new_variant_label"] = (
                            suggested_new_label
                        )
                        st.session_state[
                            "phase9d_new_variant_label_context"
                        ] = label_context
                    variant_id = ""
                    variant_label = st.text_input(
                        "New Blueprint variant label",
                        key="phase9d_new_variant_label",
                        help=(
                            "Required. Creating a new lane never supersedes "
                            "another active lane."
                        ),
                    )
                elif selected_intent == VARIANT_INTENT_UPDATE_EXISTING:
                    lane_by_id = {
                        _clean(row.get("variant_id")): row
                        for row in active_family_lanes
                    }
                    lane_options = list(lane_by_id)
                    recommended_variant_id = (
                        _clean(recommendation.get("variant_id"))
                        if recommended_intent == VARIANT_INTENT_UPDATE_EXISTING
                        else ""
                    )
                    selected_index = (
                        lane_options.index(recommended_variant_id)
                        if recommended_variant_id in lane_options
                        else 0
                    )
                    variant_id = st.selectbox(
                        "Existing variant lane to update",
                        options=lane_options,
                        index=selected_index,
                        format_func=lambda value: (
                            f"{lane_by_id[value].get('variant_label', PRIMARY_BLUEPRINT_VARIANT_LABEL)} "
                            f"· v{lane_by_id[value].get('version_number')} · "
                            f"{str(lane_by_id[value].get('blueprint_id') or '')[:12]}"
                        ),
                        key="phase9d_existing_variant_id",
                    )
                    variant_label = (
                        _clean(lane_by_id[variant_id].get("variant_label"))
                        or PRIMARY_BLUEPRINT_VARIANT_LABEL
                    )
                    st.warning(
                        "Approval supersedes only the selected variant lane. "
                        "All other active variants remain active."
                    )

            notes = st.text_area(
                "Blueprint notes",
                value="",
                key="phase9d_notes",
                help="Editable display metadata; excluded from Blueprint identity.",
            )

            provisional = aggregate.get("provisional") is True
            acknowledgement = False
            override_reason = ""
            if provisional:
                st.error(
                    "This Phase 9C evaluation is provisional because its "
                    "evaluated-JD sample is below the non-provisional minimum."
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

            missing_explicit_intent = (
                bool(active_family_lanes)
                and selected_intent is None
            )
            invalid_new_variant_label = (
                variant_intent == VARIANT_INTENT_CREATE_NEW
                and not _clean(variant_label)
            )
            approval_disabled = (
                not policy_status["approvable_policy"]
                or missing_explicit_intent
                or (provisional and not acknowledgement)
                or invalid_new_variant_label
            )

            actions = st.columns(2)
            approve_clicked = actions[0].button(
                "Approve or exactly reuse global Blueprint",
                type="primary",
                key="phase9d_approve",
                disabled=approval_disabled,
                width="stretch",
            )
            cancel_clicked = actions[1].button(
                "Cancel review",
                key="phase9d_cancel_review",
                width="stretch",
            )
            if cancel_clicked:
                _clear_phase9d_approval_review_state()
                st.rerun()

            if approve_clicked:
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
                        variant_intent=variant_intent,
                        variant_id=variant_id,
                        variant_label=variant_label,
                        display_name=display_name,
                        notes=notes,
                        actor_label=actor_label,
                    )
                    st.session_state["phase9d_last_approval"] = result
                    blueprint = result["blueprint"]
                    if result.get("cache_status") == "miss":
                        if _clean(blueprint.get("variant_id")) == "primary":
                            set_blueprint_lane_tags(
                                role_family_id=_clean(
                                    blueprint.get("role_family_id")
                                ),
                                variant_id="primary",
                                tag_ids=[GENERALIST_TAG_ID],
                                actor_label=actor_label,
                            )
                        elif (
                            variant_intent == VARIANT_INTENT_CREATE_NEW
                            and confirmed_variant_tags
                        ):
                            set_blueprint_lane_tags(
                                role_family_id=_clean(
                                    blueprint.get("role_family_id")
                                ),
                                variant_id=_clean(blueprint.get("variant_id")),
                                tag_ids=resolve_blueprint_tag_ids(
                                    confirmed_variant_tags
                                ),
                                actor_label=actor_label,
                            )
                    status_messages = {
                        "miss": "Created and activated a new immutable blueprint version.",
                        "hit_active": "Exactly reused the already-active blueprint version.",
                        "hit_reactivated": (
                            "Reactivated the original exact blueprint version and "
                            "superseded the previously active version."
                        ),
                    }
                    st.session_state["phase9d_lifecycle_flash"] = (
                        f"{status_messages[result['cache_status']]} "
                        f"Blueprint {blueprint['blueprint_id']} · "
                        f"{blueprint.get('variant_label', 'Primary')} variant · "
                        f"version {blueprint['version_number']}."
                    )
                    st.session_state["phase9d_inspect_blueprint_id"] = (
                        blueprint["blueprint_id"]
                    )
                    _clear_phase9d_approval_review_state()
                    st.rerun()
                except (Phase9DApprovalError, ValueError, RuntimeError) as exc:
                    st.error(str(exc))

        with st.expander("Phase 9C technical details", expanded=False):
            st.caption(
                f"Policy: {policy.get('policy_version', 'Unknown')} · "
                f"Evaluation: {evaluation_id} · "
                f"Fingerprint: {evaluation.get('evaluation_fingerprint', '')}"
            )
            st.json(evaluation)

    st.divider()
    st.subheader("Blueprint inspection")
    blueprints = list_global_blueprints(include_superseded=True)
    if not blueprints:
        st.caption("No Phase 9D versions are stored.")
        _render_blueprint_library_debug_panel(
            current_application_id=current_application_id
        )
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
        _render_blueprint_library_debug_panel(
            current_application_id=current_application_id
        )
        return
    st.dataframe(
        [
            {
                "Role family": row["role_family_label"],
                "Variant": row.get("variant_label", "Primary"),
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
            f"{by_blueprint_id[value].get('variant_label', 'Primary')} · "
            f"v{by_blueprint_id[value]['version_number']} · "
            f"{by_blueprint_id[value]['status']} / "
            f"{by_blueprint_id[value]['availability_status']}"
        ),
        key="phase9d_inspect_blueprint_id",
    )
    selected = by_blueprint_id[selected_blueprint_id]
    previous_edit_selection = st.session_state.get(
        "phase9d_inspection_edit_selection", ""
    )
    if previous_edit_selection != selected_blueprint_id:
        st.session_state["phase9d_inspection_edit_selection"] = (
            selected_blueprint_id
        )
        st.session_state.pop("phase9d_edit_lane_context", None)
        st.session_state.pop("phase9d_edit_display_blueprint_id", None)

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

    st.write("**Lane metadata**")
    selected_lane_tags = get_blueprint_lane_tags(
        role_family_id=_clean(selected.get("role_family_id")),
        variant_id=_clean(selected.get("variant_id")),
    )
    st.caption(
        "Lane tags describe the reusable variant lane, not this immutable "
        "Blueprint version. Updating them does not change résumé content, "
        "Blueprint fingerprints, or version history."
    )
    current_lane_tag_labels = [
        row["label"] for row in selected_lane_tags
    ]
    st.write(
        "**Tags:** "
        + (
            " · ".join(current_lane_tag_labels)
            if current_lane_tag_labels
            else "Unclassified"
        )
    )

    lane_context = (
        f"{_clean(selected.get('role_family_id'))}:"
        f"{_clean(selected.get('variant_id'))}"
    )
    lane_widget_key = (
        "phase9d_lane_tags_"
        f"{_clean(selected.get('role_family_id'))}_"
        f"{_clean(selected.get('variant_id'))}"
    )
    lane_edit_key = (
        "phase9d_edit_lane_metadata_"
        f"{_clean(selected.get('role_family_id'))}_"
        f"{_clean(selected.get('variant_id'))}"
    )
    lane_save_key = (
        "phase9d_save_lane_tags_"
        f"{_clean(selected.get('role_family_id'))}_"
        f"{_clean(selected.get('variant_id'))}"
    )
    lane_cancel_key = (
        "phase9d_cancel_lane_metadata_"
        f"{_clean(selected.get('role_family_id'))}_"
        f"{_clean(selected.get('variant_id'))}"
    )
    lane_is_active = _clean(selected.get("status")) == "active"
    lane_is_removed = selected.get("availability_status") == "removed"
    editing_lane = (
        lane_is_active
        and not lane_is_removed
        and st.session_state.get("phase9d_edit_lane_context") == lane_context
    )

    if lane_is_active and not lane_is_removed:
        if not editing_lane:
            if st.button(
                "Edit lane metadata",
                key=lane_edit_key,
            ):
                st.session_state["phase9d_edit_lane_context"] = lane_context
                st.rerun()
        else:
            lane_tag_library = list_blueprint_tags(include_inactive=False)
            lane_tag_by_id = {
                row["tag_id"]: row
                for row in lane_tag_library
            }
            is_primary_lane = (
                _clean(selected.get("variant_id")) == "primary"
            )
            lane_tag_options = [
                row["tag_id"]
                for row in lane_tag_library
                if row["tag_id"] != GENERALIST_TAG_ID
            ]
            current_editable_tag_ids = [
                row["tag_id"]
                for row in selected_lane_tags
                if row["tag_id"] != GENERALIST_TAG_ID
            ]
            if is_primary_lane:
                st.caption(
                    "Primary always keeps the **Generalist** tag. "
                    "You may add supporting tags, but Generalist remains enforced."
                )
            edited_lane_tag_ids = st.multiselect(
                "Variant lane tags",
                options=lane_tag_options,
                default=current_editable_tag_ids,
                format_func=lambda value: (
                    lane_tag_by_id[value]["label"]
                    if value in lane_tag_by_id
                    else value
                ),
                key=lane_widget_key,
            )
            lane_actions = st.columns(2)
            save_lane_clicked = lane_actions[0].button(
                "Save lane metadata",
                type="primary",
                key=lane_save_key,
                width="stretch",
            )
            cancel_lane_clicked = lane_actions[1].button(
                "Cancel",
                key=lane_cancel_key,
                width="stretch",
            )
            if cancel_lane_clicked:
                st.session_state.pop("phase9d_edit_lane_context", None)
                st.rerun()
            if save_lane_clicked:
                requested_tag_ids = (
                    [GENERALIST_TAG_ID, *edited_lane_tag_ids]
                    if is_primary_lane
                    else edited_lane_tag_ids
                )
                try:
                    updated_lane_tags = set_blueprint_lane_tags(
                        role_family_id=_clean(
                            selected.get("role_family_id")
                        ),
                        variant_id=_clean(selected.get("variant_id")),
                        tag_ids=requested_tag_ids,
                        actor_label="Local user",
                    )
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    st.session_state["phase9d_lifecycle_flash"] = (
                        "Updated Blueprint lane tags: "
                        + " · ".join(
                            row["label"] for row in updated_lane_tags
                        )
                    )
                    st.session_state.pop("phase9d_edit_lane_context", None)
                    st.rerun()
    elif lane_is_removed:
        st.caption(
            "Lane metadata is read-only while this Blueprint is removed. "
            "Restore the active Blueprint before editing its lane tags."
        )
        if st.session_state.get("phase9d_edit_lane_context") == lane_context:
            st.session_state.pop("phase9d_edit_lane_context", None)
            st.session_state.pop(lane_widget_key, None)
    else:
        st.info(
            "This is a superseded immutable version. Lane tags are read-only "
            "here; edit them from the currently active version of the same lane."
        )
        if st.session_state.get("phase9d_edit_lane_context") == lane_context:
            st.session_state.pop("phase9d_edit_lane_context", None)
            st.session_state.pop(lane_widget_key, None)

    if selected.get("availability_status") == "removed":
        st.write("**Display metadata**")
        st.write(
            f"**Display name:** "
            f"{_clean(selected.get('display_name')) or 'Global Blueprint'}"
        )
        st.write(
            f"**Notes:** "
            f"{_clean(selected.get('notes')) or '—'}"
        )
        st.caption(
            "Display metadata is read-only while this Blueprint is removed. "
            "Restore it before editing."
        )
        if (
            st.session_state.get("phase9d_edit_display_blueprint_id")
            == selected_blueprint_id
        ):
            st.session_state.pop(
                "phase9d_edit_display_blueprint_id",
                None,
            )
        _render_blueprint_library_debug_panel(
            current_application_id=current_application_id
        )
        return

    st.write("**Display metadata**")
    st.write(
        f"**Display name:** "
        f"{_clean(selected.get('display_name')) or 'Global Blueprint'}"
    )
    st.write(
        f"**Notes:** "
        f"{_clean(selected.get('notes')) or '—'}"
    )

    display_editing = (
        st.session_state.get("phase9d_edit_display_blueprint_id")
        == selected_blueprint_id
    )
    display_edit_button_key = (
        f"phase9d_edit_display_metadata_{selected_blueprint_id}"
    )
    display_name_key = f"phase9d_edit_name_{selected_blueprint_id}"
    display_notes_key = f"phase9d_edit_notes_{selected_blueprint_id}"
    display_actor_key = f"phase9d_metadata_actor_{selected_blueprint_id}"
    display_save_key = f"phase9d_save_metadata_{selected_blueprint_id}"
    display_cancel_key = (
        f"phase9d_cancel_display_metadata_{selected_blueprint_id}"
    )

    if not display_editing:
        if st.button(
            "Edit display metadata",
            key=display_edit_button_key,
        ):
            st.session_state["phase9d_edit_display_blueprint_id"] = (
                selected_blueprint_id
            )
            st.rerun()
    else:
        edited_name = st.text_input(
            "Display name",
            value=selected["display_name"],
            key=display_name_key,
        )
        edited_notes = st.text_area(
            "Notes",
            value=selected["notes"],
            key=display_notes_key,
        )
        metadata_actor = st.text_input(
            "Metadata editor label",
            value="Local user",
            key=display_actor_key,
        )
        display_actions = st.columns(2)
        save_display_clicked = display_actions[0].button(
            "Save display metadata",
            type="primary",
            key=display_save_key,
            width="stretch",
        )
        cancel_display_clicked = display_actions[1].button(
            "Cancel",
            key=display_cancel_key,
            width="stretch",
        )
        if cancel_display_clicked:
            st.session_state.pop(
                "phase9d_edit_display_blueprint_id",
                None,
            )
            st.rerun()
        if save_display_clicked:
            try:
                updated = update_global_blueprint_display_metadata(
                    blueprint_id=selected_blueprint_id,
                    display_name=edited_name,
                    notes=edited_notes,
                    actor_label=metadata_actor,
                )
            except (ValueError, RuntimeError) as exc:
                st.error(str(exc))
            else:
                st.session_state["phase9d_last_metadata_update"] = updated
                st.session_state["phase9d_lifecycle_flash"] = (
                    "Updated display metadata without changing Blueprint identity."
                )
                st.session_state.pop(
                    "phase9d_edit_display_blueprint_id",
                    None,
                )
                st.rerun()

    _render_blueprint_library_debug_panel(
        current_application_id=current_application_id
    )

"""Application Sessions UI for Phase 9E blueprint selection and binding."""

from __future__ import annotations

import json
from typing import Any

import streamlit as st

from database.application_blueprint_manager import (
    evaluate_and_bind_application_blueprint,
    export_application_blueprint_decision,
    get_current_application_blueprint_decision,
    list_application_blueprint_decisions,
    preview_application_blueprint_decision,
    resolve_current_phase9e_generation_context,
    set_application_blueprint_workflow_action,
)
from database.application_resume_result_manager import (
    create_or_reuse_current_application_result,
    create_or_reuse_phase9e_editable_action_draft,
    get_current_application_resume_result,
    list_application_resume_results,
)
from tailoring.generation_controls_ui import restore_generation_to_session
from database.global_blueprint_manager import list_global_blueprints
from database.jd_library_manager import get_exact_job_description_for_application
from database.phase9f_application_execution_manager import (
    get_phase9f_application_execution,
)
from tailoring.phase9e_blueprint_selection import (
    DECISION_LABELS,
    Phase9EDecisionError,
    recommend_active_blueprint,
)
from tailoring.phase9f_application_confirmation import (
    phase9f_d_execution_state,
)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _blueprint_label(blueprint: dict[str, Any], *, recommended: bool) -> str:
    prefix = "Recommended — " if recommended else ""
    return (
        f"{prefix}{_clean(blueprint.get('display_name')) or _clean(blueprint.get('role_family_label'))} "
        f"· {_clean(blueprint.get('role_family_label'))} "
        f"· v{int(blueprint.get('version_number', 0) or 0)}"
    )


def _provisional(blueprint: dict[str, Any]) -> bool:
    snapshot = blueprint.get("blueprint_snapshot") or {}
    evaluation = snapshot.get("phase9c_evaluation_snapshot") or {}
    aggregate = evaluation.get("aggregate_result") or {}
    return aggregate.get("provisional") is True


def _is_active_current_binding(decision: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(decision, dict)
        and decision.get("scope_activation_status") == "active"
        and decision.get("current_scope_status") == "current"
    )


def _selection_identity(decision: dict[str, Any] | None) -> tuple[Any, ...]:
    if not isinstance(decision, dict):
        return ()
    selection = decision.get("selection") or {}
    source = _clean(selection.get("selected_source"))
    mode = _clean(selection.get("selection_mode"))
    if source == "original_resume":
        return (source, mode)
    blueprint = selection.get("selected_blueprint") or {}
    return (
        source,
        mode,
        _clean(blueprint.get("blueprint_id")),
        _clean(blueprint.get("blueprint_fingerprint")),
        int(blueprint.get("version_number", 0) or 0),
    )


def _preview_matches_active_binding(
    preview: dict[str, Any] | None,
    current: dict[str, Any] | None,
) -> bool:
    """Return whether a read-only preview selects the exact active source."""
    return bool(
        _is_active_current_binding(current)
        and _selection_identity(preview)
        and _selection_identity(preview) == _selection_identity(current)
    )


def _show_blueprint_identity(blueprint: dict[str, Any]) -> None:
    columns = st.columns(4)
    columns[0].metric("Version", int(blueprint.get("version_number", 0) or 0))
    columns[1].metric(
        "Source status",
        "Provisional" if _provisional(blueprint) else "Non-provisional",
    )
    columns[2].metric("Role family", _clean(blueprint.get("role_family_label")))
    columns[3].metric("Status", _clean(blueprint.get("status")).title())
    st.write(f"**Display name:** {_clean(blueprint.get('display_name'))}")
    st.code(_clean(blueprint.get("blueprint_id")), language=None)
    st.caption(f"Fingerprint: {_clean(blueprint.get('blueprint_fingerprint'))}")


def _show_decision(decision: dict[str, Any], *, heading: str) -> None:
    st.write(f"#### {heading}")
    comparison = decision.get("comparison") or {}
    decision_label = (
        _clean(decision.get("recommended_tailoring_label"))
        or DECISION_LABELS.get(
            _clean(decision.get("recommended_tailoring")),
            _clean(decision.get("recommended_tailoring")),
        )
    )
    st.caption("Recommended workflow")
    st.write(f"**{decision_label}**")
    metrics = st.columns(4)
    metrics[0].metric(
        "Overall",
        comparison.get("deterministic_alignment_score", 0),
    )
    metrics[1].metric(
        "Required/Core",
        f"{comparison.get('required_core_coverage_score', 0)}%",
    )
    metrics[2].metric(
        "Preferred",
        f"{comparison.get('preferred_coverage_score', 0)}%",
    )
    metrics[3].metric(
        "Evidence strength",
        f"{comparison.get('evidence_strength_score', 0)}%",
    )
    st.caption(
        "The numeric values below are a visible-résumé diagnostic. "
        "Exact approved-source reuse is controlled by immutable approval provenance."
    )
    for reason in decision.get("decision_reasons") or []:
        st.write(f"- {reason}")
    gaps = comparison.get("important_gaps") or []
    if gaps:
        st.warning(
            f"Important gaps: {len(gaps)} · deal-breakers: "
            f"{comparison.get('deal_breaker_gap_count', 0)}"
        )
        st.dataframe(gaps, hide_index=True, width="stretch")
    else:
        st.success("No unsupported important or deal-breaker requirements.")
    scope = decision.get("section_lock_scope") or {}
    st.caption(
        "Locked: "
        + ", ".join(scope.get("locked_sections") or [])
        + " · Tailorable: "
        + (", ".join(scope.get("tailorable_sections") or []) or "none")
    )
    starting = decision.get("starting_snapshot") or {}
    if starting.get("source_fidelity") == "persisted_profile_only":
        st.info(
            "This legacy original-résumé decision uses the authoritative "
            "persisted profile and the deterministic profile-to-text scoring "
            "representation. It is not the original uploaded raw text."
        )


def _show_active_binding(
    *,
    application_id: int,
    current: dict[str, Any],
    generation_context: dict[str, Any],
    actor_label: str,
) -> None:
    selection = current.get("selection") or {}
    selected_source = _clean(selection.get("selected_source"))
    if selected_source == "global_blueprint":
        blueprint = selection.get("selected_blueprint") or {}
        source_label = (
            _clean(selection.get("selected_blueprint_display_name"))
            or _clean(blueprint.get("blueprint_id"))
            or "Global blueprint"
        )
        source_details = (
            f"Blueprint {_clean(blueprint.get('blueprint_id'))} · "
            f"v{int(blueprint.get('version_number', 0) or 0)} · "
            f"{_clean(blueprint.get('role_family_label'))}"
        )
    elif selected_source == "base_resume":
        source = (current.get("starting_snapshot") or {}).get(
            "source_identity"
        ) or {}
        source_label = (
            _clean(source.get("source_display_name")) or "Base Resume"
        )
        source_details = (
            "Immutable Base Resume · "
            f"v{int(source.get('source_version') or 0)}"
        )
    else:
        source_label = "Persisted original résumé"
        source_details = "Original résumé snapshot persisted for this application"

    phase9f_d_state = phase9f_d_execution_state(current)
    if phase9f_d_state is not None:
        execution = get_phase9f_application_execution(application_id)
        execution_status = _clean((execution or {}).get("status")) or "not_started"
        execution_stage = _clean((execution or {}).get("current_stage"))

        st.success("Exact Phase 9F-D Tailoring Base is bound.")
        st.write(f"**Active tailoring base:** {source_label}")
        st.caption(source_details)
        st.write(
            "**Confirmed tailoring intensity:** "
            f"{phase9f_d_state['confirmed_intensity_label']}"
        )
        st.caption(
            "Execution status: "
            f"{execution_status.replace('_', ' ')}"
        )

        if execution_status == "not_started":
            st.info(
                "Tailoring execution has not started yet. "
                f"Next action: {phase9f_d_state['next_action']}."
            )
        elif execution_status in {"preparing", "running"}:
            stage_suffix = f" at `{execution_stage}`" if execution_stage else ""
            st.info(
                f"Reuse execution is {execution_status}{stage_suffix}. "
                "The exact Phase 9F-D Tailoring Base remains bound."
            )
        elif execution_status == "failed":
            message = _clean((execution or {}).get("last_error_message"))
            st.warning(
                "Reuse execution failed safely"
                + (f" at `{execution_stage}`" if execution_stage else "")
                + (f": {message}" if message else ".")
                + " Retry from Phase 9F-E; the exact Phase 9F-D binding "
                "remains intact."
            )
        elif execution_status == "completed":
            st.info(
                "Reuse execution is complete. Review the immutable résumé "
                "result, current-JD Phase 8 verification, downloads, and "
                "source lineage below."
            )
        else:
            st.info(
                "A durable Phase 9F-E execution record exists with status "
                f"`{execution_status}`. Review Phase 9F-E below."
            )

        with st.expander(
            "View current Phase 9E decision diagnostics",
            expanded=False,
        ):
            _show_decision(current, heading="Current bound decision")
        return

    workflow = generation_context.get("workflow_action") or {}
    workflow_state = _clean(workflow.get("workflow_action")) or "not selected"

    st.success(
        "A current immutable Phase 9E tailoring base is bound for generation."
    )
    st.write(f"**Active tailoring base:** {source_label}")
    st.caption(source_details)
    st.caption(f"Current workflow state: {workflow_state.replace('_', ' ')}")
    with st.expander(
        "View current Phase 9E decision diagnostics",
        expanded=False,
    ):
        _show_decision(current, heading="Current bound decision")
    current_result = get_current_application_resume_result(
        application_id, validate_artifacts=False
    )
    if (
        current_result is not None
        and (current_result.get("state") or {}).get("active_output_mode")
        == "immutable_result"
        and current_result.get("phase9e_decision_fingerprint")
        == current.get("decision_fingerprint")
    ):
        st.success(
            "The unchanged workflow action is already materialized as the "
            "current immutable application result."
        )
        return
    _render_workflow_actions(
        application_id=application_id,
        decision=current,
        actor_label=actor_label,
    )




def _preview_source_label(decision: dict[str, Any]) -> str:
    selection = decision.get("selection") or {}
    source = _clean(selection.get("selected_source"))
    if source == "original_resume":
        return "Original application résumé"
    blueprint = selection.get("selected_blueprint") or {}
    return (
        _clean(selection.get("selected_blueprint_display_name"))
        or _clean(blueprint.get("display_name"))
        or _clean(blueprint.get("role_family_label"))
        or "Selected Global Blueprint"
    )


def _render_scope_transition_summary(
    *,
    preview: dict[str, Any],
    generation_context: dict[str, Any],
) -> None:
    """Separate the current legacy scope from the proposed Phase 9E scope."""
    with st.container(border=True):
        st.write("#### Workflow transition")
        current_col, proposed_col, status_col = st.columns(3)
        current_col.caption("Current workflow")
        current_col.write("**Legacy generation scope**")
        proposed_col.caption("Proposed Phase 9E source")
        proposed_col.write(
            f"**{_preview_source_label(preview)}**"
        )
        status_col.caption("Status")
        status_col.write("**Waiting for confirmation**")
        st.caption(
            generation_context.get("legacy_notice")
            or (
                "The current legacy generation, approval, fitting, "
                "verification, and export scope remains active until "
                "the replacement is explicitly confirmed."
            )
        )



def _render_active_original_source_guidance(
    application_id: int,
) -> None:
    # Do not tell the user to regenerate when a working draft is already open.
    workspace: dict[str, Any] = {}
    try:
        from tailoring.phase9e1_resume_workspace_ui import (
            get_resume_workspace_context,
        )

        workspace = get_resume_workspace_context(int(application_id)) or {}
    except (ImportError, OSError, RuntimeError, ValueError):
        workspace = {}

    working = (
        workspace.get("loaded_generation")
        if workspace.get("loaded_mode") == "working_draft"
        else None
    )

    if isinstance(working, dict):
        working_id = _clean(working.get("generation_id"))[:8] or "draft"
        fit_result = working.get("fit_result") or {}
        page_count_raw = fit_result.get("page_count")
        try:
            page_count = (
                int(page_count_raw)
                if page_count_raw not in (None, "")
                else None
            )
        except (TypeError, ValueError):
            page_count = None

        if page_count == 1:
            st.info(
                f"Working draft {working_id} is already generated and fitted "
                "to one page. Continue with review and approval below; after "
                "approval, run Phase 8 verification. The persisted original "
                "résumé remains the immutable starting source if you choose "
                "to regenerate."
            )
            return

        if page_count is not None:
            st.info(
                f"Working draft {working_id} is already generated but is "
                f"currently {page_count} pages. Continue Build/Fit until it "
                "fits one page, then approve and run Phase 8. The persisted "
                "original résumé remains the immutable starting source if "
                "you choose to regenerate."
            )
            return

        st.info(
            f"Working draft {working_id} is already active. Continue editing "
            "and Build/Fit this draft below; regenerate only if you intend to "
            "create a new tailored version. The persisted original résumé "
            "remains the immutable starting source if you choose to regenerate."
        )
        return

    previous_scope_approved = workspace.get(
        "previous_scope_approved_generation"
    )
    if isinstance(previous_scope_approved, dict):
        previous_scope_id = _clean(
            previous_scope_approved.get("generation_id")
        )[:8] or "result"
        st.info(
            "The current Tailoring Base is ready, but approved résumé "
            f"{previous_scope_id} belongs to a previous Tailoring Base. "
            "Before generating, use Start new résumé from current Tailoring Base "
            "in the Résumé Workspace. The previous approved result remains "
            "preserved until you make that explicit transition."
        )
        return

    st.info(
        "The persisted original résumé is the active starting source. "
        "Use Generate Projects + Skills below to create the first tailored "
        "working draft; Education and Work Experience remain protected."
    )


def _render_decision_history(application_id: int) -> None:
    history = list_application_blueprint_decisions(application_id)
    if not history:
        return
    with st.expander("Phase 9E decision history and JSON", expanded=False):
        st.dataframe(
            [
                {
                    "Status": row.get("binding_status"),
                    "Decision": row.get("recommended_tailoring"),
                    "Source": (row.get("selection") or {}).get(
                        "selected_source"
                    ),
                    "Decision ID": row.get("decision_id"),
                    "Created": row.get("created_at"),
                }
                for row in history
            ],
            hide_index=True,
            width="stretch",
        )
        inspect_id = st.selectbox(
            "Inspect Phase 9E decision",
            options=[row["decision_id"] for row in history],
            key=f"phase9e_inspect_{application_id}",
        )
        export = export_application_blueprint_decision(inspect_id)
        st.json(export)
        st.download_button(
            "Download Phase 9E decision JSON",
            data=json.dumps(export, indent=2, ensure_ascii=False),
            file_name=f"phase9e_{inspect_id[:12]}.json",
            mime="application/json",
            key=f"phase9e_export_{application_id}_{inspect_id}",
        )


def _render_application_result_history(application_id: int) -> None:
    results = list_application_resume_results(
        application_id, validate_artifacts=False
    )
    if not results:
        return
    with st.expander("Immutable application-result history", expanded=False):
        st.info(
            "Previous immutable results remain historical and inspectable when "
            "the Phase 9E source scope changes."
        )
        st.dataframe(
            [
                {
                    "Result": row.get("application_result_id"),
                    "Status": row.get("initial_status"),
                    "Blueprint": row.get("blueprint_id"),
                    "Decision": row.get("phase9e_decision_id"),
                    "Created": row.get("created_at"),
                }
                for row in results
            ],
            hide_index=True,
            width="stretch",
        )


def _record_workflow_action(
    *,
    application_id: int,
    workflow_action: str,
    actor_label: str,
    acknowledgement: bool = False,
    reason: str = "",
) -> None:
    action_result = set_application_blueprint_workflow_action(
        application_id=application_id,
        workflow_action=workflow_action,
        acknowledgement=acknowledgement,
        reason=reason,
        actor_label=actor_label,
    )
    if workflow_action in {
        "use_blueprint_unchanged",
        "use_blueprint_unchanged_override",
    }:
        materialized = create_or_reuse_current_application_result(
            application_id=application_id,
            actor_label=actor_label,
        )
        result = materialized["application_result"]
        st.session_state[f"phase9e_flash_{application_id}"] = (
            "Persisted the Phase 9E action and "
            f"{('reused' if materialized['cache_status'] == 'hit' else 'created')} "
            "one immutable application result "
            f"({result['application_result_id'][:12]})."
        )
    else:
        editable = create_or_reuse_phase9e_editable_action_draft(
            application_id=application_id
        )
        generation = editable["generation"]
        restore_generation_to_session(application_id, generation)
        st.session_state[f"phase9e_flash_{application_id}"] = (
            "Persisted the Phase 9E workflow action and "
            f"{('reused' if editable['cache_status'] == 'hit' else 'created')} "
            "one editable action draft. Content is still unchanged until the "
            "supported tailoring action runs."
        )
    st.rerun()


def _render_workflow_actions(
    *,
    application_id: int,
    decision: dict[str, Any],
    actor_label: str,
) -> None:
    outcome = _clean(decision.get("recommended_tailoring"))
    st.write("#### Choose how to continue")
    try:
        if outcome == "optional_polish":
            st.info(
                "Optional polish is not required. The approved frozen blueprint "
                "remains usable and exportable unchanged with every section locked."
            )
            unchanged, polish = st.columns(2)
            if unchanged.button(
                "Use blueprint unchanged",
                key=f"phase9e_use_unchanged_{application_id}",
                width="stretch",
            ):
                _record_workflow_action(
                    application_id=application_id,
                    workflow_action="use_blueprint_unchanged",
                    actor_label=actor_label,
                )
            if polish.button(
                "Apply optional polish",
                key=f"phase9e_optional_polish_{application_id}",
                width="stretch",
            ):
                _record_workflow_action(
                    application_id=application_id,
                    workflow_action="apply_optional_polish",
                    actor_label=actor_label,
                )
        elif outcome == "targeted_retailor":
            st.warning(
                "Targeted retargeting is recommended for Projects and Skills, "
                "but it is not mandatory."
            )
            if st.button(
                "Apply targeted retargeting",
                type="primary",
                key=f"phase9e_targeted_{application_id}",
                width="stretch",
            ):
                _record_workflow_action(
                    application_id=application_id,
                    workflow_action="apply_targeted_retargeting",
                    actor_label=actor_label,
                )
            acknowledgement = st.checkbox(
                "I understand that important gaps will remain if I use the blueprint unchanged.",
                value=False,
                key=f"phase9e_targeted_override_ack_{application_id}",
            )
            reason = st.text_area(
                "Reason for using the blueprint unchanged",
                key=f"phase9e_targeted_override_reason_{application_id}",
            )
            if st.button(
                "Use blueprint unchanged anyway",
                key=f"phase9e_targeted_override_{application_id}",
                width="stretch",
            ):
                _record_workflow_action(
                    application_id=application_id,
                    workflow_action="use_blueprint_unchanged_override",
                    actor_label=actor_label,
                    acknowledgement=acknowledgement,
                    reason=reason,
                )
        elif outcome == "full_regeneration":
            selected_source = _clean(
                (decision.get("selection") or {}).get("selected_source")
            )
            if selected_source == "original_resume":
                _render_active_original_source_guidance(application_id)
            else:
                st.warning(
                    "The selected blueprint is unsuitable. Restart from the persisted "
                    "original résumé; Education and Work Experience remain protected."
                )
                if st.button(
                    "Regenerate from original résumé",
                    type="primary",
                    key=f"phase9e_regenerate_original_{application_id}",
                    width="stretch",
                ):
                    _record_workflow_action(
                        application_id=application_id,
                        workflow_action="regenerate_from_original_resume",
                        actor_label=actor_label,
                    )
        else:
            st.success(
                "The frozen blueprint can be used unchanged with all sections locked."
            )
            if st.button(
                "Use blueprint unchanged",
                key=f"phase9e_reuse_unchanged_{application_id}",
                width="stretch",
            ):
                _record_workflow_action(
                    application_id=application_id,
                    workflow_action="use_blueprint_unchanged",
                    actor_label=actor_label,
                )
    except (Phase9EDecisionError, ValueError, RuntimeError) as exc:
        st.error(str(exc))


def render_phase9e_blueprint_selection(
    *,
    application_id: int,
    baseline_report: dict[str, Any],
) -> dict[str, Any]:
    """Render Phase 9E and return the fail-closed generation context."""
    del baseline_report  # persistence remains authoritative for preview/binding
    st.divider()
    st.header("Tailoring Base")
    st.caption(
        "Choose the immutable résumé base that future JD-specific tailoring "
        "should start from for this application. Phase 9E only binds the base; "
        "it does not generate, approve, or overwrite résumé content."
    )

    flash = st.session_state.pop(f"phase9e_flash_{application_id}", "")
    if flash:
        st.success(flash)

    current = get_current_application_blueprint_decision(application_id)
    generation_context = resolve_current_phase9e_generation_context(
        application_id
    )
    with st.expander("Binding audit details", expanded=False):
        actor_label = st.text_input(
            "Binding actor label",
            value="Local user",
            key=f"phase9e_actor_{application_id}",
            help="Audit metadata only; excluded from Phase 9E identity.",
        )
    change_key = f"phase9e_change_source_mode_{application_id}"
    changing_source = bool(st.session_state.get(change_key, False))
    active_current = _is_active_current_binding(current)

    if active_current:
        _show_active_binding(
            application_id=application_id,
            current=current,
            generation_context=generation_context,
            actor_label=actor_label,
        )
        if phase9f_d_execution_state(current) is not None:
            _render_decision_history(application_id)
            return generation_context
        if not changing_source:
            if st.button(
                "Change tailoring base",
                key=f"phase9e_change_source_{application_id}",
            ):
                st.session_state[change_key] = True
                st.rerun()
            _render_decision_history(application_id)
            return generation_context

        st.warning(
            "You are previewing a possible replacement starting source. The "
            "current binding remains active until you explicitly confirm and bind "
            "a different source; the prior approved generation will remain "
            "historical and inspectable."
        )
        if st.button(
            "Keep current tailoring base",
            key=f"phase9e_cancel_change_source_{application_id}",
        ):
            st.session_state[change_key] = False
            st.rerun()
        st.write("### Preview a replacement tailoring base")

    try:
        exact_jd = get_exact_job_description_for_application(application_id)
        if exact_jd is None:
            raise Phase9EDecisionError(
                "Analyze this application so its exact JD version is persisted."
            )
        active = list_global_blueprints(include_superseded=False)
        recommendation = recommend_active_blueprint(exact_jd, active)
    except (Phase9EDecisionError, ValueError, RuntimeError) as exc:
        st.error(str(exc))
        return {
            "status": "blocked",
            "can_generate": False,
            "reasons": [str(exc)],
        }

    classification = recommendation["classification"]
    st.write(
        f"**JD role family:** {_clean(classification.get('role_family'))} "
        f"· confidence {_clean(classification.get('confidence')).title()}"
    )
    matched = classification.get("matched_terms") or []
    if matched:
        st.caption("Matched deterministic title terms: " + ", ".join(matched))

    recommended = recommendation.get("recommended_blueprint")
    if isinstance(recommended, dict):
        st.success(
            "A single active same-family blueprint is recommended for this JD."
        )
        _show_blueprint_identity(recommended)
    else:
        st.warning(
            "No active same-family blueprint exists. The original résumé is "
            "recommended; no unrelated blueprint has been selected."
        )
    st.write(
        "**Recommendation confidence:** "
        + _clean(recommendation.get("recommendation_confidence")).title()
    )
    for reason in recommendation.get("reasons") or []:
        st.write(f"- {reason}")

    options: list[str] = []
    option_rows: dict[str, dict[str, Any] | None] = {}
    recommended_id = _clean((recommended or {}).get("blueprint_id"))
    if recommended_id:
        key = f"recommended:{recommended_id}"
        options.append(key)
        option_rows[key] = recommended
    original_key = "original_resume"
    options.append(original_key)
    option_rows[original_key] = None
    for blueprint in recommendation["active_blueprints"]:
        blueprint_id = _clean(blueprint.get("blueprint_id"))
        if blueprint_id == recommended_id:
            continue
        key = f"manual:{blueprint_id}"
        options.append(key)
        option_rows[key] = blueprint

    selection_widget_key = f"phase9e_selection_{application_id}"
    if active_current and selection_widget_key not in st.session_state:
        current_selection = (current or {}).get("selection") or {}
        if _clean(current_selection.get("selected_source")) == "original_resume":
            st.session_state[selection_widget_key] = original_key
        else:
            current_blueprint_id = _clean(
                (current_selection.get("selected_blueprint") or {}).get(
                    "blueprint_id"
                )
            )
            current_option = next(
                (
                    key
                    for key, row in option_rows.items()
                    if isinstance(row, dict)
                    and _clean(row.get("blueprint_id")) == current_blueprint_id
                ),
                "",
            )
            if current_option:
                st.session_state[selection_widget_key] = current_option

    selection_key = st.selectbox(
        "Tailoring base",
        options=options,
        format_func=lambda value: (
            "Original résumé for this application"
            if value == original_key
            else _blueprint_label(
                option_rows[value] or {},
                recommended=value.startswith("recommended:"),
            )
        ),
        key=selection_widget_key,
        help=(
            "Choose the immutable résumé base used before JD-specific tailoring. "
            "Changing this dropdown only previews the choice; the base is not "
            "rebound until you explicitly confirm below."
        ),
    )
    selected_blueprint = option_rows[selection_key]
    selected_source = (
        "original_resume"
        if selection_key == original_key
        else "global_blueprint"
    )
    selection_mode = (
        "original_resume"
        if selection_key == original_key
        else "recommended"
        if selection_key.startswith("recommended:")
        else "manual"
    )
    selected_id = _clean((selected_blueprint or {}).get("blueprint_id"))
    current_selection = (current or {}).get("selection") or {}
    current_blueprint_id = _clean(
        (current_selection.get("selected_blueprint") or {}).get("blueprint_id")
    )
    if (
        active_current
        and selected_source == _clean(current_selection.get("selected_source"))
        and selected_id == current_blueprint_id
    ):
        selection_mode = _clean(current_selection.get("selection_mode"))
    mismatch = bool(
        selected_blueprint
        and _clean(selected_blueprint.get("role_family_id"))
        != _clean(classification.get("role_family_id"))
    )
    mismatch_acknowledged = False
    if mismatch:
        st.error(
            "The selected active blueprint belongs to a different role family. "
            "Phase 9E will recommend restarting from the persisted original résumé."
        )
        mismatch_acknowledged = st.checkbox(
            "I explicitly choose this different-family blueprint and accept the mismatch warning.",
            value=False,
            key=f"phase9e_mismatch_ack_{application_id}_{selected_id}",
        )

    preview: dict[str, Any] | None = None
    preview_matches_current = False
    if not mismatch or mismatch_acknowledged:
        try:
            preview = preview_application_blueprint_decision(
                application_id=application_id,
                selected_source=selected_source,
                selected_blueprint_id=selected_id,
                selection_mode=selection_mode,
                mismatch_acknowledged=mismatch_acknowledged,
            )
            preview_matches_current = _preview_matches_active_binding(
                preview, current
            )
            if preview_matches_current:
                st.info(
                    "This preview selects the already-active immutable starting "
                    "source. Keep the current binding or choose a different source."
                )
            else:
                if (
                    generation_context.get("status") == "legacy"
                    and not active_current
                ):
                    _render_scope_transition_summary(
                        preview=preview,
                        generation_context=generation_context,
                    )
                    with st.expander(
                        "Review proposed source diagnostics",
                        expanded=False,
                    ):
                        _show_decision(
                            preview,
                            heading="Deterministic decision preview",
                        )
                else:
                    _show_decision(
                        preview,
                        heading=(
                            "Proposed replacement decision"
                            if active_current
                            else "Deterministic decision preview"
                        ),
                    )
        except (Phase9EDecisionError, ValueError, RuntimeError) as exc:
            st.error(str(exc))

    if preview is not None and not preview_matches_current:
        replacement_confirmed = st.checkbox(
            "I confirm replacing the current application scope. Any prior approved "
            "generation and Phase 8 verification will remain historical and inspectable.",
            value=False,
            key=f"phase9e_scope_replacement_ack_{application_id}",
        )
        st.caption(
            "Until this is confirmed, the existing generation, approval, fitting, "
            "export, Phase 8, and Phase 9B scope remains current."
        )
        action_label = (
            "Use original résumé as tailoring base"
            if selected_source == "original_resume"
            else "Use selected Blueprint as tailoring base"
        )
        if st.button(
            action_label,
            type="primary",
            width="stretch",
            key=f"phase9e_bind_{application_id}",
            disabled=not replacement_confirmed,
        ):
            try:
                result = evaluate_and_bind_application_blueprint(
                    application_id=application_id,
                    scope_replacement_confirmed=replacement_confirmed,
                    selected_source=selected_source,
                    selected_blueprint_id=selected_id,
                    selection_mode=selection_mode,
                    mismatch_acknowledged=mismatch_acknowledged,
                    actor_label=actor_label,
                )
                messages = {
                    "miss": "Persisted and bound a new immutable Phase 9E decision.",
                    "hit_current": "Exactly reused the already-current Phase 9E decision.",
                    "hit_rebound": "Rebound the exact historical Phase 9E decision.",
                }
                st.session_state[change_key] = False
                st.session_state[f"phase9e_flash_{application_id}"] = messages[
                    result["cache_status"]
                ]
                st.rerun()
            except (Phase9EDecisionError, ValueError, RuntimeError) as exc:
                st.error(str(exc))

    if active_current:
        pass
    elif current is None:
        if generation_context.get("status") == "legacy":
            st.info(
                "Phase 9E is optional for this legacy session. Its existing generation "
                "scope remains current until a new starting source is explicitly confirmed."
            )
        else:
            st.warning(
                "No Phase 9E tailoring base is active. Generation is blocked "
                "until a source is explicitly confirmed."
            )
    elif current.get("scope_activation_status") != "active":
        if generation_context.get("status") == "legacy":
            st.info(
                "This saved Phase 9E decision is not active because scope replacement "
                "was not explicitly confirmed under the legacy-compatibility policy. "
                "The legacy generation scope remains current."
            )
        else:
            st.warning(
                "This Phase 9E decision is awaiting explicit scope replacement "
                "confirmation, so generation remains blocked."
            )
        with st.expander(
            "View saved unconfirmed Phase 9E decision",
            expanded=False,
        ):
            _show_decision(current, heading="Unconfirmed Phase 9E decision")
    elif current.get("current_scope_status") == "stale":
        st.error(
            "The bound Phase 9E decision is historical/stale. It remains "
            "inspectable, but generation is blocked until the current scope is rebound."
        )
        for reason in current.get("stale_reasons") or []:
            st.write(f"- {reason}")
        _show_decision(current, heading="Historical bound decision")
    _render_decision_history(application_id)
    _render_application_result_history(application_id)

    return generation_context

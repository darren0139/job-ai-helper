# State-aware Phase 9B-9E Blueprint Lifecycle presentation.

from __future__ import annotations

from typing import Any

import streamlit as st

from database.blueprint_candidate_manager import list_blueprint_candidates
from database.blueprint_evaluation_manager import list_blueprint_evaluations
from database.global_blueprint_manager import list_global_blueprints
from database.tailoring_generation_control import get_application_generation_control
from database.tailoring_verification_manager import get_latest_tailoring_verification
from tailoring.phase9b_blueprint_candidate import blueprint_candidate_eligibility
from tailoring.phase9b_blueprint_ui import render_blueprint_candidate_promotion
from tailoring.phase9c_blueprint_evaluation_ui import render_phase9c_blueprint_evaluation
from tailoring.phase9d_global_blueprint import evaluation_policy_status


PHASE9E1_BLUEPRINT_LIFECYCLE_UI_VERSION = (
    "phase9e1-blueprint-lifecycle-stepper-v1"
)

_STAGE_TITLES = {
    "phase8": "Finish Resume Verification",
    "phase9b": "Create Blueprint Candidate",
    "phase9c": "Evaluate Across Similar JDs",
    "phase9d": "Approve Global Blueprint",
    "phase9e": "Use Blueprint in Applications",
}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def resolve_blueprint_lifecycle_stage(
    *,
    candidate_eligible: bool,
    candidate: dict[str, Any] | None,
    evaluation: dict[str, Any] | None,
    active_blueprint: dict[str, Any] | None,
) -> str:
    if not candidate_eligible:
        return "phase8"
    if not isinstance(candidate, dict):
        return "phase9b"
    if not isinstance(evaluation, dict):
        return "phase9c"
    if not isinstance(active_blueprint, dict):
        return "phase9d"
    return "phase9e"


def build_blueprint_lifecycle_summary(
    *,
    current_stage: str,
    candidate: dict[str, Any] | None,
    evaluation: dict[str, Any] | None,
    active_blueprint: dict[str, Any] | None,
) -> dict[str, Any]:
    stage_order = ("phase9b", "phase9c", "phase9d", "phase9e")
    current_index = (
        stage_order.index(current_stage)
        if current_stage in stage_order
        else -1
    )
    rows: list[dict[str, str]] = []
    for index, stage in enumerate(stage_order):
        if current_stage == "phase8":
            status = "Waiting"
        elif index < current_index:
            status = "Complete"
        elif index == current_index:
            status = "Current"
        else:
            status = "Waiting"
        rows.append(
            {
                "stage": stage,
                "label": {
                    "phase9b": "Phase 9B",
                    "phase9c": "Phase 9C",
                    "phase9d": "Phase 9D",
                    "phase9e": "Phase 9E",
                }[stage],
                "title": _STAGE_TITLES[stage],
                "status": status,
            }
        )
    return {
        "ui_version": PHASE9E1_BLUEPRINT_LIFECYCLE_UI_VERSION,
        "current_stage": current_stage,
        "current_title": _STAGE_TITLES[current_stage],
        "stages": rows,
        "candidate_id": _clean((candidate or {}).get("candidate_id")),
        "evaluation_id": _clean((evaluation or {}).get("evaluation_id")),
        "blueprint_id": _clean((active_blueprint or {}).get("blueprint_id")),
    }


def _current_candidate(
    *,
    application_id: int,
    generation_id: str,
    verification_fingerprint: str = "",
) -> dict[str, Any] | None:
    matches = [
        candidate
        for candidate in list_blueprint_candidates(include_archived=False)
        if int(candidate.get("source_application_id", -1) or -1)
        == int(application_id)
        and _clean(candidate.get("source_generation_id")) == generation_id
        and (
            not _clean(verification_fingerprint)
            or _clean(candidate.get("source_verification_fingerprint"))
            == _clean(verification_fingerprint)
        )
    ]
    return matches[0] if matches else None



def _current_evaluation(candidate: dict[str, Any] | None) -> dict[str, Any] | None:
    candidate_id = _clean((candidate or {}).get("candidate_id"))
    if not candidate_id:
        return None
    current = [
        evaluation
        for evaluation in list_blueprint_evaluations(candidate_id=candidate_id)
        if evaluation_policy_status(evaluation)["approvable_policy"]
    ]
    return current[0] if current else None


def _active_blueprint(
    *,
    candidate: dict[str, Any] | None,
    evaluation: dict[str, Any] | None,
) -> dict[str, Any] | None:
    candidate_id = _clean((candidate or {}).get("candidate_id"))
    evaluation_id = _clean((evaluation or {}).get("evaluation_id"))
    if not candidate_id:
        return None
    matches = [
        blueprint
        for blueprint in list_global_blueprints(include_superseded=False)
        if _clean(blueprint.get("status")) == "active"
        and _clean(blueprint.get("candidate_id")) == candidate_id
        and (
            not evaluation_id
            or _clean(blueprint.get("evaluation_id")) == evaluation_id
        )
    ]
    return matches[0] if matches else None


def load_blueprint_lifecycle_state(
    *,
    application_id: int,
    current_phase9e_decision_fingerprint: str = "",
) -> dict[str, Any]:
    control = get_application_generation_control(application_id)
    approved = control.get("approved_generation")
    if not isinstance(approved, dict):
        approved = None

    if approved is not None and (
        approved.get("source_application_result_id")
        or approved.get("phase9e_decision_fingerprint")
    ):
        approved = dict(approved)
        approved_decision_fingerprint = _clean(
            approved.get("phase9e_decision_fingerprint")
        )
        current_decision_fingerprint = _clean(
            current_phase9e_decision_fingerprint
        )
        approved["phase9e_scope_matches"] = bool(
            approved_decision_fingerprint
            and current_decision_fingerprint
            and approved_decision_fingerprint
            == current_decision_fingerprint
        )

    generation_id = _clean((approved or {}).get("generation_id"))
    verification = (
        get_latest_tailoring_verification(application_id, generation_id)
        if generation_id
        else None
    )
    eligibility = blueprint_candidate_eligibility(
        generation_state=approved,
        verification=verification,
    )
    candidate = _current_candidate(
        application_id=application_id,
        generation_id=generation_id,
        verification_fingerprint=_clean(
            (verification or {}).get("verification_fingerprint")
        ),
    )
    evaluation = _current_evaluation(candidate)
    active_blueprint = _active_blueprint(
        candidate=candidate,
        evaluation=evaluation,
    )
    current_stage = resolve_blueprint_lifecycle_stage(
        candidate_eligible=bool(eligibility.get("eligible")),
        candidate=candidate,
        evaluation=evaluation,
        active_blueprint=active_blueprint,
    )
    return {
        "summary": build_blueprint_lifecycle_summary(
            current_stage=current_stage,
            candidate=candidate,
            evaluation=evaluation,
            active_blueprint=active_blueprint,
        ),
        "approved_generation": approved,
        "verification": verification,
        "eligibility": eligibility,
        "candidate": candidate,
        "evaluation": evaluation,
        "active_blueprint": active_blueprint,
    }


def build_working_draft_lifecycle_summary(
    working_generation: dict[str, Any],
) -> dict[str, Any]:
    """Blueprint-stage presentation for an unapproved working draft."""
    summary = build_blueprint_lifecycle_summary(
        current_stage="phase8",
        candidate=None,
        evaluation=None,
        active_blueprint=None,
    )
    summary["working_generation_id"] = _clean(
        working_generation.get("generation_id")
    )
    summary["working_generation_status"] = _clean(
        working_generation.get("status")
    ).lower() or "draft"
    summary["current_title"] = "Approve and Verify Working Draft"
    return summary


def _render_stepper(summary: dict[str, Any]) -> None:
    columns = st.columns(4)
    for column, row in zip(columns, summary["stages"]):
        with column:
            with st.container(border=True):
                st.caption(row["label"])
                st.write(f"**{row['title']}**")
                if row["status"] == "Complete":
                    st.success("Complete")
                elif row["status"] == "Current":
                    st.info("Current")
                else:
                    st.caption("Waiting")


def _render_completed_phase9b_summary(
    candidate: dict[str, Any],
) -> None:
    candidate_name = _clean(
        candidate.get("candidate_name")
        or candidate.get("display_name")
    ) or "Blueprint candidate"
    with st.expander(
        "Phase 9B — Blueprint Candidate · Complete",
        expanded=False,
    ):
        st.write(f"**{candidate_name}**")
        cols = st.columns(3)
        cols[0].caption("Candidate ID")
        cols[0].write(
            f"**{_clean(candidate.get('candidate_id'))[:12] or '—'}**"
        )
        cols[1].caption("Source generation")
        cols[1].write(
            f"**{_clean(candidate.get('source_generation_id'))[:12] or '—'}**"
        )
        cols[2].caption("Role family")
        cols[2].write(
            f"**{_clean(candidate.get('role_family_label') or candidate.get('role_family')) or '—'}**"
        )
        st.caption(
            "Phase 9B is complete. The candidate remains immutable while "
            "Phase 9C evaluates it across the explicitly selected JDs."
        )


def render_state_aware_blueprint_lifecycle(
    *,
    application_id: int,
    baseline_report: dict[str, Any],
    current_phase9e_decision_fingerprint: str = "",
    working_generation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state = load_blueprint_lifecycle_state(
        application_id=application_id,
        current_phase9e_decision_fingerprint=(
            current_phase9e_decision_fingerprint
        ),
    )
    summary = state["summary"]
    current_stage = summary["current_stage"]

    st.divider()
    st.subheader("Blueprint Lifecycle")
    st.caption(
        "Completed stages stay summarized, the current actionable stage opens "
        "automatically, and future stages remain waiting. Opening this section "
        "never creates, evaluates, approves, or binds data."
    )
    if (
        isinstance(working_generation, dict)
        and _clean(working_generation.get("status")).lower() == "draft"
    ):
        working_summary = build_working_draft_lifecycle_summary(
            working_generation
        )
        _render_stepper(working_summary)
        working_id = _clean(working_generation.get("generation_id"))
        st.info(
            "Current step: approve working draft "
            f"**{working_id[:8] or 'draft'}**, then run Phase 8. "
            "Phase 9B–9E stay waiting until this draft becomes the approved, "
            "verified workflow result."
        )
        approved_id = _clean(
            (state.get("approved_generation") or {}).get("generation_id")
        )
        if approved_id:
            st.caption(
                f"Previous approved lifecycle {approved_id[:8]} is preserved "
                "as lineage/history but is not the active workflow while this "
                "draft is open."
            )
        draft_state = dict(state)
        draft_state["summary"] = working_summary
        draft_state["working_generation"] = working_generation
        draft_state["display_scope"] = "working_draft"
        return draft_state

    _render_stepper(summary)

    flash_key = f"phase9e1_lifecycle_flash_{application_id}"
    flash = st.session_state.pop(flash_key, "")
    if flash:
        st.success(flash)

    if current_stage == "phase8":
        failed_keys = [
            name
            for name, passed in (
                state["eligibility"].get("reasons") or {}
            ).items()
            if not passed
        ]
        if failed_keys == ["matches_current_phase9e_scope"]:
            st.error(
                "The approved résumé belongs to a different Phase 9E "
                "starting-source decision. Generate, fit, and approve the "
                "résumé under the current source before Phase 9B."
            )
        else:
            st.info(
                "Current step: finish and approve a one-page résumé, then "
                "pass Phase 8 Blueprint readiness. Phase 9B will open "
                "automatically."
            )
        failed = [
            name.replace("_", " ").title()
            for name in failed_keys
        ]
        if failed:
            st.caption("Waiting on: " + ", ".join(failed))
        return state

    st.info(f"Current step: **{summary['current_title']}**")

    if (
        current_stage in {"phase9c", "phase9d", "phase9e"}
        and isinstance(state.get("candidate"), dict)
    ):
        lifecycle_candidate = state["candidate"]
        source_generation_short = _clean(
            lifecycle_candidate.get("source_generation_id")
        )[:8]
        candidate_short = _clean(
            lifecycle_candidate.get("candidate_id")
        )[:8]
        source_parts = []
        if source_generation_short:
            source_parts.append(
                f"Approved résumé {source_generation_short}"
            )
        if candidate_short:
            source_parts.append(
                f"Candidate {candidate_short}"
            )
        if source_parts:
            st.caption(
                "Blueprint lifecycle source: "
                + " · ".join(source_parts)
            )
        _render_completed_phase9b_summary(lifecycle_candidate)

    if current_stage == "phase9b":
        render_blueprint_candidate_promotion(
            application_id=application_id,
            baseline_report=baseline_report,
            current_phase9e_decision_fingerprint=(
                current_phase9e_decision_fingerprint
            ),
        )
    elif current_stage == "phase9c":
        candidate = state["candidate"] or {}
        render_phase9c_blueprint_evaluation(
            preferred_candidate_id=_clean(candidate.get("candidate_id")),
            rerun_after_save=True,
            completion_flash_key=flash_key,
        )
        with st.expander(
            "Phase 9C recovery",
            expanded=False,
        ):
            st.caption(
                "If Phase 9C reports source-JD parity, frozen-seed, or stale "
                "verification errors, re-open Phase 8 and verify the current "
                "approved résumé before promoting/evaluating again."
            )
            if st.button(
                "Open Phase 8 for re-verification",
                key=f"phase9e1_phase9c_recovery_{application_id}",
                width="stretch",
            ):
                st.session_state[
                    f"phase8_force_open_{application_id}"
                ] = True
                st.session_state[flash_key] = (
                    "Phase 8 was reopened for re-verification. "
                    "Run the verification there, then return to the "
                    "Blueprint Lifecycle."
                )
                st.rerun()
    elif current_stage == "phase9d":
        evaluation = state["evaluation"] or {}
        aggregate = evaluation.get("aggregate_result") or {}
        with st.container(border=True):
            st.success(
                "The current Phase 9C evaluation is persisted and ready for "
                "Global Blueprint approval."
            )
            metrics = st.columns(3)
            metrics[0].metric("Mean score", aggregate.get("mean_score", "—"))
            metrics[1].metric(
                "Evaluated JDs", aggregate.get("evaluated_jd_count", 0)
            )
            metrics[2].metric(
                "Status",
                "Provisional" if aggregate.get("provisional") else "Non-provisional",
            )
            if st.button(
                "Continue to Global Blueprints",
                type="primary",
                width="stretch",
                key=f"phase9e1_continue_phase9d_{application_id}",
            ):
                st.session_state["phase9d_evaluation_id"] = _clean(
                    evaluation.get("evaluation_id")
                )
                # navigation_page belongs to the sidebar radio, which was
                # already instantiated during this Streamlit run. Defer the
                # state mutation until the beginning of the next run.
                st.session_state["_pending_navigation_page"] = (
                    "Global Blueprints"
                )
                st.rerun()
    else:
        blueprint = state["active_blueprint"] or {}
        with st.container(border=True):
            st.success(
                "A Global Blueprint is active for this candidate. Phase 9E can "
                "now recommend it to same-family applications."
            )
            st.write(
                f"**{_clean(blueprint.get('display_name')) or 'Global Blueprint'}**"
            )
            st.caption(
                f"Version {blueprint.get('version_number', '—')} · "
                f"{_clean(blueprint.get('role_family_label'))}"
            )
            st.info(
                "Open another same-family application to test automatic Phase 9E "
                "recommendation. Migrating this completed legacy application "
                "remains optional."
            )

    with st.expander("Blueprint lifecycle technical details", expanded=False):
        st.json(
            {
                "summary": summary,
                "eligibility": state["eligibility"],
                "candidate_id": summary["candidate_id"],
                "evaluation_id": summary["evaluation_id"],
                "blueprint_id": summary["blueprint_id"],
            }
        )
    return state

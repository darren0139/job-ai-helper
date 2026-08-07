"""Streamlit UI for explicit-scope Phase 9C evaluation."""

from __future__ import annotations

import json
from typing import Any

import streamlit as st

from database.blueprint_candidate_manager import list_blueprint_candidates
from database.blueprint_evaluation_manager import (
    save_or_reuse_blueprint_evaluation,
)
from database.jd_library_manager import get_all_job_descriptions
from tailoring.phase9b_blueprint_candidate import PHASE9B_VERSION
from tailoring.phase9c_blueprint_evaluation import (
    Phase9CEvaluationError,
    evaluate_blueprint_candidate,
    preview_selected_scope,
    selection_control_signature,
)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def render_phase9c_blueprint_evaluation(
    *,
    preferred_candidate_id: str = "",
    rerun_after_save: bool = False,
    completion_flash_key: str = "",
) -> None:
    st.divider()
    st.subheader("Phase 9C · Cross-JD Blueprint Evaluation")
    st.caption(
        "Evaluate one frozen active Phase 9B v3 candidate against only the saved "
        "JDs you explicitly select. This deterministic workflow does not tailor "
        "or mutate the candidate or JD library."
    )

    candidates = [
        candidate
        for candidate in list_blueprint_candidates(include_archived=False)
        if candidate.get("phase9b_version") == PHASE9B_VERSION
        and _clean(candidate.get("status")).lower() in {"candidate", "active"}
    ]
    if not candidates:
        st.info("No active Phase 9B v3 candidates are available.")
        return
    by_candidate = {
        str(candidate["candidate_id"]): candidate for candidate in candidates
    }
    candidate_options = list(by_candidate)
    preferred_index = next(
        (
            index
            for index, value in enumerate(candidate_options)
            if value == _clean(preferred_candidate_id)
        ),
        0,
    )
    candidate_id = st.selectbox(
        "Blueprint candidate",
        options=candidate_options,
        index=preferred_index,
        format_func=lambda value: (
            f"{by_candidate[value].get('candidate_name', 'Candidate')} · "
            f"{by_candidate[value].get('role_family', '')} · {value[:8]}"
        ),
        key="phase9c_candidate_id",
    )
    candidate = by_candidate[candidate_id]

    saved_jds = get_all_job_descriptions(limit=500)
    by_library_id = {
        int(jd["id"]): jd for jd in saved_jds if jd.get("id") is not None
    }
    if not by_library_id:
        st.info("Save job descriptions to the JD library before evaluating.")
        return
    selected_ids = st.multiselect(
        "Target JDs (explicit selection required)",
        options=list(by_library_id),
        default=[],
        format_func=lambda value: (
            f"{by_library_id[value].get('title', 'Untitled')} · "
            f"{by_library_id[value].get('company', '')} · JD {value}"
        ),
        help=(
            "Same-family JDs may be recommended by the classifications below, "
            "but no JD is selected automatically."
        ),
        key="phase9c_selected_jd_ids",
    )
    selected_jds = [by_library_id[value] for value in selected_ids]
    if not selected_jds:
        st.info("Explicitly select one or more saved target JDs.")
        return

    preview = preview_selected_scope(candidate, selected_jds)
    uncertain_keys = [
        row["jd_key"]
        for row in preview
        if row["family_match_status"] == "uncertain"
    ]
    allowed_uncertain = st.multiselect(
        "Explicitly include uncertain-family selections",
        options=uncertain_keys,
        default=[],
        help="Different-family JDs cannot be included in Phase 9C v1.",
        key="phase9c_allowed_uncertain",
    ) if uncertain_keys else []
    preview = preview_selected_scope(
        candidate,
        selected_jds,
        explicitly_allowed_uncertain=allowed_uncertain,
    )
    st.dataframe(
        [
            {
                "JD": row["jd_key"],
                "Classified family": row["classified_role_family"],
                "Status": row["family_match_status"],
                "Decision": row["selection_decision"],
                "Reason": row["selection_reason"],
            }
            for row in preview
        ],
        hide_index=True,
        width="stretch",
    )

    control_signature = selection_control_signature(
        candidate,
        selected_jds,
        explicitly_allowed_uncertain=allowed_uncertain,
    )
    result_key = "phase9c_current_evaluation"
    existing = st.session_state.get(result_key)
    if existing and existing.get("selection_control_signature") != control_signature:
        st.warning(
            "The previous Phase 9C result belongs to a different candidate or "
            "selected/excluded JD scope and is hidden until this exact scope is evaluated."
        )
        existing = None

    if st.button(
        "Evaluate exact selected scope",
        type="primary",
        key="phase9c_evaluate",
    ):
        try:
            evaluated = evaluate_blueprint_candidate(
                candidate=candidate,
                selected_jds=selected_jds,
                saved_jds_for_source_resolution=saved_jds,
                explicitly_allowed_uncertain=allowed_uncertain,
            )
            persisted = save_or_reuse_blueprint_evaluation(evaluated)
            existing = persisted["evaluation"]
            st.session_state[result_key] = existing
            if persisted["cache_status"] == "hit":
                message = "Exactly reused the identical persisted evaluation."
            else:
                message = "Saved the deterministic Phase 9C evaluation."
            if rerun_after_save:
                flash_key = (
                    completion_flash_key
                    or "phase9c_completion_flash"
                )
                st.session_state[flash_key] = (
                    message
                    + " The Blueprint Lifecycle advanced to Phase 9D."
                )
                st.rerun()
            st.success(message)
        except (Phase9CEvaluationError, ValueError, RuntimeError) as exc:
            st.error(str(exc))
            existing = None

    if not existing:
        return
    aggregate = existing["aggregate_result"]
    columns = st.columns(4)
    columns[0].metric("Mean score", aggregate["mean_score"])
    columns[1].metric("Minimum", aggregate["minimum_score"])
    columns[2].metric("Pass rate", f"{aggregate['pass_rate']}%")
    columns[3].metric(
        "Status",
        "Provisional" if aggregate["provisional"] else "Non-provisional",
    )
    st.dataframe(existing["per_jd_results"], hide_index=True, width="stretch")
    st.download_button(
        "Download Phase 9C JSON",
        data=json.dumps(existing, ensure_ascii=False, indent=2, default=str),
        file_name=(
            "phase9c_"
            + existing["evaluation_fingerprint"][:12]
            + ".json"
        ),
        mime="application/json",
        key="phase9c_download",
    )

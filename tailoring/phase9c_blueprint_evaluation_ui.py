"""Streamlit UI for explicit-scope Phase 9C evaluation."""

from __future__ import annotations

import json
from typing import Any

import streamlit as st

from database.blueprint_candidate_manager import list_blueprint_candidates
from database.blueprint_evaluation_manager import (
    list_blueprint_evaluations,
    save_or_reuse_blueprint_evaluation,
)
from database.jd_library_manager import get_all_job_descriptions
from tailoring.phase9b_blueprint_candidate import PHASE9B_VERSION
from tailoring.phase9c_blueprint_evaluation import (
    Phase9CEvaluationError,
    PHASE9C_POLICY_VERSION,
    evaluate_blueprint_candidate,
    preview_selected_scope,
    resolve_source_jd,
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
    preferred_id = _clean(preferred_candidate_id)
    if preferred_id:
        if preferred_id not in by_candidate:
            st.error(
                "The current application candidate is no longer available "
                "as an active Phase 9B candidate. Re-open Phase 8 / Phase 9B "
                "for this application before evaluating."
            )
            return
        candidate_options = [preferred_id]
        preferred_index = 0
        # The same widget key may have previously held another global
        # candidate. Synchronize it before instantiating the selectbox.
        st.session_state["phase9c_candidate_id"] = preferred_id
        st.caption(
            "This application lifecycle is locked to its current "
            "Phase 9B candidate. Historical or unrelated candidates are "
            "available only from their own lifecycle/history views."
        )
    else:
        candidate_options = list(by_candidate)
        preferred_index = 0

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

    historical_evaluations = [
        row
        for row in list_blueprint_evaluations(candidate_id=candidate_id)
        if _clean(
            ((row.get("semantic_identity") or {}).get("policy") or {}).get(
                "policy_version"
            )
        )
        != PHASE9C_POLICY_VERSION
    ]
    if historical_evaluations:
        st.warning(
            "This candidate has historical Phase 9C evaluation(s). They remain "
            "immutable and inspectable, but cannot be approved under the v4 "
            "target-sample contract. Evaluate a fresh explicit v4 target scope."
        )
        with st.expander("Inspect historical Phase 9C evaluation(s)", expanded=False):
            st.json(historical_evaluations)

    saved_jds = get_all_job_descriptions(limit=500)
    by_library_id = {
        int(jd["id"]): jd for jd in saved_jds if jd.get("id") is not None
    }
    if not by_library_id:
        st.info("Save job descriptions to the JD library before evaluating.")
        return
    try:
        source_jd, _source_identity = resolve_source_jd(candidate, saved_jds)
    except (Phase9CEvaluationError, ValueError, RuntimeError) as exc:
        st.error(str(exc))
        return

    source_library_id = source_jd.get("id")
    source_job = candidate.get("source_job") or {}
    source_title = _clean(source_job.get("job_title") or source_jd.get("title"))
    source_company = _clean(source_job.get("company") or source_jd.get("company"))
    with st.container(border=True):
        st.write("**Source JD / immutable provenance**")
        st.caption(
            "This is the JD that the frozen candidate already proved against. "
            "Phase 9C validates its immutable source parity separately; it is "
            "not a selectable portability target and never contributes to the "
            "cross-JD sample or mean."
        )
        st.write(
            f"{source_title or 'Source JD'}"
            + (f" · {source_company}" if source_company else "")
        )
        st.caption(
            f"JD {source_library_id if source_library_id is not None else '—'} · "
            f"canonical {_clean(source_jd.get('canonical_jd_id')) or '—'} · "
            f"version {_clean(source_jd.get('source_version_id')) or '—'}"
        )

    comparison_jds = [
        jd
        for jd in by_library_id.values()
        if jd.get("id") != source_library_id
    ]
    if not comparison_jds:
        st.info(
            "Phase 9C is pending: save another comparable JD before cross-JD "
            "portability can be established. The source JD is not substituted "
            "as a target."
        )
        return

    candidate_preview = preview_selected_scope(candidate, comparison_jds)
    preview_by_library_id = {
        int(row["library_jd_id"]): row
        for row in candidate_preview
        if row.get("library_jd_id") is not None
    }
    possible_target_ids = [
        library_id
        for library_id, row in preview_by_library_id.items()
        if row.get("family_match_status") in {"same", "uncertain"}
    ]
    st.write("**Comparable saved JDs**")
    st.caption(
        "Phase 9C tests other saved JDs in the same role family. Same-family "
        "rows are recommended, uncertain rows require explicit inclusion, and "
        "different-family rows remain visible but are deterministically excluded."
    )
    st.dataframe(
        [
            {
                "JD": (
                    f"{row.get('title', 'Untitled')} · "
                    f"{row.get('company', '')} · JD {row.get('id')}"
                ),
                "Classified family": preview_by_library_id[int(row["id"])].get(
                    "classified_role_family"
                ),
                "Target status": (
                    "Recommended same-family"
                    if preview_by_library_id[int(row["id"])].get(
                        "family_match_status"
                    ) == "same"
                    else "Uncertain — explicit inclusion required"
                    if preview_by_library_id[int(row["id"])].get(
                        "family_match_status"
                    ) == "uncertain"
                    else "Different family — excluded from sample"
                ),
            }
            for row in comparison_jds
        ],
        hide_index=True,
        width="stretch",
    )
    if not possible_target_ids:
        st.info(
            "Phase 9C is pending: no eligible non-source comparison target is "
            "currently saved. Save another comparable JD before evaluating."
        )
        return

    previous_selected = st.session_state.get("phase9c_selected_jd_ids", [])
    if isinstance(previous_selected, list):
        st.session_state["phase9c_selected_jd_ids"] = [
            int(value)
            for value in previous_selected
            if value in preview_by_library_id
        ]
    selected_ids = st.multiselect(
        "Target JDs (explicit selection required)",
        options=list(preview_by_library_id),
        default=[],
        format_func=lambda value: (
            f"{by_library_id[value].get('title', 'Untitled')} · "
            f"{by_library_id[value].get('company', '')} · JD {value} · "
            + (
                "recommended same-family"
                if preview_by_library_id[value]["family_match_status"] == "same"
                else "uncertain"
                if preview_by_library_id[value]["family_match_status"] == "uncertain"
                else "different family (excluded)"
            )
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
    previous_allowed = st.session_state.get("phase9c_allowed_uncertain", [])
    if isinstance(previous_allowed, list):
        st.session_state["phase9c_allowed_uncertain"] = [
            value for value in previous_allowed if value in uncertain_keys
        ]
    allowed_uncertain = st.multiselect(
        "Explicitly include uncertain-family selections",
        options=uncertain_keys,
        default=[],
        help="Different-family JDs cannot be included in Phase 9C v4.",
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

    counted_targets = [
        row for row in preview if row.get("aggregate_included") is True
    ]
    excluded_targets = [
        row for row in preview if row.get("selection_decision") == "excluded"
    ]
    accounting = st.columns(4)
    accounting[0].metric("Selected target JDs", len(preview))
    accounting[1].metric("Counted target JDs", len(counted_targets))
    accounting[2].metric("Excluded target JDs", len(excluded_targets))
    accounting[3].metric("Effective sample size", len(counted_targets))
    if not counted_targets:
        st.warning(
            "No selected non-source target is eligible. Select a same-family JD "
            "or explicitly include an uncertain-family JD; different-family JDs "
            "cannot establish portability."
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
        disabled=not counted_targets,
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
    columns = st.columns(5)
    columns[0].metric("Mean score", aggregate["mean_score"])
    columns[1].metric("Minimum", aggregate["minimum_score"])
    columns[2].metric("Pass rate", f"{aggregate['pass_rate']}%")
    columns[3].metric(
        "Status",
        "Provisional" if aggregate["provisional"] else "Non-provisional",
    )
    columns[4].metric(
        "Effective sample", aggregate.get("counted_target_jd_count", 0)
    )
    source_rows = [
        row
        for row in existing.get("per_jd_results", [])
        if row.get("is_source_jd") is True
    ]
    target_rows = [
        row
        for row in existing.get("per_jd_results", [])
        if row.get("target_sample_membership") is True
    ]
    st.write("**Source JD / provenance parity**")
    st.dataframe(source_rows, hide_index=True, width="stretch")
    st.write("**Counted target results**")
    st.dataframe(target_rows, hide_index=True, width="stretch")
    excluded = existing.get("excluded_jds") or []
    if excluded:
        st.write("**Excluded target JDs**")
        st.dataframe(excluded, hide_index=True, width="stretch")
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

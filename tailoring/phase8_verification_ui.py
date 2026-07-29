"""Streamlit UI for Phase 8 tailored-résumé verification."""

from __future__ import annotations

import json
from typing import Any

import streamlit as st

from database.tailoring_generation_control import (
    get_application_generation_control,
    list_tailoring_generations,
)
from database.tailoring_verification_manager import (
    get_latest_tailoring_verification,
    save_tailoring_verification,
)
from tailoring.phase8_verification import build_phase8_verification


def _label(state: dict[str, Any]) -> str:
    status = str(state.get("status") or "draft").title()
    short_id = str(state.get("generation_id") or "")[:8]
    pages = (state.get("fit_result") or {}).get("page_count", "—")
    return f"{status} · {short_id} · {pages} page(s)"


def _render_result(result: dict[str, Any]) -> None:
    comparison = result.get("comparison", {}) or {}
    lineage = result.get("claim_lineage", {}) or {}

    verdict = str(result.get("verdict") or "review_required")
    message = str(result.get("verdict_message") or "")
    if verdict == "invalid_canonical_mismatch":
        st.error(message)
    elif verdict == "improved":
        st.success(message)
    elif verdict == "maintained":
        st.info(message)
    else:
        st.warning(message)

    comparison_valid = bool(result.get("comparison_valid", True))
    metric1, metric2, metric3, metric4 = st.columns(4)
    metric1.metric(
        "Before score",
        comparison.get("before_score", 0),
    )
    metric2.metric(
        "After score",
        comparison.get("after_score", 0),
        delta=(
            comparison.get("score_delta", 0)
            if comparison_valid
            else None
        ),
    )
    metric3.metric(
        "Required/Core Δ",
        (
            comparison.get("required_core_coverage_delta", 0)
            if comparison_valid
            else "Invalid"
        ),
    )
    metric4.metric(
        "Claim reviews",
        lineage.get("claim_review_required_count", 0),
    )

    reconciliation = (
        result.get("requirement_reconciliation", {}) or {}
    )
    reconciled_rows = (
        reconciliation.get("reconciled_requirements", []) or []
    )
    unresolved_rows = (
        reconciliation.get("unresolved_regressions", []) or []
    )
    if reconciled_rows:
        st.info(
            "Phase 8 confirmed "
            f"{len(reconciled_rows)} initially reported evidence drop(s) "
            "were false alarms because the supporting final evidence is "
            "still present and verified."
        )
        with st.expander(
            "Final evidence reconciliation",
            expanded=False,
        ):
            st.dataframe(
                reconciled_rows,
                hide_index=True,
                width="stretch",
            )
    if unresolved_rows:
        st.warning(
            f"{len(unresolved_rows)} regression(s) could not be reconciled "
            "and remain genuine review items."
        )

    if not comparison_valid:
        added = comparison.get("added_requirements", []) or []
        removed = comparison.get("removed_requirements", []) or []
        st.error(
            "The canonical JD requirement set changed, so the displayed "
            "before/after scores are diagnostic only and must not be used for "
            "blueprint approval."
        )
        with st.expander(
            "Canonical requirement mismatch",
            expanded=True,
        ):
            st.write(
                f"Added requirement IDs: {len(added)} · "
                f"Removed requirement IDs: {len(removed)}"
            )
            if added:
                st.write("**Added after reconstruction**")
                st.dataframe(added, hide_index=True, width="stretch")
            if removed:
                st.write("**Missing after reconstruction**")
                st.dataframe(removed, hide_index=True, width="stretch")

    if result.get("blueprint_ready"):
        st.success(
            "Blueprint readiness: Passed. This approved one-page version "
            "maintained or improved alignment without detected evidence loss."
        )
    else:
        st.caption(
            "Blueprint readiness has not passed every Phase 8 gate."
        )
        st.json(result.get("blueprint_readiness_reasons", {}))

    improved = comparison.get("improved_requirements", []) or []
    regressed = comparison.get("regressed_requirements", []) or []
    if improved:
        with st.expander(
            f"Improved requirements ({len(improved)})",
            expanded=False,
        ):
            st.dataframe(improved, hide_index=True, width="stretch")
    if regressed:
        with st.expander(
            f"Regressed requirements ({len(regressed)})",
            expanded=True,
        ):
            st.dataframe(regressed, hide_index=True, width="stretch")

    bullet_risks = (
        lineage.get("project_bullet_review_risks", []) or []
    )
    skill_risks = lineage.get("skill_review_risks", []) or []
    if bullet_risks or skill_risks:
        with st.expander(
            "Evidence-lineage review",
            expanded=True,
        ):
            if bullet_risks:
                st.write("**Project bullets needing review**")
                st.dataframe(
                    bullet_risks,
                    hide_index=True,
                    width="stretch",
                )
            if skill_risks:
                st.write("**Skills needing review**")
                st.dataframe(
                    skill_risks,
                    hide_index=True,
                    width="stretch",
                )

    with st.expander("Phase 8 technical details", expanded=False):
        st.json(result)

    st.download_button(
        "Download Phase 8 Verification JSON",
        data=json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
            default=str,
        ).encode("utf-8"),
        file_name=(
            "phase8_verification_"
            f"{str(result.get('generation_id') or '')[:8]}.json"
        ),
        mime="application/json",
        width="stretch",
    )


def render_phase8_verification(
    *,
    application_id: int,
    baseline_report: dict[str, Any],
    raw_jd_text: str,
) -> None:
    st.divider()
    st.subheader("Phase 8 — Before/After Verification")
    st.caption(
        "Checks a fitted saved version against the original deterministic "
        "analysis. This verification makes no model or embedding calls."
    )

    versions = list_tailoring_generations(application_id)
    eligible = [
        state
        for state in versions
        if isinstance(state.get("fit_result"), dict)
    ]
    if not eligible:
        st.info(
            "Generate and fit a tailored résumé DOCX before running Phase 8."
        )
        return

    control = get_application_generation_control(application_id)
    approved = control.get("approved_generation")
    approved_id = (
        str(approved.get("generation_id") or "")
        if isinstance(approved, dict)
        else ""
    )
    default_index = next(
        (
            index
            for index, state in enumerate(eligible)
            if str(state.get("generation_id") or "") == approved_id
        ),
        0,
    )
    by_id = {
        str(state["generation_id"]): state
        for state in eligible
    }
    selected_id = st.selectbox(
        "Fitted version to verify",
        options=list(by_id),
        index=default_index,
        format_func=lambda value: _label(by_id[value]),
        key=f"phase8_generation_{application_id}",
    )
    selected = by_id[selected_id]

    status_col, pages_col, cost_col = st.columns(3)
    status_col.metric(
        "Status",
        str(selected.get("status") or "draft").title(),
    )
    pages_col.metric(
        "Pages",
        (selected.get("fit_result") or {}).get(
            "page_count",
            "—",
        ),
    )
    cost_col.metric(
        "Verification cost",
        "$0.000000",
    )

    if st.button(
        "Run Zero-Cost Before/After Verification",
        type="primary",
        width="stretch",
        key=f"phase8_verify_{application_id}_{selected_id}",
    ):
        try:
            with st.spinner(
                "Revalidating the final fitted evidence deterministically..."
            ):
                result = build_phase8_verification(
                    baseline_report=baseline_report,
                    generation_state=selected,
                    raw_jd_text=raw_jd_text,
                )
                saved = save_tailoring_verification(
                    application_id=application_id,
                    generation_id=selected_id,
                    result=result,
                )
            st.session_state[
                f"phase8_flash_{application_id}"
            ] = (
                "Reused the exact saved Phase 8 verification."
                if saved.get("cache_status") == "hit"
                else "Saved a new zero-cost Phase 8 verification."
            )
            st.rerun()
        except ValueError as exc:
            st.warning(str(exc))
        except Exception as exc:
            st.error(f"Phase 8 verification failed: {exc}")

    flash = st.session_state.pop(
        f"phase8_flash_{application_id}",
        "",
    )
    if flash:
        st.success(flash)

    latest = get_latest_tailoring_verification(
        application_id,
        selected_id,
    )
    if isinstance(latest, dict):
        _render_result(latest)
    else:
        st.caption(
            "No saved verification exists for this fitted version yet."
        )

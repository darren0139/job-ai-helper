"""Streamlit UI for Phase 9A Evidence Opportunity Analysis."""

from __future__ import annotations

from typing import Any

import streamlit as st

from database.evidence_opportunity_manager import (
    get_latest_evidence_opportunity,
    save_evidence_opportunity,
)
from tailoring.phase9a_evidence_opportunity import (
    build_evidence_opportunity_analysis,
)


def _render_result(result: dict[str, Any]) -> None:
    valid = bool(result.get("comparison_valid"))
    if not valid:
        st.error(
            "The canonical requirement IDs changed during the opportunity "
            "forecast, so its score delta is not safe to interpret."
        )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(
        "Current résumé",
        result.get("baseline_score", 0),
    )
    col2.metric(
        "Evidence-backed potential",
        result.get("potential_score", 0),
        delta=(
            result.get("score_delta", 0)
            if valid
            else None
        ),
    )
    col3.metric(
        "Selected evidence",
        result.get("selected_evidence_count", 0),
    )
    col4.metric("Analysis cost", "$0.000000")

    st.caption(str(result.get("forecast_notice") or ""))

    selected = result.get("selected_evidence", []) or []
    if selected:
        st.write("**Evidence selected for the constrained forecast**")
        st.dataframe(
            [
                {
                    "Evidence": row.get("title", ""),
                    "Category": row.get("category", ""),
                    "Period": row.get("period", ""),
                    "Estimated weighted gain": row.get(
                        "incremental_points",
                        0,
                    ),
                    "Requirements improved": len(
                        row.get("matched_requirements", []) or []
                    ),
                }
                for row in selected
            ],
            hide_index=True,
            width="stretch",
        )

        with st.expander(
            "Why each evidence item was selected",
            expanded=False,
        ):
            for row in selected:
                st.write(f"#### {row.get('title', 'Evidence')}")
                st.dataframe(
                    row.get("matched_requirements", []) or [],
                    hide_index=True,
                    width="stretch",
                )
    else:
        st.info(
            "No Evidence Library item produced a supported improvement under "
            "the current constraints."
        )

    improved = (
        result.get("comparison", {}) or {}
    ).get("improved_requirements", []) or []
    if improved:
        with st.expander(
            f"Forecast requirement improvements ({len(improved)})",
            expanded=False,
        ):
            st.dataframe(
                improved,
                hide_index=True,
                width="stretch",
            )

    unresolved = result.get("unresolved_requirements", []) or []
    if unresolved:
        with st.expander(
            f"Requirements still unsupported ({len(unresolved)})",
            expanded=False,
        ):
            st.dataframe(
                unresolved,
                hide_index=True,
                width="stretch",
            )

    with st.expander("Phase 9A technical details", expanded=False):
        st.json(result)


def render_evidence_opportunity_analysis(
    *,
    application_id: int,
    baseline_report: dict[str, Any],
    raw_jd_text: str,
    evidence_items: list[dict[str, Any]],
) -> None:
    st.divider()
    st.subheader("Phase 9A — Evidence Opportunity Analysis")
    st.caption(
        "Forecasts how much a realistically constrained selection from the "
        "Evidence Library could improve alignment. It does not replace the "
        "actual tailored résumé or Phase 8 verification."
    )

    if not evidence_items:
        st.info(
            "Add projects or other evidence to the Evidence Library before "
            "running this analysis."
        )
        return

    setting_col1, setting_col2, setting_col3 = st.columns(3)
    max_projects = setting_col1.number_input(
        "Maximum evidence projects",
        min_value=1,
        max_value=4,
        value=3,
        step=1,
        key=f"phase9a_max_projects_{application_id}",
    )
    max_bullets = setting_col2.number_input(
        "Maximum bullets per project",
        min_value=1,
        max_value=4,
        value=2,
        step=1,
        key=f"phase9a_max_bullets_{application_id}",
    )
    max_skills = setting_col3.number_input(
        "Maximum added Skills/Tools",
        min_value=0,
        max_value=30,
        value=20,
        step=1,
        key=f"phase9a_max_skills_{application_id}",
    )

    if st.button(
        "Analyse Evidence Opportunities",
        type="primary",
        width="stretch",
        key=f"phase9a_run_{application_id}",
    ):
        try:
            with st.spinner(
                "Scoring constrained Evidence Library opportunities..."
            ):
                result = build_evidence_opportunity_analysis(
                    application_id=application_id,
                    baseline_report=baseline_report,
                    raw_jd_text=raw_jd_text,
                    evidence_items=evidence_items,
                    max_projects=int(max_projects),
                    max_bullets_per_project=int(max_bullets),
                    max_skills=int(max_skills),
                )
                saved = save_evidence_opportunity(
                    application_id=application_id,
                    result=result,
                )
            st.session_state[
                f"phase9a_flash_{application_id}"
            ] = (
                "Reused the exact saved Evidence Opportunity Analysis."
                if saved.get("cache_status") == "hit"
                else "Saved a new zero-cost Evidence Opportunity Analysis."
            )
            st.rerun()
        except ValueError as exc:
            st.warning(str(exc))
        except Exception as exc:
            st.error(
                f"Evidence Opportunity Analysis failed: {exc}"
            )

    flash = st.session_state.pop(
        f"phase9a_flash_{application_id}",
        "",
    )
    if flash:
        st.success(flash)

    latest = get_latest_evidence_opportunity(application_id)
    if isinstance(latest, dict):
        _render_result(latest)
    else:
        st.caption(
            "No saved Evidence Opportunity Analysis exists for this "
            "application yet."
        )

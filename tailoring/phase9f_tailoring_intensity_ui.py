"""Read-only Streamlit presentation for Phase 9F-C."""

from __future__ import annotations

from typing import Any

import streamlit as st

from tailoring.phase9f_starting_source_ranking import canonical_json
from tailoring.phase9f_tailoring_intensity import (
    recommend_tailoring_intensity,
)


INTENSITY_DEFINITIONS = {
    "reuse": "Use the selected source essentially as-is for this JD.",
    "minor": (
        "Preserve the selected source and make bounded, targeted tailoring "
        "changes."
    ),
    "full": (
        "Perform broad regeneration or reselection because current-JD "
        "deficiencies are material."
    ),
}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def render_phase9f_tailoring_intensity(
    ranking_result: dict[str, Any],
    *,
    expected_ranking_input_fingerprint: str,
) -> dict[str, Any]:
    """Render one transient deterministic recommendation and return it."""
    recommendation = recommend_tailoring_intensity(
        ranking_result,
        expected_ranking_input_fingerprint=(
            expected_ranking_input_fingerprint
        ),
    )

    st.divider()
    st.subheader("Tailoring intensity")
    st.caption(
        "Given the already-selected Phase 9F-B source, determine how much "
        "current-JD tailoring is needed. This does not create an Application "
        "Session, bind a Tailoring Base, or start generation."
    )

    if recommendation.get("status") != "recommended":
        st.error(
            "Phase 9F-C failed closed. No Reuse, Minor, or Full recommendation "
            "is available for this scope."
        )
        st.warning(_clean(recommendation.get("failure_message")))
        st.caption(
            "Reason code: "
            f"{_clean(recommendation.get('failure_code')) or 'unknown'}"
        )
    else:
        intensity = _clean(recommendation.get("recommended_intensity"))
        label = _clean(recommendation.get("user_facing_label"))
        metrics = recommendation.get("metrics") or {}
        source = recommendation.get("selected_source_context") or {}
        with st.container(border=True):
            st.markdown(f"### Recommended tailoring: {label}")
            st.write(INTENSITY_DEFINITIONS.get(intensity, ""))
            exact_reuse = source.get("exact_verified_reuse") or {}
            if exact_reuse.get("eligible") is True:
                st.success("Exact verified reuse available")
                st.write(
                    "This Blueprint is the approved one-page résumé already "
                    "verified against this exact JD."
                )
                st.caption(
                    "Verified exact-JD score: "
                    f"{int(exact_reuse.get('verified_score') or 0)} · "
                    "fresh comparison metrics below are diagnostic only."
                )
            with st.container(horizontal=True):
                st.metric(
                    "Current JD alignment",
                    f"{int(metrics.get('current_jd_alignment') or 0)}%",
                    border=True,
                )
                st.metric(
                    "Required/Core",
                    f"{int(metrics.get('required_core_coverage') or 0)}%",
                    border=True,
                )
                st.metric(
                    "Evidence strength",
                    f"{int(metrics.get('evidence_strength') or 0)}%",
                    border=True,
                )
                st.metric(
                    "Important gaps",
                    (
                        f"{int(metrics.get('important_gap_count') or 0)} / "
                        f"{int(metrics.get('important_requirement_count') or 0)}"
                    ),
                    border=True,
                )
            st.caption(
                "Preferred coverage: "
                f"{int(metrics.get('preferred_coverage') or 0)}% "
                "(explanatory only; it does not determine intensity)."
            )
            st.markdown("**Why**")
            for reason in recommendation.get("explanation") or []:
                st.markdown(f"- {_clean(reason)}")
            st.caption(
                "Selected source: "
                f"{_clean(source.get('display_name')) or 'Immutable source'} | "
                f"{_clean(source.get('source_type')) or 'unknown type'} | "
                "role-family relationship: "
                f"{_clean(source.get('role_family_relationship')) or 'unavailable'}"
            )
            st.caption(
                "Source type and role-family context do not directly determine "
                "Reuse, Minor, or Full; exact verified source/JD/artifact "
                "provenance is a separate identity rule."
            )

    with st.expander(
        "Phase 9F-C deterministic policy and diagnostics",
        expanded=False,
    ):
        st.caption(
            "This is a transient, read-only result. The category and explanation "
            "are generated by deterministic Python from the exact current "
            "Phase 9F-B winner."
        )
        st.json(recommendation)
        st.download_button(
            "Download Phase 9F-C recommendation JSON",
            data=canonical_json(recommendation),
            file_name=(
                "phase9f_c_tailoring_intensity_"
                f"{_clean(recommendation.get('recommendation_fingerprint'))[:12]}"
                ".json"
            ),
            mime="application/json",
            key="phase9f_c_download_recommendation_json",
            width="stretch",
        )

    return recommendation

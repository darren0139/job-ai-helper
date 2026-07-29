from __future__ import annotations

import streamlit as st

from tailoring.phase8_verification import compare_stable_analyses


st.title("Phase 8 Zero-Cost Verification Harness")
st.caption("No model calls, embeddings, database writes, or DOCX rendering.")

before_score = st.slider("Before score", 0, 100, 50)
after_score = st.slider("After score", 0, 100, 60)
before_label = st.selectbox(
    "Before label",
    ["none", "weak", "transferable", "direct"],
    index=1,
)
after_label = st.selectbox(
    "After label",
    ["none", "weak", "transferable", "direct"],
    index=3,
)

base_row = {
    "requirement_id": "req_demo",
    "text": "Demonstrate Python",
    "importance": "required",
    "evidence_strength": 3,
}
before = {
    "deterministic_alignment_score": before_score,
    "alignment_band": "demo",
    "required_core_coverage_score": before_score,
    "preferred_coverage_score": 0,
    "evidence_strength_score": 60,
    "canonical_requirements": [
        {**base_row, "match_label": before_label}
    ],
}
after = {
    "deterministic_alignment_score": after_score,
    "alignment_band": "demo",
    "required_core_coverage_score": after_score,
    "preferred_coverage_score": 0,
    "evidence_strength_score": 60,
    "canonical_requirements": [
        {**base_row, "match_label": after_label}
    ],
}

result = compare_stable_analyses(before, after)
st.metric("Score delta", result["score_delta"])
st.json(result)

if result["important_regressions"]:
    st.warning("Required/core regression detected.")
else:
    st.success("No required/core regression detected.")

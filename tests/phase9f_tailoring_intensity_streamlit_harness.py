from __future__ import annotations

import streamlit as st

from tailoring.phase9f_tailoring_intensity_ui import (
    render_phase9f_tailoring_intensity,
)
from tests.test_phase9f_tailoring_intensity import make_phase9f_b_result


mode = st.selectbox(
    "Harness scope",
    ["reuse", "preferred_only", "minor", "full"],
    key="phase9f_c_harness_scope",
)

if mode == "preferred_only":
    values = {
        "overall": 50,
        "required_core": 0,
        "preferred": 100,
        "evidence": 100,
        "important_requirement_count": 0,
        "important_gap_count": 0,
        "deal_breaker_gap_count": 0,
        "preferred_requirement_count": 3,
    }
elif mode == "minor":
    values = {
        "overall": 79,
        "required_core": 80,
        "preferred": 100,
        "evidence": 80,
        "important_requirement_count": 10,
        "important_gap_count": 0,
        "deal_breaker_gap_count": 0,
        "preferred_requirement_count": 2,
    }
elif mode == "full":
    values = {
        "overall": 100,
        "required_core": 100,
        "preferred": 100,
        "evidence": 100,
        "important_requirement_count": 10,
        "important_gap_count": 1,
        "deal_breaker_gap_count": 1,
        "preferred_requirement_count": 2,
    }
else:
    values = {
        "overall": 90,
        "required_core": 90,
        "preferred": 20,
        "evidence": 80,
        "important_requirement_count": 10,
        "important_gap_count": 0,
        "deal_breaker_gap_count": 0,
        "preferred_requirement_count": 2,
    }

ranking = make_phase9f_b_result(name=f"streamlit-{mode}", **values)
result = render_phase9f_tailoring_intensity(
    ranking,
    expected_ranking_input_fingerprint=ranking["ranking_input_fingerprint"],
)
st.session_state["phase9f_c_test_result"] = result
zero = result["zero_cost_diagnostics"]
st.markdown(f"MODEL_CALLS={zero['model_call_count']}")
st.markdown(f"EMBEDDING_CALLS={zero['embedding_call_count']}")
st.markdown(f"CHROMA_READS={zero['chroma_read_count']}")
st.markdown(f"CHROMA_WRITES={zero['chroma_write_count']}")
st.markdown(f"PERSISTENCE_WRITES={zero['persistence_write_count']}")


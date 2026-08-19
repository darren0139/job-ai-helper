"""Isolated Streamlit harness for Phase 9F-A JD intake."""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from database import jd_library_manager


database_path = os.environ.get("PHASE9F_TEST_DATABASE", "").strip()
if not database_path:
    raise RuntimeError("PHASE9F_TEST_DATABASE is required.")
jd_library_manager.DB_PATH = Path(database_path)

from tailoring import phase9f_orchestrator_ui as ui  # noqa: E402


def _fake_extract(raw_text: str) -> dict:
    st.session_state["phase9f_test_model_calls"] = int(
        st.session_state.get("phase9f_test_model_calls", 0)
    ) + 1
    return {
        "job_title": "Junior AI Full-Stack Engineer",
        "company": "Example Company",
        "location": "Singapore",
        "experience_level": "Junior",
        "responsibilities": [
            "Build full-stack applications with Python and React."
        ],
        "required_skills": ["Python", "React"],
        "preferred_skills": ["PostgreSQL"],
        "tools_technologies": ["Python", "React", "PostgreSQL"],
        "soft_skills": ["Collaboration"],
        "buzzwords": [],
        "deal_breakers": [],
    }


def _fake_index(_jd_id: int) -> int:
    st.session_state["phase9f_test_embedding_calls"] = int(
        st.session_state.get("phase9f_test_embedding_calls", 0)
    ) + 1
    return 0


ui.extract_jd_profile = _fake_extract
ui.index_job_description_to_chroma = _fake_index

st.set_page_config(page_title="Phase 9F-A Test", layout="wide")
ui.render_phase9f_jd_intake()
st.markdown(
    "MODEL_CALLS="
    f"{int(st.session_state.get('phase9f_test_model_calls', 0))}"
)
st.markdown(
    "EMBEDDING_CALLS="
    f"{int(st.session_state.get('phase9f_test_embedding_calls', 0))}"
)

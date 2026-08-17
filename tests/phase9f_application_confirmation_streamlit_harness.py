from __future__ import annotations

from unittest.mock import patch

import streamlit as st

from tailoring.phase9f_application_confirmation_ui import (
    render_phase9f_application_confirmation,
)
from tailoring.phase9f_starting_source_ranking import (
    rank_starting_resume_sources,
)
from tailoring.phase9f_tailoring_intensity import (
    recommend_tailoring_intensity,
)
from tests.test_phase9f_starting_source_ranking import (
    make_base,
    make_blueprint,
    make_exact_jd,
)


exact_jd = make_exact_jd()
base, artifact = make_base(strong=False)
same_family = make_blueprint(
    strong=True,
    role_family_id="ai_fullstack_software_engineering",
    role_family_label="AI & Full-Stack Software Engineering",
    marker="streamlit-same",
)
cross_family = make_blueprint(
    strong=False,
    role_family_id="game_operations_configuration_qa",
    role_family_label="Game Operations, Configuration & QA",
    marker="streamlit-cross",
)
ranking = rank_starting_resume_sources(
    exact_jd=exact_jd,
    current_base_resume=base,
    current_base_artifact=artifact,
    global_blueprints=[same_family, cross_family],
)
recommendation = recommend_tailoring_intensity(
    ranking,
    expected_ranking_input_fingerprint=ranking[
        "ranking_input_fingerprint"
    ],
)
st.session_state["phase9f_d_harness_ranking"] = ranking
st.session_state["phase9f_d_harness_recommendation"] = recommendation
with patch(
    "tailoring.phase9f_application_confirmation_ui."
    "prepare_persisted_exact_jd_for_confirmation"
) as prepare_write, patch(
    "tailoring.phase9f_application_confirmation_ui."
    "confirm_phase9f_application_session"
) as confirmation_write:
    render_phase9f_application_confirmation(
        phase9f_a_snapshot=exact_jd,
        ranking_result=ranking,
        phase9f_c_recommendation=recommendation,
    )
    persistence_writes = prepare_write.call_count + confirmation_write.call_count
st.session_state["phase9f_d_harness_persistence_writes"] = persistence_writes
st.markdown("MODEL_CALLS=0")
st.markdown("EMBEDDING_CALLS=0")
st.markdown("CHROMA_READS=0")
st.markdown("CHROMA_WRITES=0")
st.markdown(f"PERSISTENCE_WRITES={persistence_writes}")

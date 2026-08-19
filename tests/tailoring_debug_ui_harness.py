from __future__ import annotations

import streamlit as st

from tailoring.tailoring_debug_ui import (
    render_lazy_fitting_debug,
    render_lazy_full_debug_bundle,
)


def _create_full_debug_bundle(**_kwargs) -> tuple[bytes, str]:
    st.session_state["debug_bundle_builder_calls"] = int(
        st.session_state.get("debug_bundle_builder_calls", 0)
    ) + 1
    return b'{"bundle":"prepared"}', "prepared-debug-bundle.json"


render_lazy_full_debug_bundle(
    application_id=77,
    has_debug_content=True,
    create_full_debug_bundle=_create_full_debug_bundle,
    bundle_kwargs={"application_id": 77},
)
render_lazy_fitting_debug(
    application_id=77,
    fit_result={
        "attempts": [{"attempt": 1, "private": "attempt payload"}],
        "tailored_projects_used": {
            "recommended_projects": [{"private": "project payload"}],
        },
        "tailored_skills_used": {
            "skill_lines": [{"private": "skills payload"}],
        },
    },
)
st.write(f"DEBUG_BUNDLE_BUILDER_CALLS={st.session_state.get('debug_bundle_builder_calls', 0)}")

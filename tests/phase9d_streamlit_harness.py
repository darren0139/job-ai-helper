"""Real Streamlit test harness for the Phase 9D page."""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from database import tailoring_version_manager as base_manager


database_path = os.environ.get("PHASE9D_TEST_DATABASE", "").strip()
if not database_path:
    raise RuntimeError("PHASE9D_TEST_DATABASE is required for the test harness.")
base_manager.DB_PATH = Path(database_path)

from tailoring.phase9d_global_blueprint_ui import (  # noqa: E402
    render_phase9d_global_blueprints,
)


st.set_page_config(page_title="Phase 9D Acceptance", layout="wide")
render_phase9d_global_blueprints()

"""Isolated passive Streamlit harness for Phase 9F-Master."""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from database import tailoring_version_manager as base_manager


database_path = os.environ.get("PHASE9F_MASTER_TEST_DATABASE", "").strip()
if not database_path:
    raise RuntimeError("PHASE9F_MASTER_TEST_DATABASE is required.")
base_manager.DB_PATH = Path(database_path)

from tailoring.phase9f_master_resume_ui import (  # noqa: E402
    render_phase9f_master_resume,
)


st.set_page_config(page_title="Phase 9F-Master Test", layout="wide")
render_phase9f_master_resume()
st.markdown("MODEL_CALLS=0")
st.markdown("EMBEDDING_CALLS=0")

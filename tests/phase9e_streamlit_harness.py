from __future__ import annotations

import json
import os
from pathlib import Path

import streamlit as st

from database import db_manager, jd_library_manager, tailoring_version_manager
from database import application_resume_result_manager as result_manager
from tailoring.phase9e_blueprint_selection_ui import (
    render_phase9e_blueprint_selection,
)


database_path = Path(os.environ["PHASE9E_TEST_DATABASE"])
db_manager.DB_PATH = database_path
jd_library_manager.DB_PATH = database_path
tailoring_version_manager.DB_PATH = database_path
result_manager.APPLICATION_RESULT_ARTIFACT_DIR = (
    database_path.parent / "application-results"
)

connection = db_manager._connect()
try:
    row = connection.execute(
        "SELECT report_json FROM applications WHERE id = 94"
    ).fetchone()
finally:
    connection.close()

report = json.loads(row[0])
context = render_phase9e_blueprint_selection(
    application_id=94,
    baseline_report=report,
)
st.write(f"GENERATION_CONTEXT={context.get('status')}")

from __future__ import annotations

import json
import os
from pathlib import Path

import streamlit as st

from database import db_manager, jd_library_manager, tailoring_version_manager
from tailoring.phase9e_blueprint_selection_ui import (
    render_phase9e_blueprint_selection,
)


database_path = Path(os.environ["PHASE9F_D_TEST_DATABASE"])
application_id = int(os.environ["PHASE9F_D_TEST_APPLICATION_ID"])
db_manager.DB_PATH = database_path
jd_library_manager.DB_PATH = database_path
tailoring_version_manager.DB_PATH = database_path

connection = db_manager._connect()
try:
    row = connection.execute(
        "SELECT report_json FROM applications WHERE id = ?",
        (application_id,),
    ).fetchone()
finally:
    connection.close()

report = json.loads(row[0])
context = render_phase9e_blueprint_selection(
    application_id=application_id,
    baseline_report=report,
)
st.markdown(f"CONTEXT_STATUS={context.get('status')}")
st.markdown(
    f"SOURCE_BINDING_STATUS={context.get('source_binding_status')}"
)
st.markdown(f"EXECUTION_STATUS={context.get('execution_status')}")
st.markdown(
    f"CONFIRMED_INTENSITY={context.get('confirmed_intensity')}"
)
st.markdown(f"CAN_GENERATE={context.get('can_generate')}")

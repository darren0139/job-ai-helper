from __future__ import annotations

import json
import os
from pathlib import Path

import streamlit as st

from database import db_manager, jd_library_manager, tailoring_version_manager
from database.phase9f_application_execution_manager import (
    execute_phase9f_reuse as _execute_phase9f_reuse,
)
from tailoring.phase9e_blueprint_selection_ui import (
    render_phase9e_blueprint_selection,
)
import tailoring.phase9f_application_execution_ui as execution_ui


database_path = Path(os.environ["PHASE9F_E_TEST_DATABASE"])
application_id = int(os.environ["PHASE9F_E_TEST_APPLICATION_ID"])
artifact_root = Path(os.environ["PHASE9F_E_TEST_ARTIFACT_ROOT"])

db_manager.DB_PATH = database_path
jd_library_manager.DB_PATH = database_path
tailoring_version_manager.DB_PATH = database_path


def _execute_for_test(*, application_id: int, actor_label: str):
    return _execute_phase9f_reuse(
        application_id=application_id,
        actor_label=actor_label,
        artifact_root=artifact_root,
    )


execution_ui.execute_phase9f_reuse = _execute_for_test

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
state = execution_ui.render_phase9f_reuse_execution(
    application_id=application_id,
    phase9e_context=context,
)
st.write(f"EXECUTION_STATUS={state.get('status')}")
st.write(f"OWNS_WORKFLOW={state.get('owns_workflow')}")

from __future__ import annotations

import json
import os
from pathlib import Path

from database import db_manager, jd_library_manager, tailoring_version_manager
from database import application_resume_result_manager as result_manager
from database.application_resume_result_manager import (
    get_current_application_resume_result,
)
from tailoring.phase9e_application_result_ui import (
    render_phase9e_application_result,
)
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


def fixture_cover_letter_generator(system: str, user: str, model_id: str):
    return (
        "Deterministic Streamlit cover letter.",
        {
            "model_id": model_id,
            "model_calls": 1,
            "embedding_calls": 0,
        },
    )


render_phase9e_blueprint_selection(
    application_id=94,
    baseline_report=report,
)
current = get_current_application_resume_result(94)
if current is not None and (
    current.get("state") or {}
).get("active_output_mode") == "immutable_result":
    render_phase9e_application_result(
        application_id=94,
        result=current,
        cover_letter_generator=fixture_cover_letter_generator,
    )

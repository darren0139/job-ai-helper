from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

from database import tailoring_version_manager as base_manager
from database.global_blueprint_manager import list_global_blueprints
from tests.phase9d_test_support import (
    persist_historical_v2_evaluation,
    seed_phase9d_database,
)


HARNESS = Path(__file__).with_name("phase9d_streamlit_harness.py")


def _by_key(elements, key):
    return next(element for element in elements if element.key == key)


class Phase9DStreamlitAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.old_path = base_manager.DB_PATH
        self.old_environment = os.environ.get("PHASE9D_TEST_DATABASE")
        self.database_path = Path(self.temporary.name) / "streamlit-phase9d.sqlite"
        self.state = seed_phase9d_database(self.database_path)
        self.historical = persist_historical_v2_evaluation(
            self.state["provisional_evaluation"]
        )
        os.environ["PHASE9D_TEST_DATABASE"] = str(self.database_path)

    def tearDown(self) -> None:
        base_manager.DB_PATH = self.old_path
        if self.old_environment is None:
            os.environ.pop("PHASE9D_TEST_DATABASE", None)
        else:
            os.environ["PHASE9D_TEST_DATABASE"] = self.old_environment
        self.temporary.cleanup()

    def test_historical_is_disabled_and_provisional_requires_explicit_override(self):
        app = AppTest.from_file(str(HARNESS), default_timeout=30).run()
        self.assertEqual(list(app.exception), [])
        evaluation = _by_key(app.selectbox, "phase9d_evaluation_id")
        evaluation.set_value(self.historical["evaluation_id"]).run()
        approve = _by_key(app.button, "phase9d_approve")
        self.assertTrue(approve.disabled)
        self.assertTrue(
            any("inspection" in warning.value.lower() for warning in app.warning)
        )

        evaluation = _by_key(app.selectbox, "phase9d_evaluation_id")
        evaluation.set_value(
            self.state["provisional_evaluation"]["evaluation_id"]
        ).run()
        acknowledgement = _by_key(
            app.checkbox, "phase9d_provisional_acknowledgement"
        )
        self.assertFalse(acknowledgement.value)
        self.assertTrue(_by_key(app.button, "phase9d_approve").disabled)

        acknowledgement.set_value(True)
        reason = _by_key(app.text_area, "phase9d_provisional_reason")
        reason.set_value(
            "Source parity is strong while more target JDs are collected."
        ).run()
        approve = _by_key(app.button, "phase9d_approve")
        self.assertFalse(approve.disabled)
        approve.click().run()
        self.assertEqual(list(app.exception), [])
        self.assertTrue(
            any("immutable blueprint" in message.value for message in app.success)
        )
        versions = list_global_blueprints()
        self.assertEqual(len(versions), 1)
        self.assertEqual(versions[0]["status"], "active")
        snapshot = versions[0]["blueprint_snapshot"]
        self.assertIn("frozen_resume_snapshot", snapshot)
        self.assertIn("phase9b_candidate_semantic_snapshot", snapshot)
        self.assertIn("phase9c_evaluation_snapshot", snapshot)

    def test_main_app_registers_top_level_global_blueprints_route(self):
        source = (HARNESS.parents[1] / "app.py").read_text(encoding="utf-8")
        self.assertIn('"Global Blueprints"', source)
        self.assertIn('elif page == "Global Blueprints":', source)
        self.assertIn("render_phase9d_global_blueprints(", source)
        self.assertIn(
            "current_application_id=current_application_id",
            source,
        )


if __name__ == "__main__":
    unittest.main()

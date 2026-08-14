from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

from database import global_master_resume_manager as manager
from database import tailoring_version_manager as base_manager


HARNESS = Path(__file__).with_name("phase9f_master_streamlit_harness.py")
REPO_ROOT = HARNESS.parents[1]


def _contains(elements, expected: str) -> bool:
    return any(expected in str(element.value) for element in elements)


class Phase9FMasterStreamlitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.old_path = base_manager.DB_PATH
        self.old_environment = os.environ.get("PHASE9F_MASTER_TEST_DATABASE")
        self.database_path = Path(self.temporary.name) / "master-ui.sqlite"
        base_manager.DB_PATH = self.database_path
        manager.init_global_master_resume_registry()
        os.environ["PHASE9F_MASTER_TEST_DATABASE"] = str(self.database_path)

    def tearDown(self) -> None:
        base_manager.DB_PATH = self.old_path
        if self.old_environment is None:
            os.environ.pop("PHASE9F_MASTER_TEST_DATABASE", None)
        else:
            os.environ["PHASE9F_MASTER_TEST_DATABASE"] = self.old_environment
        self.temporary.cleanup()

    def _row_counts(self) -> tuple[int, int, int, int]:
        connection = sqlite3.connect(self.database_path)
        try:
            return tuple(
                int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                for table in (
                    "global_master_resume_versions",
                    "global_master_resume_artifacts",
                    "global_master_resume_state",
                    "global_master_resume_events",
                )
            )
        finally:
            connection.close()

    def test_passive_render_history_and_download_surface_are_zero_call_read_only(self):
        before = self._row_counts()
        app = AppTest.from_file(str(HARNESS), default_timeout=30).run()
        self.assertEqual(list(app.exception), [])
        self.assertTrue(_contains(app.subheader, "Base Resume"))
        self.assertTrue(_contains(app.markdown, "MODEL_CALLS=0"))
        self.assertTrue(_contains(app.markdown, "EMBEDDING_CALLS=0"))
        self.assertTrue(
            any(
                item.label == "Base Resume version history"
                for item in app.expander
            )
        )
        app.run()
        self.assertEqual(list(app.exception), [])
        self.assertEqual(self._row_counts(), before)

    def test_app_integrates_dedicated_ui_without_phase9f_b(self):
        source = (REPO_ROOT / "app.py").read_text(encoding="utf-8")
        ui_source = (
            REPO_ROOT / "tailoring" / "phase9f_master_resume_ui.py"
        ).read_text(encoding="utf-8")
        self.assertIn("init_global_master_resume_registry()", source)
        self.assertIn("render_phase9f_master_resume()", source)
        self.assertIn('elif page == "Profile & Evidence":', source)
        self.assertNotIn("phase9f_b", ui_source.lower())
        self.assertNotIn("index_job_description_to_chroma", ui_source)
        self.assertIn("Remove Current Base Resume", ui_source)
        self.assertIn("clear_current_global_master_resume", ui_source)
        self.assertNotIn('st.subheader("Global Master Resume")', ui_source)


if __name__ == "__main__":
    unittest.main()

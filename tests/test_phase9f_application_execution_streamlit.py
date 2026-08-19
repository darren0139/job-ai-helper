from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from database import db_manager, jd_library_manager, tailoring_version_manager
from database.application_resume_result_manager import (
    list_application_result_verifications,
    list_application_resume_results,
)
from database.phase9f_application_execution_manager import (
    get_phase9f_application_execution,
)
from tests.phase9f_d_test_support import configure_database
from tests.phase9f_e_test_support import create_d_reuse_session


REPO_ROOT = Path(__file__).resolve().parents[1]
HARNESS = REPO_ROOT / "tests" / (
    "phase9f_application_execution_streamlit_harness.py"
)


def _contains(elements, text: str) -> bool:
    return any(text in str(item.value) for item in elements)


def _metric_value(elements, label: str) -> str:
    matches = [
        str(item.value)
        for item in elements
        if str(getattr(item, "label", "")) == label
    ]
    if len(matches) != 1:
        raise AssertionError(
            f"Expected exactly one metric labelled {label!r}; got {matches!r}"
        )
    return matches[0]


class Phase9FApplicationExecutionStreamlitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.database_path = self.root / "phase9f-e-streamlit.db"
        self.source_root = self.root / "sources"
        self.source_root.mkdir()
        self.result_root = self.root / "results"
        self.old_paths = (
            db_manager.DB_PATH,
            jd_library_manager.DB_PATH,
            tailoring_version_manager.DB_PATH,
        )
        configure_database(self.database_path)
        state = create_d_reuse_session(
            self.database_path,
            source_type="base_resume",
            artifact_root=self.source_root,
        )
        self.application_id = state["application_id"]
        self.environment = {
            "PHASE9F_E_TEST_DATABASE": str(self.database_path),
            "PHASE9F_E_TEST_APPLICATION_ID": str(self.application_id),
            "PHASE9F_E_TEST_ARTIFACT_ROOT": str(self.result_root),
        }

    def tearDown(self) -> None:
        (
            db_manager.DB_PATH,
            jd_library_manager.DB_PATH,
            tailoring_version_manager.DB_PATH,
        ) = self.old_paths
        self.temporary.cleanup()

    def _counts(self) -> dict[str, int]:
        connection = tailoring_version_manager._connect()
        try:
            names = {
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            tables = (
                "phase9f_application_executions",
                "phase9f_application_execution_events",
                "application_resume_results",
                "application_resume_result_artifacts",
                "application_resume_result_events",
                "application_result_verifications",
                "application_tailoring_versions",
            )
            return {
                table: (
                    int(
                        connection.execute(
                            f"SELECT COUNT(*) FROM {table}"
                        ).fetchone()[0]
                    )
                    if table in names
                    else 0
                )
                for table in tables
            }
        finally:
            connection.close()

    def _run(self) -> AppTest:
        with patch.dict(os.environ, self.environment):
            return AppTest.from_file(str(HARNESS), default_timeout=60).run()

    def test_passive_render_is_read_only_and_explicit_begin_survives_restart(self) -> None:
        before = self._counts()
        app = self._run()
        self.assertEqual(app.exception, [])
        self.assertEqual(self._counts(), before)
        self.assertTrue(
            _contains(app.info, "Tailoring execution has not started")
        )
        begin = next(
            button for button in app.button if button.label == "Begin Reuse tailoring"
        )
        self.assertFalse(begin.disabled)
        self.assertTrue(_contains(app.markdown, "EXECUTION_STATUS=not_started"))

        with patch.dict(os.environ, self.environment):
            completed = begin.click().run(timeout=60)
        self.assertEqual(completed.exception, [])
        self.assertTrue(_contains(completed.success, "Reuse execution completed"))
        self.assertTrue(_contains(completed.markdown, "EXECUTION_STATUS=completed"))
        self.assertFalse(
            any(button.label == "Begin Reuse tailoring" for button in completed.button)
        )
        execution = get_phase9f_application_execution(self.application_id)
        self.assertIsNotNone(execution)
        result_id = execution["application_result_id"]
        self.assertEqual(len(list_application_resume_results(self.application_id)), 1)
        self.assertEqual(
            self._counts()["application_tailoring_versions"], 0
        )

        verifications = list_application_result_verifications(result_id)
        self.assertTrue(verifications)
        phase8 = verifications[-1]["phase8_result"]
        after = phase8.get("after_stable_analysis") or {}
        seed_aggregate = (
            (phase8.get("final_scoring_seed") or {}).get("aggregate")
            or {}
        )

        def expected_metric(name: str) -> str:
            value = after.get(name)
            if value is None:
                value = seed_aggregate.get(name)
            return f"{int(value)}%"

        self.assertEqual(
            _metric_value(completed.metric, "Final alignment"),
            expected_metric("deterministic_alignment_score"),
        )
        self.assertEqual(
            _metric_value(completed.metric, "Final Required/Core"),
            expected_metric("required_core_coverage_score"),
        )
        self.assertEqual(
            _metric_value(completed.metric, "Final Preferred"),
            expected_metric("preferred_coverage_score"),
        )
        self.assertEqual(
            _metric_value(completed.metric, "Final evidence strength"),
            expected_metric("evidence_strength_score"),
        )
        self.assertTrue(
            _contains(completed.caption, "Execution status: completed")
        )
        self.assertFalse(
            _contains(completed.caption, "Execution status: not started")
        )
        self.assertFalse(
            any(
                expander.label == "Source Blueprint lineage"
                for expander in completed.expander
            )
        )

        completed_button_labels = [
            button.label for button in completed.button
        ]
        self.assertIn(
            "Prepare Phase 8 JSON download",
            completed_button_labels,
        )
        self.assertIn(
            "Prepare Phase 9F-E audit JSON",
            completed_button_labels,
        )

        before_audit_prepare = self._counts()
        prepare_audit = next(
            button
            for button in completed.button
            if button.label == "Prepare Phase 9F-E audit JSON"
        )
        with patch.dict(os.environ, self.environment):
            audit_ready = prepare_audit.click().run(timeout=60)
        self.assertEqual(audit_ready.exception, [])
        self.assertEqual(self._counts(), before_audit_prepare)
        self.assertTrue(
            _contains(
                audit_ready.caption,
                "Audit export prepared",
            )
        )

        completed_counts = self._counts()
        restarted = self._run()
        self.assertEqual(restarted.exception, [])
        self.assertEqual(self._counts(), completed_counts)
        self.assertTrue(_contains(restarted.success, "Reuse execution completed"))
        self.assertFalse(
            any(button.label == "Begin Reuse tailoring" for button in restarted.button)
        )
        restarted_execution = get_phase9f_application_execution(
            self.application_id
        )
        self.assertEqual(restarted_execution["application_result_id"], result_id)
        self.assertEqual(len(list_application_resume_results(self.application_id)), 1)


if __name__ == "__main__":
    unittest.main()

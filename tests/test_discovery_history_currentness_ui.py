from __future__ import annotations

from contextlib import contextmanager
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database import db_manager
from tailoring.initial_analysis_explainer_ui import (
    _discovery_source_currentness,
    render_discovery_history,
)


class _FakeStreamlit:
    def __init__(self):
        self.expanders = []
        self.captions = []
        self.warnings = []

    @contextmanager
    def expander(self, label, *args, **kwargs):
        self.expanders.append(label)
        yield self

    def caption(self, value, *args, **kwargs):
        self.captions.append(str(value))

    def warning(self, value, *args, **kwargs):
        self.warnings.append(str(value))


class DiscoveryHistoryCurrentnessTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.tempdir.name) / "applications.db"
        connection = sqlite3.connect(self.database_path)
        connection.execute(
            """
            CREATE TABLE discovered_jobs (
                id INTEGER PRIMARY KEY,
                description TEXT NOT NULL,
                content_hash TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO discovered_jobs(id, description, content_hash)
            VALUES (4103, ?, ?)
            """,
            (
                "Job description\nPartner with stakeholders.",
                "current-hash",
            ),
        )
        connection.commit()
        connection.close()

    def tearDown(self):
        self.tempdir.cleanup()

    def _view(self, raw_text):
        return {
            "provenance": "JOB_FINDER_INITIAL_MATCH",
            "identity": {
                "application_id": 17,
                "discovered_job_id": 4103,
            },
            "raw_jd_text": raw_text,
            "stable_analysis": {
                "canonical_requirements": [{"requirement_id": "r1"}]
            },
        }

    def test_frozen_discovery_match_reports_unchanged_source_jd(self):
        with patch.object(db_manager, "DB_PATH", self.database_path):
            result = _discovery_source_currentness(
                self._view(
                    "Job description\nPartner with stakeholders."
                )
            )

        self.assertEqual(result["status"], "unchanged")
        self.assertEqual(result["current_content_hash"], "current-hash")

    def test_frozen_discovery_match_reports_changed_source_jd(self):
        with patch.object(db_manager, "DB_PATH", self.database_path):
            result = _discovery_source_currentness(
                self._view(
                    "Job description\n"
                    "Partner\\u202fwith\\u202fstakeholders."
                )
            )

        self.assertEqual(result["status"], "changed")
        self.assertEqual(result["current_content_hash"], "current-hash")

    def test_application_history_labels_changed_receipt_as_historical(self):
        st = _FakeStreamlit()
        historical = self._view(
            "Job description\nPartner\\u202fwith\\u202fstakeholders."
        )

        with patch(
            "tailoring.initial_analysis_explainer_ui.load_application_initial",
            return_value=historical,
        ), patch(
            "tailoring.initial_analysis_explainer_ui._discovery_source_currentness",
            return_value={
                "status": "changed",
                "current_content_hash": "current-hash",
            },
        ), patch(
            "tailoring.initial_analysis_explainer_ui.render_analysis_receipt",
        ):
            render_discovery_history(st, 17)

        self.assertIn("Historical Discovery Match", st.expanders)
        self.assertTrue(
            any(
                "current Job Finder source JD has changed" in warning
                for warning in st.warnings
            )
        )
        self.assertTrue(
            any(
                "will not be rewritten" in warning
                for warning in st.warnings
            )
        )


if __name__ == "__main__":
    unittest.main()

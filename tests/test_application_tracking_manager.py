from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from database import db_manager
from database.application_tracking_manager import (
    delete_application_tracking,
    get_application_tracking,
    init_application_tracking_schema,
    list_application_tracking_rows,
    update_application_tracking,
)


class ApplicationTrackingManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_path = db_manager.DB_PATH
        db_manager.DB_PATH = Path(self.temp.name) / "applications.db"
        db_manager.init_db()
        init_application_tracking_schema()

        self.application_id = db_manager.create_empty_application_session()
        db_manager.update_application_report(
            application_id=self.application_id,
            resume_filename="resume.docx",
            report={
                "jd_profile": {
                    "job_title": "Software Engineer",
                    "company": "Example Co",
                },
                "meta": {"degree": "IMGD"},
                "overall_score": 82,
                "summary": "Example",
            },
        )

    def tearDown(self):
        db_manager.DB_PATH = self.old_path
        self.temp.cleanup()

    def test_default_row_is_not_applied(self):
        rows = list_application_tracking_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["application_id"], self.application_id)
        self.assertFalse(rows[0]["applied"])
        self.assertEqual(rows[0]["status"], "not_applied")
        self.assertFalse(rows[0]["completed"])

    def test_non_default_status_implies_applied_but_not_completed(self):
        saved = update_application_tracking(
            application_id=self.application_id,
            applied=False,
            status="interview",
            completed=False,
            notes="Phone screen passed",
        )
        self.assertTrue(saved["applied"])
        self.assertTrue(saved["applied_at"])
        self.assertEqual(saved["status"], "interview")
        self.assertFalse(saved["completed"])
        self.assertEqual(saved["notes"], "Phone screen passed")

    def test_completed_timestamp_is_user_controlled(self):
        first = update_application_tracking(
            application_id=self.application_id,
            applied=True,
            status="offer",
            completed=False,
        )
        self.assertFalse(first["completed"])
        self.assertEqual(first["completed_at"], "")

        second = update_application_tracking(
            application_id=self.application_id,
            applied=True,
            status="offer",
            completed=True,
        )
        self.assertTrue(second["completed"])
        self.assertTrue(second["completed_at"])

    def test_cleanup_removes_tracking_row(self):
        update_application_tracking(
            application_id=self.application_id,
            applied=True,
            status="applied",
            completed=False,
        )
        self.assertIsNotNone(get_application_tracking(self.application_id))
        self.assertEqual(delete_application_tracking(self.application_id), 1)
        self.assertIsNone(get_application_tracking(self.application_id))

    def test_invalid_status_is_rejected(self):
        with self.assertRaises(ValueError):
            update_application_tracking(
                application_id=self.application_id,
                applied=True,
                status="maybe",
                completed=False,
            )


if __name__ == "__main__":
    unittest.main()

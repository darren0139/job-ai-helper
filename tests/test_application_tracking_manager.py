from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

from database import application_tracking_manager as manager


class ApplicationTrackingManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_path = manager.DB_PATH
        manager.DB_PATH = Path(self.temp.name) / "applications.db"
        connection = sqlite3.connect(manager.DB_PATH)
        connection.execute(
            """
            CREATE TABLE applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company TEXT,
                job_title TEXT,
                overall_score INTEGER,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        connection.execute(
            """
            INSERT INTO applications (
                company, job_title, overall_score, created_at, updated_at
            ) VALUES ('Example Co', 'Software Engineer', 82,
                      '2026-09-01T10:00:00', '2026-09-01T10:00:00')
            """
        )
        connection.commit()
        connection.close()

    def tearDown(self):
        manager.DB_PATH = self.old_path
        self.temp.cleanup()

    def test_application_sessions_are_synced_into_tracker(self):
        rows = manager.list_application_tracking_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["company"], "Example Co")
        self.assertEqual(rows[0]["application_id"], 1)

    def test_manual_job_does_not_create_application_session(self):
        tracked_job_id = manager.add_manual_tracked_job(
            company="Manual Co",
            job_title="Data Engineer",
        )
        rows = manager.list_application_tracking_rows()
        manual = next(row for row in rows if row["tracked_job_id"] == tracked_job_id)
        self.assertIsNone(manual["application_id"])
        self.assertEqual(manual["source_type"], "manual")

    def test_applied_without_date_defaults_to_today(self):
        manager.update_application_tracking(
            application_id=1,
            applied=True,
            status="applied",
            completed=False,
        )
        row = manager.list_application_tracking_rows()[0]
        self.assertEqual(row["applied_at"], date.today().isoformat())
        self.assertEqual(row["status"], "applied")

    def test_historical_applied_date_is_preserved(self):
        manager.update_application_tracking(
            application_id=1,
            applied=True,
            applied_at="2026-08-14",
            status="Interview",
            completed=False,
        )
        row = manager.list_application_tracking_rows()[0]
        self.assertEqual(row["applied_at"], "2026-08-14")
        self.assertEqual(row["status"], "interview")

    def test_status_change_records_history(self):
        manager.update_application_tracking(
            application_id=1,
            applied=True,
            applied_at="2026-09-01",
            status="applied",
            completed=False,
        )
        manager.update_application_tracking(
            application_id=1,
            applied=True,
            applied_at="2026-09-01",
            status="interview",
            completed=False,
        )
        history = manager.list_application_status_history()
        self.assertEqual(
            [row["to_status"] for row in history],
            ["applied", "interview"],
        )

    def test_completed_without_date_defaults_to_today(self):
        manager.update_application_tracking(
            application_id=1,
            applied=True,
            applied_at="2026-09-01",
            status="rejected",
            completed=True,
        )
        row = manager.list_application_tracking_rows()[0]
        self.assertEqual(row["completed_at"], date.today().isoformat())
        self.assertEqual(row["completed"], 1)


    def test_applied_true_promotes_not_applied_status(self):
        manager.update_application_tracking(
            application_id=1,
            applied=True,
            status="not_applied",
            completed=False,
        )
        row = manager.list_application_tracking_rows()[0]
        self.assertEqual(row["applied"], 1)
        self.assertEqual(row["status"], "applied")
        self.assertEqual(row["applied_at"], date.today().isoformat())

    def test_advanced_status_still_implies_applied(self):
        manager.update_application_tracking(
            application_id=1,
            applied=False,
            applied_at="2026-09-03",
            status="Interview",
            completed=False,
        )
        row = manager.list_application_tracking_rows()[0]
        self.assertEqual(row["applied"], 1)
        self.assertEqual(row["status"], "interview")
        self.assertEqual(row["applied_at"], "2026-09-03")

    def test_schema_repairs_legacy_applied_not_applied_row(self):
        manager.list_application_tracking_rows()
        connection = sqlite3.connect(manager.DB_PATH)
        try:
            connection.execute(
                """
                UPDATE application_tracking
                SET applied = 1,
                    applied_at = '2026-08-20',
                    status = 'not_applied'
                """
            )
            connection.commit()
        finally:
            connection.close()

        manager.init_application_tracking_schema()
        row = manager.list_application_tracking_rows()[0]
        self.assertEqual(row["applied"], 1)
        self.assertEqual(row["applied_at"], "2026-08-20")
        self.assertEqual(row["status"], "applied")

    def test_delete_application_tracking_removes_linked_tracker_row(self):
        manager.list_application_tracking_rows()
        self.assertEqual(manager.delete_application_tracking(1), 1)
        connection = sqlite3.connect(manager.DB_PATH)
        try:
            count = connection.execute(
                "SELECT COUNT(*) FROM tracked_jobs WHERE application_id = 1"
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()

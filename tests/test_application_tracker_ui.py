from __future__ import annotations

import unittest
from datetime import date

import pandas as pd

from tailoring.application_tracker_ui import (
    _to_date,
    compute_tracker_metrics,
    tracker_has_unsaved_changes,
    tracker_rows_to_dataframe,
)


class ApplicationTrackerUiTests(unittest.TestCase):
    def test_to_date_accepts_iso_text(self):
        self.assertEqual(_to_date("2026-09-03"), date(2026, 9, 3))

    def test_metrics_count_pipeline_values(self):
        rows = [
            {
                "tracked_job_id": 1,
                "application_id": 1,
                "company": "A",
                "job_title": "Engineer",
                "location": "",
                "overall_score": 80,
                "applied": 1,
                "applied_at": "2026-09-01",
                "status": "interview",
                "completed": 0,
                "completed_at": None,
                "notes": "",
                "job_url": "",
                "source_type": "application_session",
            },
            {
                "tracked_job_id": 2,
                "application_id": None,
                "company": "B",
                "job_title": "Engineer",
                "location": "",
                "overall_score": None,
                "applied": 1,
                "applied_at": "2026-09-02",
                "status": "offer",
                "completed": 1,
                "completed_at": "2026-09-10",
                "notes": "",
                "job_url": "",
                "source_type": "manual",
            },
        ]
        metrics = compute_tracker_metrics(rows)
        self.assertEqual(metrics["tracked"], 2)
        self.assertEqual(metrics["applied"], 2)
        self.assertEqual(metrics["interviews"], 1)
        self.assertEqual(metrics["offers"], 1)
        self.assertEqual(metrics["completed"], 1)

    def test_change_detection_includes_applied_date(self):
        rows = [
            {
                "tracked_job_id": 1,
                "application_id": 1,
                "company": "A",
                "job_title": "Engineer",
                "location": "",
                "overall_score": 80,
                "applied": 1,
                "applied_at": "2026-09-01",
                "status": "applied",
                "completed": 0,
                "completed_at": None,
                "notes": "",
                "job_url": "",
                "source_type": "application_session",
            }
        ]
        original = tracker_rows_to_dataframe(rows)
        edited = original.copy()
        edited.loc[0, "applied_at"] = date(2026, 8, 20)
        self.assertTrue(tracker_has_unsaved_changes(original, edited))


if __name__ == "__main__":
    unittest.main()

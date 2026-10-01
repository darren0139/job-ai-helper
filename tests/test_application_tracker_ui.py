from __future__ import annotations

import unittest
from datetime import date

import pandas as pd

from tailoring.application_tracker_ui import (
    COHORT_CHART_TYPES,
    HISTORY_CHART_TYPES,
    STATUS_CHART_TYPES,
    WEEKLY_CHART_TYPES,
    _to_date,
    compute_tracker_metrics,
    normalise_tracker_editor_lifecycle,
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

    def _base_row(self):
        return {
            "tracked_job_id": 1,
            "application_id": 1,
            "company": "A",
            "job_title": "Engineer",
            "location": "",
            "overall_score": 80,
            "applied": 0,
            "applied_at": None,
            "status": "not_applied",
            "completed": 0,
            "completed_at": None,
            "notes": "",
            "job_url": "",
            "source_type": "application_session",
        }

    def test_applied_checkbox_promotes_not_applied_in_preview(self):
        original = tracker_rows_to_dataframe([self._base_row()])
        edited = original.copy()
        edited.loc[0, "applied"] = True

        normalized = normalise_tracker_editor_lifecycle(original, edited)

        self.assertTrue(bool(normalized.loc[0, "applied"]))
        self.assertEqual(normalized.loc[0, "status"], "Applied")
        self.assertEqual(normalized.loc[0, "applied_at"], date.today())

    def test_status_change_to_interview_implies_applied(self):
        original = tracker_rows_to_dataframe([self._base_row()])
        edited = original.copy()
        edited.loc[0, "status"] = "Interview"

        normalized = normalise_tracker_editor_lifecycle(original, edited)

        self.assertTrue(bool(normalized.loc[0, "applied"]))
        self.assertEqual(normalized.loc[0, "status"], "Interview")
        self.assertEqual(normalized.loc[0, "applied_at"], date.today())

    def test_unchecking_applied_resets_unchanged_advanced_status(self):
        row = self._base_row()
        row.update(
            applied=1,
            applied_at="2026-09-01",
            status="interview",
        )
        original = tracker_rows_to_dataframe([row])
        edited = original.copy()
        edited.loc[0, "applied"] = False

        normalized = normalise_tracker_editor_lifecycle(original, edited)

        self.assertFalse(bool(normalized.loc[0, "applied"]))
        self.assertEqual(normalized.loc[0, "status"], "Not Applied")
        self.assertIsNone(normalized.loc[0, "applied_at"])

    def test_chart_type_choices_are_explicit_and_bounded(self):
        self.assertEqual(STATUS_CHART_TYPES, ("Bar", "Donut"))
        self.assertEqual(WEEKLY_CHART_TYPES, ("Line", "Bar"))
        self.assertEqual(COHORT_CHART_TYPES, ("Stacked Bar", "Grouped Bar"))
        self.assertEqual(HISTORY_CHART_TYPES, ("Line", "Stacked Bar"))



if __name__ == "__main__":
    unittest.main()

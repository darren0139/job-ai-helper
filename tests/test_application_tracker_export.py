from __future__ import annotations

import unittest
from io import BytesIO

from openpyxl import load_workbook

from tailoring.application_tracker_export import build_application_tracker_workbook


class ApplicationTrackerExportTests(unittest.TestCase):
    def test_workbook_contains_expected_sheets_and_values(self):
        workbook_bytes = build_application_tracker_workbook(
            [
                {
                    "application_id": 7,
                    "company": "Example Co",
                    "job_title": "Software Engineer",
                    "location": "Singapore",
                    "overall_score": 82,
                    "applied": True,
                    "applied_at": "2026-09-15T10:00:00",
                    "status": "interview",
                    "completed": False,
                    "completed_at": "",
                    "notes": "Technical interview next week",
                }
            ]
        )
        workbook = load_workbook(BytesIO(workbook_bytes), data_only=True)

        self.assertEqual(
            workbook.sheetnames,
            ["Applications", "Summary", "Weekly Trend"],
        )
        applications = workbook["Applications"]
        self.assertEqual(applications["A2"].value, 7)
        self.assertEqual(applications["B2"].value, "Example Co")
        self.assertEqual(applications["H2"].value, "Interview")

        summary = workbook["Summary"]
        summary_values = {
            summary.cell(row=row, column=1).value: summary.cell(row=row, column=2).value
            for row in range(2, summary.max_row + 1)
        }
        self.assertEqual(summary_values["Tracked Jobs"], 1)
        self.assertEqual(summary_values["Applied"], 1)
        self.assertEqual(summary_values["Interview"], 1)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from tailoring.application_tracker_ui import (
    build_tracker_dataframe,
    build_tracker_metrics,
)


class ApplicationTrackerUiTests(unittest.TestCase):
    def test_metrics_are_built_from_editor_frame(self):
        frame = build_tracker_dataframe(
            [
                {
                    "application_id": 1,
                    "company": "A",
                    "job_title": "Engineer",
                    "applied": True,
                    "status": "interview",
                    "completed": False,
                },
                {
                    "application_id": 2,
                    "company": "B",
                    "job_title": "Developer",
                    "applied": True,
                    "status": "rejected",
                    "completed": True,
                },
                {
                    "application_id": 3,
                    "company": "C",
                    "job_title": "Analyst",
                    "applied": False,
                    "status": "not_applied",
                    "completed": False,
                },
            ]
        )
        metrics = build_tracker_metrics(frame)
        self.assertEqual(metrics["tracked"], 3)
        self.assertEqual(metrics["applied"], 2)
        self.assertEqual(metrics["active"], 1)
        self.assertEqual(metrics["interviews"], 1)
        self.assertEqual(metrics["completed"], 1)


if __name__ == "__main__":
    unittest.main()

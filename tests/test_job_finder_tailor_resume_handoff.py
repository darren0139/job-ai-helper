from __future__ import annotations

import unittest
from pathlib import Path

from job_discovery.tailor_resume_handoff import (
    apply_job_finder_tailor_resume_handoff,
)


ROOT = Path(__file__).resolve().parents[1]


class JobFinderTailorResumeHandoffTests(unittest.TestCase):
    def test_handoff_prefills_existing_manual_tailor_resume_workflow(self):
        state = {
            "phase9f_jd_analysis": {"old": True},
            "phase9f_jd_analysis_input_fingerprint": "old",
            "phase9f_jd_save_receipt": {"old": True},
            "phase9f_b_ranking_result": {"old": True},
            "phase9f_d_confirmation_receipt": {"old": True},
            "phase9f_jd_preferred_requirements": "stale override",
        }
        job = {
            "id": 4103,
            "title": "AI Software Engineer",
            "company": "NCS",
            "location": "Singapore",
            "description": "Exact normalized Job Finder JD text.",
            "source_url": "https://example.test/job/4103",
        }

        apply_job_finder_tailor_resume_handoff(
            state,
            application_id=73,
            job=job,
        )

        self.assertEqual(state["current_application_id"], 73)
        self.assertEqual(state["phase9f_jd_source_mode"], "Paste job description")
        self.assertEqual(
            state["phase9f_pasted_jd_text"],
            "Exact normalized Job Finder JD text.",
        )
        self.assertEqual(state["phase9f_jd_company"], "NCS")
        self.assertEqual(state["phase9f_jd_title"], "AI Software Engineer")
        self.assertEqual(state["phase9f_jd_location"], "Singapore")
        self.assertEqual(
            state["phase9f_jd_source_url"],
            "https://example.test/job/4103",
        )
        self.assertEqual(state["_pending_navigation_page"], "Tailor Resume")
        for key in (
            "phase9f_jd_analysis",
            "phase9f_jd_analysis_input_fingerprint",
            "phase9f_jd_save_receipt",
            "phase9f_b_ranking_result",
            "phase9f_d_confirmation_receipt",
            "phase9f_jd_preferred_requirements",
        ):
            self.assertNotIn(key, state)

    def test_ui_keeps_discovery_match_separate_and_routes_to_tailor_resume(self):
        source = (ROOT / "job_discovery" / "ui.py").read_text(encoding="utf-8")
        self.assertIn('"Tailor this job"', source)
        self.assertIn("apply_job_finder_tailor_resume_handoff", source)
        self.assertIn("Profile & Evidence score is preserved as Discovery Match", source)
        self.assertIn("current Phase 9F workflow", source)


if __name__ == "__main__":
    unittest.main()

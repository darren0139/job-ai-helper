from __future__ import annotations

import unittest

from browser_integration.tailor_resume_handoff import (
    BROWSER_CAPTURE_SOURCE_LABEL,
    apply_browser_capture_tailor_resume_handoff,
    browser_capture_to_phase9f_input,
)


class BrowserTailorResumeHandoffTests(unittest.TestCase):
    def test_capture_maps_to_phase9f_input_without_rewriting_text(self) -> None:
        capture = {
            "id": 7,
            "capture_hash": "abc123",
            "job_title": "DevOps Engineer",
            "company": "Example Agency",
            "location": "Singapore",
            "source_url": "https://example.test/job/7",
            "jd_text": "Exact clean JD text.",
        }

        result = browser_capture_to_phase9f_input(capture)

        self.assertEqual(result["raw_text"], "Exact clean JD text.")
        self.assertEqual(result["title"], "DevOps Engineer")
        self.assertEqual(result["company"], "Example Agency")
        self.assertEqual(result["location"], "Singapore")
        self.assertEqual(result["source_url"], "https://example.test/job/7")
        self.assertEqual(result["source_artifact_sha256"], "abc123")

    def test_handoff_selects_browser_source_and_tailor_resume(self) -> None:
        state = {
            "phase9f_jd_analysis": {"old": True},
            "phase9f_jd_analysis_input_fingerprint": "old",
            "phase9f_jd_save_receipt": {"old": True},
        }

        apply_browser_capture_tailor_resume_handoff(state, 12)

        self.assertEqual(
            state["phase9f_jd_source_mode"],
            BROWSER_CAPTURE_SOURCE_LABEL,
        )
        self.assertEqual(state["phase9f_browser_capture_id"], 12)
        self.assertEqual(state["navigation_page"], "Tailor Resume")
        self.assertNotIn("phase9f_jd_analysis", state)
        self.assertNotIn(
            "phase9f_jd_analysis_input_fingerprint",
            state,
        )
        self.assertNotIn("phase9f_jd_save_receipt", state)


if __name__ == "__main__":
    unittest.main()

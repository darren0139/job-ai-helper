from __future__ import annotations

from copy import deepcopy
import unittest
from unittest.mock import patch

from analysis_stability.stable_evidence_scoring import SCORING_VERSION
from tailoring.capability_taxonomy import get_default_taxonomy
from tailoring.jd_user_input_overrides import (
    APPLICATION_SESSION_STABLE_CURRENTNESS_VERSION,
    apply_application_session_jd_user_inputs,
    refresh_application_session_analysis_report,
)


class ApplicationSessionAnalysisCurrentnessTests(unittest.TestCase):
    def _report(self, stable_analysis: dict) -> dict:
        original_jd_profile = {
            "job_title": "Backend Engineer",
            "company": "Example",
            "location": "",
            "required_skills": ["Python"],
            "preferred_skills": [],
            "responsibilities": [],
            "soft_skills": [],
            "tools_technologies": [],
            "deal_breakers": [],
        }
        return {
            "meta": {
                "jd_user_inputs": {
                    "policy_version": "application-session-jd-user-overrides-v2",
                    "company": "",
                    "job_title": "",
                    "location": "",
                    "source_url": "",
                    "preferred_requirement_overrides": [],
                    "original_extracted_metadata": {
                        "company": "Example",
                        "job_title": "Backend Engineer",
                        "location": "",
                    },
                    "original_extracted_jd_profile": deepcopy(
                        original_jd_profile
                    ),
                }
            },
            "resume_profile": {
                "name": "Candidate",
                "summary": "",
                "education": [],
                "experience": [],
                "projects": [
                    {
                        "title": "Python Service",
                        "date": "2026",
                        "bullets": ["Built a Python backend service."],
                    }
                ],
                "skills": {"languages": ["Python"]},
            },
            "jd_profile": deepcopy(original_jd_profile),
            "keyword_match": {"present": [], "missing": []},
            "bullets": {"bullet_quality_avg": 80},
            "structure": {"structure_score": 100},
            "raw_jd_text": "Requirements\nPython",
            "stable_analysis": deepcopy(stable_analysis),
        }

    def _current_stable(self) -> dict:
        return {
            "scoring_version": SCORING_VERSION,
            "capability_taxonomy_version": get_default_taxonomy().version,
            "input_fingerprint": "current-fingerprint",
            "canonical_requirements": [],
            "deterministic_alignment_score": 25,
            "requirement_count": 1,
            "credited_requirement_count": 1,
        }

    def test_apply_rebuilds_stale_stable_analysis_without_user_overrides(self):
        report = self._report(
            {
                "scoring_version": "stable-evidence-old",
                "capability_taxonomy_version": "taxonomy-old",
                "deterministic_alignment_score": 12,
            }
        )
        rebuilt = self._current_stable()

        with patch(
            "tailoring.jd_user_input_overrides._rebuild_stable_analysis",
            return_value=deepcopy(rebuilt),
        ) as rebuild:
            output = apply_application_session_jd_user_inputs(
                report,
                raw_jd_text=report["raw_jd_text"],
                raw_resume_text="languages: Python",
            )

        rebuild.assert_called_once()
        self.assertEqual(output["stable_analysis"], rebuilt)
        self.assertEqual(
            report["stable_analysis"]["scoring_version"],
            "stable-evidence-old",
        )

    def test_apply_reuses_current_stable_analysis_without_rebuild(self):
        current = self._current_stable()
        report = self._report(current)

        with patch(
            "tailoring.jd_user_input_overrides._rebuild_stable_analysis",
            side_effect=AssertionError("current stable analysis was rebuilt"),
        ):
            output = apply_application_session_jd_user_inputs(
                report,
                raw_jd_text=report["raw_jd_text"],
                raw_resume_text="languages: Python",
            )

        self.assertEqual(output["stable_analysis"], current)

    def test_taxonomy_version_change_alone_forces_rebuild(self):
        stale_taxonomy = self._current_stable()
        stale_taxonomy["capability_taxonomy_version"] = "taxonomy-old"
        report = self._report(stale_taxonomy)
        rebuilt = self._current_stable()

        with patch(
            "tailoring.jd_user_input_overrides._rebuild_stable_analysis",
            return_value=deepcopy(rebuilt),
        ) as rebuild:
            output = apply_application_session_jd_user_inputs(
                report,
                raw_jd_text=report["raw_jd_text"],
                raw_resume_text="languages: Python",
            )

        rebuild.assert_called_once()
        self.assertEqual(output["stable_analysis"], rebuilt)

    def test_refresh_returns_current_facing_copy_and_preserves_history(self):
        report = self._report(
            {
                "scoring_version": "stable-evidence-v1.3-phase6d7",
                "capability_taxonomy_version": (
                    "phase6d-capability-taxonomy-v1.2"
                ),
                "deterministic_alignment_score": 12,
                "requirement_count": 16,
                "credited_requirement_count": 1,
            }
        )
        historical = deepcopy(report)
        rebuilt = self._current_stable()

        with patch(
            "tailoring.jd_user_input_overrides._rebuild_stable_analysis",
            return_value=deepcopy(rebuilt),
        ) as rebuild:
            current = refresh_application_session_analysis_report(report)

        rebuild.assert_called_once()
        self.assertEqual(report, historical)
        self.assertEqual(current["stable_analysis"], rebuilt)

        metadata = current["meta"]["stable_analysis_currentness"]
        self.assertEqual(
            metadata["resolution_version"],
            APPLICATION_SESSION_STABLE_CURRENTNESS_VERSION,
        )
        self.assertEqual(metadata["mode"], "rebuilt_with_current_scorer")
        self.assertTrue(metadata["rebuilt"])
        self.assertEqual(
            metadata["stored_scoring_version"],
            "stable-evidence-v1.3-phase6d7",
        )
        self.assertEqual(
            metadata["current_scoring_version"],
            SCORING_VERSION,
        )
        self.assertEqual(
            metadata["resume_text_source"],
            "reconstructed_from_resume_profile",
        )
        self.assertTrue(metadata["raw_jd_available"])

        call_kwargs = rebuild.call_args.kwargs
        self.assertIn(
            "Built a Python backend service.",
            call_kwargs["raw_resume_text"],
        )
        self.assertIn("languages: Python", call_kwargs["raw_resume_text"])

    def test_refresh_reuses_current_analysis_but_still_returns_copy(self):
        current_stable = self._current_stable()
        report = self._report(current_stable)

        with patch(
            "tailoring.jd_user_input_overrides._rebuild_stable_analysis",
            side_effect=AssertionError("current stable analysis was rebuilt"),
        ):
            current = refresh_application_session_analysis_report(report)

        self.assertIsNot(current, report)
        self.assertEqual(current["stable_analysis"], current_stable)
        metadata = current["meta"]["stable_analysis_currentness"]
        self.assertEqual(metadata["mode"], "reused_current_stable_analysis")
        self.assertFalse(metadata["rebuilt"])


if __name__ == "__main__":
    unittest.main()

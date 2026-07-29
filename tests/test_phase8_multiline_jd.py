from __future__ import annotations

import unittest
from unittest.mock import patch

from tailoring.phase8_verification import (
    _normalise_multiline_text,
    _verification_fingerprint,
    build_phase8_verification,
)


BASE_ROW = {
    "requirement_id": "req_python",
    "text": "Minimum 1 year of Python experience",
    "importance": "required",
    "match_label": "direct",
    "evidence_strength": 5,
}


def stable(score: int = 50) -> dict:
    return {
        "deterministic_alignment_score": score,
        "alignment_band": "partial alignment",
        "required_core_coverage_score": score,
        "preferred_coverage_score": 0,
        "evidence_strength_score": 60,
        "canonical_requirements": [BASE_ROW],
        "input_fingerprint": "baseline",
    }


def baseline_report() -> dict:
    return {
        "stable_analysis": stable(),
        "resume_profile": {
            "projects": [],
            "skills": {},
            "experience": [],
            "education": [],
        },
        "jd_profile": {},
        "keyword_match": {"present": [], "missing": []},
        "bullets": {"bullet_quality_avg": 80},
        "structure": {"structure_score": 100},
    }


GENERATION = {
    "application_id": 1,
    "generation_id": "generation-a",
    "status": "approved",
    "updated_at": "2026-07-29T21:45:00",
    "projects": {"recommended_projects": []},
    "skills": {"skill_lines": []},
    "fit_result": {
        "fit_one_page": True,
        "page_count": 1,
    },
}


MULTILINE_JD_CRLF = (
    "\r\nJob Description\r\n\r\n"
    "Build and maintain Python services.\r\n"
    "Coordinate release work.\r\n\r\n"
    "Job Requirements\r\n\r\n"
    "Minimum 1 year of Python experience.\r\n"
    "PostgreSQL familiarity would be preferred.\r\n\r\n"
)

MULTILINE_JD_LF = (
    "Job Description\n\n"
    "Build and maintain Python services.\n"
    "Coordinate release work.\n\n"
    "Job Requirements\n\n"
    "Minimum 1 year of Python experience.\n"
    "PostgreSQL familiarity would be preferred."
)


class Phase8MultilineJDTests(unittest.TestCase):
    def test_normalisation_preserves_structure_and_line_endings(self):
        result = _normalise_multiline_text(MULTILINE_JD_CRLF)
        self.assertEqual(result, MULTILINE_JD_LF)
        self.assertIn("Job Description\n\n", result)
        self.assertIn("\n\nJob Requirements\n\n", result)

    @patch("tailoring.phase8_verification.build_stable_analysis")
    def test_stable_scorer_receives_multiline_jd(
        self,
        mocked_build,
    ):
        mocked_build.return_value = stable(55)

        result = build_phase8_verification(
            baseline_report=baseline_report(),
            generation_state=GENERATION,
            raw_jd_text=MULTILINE_JD_CRLF,
        )

        self.assertEqual(
            mocked_build.call_args.kwargs["raw_jd_text"],
            MULTILINE_JD_LF,
        )
        self.assertEqual(
            result["phase8_version"],
            "phase8-before-after-verification-v5",
        )

    def test_fingerprint_is_stable_across_line_endings(self):
        left = _verification_fingerprint(
            baseline_report(),
            GENERATION,
            MULTILINE_JD_CRLF,
        )
        right = _verification_fingerprint(
            baseline_report(),
            GENERATION,
            MULTILINE_JD_LF,
        )
        self.assertEqual(left, right)

    def test_collapsed_jd_has_different_fingerprint(self):
        multiline = _verification_fingerprint(
            baseline_report(),
            GENERATION,
            MULTILINE_JD_LF,
        )
        collapsed = _verification_fingerprint(
            baseline_report(),
            GENERATION,
            " ".join(MULTILINE_JD_LF.split()),
        )
        self.assertNotEqual(multiline, collapsed)


if __name__ == "__main__":
    unittest.main()

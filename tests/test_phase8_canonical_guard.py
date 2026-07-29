from __future__ import annotations

import unittest
from unittest.mock import patch

from tailoring.phase8_verification import (
    build_phase8_verification,
    compare_stable_analyses,
)


def stable(score: int, rows: list[dict]):
    return {
        "deterministic_alignment_score": score,
        "alignment_band": "partial alignment",
        "required_core_coverage_score": score,
        "preferred_coverage_score": 0,
        "evidence_strength_score": 60,
        "canonical_requirements": rows,
        "input_fingerprint": "baseline",
    }


BASE_ROW = {
    "requirement_id": "req_a",
    "text": "Python",
    "importance": "required",
    "match_label": "direct",
    "evidence_strength": 5,
}


GENERATION = {
    "application_id": 1,
    "generation_id": "gen-a",
    "status": "approved",
    "updated_at": "2026-07-29T10:00:00",
    "candidate_pool": [
        {
            "project_id": "project-a",
            "title": "Project A",
            "display_title": "Project A (Python)",
            "evidence_records": [
                {"kind": "bullet", "text": "Built a Python API."},
                {"kind": "tool", "text": "Python"},
            ],
        }
    ],
    "projects": {
        "recommended_projects": [
            {
                "project_id": "project-a",
                "title": "Project A",
                "display_title": "Project A (Python)",
                "draft_bullets": ["Built a Python API."],
                "requirement_matches": [
                    {
                        "requirement_id": "req_a",
                        "requirement_text": "Python",
                        "importance": "required",
                        "match_label": "direct",
                        "evidence_snippets": ["Built a Python API."],
                    }
                ],
            }
        ]
    },
    "skills": {
        "skill_lines": [
            {
                "category": "Programming",
                "items": ["Python"],
            }
        ]
    },
    "fit_result": {
        "fit_one_page": True,
        "page_count": 1,
    },
}


def baseline_report():
    return {
        "stable_analysis": stable(55, [BASE_ROW]),
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


class Phase8CanonicalRequirementGuardTests(unittest.TestCase):
    def test_missing_original_jd_text_stops_verification(self):
        with self.assertRaisesRegex(
            ValueError,
            "original job-description text",
        ):
            build_phase8_verification(
                baseline_report=baseline_report(),
                generation_state=GENERATION,
                raw_jd_text="",
            )

    @patch("tailoring.phase8_verification.build_stable_analysis")
    def test_original_jd_text_is_passed_to_stable_scorer(
        self,
        mocked_build,
    ):
        mocked_build.return_value = stable(60, [BASE_ROW])
        raw_jd_text = "Python is required for this role."
        build_phase8_verification(
            baseline_report=baseline_report(),
            generation_state=GENERATION,
            raw_jd_text=raw_jd_text,
        )
        self.assertEqual(
            mocked_build.call_args.kwargs["raw_jd_text"],
            raw_jd_text,
        )

    @patch("tailoring.phase8_verification.build_stable_analysis")
    def test_stable_requirement_ids_allow_valid_comparison(
        self,
        mocked_build,
    ):
        mocked_build.return_value = stable(60, [BASE_ROW])
        result = build_phase8_verification(
            baseline_report=baseline_report(),
            generation_state=GENERATION,
            raw_jd_text="Python is required.",
        )
        self.assertTrue(result["comparison_valid"])
        self.assertEqual(result["verdict"], "improved")
        self.assertTrue(result["blueprint_ready"])
        self.assertEqual(
            result["phase8_version"],
            "phase8-before-after-verification-v5",
        )

    @patch("tailoring.phase8_verification.build_stable_analysis")
    def test_requirement_id_mismatch_fails_closed(
        self,
        mocked_build,
    ):
        changed_row = {
            **BASE_ROW,
            "requirement_id": "req_changed",
        }
        mocked_build.return_value = stable(60, [changed_row])
        result = build_phase8_verification(
            baseline_report=baseline_report(),
            generation_state=GENERATION,
            raw_jd_text="Python is required.",
        )
        self.assertFalse(result["comparison_valid"])
        self.assertEqual(
            result["verdict"],
            "invalid_canonical_mismatch",
        )
        self.assertFalse(result["blueprint_ready"])
        self.assertEqual(
            result["canonical_requirement_guard"]["action"],
            "invalidate_score_delta",
        )
        self.assertEqual(
            len(result["comparison"]["added_requirements"]),
            1,
        )
        self.assertEqual(
            len(result["comparison"]["removed_requirements"]),
            1,
        )

    def test_compare_function_still_reports_id_instability(self):
        result = compare_stable_analyses(
            stable(50, [BASE_ROW]),
            stable(
                50,
                [{**BASE_ROW, "requirement_id": "req_b"}],
            ),
        )
        self.assertFalse(
            result["canonical_requirement_ids_stable"]
        )


if __name__ == "__main__":
    unittest.main()

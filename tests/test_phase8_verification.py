from __future__ import annotations

import unittest
from unittest.mock import patch
from analysis_stability.stable_evidence_scoring import SCORING_VERSION

from tailoring.phase8_verification import (
    audit_claim_lineage,
    build_final_resume_profile,
    build_phase8_verification,
    compare_stable_analyses,
    refresh_phase8_readiness,
)


def stable(score: int, rows: list[dict]):
    return {
        "scoring_version": SCORING_VERSION,
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
                {
                    "kind": "bullet",
                    "text": "Built a Python API.",
                },
                {
                    "kind": "tool",
                    "text": "Python",
                },
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


class Phase8VerificationTests(unittest.TestCase):
    def test_final_profile_uses_final_projects_and_skills(self):
        profile = build_final_resume_profile(
            {
                "projects": [{"title": "Old"}],
                "skills": {"languages": ["C++"]},
                "experience": [],
                "education": [],
            },
            GENERATION,
        )
        self.assertEqual(
            profile["projects"][0]["title"],
            "Project A (Python)",
        )
        self.assertEqual(
            profile["skills"]["Programming"],
            ["Python"],
        )

    def test_comparison_detects_improvement(self):
        before = stable(
            40,
            [{**BASE_ROW, "match_label": "none", "evidence_strength": 0}],
        )
        after = stable(55, [BASE_ROW])
        result = compare_stable_analyses(before, after)
        self.assertEqual(result["score_delta"], 15)
        self.assertEqual(len(result["improved_requirements"]), 1)
        self.assertFalse(result["important_regressions"])

    def test_comparison_detects_required_regression(self):
        before = stable(55, [BASE_ROW])
        after = stable(
            40,
            [{**BASE_ROW, "match_label": "none", "evidence_strength": 0}],
        )
        result = compare_stable_analyses(before, after)
        self.assertEqual(len(result["important_regressions"]), 1)

    def test_claim_lineage_accepts_supported_bullet_and_skill(self):
        result = audit_claim_lineage(
            {"projects": [], "skills": {}},
            GENERATION,
        )
        self.assertEqual(result["claim_review_required_count"], 0)

    def test_claim_lineage_flags_unrelated_bullet(self):
        generation = {
            **GENERATION,
            "projects": {
                "recommended_projects": [
                    {
                        "project_id": "project-a",
                        "title": "Project A",
                        "draft_bullets": [
                            "Managed global production outages for five years."
                        ],
                    }
                ]
            },
        }
        result = audit_claim_lineage(
            {"projects": [], "skills": {}},
            generation,
        )
        self.assertEqual(
            len(result["project_bullet_review_risks"]),
            1,
        )

    @patch("tailoring.phase8_verification.build_stable_analysis")
    def test_complete_verification_can_be_blueprint_ready(
        self,
        mocked_build,
    ):
        mocked_build.return_value = stable(60, [BASE_ROW])
        baseline = {
            "stable_analysis": stable(55, [BASE_ROW]),
            "resume_profile": {
                "projects": [],
                "skills": {},
                "experience": [],
                "education": [],
            },
            "jd_profile": {},
            "keyword_match": {"present": [], "missing": []},
            "raw_jd_text": "Python required",
            "bullets": {"bullet_quality_avg": 80},
            "structure": {"structure_score": 100},
        }
        result = build_phase8_verification(
            baseline_report=baseline,
            generation_state=GENERATION,
            raw_jd_text="Python is required for this role.",
        )
        self.assertEqual(result["verdict"], "improved")
        self.assertTrue(result["blueprint_ready"])
        self.assertEqual(
            result["verification_mode"],
            "zero_cost_deterministic",
        )



    @patch("tailoring.phase8_verification.build_stable_analysis")
    def test_stale_stored_baseline_is_rebuilt_with_current_scorer(
        self,
        mocked_build,
    ):
        stored_heading = {
            **BASE_ROW,
            "requirement_id": "req_heading",
            "text": "Key Responsibilities",
            "match_label": "none",
            "evidence_strength": 0,
        }
        stored_baseline = stable(
            36,
            [stored_heading, BASE_ROW],
        )
        stored_baseline["scoring_version"] = (
            "stable-evidence-v1.3-phase6d6"
        )

        rebuilt_before = stable(50, [BASE_ROW])
        rebuilt_after = stable(60, [BASE_ROW])
        mocked_build.side_effect = [
            rebuilt_before,
            rebuilt_after,
        ]

        baseline = {
            "stable_analysis": stored_baseline,
            "resume_profile": {
                "projects": [],
                "skills": {},
                "experience": [],
                "education": [],
            },
            "jd_profile": {},
            "keyword_match": {
                "present": [],
                "missing": [],
            },
            "raw_jd_text": "Python required",
            "bullets": {"bullet_quality_avg": 80},
            "structure": {"structure_score": 100},
        }

        result = build_phase8_verification(
            baseline_report=baseline,
            generation_state=GENERATION,
            raw_jd_text="Python is required for this role.",
        )

        self.assertEqual(mocked_build.call_count, 2)
        self.assertTrue(result["comparison_valid"])
        self.assertEqual(result["comparison"]["before_score"], 50)
        self.assertEqual(
            result["raw_comparison_before_reconciliation"][
                "after_score"
            ],
            60,
        )
        self.assertEqual(
            result["comparison"]["after_score"],
            result["after_stable_analysis"][
                "deterministic_alignment_score"
            ],
        )
        self.assertGreaterEqual(
            result["comparison"]["after_score"],
            60,
        )
        self.assertFalse(result["comparison"]["removed_requirements"])
        self.assertFalse(result["comparison"]["added_requirements"])
        self.assertTrue(result["baseline_resolution"]["rebuilt"])
        self.assertEqual(
            result["baseline_resolution"]["stored_scoring_version"],
            "stable-evidence-v1.3-phase6d6",
        )
        self.assertEqual(
            result["baseline_resolution"]["resolved_scoring_version"],
            SCORING_VERSION,
        )
        self.assertEqual(
            result["before_stable_analysis"]["scoring_version"],
            SCORING_VERSION,
        )
        self.assertEqual(
            mocked_build.call_args_list[0].kwargs["keyword_match"],
            baseline["keyword_match"],
        )

    def test_cached_draft_readiness_refreshes_after_approval(self):
        cached = {
            "generation_status": "draft",
            "fit_one_page": True,
            "page_count": 1,
            "comparison_valid": True,
            "comparison": {
                "score_delta": 5,
                "important_regressions": [],
                "canonical_requirement_ids_stable": True,
            },
            "claim_lineage": {
                "claim_review_required_count": 0,
            },
            "blueprint_ready": False,
            "blueprint_readiness_reasons": {
                "is_approved": False,
                "fits_one_page": True,
                "canonical_requirement_ids_stable": True,
                "no_required_core_regression": True,
                "no_claim_review_risks": True,
                "score_not_lower": True,
            },
        }
        approved_generation = {
            **GENERATION,
            "status": "approved",
        }

        refreshed = refresh_phase8_readiness(
            cached,
            approved_generation,
        )

        self.assertEqual(cached["generation_status"], "draft")
        self.assertFalse(cached["blueprint_ready"])
        self.assertEqual(
            refreshed["generation_status"],
            "approved",
        )
        self.assertTrue(
            refreshed["blueprint_readiness_reasons"][
                "is_approved"
            ]
        )
        self.assertTrue(refreshed["blueprint_ready"])


if __name__ == "__main__":
    unittest.main()

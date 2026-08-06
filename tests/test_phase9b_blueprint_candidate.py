from __future__ import annotations

import unittest

from tailoring.phase9b_blueprint_candidate import (
    PHASE9B_VERSION,
    blueprint_candidate_eligibility,
    build_blueprint_candidate,
)


GENERATION = {
    "application_id": 1,
    "generation_id": "generation-approved",
    "status": "approved",
    "projects": {
        "recommended_projects": [
            {"title": "Generated project"}
        ]
    },
    "skills": {
        "skill_lines": [
            {"category": "Programming", "items": ["Python"]}
        ]
    },
    "fit_result": {
        "fit_one_page": True,
        "page_count": 1,
        "tailored_projects_used": {
            "recommended_projects": [
                {"title": "Final fitted project"}
            ]
        },
        "tailored_skills_used": {
            "skill_lines": [
                {
                    "category": "Programming",
                    "items": ["Python", "TypeScript"],
                }
            ]
        },
    },
}


VERIFICATION = {
    "verification_id": "verification-a",
    "verification_fingerprint": "verification-fingerprint",
    "generation_id": "generation-approved",
    "comparison_valid": True,
    "blueprint_ready": True,
    "blueprint_readiness_reasons": {
        "is_approved": True,
        "fits_one_page": True,
        "canonical_requirement_ids_stable": True,
        "no_required_core_regression": True,
        "no_claim_review_risks": True,
        "score_not_lower": True,
    },
    "claim_lineage": {
        "lineage_version": "phase8-claim-lineage-v2",
        "claim_review_required_count": 0,
    },
    "after_stable_analysis": {
        "deterministic_alignment_score": 65,
        "canonical_requirements": [
            {"requirement_id": "req_python"}
        ],
    },
}


BASELINE = {
    "stable_analysis": {
        "deterministic_alignment_score": 40,
    }
}


class Phase9BBlueprintCandidateTests(unittest.TestCase):
    def test_eligibility_passes_for_verified_approved_generation(self):
        result = blueprint_candidate_eligibility(
            generation_state=GENERATION,
            verification=VERIFICATION,
        )
        self.assertTrue(result["eligible"])
        self.assertTrue(all(result["reasons"].values()))

    def test_unapproved_generation_is_blocked(self):
        result = blueprint_candidate_eligibility(
            generation_state={
                **GENERATION,
                "status": "draft",
            },
            verification=VERIFICATION,
        )
        self.assertFalse(result["eligible"])
        self.assertFalse(
            result["reasons"]["approved_generation"]
        )

    def test_unchanged_application_result_fork_cannot_satisfy_phase9b(self):
        result = blueprint_candidate_eligibility(
            generation_state={
                **GENERATION,
                "source_application_result_id": "immutable-result-a",
                "content_changed": False,
                "phase9e_scope_matches": True,
            },
            verification=VERIFICATION,
        )
        self.assertFalse(result["eligible"])
        self.assertFalse(result["reasons"]["content_materially_changed"])

    def test_changed_fork_requires_the_current_phase9e_scope(self):
        historical = blueprint_candidate_eligibility(
            generation_state={
                **GENERATION,
                "source_application_result_id": "immutable-result-a",
                "content_changed": True,
                "phase9e_scope_matches": False,
            },
            verification=VERIFICATION,
        )
        current = blueprint_candidate_eligibility(
            generation_state={
                **GENERATION,
                "source_application_result_id": "immutable-result-a",
                "content_changed": True,
                "phase9e_scope_matches": True,
            },
            verification=VERIFICATION,
        )
        self.assertFalse(historical["eligible"])
        self.assertFalse(
            historical["reasons"]["matches_current_phase9e_scope"]
        )
        self.assertTrue(current["eligible"])

    def test_build_uses_final_fitted_projects_and_skills(self):
        candidate = build_blueprint_candidate(
            application_id=1,
            generation_state=GENERATION,
            verification=VERIFICATION,
            baseline_report=BASELINE,
            role_family="AI & Full-Stack Engineering",
            candidate_name="AI General Blueprint Candidate",
            evidence_opportunity={
                "opportunity_id": "opportunity-a",
                "opportunity_fingerprint": "opportunity-fingerprint",
                "potential_score": 72,
            },
        )
        self.assertEqual(
            candidate["projects"]["recommended_projects"][0][
                "title"
            ],
            "Final fitted project",
        )
        self.assertEqual(
            candidate["skills"]["skill_lines"][0]["items"],
            ["Python", "TypeScript"],
        )
        self.assertEqual(
            candidate["score_summary"]["original_resume_score"],
            40,
        )
        self.assertEqual(
            candidate["score_summary"]["approved_tailored_score"],
            65,
        )
        self.assertEqual(
            candidate["score_summary"]["evidence_potential_score"],
            72,
        )
        self.assertTrue(candidate["global_scope"])


    def test_candidate_prefers_phase8_resolved_baseline(
        self,
    ):
        verification = {
            **VERIFICATION,
            "before_stable_analysis": {
                "deterministic_alignment_score": 32,
                "input_fingerprint": (
                    "resolved-before-fingerprint"
                ),
            },
        }
        baseline = {
            **BASELINE,
            "stable_analysis": {
                **BASELINE["stable_analysis"],
                "deterministic_alignment_score": 36,
                "input_fingerprint": (
                    "stored-phase6d6-fingerprint"
                ),
            },
        }

        candidate = build_blueprint_candidate(
            application_id=1,
            generation_state=GENERATION,
            verification=verification,
            baseline_report=baseline,
            role_family="AI & Full-Stack Engineering",
            candidate_name="AI General Blueprint Candidate",
        )

        self.assertEqual(
            candidate["phase9b_version"],
            PHASE9B_VERSION,
        )
        self.assertEqual(
            candidate["score_summary"][
                "original_resume_score"
            ],
            32,
        )
        self.assertEqual(
            candidate["score_summary"][
                "approved_tailored_score"
            ],
            65,
        )
        self.assertEqual(
            candidate["evaluation_metadata"][
                "baseline_stable_fingerprint"
            ],
            "resolved-before-fingerprint",
        )

    def test_not_blueprint_ready_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "not eligible",
        ):
            build_blueprint_candidate(
                application_id=1,
                generation_state=GENERATION,
                verification={
                    **VERIFICATION,
                    "blueprint_ready": False,
                },
                baseline_report=BASELINE,
                role_family="AI",
                candidate_name="Candidate",
            )


if __name__ == "__main__":
    unittest.main()

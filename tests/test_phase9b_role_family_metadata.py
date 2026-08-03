from __future__ import annotations

import unittest

from tailoring.phase9b_blueprint_candidate import (
    build_blueprint_candidate,
)
from tailoring.phase9b_role_family import (
    build_default_candidate_name,
    build_default_candidate_notes,
    canonical_role_family_id,
    suggest_role_family,
)


GENERATION = {
    "application_id": 94,
    "generation_id": "ac8191407bea4aecac63b1330729e5ec",
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
                {
                    "title": "Job AI Helper",
                    "bullets": ["Built a Streamlit application."],
                },
                {
                    "title": "QueryAI",
                    "bullets": ["Built React workflows."],
                },
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
    "phase8_version": "phase8-before-after-verification-v5",
    "verification_id": "verification-a",
    "verification_fingerprint": "verification-fingerprint",
    "generation_id": GENERATION["generation_id"],
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
    "comparison": {
        "before_score": 36,
        "after_score": 74,
        "score_delta": 38,
        "required_core_coverage_delta": 46,
        "improved_requirements": [
            {"requirement_id": "req_streamlit"}
        ],
        "important_regressions": [],
    },
    "claim_lineage": {
        "lineage_version": "phase8-claim-lineage-v2",
        "claim_review_required_count": 0,
    },
    "after_stable_analysis": {
        "deterministic_alignment_score": 74,
        "scoring_version": "stable-evidence-v1",
        "capability_taxonomy_version": "taxonomy-v1",
        "canonical_requirements": [
            {
                "requirement_id": "req_streamlit",
                "text": "Hands-on experience with Streamlit",
                "importance": "required",
                "match_label": "direct",
                "evidence_strength": 5,
                "capability_id": "frontend.ui_development",
            },
            {
                "requirement_id": "req_missing",
                "text": "Production incident response",
                "importance": "core",
                "match_label": "none",
                "evidence_strength": 0,
            },
        ],
    },
}

BASELINE = {
    "jd_profile": {
        "job_title": "Junior AI and Full-Stack Software Engineer",
        "company": "Example Co",
    },
    "resume_profile": {
        "education": [
            {
                "degree": "BSc Computer Science",
                "school": "Example University",
            }
        ],
        "experience": [
            {
                "title": "Software Engineer Intern",
                "company": "Example Company",
                "bullets": ["Built software features."],
            }
        ],
    },
    "stable_analysis": {
        "deterministic_alignment_score": 36,
        "input_fingerprint": "baseline-fingerprint",
    },
}


class Phase9BRoleFamilyMetadataTests(unittest.TestCase):
    def test_ai_fullstack_title_maps_to_canonical_family(self):
        suggestion = suggest_role_family(BASELINE)
        self.assertEqual(
            suggestion["role_family"],
            "AI & Full-Stack Software Engineering",
        )
        self.assertEqual(suggestion["confidence"], "high")

    def test_garena_configuration_qa_maps_to_game_ops_family(self):
        suggestion = suggest_role_family(
            {
                "jd_profile": {
                    "job_title": "Associate, Configuration & QA"
                }
            }
        )
        self.assertEqual(
            suggestion["role_family"],
            "Game Operations, Configuration & QA",
        )
        self.assertEqual(suggestion["confidence"], "high")

    def test_custom_family_gets_stable_id(self):
        self.assertEqual(
            canonical_role_family_id(
                "Security Software Engineering"
            ),
            "custom_security_software_engineering",
        )

    def test_default_name_is_readable_and_stable(self):
        name = build_default_candidate_name(
            application_id=94,
            generation_id=GENERATION["generation_id"],
            role_family="AI & Full-Stack Software Engineering",
        )
        self.assertEqual(
            name,
            "AI & Full-Stack — App 94 — ac819140",
        )

    def test_default_notes_are_optional_human_context(self):
        notes = build_default_candidate_notes(
            application_id=94,
            generation_state=GENERATION,
            verification=VERIFICATION,
            baseline_report=BASELINE,
            role_family="AI & Full-Stack Software Engineering",
        )
        self.assertIn("Application 94", notes)
        self.assertIn("36 to 74", notes)
        self.assertIn("Job AI Helper", notes)
        self.assertIn("Phase 9C", notes)

    def test_candidate_stores_compact_phase9c_seed_not_full_debug(self):
        suggestion = suggest_role_family(BASELINE)
        candidate = build_blueprint_candidate(
            application_id=94,
            generation_state=GENERATION,
            verification=VERIFICATION,
            baseline_report=BASELINE,
            role_family=suggestion["role_family"],
            role_family_id=suggestion["role_family_id"],
            role_family_suggestion=suggestion,
            candidate_name="AI & Full-Stack — App 94 — ac819140",
            notes="",
            notes_source="blank",
        )

        self.assertEqual(
            candidate["role_family_id"],
            "ai_fullstack_software_engineering",
        )
        self.assertIn("resume_profile_snapshot", candidate)
        self.assertIn("resume_text_snapshot", candidate)
        self.assertIn("evaluation_metadata", candidate)
        self.assertEqual(
            candidate["evaluation_metadata"][
                "source_jd_remaining_important_gap_count"
            ],
            1,
        )
        self.assertFalse(
            candidate["provenance"]["full_debug_json_embedded"]
        )
        self.assertNotIn("before_stable_analysis", candidate)
        self.assertNotIn("after_stable_analysis", candidate)
        self.assertNotIn(
            "raw_comparison_before_reconciliation",
            candidate,
        )
        self.assertEqual(
            candidate["candidate_metadata"][
                "notes_influence_scoring"
            ],
            False,
        )


if __name__ == "__main__":
    unittest.main()

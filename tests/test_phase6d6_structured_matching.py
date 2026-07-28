from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from analysis_stability.stable_evidence_scoring import build_stable_analysis
from tailoring.phase6d6_structured_matching import (
    STRUCTURED_MATCH_VERSION,
    apply_structured_requirement_matches,
    structured_match_requirement,
)


RESUME_PROFILE = {
    "education": [
        {
            "school": "Singapore Institute of Technology - DigiPen",
            "degree": (
                "Bachelor of Science with Honours in Computer Science "
                "in Interactive Media and Game Development"
            ),
        }
    ],
    "skills": {
        "languages": ["C++", "C#", "Python", "TypeScript"],
        "tools": ["Git", "Docker"],
        "concepts": ["RESTful APIs"],
        "platforms": ["PostgreSQL", "AWS"],
    },
}


class Phase6D6StructuredMatchingTests(unittest.TestCase):
    def test_programming_or_group_is_direct_from_language_list(self):
        decision = structured_match_requirement(
            {
                "text": (
                    "Experience programming in Python, TypeScript, C++, or C#"
                )
            },
            resume_profile=RESUME_PROFILE,
        )

        self.assertIsNotNone(decision)
        self.assertEqual(decision["kind"], "programming_language_group")
        self.assertEqual(decision["group_mode"], "any")
        self.assertEqual(
            set(decision["matched_terms"]),
            {"Python", "TypeScript", "C++", "C#"},
        )

    def test_programming_and_group_requires_every_language(self):
        decision = structured_match_requirement(
            {"text": "Proficiency in Python and Rust"},
            resume_profile=RESUME_PROFILE,
        )
        self.assertIsNone(decision)

    def test_exact_git_skill_is_direct(self):
        decision = structured_match_requirement(
            {"text": "Experience using Git"},
            resume_profile=RESUME_PROFILE,
        )
        self.assertEqual(decision["kind"], "exact_structured_skill")
        self.assertEqual(decision["matched_terms"], ["Git"])

    def test_rest_api_alias_is_supported(self):
        decision = structured_match_requirement(
            {"text": "Experience using REST APIs"},
            resume_profile=RESUME_PROFILE,
        )
        self.assertEqual(decision["kind"], "exact_structured_skill")
        self.assertEqual(decision["matched_terms"], ["RESTful APIs"])

    def test_relational_database_is_derived_from_postgresql(self):
        decision = structured_match_requirement(
            {"text": "Experience using relational databases"},
            resume_profile=RESUME_PROFILE,
        )
        self.assertEqual(decision["kind"], "exact_structured_skill")
        self.assertEqual(decision["matched_terms"], ["PostgreSQL"])

    def test_education_is_verified_from_structured_education(self):
        decision = structured_match_requirement(
            {
                "text": (
                    "Diploma or degree in Computer Science, Software "
                    "Engineering, Game Development, or a related field"
                )
            },
            resume_profile=RESUME_PROFILE,
        )
        self.assertEqual(decision["kind"], "education_qualification")
        self.assertIn("Computer Science", decision["matched_terms"])

    def test_subjective_interest_is_not_inferred_from_game_degree(self):
        decision = structured_match_requirement(
            {"text": "Interest in online games"},
            resume_profile=RESUME_PROFILE,
        )
        self.assertIsNone(decision)

    def test_structured_stage_upgrades_weak_language_result(self):
        rows, warnings = apply_structured_requirement_matches(
            [
                {
                    "requirement_id": "req_languages",
                    "text": (
                        "Experience programming in Python, TypeScript, C++, or C#"
                    ),
                    "atomic_focus": (
                        "Experience programming in Python, TypeScript, C++, or C#"
                    ),
                    "match_label": "weak",
                    "match_value": 0.20,
                    "evidence_strength": 2,
                    "evidence": [{"text": "Python"}],
                    "match_source": "unmatched",
                }
            ],
            resume_profile=RESUME_PROFILE,
        )

        row = rows[0]
        self.assertEqual(row["match_label"], "direct")
        self.assertEqual(row["match_value"], 1.0)
        self.assertEqual(row["evidence_strength"], 5)
        self.assertEqual(row["match_source"], "structured_resume_profile")
        self.assertEqual(row["structured_match_status"], "applied")
        self.assertEqual(
            row["structured_match_version"],
            STRUCTURED_MATCH_VERSION,
        )
        self.assertEqual(
            warnings[0]["code"],
            "structured_resume_match_applied",
        )

    def test_full_stable_analysis_is_independent_of_ai_language_result(self):
        jd = (
            "Job Requirements\n"
            "- Experience programming in Python, TypeScript, C++, or C#"
        )
        weak_keyword_match = {
            "present": [],
            "missing": [
                {
                    "keyword": (
                        "Experience programming in Python, TypeScript, C++, or C#"
                    ),
                    "match_type": "missing",
                    "evidence_type": "none",
                    "match_reason": "The model incorrectly missed the languages.",
                }
            ],
        }

        with patch.dict(
            os.environ,
            {"CAPABILITY_RAG_MODE": "off"},
            clear=False,
        ):
            result = build_stable_analysis(
                jd_profile={
                    "required_skills": [
                        "Experience programming in Python, TypeScript, C++, or C#"
                    ],
                    "responsibilities": [],
                    "soft_skills": [],
                    "preferred_skills": [],
                    "deal_breakers": [],
                    "tools_technologies": [],
                },
                keyword_match=weak_keyword_match,
                raw_jd_text=jd,
                resume_profile=RESUME_PROFILE,
            )

        row = result["canonical_requirements"][0]
        self.assertEqual(row["match_label"], "direct")
        self.assertEqual(row["match_source"], "structured_resume_profile")
        self.assertEqual(row["structured_match_status"], "applied")
        self.assertFalse(
            row["capability_retrieval"]["influences_scoring"]
        )

    def test_repeated_structured_matching_is_identical(self):
        requirement = {
            "text": "Experience programming in Python, TypeScript, C++, or C#"
        }
        first = structured_match_requirement(
            requirement,
            resume_profile=RESUME_PROFILE,
        )
        second = structured_match_requirement(
            requirement,
            resume_profile=RESUME_PROFILE,
        )
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()

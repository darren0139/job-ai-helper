from __future__ import annotations

import copy
import unittest

from analysis_stability.stable_evidence_scoring import (
    build_deterministic_keyword_match,
    canonicalise_requirements,
)
from tailoring.phase9e_blueprint_selection import (
    PHASE9E_EVIDENCE_SELECTION_POLICY_VERSION,
    build_phase9e_keyword_match,
)


class Phase9EDeterministicEvidencePrecisionTests(unittest.TestCase):
    def _keyword_match(
        self,
        requirement_text: str,
        *,
        profile: dict,
        raw_resume_text: str,
        phase9e: bool = False,
    ) -> dict:
        raw_jd = f"Requirements:\n- {requirement_text}"
        canonical = canonicalise_requirements(
            jd_profile={"required_skills": [requirement_text]},
            raw_jd_text=raw_jd,
        )
        builder = (
            build_phase9e_keyword_match
            if phase9e
            else build_deterministic_keyword_match
        )
        return builder(
            requirements=copy.deepcopy(canonical["requirements"]),
            acronym_map=copy.deepcopy(canonical["acronym_map"]),
            resume_profile=copy.deepcopy(profile),
            raw_resume_text=raw_resume_text,
        )

    def _assert_missing(
        self,
        requirement_text: str,
        *,
        profile: dict,
        raw_resume_text: str,
    ) -> None:
        for phase9e in (False, True):
            with self.subTest(
                requirement=requirement_text,
                phase9e=phase9e,
            ):
                result = self._keyword_match(
                    requirement_text,
                    profile=profile,
                    raw_resume_text=raw_resume_text,
                    phase9e=phase9e,
                )
                present_keywords = {
                    str(row.get("keyword") or "")
                    for row in result.get("present", []) or []
                    if isinstance(row, dict)
                }
                missing_keywords = {
                    str(row.get("keyword") or "")
                    for row in result.get("missing", []) or []
                    if isinstance(row, dict)
                }
                self.assertNotIn(requirement_text, present_keywords)
                self.assertIn(requirement_text, missing_keywords)

    def test_postgrest_data_token_does_not_prove_data_structures(self):
        bullet = (
            "Implemented PostgREST data access and Row-Level Security "
            "policies to support real-time queries while controlling "
            "database access."
        )
        profile = {
            "projects": [{"title": "QueryAI", "bullets": [bullet]}],
            "experience": [],
            "education": [],
            "skills": {},
        }
        self._assert_missing(
            "Strong foundation in Data Structures/Algorithms",
            profile=profile,
            raw_resume_text=bullet,
        )
        self._assert_missing(
            "Understanding and familiarity with 3D Data Structures/Algorithms",
            profile=profile,
            raw_resume_text=bullet,
        )
        self._assert_missing(
            "Understand concepts in data oriented programming",
            profile=profile,
            raw_resume_text=bullet,
        )

    def test_generic_concepts_line_does_not_prove_memory_or_cache(self):
        concepts = (
            "concepts: OpenAI API, ChromaDB, RAG, Prompt Engineering, "
            "PostgREST, Row-Level Security, REST APIs, CI, Scrum"
        )
        profile = {
            "projects": [],
            "experience": [],
            "education": [],
            "skills": {
                "concepts": [
                    "OpenAI API",
                    "ChromaDB",
                    "RAG",
                    "Prompt Engineering",
                    "PostgREST",
                    "Row-Level Security",
                    "REST APIs",
                    "CI",
                    "Scrum",
                ]
            },
        }
        self._assert_missing(
            "Understand concepts in memory allocation",
            profile=profile,
            raw_resume_text=concepts,
        )
        self._assert_missing(
            "Understand concepts in cache performance",
            profile=profile,
            raw_resume_text=concepts,
        )

    def test_team_code_integration_does_not_prove_large_code_bases(self):
        bullet = (
            "Integrated team members' code into a working build and "
            "implemented image-attachment support using Coil."
        )
        profile = {
            "projects": [{"title": "Workout Buddy", "bullets": [bullet]}],
            "experience": [],
            "education": [],
            "skills": {},
        }
        self._assert_missing(
            "Comfortable working on large code bases",
            profile=profile,
            raw_resume_text=bullet,
        )

    def test_exact_cpp_evidence_remains_present(self):
        requirement = "Good foundation in modern C/C++ programming"
        profile = {
            "projects": [],
            "experience": [],
            "education": [],
            "skills": {"languages": ["C++"]},
        }
        result = self._keyword_match(
            requirement,
            profile=profile,
            raw_resume_text="C++",
            phase9e=False,
        )
        present = [
            row
            for row in result.get("present", []) or []
            if row.get("keyword") == requirement
        ]
        self.assertEqual(len(present), 1)
        self.assertIn(
            present[0].get("match_type"),
            {"direct", "transferable"},
        )

    def test_phase9e_policy_version_is_bumped_for_new_evidence_gate(self):
        self.assertEqual(
            PHASE9E_EVIDENCE_SELECTION_POLICY_VERSION,
            "phase9e-capability-aware-single-row-evidence-v4",
        )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import copy
import unittest

from analysis_stability.stable_evidence_scoring import (
    SCORING_VERSION,
    build_deterministic_keyword_match,
    build_resume_evidence_index,
    canonicalise_requirements,
)
from tailoring.phase9e_blueprint_selection import build_phase9e_keyword_match


class ResumeEvidenceStructuralHeadingTests(unittest.TestCase):
    def empty_profile(self) -> dict:
        return {
            "education": [],
            "experience": [],
            "projects": [],
            "skills": {},
        }

    def keyword_match(
        self,
        requirement: str,
        *,
        raw_resume_text: str,
        profile: dict | None = None,
        phase9e: bool = False,
    ) -> dict:
        canonical = canonicalise_requirements(
            jd_profile={"required_skills": [requirement]},
            raw_jd_text=f"Requirements:\n- {requirement}",
        )
        builder = (
            build_phase9e_keyword_match
            if phase9e
            else build_deterministic_keyword_match
        )
        return builder(
            requirements=copy.deepcopy(canonical["requirements"]),
            acronym_map=copy.deepcopy(canonical["acronym_map"]),
            resume_profile=copy.deepcopy(profile or self.empty_profile()),
            raw_resume_text=raw_resume_text,
        )

    def assert_missing(self, requirement: str, raw_resume_text: str) -> None:
        for phase9e in (False, True):
            with self.subTest(phase9e=phase9e):
                result = self.keyword_match(
                    requirement,
                    raw_resume_text=raw_resume_text,
                    phase9e=phase9e,
                )
                present = {
                    str(row.get("keyword") or "")
                    for row in result.get("present", []) or []
                    if isinstance(row, dict)
                }
                self.assertNotIn(requirement, present)

    def test_scoring_version_bumped(self):
        self.assertEqual(
            SCORING_VERSION,
            "stable-evidence-v1.13-phase6d20",
        )

    def test_structural_headings_are_not_evidence_rows(self):
        raw = (
            "SUMMARY\n"
            "WORK EXPERIENCE\n"
            "PROJECTS\n"
            "TECHNICAL SKILLS\n"
            "EDUCATION\n"
            "CERTIFICATIONS\n"
        )
        self.assertEqual(
            build_resume_evidence_index(self.empty_profile(), raw),
            [],
        )

    def test_projects_heading_cannot_prove_gemini_requirements(self):
        raw = "WORK EXPERIENCE\nPROJECTS\nSKILLS\n"
        requirements = (
            (
                "Improve the performance, maintainability, and operations of "
                "the Gemini code base by engaging in occasional refactoring "
                "and upgrade projects"
            ),
            (
                "Plan and coordinate project implementation support efforts "
                "and estimate work efforts and schedule for supporting project "
                "development and deployment"
            ),
        )
        for requirement in requirements:
            self.assert_missing(requirement, raw)

    def test_real_project_bullet_remains_eligible(self):
        requirement = (
            "Improve application performance and maintainability through "
            "refactoring"
        )
        bullet = (
            "Improved application performance and maintainability by "
            "refactoring the request pipeline."
        )
        profile = self.empty_profile()
        profile["projects"] = [
            {"title": "Job AI Helper", "bullets": [bullet]}
        ]
        result = self.keyword_match(
            requirement,
            raw_resume_text=f"PROJECTS\n{bullet}",
            profile=profile,
        )
        matching = [
            row
            for row in result.get("present", []) or []
            if row.get("keyword") == requirement
        ]
        self.assertEqual(len(matching), 1)
        self.assertNotEqual(
            str(matching[0].get("matched_resume_term") or "").strip(),
            "PROJECTS",
        )

    def test_structured_cpp_skill_remains_eligible(self):
        requirement = "Advanced proficiency in C++"
        profile = self.empty_profile()
        profile["skills"] = {"languages": ["C++"]}
        result = self.keyword_match(
            requirement,
            raw_resume_text="SKILLS\nC++",
            profile=profile,
        )
        matching = [
            row
            for row in result.get("present", []) or []
            if row.get("keyword") == requirement
        ]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0].get("matched_resume_term"), "C++")


if __name__ == "__main__":
    unittest.main()

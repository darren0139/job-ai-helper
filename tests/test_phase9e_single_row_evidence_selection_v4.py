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


class Phase9ESingleRowEvidenceSelectionV4Tests(unittest.TestCase):
    def test_android_kotlin_prefers_broader_single_project_row(self):
        requirement = "Experience working with Android app development and Kotlin"
        strong_bullet = (
            "Led frontend implementation for a GPS-based Android application "
            "using Kotlin and Jetpack Compose."
        )
        profile = {
            "projects": [
                {
                    "title": "Workout Buddy",
                    "bullets": [strong_bullet],
                }
            ],
            "experience": [],
            "education": [],
            "skills": {"languages": ["Kotlin"]},
        }
        raw_resume_text = f"{strong_bullet}\nKotlin"
        raw_jd = f"Preferred:\n- {requirement}"
        canonical = canonicalise_requirements(
            jd_profile={"preferred_skills": [requirement]},
            raw_jd_text=raw_jd,
        )

        baseline = build_deterministic_keyword_match(
            requirements=copy.deepcopy(canonical["requirements"]),
            acronym_map=copy.deepcopy(canonical["acronym_map"]),
            resume_profile=copy.deepcopy(profile),
            raw_resume_text=raw_resume_text,
        )
        corrected = build_phase9e_keyword_match(
            requirements=copy.deepcopy(canonical["requirements"]),
            acronym_map=copy.deepcopy(canonical["acronym_map"]),
            resume_profile=copy.deepcopy(profile),
            raw_resume_text=raw_resume_text,
        )

        baseline_row = next(
            row
            for row in baseline.get("present", [])
            if row.get("keyword") == requirement
        )
        corrected_row = next(
            row
            for row in corrected.get("present", [])
            if row.get("keyword") == requirement
        )

        self.assertEqual(baseline_row["matched_resume_term"], "Kotlin")
        self.assertEqual(corrected_row["matched_resume_term"], strong_bullet)

        # Citation quality changes; scoring semantics do not.
        self.assertEqual(
            corrected_row["match_type"],
            baseline_row["match_type"],
        )
        self.assertEqual(
            corrected_row["evidence_type"],
            baseline_row["evidence_type"],
        )

        audit = corrected_row["phase9e_evidence_selection"]
        self.assertEqual(
            audit["policy_version"],
            "phase9e-capability-aware-single-row-evidence-v4",
        )
        self.assertEqual(
            audit["selection_basis"],
            "broader_requirement_coverage",
        )
        self.assertEqual(audit["original_matched_resume_term"], "Kotlin")
        self.assertGreaterEqual(
            audit["selected_requirement_coverage"],
            0.50,
        )
        self.assertGreaterEqual(
            audit["selected_requirement_overlap_count"],
            2,
        )
        self.assertFalse(audit["combined_evidence_rows"])

    def test_broader_fallback_does_not_replace_a_multi_token_skill_match(self):
        requirement = "Good foundation in modern C/C++ programming"
        bullet = (
            "Built a C++ asset manager that centralised engine asset loading."
        )
        profile = {
            "projects": [{"title": "Engine", "bullets": [bullet]}],
            "experience": [],
            "education": [],
            "skills": {"languages": ["C++"]},
        }
        raw_jd = f"Requirements:\n- {requirement}"
        canonical = canonicalise_requirements(
            jd_profile={"required_skills": [requirement]},
            raw_jd_text=raw_jd,
        )
        corrected = build_phase9e_keyword_match(
            requirements=copy.deepcopy(canonical["requirements"]),
            acronym_map=copy.deepcopy(canonical["acronym_map"]),
            resume_profile=copy.deepcopy(profile),
            raw_resume_text=f"{bullet}\nC++",
        )
        row = next(
            item
            for item in corrected.get("present", [])
            if item.get("keyword") == requirement
        )
        self.assertEqual(row["matched_resume_term"], "C++")
        self.assertNotIn("phase9e_evidence_selection", row)

    def test_policy_version_is_v4(self):
        self.assertEqual(
            PHASE9E_EVIDENCE_SELECTION_POLICY_VERSION,
            "phase9e-capability-aware-single-row-evidence-v4",
        )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from tailoring.tailoring_generation_fingerprint import (
    build_generation_action_plan,
    build_tailoring_input_fingerprint,
    compare_tailoring_generations,
    get_effective_generation_sections,
    resolve_locked_sections,
)


def approved_generation() -> dict:
    return {
        "generation_id": "approved-1",
        "projects": {
            "recommended_projects": [
                {
                    "title": "CyberSphere",
                    "draft_bullets": ["Kept.", "Removed by fitting."],
                }
            ]
        },
        "skills": {
            "skill_lines": [
                {"category": "Programming", "items": ["C++", "C#"]}
            ]
        },
        "fit_result": {
            "page_count": 1,
            "fit_one_page": True,
            "tailored_projects_used": {
                "recommended_projects": [
                    {
                        "title": "CyberSphere",
                        "draft_bullets": ["Kept."],
                    }
                ]
            },
            "tailored_skills_used": {
                "skill_lines": [
                    {"category": "Programming", "items": ["C++"]}
                ]
            },
        },
    }


class Phase7ApprovedFinalLockTests(unittest.TestCase):
    def test_effective_sections_prefer_final_fitted_output(self):
        effective = get_effective_generation_sections(
            approved_generation()
        )
        bullets = effective["projects"]["recommended_projects"][0][
            "draft_bullets"
        ]
        self.assertEqual(bullets, ["Kept."])
        self.assertEqual(
            effective["projects_source"],
            "final_fitted_output",
        )
        self.assertEqual(
            effective["skills"]["skill_lines"][0]["items"],
            ["C++"],
        )

    def test_locked_sections_use_final_fitted_output(self):
        projects, skills = resolve_locked_sections(
            proposed_projects={"marker": "new-projects"},
            proposed_skills={"marker": "new-skills"},
            approved_generation=approved_generation(),
            lock_projects=True,
            lock_skills=True,
        )
        self.assertEqual(
            projects["recommended_projects"][0]["draft_bullets"],
            ["Kept."],
        )
        self.assertEqual(
            skills["skill_lines"][0]["items"],
            ["C++"],
        )

    def test_both_locked_loads_approved_without_draft(self):
        plan = build_generation_action_plan(
            lock_projects=True,
            lock_skills=True,
            approved_generation=approved_generation(),
        )
        self.assertEqual(plan["mode"], "load_approved")
        self.assertFalse(plan["requires_project_ai"])
        self.assertFalse(plan["requires_skills_ai"])
        self.assertFalse(plan["creates_draft"])

    def test_single_lock_generates_only_unlocked_section(self):
        plan = build_generation_action_plan(
            lock_projects=False,
            lock_skills=True,
            approved_generation=approved_generation(),
        )
        self.assertTrue(plan["requires_project_ai"])
        self.assertFalse(plan["requires_skills_ai"])
        self.assertTrue(plan["creates_draft"])

    def test_fingerprint_uses_final_locked_content(self):
        base_args = {
            "report": {
                "resume_profile": {"name": "Candidate"},
                "jd_profile": {"job_title": "Engineer"},
                "raw_jd_text": "JD",
                "stable_analysis": {
                    "input_fingerprint": "stable-1",
                    "scoring_version": "stable-v1",
                },
            },
            "evidence_items": [],
            "generation_settings": {"max_projects": 3},
            "generation_kind": "projects_skills",
            "model_id": "model-a",
            "approved_generation": approved_generation(),
            "lock_projects": True,
            "lock_skills": True,
        }
        first = build_tailoring_input_fingerprint(**base_args)
        changed = approved_generation()
        changed["projects"]["recommended_projects"][0][
            "draft_bullets"
        ].append("Hidden pre-fit change.")
        second = build_tailoring_input_fingerprint(
            **{**base_args, "approved_generation": changed}
        )
        # A hidden pre-fit change must not invalidate the final-output lock.
        self.assertEqual(first, second)

    def test_comparison_uses_final_outputs(self):
        left = approved_generation()
        right = approved_generation()
        right["projects"]["recommended_projects"][0][
            "draft_bullets"
        ].append("Different hidden raw bullet.")
        result = compare_tailoring_generations(left, right)
        self.assertTrue(result["identical_projects"])


if __name__ == "__main__":
    unittest.main()

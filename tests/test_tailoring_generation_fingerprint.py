from __future__ import annotations

import unittest

from tailoring.tailoring_generation_fingerprint import (
    build_fitting_lock_policy,
    build_tailoring_input_fingerprint,
    compare_tailoring_generations,
    resolve_locked_sections,
)


class TailoringGenerationFingerprintTests(unittest.TestCase):
    def payload(self):
        return {
            "report": {
                "resume_profile": {"skills": {"languages": ["Python"]}},
                "jd_profile": {"job_title": "Engineer"},
                "stable_analysis": {
                    "input_fingerprint": "stable-a",
                    "scoring_version": "stable-v1",
                },
            },
            "evidence_items": [{"id": 1, "title": "Project"}],
            "generation_settings": {"max_projects": 3},
            "generation_kind": "projects_skills",
            "model_id": "model-a",
        }

    def test_fingerprint_is_dict_order_stable(self):
        first = build_tailoring_input_fingerprint(**self.payload())
        payload = self.payload()
        payload["generation_settings"] = {"max_projects": 3}
        second = build_tailoring_input_fingerprint(**payload)
        self.assertEqual(first, second)

    def test_fingerprint_changes_when_list_order_changes(self):
        payload = self.payload()
        payload["evidence_items"] = [
            {"id": 1, "title": "First"},
            {"id": 2, "title": "Second"},
        ]
        first = build_tailoring_input_fingerprint(**payload)
        payload["evidence_items"] = list(
            reversed(payload["evidence_items"])
        )
        second = build_tailoring_input_fingerprint(**payload)
        self.assertNotEqual(first, second)

    def test_fingerprint_changes_with_settings(self):
        first = build_tailoring_input_fingerprint(**self.payload())
        payload = self.payload()
        payload["generation_settings"]["max_projects"] = 4
        second = build_tailoring_input_fingerprint(**payload)
        self.assertNotEqual(first, second)

    def test_locked_sections_override_proposed_content(self):
        approved = {
            "projects": {"marker": "approved-projects"},
            "skills": {"marker": "approved-skills"},
        }
        projects, skills = resolve_locked_sections(
            proposed_projects={"marker": "new-projects"},
            proposed_skills={"marker": "new-skills"},
            approved_generation=approved,
            lock_projects=True,
            lock_skills=False,
        )
        self.assertEqual(projects["marker"], "approved-projects")
        self.assertEqual(skills["marker"], "new-skills")

    def test_lock_policy_blocks_locked_reductions(self):
        policy = build_fitting_lock_policy(
            lock_projects=True,
            lock_skills=True,
        )
        self.assertFalse(policy["allow_project_compaction"])
        self.assertFalse(policy["allow_project_bullet_removal"])
        self.assertFalse(policy["allow_project_removal"])
        self.assertFalse(policy["allow_skills_compaction"])

    def test_comparison_reports_project_and_skill_changes(self):
        left = {
            "generation_id": "left",
            "projects": {
                "recommended_projects": [
                    {"title": "A", "draft_bullets": ["One."]}
                ]
            },
            "skills": {
                "skill_lines": [
                    {"category": "Languages", "items": ["Python"]}
                ]
            },
        }
        right = {
            "generation_id": "right",
            "projects": {
                "recommended_projects": [
                    {"title": "B", "draft_bullets": ["Two."]}
                ]
            },
            "skills": {
                "skill_lines": [
                    {"category": "Languages", "items": ["Python", "C++"]}
                ]
            },
        }
        result = compare_tailoring_generations(left, right)
        self.assertEqual(result["project_changes"]["added"], ["B"])
        self.assertEqual(result["project_changes"]["removed"], ["A"])
        self.assertEqual(
            result["skill_changes"]["changed_categories"],
            ["Languages"],
        )


if __name__ == "__main__":
    unittest.main()

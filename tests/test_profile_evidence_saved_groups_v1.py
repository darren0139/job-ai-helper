"""UI-only grouping regression tests. No DB/LLM/Streamlit imports."""
from __future__ import annotations

import unittest
from pathlib import Path

from tailoring.profile_evidence_saved_groups import (
    GROUP_HEADINGS,
    GROUP_ORDER,
    ordered_saved_evidence_items,
    saved_evidence_group,
    saved_evidence_group_heading,
    saved_evidence_item_label,
)


class SavedEvidenceGroupingTests(unittest.TestCase):
    def test_work_project_skill_other_group_order(self):
        items = [
            {"id": 3, "category": "Skill", "title": "NVIDIA cuDF"},
            {"id": 6, "category": "Coursework", "title": "Algebra"},
            {"id": 5, "category": "project", "title": "Job AI Helper"},
            {"id": 2, "category": "Work Experience", "title": "Engineer"},
            {"id": 4, "category": "Project", "title": "CyberSphere"},
            {"id": 1, "category": "Internship", "title": "Game Dev Intern"},
        ]
        result = ordered_saved_evidence_items(items)
        self.assertEqual([x["id"] for x in result], [2, 1, 5, 4, 3, 6])
        self.assertEqual([x["id"] for x in items], [3, 6, 5, 2, 4, 1])
        self.assertEqual(len(result), len(items))
        self.assertEqual({x["id"] for x in result}, {x["id"] for x in items})

    def test_original_sort_is_preserved_within_each_group(self):
        original = [
            {"id": 8, "category": "Project"},
            {"id": 1, "category": "Work Experience"},
            {"id": 7, "category": "Project"},
            {"id": 2, "category": "Internship"},
            {"id": 9, "category": "Project"},
            {"id": 3, "category": "Skill"},
            {"id": 4, "category": "Skill"},
        ]
        result = ordered_saved_evidence_items(original)
        self.assertEqual([row["id"] for row in result], [1, 2, 8, 7, 9, 3, 4])

    def test_categories_case_and_unknown_are_non_destructive(self):
        for category in [" Work Experience ", "internship", "INTERNSHIP"]:
            self.assertEqual(saved_evidence_group({"category": category}), "work")
        for category in ["Skill", "skill "]:
            self.assertEqual(saved_evidence_group({"category": category}), "skill")
        for category in ["Coursework", "Certification", "Achievement", "Other", None, ""]:
            self.assertEqual(saved_evidence_group({"category": category}), "other")
        self.assertEqual(ordered_saved_evidence_items([]), [])

    def test_work_header_uses_employer_without_changing_stored_item(self):
        work = {"id": 12, "category": "Work Experience", "title": "Software Engineer Intern", "subtitle": "Singapore Maritime Institute"}
        self.assertEqual(saved_evidence_item_label(work), "Software Engineer Intern — Singapore Maritime Institute")
        self.assertEqual(work["title"], "Software Engineer Intern")
        self.assertEqual(saved_evidence_item_label({"category": "Project", "title": "CyberSphere", "subtitle": "Shooter Game"}), "CyberSphere")
        self.assertEqual(saved_evidence_item_label({"category": "Skill", "title": "NVIDIA cuDF"}), "NVIDIA cuDF")

    def test_every_group_has_distinct_user_visible_heading(self):
        self.assertEqual(GROUP_ORDER, ("work", "project", "skill", "other"))
        self.assertEqual(len(GROUP_HEADINGS), len(GROUP_ORDER))
        self.assertIn("Saved Work Experience", saved_evidence_group_heading("work"))
        self.assertIn("Saved Projects", saved_evidence_group_heading("project"))
        self.assertIn("Saved Skills", saved_evidence_group_heading("skill"))

    def test_integration_anchor_keeps_existing_edit_delete_code(self):
        app = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
        self.assertIn("# saved-evidence-grouped-display-v1", app)
        self.assertIn("for item in ordered_saved_evidence_items(evidence_items):", app)
        self.assertIn("saved_evidence_item_label(item)", app)
        self.assertIn("edit_evidence_mode_", app)
        self.assertIn("delete_evidence_", app)


if __name__ == "__main__":
    unittest.main()

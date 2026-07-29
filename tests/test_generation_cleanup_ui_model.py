from __future__ import annotations

import unittest

from tailoring.generation_cleanup_ui_model import (
    build_cleanup_rows,
    cleanup_option_label,
    filter_cleanup_versions,
    selected_cleanup_versions,
)


VERSIONS = [
    {
        "generation_id": "approved-12345678",
        "status": "approved",
        "generation_kind": "projects_skills",
        "updated_at": "2026-07-29T10:00:00",
        "fit_result": {"page_count": 1},
    },
    {
        "generation_id": "draft-abcdefgh",
        "status": "draft",
        "generation_kind": "projects_skills",
        "updated_at": "2026-07-29T11:00:00",
        "fit_result": {"page_count": 1},
    },
    {
        "generation_id": "archived-xyz12345",
        "status": "archived",
        "generation_kind": "projects_skills",
        "updated_at": "2026-07-29T12:00:00",
        "fit_result": {"page_count": 2},
    },
]


class GenerationCleanupUIModelTests(unittest.TestCase):
    def test_draft_filter_excludes_approved_and_archived(self):
        result = filter_cleanup_versions(VERSIONS, "Drafts")
        self.assertEqual(
            [row["generation_id"] for row in result],
            ["draft-abcdefgh"],
        )

    def test_all_deletable_excludes_approved(self):
        result = filter_cleanup_versions(VERSIONS, "All deletable")
        self.assertEqual(
            [row["status"] for row in result],
            ["draft", "archived"],
        )

    def test_selected_versions_preserve_visible_order(self):
        result = selected_cleanup_versions(
            VERSIONS,
            ["archived-xyz12345", "draft-abcdefgh"],
        )
        self.assertEqual(
            [row["generation_id"] for row in result],
            ["draft-abcdefgh", "archived-xyz12345"],
        )

    def test_cleanup_rows_show_loaded_state(self):
        rows = build_cleanup_rows(
            VERSIONS[1:],
            loaded_generation_id="draft-abcdefgh",
        )
        self.assertEqual(rows[0]["Loaded"], "Yes")
        self.assertEqual(rows[1]["Pages"], 2)

    def test_option_label_is_readable(self):
        label = cleanup_option_label(VERSIONS[1])
        self.assertIn("Draft", label)
        self.assertIn("draft-ab", label)
        self.assertIn("projects_skills", label)

    def test_invalid_filter_is_rejected(self):
        with self.assertRaises(ValueError):
            filter_cleanup_versions(VERSIONS, "Approved")


if __name__ == "__main__":
    unittest.main()

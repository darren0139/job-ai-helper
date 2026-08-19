from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from database import user_profile_manager as profile_manager
from resume_builder.project_header_format import (
    build_project_title,
    format_project_metadata,
    inline_project_header,
    normalise_project_header_layout,
    normalise_project_metadata_style,
    split_legacy_project_title,
)
from tailoring.project_section_tailor import _evidence_item_to_candidate


class ResumeFormatStylePolicyTests(unittest.TestCase):
    def test_pipe_groups_are_semantic_not_baked_into_title(self):
        project = {
            "title": "CyberSphere",
            "resume_header_tools": ["Unity Engine", "C#"],
            "resume_header_context": ["Team of 2", "Published on Google Play"],
        }
        self.assertEqual(build_project_title(project), "CyberSphere")
        self.assertEqual(
            format_project_metadata(project, style="pipes"),
            "Unity Engine, C# | Team of 2 | Published on Google Play",
        )
        self.assertEqual(
            inline_project_header(project, style="pipes"),
            "CyberSphere | Unity Engine, C# | Team of 2 | Published on Google Play",
        )

    def test_parentheses_remain_legacy_option(self):
        project = {
            "title": "CyberSphere",
            "resume_header_tools": ["Unity Engine", "C#"],
            "resume_header_context": ["Team of 2"],
        }
        self.assertEqual(
            inline_project_header(project, style="parentheses"),
            "CyberSphere (Unity Engine, C#, Team of 2)",
        )

    def test_subtitle_is_separate_from_metadata(self):
        project = {
            "title": "RequestFlow",
            "subtitle": "IT Service Request Tracker",
            "resume_header_tools": ["React", "TypeScript", "FastAPI"],
            "resume_header_context": ["Individual Project"],
        }
        self.assertEqual(
            build_project_title(project),
            "RequestFlow — IT Service Request Tracker",
        )
        self.assertEqual(
            format_project_metadata(project, style="pipes"),
            "React, TypeScript, FastAPI | Individual Project",
        )

    def test_legacy_title_parser(self):
        parsed = split_legacy_project_title(
            "CyberSphere (Unity Engine, Team of 2, Published on Google Play)"
        )
        self.assertEqual(parsed["title"], "CyberSphere")
        self.assertEqual(parsed["resume_header_tools"], ["Unity Engine"])
        self.assertEqual(
            parsed["resume_header_context"],
            ["Team of 2", "Published on Google Play"],
        )
        self.assertTrue(parsed["legacy_metadata_found"])

    def test_defaults_fail_safe(self):
        self.assertEqual(normalise_project_header_layout("nonsense"), "auto")
        self.assertEqual(normalise_project_metadata_style("nonsense"), "pipes")

    def test_evidence_candidate_propagates_metadata(self):
        candidate = _evidence_item_to_candidate({
            "category": "Project",
            "title": "CyberSphere",
            "subtitle": "",
            "description": "Built gameplay systems.",
            "period": "Jan 2018 - Feb 2018",
            "skills": ["Gameplay scripting"],
            "tools": ["Unity Engine", "C#"],
            "resume_header_tools": ["Unity Engine", "C#"],
            "resume_header_context": ["Team of 2", "Published on Google Play"],
            "impact": "Published mobile game",
        })
        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual(candidate["title"], "CyberSphere")
        self.assertEqual(candidate["resume_header_tools"], ["Unity Engine", "C#"])

    def test_database_migration_preserves_id_and_canonical_tools(self):
        original_db = profile_manager.DB_PATH
        with tempfile.TemporaryDirectory() as temporary:
            profile_manager.DB_PATH = Path(temporary) / "applications.db"
            try:
                profile_manager.init_user_profile_library()
                item_id = profile_manager.create_evidence_item(
                    category="Project",
                    title=(
                        "CyberSphere (Unity Engine, Team of 2, "
                        "Published on Google Play)"
                    ),
                    description="Built gameplay systems.",
                    tools=["Unity Engine", "C#"],
                )
                self.assertEqual(
                    profile_manager.migrate_legacy_project_titles_to_structured_metadata(),
                    1,
                )
                item = profile_manager.get_evidence_item_by_id(item_id)
                self.assertIsNotNone(item)
                assert item is not None
                self.assertEqual(item["id"], item_id)
                self.assertEqual(item["title"], "CyberSphere")
                self.assertEqual(item["tools"], ["Unity Engine", "C#"])
                self.assertEqual(item["resume_header_tools"], ["Unity Engine"])
                self.assertEqual(
                    item["resume_header_context"],
                    ["Team of 2", "Published on Google Play"],
                )
            finally:
                profile_manager.DB_PATH = original_db

    def test_profile_preferences(self):
        original_db = profile_manager.DB_PATH
        with tempfile.TemporaryDirectory() as temporary:
            profile_manager.DB_PATH = Path(temporary) / "applications.db"
            try:
                profile_manager.init_user_profile_library()
                self.assertEqual(
                    profile_manager.get_resume_format_preferences(),
                    {"project_header_layout": "auto", "project_metadata_style": "pipes"},
                )
                profile_manager.update_resume_format_preferences(
                    project_header_layout="stacked",
                    project_metadata_style="parentheses",
                )
                self.assertEqual(
                    profile_manager.get_resume_format_preferences(),
                    {"project_header_layout": "stacked", "project_metadata_style": "parentheses"},
                )
            finally:
                profile_manager.DB_PATH = original_db


if __name__ == "__main__":
    unittest.main()

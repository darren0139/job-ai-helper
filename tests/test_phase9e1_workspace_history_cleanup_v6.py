"""Regression tests for Phase 9E.1 workspace/history cleanup V6."""

from __future__ import annotations

import tempfile
import ast
import unittest
from pathlib import Path

from database import tailoring_generation_control as control
from database import tailoring_version_manager as base


REPO_ROOT = Path(__file__).resolve().parents[1]


class Phase9E1WorkspaceHistoryCleanupV6Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db = base.DB_PATH
        base.DB_PATH = Path(self.temp_dir.name) / "applications.db"

    def tearDown(self) -> None:
        base.DB_PATH = self.old_db
        self.temp_dir.cleanup()

    def _save(self, application_id: int, generation_id: str) -> None:
        base.save_application_tailoring_generation(
            application_id=application_id,
            generation_id=generation_id,
            projects={
                "recommended_projects": [
                    {
                        "title": generation_id,
                        "draft_bullets": ["Built X."],
                    }
                ]
            },
            skills={
                "skill_lines": [
                    {
                        "category": "Programming",
                        "items": ["Python"],
                    }
                ]
            },
        )
        control.record_generation_metadata(
            application_id=application_id,
            generation_id=generation_id,
            generation_kind="projects_skills",
        )

    def test_unreferenced_draft_can_be_deleted(self) -> None:
        self._save(1, "draft-a")
        plan = control.get_tailoring_generation_delete_plan(
            application_id=1,
            generation_id="draft-a",
        )
        self.assertTrue(plan["deletable"])
        control.delete_tailoring_generation(
            application_id=1,
            generation_id="draft-a",
        )
        self.assertIsNone(
            control.get_tailoring_generation(1, "draft-a")
        )

    def test_phase8_reference_protects_history(self) -> None:
        self._save(2, "draft-a")
        connection = control._connect()
        connection.execute(
            """
            CREATE TABLE application_tailoring_verifications (
                application_id INTEGER NOT NULL,
                generation_id TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO application_tailoring_verifications (
                application_id, generation_id
            ) VALUES (?, ?)
            """,
            (2, "draft-a"),
        )
        connection.commit()
        connection.close()

        plan = control.get_tailoring_generation_delete_plan(
            application_id=2,
            generation_id="draft-a",
        )
        self.assertFalse(plan["deletable"])
        self.assertTrue(
            any("Phase 8" in item for item in plan["blockers"])
        )
        with self.assertRaises(ValueError):
            control.delete_tailoring_generation(
                application_id=2,
                generation_id="draft-a",
            )

    def test_phase9b_candidate_reference_protects_history(self) -> None:
        self._save(3, "draft-a")
        connection = control._connect()
        connection.execute(
            """
            CREATE TABLE global_blueprint_candidates (
                source_application_id INTEGER NOT NULL,
                source_generation_id TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO global_blueprint_candidates (
                source_application_id, source_generation_id
            ) VALUES (?, ?)
            """,
            (3, "draft-a"),
        )
        connection.commit()
        connection.close()

        plan = control.get_tailoring_generation_delete_plan(
            application_id=3,
            generation_id="draft-a",
        )
        self.assertFalse(plan["deletable"])
        self.assertTrue(
            any("Phase 9B" in item for item in plan["blockers"])
        )

    def test_clear_drafts_skips_referenced_drafts(self) -> None:
        self._save(4, "protected")
        self._save(4, "remove-me")
        connection = control._connect()
        connection.execute(
            """
            CREATE TABLE application_tailoring_verifications (
                application_id INTEGER NOT NULL,
                generation_id TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO application_tailoring_verifications (
                application_id, generation_id
            ) VALUES (?, ?)
            """,
            (4, "protected"),
        )
        connection.commit()
        connection.close()

        result = control.clear_tailoring_drafts(application_id=4)
        self.assertEqual(result["deleted_count"], 1)
        self.assertIn("protected", result["skipped_generation_ids"])
        self.assertIsNotNone(
            control.get_tailoring_generation(4, "protected")
        )
        self.assertIsNone(
            control.get_tailoring_generation(4, "remove-me")
        )

    def test_normal_workspace_dropdown_excludes_history(self) -> None:
        text = (
            REPO_ROOT
            / "tailoring"
            / "phase9e1_resume_workspace_ui.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"Current résumé version"', text)
        self.assertIn('"Version history and recovery', text)
        self.assertIn("current_by_id", text)
        self.assertIn('"Delete draft"', text)
        self.assertIn('"Development cleanup"', text)
        self.assertIn(
            "Historical versions are intentionally excluded",
            text,
        )

    def test_completed_phases_are_progressively_collapsed(self) -> None:
        app_text = (REPO_ROOT / "app.py").read_text(encoding="utf-8")
        lifecycle_text = (
            REPO_ROOT
            / "tailoring"
            / "phase9e1_blueprint_lifecycle_ui.py"
        ).read_text(encoding="utf-8")
        self.assertIn("phase9a_lifecycle_stage", app_text)
        self.assertIn("post_fit_lifecycle_stage", app_text)
        app_tree = ast.parse(app_text)
        app_string_literals = {
            node.value
            for node in ast.walk(app_tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
        }
        self.assertIn(
            "Phase 8 — Approved résumé ",
            app_string_literals,
        )
        self.assertIn(
            " · Complete",
            app_string_literals,
        )
        self.assertIn(
            "Phase 9B — Blueprint Candidate · Complete",
            lifecycle_text,
        )

    def test_workspace_is_primary_normal_version_controller(self) -> None:
        controls_text = (
            REPO_ROOT
            / "tailoring"
            / "generation_controls_ui.py"
        ).read_text(encoding="utf-8")
        self.assertIn("workspace_managed: bool = False", controls_text)
        self.assertNotIn(
            "Advanced version history and recovery",
            controls_text,
        )
        self.assertIn(
            "if not workspace_managed:",
            controls_text,
        )
        self.assertIn(
            "Approve current working draft",
            controls_text,
        )


if __name__ == "__main__":
    unittest.main()

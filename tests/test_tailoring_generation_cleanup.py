from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from database import tailoring_version_manager as base
from database import tailoring_generation_control as control


class TailoringGenerationCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db = base.DB_PATH
        base.DB_PATH = Path(self.temp_dir.name) / "applications.db"

    def tearDown(self):
        base.DB_PATH = self.old_db
        self.temp_dir.cleanup()

    def _save(
        self,
        application_id: int,
        generation_id: str,
        *,
        path: Path | None = None,
    ):
        base.save_application_tailoring_generation(
            application_id=application_id,
            generation_id=generation_id,
            projects={
                "recommended_projects": [
                    {"title": generation_id, "draft_bullets": ["Built X."]}
                ]
            },
            skills={
                "skill_lines": [
                    {"category": "Programming", "items": ["Python"]}
                ]
            },
            docx_path=path,
        )
        control.record_generation_metadata(
            application_id=application_id,
            generation_id=generation_id,
            input_fingerprint=f"fingerprint-{generation_id}",
            generation_kind="projects_skills",
        )

    def test_delete_draft_removes_version_and_metadata(self):
        self._save(1, "draft-a")
        result = control.delete_tailoring_generation(
            application_id=1,
            generation_id="draft-a",
        )
        self.assertEqual(result["status"], "draft")
        self.assertEqual(result["version_deleted"], 1)
        self.assertIsNone(
            control.get_tailoring_generation(1, "draft-a")
        )

    def test_approved_generation_is_protected(self):
        self._save(2, "approved-a")
        control.approve_tailoring_generation(2, "approved-a")
        with self.assertRaises(ValueError):
            control.delete_tailoring_generation(
                application_id=2,
                generation_id="approved-a",
            )
        self.assertIsNotNone(
            control.get_tailoring_generation(2, "approved-a")
        )

    def test_archived_generation_can_be_deleted(self):
        self._save(3, "archived-a")
        control.archive_tailoring_generation(3, "archived-a")
        result = control.delete_tailoring_generation(
            application_id=3,
            generation_id="archived-a",
        )
        self.assertEqual(result["status"], "archived")
        self.assertIsNone(
            control.get_tailoring_generation(3, "archived-a")
        )

    def test_clear_drafts_keeps_approved_and_archived(self):
        self._save(4, "approved-a")
        self._save(4, "archived-a")
        self._save(4, "draft-a")
        self._save(4, "draft-b")
        control.approve_tailoring_generation(4, "approved-a")
        control.archive_tailoring_generation(4, "archived-a")

        result = control.clear_tailoring_drafts(application_id=4)
        self.assertEqual(result["deleted_count"], 2)
        remaining = {
            row["generation_id"]: row["status"]
            for row in control.list_tailoring_generations(4)
        }
        self.assertEqual(
            remaining,
            {
                "approved-a": "approved",
                "archived-a": "archived",
            },
        )

    def test_shared_output_file_is_deleted_only_when_unreferenced(self):
        shared = Path(self.temp_dir.name) / "shared.docx"
        shared.write_text("content", encoding="utf-8")
        self._save(5, "draft-a", path=shared)
        self._save(5, "draft-b", path=shared)

        first = control.delete_tailoring_generation(
            application_id=5,
            generation_id="draft-a",
            delete_unreferenced_files=True,
        )
        self.assertTrue(shared.exists())
        self.assertIn(str(shared), first["files"]["kept"])

        second = control.delete_tailoring_generation(
            application_id=5,
            generation_id="draft-b",
            delete_unreferenced_files=True,
        )
        self.assertFalse(shared.exists())
        self.assertIn(str(shared), second["files"]["deleted"])

    def test_saved_lock_state_is_returned_visibly(self):
        self._save(6, "approved-a")
        control.approve_tailoring_generation(6, "approved-a")
        saved = control.set_tailoring_section_locks(
            application_id=6,
            lock_projects=True,
            lock_skills=False,
        )
        self.assertTrue(saved["lock_projects"])
        self.assertFalse(saved["lock_skills"])
        self.assertTrue(saved["updated_at"])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from database import tailoring_version_manager as manager


class TailoringVersionManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.original_db_path = manager.DB_PATH
        self.original_tailored_dir = manager.TAILORED_RESUME_DIR
        self.original_preview_dir = manager.PREVIEW_DIR
        manager.DB_PATH = root / "applications.db"
        manager.TAILORED_RESUME_DIR = root / "tailored"
        manager.PREVIEW_DIR = root / "previews"

    def tearDown(self):
        manager.DB_PATH = self.original_db_path
        manager.TAILORED_RESUME_DIR = self.original_tailored_dir
        manager.PREVIEW_DIR = self.original_preview_dir
        self.temp_dir.cleanup()

    def test_round_trip_generation(self):
        docx = manager.TAILORED_RESUME_DIR / "app_7_tailored_resume_a.docx"
        docx.parent.mkdir(parents=True)
        docx.write_bytes(b"docx")

        row_id = manager.save_application_tailoring_generation(
            application_id=7,
            generation_id="gen-a",
            projects={"recommended_projects": [{"title": "QueryAI"}]},
            skills={"skill_lines": [{"category": "Programming"}]},
            fit_result={"page_count": 1, "docx_path": str(docx)},
        )

        loaded = manager.get_latest_application_tailoring(7)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["id"], row_id)
        self.assertEqual(loaded["generation_id"], "gen-a")
        self.assertEqual(
            loaded["projects"]["recommended_projects"][0]["title"],
            "QueryAI",
        )
        self.assertEqual(loaded["fit_result"]["page_count"], 1)
        self.assertEqual(loaded["docx_path"], str(docx))

    def test_partial_update_preserves_existing_json(self):
        manager.save_application_tailoring_generation(
            application_id=8,
            generation_id="gen-a",
            projects={"recommended_projects": [{"title": "CyberSphere"}]},
        )
        manager.save_application_tailoring_generation(
            application_id=8,
            generation_id="gen-a",
            skills={"skill_lines": [{"category": "Game"}]},
        )

        loaded = manager.get_latest_application_tailoring(8)
        self.assertEqual(
            loaded["projects"]["recommended_projects"][0]["title"],
            "CyberSphere",
        )
        self.assertEqual(
            loaded["skills"]["skill_lines"][0]["category"],
            "Game",
        )

    def test_latest_generation_is_returned(self):
        manager.save_application_tailoring_generation(
            application_id=9,
            generation_id="older",
            projects={"marker": "old"},
        )
        manager.save_application_tailoring_generation(
            application_id=9,
            generation_id="newer",
            projects={"marker": "new"},
        )
        loaded = manager.get_latest_application_tailoring(9)
        self.assertEqual(loaded["generation_id"], "newer")

    def test_legacy_file_recovery(self):
        manager.TAILORED_RESUME_DIR.mkdir(parents=True)
        older = (
            manager.TAILORED_RESUME_DIR
            / "app_10_tailored_resume_20260101_000000.docx"
        )
        newer = (
            manager.TAILORED_RESUME_DIR
            / "app_10_tailored_resume_20260102_000000.docx"
        )
        older.write_bytes(b"old")
        newer.write_bytes(b"new")

        # Deliberately make the older filename newer by filesystem mtime.
        # Recovery must follow the generated filename timestamp.
        import os
        older_mtime = 1_700_000_060
        newer_mtime = 1_700_000_000
        os.utime(older, (older_mtime, older_mtime))
        os.utime(newer, (newer_mtime, newer_mtime))

        recovered = manager.get_restorable_application_tailoring(10)
        self.assertEqual(recovered["docx_path"], str(newer))
        self.assertTrue(
            recovered["fit_result"]["restored_from_legacy_files"]
        )

    def test_missing_stored_path_uses_legacy_file(self):
        missing = Path(self.temp_dir.name) / "missing.docx"
        manager.save_application_tailoring_generation(
            application_id=11,
            generation_id="gen-a",
            projects={"marker": "structured"},
            docx_path=missing,
        )
        manager.TAILORED_RESUME_DIR.mkdir(parents=True)
        legacy = (
            manager.TAILORED_RESUME_DIR
            / "app_11_tailored_resume_legacy.docx"
        )
        legacy.write_bytes(b"legacy")

        loaded = manager.get_restorable_application_tailoring(11)
        self.assertEqual(loaded["docx_path"], str(legacy))
        self.assertEqual(loaded["projects"]["marker"], "structured")

    def test_delete_application_generations(self):
        manager.save_application_tailoring_generation(
            application_id=12,
            generation_id="one",
            projects={},
        )
        manager.save_application_tailoring_generation(
            application_id=12,
            generation_id="two",
            projects={},
        )
        deleted = manager.delete_application_tailoring_generations(12)
        self.assertEqual(deleted, 2)
        self.assertIsNone(manager.get_latest_application_tailoring(12))


if __name__ == "__main__":
    unittest.main()

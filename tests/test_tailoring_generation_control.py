from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from database import tailoring_version_manager as base
from database import tailoring_generation_control as control


class TailoringGenerationControlTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db = base.DB_PATH
        base.DB_PATH = Path(self.temp_dir.name) / "applications.db"

    def tearDown(self):
        base.DB_PATH = self.old_db
        self.temp_dir.cleanup()

    def save_generation(self, application_id: int, generation_id: str):
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
                    {"category": "Languages", "items": ["Python"]}
                ]
            },
        )

    def test_persistent_fingerprint_cache_round_trip(self):
        self.save_generation(1, "gen-a")
        control.record_generation_metadata(
            application_id=1,
            generation_id="gen-a",
            input_fingerprint="fingerprint-a",
            generation_kind="projects_skills",
        )
        cached = control.find_cached_tailoring_generation(
            application_id=1,
            input_fingerprint="fingerprint-a",
            generation_kind="projects_skills",
        )
        self.assertEqual(cached["generation_id"], "gen-a")
        self.assertEqual(cached["status"], "draft")

    def test_blank_metadata_update_preserves_generation_kind(self):
        self.save_generation(13, "gen-a")
        control.record_generation_metadata(
            application_id=13,
            generation_id="gen-a",
            input_fingerprint="fingerprint-a",
            generation_kind="projects_skills",
        )
        control.record_generation_metadata(
            application_id=13,
            generation_id="gen-a",
        )
        state = control.get_tailoring_generation(13, "gen-a")
        self.assertEqual(state["generation_kind"], "projects_skills")
        self.assertEqual(state["input_fingerprint"], "fingerprint-a")

    def test_approving_new_generation_archives_previous(self):
        self.save_generation(2, "gen-a")
        self.save_generation(2, "gen-b")
        for value in ("gen-a", "gen-b"):
            control.record_generation_metadata(
                application_id=2,
                generation_id=value,
            )
        control.approve_tailoring_generation(2, "gen-a")
        control.set_tailoring_section_locks(
            application_id=2,
            lock_projects=True,
            lock_skills=True,
        )
        control.approve_tailoring_generation(2, "gen-b")

        old = control.get_tailoring_generation(2, "gen-a")
        new = control.get_tailoring_generation(2, "gen-b")
        state = control.get_application_generation_control(2)
        self.assertEqual(old["status"], "archived")
        self.assertEqual(new["status"], "approved")
        self.assertFalse(state["lock_projects"])
        self.assertFalse(state["lock_skills"])

    def test_archived_generation_is_not_used_as_cache_hit(self):
        self.save_generation(14, "gen-a")
        control.record_generation_metadata(
            application_id=14,
            generation_id="gen-a",
            input_fingerprint="fingerprint-a",
            generation_kind="projects_skills",
        )
        control.archive_tailoring_generation(14, "gen-a")
        cached = control.find_cached_tailoring_generation(
            application_id=14,
            input_fingerprint="fingerprint-a",
            generation_kind="projects_skills",
        )
        self.assertIsNone(cached)

    def test_locks_require_approved_generation(self):
        self.save_generation(3, "gen-a")
        control.record_generation_metadata(
            application_id=3,
            generation_id="gen-a",
        )
        with self.assertRaises(ValueError):
            control.set_tailoring_section_locks(
                application_id=3,
                lock_projects=True,
                lock_skills=False,
            )

    def test_restore_approved_generation_creates_new_draft(self):
        self.save_generation(4, "gen-a")
        control.record_generation_metadata(
            application_id=4,
            generation_id="gen-a",
            input_fingerprint="fingerprint-a",
        )
        control.approve_tailoring_generation(4, "gen-a")
        restored = control.restore_tailoring_generation_as_draft(
            application_id=4,
            source_generation_id="gen-a",
            new_generation_id="gen-restored",
        )
        self.assertEqual(restored["status"], "draft")
        self.assertEqual(
            restored["restored_from_generation_id"],
            "gen-a",
        )
        self.assertEqual(
            restored["projects"]["recommended_projects"][0]["title"],
            "gen-a",
        )

    def test_delete_application_generation_control(self):
        self.save_generation(6, "gen-a")
        control.record_generation_metadata(
            application_id=6,
            generation_id="gen-a",
        )
        control.approve_tailoring_generation(6, "gen-a")
        result = control.delete_application_generation_control(6)
        self.assertEqual(result["metadata_deleted"], 1)
        self.assertEqual(result["preferences_deleted"], 1)
        self.assertEqual(
            control.get_application_generation_control(6)[
                "approved_generation_id"
            ],
            "",
        )

    def test_ensure_mutable_clones_approved_generation(self):
        self.save_generation(5, "gen-a")
        control.record_generation_metadata(
            application_id=5,
            generation_id="gen-a",
        )
        control.approve_tailoring_generation(5, "gen-a")
        mutable = control.ensure_mutable_tailoring_generation(
            application_id=5,
            generation_id="gen-a",
        )
        self.assertNotEqual(mutable["generation_id"], "gen-a")
        self.assertEqual(mutable["status"], "draft")


if __name__ == "__main__":
    unittest.main()

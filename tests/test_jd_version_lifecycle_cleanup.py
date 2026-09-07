from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from database import jd_library_manager
from database.jd_library_manager import (
    archive_job_description_version,
    delete_unlinked_saved_job_description,
    get_exact_job_description_for_application,
    get_exact_job_description_version,
    get_jd_library_cleanup_preview,
    get_job_description_by_id,
    get_job_description_versions,
    init_jd_library,
    purge_unreferenced_archived_job_description_versions,
    restore_job_description_version,
    save_job_description_to_library,
)


class JDVersionLifecycleCleanupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.previous_db_path = jd_library_manager.DB_PATH
        jd_library_manager.DB_PATH = (
            Path(self.temporary.name) / "applications.db"
        )
        init_jd_library()

        profile = {
            "job_title": "Software Engineer",
            "company": "Example Company",
            "location": "",
            "required_skills": ["Modern C++"],
            "preferred_skills": [],
            "tools_technologies": ["C++"],
        }
        self.old = save_job_description_to_library(
            raw_text=(
                "Software Engineer\n"
                "Required: modern C++.\n"
                "Preferred: linear algebra."
            ),
            jd_profile=profile,
            title="Software Engineer",
            company="Example Company",
        )
        self.fresh = save_job_description_to_library(
            raw_text=(
                "Software Engineer\n"
                "Required: modern C++.\n"
                "Preferred: linear algebra, Vulkan, and CUDA."
            ),
            jd_profile=profile,
            title="Software Engineer",
            company="Example Company",
        )
        self.jd_id = int(self.fresh["job_description_id"])
        self.old_version = str(self.old["source_version_id"])
        self.fresh_version = str(self.fresh["source_version_id"])

    def tearDown(self) -> None:
        jd_library_manager.DB_PATH = self.previous_db_path
        self.temporary.cleanup()

    def _link(self, application_id: int, source_version_id: str) -> None:
        connection = jd_library_manager._connect()
        try:
            connection.execute(
                """
                INSERT INTO application_job_links (
                    application_id,
                    job_description_id,
                    source_version_id,
                    linked_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    int(application_id),
                    self.jd_id,
                    str(source_version_id),
                    "2026-09-02T00:00:00",
                    "2026-09-02T00:00:00",
                ),
            )
            connection.commit()
        finally:
            connection.close()

    def test_archive_hides_normal_picker_and_exact_history_survives(self):
        archived = archive_job_description_version(
            self.jd_id,
            self.old_version,
            reason="Superseded by fresh analysis.",
        )
        self.assertEqual(archived["status"], "archived")
        self.assertFalse(archived["needs_chroma_reindex"])

        visible_ids = {
            row["source_version_id"]
            for row in get_job_description_versions(self.jd_id)
        }
        self.assertNotIn(self.old_version, visible_ids)
        self.assertIn(self.fresh_version, visible_ids)

        all_versions = get_job_description_versions(
            self.jd_id,
            include_archived=True,
        )
        archived_row = next(
            row
            for row in all_versions
            if row["source_version_id"] == self.old_version
        )
        self.assertTrue(archived_row["is_archived"])

        exact = get_exact_job_description_version(
            self.jd_id,
            self.old_version,
        )
        self.assertIsNotNone(exact)
        self.assertEqual(exact["source_version_id"], self.old_version)

    def test_archive_current_promotes_an_available_version(self):
        result = archive_job_description_version(
            self.jd_id,
            self.fresh_version,
        )
        self.assertTrue(result["needs_chroma_reindex"])
        self.assertEqual(
            result["promoted_source_version_id"],
            self.old_version,
        )
        current = get_job_description_by_id(self.jd_id)
        self.assertEqual(
            current["source_version_id"],
            self.old_version,
        )

    def test_archived_linked_version_is_protected_from_purge(self):
        self._link(9876, self.old_version)
        archive_job_description_version(
            self.jd_id,
            self.old_version,
        )

        preview = get_jd_library_cleanup_preview()
        self.assertEqual(
            preview["protected_archived_version_count"],
            1,
        )
        self.assertEqual(
            preview["purgeable_archived_version_count"],
            0,
        )

        purged = (
            purge_unreferenced_archived_job_description_versions()
        )
        self.assertEqual(purged["purged_version_count"], 0)

        historical = get_exact_job_description_for_application(9876)
        self.assertIsNotNone(historical)
        self.assertEqual(
            historical["source_version_id"],
            self.old_version,
        )

    def test_unreferenced_archived_version_can_be_purged(self):
        archive_job_description_version(
            self.jd_id,
            self.old_version,
        )
        purged = (
            purge_unreferenced_archived_job_description_versions()
        )
        self.assertEqual(purged["purged_version_count"], 1)
        self.assertIsNone(
            get_exact_job_description_version(
                self.jd_id,
                self.old_version,
            )
        )

    def test_restore_returns_version_to_normal_picker(self):
        archive_job_description_version(
            self.jd_id,
            self.old_version,
        )
        restored = restore_job_description_version(
            self.jd_id,
            self.old_version,
        )
        self.assertEqual(restored["status"], "restored")
        visible_ids = {
            row["source_version_id"]
            for row in get_job_description_versions(self.jd_id)
        }
        self.assertIn(self.old_version, visible_ids)

    def test_last_available_version_cannot_be_archived(self):
        archive_job_description_version(
            self.jd_id,
            self.old_version,
        )
        with self.assertRaisesRegex(ValueError, "last available"):
            archive_job_description_version(
                self.jd_id,
                self.fresh_version,
            )

    def test_unlinked_saved_jd_can_be_deleted_but_linked_one_cannot(self):
        preview = get_jd_library_cleanup_preview()
        ids = {
            int(row["job_description_id"])
            for row in preview["unlinked_saved_jobs"]
        }
        self.assertIn(self.jd_id, ids)

        self._link(4321, self.fresh_version)
        with self.assertRaisesRegex(ValueError, "still referenced"):
            delete_unlinked_saved_job_description(self.jd_id)

        connection = jd_library_manager._connect()
        try:
            connection.execute(
                "DELETE FROM application_job_links WHERE application_id = ?",
                (4321,),
            )
            connection.commit()
        finally:
            connection.close()

        deleted = delete_unlinked_saved_job_description(self.jd_id)
        self.assertEqual(deleted["status"], "deleted")
        self.assertIsNone(get_job_description_by_id(self.jd_id))


if __name__ == "__main__":
    unittest.main()

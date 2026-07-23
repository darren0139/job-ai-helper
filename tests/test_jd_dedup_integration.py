from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from database import jd_library_manager as manager


class JDDedupIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = manager.DB_PATH
        manager.DB_PATH = Path(self.temp_dir.name) / "applications.db"
        manager.init_jd_library()

    def tearDown(self) -> None:
        manager.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    @staticmethod
    def profile(*, title: str = "Software Engineer", company: str = "Example", location: str = "Singapore") -> dict:
        return {
            "job_title": title,
            "company": company,
            "location": location,
            "required_skills": ["Python", "REST APIs"],
            "tools_technologies": ["Docker"],
        }

    def test_same_jd_in_two_sessions_is_stored_once(self) -> None:
        text = "Build Python APIs and containerise services with Docker."
        first = manager.save_or_link_job_description_for_application(
            application_id=1,
            raw_text=text,
            jd_profile=self.profile(),
        )
        second = manager.save_or_link_job_description_for_application(
            application_id=2,
            raw_text=text,
            jd_profile=self.profile(),
        )

        self.assertEqual(first["job_description_id"], second["job_description_id"])
        self.assertTrue(first["needs_chroma_index"])
        self.assertFalse(second["needs_chroma_index"])
        self.assertEqual(
            manager.get_jd_library_stats(),
            {"canonical_jobs": 1, "versions": 1, "session_links": 2},
        )

    def test_revised_text_creates_version_but_not_new_canonical_job(self) -> None:
        first = manager.save_or_link_job_description_for_application(
            application_id=1,
            raw_text="Build Python APIs.",
            jd_profile=self.profile(),
        )
        revised = manager.save_or_link_job_description_for_application(
            application_id=2,
            raw_text="Build Python APIs and deploy them with Docker.",
            jd_profile=self.profile(),
        )

        self.assertEqual(first["job_description_id"], revised["job_description_id"])
        self.assertTrue(revised["created_new_version"])
        self.assertTrue(revised["needs_chroma_index"])
        self.assertEqual(
            manager.get_jd_library_stats(),
            {"canonical_jobs": 1, "versions": 2, "session_links": 2},
        )

    def test_different_title_creates_new_canonical_job(self) -> None:
        manager.save_or_link_job_description_for_application(
            application_id=1,
            raw_text="Build APIs.",
            jd_profile=self.profile(title="Software Engineer"),
        )
        manager.save_or_link_job_description_for_application(
            application_id=2,
            raw_text="Operate Kubernetes clusters.",
            jd_profile=self.profile(title="Cloud Engineer"),
        )
        self.assertEqual(manager.get_jd_library_stats()["canonical_jobs"], 2)

    def test_unlink_keeps_shared_jd_until_last_session_is_deleted(self) -> None:
        text = "Build Python APIs."
        manager.save_or_link_job_description_for_application(
            application_id=1,
            raw_text=text,
            jd_profile=self.profile(),
        )
        manager.save_or_link_job_description_for_application(
            application_id=2,
            raw_text=text,
            jd_profile=self.profile(),
        )

        first_unlink = manager.unlink_job_description_from_application(1)
        self.assertFalse(first_unlink["deleted_canonical_job"])
        self.assertEqual(first_unlink["remaining_link_count"], 1)
        self.assertEqual(manager.get_jd_library_stats()["canonical_jobs"], 1)

        second_unlink = manager.unlink_job_description_from_application(2)
        self.assertTrue(second_unlink["deleted_canonical_job"])
        self.assertEqual(manager.get_jd_library_stats()["canonical_jobs"], 0)

    def test_reanalysing_session_with_different_job_removes_old_orphan(self) -> None:
        old = manager.save_or_link_job_description_for_application(
            application_id=1,
            raw_text="Build APIs.",
            jd_profile=self.profile(title="Software Engineer"),
        )
        new = manager.save_or_link_job_description_for_application(
            application_id=1,
            raw_text="Operate Kubernetes clusters.",
            jd_profile=self.profile(title="Cloud Engineer"),
        )

        self.assertNotEqual(old["job_description_id"], new["job_description_id"])
        self.assertEqual(new["orphaned_job_description_id"], old["job_description_id"])
        self.assertEqual(manager.get_jd_library_stats()["canonical_jobs"], 1)

    def test_legacy_duplicate_rows_are_merged_during_init(self) -> None:
        # Recreate a minimal legacy table directly.
        manager.DB_PATH.unlink(missing_ok=True)
        connection = sqlite3.connect(manager.DB_PATH)
        connection.execute(
            """
            CREATE TABLE job_descriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                application_id INTEGER,
                title TEXT,
                company TEXT,
                source_type TEXT,
                source_url TEXT,
                raw_text TEXT,
                jd_profile_json TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        profile_json = '{"job_title":"Software Engineer","company":"Example","location":"Singapore"}'
        for application_id in (1, 2):
            connection.execute(
                """
                INSERT INTO job_descriptions (
                    application_id, title, company, source_type, source_url,
                    raw_text, jd_profile_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    application_id,
                    "Software Engineer",
                    "Example",
                    "application_session",
                    "",
                    "Build Python APIs.",
                    profile_json,
                    "2026-01-01T00:00:00",
                    "2026-01-01T00:00:00",
                ),
            )
        connection.commit()
        connection.close()

        manager.init_jd_library()
        self.assertEqual(
            manager.get_jd_library_stats(),
            {"canonical_jobs": 1, "versions": 1, "session_links": 2},
        )


if __name__ == "__main__":
    unittest.main()

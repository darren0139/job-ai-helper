from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import database.jd_library_manager as jd_library_manager


class OptionalCompanyJDIdentityPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        self._original_db_path = jd_library_manager.DB_PATH
        jd_library_manager.DB_PATH = (
            Path(self._temporary_directory.name) / "applications.db"
        )
        jd_library_manager.init_jd_library()

    def tearDown(self) -> None:
        jd_library_manager.DB_PATH = self._original_db_path
        self._temporary_directory.cleanup()

    def _stored_version_profile(self) -> dict:
        connection = sqlite3.connect(jd_library_manager.DB_PATH)
        try:
            row = connection.execute(
                """
                SELECT jd_profile_json
                FROM job_description_versions
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()
        finally:
            connection.close()
        self.assertIsNotNone(row)
        return json.loads(str(row[0] or "{}"))

    def test_missing_company_uses_fallback_in_persisted_version_profile(self) -> None:
        raw_text = (
            "Software Engineer\n"
            "Required Skills\n"
            "- Strong modern C++ programming experience.\n"
        )
        profile = {
            "job_title": "Software Engineer",
            "company": "",
            "required_skills": [
                "Strong modern C++ programming experience",
            ],
        }

        jd_library_manager.save_or_link_job_description_for_application(
            application_id=132,
            raw_text=raw_text,
            jd_profile=profile,
        )

        stored_profile = self._stored_version_profile()
        self.assertEqual(stored_profile["job_title"], "Software Engineer")
        self.assertEqual(stored_profile["company"], "Unknown Company")

        snapshot = (
            jd_library_manager.get_exact_job_description_for_application(132)
        )
        self.assertIsNotNone(snapshot)

    def test_init_repairs_legacy_version_missing_company_identity(self) -> None:
        raw_text = (
            "Software Engineer\n"
            "Required Skills\n"
            "- Strong modern C++ programming experience.\n"
        )
        profile = {
            "job_title": "Software Engineer",
            "company": "",
            "required_skills": [
                "Strong modern C++ programming experience",
            ],
        }

        jd_library_manager.save_or_link_job_description_for_application(
            application_id=133,
            raw_text=raw_text,
            jd_profile=profile,
        )

        broken_profile = dict(self._stored_version_profile())
        broken_profile["company"] = ""
        connection = sqlite3.connect(jd_library_manager.DB_PATH)
        try:
            connection.execute(
                """
                UPDATE job_description_versions
                SET jd_profile_json = ?
                """,
                (json.dumps(broken_profile),),
            )
            connection.commit()
        finally:
            connection.close()

        with self.assertRaisesRegex(
            ValueError,
            "lacks title/company identity",
        ):
            jd_library_manager.get_exact_job_description_for_application(133)

        jd_library_manager.init_jd_library()

        repaired_profile = self._stored_version_profile()
        self.assertEqual(repaired_profile["company"], "Unknown Company")
        self.assertEqual(
            repaired_profile["required_skills"],
            ["Strong modern C++ programming experience"],
        )
        snapshot = (
            jd_library_manager.get_exact_job_description_for_application(133)
        )
        self.assertIsNotNone(snapshot)


if __name__ == "__main__":
    unittest.main()

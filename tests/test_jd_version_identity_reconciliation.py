from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from database import jd_library_manager
from database.jd_library_manager import (
    init_jd_library,
    save_job_description_to_library,
)


class JDVersionIdentityReconciliationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.previous_db_path = jd_library_manager.DB_PATH
        jd_library_manager.DB_PATH = (
            Path(self.temporary.name) / "applications.db"
        )
        init_jd_library()

    def tearDown(self) -> None:
        jd_library_manager.DB_PATH = self.previous_db_path
        self.temporary.cleanup()

    def test_init_repairs_stale_nonempty_version_identity_only(self) -> None:
        profile = {
            "job_title": "Software Engineer",
            "company": "Example Company",
            "location": "London",
            "required_skills": ["Modern C++"],
            "preferred_skills": ["Vulkan"],
            "tools_technologies": ["C++"],
        }
        saved = save_job_description_to_library(
            raw_text=(
                "Software Engineer\n"
                "Location: London\n"
                "Required: modern C++.\n"
                "Preferred: Vulkan."
            ),
            jd_profile=profile,
            title="Software Engineer",
            company="Example Company",
        )
        jd_id = int(saved["job_description_id"])
        version_id = str(saved["source_version_id"])

        stale_profile = dict(profile)
        stale_profile["job_title"] = "Senior Software Engineer"
        stale_profile["company"] = "Stale Example Company"
        stale_profile["location"] = "Manchester"

        connection = jd_library_manager._connect()
        try:
            connection.execute(
                "UPDATE job_description_versions "
                "SET jd_profile_json = ? "
                "WHERE job_description_id = ? AND source_version_id = ?",
                (
                    json.dumps(stale_profile, ensure_ascii=False),
                    jd_id,
                    version_id,
                ),
            )
            connection.commit()
        finally:
            connection.close()

        init_jd_library()

        connection = jd_library_manager._connect()
        try:
            row = connection.execute(
                "SELECT jd_profile_json "
                "FROM job_description_versions "
                "WHERE job_description_id = ? AND source_version_id = ? "
                "LIMIT 1",
                (jd_id, version_id),
            ).fetchone()
            link_count = int(
                connection.execute(
                    "SELECT COUNT(*) AS count "
                    "FROM application_job_links "
                    "WHERE job_description_id = ?",
                    (jd_id,),
                ).fetchone()["count"]
            )
        finally:
            connection.close()

        self.assertIsNotNone(row)
        repaired = json.loads(str(row["jd_profile_json"]))

        self.assertEqual(repaired["job_title"], "Software Engineer")
        self.assertEqual(repaired["company"], "Example Company")
        self.assertEqual(repaired["location"], "London")
        self.assertEqual(repaired["required_skills"], ["Modern C++"])
        self.assertEqual(repaired["preferred_skills"], ["Vulkan"])
        self.assertEqual(repaired["tools_technologies"], ["C++"])
        self.assertEqual(link_count, 0)


if __name__ == "__main__":
    unittest.main()

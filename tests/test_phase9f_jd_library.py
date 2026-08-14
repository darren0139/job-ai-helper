from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from database import jd_library_manager as manager
from tailoring.phase9f_jd_intake import build_saved_exact_jd_snapshot


def profile(title: str, company: str) -> dict:
    return {
        "job_title": title,
        "company": company,
        "location": "Singapore",
        "experience_level": "Junior",
        "responsibilities": ["Build and maintain reliable software services."],
        "required_skills": ["Python", "REST APIs"],
        "preferred_skills": ["Docker"],
        "tools_technologies": ["Python", "Docker"],
        "soft_skills": ["Collaboration"],
        "buzzwords": [],
        "deal_breakers": [],
    }


class Phase9FJDLibraryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.original_path = manager.DB_PATH
        manager.DB_PATH = Path(self.temporary.name) / "jd-library.sqlite"
        manager.init_jd_library()

    def tearDown(self) -> None:
        manager.DB_PATH = self.original_path
        self.temporary.cleanup()

    def test_multiple_standalone_jds_need_no_application_links(self):
        first = manager.save_job_description_to_library(
            raw_text=(
                "Junior Software Engineer. Build Python REST APIs and test "
                "reliable services with a collaborative engineering team."
            ),
            jd_profile=profile("Junior Software Engineer", "Company A"),
        )
        second = manager.save_job_description_to_library(
            raw_text=(
                "Backend Engineer. Build cloud services with Python, Docker, "
                "PostgreSQL, observability, and secure API access controls."
            ),
            jd_profile=profile("Backend Engineer", "Company B"),
        )
        self.assertNotEqual(
            first["job_description_id"], second["job_description_id"]
        )
        self.assertEqual(
            manager.get_jd_library_stats(),
            {"canonical_jobs": 2, "versions": 2, "session_links": 0},
        )
        self.assertEqual(manager.get_application_job_links(), [])
        self.assertEqual(len(manager.get_recent_job_descriptions()), 2)

    def test_identical_save_reuses_authoritative_row_and_version(self):
        raw = (
            "Junior Software Engineer. Build Python REST APIs and test reliable "
            "services with a collaborative engineering team."
        )
        first = manager.save_job_description_to_library(
            raw_text=raw,
            jd_profile=profile("Junior Software Engineer", "Company A"),
        )
        second = manager.save_job_description_to_library(
            raw_text=raw,
            jd_profile=profile("Junior Software Engineer", "Company A"),
        )
        self.assertEqual(first["job_description_id"], second["job_description_id"])
        self.assertEqual(first["source_version_id"], second["source_version_id"])
        self.assertFalse(second["created_new_job"])
        self.assertFalse(second["created_new_version"])
        self.assertFalse(second["needs_chroma_index"])

    def test_exact_saved_version_rebuilds_without_model_provenance(self):
        saved = manager.save_job_description_to_library(
            raw_text=(
                "AI Full-Stack Engineer. Build Python and React applications "
                "with PostgreSQL, authentication, tests, and secure deployment."
            ),
            jd_profile=profile("AI Full-Stack Engineer", "Company A"),
        )
        exact = manager.get_exact_job_description_version(
            saved["job_description_id"], saved["source_version_id"]
        )
        self.assertIsNotNone(exact)
        snapshot = build_saved_exact_jd_snapshot(exact or {})
        self.assertEqual(snapshot["source_type"], "saved")
        self.assertEqual(snapshot["model_call_count"], 0)
        self.assertEqual(snapshot["embedding_call_count"], 0)
        self.assertEqual(
            snapshot["canonical_requirement_fingerprint"],
            exact["canonical_requirement_fingerprint"],
        )
        self.assertIsNone(
            manager.get_exact_job_description_version(
                saved["job_description_id"], "not-an-exact-version"
            )
        )

    def test_explicitly_saved_jd_survives_last_application_unlink(self):
        raw = (
            "Junior Software Engineer. Build Python REST APIs and test reliable "
            "services with a collaborative engineering team."
        )
        saved = manager.save_job_description_to_library(
            raw_text=raw,
            jd_profile=profile("Junior Software Engineer", "Company A"),
        )
        manager.save_or_link_job_description_for_application(
            application_id=91,
            raw_text=raw,
            jd_profile=profile("Junior Software Engineer", "Company A"),
        )
        result = manager.unlink_job_description_from_application(91)
        self.assertFalse(result["deleted_canonical_job"])
        self.assertEqual(result["remaining_link_count"], 0)
        self.assertIsNotNone(
            manager.get_job_description_by_id(saved["job_description_id"])
        )

    def test_ambiguous_identity_is_not_saved(self):
        with self.assertRaisesRegex(ValueError, "job title and company"):
            manager.save_job_description_to_library(
                raw_text=(
                    "Build Python REST APIs and test reliable services with a "
                    "collaborative engineering team."
                ),
                jd_profile={"required_skills": ["Python"]},
            )


if __name__ == "__main__":
    unittest.main()

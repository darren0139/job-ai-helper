from __future__ import annotations

import unittest

from rag.jd_identity import (
    build_job_identity,
    canonical_job_id,
    is_probable_near_duplicate,
    source_version_id,
)


class JobIdentityTests(unittest.TestCase):
    def test_same_job_identity_ignores_case_and_spacing(self) -> None:
        first = canonical_job_id(
            company="Garena",
            title="Associate, Configuration & QA",
            location="Singapore",
        )
        second = canonical_job_id(
            company="  GARENA ",
            title="associate configuration qa",
            location="singapore",
        )
        self.assertEqual(first, second)

    def test_source_version_changes_when_content_changes(self) -> None:
        self.assertNotEqual(
            source_version_id("Quality assurance and live operations"),
            source_version_id("Quality assurance and configuration"),
        )

    def test_near_duplicate_same_role_and_similar_text(self) -> None:
        base = (
            "Operate and maintain daily gaming product operations. "
            "Coordinate configuration and QA tasks between offices. "
            "Collaborate with local and global stakeholders."
        )
        revised = (
            "Operate and maintain the daily gaming-product operations. "
            "Coordinate QA and configuration tasks between offices. "
            "Collaborate with local and global stakeholders."
        )
        self.assertTrue(
            is_probable_near_duplicate(
                existing_company="Garena",
                existing_title="Associate Configuration QA",
                existing_location="Singapore",
                existing_text=base,
                candidate_company="Garena",
                candidate_title="Associate Configuration QA",
                candidate_location="Singapore",
                candidate_text=revised,
                minimum_text_similarity=0.55,
            )
        )

    def test_different_company_is_not_duplicate(self) -> None:
        self.assertFalse(
            is_probable_near_duplicate(
                existing_company="Garena",
                existing_title="QA Engineer",
                existing_location="Singapore",
                existing_text="Test games and handle defects",
                candidate_company="Another Company",
                candidate_title="QA Engineer",
                candidate_location="Singapore",
                candidate_text="Test games and handle defects",
            )
        )

    def test_build_identity_has_canonical_and_version_ids(self) -> None:
        identity = build_job_identity(
            company="Garena",
            title="QA",
            location="Singapore",
            raw_jd_text="Test games.",
        )
        self.assertTrue(identity.canonical_jd_id.startswith("jd_"))
        self.assertTrue(identity.source_version_id.startswith("jdv_"))


if __name__ == "__main__":
    unittest.main()

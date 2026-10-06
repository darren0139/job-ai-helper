from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

import database.job_match_manager as manager
from job_discovery.matching import inspect_job_match, inspect_job_matches


class BatchedJobMatchInspectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_db_path = manager.DB_PATH
        manager.DB_PATH = Path(self.tempdir.name) / "applications.db"
        manager.init_job_match_schema()

        self.context = {
            "evidence_fingerprint": "candidate-a",
            "evidence_item_count": 1,
        }
        self.versions = {
            "match_version": "match-v1",
            "scoring_version": "score-v1",
            "taxonomy_version": "tax-v1",
            "technology_registry_version": "",
        }
        self.jobs = [
            {"id": 1, "content_hash": "hash-a", "description": "A" * 120},
            {"id": 2, "content_hash": "hash-b-new", "description": "B" * 120},
            {"id": 3, "content_hash": "hash-c", "description": "C" * 120},
        ]

        manager.save_job_match_snapshot(
            discovered_job_id=1,
            job_content_hash="hash-a",
            evidence_fingerprint="candidate-a",
            match_version="match-v1",
            scoring_version="score-v1",
            taxonomy_version="tax-v1",
            jd_profile={"required_skills": ["Python"]},
            evidence_snapshot=[],
            stable_analysis={},
            summary={"ranking_eligible": True},
        )
        manager.save_job_match_snapshot(
            discovered_job_id=2,
            job_content_hash="hash-b-old",
            evidence_fingerprint="candidate-a",
            match_version="match-v1",
            scoring_version="score-v1",
            taxonomy_version="tax-v1",
            jd_profile={"required_skills": ["Python"]},
            evidence_snapshot=[],
            stable_analysis={},
            summary={"ranking_eligible": True},
        )

    def tearDown(self) -> None:
        manager.DB_PATH = self.original_db_path
        self.tempdir.cleanup()

    def test_batch_matches_single_job_inspector(self) -> None:
        batch = inspect_job_matches(
            self.jobs,
            context=self.context,
            versions=self.versions,
        )
        self.assertEqual(set(batch), {1, 2, 3})

        for job in self.jobs:
            single = inspect_job_match(
                job,
                context=self.context,
                versions=self.versions,
            )
            multi = batch[int(job["id"])]
            self.assertEqual(multi["status"], single["status"])
            self.assertEqual(
                multi.get("stale_reasons"),
                single.get("stale_reasons"),
            )

    def test_changed_job_is_stale(self) -> None:
        batch = inspect_job_matches(
            self.jobs,
            context=self.context,
            versions=self.versions,
        )
        self.assertEqual(batch[2]["status"], "stale")
        self.assertIn(
            "job description changed",
            batch[2]["stale_reasons"],
        )

    def test_unseen_job_is_none(self) -> None:
        batch = inspect_job_matches(
            self.jobs,
            context=self.context,
            versions=self.versions,
        )
        self.assertEqual(batch[3]["status"], "none")


if __name__ == "__main__":
    unittest.main()

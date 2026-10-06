from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

import database.job_match_manager as manager


class LightweightJobMatchStateQueryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_db_path = manager.DB_PATH
        manager.DB_PATH = Path(self.tempdir.name) / "applications.db"
        manager.init_job_match_schema()

        for job_id in (1, 2, 3):
            manager.save_job_match_snapshot(
                discovered_job_id=job_id,
                job_content_hash=f"hash-{job_id}",
                evidence_fingerprint="candidate-a",
                match_version="match-v1",
                scoring_version="score-v1",
                taxonomy_version="tax-v1",
                jd_profile={"required_skills": ["Python"]},
                evidence_snapshot=[{"id": 1}],
                stable_analysis={
                    "canonical_requirements": [
                        {"requirement_id": "req-1"}
                    ]
                },
                summary={
                    "ranking_eligible": True,
                    "deterministic_alignment_score": job_id * 10,
                },
            )

    def tearDown(self) -> None:
        manager.DB_PATH = self.original_db_path
        self.tempdir.cleanup()

    def test_current_state_rows_are_id_scoped_and_lightweight(self) -> None:
        rows = manager.list_current_job_match_state_rows(
            [1, 3],
            evidence_fingerprint="candidate-a",
            match_version="match-v1",
            scoring_version="score-v1",
            taxonomy_version="tax-v1",
        )
        self.assertEqual(
            [int(row["discovered_job_id"]) for row in rows],
            [1, 3],
        )
        for row in rows:
            self.assertIn("summary", row)
            self.assertNotIn("stable_analysis", row)
            self.assertNotIn("evidence_snapshot", row)
            self.assertNotIn("jd_profile", row)

    def test_latest_state_rows_are_id_scoped(self) -> None:
        rows = manager.list_latest_job_match_state_rows([2])
        self.assertEqual(len(rows), 1)
        self.assertEqual(int(rows[0]["discovered_job_id"]), 2)


if __name__ == "__main__":
    unittest.main()

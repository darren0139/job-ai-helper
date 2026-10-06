from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

import database.job_match_manager as manager
from job_discovery.match_ranking import (
    MIN_IMPORTANT_TAXONOMY_COVERAGE,
    RANKING_VERSION,
    best_match_sort_key,
    build_ranking_quality,
)


def _row(importance: str, resolved: bool) -> dict:
    return {
        "requirement_id": f"req_{importance}_{resolved}",
        "importance": importance,
        "status": "resolved" if resolved else "unresolved",
    }


class JobMatchRankingQualityTests(unittest.TestCase):
    def test_good_taxonomy_coverage_is_eligible(self):
        quality = build_ranking_quality({
            "rows": [
                _row("required", True),
                _row("required", True),
                _row("core", True),
                _row("core", True),
                _row("preferred", False),
            ]
        })
        self.assertTrue(quality["ranking_eligible"])
        self.assertEqual(quality["ranking_version"], RANKING_VERSION)

    def test_low_important_coverage_blocks_ranking(self):
        quality = build_ranking_quality({
            "rows": [
                _row("required", True),
                _row("required", False),
                _row("core", False),
                _row("preferred", True),
                _row("preferred", True),
            ]
        })
        self.assertFalse(quality["ranking_eligible"])
        self.assertIn(
            "insufficient_important_taxonomy_coverage",
            quality["ranking_ineligible_reasons"],
        )
        self.assertLess(
            quality["important_taxonomy_coverage"],
            MIN_IMPORTANT_TAXONOMY_COVERAGE,
        )

    def test_too_few_requirements_blocks_ranking(self):
        quality = build_ranking_quality({
            "rows": [
                _row("required", True),
                _row("preferred", True),
            ]
        })
        self.assertFalse(quality["ranking_eligible"])
        self.assertEqual(
            quality["ranking_status"],
            "insufficient_requirement_count",
        )

    def test_no_important_rows_uses_overall_gate(self):
        quality = build_ranking_quality({
            "rows": [
                _row("preferred", True),
                _row("preferred", True),
                _row("preferred", True),
            ]
        })
        self.assertTrue(quality["ranking_eligible"])
        self.assertEqual(quality["important_taxonomy_coverage"], 1.0)

    def test_eligible_ranks_above_ineligible_and_unanalyzed(self):
        eligible = {
            "summary": {
                "ranking_eligible": True,
                "deterministic_alignment_score": 70,
                "required_core_coverage_score": 80,
                "important_gap_count": 2,
                "direct_requirement_count": 4,
                "preferred_coverage_score": 50,
                "evidence_strength_score": 75,
                "important_taxonomy_coverage_pct": 90,
            }
        }
        ineligible = {
            "summary": {
                "ranking_eligible": False,
                "deterministic_alignment_score": 99,
                "important_taxonomy_coverage_pct": 30,
            }
        }
        a = best_match_sort_key(eligible, search_relevance=1)
        b = best_match_sort_key(ineligible, search_relevance=100)
        c = best_match_sort_key(None, search_relevance=100)
        self.assertGreater(a, b)
        self.assertGreater(b, c)

    def test_ineligible_raw_alignment_does_not_affect_order(self):
        low_raw = {
            "summary": {
                "ranking_eligible": False,
                "deterministic_alignment_score": 1,
                "important_taxonomy_coverage_pct": 60,
            }
        }
        high_raw = {
            "summary": {
                "ranking_eligible": False,
                "deterministic_alignment_score": 99,
                "important_taxonomy_coverage_pct": 60,
            }
        }
        self.assertEqual(
            best_match_sort_key(
                low_raw,
                search_relevance=20,
                freshness_timestamp=10,
                discovered_job_id=1,
            ),
            best_match_sort_key(
                high_raw,
                search_relevance=20,
                freshness_timestamp=10,
                discovered_job_id=1,
            ),
        )


class CurrentSnapshotBatchTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_db_path = manager.DB_PATH
        manager.DB_PATH = Path(self.tempdir.name) / "applications.db"
        manager.init_job_match_schema()

    def tearDown(self):
        manager.DB_PATH = self.original_db_path
        self.tempdir.cleanup()

    def _save(self, job_id: int, content_hash: str, evidence_fp: str):
        manager.save_job_match_snapshot(
            discovered_job_id=job_id,
            job_content_hash=content_hash,
            evidence_fingerprint=evidence_fp,
            match_version="match-v1",
            scoring_version="score-v1",
            taxonomy_version="tax-v1",
            jd_profile={"required_skills": ["Python"]},
            evidence_snapshot=[],
            stable_analysis={"canonical_requirements": []},
            summary={"ranking_eligible": True},
        )

    def test_batch_loader_is_scoped_to_candidate_identity(self):
        self._save(1, "hash-a", "candidate-a")
        self._save(1, "hash-b", "candidate-b")
        self._save(2, "hash-c", "candidate-a")
        rows = manager.list_current_job_match_snapshots(
            evidence_fingerprint="candidate-a",
            match_version="match-v1",
            scoring_version="score-v1",
            taxonomy_version="tax-v1",
        )
        self.assertEqual(
            {int(item["discovered_job_id"]) for item in rows},
            {1, 2},
        )


if __name__ == "__main__":
    unittest.main()

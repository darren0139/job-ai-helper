from __future__ import annotations

import unittest

from job_discovery.batch_matching import (
    classify_batch_jobs,
    job_is_analyzable,
    match_display_label,
    select_pending_batch_jobs,
)


def job(
    job_id: int,
    *,
    description: str = "X" * 120,
    content_hash: str = "hash",
) -> dict:
    return {
        "id": job_id,
        "description": description,
        "content_hash": content_hash,
    }


class MissingStaleBatchTests(unittest.TestCase):
    def test_current_jobs_are_never_pending(self) -> None:
        jobs = [job(1), job(2), job(3)]
        states = {
            1: {"status": "current", "snapshot": {"summary": {}}},
            2: {"status": "stale", "snapshot": None},
            3: {"status": "none", "snapshot": None},
        }
        result = classify_batch_jobs(jobs, states)
        self.assertEqual(result["current_count"], 1)
        self.assertEqual(result["stale_count"], 1)
        self.assertEqual(result["not_analyzed_count"], 1)
        self.assertEqual(
            [row["id"] for row in result["pending_jobs"]],
            [2, 3],
        )

    def test_not_analyzable_is_separate_from_not_analyzed(self) -> None:
        jobs = [
            job(1, description="short"),
            job(2, content_hash=""),
            job(3),
        ]
        result = classify_batch_jobs(jobs, {})
        self.assertEqual(result["not_analyzable_count"], 2)
        self.assertEqual(result["not_analyzed_count"], 1)
        self.assertEqual(
            [row["id"] for row in result["pending_jobs"]],
            [3],
        )

    def test_pending_selection_respects_limit_and_order(self) -> None:
        jobs = [job(1), job(2), job(3), job(4)]
        states = {
            1: {"status": "current"},
            2: {"status": "none"},
            3: {"status": "stale"},
            4: {"status": "none"},
        }
        selected = select_pending_batch_jobs(
            jobs,
            states,
            limit=2,
        )
        self.assertEqual(
            [row["id"] for row in selected],
            [2, 3],
        )

    def test_display_labels_hide_internal_taxonomy_status(self) -> None:
        eligible = {
            "status": "current",
            "snapshot": {
                "summary": {
                    "ranking_eligible": True,
                    "ranking_status": "eligible",
                }
            },
        }
        provisional = {
            "status": "current",
            "snapshot": {
                "summary": {
                    "ranking_eligible": False,
                    "ranking_status": "insufficient_taxonomy_coverage",
                }
            },
        }
        self.assertEqual(
            match_display_label(job(1), eligible),
            "Eligible",
        )
        self.assertEqual(
            match_display_label(job(2), provisional),
            "Provisional",
        )
        self.assertEqual(
            match_display_label(
                job(3, description="short"),
                {"status": "none"},
            ),
            "Not analyzable",
        )

    def test_job_is_analyzable_contract(self) -> None:
        self.assertTrue(job_is_analyzable(job(1)))
        self.assertFalse(job_is_analyzable(job(0)))
        self.assertFalse(job_is_analyzable(job(1, content_hash="")))
        self.assertFalse(job_is_analyzable(job(1, description="short")))


if __name__ == "__main__":
    unittest.main()

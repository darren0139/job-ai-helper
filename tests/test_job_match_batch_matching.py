from __future__ import annotations

import unittest

from job_discovery.batch_matching import select_batch_jobs


class JobMatchBatchSelectionTests(unittest.TestCase):
    def test_preserves_current_order_and_limit(self) -> None:
        jobs = [
            {"id": 3, "description": "A" * 120},
            {"id": 1, "description": "B" * 120},
            {"id": 2, "description": "C" * 120},
        ]
        selected = select_batch_jobs(jobs, limit=2)
        self.assertEqual([job["id"] for job in selected], [3, 1])

    def test_skips_invalid_short_and_duplicate_jobs(self) -> None:
        jobs = [
            {"id": 0, "description": "A" * 120},
            {"id": 1, "description": "short"},
            {"id": 2, "description": "B" * 120},
            {"id": 2, "description": "C" * 120},
            {"id": 3, "description": "D" * 120},
        ]
        selected = select_batch_jobs(jobs, limit=10)
        self.assertEqual([job["id"] for job in selected], [2, 3])

    def test_zero_limit_selects_nothing(self) -> None:
        self.assertEqual(
            select_batch_jobs(
                [{"id": 1, "description": "A" * 120}],
                limit=0,
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()

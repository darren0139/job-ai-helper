from __future__ import annotations

import unittest

from job_discovery.view_performance import (
    clamp_page,
    match_state_cache_key,
)


class JobFinderViewPerformanceTests(unittest.TestCase):
    def test_cache_key_changes_with_job_content(self) -> None:
        a = match_state_cache_key(
            [{"id": 1, "content_hash": "a"}],
            evidence_fingerprint="candidate-a",
            versions={"match_version": "v1"},
        )
        b = match_state_cache_key(
            [{"id": 1, "content_hash": "b"}],
            evidence_fingerprint="candidate-a",
            versions={"match_version": "v1"},
        )
        self.assertNotEqual(a, b)

    def test_cache_key_changes_with_candidate_identity(self) -> None:
        jobs = [{"id": 1, "content_hash": "a"}]
        a = match_state_cache_key(
            jobs,
            evidence_fingerprint="candidate-a",
            versions={"match_version": "v1"},
        )
        b = match_state_cache_key(
            jobs,
            evidence_fingerprint="candidate-b",
            versions={"match_version": "v1"},
        )
        self.assertNotEqual(a, b)

    def test_cache_key_is_deterministic(self) -> None:
        jobs = [
            {"id": 1, "content_hash": "a"},
            {"id": 2, "content_hash": "b"},
        ]
        a = match_state_cache_key(
            jobs,
            evidence_fingerprint="candidate-a",
            versions={"taxonomy_version": "t1", "match_version": "m1"},
        )
        b = match_state_cache_key(
            jobs,
            evidence_fingerprint="candidate-a",
            versions={"match_version": "m1", "taxonomy_version": "t1"},
        )
        self.assertEqual(a, b)

    def test_clamp_page(self) -> None:
        self.assertEqual(clamp_page(0, 10), 1)
        self.assertEqual(clamp_page(4, 10), 4)
        self.assertEqual(clamp_page(99, 10), 10)
        self.assertEqual(clamp_page(5, 0), 1)


if __name__ == "__main__":
    unittest.main()

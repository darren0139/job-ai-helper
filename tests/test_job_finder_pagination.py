from __future__ import annotations

import unittest

from job_discovery.faceted_search import apply_job_finder_filters
from job_discovery.match_ranking import best_match_sort_key
from job_discovery.result_pagination import paginate_jobs


class JobFinderPaginationTests(unittest.TestCase):
    def test_pagination_renders_only_requested_page(self) -> None:
        jobs = [{"id": i, "source": "mycareersfuture"} for i in range(1, 676)]
        page = paginate_jobs(jobs, page=1, page_size=20)
        self.assertEqual(page["total"], 675)
        self.assertEqual(page["total_pages"], 34)
        self.assertEqual(len(page["jobs"]), 20)
        self.assertEqual([row["id"] for row in page["jobs"]], list(range(1, 21)))

    def test_last_page_is_partial_and_clamped(self) -> None:
        jobs = [{"id": i} for i in range(1, 676)]
        page = paginate_jobs(jobs, page=999, page_size=20)
        self.assertEqual(page["page"], 34)
        self.assertEqual(len(page["jobs"]), 15)
        self.assertEqual(page["jobs"][0]["id"], 661)

    def test_source_filter_happens_before_pagination(self) -> None:
        jobs = [
            {"id": 1, "source": "mycareersfuture", "company": "Alpha", "description": "A" * 120},
            {"id": 2, "source": "smartrecruiters", "company": "Beta", "description": "B" * 120},
            {"id": 3, "source": "mycareersfuture", "company": "Gamma", "description": "C" * 120},
        ]
        filtered = apply_job_finder_filters(
            jobs,
            selected_sources=["mycareersfuture"],
            selected_lifecycle_statuses=[],
        )["jobs"]
        page = paginate_jobs(filtered, page=1, page_size=20)
        self.assertEqual([row["id"] for row in page["jobs"]], [1, 3])
        self.assertTrue(all(row["source"] == "mycareersfuture" for row in page["jobs"]))

    def test_provisional_best_match_uses_taxonomy_before_alignment(self) -> None:
        stronger_taxonomy = {
            "summary": {
                "ranking_eligible": False,
                "deterministic_alignment_score": 24,
                "important_taxonomy_coverage_pct": 45,
            }
        }
        stronger_alignment = {
            "summary": {
                "ranking_eligible": False,
                "deterministic_alignment_score": 25,
                "important_taxonomy_coverage_pct": 43,
            }
        }
        self.assertGreater(
            best_match_sort_key(
                stronger_taxonomy,
                search_relevance=1,
                discovered_job_id=1,
            ),
            best_match_sort_key(
                stronger_alignment,
                search_relevance=100,
                discovered_job_id=2,
            ),
        )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from job_discovery.faceted_search import (
    filter_jobs_by_companies,
    filter_jobs_by_sources,
)


class RefreshFilterUxRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.jobs = [
            {"id": 1, "source": "smartrecruiters", "company": "NCS"},
            {"id": 2, "source": "smartrecruiters", "company": "Grab"},
            {"id": 3, "source": "mycareersfuture", "company": "NCS"},
            {"id": 4, "source": "greenhouse", "company": "GovTech"},
        ]

    def test_specific_company_is_global_exact_display_filter(self) -> None:
        filtered = filter_jobs_by_companies(self.jobs, ["NCS"])
        self.assertEqual([job["id"] for job in filtered], [1, 3])
        self.assertEqual({job["company"] for job in filtered}, {"NCS"})

    def test_company_filter_can_select_multiple_companies(self) -> None:
        filtered = filter_jobs_by_companies(self.jobs, ["NCS", "Grab"])
        self.assertEqual([job["id"] for job in filtered], [1, 2, 3])
        self.assertEqual({job["company"] for job in filtered}, {"NCS", "Grab"})

    def test_source_filter_and_company_filter_compose(self) -> None:
        source_filtered = filter_jobs_by_sources(self.jobs, ["smartrecruiters"])
        company_filtered = filter_jobs_by_companies(source_filtered, ["NCS"])
        self.assertEqual([job["id"] for job in company_filtered], [1])

    def test_blank_company_filter_means_all_companies(self) -> None:
        self.assertEqual(filter_jobs_by_companies(self.jobs, []), self.jobs)


if __name__ == "__main__":
    unittest.main()

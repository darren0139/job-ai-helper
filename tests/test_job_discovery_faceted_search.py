from __future__ import annotations

import unittest

from job_discovery.faceted_search import (
    company_counts,
    employment_type_counts,
    filter_jobs_by_companies,
    filter_jobs_by_employment_types,
    filter_jobs_by_max_explicit_minimum_experience,
    filter_jobs_by_sources,
    source_counts,
)


class JobDiscoveryFacetedSearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.jobs = [
            {
                "source": "smartrecruiters",
                "company": "NCS",
                "employment_type": "Full-time",
                "experience_years_min": 0,
            },
            {
                "source": "smartrecruiters",
                "company": "Grab",
                "employment_type": "Full-time",
                "experience_years_min": 3,
            },
            {
                "source": "mycareersfuture",
                "company": "Example Co",
                "employment_type": "Contract",
                "experience_years_min": 5,
            },
            {
                "source": "careers_gov",
                "company": "Agency",
                "employment_type": "Full-time",
                "experience_years_min": None,
            },
        ]

    def test_no_source_selection_means_all_sources(self) -> None:
        self.assertEqual(filter_jobs_by_sources(self.jobs, []), self.jobs)

    def test_source_filter_is_live_scope(self) -> None:
        filtered = filter_jobs_by_sources(self.jobs, ["smartrecruiters"])
        self.assertEqual([job["company"] for job in filtered], ["NCS", "Grab"])

    def test_source_counts(self) -> None:
        self.assertEqual(
            source_counts(self.jobs),
            {"smartrecruiters": 2, "mycareersfuture": 1, "careers_gov": 1},
        )

    def test_no_company_selection_means_all_companies(self) -> None:
        self.assertEqual(filter_jobs_by_companies(self.jobs, []), self.jobs)

    def test_company_filter_is_exact_case_insensitive(self) -> None:
        filtered = filter_jobs_by_companies(self.jobs, ["ncs"])
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["company"], "NCS")

    def test_company_counts(self) -> None:
        self.assertEqual(company_counts(self.jobs)["NCS"], 1)
        self.assertEqual(company_counts(self.jobs)["Grab"], 1)

    def test_employment_type_filter(self) -> None:
        filtered = filter_jobs_by_employment_types(self.jobs, ["Contract"])
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["company"], "Example Co")
        self.assertEqual(employment_type_counts(self.jobs)["Full-time"], 3)

    def test_experience_ceiling_keeps_unknown_conservatively(self) -> None:
        filtered = filter_jobs_by_max_explicit_minimum_experience(self.jobs, 2)
        self.assertEqual([job["company"] for job in filtered], ["NCS", "Agency"])

    def test_no_experience_ceiling_means_all(self) -> None:
        self.assertEqual(
            filter_jobs_by_max_explicit_minimum_experience(self.jobs, None),
            self.jobs,
        )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from job_discovery.search_filters import (
    filter_jobs_by_target_companies,
    target_key,
    targets_for_sources,
)


class JobDiscoverySearchFilterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ncs = {
            "company_name": "NCS",
            "ats_provider": "smartrecruiters",
            "ats_identifier": "NCS3",
        }
        self.grab = {
            "company_name": "Grab",
            "ats_provider": "smartrecruiters",
            "ats_identifier": "Grab",
        }
        self.example_ashby = {
            "company_name": "Example AI",
            "ats_provider": "ashby",
            "ats_identifier": "ExampleAI",
        }

    def test_target_key_uses_provider_and_identifier(self) -> None:
        self.assertEqual(target_key(self.ncs), "smartrecruiters:NCS3")

    def test_targets_for_sources_keeps_only_selected_providers(self) -> None:
        targets = targets_for_sources(
            [self.ncs, self.example_ashby],
            ["smartrecruiters"],
        )
        self.assertEqual(targets, [self.ncs])

    def test_empty_target_selection_does_not_filter_jobs(self) -> None:
        jobs = [
            {"source": "smartrecruiters", "source_scope": "smartrecruiters:NCS3"},
            {"source": "mycareersfuture", "source_scope": "mycareersfuture"},
        ]
        self.assertEqual(filter_jobs_by_target_companies(jobs, []), jobs)

    def test_company_filter_only_restricts_its_ats_provider(self) -> None:
        jobs = [
            {
                "source": "smartrecruiters",
                "source_scope": "smartrecruiters:NCS3",
                "company": "NCS",
            },
            {
                "source": "smartrecruiters",
                "source_scope": "smartrecruiters:Grab",
                "company": "Grab",
            },
            {
                "source": "mycareersfuture",
                "source_scope": "mycareersfuture",
                "company": "Some Employer",
            },
            {
                "source": "ashby",
                "source_scope": "ashby:ExampleAI",
                "company": "Example AI",
            },
        ]
        filtered = filter_jobs_by_target_companies(jobs, [self.ncs])
        self.assertEqual(
            [(job["source"], job["company"]) for job in filtered],
            [
                ("smartrecruiters", "NCS"),
                ("mycareersfuture", "Some Employer"),
                ("ashby", "Example AI"),
            ],
        )

    def test_different_company_filters_can_apply_per_provider(self) -> None:
        jobs = [
            {
                "source": "smartrecruiters",
                "source_scope": "smartrecruiters:NCS3",
                "company": "NCS",
            },
            {
                "source": "smartrecruiters",
                "source_scope": "smartrecruiters:Grab",
                "company": "Grab",
            },
            {
                "source": "ashby",
                "source_scope": "ashby:ExampleAI",
                "company": "Example AI",
            },
            {
                "source": "ashby",
                "source_scope": "ashby:OtherAI",
                "company": "Other AI",
            },
        ]
        filtered = filter_jobs_by_target_companies(
            jobs,
            [self.grab, self.example_ashby],
        )
        self.assertEqual(
            [(job["source"], job["company"]) for job in filtered],
            [
                ("smartrecruiters", "Grab"),
                ("ashby", "Example AI"),
            ],
        )

    def test_legacy_row_without_source_scope_can_match_company_name(self) -> None:
        jobs = [
            {
                "source": "smartrecruiters",
                "source_scope": "",
                "company": "NCS",
            },
            {
                "source": "smartrecruiters",
                "source_scope": "",
                "company": "Grab",
            },
        ]
        filtered = filter_jobs_by_target_companies(jobs, [self.ncs])
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["company"], "NCS")


if __name__ == "__main__":
    unittest.main()

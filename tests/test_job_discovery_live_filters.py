from __future__ import annotations

from datetime import datetime, timezone
import unittest

from job_discovery.faceted_search import (
    filter_jobs_by_companies,
    filter_jobs_by_employment_types,
    filter_jobs_by_entry_level,
    filter_jobs_by_events,
    filter_jobs_by_freshness,
    filter_jobs_by_lifecycle,
    filter_jobs_by_max_explicit_minimum_experience,
    filter_jobs_by_sources,
)


class LiveFilterConsistencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 9, 22, 8, 0, tzinfo=timezone.utc).timestamp()
        self.jobs = [
            {
                "id": 1,
                "source": "smartrecruiters",
                "company": "NCS",
                "posted_at": "2026-09-22T06:00:00+00:00",
                "first_seen_at": "2026-09-22T06:30:00+00:00",
                "experience_years_min": 0,
                "employment_type": "Full-time",
                "lifecycle_status": "active",
                "last_event": "new",
                "title": "Junior Software Engineer",
                "seniority": "Entry Level",
                "description": "Fresh graduate role.",
            },
            {
                "id": 2,
                "source": "smartrecruiters",
                "company": "Grab",
                "posted_at": "2026-09-10T06:00:00+00:00",
                "first_seen_at": "2026-09-21T06:30:00+00:00",
                "experience_years_min": 4,
                "employment_type": "Full-time",
                "lifecycle_status": "active",
                "last_event": "changed",
                "title": "Senior Software Engineer",
                "seniority": "Senior",
                "description": "Experienced role.",
            },
            {
                "id": 3,
                "source": "mycareersfuture",
                "company": "Example Co",
                "posted_at": "",
                "first_seen_at": "2026-09-21T07:00:00+00:00",
                "experience_years_min": None,
                "employment_type": "Contract",
                "lifecycle_status": "removed",
                "last_event": "removed",
                "title": "Backend Developer",
                "seniority": "",
                "description": "General backend role.",
            },
        ]

    def ids(self, jobs):
        return [job["id"] for job in jobs]

    def test_source_live_filter(self) -> None:
        self.assertEqual(
            self.ids(filter_jobs_by_sources(self.jobs, ["smartrecruiters"])),
            [1, 2],
        )
        self.assertEqual(self.ids(filter_jobs_by_sources(self.jobs, [])), [1, 2, 3])

    def test_company_live_filter(self) -> None:
        self.assertEqual(self.ids(filter_jobs_by_companies(self.jobs, ["NCS"])), [1])
        self.assertEqual(self.ids(filter_jobs_by_companies(self.jobs, [])), [1, 2, 3])

    def test_freshness_live_filter_and_first_seen_fallback(self) -> None:
        filtered = filter_jobs_by_freshness(
            self.jobs,
            3,
            now_timestamp=self.now,
        )
        self.assertEqual(self.ids(filtered), [1, 3])
        self.assertEqual(
            self.ids(filter_jobs_by_freshness(self.jobs, None, now_timestamp=self.now)),
            [1, 2, 3],
        )

    def test_experience_ceiling_is_live_and_unknown_passes(self) -> None:
        self.assertEqual(
            self.ids(filter_jobs_by_max_explicit_minimum_experience(self.jobs, 2)),
            [1, 3],
        )

    def test_availability_blank_means_all(self) -> None:
        self.assertEqual(
            self.ids(filter_jobs_by_lifecycle(self.jobs, [])),
            [1, 2, 3],
        )
        self.assertEqual(
            self.ids(filter_jobs_by_lifecycle(self.jobs, ["active"])),
            [1, 2],
        )

    def test_event_filter_is_exact_for_removed_rows(self) -> None:
        self.assertEqual(
            self.ids(filter_jobs_by_events(self.jobs, ["new"])),
            [1],
        )
        self.assertEqual(
            self.ids(filter_jobs_by_events(self.jobs, ["removed"])),
            [3],
        )
        self.assertEqual(
            self.ids(filter_jobs_by_events(self.jobs, [])),
            [1, 2, 3],
        )

    def test_employment_type_is_live(self) -> None:
        self.assertEqual(
            self.ids(filter_jobs_by_employment_types(self.jobs, ["Contract"])),
            [3],
        )

    def test_entry_filter_rejects_senior_title(self) -> None:
        self.assertEqual(
            self.ids(filter_jobs_by_entry_level(self.jobs, True)),
            [1],
        )
        self.assertEqual(
            self.ids(filter_jobs_by_entry_level(self.jobs, False)),
            [1, 2, 3],
        )

    def test_filters_compose_as_a_pipeline(self) -> None:
        jobs = filter_jobs_by_sources(self.jobs, ["smartrecruiters"])
        jobs = filter_jobs_by_companies(jobs, ["NCS"])
        jobs = filter_jobs_by_freshness(jobs, 3, now_timestamp=self.now)
        jobs = filter_jobs_by_max_explicit_minimum_experience(jobs, 2)
        jobs = filter_jobs_by_lifecycle(jobs, ["active"])
        jobs = filter_jobs_by_events(jobs, ["new"])
        jobs = filter_jobs_by_employment_types(jobs, ["Full-time"])
        jobs = filter_jobs_by_entry_level(jobs, True)
        self.assertEqual(self.ids(jobs), [1])


if __name__ == "__main__":
    unittest.main()

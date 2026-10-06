from __future__ import annotations

from datetime import datetime, timezone
import unittest

from job_discovery.faceted_search import apply_job_finder_filters


class AuthoritativeJobFinderFilterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(
            2026, 10, 3, 0, 0, tzinfo=timezone.utc
        ).timestamp()
        self.jobs = [
            {
                "id": 1,
                "source": "mycareersfuture",
                "company": "Alpha",
                "posted_at": "2026-10-02T12:00:00+00:00",
                "first_seen_at": "2026-10-02T12:00:00+00:00",
                "experience_years_min": 1,
                "lifecycle_status": "active",
                "last_event": "new",
                "employment_type": "Full-time",
                "title": "Junior Software Engineer",
                "seniority": "Junior",
                "description": "Entry level software engineer role.",
            },
            {
                "id": 2,
                "source": "smartrecruiters",
                "company": "Beta",
                "posted_at": "2026-09-20T12:00:00+00:00",
                "first_seen_at": "2026-09-20T12:00:00+00:00",
                "experience_years_min": 5,
                "lifecycle_status": "active",
                "last_event": "unchanged",
                "employment_type": "Full-time",
                "title": "Senior Software Engineer",
                "seniority": "Senior",
                "description": "Senior backend software engineer.",
            },
            {
                "id": 3,
                "source": "smartrecruiters",
                "company": "Gamma",
                "posted_at": "2026-10-02T12:00:00+00:00",
                "first_seen_at": "2026-10-02T12:00:00+00:00",
                "experience_years_min": None,
                "lifecycle_status": "removed",
                "last_event": "changed",
                "employment_type": "Contract",
                "title": "Software Developer",
                "seniority": "",
                "description": "Software developer contract role.",
            },
        ]

    def ids(self, result: dict) -> list[int]:
        return [int(job["id"]) for job in result["jobs"]]

    def test_blank_optional_filters_preserve_base_rows(self) -> None:
        result = apply_job_finder_filters(
            self.jobs,
            selected_lifecycle_statuses=[],
            now_timestamp=self.now,
        )
        self.assertEqual(self.ids(result), [1, 2, 3])

    def test_each_filter_is_authoritative(self) -> None:
        self.assertEqual(
            self.ids(apply_job_finder_filters(
                self.jobs,
                selected_sources=["mycareersfuture"],
                selected_lifecycle_statuses=[],
                now_timestamp=self.now,
            )),
            [1],
        )
        self.assertEqual(
            self.ids(apply_job_finder_filters(
                self.jobs,
                selected_companies=["Gamma"],
                selected_lifecycle_statuses=[],
                now_timestamp=self.now,
            )),
            [3],
        )
        self.assertEqual(
            self.ids(apply_job_finder_filters(
                self.jobs,
                max_age_days=3,
                selected_lifecycle_statuses=[],
                now_timestamp=self.now,
            )),
            [1, 3],
        )
        self.assertEqual(
            self.ids(apply_job_finder_filters(
                self.jobs,
                max_experience_years=2,
                selected_lifecycle_statuses=[],
                now_timestamp=self.now,
            )),
            [1, 3],
        )
        self.assertEqual(
            self.ids(apply_job_finder_filters(
                self.jobs,
                selected_lifecycle_statuses=["removed"],
                now_timestamp=self.now,
            )),
            [3],
        )
        self.assertEqual(
            self.ids(apply_job_finder_filters(
                self.jobs,
                selected_events=["changed"],
                selected_lifecycle_statuses=[],
                now_timestamp=self.now,
            )),
            [3],
        )
        self.assertEqual(
            self.ids(apply_job_finder_filters(
                self.jobs,
                selected_employment_types=["Contract"],
                selected_lifecycle_statuses=[],
                now_timestamp=self.now,
            )),
            [3],
        )
        self.assertEqual(
            self.ids(apply_job_finder_filters(
                self.jobs,
                entry_only=True,
                selected_lifecycle_statuses=[],
                now_timestamp=self.now,
            )),
            [1],
        )

    def test_all_filters_compose_from_same_base(self) -> None:
        result = apply_job_finder_filters(
            self.jobs,
            selected_sources=["mycareersfuture"],
            selected_companies=["Alpha"],
            max_age_days=3,
            max_experience_years=2,
            selected_lifecycle_statuses=["active"],
            selected_events=["new"],
            selected_employment_types=["Full-time"],
            entry_only=True,
            now_timestamp=self.now,
        )
        self.assertEqual(self.ids(result), [1])
        self.assertEqual(
            result["trace"][-1]["Jobs"],
            result["output_count"],
        )


if __name__ == "__main__":
    unittest.main()

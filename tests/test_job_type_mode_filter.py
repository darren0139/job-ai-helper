from __future__ import annotations

import unittest

from job_discovery.faceted_search import (
    JOB_TYPE_MODES,
    apply_job_finder_filters,
    filter_jobs_by_job_type_mode,
    job_type_bucket,
)


class JobTypeModeFilterTests(unittest.TestCase):
    def _job(
        self,
        job_id: int,
        *,
        employment_type: str = "",
        title: str = "Software Engineer",
        description: str = "Build software.",
    ) -> dict:
        return {
            "id": job_id,
            "source": "example",
            "company": "Example",
            "employment_type": employment_type,
            "title": title,
            "description": description,
            "lifecycle_status": "active",
            "last_event": "unchanged",
            "posted_at": "",
            "first_seen_at": "",
            "experience_years_min": None,
            "seniority": "",
        }

    def ids(self, rows: list[dict]) -> list[int]:
        return [int(row["id"]) for row in rows]

    def test_modes_are_pinned(self) -> None:
        self.assertEqual(
            JOB_TYPE_MODES,
            (
                "All jobs",
                "Full-time",
                "Part-time / shift",
                "Internship",
                "Contract / temporary",
            ),
        )

    def test_all_jobs_returns_all(self) -> None:
        jobs = [
            self._job(1, employment_type="Full-time"),
            self._job(2, employment_type="Part-time"),
            self._job(3),
        ]
        self.assertEqual(
            self.ids(filter_jobs_by_job_type_mode(jobs, "All jobs")),
            [1, 2, 3],
        )

    def test_full_time_aliases(self) -> None:
        for value in ["Full-time", "Full time", "Fulltime", "Permanent"]:
            with self.subTest(value=value):
                self.assertEqual(
                    job_type_bucket(self._job(1, employment_type=value)),
                    "Full-time",
                )

    def test_part_time_shift_aliases(self) -> None:
        values = [
            "Part-time",
            "Part time",
            "Gig / shift",
            "Gig",
            "Shift",
            "Casual",
            "Freelance",
            "Hourly",
        ]
        for value in values:
            with self.subTest(value=value):
                self.assertEqual(
                    job_type_bucket(self._job(1, employment_type=value)),
                    "Part-time / shift",
                )

    def test_internship_aliases(self) -> None:
        for value in ["Internship", "Intern"]:
            with self.subTest(value=value):
                self.assertEqual(
                    job_type_bucket(self._job(1, employment_type=value)),
                    "Internship",
                )

    def test_contract_temporary_aliases(self) -> None:
        for value in ["Contract", "Temporary", "Temp"]:
            with self.subTest(value=value):
                self.assertEqual(
                    job_type_bucket(self._job(1, employment_type=value)),
                    "Contract / temporary",
                )

    def test_unknown_does_not_accidentally_classify(self) -> None:
        job = self._job(
            1,
            employment_type="Project based",
            title="Software Engineer",
            description="Build internal tools.",
        )
        self.assertEqual(job_type_bucket(job), "Other / unspecified")

    def test_title_description_fallback(self) -> None:
        cases = [
            (
                self._job(1, title="Part Time Retail Assistant"),
                "Part-time / shift",
            ),
            (
                self._job(
                    2,
                    description="This internship supports engineering.",
                ),
                "Internship",
            ),
            (
                self._job(
                    3,
                    description="Six-month contract role.",
                ),
                "Contract / temporary",
            ),
            (
                self._job(
                    4,
                    description="Permanent position in Singapore.",
                ),
                "Full-time",
            ),
        ]
        for job, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(job_type_bucket(job), expected)

    def test_unrecognized_structured_value_can_fall_back(self) -> None:
        job = self._job(
            1,
            employment_type="Regular",
            title="Hourly Service Crew",
        )
        self.assertEqual(job_type_bucket(job), "Part-time / shift")

    def test_structured_known_type_wins(self) -> None:
        job = self._job(
            1,
            employment_type="Contract",
            title="Software Intern",
            description="Internship-style programme.",
        )
        self.assertEqual(job_type_bucket(job), "Contract / temporary")

    def test_authoritative_pipeline_applies_job_type(self) -> None:
        jobs = [
            self._job(1, employment_type="Full-time"),
            self._job(2, employment_type="Part-time"),
            self._job(3, title="Casual Event Crew"),
        ]
        result = apply_job_finder_filters(
            jobs,
            job_type_mode="Part-time / shift",
            selected_lifecycle_statuses=[],
        )
        self.assertEqual(self.ids(result["jobs"]), [2, 3])
        self.assertIn(
            {"Stage": "Job Type", "Jobs": 2},
            result["trace"],
        )

    def test_exact_employment_facet_is_independent(self) -> None:
        jobs = [
            self._job(1, employment_type="Part-time"),
            self._job(2, employment_type="Casual"),
            self._job(3, employment_type="Gig"),
        ]
        result = apply_job_finder_filters(
            jobs,
            job_type_mode="Part-time / shift",
            selected_employment_types=["Casual"],
            selected_lifecycle_statuses=[],
        )
        self.assertEqual(self.ids(result["jobs"]), [2])

    def test_unknown_mode_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown Job Type mode"):
            filter_jobs_by_job_type_mode(
                [self._job(1)],
                "Mystery",
            )


if __name__ == "__main__":
    unittest.main()

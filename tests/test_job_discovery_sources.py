from __future__ import annotations

import unittest

from job_discovery.models import SearchSpec
from job_discovery.sources.ashby import AshbySource
from job_discovery.sources.careers_gov import CareersGovSource
from job_discovery.sources.greenhouse import GreenhouseSource
from job_discovery.sources.lever import LeverSource
from job_discovery.sources.mycareersfuture import MyCareersFutureSource
from job_discovery.sources.smartrecruiters import SmartRecruitersSource


class FakeClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get_json(self, url, *, params=None, headers=None):
        self.calls.append((url, params, headers))
        return self.response

    def pause(self, seconds):
        return None


class SequenceClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get_json(self, url, *, params=None, headers=None):
        self.calls.append((url, params, headers))
        if not self.responses:
            raise AssertionError("No fake response left for request")
        return self.responses.pop(0)

    def pause(self, seconds):
        return None


class JobDiscoverySourceTests(unittest.TestCase):
    def test_mcf_normalizes_job(self) -> None:
        raw = {
            "uuid": "abc-123",
            "title": "AI Engineer",
            "description": "Build production AI services with Python.",
            "postedCompany": {"name": "Example Pte Ltd"},
            "addressFormatted": "Singapore",
            "salary": {"minimum": 4500, "maximum": 6500},
            "metadata": {"createdAt": "2026-09-20T00:00:00Z"},
            "positionLevels": ["Fresh/entry level"],
        }
        client = FakeClient({"results": [raw]})
        source = MyCareersFutureSource(client=client, delay_seconds=0)
        jobs = source.fetch(SearchSpec(query="AI Engineer", max_pages=1))
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].company, "Example Pte Ltd")
        self.assertEqual(jobs[0].salary_min, 4500.0)
        self.assertIn("Python", jobs[0].description)

    def test_careers_gov_normalizes_combined_description(self) -> None:
        raw = {
            "platform": "hrp",
            "postingNo": "guid-1",
            "jobId": "123",
            "jobTitle": "Data Engineer",
            "agency": "Gov Agency",
            "location": "Singapore",
            "jobDescription": "Build data systems.",
            "jobResponsibilities": "Maintain pipelines.",
            "jobRequirements": "Python and SQL.",
            "startDate": 1789948800000,
            "closingDate": 1790553600000,
            "experienceYearsMin": 0,
            "experienceYearsMax": 2,
            "employmentType": "Permanent",
        }
        client = FakeClient([raw])
        source = CareersGovSource(client=client)
        jobs = source.fetch(SearchSpec(query="Data Engineer"))
        self.assertEqual(len(jobs), 1)
        self.assertIn("Responsibilities", jobs[0].description)
        self.assertIn("Python and SQL", jobs[0].description)
        self.assertEqual(jobs[0].experience_years_min, 0.0)

    def test_greenhouse_normalizes_public_board_job(self) -> None:
        client = FakeClient({
            "jobs": [{
                "id": 42,
                "title": "Machine Learning Engineer",
                "company_name": "Example AI",
                "content": "<p>Build Python AI services.</p>",
                "location": {"name": "Singapore"},
                "absolute_url": "https://boards.greenhouse.io/example/jobs/42",
                "first_published": "2026-09-20T10:00:00Z",
            }]
        })
        jobs = GreenhouseSource("example", client=client).fetch(
            SearchSpec(query="Machine Learning", max_pages=1)
        )
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].source_job_id, "example:42")
        self.assertIn("Python AI services", jobs[0].description)

    def test_lever_normalizes_public_posting(self) -> None:
        client = FakeClient([{
            "id": "lever-1",
            "text": "Backend Engineer",
            "descriptionPlain": "Build Python backend systems.",
            "categories": {"location": "Singapore", "commitment": "Full-time"},
            "hostedUrl": "https://jobs.lever.co/example/lever-1",
            "applyUrl": "https://jobs.lever.co/example/lever-1/apply",
        }])
        jobs = LeverSource("example", client=client).fetch(
            SearchSpec(query="Backend Engineer", max_pages=1)
        )
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].employment_type, "Full-time")

    def test_ashby_normalizes_public_board_job(self) -> None:
        client = FakeClient({
            "jobs": [{
                "title": "AI Engineer",
                "descriptionPlain": "Build production AI systems with Python.",
                "location": "Singapore",
                "jobUrl": "https://jobs.ashbyhq.com/example/job-123",
                "applyUrl": "https://jobs.ashbyhq.com/example/job-123/application",
                "publishedAt": "2026-09-20T10:00:00Z",
                "employmentType": "FullTime",
                "isListed": True,
                "compensation": {
                    "summaryComponents": [{
                        "compensationType": "Salary",
                        "minValue": 5000,
                        "maxValue": 7000,
                        "currencyCode": "SGD",
                        "interval": "MONTH",
                    }]
                },
            }]
        })
        jobs = AshbySource("example", client=client).fetch(
            SearchSpec(query="AI Engineer")
        )
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].salary_min, 5000)
        self.assertEqual(jobs[0].salary_currency, "SGD")

    def test_smartrecruiters_normalizes_public_posting(self) -> None:
        client = SequenceClient([
            {"content": [{"id": "sr-1", "name": "Data Engineer"}]},
            {
                "id": "sr-1",
                "name": "Data Engineer",
                "company": {"name": "Example Data"},
                "location": {"city": "Singapore", "country": "Singapore"},
                "jobAd": {
                    "sections": {
                        "jobDescription": "Build Python data services.",
                        "qualifications": "SQL and cloud experience.",
                    },
                    "jobUrl": "https://jobs.smartrecruiters.com/example/sr-1",
                },
                "applyUrl": "https://jobs.smartrecruiters.com/example/sr-1/apply",
                "releasedDate": "2026-09-20T10:00:00Z",
                "typeOfEmployment": {"label": "Full-time"},
            },
        ])
        jobs = SmartRecruitersSource("example", client=client).fetch(
            SearchSpec(query="Data Engineer", max_pages=1)
        )
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].company, "Example Data")
        self.assertIn("SQL and cloud", jobs[0].description)


if __name__ == "__main__":
    unittest.main()

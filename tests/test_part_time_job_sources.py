from __future__ import annotations

import unittest

from job_discovery.models import SearchSpec
from job_discovery.sources.fastjobs import FastJobsSource
from job_discovery.sources.staffie import StaffieSource
from job_discovery.sources.workjio import WorkJioSource


class FakeTextClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get_text(self, url, *, params=None, headers=None):
        self.calls.append((url, params, headers))
        key = (url, tuple(sorted((params or {}).items())))
        if key in self.responses:
            return self.responses[key]
        if url in self.responses:
            return self.responses[url]
        raise AssertionError(f"No fake response for {url} params={params}")

    def pause(self, seconds):
        return None


class PartTimeSourceTests(unittest.TestCase):
    def test_fastjobs_direct_detail_normalizes(self) -> None:
        url = "https://www.fastjobs.sg/singapore-job-ad/2644093/rec-job"
        html = """
        <html><head>
        <title>Cashier job Singapore - PASTAGO PTE. LTD. | FastJobs</title>
        </head><body>
        <h1>Cashier for a Pasta Kiosk</h1>
        <div>Bedok North MRT, Bedok</div>
        <div>Part Time, Contract</div>
        <div>S$12.5 - 14 / hour</div>
        <p>Join our modern pasta kiosk. Training provided.</p>
        <h2>Job Description</h2>
        <p>Take orders, pack orders, clean the kiosk, and support stocktake.</p>
        <h2>Requirements</h2>
        <p>Able to work in a fast paced environment and multitask well.</p>
        <div>About the Employer</div>
        <div>PASTAGO PTE. LTD.</div>
        <div>BRN/UEN: 202137956C</div>
        </body></html>
        """
        jobs = FastJobsSource(
            [url],
            client=FakeTextClient({url: html}),
            delay_seconds=0,
        ).fetch(SearchSpec(query="Cashier"))
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].source_job_id, "2644093")
        self.assertEqual(jobs[0].company, "PASTAGO PTE. LTD.")
        self.assertEqual(jobs[0].salary_min, 12.5)
        self.assertEqual(jobs[0].salary_max, 14.0)
        self.assertEqual(jobs[0].salary_period, "hour")
        self.assertIn("Part Time", jobs[0].employment_type)

    def test_workjio_pages_and_normalizes_detail(self) -> None:
        list_url = "https://www.workjio.com/part-time-jobs"
        detail_url = (
            "https://www.workjio.com/jobs/"
            "project-coordinator-hourly-rated-lalamove-r6hb5"
        )
        listing = f"""
        <html><body><h1>270 part-time jobs</h1>
        <h2>Job listings</h2>
        <a href="{detail_url}">Project Coordinator (Hourly Rated)</a>
        </body></html>
        """
        detail = """
        <html><head>
        <title>Project Coordinator (Hourly Rated) job at Lalamove, Singapore | WorkJio</title>
        </head><body>
        <h1>Project Coordinator (Hourly Rated)</h1>
        <div>Salary</div><div>S$12–13</div><div>per hour</div>
        <div>When</div><div>Minimum 3 days/week</div>
        <div>Where</div><div>Location not stated</div>
        <h2>About the role</h2>
        <p>Assist with routing and scheduling client delivery orders and support customers.</p>
        <h2>Requirements</h2>
        <ul><li>Strong customer service and communication skills</li>
        <li>Able to work independently</li></ul>
        <div>Apply on the company website</div>
        <div>Listing ID 193</div>
        </body></html>
        """
        client = FakeTextClient({list_url: listing, detail_url: detail})
        jobs = WorkJioSource(client=client, delay_seconds=0).fetch(
            SearchSpec(
                query="Project Coordinator",
                max_pages=1,
                limit_per_source=20,
            )
        )
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].source_job_id, "193")
        self.assertEqual(jobs[0].company, "Lalamove")
        self.assertEqual(jobs[0].location, "Singapore")
        self.assertEqual(jobs[0].salary_min, 12.0)
        self.assertEqual(jobs[0].salary_max, 13.0)
        self.assertEqual(jobs[0].employment_type, "Part-time")
        self.assertIn("communication skills", jobs[0].description)

    def test_staffie_public_weekly_shift_samples(self) -> None:
        html = """
        <html><body>
        <h2>New shifts this week</h2>
        <p>See some of the shifts other Pros are picking up this week.</p>
        <h4>Clos Pasoh</h4>
        <p>French Restaurant at Outram Park</p>
        <p>Server · S$16/hr · 10 shifts</p>
        <p>Cook · S$18/hr · 6 shifts</p>
        <h4>Harry's Chijmes</h4>
        <p>Bar at City Hall</p>
        <p>Server · S$14/hr · 9 shifts</p>
        <h4>Book these and more, instantly →</h4>
        </body></html>
        """
        jobs = StaffieSource(
            client=FakeTextClient({StaffieSource.BASE_URL: html})
        ).fetch(SearchSpec(query=""))
        self.assertEqual(len(jobs), 3)
        self.assertEqual(jobs[0].company, "Clos Pasoh")
        self.assertEqual(jobs[0].title, "Server")
        self.assertEqual(jobs[0].location, "Outram Park")
        self.assertEqual(jobs[0].salary_min, 16.0)
        self.assertEqual(jobs[0].employment_type, "Gig / Shift")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from job_discovery.models import NormalizedJob, SearchSpec
from job_discovery.pipeline import _can_reuse_recent_run, _targets
from job_discovery.sources.careers_gov import CareersGovSource
from job_discovery.sources.smartrecruiters import SmartRecruitersSource


class FakeClient:
    def __init__(self, listing, details=None):
        self.listing = listing
        self.details = details or {}
        self.calls = []

    def get_json(self, url, *, params=None, headers=None):
        self.calls.append((url, params))
        if url.endswith('/postings'):
            return {"content": list(self.listing)}
        posting_id = url.rstrip('/').split('/')[-1]
        return self.details[posting_id]


class FastRefreshTests(unittest.TestCase):
    def _detail(self, posting_id='1', title='Software Engineer'):
        return {
            "id": posting_id,
            "jobAdId": f"ad-{posting_id}",
            "name": title,
            "releasedDate": "2026-09-20T00:00:00Z",
            "company": {"name": "NCS"},
            "location": {"city": "Singapore", "country": "sg"},
            "typeOfEmployment": {"label": "Full-time"},
            "jobAd": {
                "jobUrl": f"https://jobs.smartrecruiters.com/NCS3/{posting_id}",
                "sections": {"jobDescription": "Build production software systems."},
            },
        }

    def _summary(self, posting_id='1', title='Software Engineer'):
        return {
            "id": posting_id,
            "jobAdId": f"ad-{posting_id}",
            "name": title,
            "releasedDate": "2026-09-20T00:00:00Z",
            "company": {"name": "NCS"},
            "location": {"city": "Singapore", "country": "sg"},
            "typeOfEmployment": {"label": "Full-time"},
        }

    def _known_row(self):
        detail = self._detail()
        return {
            "source": "smartrecruiters",
            "source_job_id": "NCS3:1",
            "source_platform": "smartrecruiters",
            "title": "Software Engineer",
            "company": "NCS",
            "description": "Job description\nBuild production software systems.",
            "location": "Singapore, sg",
            "source_url": "https://jobs.smartrecruiters.com/NCS3/1",
            "apply_url": "",
            "posted_at": "2026-09-20T00:00:00Z",
            "expires_at": "",
            "salary_min": None,
            "salary_max": None,
            "salary_currency": "",
            "salary_period": "",
            "employment_type": "Full-time",
            "seniority": "",
            "experience_years_min": None,
            "experience_years_max": None,
            "raw_payload_json": json.dumps(detail),
        }

    def test_smartrecruiters_reuses_unchanged_known_detail(self):
        client = FakeClient([self._summary()])
        source = SmartRecruitersSource("NCS3", company_name="NCS", client=client)
        jobs = source.fetch(
            SearchSpec(query="", max_pages=1, page_size=100),
            known_jobs={"NCS3:1": self._known_row()},
        )
        self.assertEqual(len(jobs), 1)
        self.assertEqual(source.detail_reused_count, 1)
        self.assertEqual(source.detail_fetched_count, 0)
        self.assertEqual(len(client.calls), 1)

    def test_smartrecruiters_changed_summary_fetches_detail(self):
        changed_summary = self._summary(title="Senior Software Engineer")
        detail = self._detail(title="Senior Software Engineer")
        client = FakeClient([changed_summary], {"1": detail})
        source = SmartRecruitersSource("NCS3", company_name="NCS", client=client)
        jobs = source.fetch(
            SearchSpec(query="", max_pages=1, page_size=100),
            known_jobs={"NCS3:1": self._known_row()},
        )
        self.assertEqual(len(jobs), 1)
        self.assertEqual(source.detail_fetched_count, 1)
        self.assertEqual(source.detail_reused_count, 0)
        self.assertEqual(len(client.calls), 2)

    def test_force_full_refresh_fetches_known_detail(self):
        client = FakeClient([self._summary()], {"1": self._detail()})
        source = SmartRecruitersSource("NCS3", company_name="NCS", client=client)
        source.fetch(
            SearchSpec(query="", max_pages=1, page_size=100),
            known_jobs={"NCS3:1": self._known_row()},
            force_detail_refresh=True,
        )
        self.assertEqual(source.detail_fetched_count, 1)
        self.assertEqual(source.detail_reused_count, 0)

    def test_target_selection_narrows_saved_registry(self):
        saved = [
            {"ats_identifier": "NCS3", "company_name": "NCS"},
            {"ats_identifier": "Grab", "company_name": "Grab"},
        ]
        with patch("job_discovery.pipeline.list_target_companies", return_value=saved):
            targets = _targets(
                {"targets": {}},
                "smartrecruiters",
                overrides=None,
                target_selection={"smartrecruiters": ["NCS3"]},
            )
        self.assertEqual(targets, [{"identifier": "NCS3", "company": "NCS"}])

    def test_recent_skip_is_query_sensitive_for_broad_sources(self):
        source = CareersGovSource(client=FakeClient([]))
        spec = SearchSpec(query="Software Engineer")
        self.assertFalse(
            _can_reuse_recent_run(
                source,
                {"query": "AI Engineer"},
                2.0,
                spec,
                min_interval=15,
                force_full_refresh=False,
            )
        )
        self.assertTrue(
            _can_reuse_recent_run(
                source,
                {"query": "Software Engineer"},
                2.0,
                spec,
                min_interval=15,
                force_full_refresh=False,
            )
        )

    def test_recent_skip_is_query_independent_for_ats_sources(self):
        source = SmartRecruitersSource("NCS3", company_name="NCS", client=FakeClient([]))
        self.assertTrue(
            _can_reuse_recent_run(
                source,
                {"query": "AI Engineer"},
                2.0,
                SearchSpec(query="Software Engineer"),
                min_interval=15,
                force_full_refresh=False,
            )
        )

    def test_blank_target_selection_keeps_all_saved_targets(self):
        saved = [
            {"ats_identifier": "NCS3", "company_name": "NCS"},
            {"ats_identifier": "Grab", "company_name": "Grab"},
        ]
        with patch("job_discovery.pipeline.list_target_companies", return_value=saved):
            targets = _targets(
                {"targets": {}},
                "smartrecruiters",
                overrides=None,
                target_selection={},
            )
        self.assertEqual(len(targets), 2)


if __name__ == "__main__":
    unittest.main()

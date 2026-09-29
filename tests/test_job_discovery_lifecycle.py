from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from database import job_discovery_manager as manager
from job_discovery.models import NormalizedJob, SearchSpec
from job_discovery.sources.greenhouse import GreenhouseSource
from job_discovery.sources.lever import LeverSource
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


class JobDiscoveryLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.db_path = Path(self.tempdir.name) / "applications.db"
        self.patch = patch.object(manager, "DB_PATH", self.db_path)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        manager.init_job_discovery_schema()

    def _job(
        self,
        source_job_id: str,
        description: str = "Build Python APIs",
        expires_at: str = "",
    ) -> NormalizedJob:
        return NormalizedJob(
            source="greenhouse",
            source_job_id=source_job_id,
            title="Backend Engineer",
            company="Example",
            description=description,
            location="Singapore",
            expires_at=expires_at,
            raw_payload={"description": description},
        )

    def test_new_changed_and_unchanged_events(self) -> None:
        first = manager.upsert_discovered_jobs(
            [self._job("example:1")],
            source_scope="greenhouse:example",
        )
        self.assertEqual(first["new"], 1)
        row = manager.list_discovered_jobs()[0]
        self.assertEqual(row["lifecycle_status"], "active")
        self.assertEqual(row["last_event"], "new")

        second = manager.upsert_discovered_jobs(
            [self._job("example:1")],
            source_scope="greenhouse:example",
        )
        self.assertEqual(second["unchanged"], 1)
        self.assertEqual(manager.list_discovered_jobs()[0]["last_event"], "unchanged")

        third = manager.upsert_discovered_jobs(
            [self._job("example:1", "Build Python and FastAPI services")],
            source_scope="greenhouse:example",
        )
        self.assertEqual(third["changed"], 1)
        row = manager.list_discovered_jobs()[0]
        self.assertEqual(row["last_event"], "changed")
        self.assertTrue(row["last_changed_at"])

    def test_complete_scope_can_mark_missing_removed_and_reactivate(self) -> None:
        manager.upsert_discovered_jobs(
            [self._job("example:1"), self._job("example:2")],
            source_scope="greenhouse:example",
        )
        removed = manager.mark_missing_jobs_removed(
            source_scope="greenhouse:example",
            seen_source_job_ids=["example:1"],
        )
        self.assertEqual(removed, 1)
        rows = {row["source_job_id"]: row for row in manager.list_discovered_jobs()}
        self.assertEqual(rows["example:2"]["lifecycle_status"], "removed")
        self.assertEqual(rows["example:2"]["last_event"], "removed")

        stats = manager.upsert_discovered_jobs(
            [self._job("example:2")],
            source_scope="greenhouse:example",
        )
        self.assertEqual(stats["reactivated"], 1)
        rows = {row["source_job_id"]: row for row in manager.list_discovered_jobs()}
        self.assertEqual(rows["example:2"]["lifecycle_status"], "active")
        self.assertEqual(rows["example:2"]["last_event"], "reactivated")
        self.assertIsNone(rows["example:2"]["removed_at"])

    def test_unscoped_v1_rows_are_not_removed_during_migration(self) -> None:
        manager.upsert_discovered_jobs([self._job("legacy:1")])
        removed = manager.mark_missing_jobs_removed(
            source_scope="greenhouse:example",
            seen_source_job_ids=[],
        )
        self.assertEqual(removed, 0)
        self.assertEqual(manager.list_discovered_jobs()[0]["lifecycle_status"], "active")

    def test_explicit_expiry_marks_job_expired(self) -> None:
        manager.upsert_discovered_jobs(
            [self._job("example:1", expires_at="2026-09-20T00:00:00Z")],
            source_scope="greenhouse:example",
        )
        changed = manager.mark_expired_jobs(
            now=datetime(2026, 9, 21, tzinfo=timezone.utc)
        )
        self.assertEqual(changed, 1)
        row = manager.list_discovered_jobs()[0]
        self.assertEqual(row["lifecycle_status"], "expired")
        self.assertEqual(row["last_event"], "expired")

    def test_run_diagnostics_store_removed_and_reactivated_counts(self) -> None:
        manager.record_discovery_run(
            source_key="greenhouse:example",
            query="AI",
            status="ok",
            fetched_count=4,
            new_count=1,
            changed_count=1,
            unchanged_count=1,
            reactivated_count=1,
            removed_count=2,
            started_at="2026-09-21T10:00:00",
            finished_at="2026-09-21T10:00:01",
        )
        run = manager.get_recent_discovery_runs()[0]
        self.assertEqual(run["reactivated_count"], 1)
        self.assertEqual(run["removed_count"], 2)

    def test_greenhouse_complete_snapshot_is_not_limited_by_search_query(self) -> None:
        client = FakeClient({
            "jobs": [{
                "id": 42,
                "title": "Backend Engineer",
                "company_name": "Example",
                "content": "<p>Build Python services.</p>",
                "location": {"name": "Singapore"},
                "absolute_url": "https://boards.greenhouse.io/example/jobs/42",
            }]
        })
        source = GreenhouseSource("example", client=client)
        jobs = source.fetch(SearchSpec(query="Machine Learning", max_pages=1))
        self.assertEqual(len(jobs), 1)
        self.assertTrue(source.fetch_complete)

    def test_lever_short_page_is_complete_snapshot(self) -> None:
        client = FakeClient([{
            "id": "lever-1",
            "text": "Backend Engineer",
            "descriptionPlain": "Build Python backend systems.",
            "categories": {"location": "Singapore"},
        }])
        source = LeverSource("example", client=client)
        jobs = source.fetch(SearchSpec(query="Machine Learning", max_pages=1))
        self.assertEqual(len(jobs), 1)
        self.assertTrue(source.fetch_complete)

    def test_smartrecruiters_refresh_does_not_send_search_query(self) -> None:
        client = SequenceClient([
            {"content": [{"id": "sr-1", "name": "Backend Engineer"}]},
            {
                "id": "sr-1",
                "name": "Backend Engineer",
                "company": {"name": "Example"},
                "location": {"city": "Singapore", "country": "Singapore"},
                "jobAd": {
                    "sections": {"jobDescription": "Build Python services."}
                },
            },
        ])
        source = SmartRecruitersSource("example", client=client)
        jobs = source.fetch(SearchSpec(query="Machine Learning", max_pages=1))
        self.assertEqual(len(jobs), 1)
        self.assertIsNone(client.calls[0][1]["q"])
        self.assertTrue(source.fetch_complete)


if __name__ == "__main__":
    unittest.main()

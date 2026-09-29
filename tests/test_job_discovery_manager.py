from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database import job_discovery_manager as manager
from job_discovery.models import NormalizedJob


class JobDiscoveryManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.db_path = Path(self.tempdir.name) / "applications.db"
        self.patch = patch.object(manager, "DB_PATH", self.db_path)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        manager.init_job_discovery_schema()

    def _job(self, description: str = "Build Python APIs") -> NormalizedJob:
        return NormalizedJob(
            source="test",
            source_job_id="job-1",
            title="Backend Engineer",
            company="Example",
            description=description,
            location="Singapore",
            raw_payload={"description": description},
        )

    def test_upsert_tracks_new_unchanged_and_changed(self) -> None:
        first = manager.upsert_discovered_jobs([self._job()])
        second = manager.upsert_discovered_jobs([self._job()])
        third = manager.upsert_discovered_jobs([self._job("Build Python and FastAPI services")])
        self.assertEqual(first["new"], 1)
        self.assertEqual(second["unchanged"], 1)
        self.assertEqual(third["changed"], 1)
        rows = manager.list_discovered_jobs()
        self.assertEqual(len(rows), 1)
        self.assertIn("FastAPI", rows[0]["description"])

    def test_run_diagnostics_are_persisted(self) -> None:
        manager.record_discovery_run(
            source_key="test",
            query="backend",
            status="ok",
            fetched_count=2,
            new_count=1,
            unchanged_count=1,
            started_at="2026-09-21T10:00:00",
            finished_at="2026-09-21T10:00:01",
        )
        runs = manager.get_recent_discovery_runs()
        self.assertEqual(runs[0]["source_key"], "test")
        self.assertEqual(runs[0]["fetched_count"], 2)


if __name__ == "__main__":
    unittest.main()

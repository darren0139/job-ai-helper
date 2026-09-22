from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database import job_discovery_manager as manager
from job_discovery import pipeline


class JobDiscoveryTargetCompanyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.db_path = Path(self.tempdir.name) / "applications.db"
        self.patch = patch.object(manager, "DB_PATH", self.db_path)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        manager.init_job_discovery_schema()

    def test_upsert_update_toggle_and_delete_target(self) -> None:
        target_id = manager.upsert_target_company(
            company_name="Example",
            ats_provider="lever",
            ats_identifier="example",
            careers_url="https://jobs.lever.co/example",
            enabled=True,
        )
        same_id = manager.upsert_target_company(
            company_name="Example SG",
            ats_provider="lever",
            ats_identifier="example",
            enabled=True,
        )
        self.assertEqual(target_id, same_id)

        rows = manager.list_target_companies(include_disabled=True)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["company_name"], "Example SG")
        self.assertTrue(rows[0]["enabled"])

        manager.set_target_company_enabled(target_id, False)
        self.assertEqual(manager.list_target_companies(), [])
        disabled = manager.list_target_companies(include_disabled=True)
        self.assertFalse(disabled[0]["enabled"])

        manager.delete_target_company(target_id)
        self.assertEqual(manager.list_target_companies(include_disabled=True), [])

    def test_identifier_can_be_extracted_from_full_careers_url(self) -> None:
        target_id = manager.upsert_target_company(
            company_name="Example",
            ats_provider="ashby",
            ats_identifier="https://jobs.ashbyhq.com/Example/jobs/abc123",
        )
        rows = manager.list_target_companies(include_disabled=True)
        self.assertEqual(rows[0]["id"], target_id)
        self.assertEqual(rows[0]["ats_identifier"], "Example")

    def test_pipeline_prefers_override_then_registry_then_config(self) -> None:
        config = {
            "targets": {
                "greenhouse": [{"identifier": "config-board", "company": "Config Co"}]
            }
        }

        config_only = pipeline._targets(config, "greenhouse", None)
        self.assertEqual(config_only[0]["identifier"], "config-board")

        manager.upsert_target_company(
            company_name="Saved Co",
            ats_provider="greenhouse",
            ats_identifier="saved-board",
        )
        saved = pipeline._targets(config, "greenhouse", None)
        self.assertEqual(saved, [{"identifier": "saved-board", "company": "Saved Co"}])

        override = pipeline._targets(
            config,
            "greenhouse",
            {"greenhouse": ["one-off-board"]},
        )
        self.assertEqual(
            override,
            [{"identifier": "one-off-board", "company": ""}],
        )

    def test_disabled_registry_target_does_not_reactivate_v1_config(self) -> None:
        config = {
            "targets": {
                "smartrecruiters": [
                    {"identifier": "legacy-config", "company": "Legacy Co"}
                ]
            }
        }
        target_id = manager.upsert_target_company(
            company_name="Disabled Co",
            ats_provider="smartrecruiters",
            ats_identifier="disabled-co",
        )
        manager.set_target_company_enabled(target_id, False)

        targets = pipeline._targets(config, "smartrecruiters", None)
        self.assertEqual(targets, [])


if __name__ == "__main__":
    unittest.main()

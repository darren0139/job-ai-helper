from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from taxonomy_discovery.triage import (
    _load_compatible_snapshots,
    _load_default_discovery_report,
)


class TaxonomyDiscoveryAppIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.versions = {
            "match_version": "job-match-snapshot-v2.1.0",
            "scoring_version": "stable-evidence-v1.7-phase6d12",
            "taxonomy_version": "phase6d-capability-taxonomy-v1.4",
        }

    def test_default_loader_uses_real_keyword_contracts(self) -> None:
        snapshots = [
            {
                "id": 1,
                "discovered_job_id": 632,
            }
        ]
        discovery_report = {
            **self.versions,
            "candidates": [],
            "candidate_count": 0,
        }

        with (
            patch(
                "job_discovery.matching.current_match_versions",
                return_value=dict(self.versions),
            ),
            patch(
                "database.job_match_manager."
                "list_latest_compatible_job_match_snapshots",
                return_value=snapshots,
            ) as snapshot_loader,
            patch(
                "taxonomy_discovery.observations."
                "build_discovery_report",
                return_value=discovery_report,
            ) as discovery_builder,
        ):
            result = _load_default_discovery_report()

        self.assertEqual(result, discovery_report)
        snapshot_loader.assert_called_once_with(
            match_version=self.versions["match_version"],
            scoring_version=self.versions["scoring_version"],
            taxonomy_version=self.versions["taxonomy_version"],
        )
        discovery_builder.assert_called_once_with(
            snapshots,
            match_version=self.versions["match_version"],
            scoring_version=self.versions["scoring_version"],
            taxonomy_version=self.versions["taxonomy_version"],
        )

    def test_secondary_snapshot_loader_uses_keyword_contract(self) -> None:
        snapshots = [
            {
                "id": 2,
                "discovered_job_id": 644,
            }
        ]

        with patch(
            "database.job_match_manager."
            "list_latest_compatible_job_match_snapshots",
            return_value=snapshots,
        ) as snapshot_loader:
            result = _load_compatible_snapshots(
                dict(self.versions)
            )

        self.assertEqual(result, snapshots)
        snapshot_loader.assert_called_once_with(
            match_version=self.versions["match_version"],
            scoring_version=self.versions["scoring_version"],
            taxonomy_version=self.versions["taxonomy_version"],
        )

    def test_main_app_contains_capability_discovery_route(self) -> None:
        root = Path(__file__).resolve().parents[1]
        app_text = (root / "app.py").read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "from taxonomy_discovery.review_ui import "
            "render_capability_discovery_review",
            app_text,
        )
        self.assertIn(
            '"Capability Discovery"',
            app_text,
        )
        self.assertIn(
            'elif page == "Capability Discovery":',
            app_text,
        )
        self.assertIn(
            "render_capability_discovery_review()",
            app_text,
        )

    def test_review_ui_has_no_deprecated_container_width(self) -> None:
        root = Path(__file__).resolve().parents[1]
        ui_text = (
            root / "taxonomy_discovery" / "review_ui.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn("use_container_width", ui_text)
        self.assertIn('width="stretch"', ui_text)


if __name__ == "__main__":
    unittest.main()

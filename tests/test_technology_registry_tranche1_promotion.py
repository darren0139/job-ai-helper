from __future__ import annotations

import json
import unittest
from pathlib import Path

from taxonomy_discovery.technology_registry import (
    get_default_registry,
    load_registry,
)


class TechnologyRegistryTranche1PromotionTests(unittest.TestCase):
    def setUp(self) -> None:
        get_default_registry.cache_clear()

    def tearDown(self) -> None:
        get_default_registry.cache_clear()

    def test_registry_is_promoted_v1_1_with_expected_size(self) -> None:
        registry = get_default_registry()
        self.assertEqual(
            registry.version,
            "technology-registry-v1.1",
        )
        self.assertEqual(len(registry.entries), 27)

    def test_tranche1_mappings_are_present(self) -> None:
        by_id = get_default_registry().by_id()
        expected = {
            "apache.pulsar": "realtime.messaging_streaming",
            "circleci": "devops.ci_cd",
            "docker.compose": "devops.containerisation",
            "github.actions": "devops.ci_cd",
            "gitlab.ci_cd": "devops.ci_cd",
            "grafana": "devops.observability",
            "jenkins": "devops.ci_cd",
            "nats": "realtime.messaging_streaming",
            "opentelemetry": "devops.observability",
            "prometheus": "devops.observability",
            "rabbitmq": "realtime.messaging_streaming",
            "svelte": "frontend.ui_development",
            "vue.js": "frontend.ui_development",
        }

        for technology_id, capability_id in expected.items():
            with self.subTest(technology_id=technology_id):
                entry = by_id[technology_id]
                approved = [
                    row
                    for row in entry.get(
                        "capability_relationships",
                        [],
                    )
                    if row.get("relationship_type")
                    == "maps_to_capability"
                    and row.get("status") == "approved"
                ]
                self.assertEqual(len(approved), 1)
                self.assertEqual(
                    approved[0]["capability_id"],
                    capability_id,
                )

    def test_recognized_unmapped_entries_stay_unmapped(self) -> None:
        by_id = get_default_registry().by_id()
        for technology_id in (
            "keycloak",
            "microservices",
            "mongodb",
            "node.js",
        ):
            with self.subTest(technology_id=technology_id):
                self.assertIn(technology_id, by_id)
                approved = [
                    row
                    for row in by_id[technology_id].get(
                        "capability_relationships",
                        [],
                    )
                    if row.get("relationship_type")
                    == "maps_to_capability"
                    and row.get("status") == "approved"
                ]
                self.assertEqual(approved, [])

    def test_registry_file_validates_through_runtime_loader(self) -> None:
        path = (
            Path(__file__).resolve().parents[1]
            / "taxonomy"
            / "technology_registry_v1.json"
        )
        registry = load_registry(path)
        self.assertEqual(
            registry.version,
            "technology-registry-v1.1",
        )

    def test_promotion_manifest_matches_registry(self) -> None:
        root = Path(__file__).resolve().parents[1]
        manifest_path = (
            root
            / "taxonomy"
            / "research"
            / "technology_registry_tranche1_promotion_v1.json"
        )
        manifest = json.loads(
            manifest_path.read_text(encoding="utf-8")
        )
        self.assertEqual(
            manifest["promoted_registry_version"],
            "technology-registry-v1.1",
        )
        self.assertEqual(
            manifest["promoted_entry_count"],
            13,
        )
        self.assertEqual(len(manifest["applied_proposal_ids"]), 13)
        self.assertEqual(manifest["skipped"], [])


if __name__ == "__main__":
    unittest.main()

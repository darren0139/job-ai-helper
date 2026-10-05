from __future__ import annotations

import unittest

from taxonomy_discovery.assisted_review import (
    build_deterministic_suggestion,
)
from taxonomy_discovery.technology_registry import (
    get_default_registry,
    registry_rows,
    resolve_requirement_text,
)


class TechnologyRegistryTests(unittest.TestCase):
    def test_registry_loads_and_targets_exist(self) -> None:
        registry = get_default_registry()
        self.assertEqual(
            registry.version,
            "technology-registry-v1.2",
        )
        self.assertGreaterEqual(len(registry.entries), 10)

    def test_cpp_governed_mapping_is_preserved(self) -> None:
        result = resolve_requirement_text("Experience with C++")
        self.assertEqual(result["status"], "resolved")
        self.assertEqual(result["technology_id"], "focused.cedb1bac7efcd7db")
        self.assertEqual(result["capability_id"], "language.modern_cpp")

    def test_kafka_resolves_to_existing_messaging_capability(self) -> None:
        result = resolve_requirement_text("Experience with Kafka")
        self.assertEqual(result["status"], "resolved")
        self.assertEqual(
            result["technology_id"],
            "apache.kafka",
        )
        self.assertEqual(
            result["capability_id"],
            "realtime.messaging_streaming",
        )

    def test_podman_resolves_to_containerisation(self) -> None:
        result = resolve_requirement_text("Experience with Podman")
        self.assertEqual(result["status"], "resolved")
        self.assertEqual(
            result["capability_id"],
            "devops.containerisation",
        )

    def test_react_and_angular_resolve_to_frontend(self) -> None:
        react = resolve_requirement_text("Experience with React")
        angular = resolve_requirement_text(
            "Proficiency in web technologies such as Angular"
        )
        self.assertEqual(
            react["capability_id"],
            "frontend.ui_development",
        )
        self.assertEqual(
            angular["capability_id"],
            "frontend.ui_development",
        )

    def test_mongodb_is_recognized_but_not_overmapped(self) -> None:
        result = resolve_requirement_text("Experience with MongoDB")
        self.assertEqual(result["status"], "recognized_unmapped")
        self.assertIsNone(result["capability_id"])

    def test_csharp_is_not_mapped_to_cpp(self) -> None:
        result = resolve_requirement_text("Experience with C#")
        self.assertEqual(result["status"], "recognized_unmapped")
        self.assertIsNone(result["capability_id"])

    def test_registry_rows_separate_mapped_and_unmapped(self) -> None:
        rows = registry_rows()
        statuses = {row["mapping_status"] for row in rows}
        self.assertIn("mapped", statuses)
        self.assertIn("recognized_unmapped", statuses)

    def test_registry_resolved_candidate_needs_no_human_suggestion(self) -> None:
        candidate = {
            "candidate_id": "taxcand_kafka",
            "observed_terms": ["Experience with Kafka"],
            "technology_registry_resolution": {
                "status": "resolved",
                "technology_id": "apache.kafka",
                "technology_label": "Apache Kafka",
                "capability_id": "realtime.messaging_streaming",
            },
        }
        suggestion = build_deterministic_suggestion(candidate)
        self.assertEqual(
            suggestion["routing"],
            "registry_resolved",
        )
        self.assertIsNone(suggestion["suggested_status"])


if __name__ == "__main__":
    unittest.main()

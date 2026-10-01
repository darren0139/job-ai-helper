from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from taxonomy_discovery.broad_mining_candidates import (
    BROAD_MINING_CANDIDATE_VERSION,
    STATUS_ALREADY_KNOWN,
    STATUS_AMBIGUOUS,
    STATUS_POSSIBLE_NEW,
    build_broad_mining_candidate_report,
    extract_broad_mining_candidates,
)


def _write_registry(tmp: str, entries: list[dict]) -> Path:
    path = Path(tmp) / "registry.json"
    path.write_text(
        json.dumps({"entries": entries}),
        encoding="utf-8",
    )
    return path


def _result(*technologies: dict, domain: str = "Messaging") -> dict:
    return {
        "provider": "tavily",
        "endpoint": "research",
        "provider_request_id": "req-1",
        "target_id": "target-1",
        "seed_id": "messaging_streaming",
        "domain": domain,
        "structured_output": {
            "technologies": list(technologies),
        },
    }


class BroadMiningCandidateTests(unittest.TestCase):
    def test_exact_candidate_name_only_prevents_prose_false_positives(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = _write_registry(
                tmp,
                [
                    {
                        "technology_id": "nats",
                        "label": "NATS",
                        "aliases": ["NATS"],
                        "entry_kind": "platform",
                        "status": "approved",
                    },
                    {
                        "technology_id": "microservices",
                        "label": "Microservices",
                        "aliases": ["Microservices"],
                        "status": "approved",
                    },
                    {
                        "technology_id": "mqtt",
                        "label": "MQTT",
                        "aliases": ["MQTT"],
                        "status": "approved",
                    },
                ],
            )

            candidates = extract_broad_mining_candidates(
                _result(
                    {
                        "canonical_name": "NATS",
                        "entity_type": "message broker",
                        "primary_purpose": (
                            "Messaging for cloud-native microservices "
                            "with MQTT-adjacent integrations"
                        ),
                        "adoption_evidence": "Widely used",
                    }
                ),
                registry_path=registry,
            )

            self.assertEqual(len(candidates), 1)
            row = candidates[0]
            self.assertEqual(row["canonical_name"], "NATS")
            self.assertEqual(row["status"], STATUS_ALREADY_KNOWN)
            self.assertEqual(
                [match["technology_id"] for match in row["registry_matches"]],
                ["nats"],
            )

    def test_unknown_structured_name_is_possible_new_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = _write_registry(tmp, [])
            candidates = extract_broad_mining_candidates(
                _result(
                    {
                        "canonical_name": "Google Cloud Pub/Sub",
                        "entity_type": "pub/sub service",
                        "primary_purpose": "Managed messaging",
                        "adoption_evidence": "Broad production use",
                        "authoritative_source_urls": [
                            "https://cloud.google.com/pubsub"
                        ],
                    }
                ),
                registry_path=registry,
            )
            self.assertEqual(len(candidates), 1)
            row = candidates[0]
            self.assertEqual(row["status"], STATUS_POSSIBLE_NEW)
            self.assertEqual(
                row["supporting_source_urls"],
                ["https://cloud.google.com/pubsub"],
            )
            self.assertNotIn(
                "authoritative_source_urls",
                row,
            )

    def test_duplicate_exact_name_merges_across_domains(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = _write_registry(tmp, [])
            first = _result(
                {
                    "canonical_name": "Example Tech",
                    "entity_type": "broker",
                    "primary_purpose": "Messaging",
                    "adoption_evidence": "Evidence A",
                },
                domain="Messaging",
            )
            second = _result(
                {
                    "canonical_name": "example   tech",
                    "entity_type": "platform",
                    "primary_purpose": "Streaming",
                    "adoption_evidence": "Evidence B",
                },
                domain="Data engineering",
            )
            second["provider_request_id"] = "req-2"
            second["seed_id"] = "data_engineering"

            candidates = extract_broad_mining_candidates(
                [first, second],
                registry_path=registry,
            )
            self.assertEqual(len(candidates), 1)
            row = candidates[0]
            self.assertEqual(
                set(row["domains"]),
                {"Messaging", "Data engineering"},
            )
            self.assertEqual(
                set(row["provider_request_ids"]),
                {"req-1", "req-2"},
            )

    def test_duplicate_registry_alias_is_ambiguous(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = _write_registry(
                tmp,
                [
                    {
                        "technology_id": "one",
                        "label": "Example",
                        "aliases": ["Shared Alias"],
                        "status": "approved",
                    },
                    {
                        "technology_id": "two",
                        "label": "Other",
                        "aliases": ["Shared Alias"],
                        "status": "approved",
                    },
                ],
            )
            candidates = extract_broad_mining_candidates(
                _result(
                    {
                        "canonical_name": "Shared Alias",
                        "entity_type": "tool",
                        "primary_purpose": "Example",
                        "adoption_evidence": "Example",
                    }
                ),
                registry_path=registry,
            )
            self.assertEqual(
                candidates[0]["status"],
                STATUS_AMBIGUOUS,
            )
            self.assertEqual(
                len(candidates[0]["registry_matches"]),
                2,
            )

    def test_report_is_non_mutating_and_versioned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = _write_registry(tmp, [])
            report = build_broad_mining_candidate_report(
                _result(
                    {
                        "canonical_name": "New Tech",
                        "entity_type": "tool",
                        "primary_purpose": "Example",
                        "adoption_evidence": "Example",
                    }
                ),
                registry_path=registry,
            )
            self.assertEqual(
                report["candidate_version"],
                BROAD_MINING_CANDIDATE_VERSION,
            )
            self.assertFalse(
                report["matching_contract"]["prose_scanning"]
            )
            self.assertFalse(
                report["governance"]["proposal_creation"]
            )
            self.assertEqual(
                report["governance"]["registry_mutations"],
                0,
            )
            self.assertFalse(
                report["governance"]["scoring_influence"]
            )


if __name__ == "__main__":
    unittest.main()

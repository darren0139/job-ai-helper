from __future__ import annotations

import unittest
from unittest.mock import patch

from taxonomy_discovery.assisted_review import (
    build_deterministic_suggestion,
)
from taxonomy_discovery.research_proposals import (
    PROPOSAL_CONTRACT_VERSION,
    build_registry_vnext_preview,
    detect_possible_compound_requirement,
    validate_proposal_bundle,
)


class TechnologyRegistryResearchProposalTests(unittest.TestCase):
    def _taxonomy(self):
        class _Taxonomy:
            version = "phase6d-capability-taxonomy-v1.4"
            capabilities = (
                {
                    "capability_id": "realtime.messaging_streaming",
                    "label": "Real-time messaging and streaming",
                    "domain": "distributed_systems",
                },
            )

            def by_id(self):
                return {
                    "realtime.messaging_streaming": (
                        self.capabilities[0]
                    )
                }

        return _Taxonomy()

    def _registry(self):
        class _Registry:
            version = "technology-registry-v1.0-bootstrap"

        return _Registry()

    def test_compound_image_processing_database_is_flagged(self) -> None:
        candidate = {
            "candidate_id": "taxcand_compound",
            "observed_terms": [
                "A good understanding of image processing and databases is an advantage"
            ],
            "observation_contexts": [
                {"is_atomic": False}
            ],
            "technology_registry_resolution": {
                "status": "unresolved"
            },
        }

        result = detect_possible_compound_requirement(candidate)
        self.assertTrue(result["possible"])
        self.assertIn("image_processing", result["hints"])
        self.assertIn("database", result["hints"])

        suggestion = build_deterministic_suggestion(candidate)
        self.assertEqual(
            suggestion["suggested_status"],
            "decomposition_issue",
        )
        self.assertEqual(suggestion["confidence"], "medium")

    def test_safe_mapping_requires_source_and_current_target(self) -> None:
        bundle = {
            "proposal_bundle_version": PROPOSAL_CONTRACT_VERSION,
            "taxonomy_version": "phase6d-capability-taxonomy-v1.4",
            "registry_version": "technology-registry-v1.0-bootstrap",
            "proposals": [
                {
                    "proposal_id": "prop_rabbitmq",
                    "technology_id": "rabbitmq",
                    "label": "RabbitMQ",
                    "entry_kind": "product",
                    "aliases": ["RabbitMQ"],
                    "proposal_classification": "safe_mapping_candidate",
                    "proposed_capability_id": "realtime.messaging_streaming",
                    "relationship_type": "maps_to_capability",
                    "confidence": 0.95,
                    "summary": "Messaging broker candidate.",
                    "sources": [],
                }
            ],
        }

        with (
            patch(
                "taxonomy_discovery.research_proposals.get_default_taxonomy",
                return_value=self._taxonomy(),
            ),
            patch(
                "taxonomy_discovery.research_proposals.get_default_registry",
                return_value=self._registry(),
            ),
        ):
            with self.assertRaises(ValueError):
                validate_proposal_bundle(bundle)

            bundle["proposals"][0]["sources"] = [
                {
                    "title": "RabbitMQ docs",
                    "url": "https://www.rabbitmq.com/docs",
                    "publisher": "RabbitMQ",
                }
            ]
            cleaned = validate_proposal_bundle(bundle)

        self.assertEqual(len(cleaned["proposals"]), 1)

    def test_vnext_preview_only_applies_explicit_approval(self) -> None:
        proposals = [
            {
                "proposal_id": "prop_rabbitmq",
                "proposal_bundle_version": PROPOSAL_CONTRACT_VERSION,
                "technology_id": "rabbitmq",
                "label": "RabbitMQ",
                "entry_kind": "product",
                "aliases": ["RabbitMQ"],
                "proposal_classification": "safe_mapping_candidate",
                "proposed_capability_id": "realtime.messaging_streaming",
                "relationship_type": "maps_to_capability",
                "confidence": 0.95,
                "summary": "Messaging broker.",
                "sources": [
                    {
                        "title": "RabbitMQ docs",
                        "url": "https://www.rabbitmq.com/docs",
                        "publisher": "RabbitMQ",
                    }
                ],
            }
        ]
        reviews = [
            {
                "proposal_id": "prop_rabbitmq",
                "proposal_bundle_version": PROPOSAL_CONTRACT_VERSION,
                "decision": "keep_unmapped",
            }
        ]

        with patch(
            "taxonomy_discovery.research_proposals.get_default_taxonomy",
            return_value=self._taxonomy(),
        ):
            preview = build_registry_vnext_preview(
                proposals,
                reviews,
            )

        self.assertEqual(
            preview["applied_proposal_ids"],
            [],
        )


if __name__ == "__main__":
    unittest.main()

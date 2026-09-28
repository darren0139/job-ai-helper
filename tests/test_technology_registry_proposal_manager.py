from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database.technology_registry_proposal_manager import (
    import_proposal_bundle,
    list_proposal_reviews,
    list_proposals,
    save_proposal_review,
)
from taxonomy_discovery.research_proposals import (
    PROPOSAL_CONTRACT_VERSION,
)


class TechnologyRegistryProposalManagerTests(unittest.TestCase):
    def _taxonomy(self):
        class _Taxonomy:
            version = "phase6d-capability-taxonomy-v1.4"

            def by_id(self):
                return {
                    "realtime.messaging_streaming": {
                        "capability_id": "realtime.messaging_streaming"
                    }
                }

        return _Taxonomy()

    def _registry(self):
        class _Registry:
            version = "technology-registry-v1.0-bootstrap"

        return _Registry()

    def _bundle(self):
        return {
            "proposal_bundle_version": PROPOSAL_CONTRACT_VERSION,
            "taxonomy_version": "phase6d-capability-taxonomy-v1.4",
            "registry_version": "technology-registry-v1.0-bootstrap",
            "research_method": "unit-test",
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
                    "sources": [
                        {
                            "title": "RabbitMQ docs",
                            "url": "https://www.rabbitmq.com/docs",
                            "publisher": "RabbitMQ",
                        }
                    ],
                }
            ],
        }

    def test_import_and_review_persist_cleanly_on_windows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "proposals.sqlite3"

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
                count = import_proposal_bundle(
                    self._bundle(),
                    db_path=db_path,
                )

            self.assertEqual(count, 1)
            proposals = list_proposals(db_path=db_path)
            self.assertEqual(
                proposals[0]["proposal_id"],
                "prop_rabbitmq",
            )

            save_proposal_review(
                proposal_id="prop_rabbitmq",
                proposal_bundle_version=PROPOSAL_CONTRACT_VERSION,
                decision="approve_mapping",
                notes="approved test",
                db_path=db_path,
            )
            reviews = list_proposal_reviews(db_path=db_path)
            self.assertEqual(
                reviews[0]["decision"],
                "approve_mapping",
            )

            changed = self._bundle()
            changed["proposals"][0]["summary"] = (
                "Changed researched proposal content."
            )
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
                import_proposal_bundle(
                    changed,
                    db_path=db_path,
                )

            self.assertEqual(
                list_proposal_reviews(db_path=db_path),
                [],
                "Changed proposal content must invalidate an old approval.",
            )


if __name__ == "__main__":
    unittest.main()

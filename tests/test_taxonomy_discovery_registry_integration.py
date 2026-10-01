from __future__ import annotations

import unittest

from taxonomy_discovery.triage import enrich_discovery_report


class TechnologyRegistryTriageIntegrationTests(unittest.TestCase):
    def _report(self) -> dict:
        return {
            "discovery_version": "capability-taxonomy-discovery-v1",
            "match_version": "job-match-snapshot-v2.1.0",
            "scoring_version": "stable-evidence-v1.7-phase6d12",
            "taxonomy_version": "phase6d-capability-taxonomy-v1.4",
            "candidate_count": 2,
            "candidates": [
                {
                    "candidate_id": "taxcand_kafka",
                    "taxonomy_version": "phase6d-capability-taxonomy-v1.4",
                    "observed_terms": ["Experience with Kafka"],
                    "observations": [
                        {
                            "discovered_job_id": 632,
                            "requirement_id": "req_kafka",
                            "requirement_text": "Experience with Kafka",
                            "match_label": "none",
                        }
                    ],
                },
                {
                    "candidate_id": "taxcand_mongo",
                    "taxonomy_version": "phase6d-capability-taxonomy-v1.4",
                    "observed_terms": ["Experience with MongoDB"],
                    "observations": [
                        {
                            "discovered_job_id": 632,
                            "requirement_id": "req_mongo",
                            "requirement_text": "Experience with MongoDB",
                            "match_label": "none",
                        }
                    ],
                },
            ],
        }

    def test_registry_resolution_reduces_manual_queue_without_mutation(self) -> None:
        enriched = enrich_discovery_report(
            self._report(),
            snapshots=[],
            reviews=[],
        )
        self.assertEqual(
            enriched["technology_registry_version"],
            "technology-registry-v1.1",
        )
        self.assertEqual(
            enriched["registry_resolved_candidate_count"],
            1,
        )
        self.assertEqual(
            enriched["registry_recognized_unmapped_candidate_count"],
            1,
        )
        self.assertEqual(
            enriched["manual_review_queue_count"],
            1,
        )

        kafka, mongo = enriched["candidates"]
        self.assertEqual(
            kafka["technology_registry_resolution"]["capability_id"],
            "realtime.messaging_streaming",
        )
        self.assertEqual(
            kafka["triage"]["status"],
            "unreviewed",
        )
        self.assertEqual(
            mongo["technology_registry_resolution"]["status"],
            "recognized_unmapped",
        )


if __name__ == "__main__":
    unittest.main()

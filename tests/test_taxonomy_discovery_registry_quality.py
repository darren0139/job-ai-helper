from __future__ import annotations

import unittest

from taxonomy_discovery.assisted_review import (
    build_deterministic_suggestion,
)
from taxonomy_discovery.triage import enrich_discovery_report


class TaxonomyDiscoveryRegistryQualityTests(unittest.TestCase):
    def test_lower_lexical_duration_still_routes_to_duration_near_miss(self) -> None:
        candidate = {
            "candidate_id": "taxcand_duration_8y",
            "observed_terms": [
                "At least 8 years of software engineering experience"
            ],
            "technology_registry_resolution": {
                "status": "unresolved",
            },
            "observation_contexts": [
                {
                    "is_atomic": False,
                    "parent_text": (
                        "At least 8 years of software engineering experience"
                    ),
                    "retrieval": {
                        "candidates": [
                            {
                                "capability_id": "experience.duration",
                                "lexical_score": 0.428571,
                            },
                            {
                                "capability_id": "delivery.end_to_end_application",
                                "lexical_score": 0.285714,
                            },
                        ]
                    },
                }
            ],
        }

        suggestion = build_deterministic_suggestion(candidate)

        self.assertEqual(
            suggestion["suggested_status"],
            "existing_taxonomy_near_miss",
        )
        self.assertEqual(
            suggestion["suggested_target_capability_id"],
            "experience.duration",
        )
        self.assertEqual(suggestion["confidence"], "high")

    def test_pending_review_count_drops_after_confirmed_review(self) -> None:
        report = {
            "discovery_version": "capability-taxonomy-discovery-v1",
            "match_version": "job-match-snapshot-v2.1.0",
            "scoring_version": "stable-evidence-v1.7-phase6d12",
            "taxonomy_version": "phase6d-capability-taxonomy-v1.4",
            "candidate_count": 2,
            "candidates": [
                {
                    "candidate_id": "taxcand_duration",
                    "taxonomy_version": "phase6d-capability-taxonomy-v1.4",
                    "observed_terms": [
                        "2-5 years of relevant professional working experience"
                    ],
                    "observations": [
                        {
                            "discovered_job_id": 632,
                            "requirement_id": "req_duration",
                            "requirement_text": (
                                "2-5 years of relevant professional working experience"
                            ),
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
        reviews = [
            {
                "candidate_id": "taxcand_duration",
                "taxonomy_version": "phase6d-capability-taxonomy-v1.4",
                "triage_status": "existing_taxonomy_near_miss",
                "target_capability_id": "experience.duration",
                "notes": "confirmed",
                "reviewed_at": "2026-09-25T10:00:00+00:00",
            }
        ]

        enriched = enrich_discovery_report(
            report,
            snapshots=[],
            reviews=reviews,
        )

        self.assertEqual(
            enriched["manual_review_eligible_candidate_count"],
            2,
        )
        self.assertEqual(
            enriched["human_reviewed_queue_count"],
            1,
        )
        self.assertEqual(
            enriched["pending_human_review_candidate_count"],
            1,
        )
        self.assertEqual(
            enriched["manual_review_queue_count"],
            1,
        )


if __name__ == "__main__":
    unittest.main()

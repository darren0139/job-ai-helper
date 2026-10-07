from __future__ import annotations

import unittest

from taxonomy_discovery.broad_mining_review_assist import (
    BROAD_MINING_REVIEW_ASSIST_VERSION,
    build_broad_mining_review_suggestion,
    validate_ollama_candidate_review,
)


def _candidate(
    *,
    status: str = "possible_new_technology",
    sources: int = 2,
    primary: int = 1,
    secondary: int = 0,
    unclassified: int = 0,
) -> dict:
    return {
        "candidate_id": "tqdmincand_test",
        "canonical_name": "ExampleTech",
        "status": status,
        "entity_type": "platform",
        "supporting_source_urls": [
            f"https://example{i}.com"
            for i in range(sources)
        ],
        "source_authority": {
            "counts": {
                "primary_official": primary,
                "first_party_other_technology": 0,
                "secondary": secondary,
                "unclassified": unclassified,
            },
            "has_primary_official": primary > 0,
        },
    }


class BroadMiningReviewAssistTests(unittest.TestCase):
    def test_primary_multi_source_candidate_is_high_research(
        self,
    ) -> None:
        suggestion = build_broad_mining_review_suggestion(
            _candidate()
        )
        self.assertEqual(
            suggestion["assist_version"],
            BROAD_MINING_REVIEW_ASSIST_VERSION,
        )
        self.assertEqual(
            suggestion["suggested_decision"],
            "research_further",
        )
        self.assertEqual(
            suggestion["confidence"],
            "high",
        )

    def test_ambiguous_registry_match_defers(self) -> None:
        suggestion = build_broad_mining_review_suggestion(
            _candidate(
                status="ambiguous_registry_match"
            )
        )
        self.assertEqual(
            suggestion["suggested_decision"],
            "defer",
        )
        self.assertEqual(
            suggestion["confidence"],
            "high",
        )

    def test_unclassified_only_candidate_defers(self) -> None:
        suggestion = build_broad_mining_review_suggestion(
            _candidate(
                sources=2,
                primary=0,
                unclassified=2,
            )
        )
        self.assertEqual(
            suggestion["suggested_decision"],
            "defer",
        )

    def test_suggestion_is_non_mutating_zero_model(self) -> None:
        governance = build_broad_mining_review_suggestion(
            _candidate()
        )["governance"]
        self.assertEqual(governance["network_calls"], 0)
        self.assertEqual(governance["model_calls"], 0)
        self.assertFalse(
            governance["automatic_persistence"]
        )
        self.assertFalse(
            governance["scoring_influence"]
        )

    def test_ollama_payload_validation(self) -> None:
        validated = validate_ollama_candidate_review(
            {
                "suggested_decision": "defer",
                "confidence": "medium",
                "reasons": ["Evidence is mixed."],
            }
        )
        self.assertEqual(
            validated["suggested_decision"],
            "defer",
        )

    def test_ollama_payload_rejects_unknown_decision(
        self,
    ) -> None:
        with self.assertRaises(ValueError):
            validate_ollama_candidate_review(
                {
                    "suggested_decision": "approve",
                    "confidence": "high",
                }
            )


if __name__ == "__main__":
    unittest.main()

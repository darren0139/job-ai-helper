from __future__ import annotations

import unittest
from unittest.mock import patch

from taxonomy_discovery.research_proposals import (
    ask_local_ai_proposal_review,
    build_proposal_decision_suggestion,
)


class TechnologyRegistryProposalReviewUxTests(unittest.TestCase):
    def _proposal(
        self,
        classification: str,
        *,
        confidence: float = 0.99,
    ) -> dict:
        return {
            "proposal_id": f"prop_{classification}",
            "technology_id": classification.replace("_", "."),
            "label": classification,
            "entry_kind": "tool",
            "aliases": [classification],
            "proposal_classification": classification,
            "proposed_capability_id": (
                "devops.ci_cd"
                if classification == "safe_mapping_candidate"
                else None
            ),
            "relationship_type": (
                "maps_to_capability"
                if classification == "safe_mapping_candidate"
                else None
            ),
            "confidence": confidence,
            "summary": "test",
            "sources": (
                [
                    {
                        "title": "docs",
                        "url": "https://example.com/docs",
                        "publisher": "example",
                    }
                ]
                if classification
                in {
                    "safe_mapping_candidate",
                    "new_capability_candidate",
                }
                else []
            ),
        }

    def test_python_recommendations_cover_all_research_classes(self) -> None:
        expectations = {
            "safe_mapping_candidate": "approve_mapping",
            "recognized_unmapped": "keep_unmapped",
            "new_capability_candidate": "new_capability_needed",
            "reject": "reject_proposal",
        }
        for classification, expected in expectations.items():
            with self.subTest(classification=classification):
                result = build_proposal_decision_suggestion(
                    self._proposal(classification)
                )
                self.assertEqual(
                    result["suggested_decision"],
                    expected,
                )
                self.assertTrue(result["advisory_only"])

    def test_lower_confidence_safe_mapping_is_not_auto_recommended(self) -> None:
        result = build_proposal_decision_suggestion(
            self._proposal(
                "safe_mapping_candidate",
                confidence=0.80,
            )
        )
        self.assertEqual(
            result["suggested_decision"],
            "unreviewed",
        )

    def test_proposal_ai_rejects_nonlocal_model(self) -> None:
        with self.assertRaises(ValueError):
            ask_local_ai_proposal_review(
                self._proposal("safe_mapping_candidate"),
                model="openai/gpt-5.6",
            )

    def test_local_ai_cannot_approve_non_safe_mapping(self) -> None:
        proposal = self._proposal("recognized_unmapped")
        with patch(
            "llm.ask_json",
            return_value={
                "suggested_decision": "approve_mapping",
                "confidence": 0.9,
                "reasons": ["incorrect approval"],
            },
        ):
            with self.assertRaises(ValueError):
                ask_local_ai_proposal_review(
                    proposal,
                    model="ollama/qwen3:8b",
                )


if __name__ == "__main__":
    unittest.main()

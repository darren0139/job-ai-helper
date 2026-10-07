from __future__ import annotations

import unittest

from taxonomy_discovery.broad_mining_guided_review import (
    BUCKET_ALREADY_KNOWN,
    BUCKET_CONFIRMED,
    BUCKET_NEEDS_VERIFICATION,
    BUCKET_PARKED,
    BUCKET_RECOMMENDED,
    build_guided_review_item,
    build_guided_review_summary,
)


def _candidate(
    *,
    candidate_id: str = "c1",
    status: str = "possible_new_technology",
) -> dict:
    return {
        "candidate_id": candidate_id,
        "canonical_name": "ExampleTech",
        "status": status,
    }


def _suggestion(
    *,
    decision: str = "research_further",
    confidence: str = "high",
    reason_code: str = "primary_official_multiple_sources",
) -> dict:
    return {
        "suggested_decision": decision,
        "confidence": confidence,
        "reason_code": reason_code,
        "signals": {
            "supporting_sources": 2,
            "authority_counts": {
                "primary_official": 1,
                "secondary": 0,
                "unclassified": 0,
            },
            "taxonomy_coverage": {
                "matched": False,
                "capability_ids": [],
            },
        },
    }


class GuidedBroadMiningReviewTests(unittest.TestCase):
    def test_high_research_is_recommended(self) -> None:
        item = build_guided_review_item(
            _candidate(),
            _suggestion(),
        )
        self.assertEqual(
            item["bucket"],
            BUCKET_RECOMMENDED,
        )
        self.assertEqual(
            item["next_action"],
            "Confirm for verification",
        )

    def test_medium_research_needs_verification(self) -> None:
        item = build_guided_review_item(
            _candidate(),
            _suggestion(confidence="medium"),
        )
        self.assertEqual(
            item["bucket"],
            BUCKET_NEEDS_VERIFICATION,
        )

    def test_defer_is_parked_not_rejected(self) -> None:
        item = build_guided_review_item(
            _candidate(),
            _suggestion(
                decision="defer",
                confidence="medium",
                reason_code="all_sources_unclassified",
            ),
        )
        self.assertEqual(
            item["bucket"],
            BUCKET_PARKED,
        )
        self.assertEqual(
            item["next_action"],
            "No action now",
        )

    def test_human_research_decision_is_confirmed(self) -> None:
        item = build_guided_review_item(
            _candidate(),
            _suggestion(),
            {
                "candidate_id": "c1",
                "decision": "research_further",
            },
        )
        self.assertEqual(
            item["bucket"],
            BUCKET_CONFIRMED,
        )

    def test_already_known_is_handled(self) -> None:
        item = build_guided_review_item(
            _candidate(status="already_known"),
            {},
        )
        self.assertEqual(
            item["bucket"],
            BUCKET_ALREADY_KNOWN,
        )

    def test_summary_is_zero_network_zero_model(self) -> None:
        summary = build_guided_review_summary(
            [
                _candidate(candidate_id="c1"),
                _candidate(candidate_id="c2"),
            ],
            {
                "c1": _suggestion(),
                "c2": _suggestion(
                    decision="defer",
                    confidence="medium",
                ),
            },
            [],
        )
        self.assertEqual(
            summary["counts"][
                BUCKET_RECOMMENDED
            ],
            1,
        )
        self.assertEqual(
            summary["counts"][
                BUCKET_PARKED
            ],
            1,
        )
        self.assertEqual(
            summary["governance"]["network_calls"],
            0,
        )
        self.assertFalse(
            summary["governance"][
                "automatic_review_persistence"
            ]
        )


if __name__ == "__main__":
    unittest.main()

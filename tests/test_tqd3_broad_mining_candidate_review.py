from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from database.taxonomy_discovery_review_manager import (
    BROAD_MINING_CANDIDATE_REVIEW_DECISIONS,
    BROAD_MINING_CANDIDATE_REVIEW_VERSION,
    delete_broad_mining_candidate_review,
    get_broad_mining_candidate_review,
    list_broad_mining_candidate_reviews,
    save_broad_mining_candidate_review,
)


def _candidate(
    *,
    candidate_id: str = "tqdmincand_abc",
    status: str = "possible_new_technology",
) -> dict:
    return {
        "candidate_id": candidate_id,
        "canonical_name": "Redpanda",
        "status": status,
        "entity_type": "Event streaming platform",
        "supporting_source_urls": [
            "https://www.redpanda.com/customers"
        ],
        "source_authority": {
            "primary_official": [
                "https://www.redpanda.com/customers"
            ]
        },
    }


class BroadMiningCandidateReviewTests(unittest.TestCase):
    def test_save_round_trip_and_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "reviews.sqlite3"
            candidate = _candidate()
            saved = save_broad_mining_candidate_review(
                candidate=candidate,
                decision="research_further",
                notes="Identity should be researched.",
                db_path=db,
            )
            self.assertEqual(
                saved["review_version"],
                BROAD_MINING_CANDIDATE_REVIEW_VERSION,
            )
            self.assertEqual(
                saved["decision"],
                "research_further",
            )
            self.assertEqual(
                saved["candidate_snapshot"],
                candidate,
            )

    def test_upsert_is_single_row_per_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "reviews.sqlite3"
            candidate = _candidate()
            save_broad_mining_candidate_review(
                candidate=candidate,
                decision="defer",
                db_path=db,
            )
            save_broad_mining_candidate_review(
                candidate=candidate,
                decision="research_further",
                db_path=db,
            )
            rows = list_broad_mining_candidate_reviews(
                db_path=db,
            )
            self.assertEqual(len(rows), 1)
            self.assertEqual(
                rows[0]["decision"],
                "research_further",
            )

    def test_invalid_decision_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "reviews.sqlite3"
            with self.assertRaises(ValueError):
                save_broad_mining_candidate_review(
                    candidate=_candidate(),
                    decision="approve",
                    db_path=db,
                )

    def test_already_known_candidate_cannot_enter_queue(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "reviews.sqlite3"
            with self.assertRaises(ValueError):
                save_broad_mining_candidate_review(
                    candidate=_candidate(
                        status="already_known"
                    ),
                    decision="defer",
                    db_path=db,
                )

    def test_ambiguous_exact_match_can_be_reviewed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "reviews.sqlite3"
            saved = save_broad_mining_candidate_review(
                candidate=_candidate(
                    candidate_id="tqdmincand_amb",
                    status="ambiguous_registry_match",
                ),
                decision="defer",
                db_path=db,
            )
            self.assertEqual(
                saved["candidate_status"],
                "ambiguous_registry_match",
            )

    def test_filter_and_delete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "reviews.sqlite3"
            save_broad_mining_candidate_review(
                candidate=_candidate(
                    candidate_id="tqdmincand_a"
                ),
                decision="research_further",
                db_path=db,
            )
            save_broad_mining_candidate_review(
                candidate=_candidate(
                    candidate_id="tqdmincand_b"
                ),
                decision="reject",
                db_path=db,
            )

            research_rows = (
                list_broad_mining_candidate_reviews(
                    decision="research_further",
                    db_path=db,
                )
            )
            self.assertEqual(len(research_rows), 1)
            self.assertTrue(
                delete_broad_mining_candidate_review(
                    "tqdmincand_a",
                    db_path=db,
                )
            )
            self.assertIsNone(
                get_broad_mining_candidate_review(
                    "tqdmincand_a",
                    db_path=db,
                )
            )

    def test_decision_contract_is_narrow(self) -> None:
        self.assertEqual(
            BROAD_MINING_CANDIDATE_REVIEW_DECISIONS,
            (
                "research_further",
                "defer",
                "reject",
            ),
        )


if __name__ == "__main__":
    unittest.main()

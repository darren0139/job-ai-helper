from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from database.taxonomy_discovery_review_manager import (
    BROAD_MINING_RESEARCH_STORE_VERSION,
    get_broad_mining_research_result,
    list_broad_mining_research_artifacts,
    load_latest_broad_mining_research_results,
    save_broad_mining_research_result,
    save_broad_mining_research_results,
)


def _result(
    *,
    seed_id: str = "messaging_streaming",
    request_id: str = "req-1",
    technology: str = "Apache Kafka",
) -> dict:
    return {
        "provider": "tavily",
        "endpoint": "research",
        "provider_request_id": request_id,
        "seed_id": seed_id,
        "domain": (
            "Messaging & event streaming"
            if seed_id == "messaging_streaming"
            else "Cloud platforms & managed services"
        ),
        "research_model": "mini",
        "structured_output": {
            "technologies": [
                {
                    "canonical_name": technology,
                    "entity_type": "platform",
                }
            ]
        },
        "sources": [{"url": "https://example.com/"}],
        "governance": {
            "untrusted_research": True,
            "registry_mutations": 0,
            "scoring_influence": False,
        },
    }


class BroadMiningPersistenceTests(unittest.TestCase):
    def test_raw_result_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "reviews.sqlite3"
            original = _result()
            saved = save_broad_mining_research_result(
                original,
                db_path=db,
            )
            loaded = get_broad_mining_research_result(
                saved["artifact_id"],
                db_path=db,
            )
            self.assertEqual(loaded, original)

    def test_same_provider_request_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "reviews.sqlite3"
            a = save_broad_mining_research_result(
                _result(),
                db_path=db,
            )
            b = save_broad_mining_research_result(
                _result(),
                db_path=db,
            )
            self.assertEqual(
                a["artifact_id"],
                b["artifact_id"],
            )
            self.assertEqual(
                len(
                    list_broad_mining_research_artifacts(
                        db_path=db,
                    )
                ),
                1,
            )

    def test_latest_loader_returns_newest_per_seed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "reviews.sqlite3"
            save_broad_mining_research_result(
                _result(
                    request_id="req-old",
                    technology="Apache Kafka",
                ),
                db_path=db,
            )
            save_broad_mining_research_result(
                _result(
                    request_id="req-new",
                    technology="NATS",
                ),
                db_path=db,
            )
            save_broad_mining_research_result(
                _result(
                    seed_id="cloud_platforms",
                    request_id="req-cloud",
                    technology="AWS",
                ),
                db_path=db,
            )

            loaded = load_latest_broad_mining_research_results(
                db_path=db,
            )
            self.assertEqual(len(loaded), 2)
            by_seed = {
                row["seed_id"]: row
                for row in loaded
            }
            self.assertEqual(
                by_seed["messaging_streaming"][
                    "provider_request_id"
                ],
                "req-new",
            )
            self.assertEqual(
                by_seed["cloud_platforms"][
                    "provider_request_id"
                ],
                "req-cloud",
            )

    def test_batch_save_and_summary_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "reviews.sqlite3"
            saved = save_broad_mining_research_results(
                [
                    _result(request_id="req-a"),
                    _result(
                        seed_id="cloud_platforms",
                        request_id="req-b",
                    ),
                ],
                db_path=db,
            )
            self.assertEqual(len(saved), 2)
            summaries = list_broad_mining_research_artifacts(
                db_path=db,
            )
            self.assertEqual(len(summaries), 2)
            self.assertTrue(
                all(
                    row["store_version"]
                    == BROAD_MINING_RESEARCH_STORE_VERSION
                    for row in summaries
                )
            )

    def test_store_keeps_raw_research_not_derived_state(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "reviews.sqlite3"
            saved = save_broad_mining_research_result(
                _result(),
                db_path=db,
            )
            loaded = get_broad_mining_research_result(
                saved["artifact_id"],
                db_path=db,
            )
            self.assertNotIn(
                "candidate_report",
                loaded,
            )
            self.assertNotIn(
                "source_authority",
                loaded,
            )
            self.assertTrue(
                loaded["governance"]["untrusted_research"]
            )


if __name__ == "__main__":
    unittest.main()

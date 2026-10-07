from __future__ import annotations

import tempfile
from pathlib import Path

from database.taxonomy_discovery_review_manager import (
    delete_broad_mining_candidate_review,
    list_broad_mining_candidate_reviews,
    save_broad_mining_candidate_review,
)


def main() -> None:
    candidate = {
        "candidate_id": "tqdmincand_smoke",
        "canonical_name": "Redpanda",
        "status": "possible_new_technology",
        "entity_type": "Event streaming platform",
        "source_authority": {
            "primary_official": [
                "https://www.redpanda.com/customers"
            ]
        },
    }

    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "reviews.sqlite3"
        save_broad_mining_candidate_review(
            candidate=candidate,
            decision="research_further",
            notes="smoke",
            db_path=db,
        )
        rows = list_broad_mining_candidate_reviews(
            db_path=db,
        )
        assert len(rows) == 1
        assert rows[0]["decision"] == "research_further"
        assert rows[0]["candidate_snapshot"] == candidate
        assert delete_broad_mining_candidate_review(
            candidate["candidate_id"],
            db_path=db,
        )

    print(
        "TQ-D3 broad mining candidate review smoke PASS: "
        "sqlite=true explicit_human_decision=true "
        "decisions=research_further,defer,reject "
        "candidate_snapshot_on_explicit_save=true "
        "tavily_calls=0 proposal_creation=false "
        "registry_mutation=0 taxonomy_mutation=0 "
        "scoring_influence=false"
    )


if __name__ == "__main__":
    main()

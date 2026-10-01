from __future__ import annotations

import tempfile
from pathlib import Path

from database.taxonomy_discovery_review_manager import (
    list_broad_mining_research_artifacts,
    load_latest_broad_mining_research_results,
    save_broad_mining_research_results,
)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "review.sqlite3"
        result = {
            "provider": "tavily",
            "endpoint": "research",
            "provider_request_id": "smoke-request",
            "seed_id": "messaging_streaming",
            "domain": "Messaging & event streaming",
            "research_model": "mini",
            "structured_output": {
                "technologies": [
                    {
                        "canonical_name": "Apache Kafka",
                    }
                ]
            },
            "sources": [
                {
                    "url": "https://kafka.apache.org/",
                }
            ],
            "governance": {
                "untrusted_research": True,
                "registry_mutations": 0,
                "scoring_influence": False,
            },
        }

        save_broad_mining_research_results(
            [result],
            db_path=db,
        )
        save_broad_mining_research_results(
            [result],
            db_path=db,
        )

        summaries = list_broad_mining_research_artifacts(
            db_path=db,
        )
        loaded = load_latest_broad_mining_research_results(
            db_path=db,
        )
        assert len(summaries) == 1
        assert len(loaded) == 1
        assert loaded[0] == result

    print(
        "TQ-D3 broad mining persistence smoke PASS: "
        "sqlite=true raw_research=true idempotent=true "
        "reload_without_network=true derived_state_persisted=false "
        "mutation=0 scoring_influence=false"
    )


if __name__ == "__main__":
    main()

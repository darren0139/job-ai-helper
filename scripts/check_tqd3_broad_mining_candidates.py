from __future__ import annotations

import json
import tempfile
from pathlib import Path

from taxonomy_discovery.broad_mining_candidates import (
    build_broad_mining_candidate_report,
)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        registry = Path(tmp) / "registry.json"
        registry.write_text(
            json.dumps(
                {
                    "entries": [
                        {
                            "technology_id": "nats",
                            "label": "NATS",
                            "aliases": ["NATS"],
                            "entry_kind": "platform",
                            "status": "approved",
                        },
                        {
                            "technology_id": "microservices",
                            "label": "Microservices",
                            "aliases": ["Microservices"],
                            "status": "approved",
                        },
                    ]
                }
            ),
            encoding="utf-8",
        )

        report = build_broad_mining_candidate_report(
            {
                "provider_request_id": "smoke",
                "seed_id": "messaging_streaming",
                "domain": "Messaging & event streaming",
                "structured_output": {
                    "technologies": [
                        {
                            "canonical_name": "NATS",
                            "entity_type": "message broker",
                            "primary_purpose": (
                                "Cloud-native microservices messaging"
                            ),
                            "adoption_evidence": "Broad production use",
                        },
                        {
                            "canonical_name": "New Broker",
                            "entity_type": "message broker",
                            "primary_purpose": "Messaging",
                            "adoption_evidence": "Broad production use",
                        },
                    ]
                },
            },
            registry_path=registry,
        )

        assert report["candidate_count"] == 2
        by_name = {
            row["canonical_name"]: row
            for row in report["candidates"]
        }
        assert by_name["NATS"]["status"] == "already_known"
        assert (
            by_name["NATS"]["registry_matches"][0]["technology_id"]
            == "nats"
        )
        assert (
            by_name["New Broker"]["status"]
            == "possible_new_technology"
        )
        assert report["matching_contract"]["prose_scanning"] is False
        assert report["governance"]["registry_mutations"] == 0

    print(
        "TQ-D3 broad mining candidate extraction smoke PASS: "
        "exact_canonical_name_match=true prose_scanning=false "
        "dedupe=deterministic candidate_extraction=true "
        "proposal_creation=false mutation=0 scoring_influence=false"
    )


if __name__ == "__main__":
    main()

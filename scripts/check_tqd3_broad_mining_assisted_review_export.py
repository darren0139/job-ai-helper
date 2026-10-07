from __future__ import annotations

import io
import zipfile

from taxonomy_discovery.broad_mining_export import (
    build_broad_mining_debug_zip,
)
from taxonomy_discovery.broad_mining_review_assist import (
    build_broad_mining_review_suggestion,
)


def main() -> None:
    candidate = {
        "candidate_id": "tqdmincand_smoke",
        "canonical_name": "ExampleTech",
        "status": "possible_new_technology",
        "supporting_source_urls": [
            "https://example.com/one",
            "https://example.com/two",
        ],
        "source_authority": {
            "counts": {
                "primary_official": 1,
                "secondary": 0,
                "unclassified": 0,
            }
        },
    }
    suggestion = (
        build_broad_mining_review_suggestion(
            candidate
        )
    )
    assert (
        suggestion["suggested_decision"]
        == "research_further"
    )
    assert (
        suggestion["governance"]["network_calls"]
        == 0
    )

    bundle = build_broad_mining_debug_zip(
        research_artifacts=[],
        raw_research=[],
        candidate_report={
            "candidates": [candidate]
        },
        candidate_reviews=[],
        suggestions={
            candidate["candidate_id"]:
                suggestion
        },
    )
    with zipfile.ZipFile(
        io.BytesIO(bundle)
    ) as archive:
        assert (
            "candidate_summary.csv"
            in archive.namelist()
        )

    print(
        "TQ-D3 broad mining assisted review/export smoke PASS: "
        "python_suggestions=true explicit_accept_required=true "
        "ollama=explicit_click_only export_zip=true "
        "network=0 model=0 automatic_review=false "
        "proposal_creation=false registry_mutation=0 "
        "taxonomy_mutation=0 scoring_influence=false"
    )


if __name__ == "__main__":
    main()

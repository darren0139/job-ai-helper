from __future__ import annotations

from taxonomy_discovery.broad_mining_review_assist import (
    build_broad_mining_review_suggestion,
)


def main() -> None:
    candidate = {
        "candidate_id": "tqdmincand_cpp",
        "canonical_name": "C++",
        "status": "possible_new_technology",
        "entity_type": "programming language",
        "supporting_source_urls": [
            "https://example.com/one",
            "https://example.com/two",
        ],
        "source_authority": {
            "counts": {
                "primary_official": 0,
                "first_party_other_technology":
                    0,
                "secondary": 1,
                "unclassified": 1,
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
    assert suggestion["confidence"] == "high"
    assert (
        suggestion["reason_code"]
        == "exact_capability_taxonomy_coverage"
    )
    assert (
        "language.modern_cpp"
        in suggestion["signals"][
            "taxonomy_coverage"
        ]["capability_ids"]
    )
    assert (
        suggestion["governance"]["network_calls"]
        == 0
    )
    assert (
        suggestion["governance"]["model_calls"]
        == 0
    )

    print(
        "TQ-D3 taxonomy-aware review smoke PASS: "
        "cpp_taxonomy_covered=true "
        "cpp_registry_gap=true "
        "cpp_route=research_further/high "
        "taxonomy_match=exact_only "
        "network=0 model=0 automatic_review=false "
        "mutation=0 scoring_influence=false"
    )


if __name__ == "__main__":
    main()

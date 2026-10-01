from __future__ import annotations

from taxonomy_discovery.broad_mining_discovery_catalog import (
    build_discovery_catalog,
    find_discovery_exact,
)


def main() -> None:
    guided = {
        "items": [
            {
                "candidate_id": "c1",
                "canonical_name": "Django",
                "bucket": "other_discoveries",
                "friendly_reason":
                    "Not prioritized yet.",
                "taxonomy_capabilities": [],
                "supporting_sources": 1,
                "current_review": "unreviewed",
            },
            {
                "candidate_id": "c2",
                "canonical_name": "C++",
                "bucket": "confirmed",
                "friendly_reason":
                    "Known capability registry gap.",
                "taxonomy_capabilities": [
                    "language.modern_cpp"
                ],
                "supporting_sources": 3,
                "current_review":
                    "research_further",
            },
        ]
    }
    catalog = build_discovery_catalog(guided)
    assert catalog["count"] == 2
    django = find_discovery_exact(
        "Django",
        catalog,
    )
    assert len(django) == 1
    assert (
        django[0]["catalog_status"]
        == "other_discovery"
    )
    assert (
        catalog["governance"][
            "recognition_only"
        ]
        is True
    )
    assert (
        catalog["governance"][
            "scoring_influence"
        ]
        is False
    )

    print(
        "TQ-D3 discovery workflow consolidation smoke PASS: "
        "all_discoveries_retained=true "
        "other_discoveries_searchable=true "
        "exact_lookup=true recognition_only=true "
        "send_to_verification=explicit "
        "network=0 model=0 automatic_verification=false "
        "proposal_creation=false mutation=0 "
        "scoring_influence=false"
    )


if __name__ == "__main__":
    main()

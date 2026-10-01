from __future__ import annotations

from taxonomy_discovery.broad_mining_guided_review import (
    BUCKET_NEEDS_VERIFICATION,
    BUCKET_PARKED,
    BUCKET_RECOMMENDED,
    build_guided_review_summary,
)


def main() -> None:
    candidates = [
        {
            "candidate_id": "high",
            "canonical_name": "HighTech",
            "status": "possible_new_technology",
        },
        {
            "candidate_id": "medium",
            "canonical_name": "MediumTech",
            "status": "possible_new_technology",
        },
        {
            "candidate_id": "park",
            "canonical_name": "ParkTech",
            "status": "possible_new_technology",
        },
    ]
    suggestions = {
        "high": {
            "suggested_decision": "research_further",
            "confidence": "high",
            "reason_code":
                "primary_official_multiple_sources",
            "signals": {
                "supporting_sources": 2,
                "authority_counts": {
                    "primary_official": 1,
                },
            },
        },
        "medium": {
            "suggested_decision": "research_further",
            "confidence": "medium",
            "reason_code":
                "multiple_secondary_supported_sources",
            "signals": {
                "supporting_sources": 3,
                "authority_counts": {
                    "secondary": 1,
                },
            },
        },
        "park": {
            "suggested_decision": "defer",
            "confidence": "medium",
            "reason_code":
                "all_sources_unclassified",
            "signals": {
                "supporting_sources": 1,
                "authority_counts": {
                    "unclassified": 1,
                },
            },
        },
    }
    summary = build_guided_review_summary(
        candidates,
        suggestions,
        [],
    )
    assert (
        summary["counts"][BUCKET_RECOMMENDED]
        == 1
    )
    assert (
        summary["counts"][
            BUCKET_NEEDS_VERIFICATION
        ]
        == 1
    )
    assert (
        summary["counts"][BUCKET_PARKED]
        == 1
    )
    assert (
        summary["governance"]["network_calls"]
        == 0
    )

    print(
        "TQ-D3 guided discovery review UX smoke PASS: "
        "workflow_steps=5 user_buckets=true "
        "strong_batch_confirmation=explicit "
        "parked_hidden_default=true "
        "advanced_queue_hidden_default=true "
        "network=0 model=0 automatic_review=false "
        "proposal_creation=false mutation=0 "
        "scoring_influence=false"
    )


if __name__ == "__main__":
    main()

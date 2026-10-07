from __future__ import annotations

from taxonomy_discovery.focused_verification_targets import (
    TARGET_REGISTRY_RELATIONSHIP,
    build_focused_verification_targets,
)


def main() -> None:
    report = build_focused_verification_targets(
        {
            "items": [
                {
                    "candidate_id": "cpp",
                    "canonical_name": "C++",
                    "candidate_status":
                        "possible_new_technology",
                    "bucket": "confirmed",
                    "taxonomy_capabilities": [
                        "language.modern_cpp"
                    ],
                    "supporting_sources": 3,
                    "current_review":
                        "research_further",
                    "friendly_reason":
                        "Known capability, registry gap.",
                }
            ]
        }
    )

    assert report["count"] == 1
    assert (
        report["targets"][0]["route"]
        == TARGET_REGISTRY_RELATIONSHIP
    )
    assert (
        report["governance"][
            "network_calls"
        ]
        == 0
    )
    assert (
        report["governance"][
            "automatic_research"
        ]
        is False
    )

    print(
        "TQ-D3 focused verification targets smoke PASS: "
        "confirmed_only=true "
        "cpp_route=technology_registry_relationship "
        "stable_targets=true explicit_execution=true "
        "network=0 model=0 automatic_research=false "
        "proposal_creation=false mutation=0 "
        "scoring_influence=false"
    )


if __name__ == "__main__":
    main()

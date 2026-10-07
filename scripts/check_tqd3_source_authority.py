from __future__ import annotations

from taxonomy_discovery.source_authority import (
    PRIMARY_OFFICIAL,
    SECONDARY,
    assess_candidate_source_authority,
)


def main() -> None:
    candidate = {
        "canonical_name": "Apache Kafka",
        "maintainers_vendors_or_standards_bodies": [
            "Apache Software Foundation"
        ],
        "supporting_source_urls": [
            "https://kafka.apache.org/documentation/",
            "https://www.geeksforgeeks.org/apache-kafka/",
        ],
    }
    result = assess_candidate_source_authority(candidate)

    assert result["counts"][PRIMARY_OFFICIAL] == 1
    assert result["counts"][SECONDARY] == 1
    assert result["has_primary_official"] is True
    assert (
        result["contract"]["provider_authority_claim_trusted"]
        is False
    )


    coverage_cases = (
        (
            {
                "canonical_name": "Mosquitto",
                "maintainers_vendors_or_standards_bodies": [
                    "Eclipse Foundation"
                ],
            },
            "https://mosquitto.org",
        ),
        (
            {
                "canonical_name": "EMQX",
                "maintainers_vendors_or_standards_bodies": [
                    "EMQ Technologies"
                ],
            },
            "https://www.emqx.com/en/blog/example",
        ),
        (
            {
                "canonical_name": "ZeroMQ",
                "maintainers_vendors_or_standards_bodies": [
                    "ZeroMQ community (GPLv3)"
                ],
            },
            "https://zguide.zeromq.org/docs/chapter1",
        ),
        (
            {
                "canonical_name": "RabbitMQ",
                "maintainers_vendors_or_standards_bodies": [
                    "RabbitMQ Ltd."
                ],
            },
            "https://www.rabbitmq.com/docs/",
        ),
        (
            {
                "canonical_name": "C++",
                "maintainers_vendors_or_standards_bodies": [],
            },
            "https://www.iso.org/standard/68564.html",
        ),
    )
    from taxonomy_discovery.source_authority import (
        classify_candidate_source_url,
    )
    for coverage_candidate, coverage_url in coverage_cases:
        coverage_row = classify_candidate_source_url(
            coverage_candidate,
            coverage_url,
        )
        assert coverage_row["authority"] == PRIMARY_OFFICIAL

    print(
        "TQ-D3 source authority smoke PASS: "
        "primary_official=1 secondary=1 "
        "provider_authority_claim_trusted=false "
        "coverage=mosquitto_emqx_zeromq_rabbitmq cpp_standards=true "
        "network=0 model=0 mutation=0 scoring_influence=false"
    )


if __name__ == "__main__":
    main()

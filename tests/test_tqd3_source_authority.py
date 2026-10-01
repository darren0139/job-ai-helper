from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from taxonomy_discovery.source_authority import (
    FIRST_PARTY_OTHER,
    PRIMARY_OFFICIAL,
    SECONDARY,
    UNCLASSIFIED,
    assess_candidate_source_authority,
    classify_candidate_source_url,
)


def _registry(tmp: str) -> Path:
    path = Path(tmp) / "source_rules.json"
    path.write_text(
        json.dumps(
            {
                "version": "test-v1",
                "technology_domains": [
                    {
                        "technology_aliases": ["Apache Kafka"],
                        "official_domains": ["kafka.apache.org"],
                    },
                    {
                        "technology_aliases": ["Confluent Platform"],
                        "official_domains": ["confluent.io"],
                    },
                ],
                "organization_domains": [
                    {
                        "organization_aliases": [
                            "Apache Software Foundation"
                        ],
                        "official_domains": ["apache.org"],
                    }
                ],
                "secondary_domains": [
                    {
                        "domain": "geeksforgeeks.org",
                        "kind": "technical_secondary",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _candidate() -> dict:
    return {
        "canonical_name": "Apache Kafka",
        "maintainers_vendors_or_standards_bodies": [
            "Apache Software Foundation"
        ],
        "supporting_source_urls": [],
    }


class SourceAuthorityTests(unittest.TestCase):
    def test_candidate_official_domain_is_primary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            row = classify_candidate_source_url(
                _candidate(),
                "https://kafka.apache.org/documentation/",
                registry_path=_registry(tmp),
            )
            self.assertEqual(row["authority"], PRIMARY_OFFICIAL)

    def test_other_vendor_domain_is_not_primary_for_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            row = classify_candidate_source_url(
                _candidate(),
                "https://www.confluent.io/blog/kafka/",
                registry_path=_registry(tmp),
            )
            self.assertEqual(row["authority"], FIRST_PARTY_OTHER)

    def test_known_secondary_is_secondary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            row = classify_candidate_source_url(
                _candidate(),
                "https://www.geeksforgeeks.org/apache-kafka/",
                registry_path=_registry(tmp),
            )
            self.assertEqual(row["authority"], SECONDARY)
            self.assertEqual(
                row["source_kind"],
                "technical_secondary",
            )

    def test_unknown_domain_is_unclassified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            row = classify_candidate_source_url(
                _candidate(),
                "https://example.invalid/kafka",
                registry_path=_registry(tmp),
            )
            self.assertEqual(row["authority"], UNCLASSIFIED)

    def test_provider_authority_label_is_not_trusted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            candidate = _candidate()
            candidate["supporting_source_urls"] = [
                "https://www.geeksforgeeks.org/apache-kafka/"
            ]
            result = assess_candidate_source_authority(
                candidate,
                registry_path=_registry(tmp),
            )
            self.assertFalse(result["has_primary_official"])
            self.assertFalse(
                result["contract"][
                    "provider_authority_claim_trusted"
                ]
            )
            self.assertEqual(result["counts"][SECONDARY], 1)

    def test_default_registry_covers_current_messaging_first_party_domains(
        self,
    ) -> None:
        cases = (
            (
                {
                    "canonical_name": "Mosquitto",
                    "maintainers_vendors_or_standards_bodies": [
                        "Eclipse Foundation"
                    ],
                },
                "https://mosquitto.org",
                PRIMARY_OFFICIAL,
            ),
            (
                {
                    "canonical_name": "EMQX",
                    "maintainers_vendors_or_standards_bodies": [
                        "EMQ Technologies"
                    ],
                },
                "https://www.emqx.com/en/blog/example",
                PRIMARY_OFFICIAL,
            ),
            (
                {
                    "canonical_name": "ZeroMQ",
                    "maintainers_vendors_or_standards_bodies": [
                        "ZeroMQ community (GPLv3)"
                    ],
                },
                "https://zguide.zeromq.org/docs/chapter1",
                PRIMARY_OFFICIAL,
            ),
            (
                {
                    "canonical_name": "ZeroMQ",
                    "maintainers_vendors_or_standards_bodies": [
                        "ZeroMQ community (GPLv3)"
                    ],
                },
                "https://www.zeromq.org",
                PRIMARY_OFFICIAL,
            ),
            (
                {
                    "canonical_name": "RabbitMQ",
                    "maintainers_vendors_or_standards_bodies": [
                        "RabbitMQ Ltd."
                    ],
                },
                "https://www.rabbitmq.com/docs/",
                PRIMARY_OFFICIAL,
            ),
        )

        for candidate, url, expected in cases:
            with self.subTest(
                candidate=candidate["canonical_name"],
                url=url,
            ):
                row = classify_candidate_source_url(
                    candidate,
                    url,
                )
                self.assertEqual(
                    row["authority"],
                    expected,
                )

    def test_default_registry_classifies_current_secondary_domains(
        self,
    ) -> None:
        candidate = {
            "canonical_name": "Apache RocketMQ",
            "maintainers_vendors_or_standards_bodies": [
                "Apache Software Foundation"
            ],
        }
        for url in (
            "https://www.infoq.com/articles/alibaba-apache-rocketmq",
            "https://www.automq.com/blog/kafka-in-production",
            "https://theirstack.com/en/technology/rabbitmq",
        ):
            with self.subTest(url=url):
                row = classify_candidate_source_url(
                    candidate,
                    url,
                )
                self.assertEqual(
                    row["authority"],
                    SECONDARY,
                )

    def test_docker_hub_is_known_first_party_other_for_mosquitto(
        self,
    ) -> None:
        candidate = {
            "canonical_name": "Mosquitto",
            "maintainers_vendors_or_standards_bodies": [
                "Eclipse Foundation"
            ],
        }
        row = classify_candidate_source_url(
            candidate,
            "https://hub.docker.com/_/eclipse-mosquitto",
        )
        self.assertEqual(
            row["authority"],
            FIRST_PARTY_OTHER,
        )



if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from taxonomy_discovery.broad_mining import (
    BROAD_MINING_VERSION,
    build_broad_mining_queue,
    registry_mentions_for_result,
    research_selected_mining_seeds_with_tavily,
)


def main() -> None:
    calls = 0

    def fake_transport(endpoint, payload, headers, timeout):
        nonlocal calls
        calls += 1
        return {
            "query": payload["query"],
            "answer": "Apache Kafka and RabbitMQ are widely used.",
            "results": [
                {
                    "title": "Example",
                    "url": "https://example.com",
                    "content": "Apache Kafka and RabbitMQ",
                    "score": 0.8,
                }
            ],
            "usage": {"credits": 1},
        }

    queue = build_broad_mining_queue()
    result = research_selected_mining_seeds_with_tavily(
        queue,
        selected_seed_ids=["messaging_streaming"],
        api_key="tvly-smoke",
        transport=fake_transport,
    )[0]

    mentions = registry_mentions_for_result(result)

    assert calls == 1
    assert result["broad_mining_version"] == BROAD_MINING_VERSION
    assert result["mining_governance"]["seed_research_only"] is True
    assert result["mining_governance"]["candidate_extraction"] is False
    assert result["mining_governance"]["registry_mutations"] == 0
    assert result["mining_governance"]["scoring_influence"] is False
    assert any(row["label"] == "Apache Kafka" for row in mentions)

    print(
        "TQ-D3 broad technology mining smoke PASS: "
        f"version={BROAD_MINING_VERSION} seeds={len(queue)} "
        "live_network=0 fake_transport_calls=1 candidate_extraction=false "
        "mutation=0 scoring_influence=false"
    )


if __name__ == "__main__":
    main()

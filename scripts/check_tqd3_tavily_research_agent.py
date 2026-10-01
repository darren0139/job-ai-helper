from __future__ import annotations

from taxonomy_discovery.broad_mining import build_broad_mining_queue
from taxonomy_discovery.tavily_research_agent import (
    _validate_tavily_output_schema,
    broad_technology_output_schema,
    TAVILY_RESEARCH_AGENT_VERSION,
    run_broad_research_with_tavily,
)


def main() -> None:
    seed = next(
        row
        for row in build_broad_mining_queue()
        if row["seed_id"] == "messaging_streaming"
    )
    responses = iter(
        [
            {"request_id": "smoke", "status": "pending"},
            {
                "request_id": "smoke",
                "status": "completed",
                "content": {
                    "technologies": [
                        {
                            "canonical_name": "Apache Kafka",
                            "entity_type": "event streaming platform",
                            "primary_purpose": "Event streaming",
                            "adoption_evidence": "Broad production use",
                        }
                    ]
                },
                "sources": [
                    {
                        "title": "Apache Kafka",
                        "url": "https://kafka.apache.org/",
                    }
                ],
            },
        ]
    )
    result = run_broad_research_with_tavily(
        seed,
        api_key="tvly-smoke",
        transport=lambda *args: next(responses),
        sleep_fn=lambda _: None,
    )
    assert result["technology_count"] == 1
    schema = broad_technology_output_schema()
    _validate_tavily_output_schema(schema)
    assert set(schema) == {"properties", "required"}
    assert (
        schema["properties"]["technologies"]["items"]["type"]
        == "object"
    )
    assert result["governance"]["registry_mutations"] == 0
    assert result["governance"]["scoring_influence"] is False

    print(
        "TQ-D3 Tavily Research agent smoke PASS: "
        f"version={TAVILY_RESEARCH_AGENT_VERSION} "
        "model=mini live_network=0 structured_output=true "
        "schema_wrapper=properties_required_only "
        "nested_item_type=object "
        "descriptions=required_and_present "
        "mutation=0 scoring_influence=false"
    )


if __name__ == "__main__":
    main()

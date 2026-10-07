from __future__ import annotations

from taxonomy_discovery.tavily_research import (
    TAVILY_RESEARCH_VERSION,
    research_target_with_tavily,
)


def main() -> None:
    calls = 0

    def fake_transport(endpoint, payload, headers, timeout):
        nonlocal calls
        calls += 1
        assert endpoint.endswith("/search")
        assert headers["Authorization"] == "Bearer tvly-smoke"
        assert payload["include_raw_content"] is False
        return {
            "query": payload["query"],
            "answer": "Structured smoke answer",
            "results": [
                {
                    "title": "Example",
                    "url": "https://example.com",
                    "content": "Example content",
                    "score": 0.8,
                }
            ],
            "request_id": "smoke-request",
            "usage": {"credits": 1},
        }

    result = research_target_with_tavily(
        {
            "target_id": "smoke-target",
            "target_type": "technology_identity",
            "target_key": "java",
            "label": "Java",
            "research_question": "What is Java?",
            "tavily_eligible": True,
        },
        api_key="tvly-smoke",
        transport=fake_transport,
    )

    assert calls == 1
    assert result["research_version"] == TAVILY_RESEARCH_VERSION
    assert result["provider"] == "tavily"
    assert result["source_count"] == 1
    assert result["governance"]["untrusted_research"] is True
    assert result["governance"]["requires_human_review"] is True
    assert result["governance"]["taxonomy_mutations"] == 0
    assert result["governance"]["registry_mutations"] == 0
    assert result["governance"]["scoring_influence"] is False

    print(
        "TQ-D3 Tavily research adapter smoke PASS: "
        f"version={TAVILY_RESEARCH_VERSION} "
        "live_network=0 fake_transport_calls=1 "
        "mutation=0 scoring_influence=false"
    )


if __name__ == "__main__":
    main()

from __future__ import annotations

from taxonomy_discovery.tavily_account_usage import (
    fetch_tavily_account_usage,
)


def main() -> None:
    result = fetch_tavily_account_usage(
        api_key="tvly-smoke",
        transport=lambda endpoint, headers, timeout: {
            "key": {
                "usage": 12,
                "limit": 1000,
                "search_usage": 7,
                "research_usage": 5,
            },
            "account": {
                "current_plan": "Researcher",
                "plan_usage": 12,
                "plan_limit": 1000,
            },
        },
    )
    assert result["key"]["usage"] == 12.0
    assert result["key"]["limit"] == 1000.0
    print(
        "Tavily official usage smoke PASS: "
        "live_network=0 explicit_refresh_only=true "
        "key_usage=12 key_limit=1000"
    )


if __name__ == "__main__":
    main()

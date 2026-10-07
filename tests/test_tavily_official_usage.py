from __future__ import annotations

import unittest

from taxonomy_discovery.tavily_account_usage import (
    fetch_tavily_account_usage,
)


class TavilyOfficialUsageTests(unittest.TestCase):
    def test_explicit_usage_fetch_normalises_response(self) -> None:
        result = fetch_tavily_account_usage(
            api_key="tvly-test",
            transport=lambda endpoint, headers, timeout: {
                "key": {
                    "usage": 150,
                    "limit": 1000,
                    "search_usage": 100,
                    "research_usage": 3,
                },
                "account": {
                    "current_plan": "Researcher",
                    "plan_usage": 150,
                    "plan_limit": 1000,
                },
            },
        )
        self.assertEqual(result["key"]["usage"], 150.0)
        self.assertEqual(result["key"]["limit"], 1000.0)
        self.assertEqual(result["key"]["research_usage"], 3.0)
        self.assertEqual(
            result["account"]["current_plan"],
            "Researcher",
        )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database.tavily_usage_manager import current_month_usage_summary
from taxonomy_discovery.tavily_research import research_target_with_tavily


def _target() -> dict:
    return {
        "target_id": "usage-target",
        "target_type": "technology_identity",
        "target_key": "java",
        "label": "Java",
        "research_question": "What does Java refer to in software engineering?",
        "search_query": "Java programming language official documentation",
        "tavily_eligible": True,
    }


def _response(query: str) -> dict:
    return {
        "query": query,
        "answer": "Java is a programming language.",
        "results": [
            {
                "title": "Java",
                "url": "https://example.com/java",
                "content": "Java documentation",
                "score": 0.9,
            }
        ],
        "request_id": "usage-live-request",
        "response_time": 1.0,
        "usage": {"credits": 1},
    }


class TavilyUsageIntegrationTests(unittest.TestCase):
    def test_live_adapter_records_usage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "usage.sqlite3")
            with patch.dict(
                os.environ,
                {"TAVILY_USAGE_DB": db},
                clear=False,
            ):
                with patch(
                    "taxonomy_discovery.tavily_research._default_transport",
                    side_effect=lambda endpoint, payload, headers, timeout: (
                        _response(payload["query"])
                    ),
                ):
                    result = research_target_with_tavily(
                        _target(),
                        api_key="tvly-test",
                    )

                self.assertTrue(
                    result["usage_tracking"]["recorded"]
                )
                summary = current_month_usage_summary(db_path=db)
                self.assertEqual(summary["credits"], 1.0)
                self.assertEqual(summary["call_count"], 1)

    def test_custom_transport_does_not_touch_persistent_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "usage.sqlite3")
            with patch.dict(
                os.environ,
                {"TAVILY_USAGE_DB": db},
                clear=False,
            ):
                result = research_target_with_tavily(
                    _target(),
                    api_key="tvly-test",
                    transport=(
                        lambda endpoint, payload, headers, timeout: (
                            _response(payload["query"])
                        )
                    ),
                )

                self.assertFalse(
                    result["usage_tracking"]["recorded"]
                )
                summary = current_month_usage_summary(db_path=db)
                self.assertEqual(summary["credits"], 0.0)
                self.assertEqual(summary["call_count"], 0)


if __name__ == "__main__":
    unittest.main()

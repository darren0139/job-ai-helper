from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database.tavily_usage_manager import (
    current_month_usage_summary,
    record_tavily_usage,
    tavily_monthly_credit_budget,
)


def _result(
    request_id: str,
    *,
    credits: float,
    source_count: int,
) -> dict:
    return {
        "provider": "tavily",
        "endpoint": "search",
        "provider_request_id": request_id,
        "target_id": "target-1",
        "target_type": "technology_identity",
        "target_key": "java",
        "target_label": "Java",
        "provider_query": "Java official documentation",
        "provider_response_time": 1.0,
        "answer": "Java is a programming language.",
        "source_count": source_count,
        "usage": {"credits": credits},
        "request": {"search_depth": "basic"},
    }


class TavilyUsageManagerTests(unittest.TestCase):
    def test_records_and_summarises_month_usage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "usage.sqlite3"
            record_tavily_usage(
                _result("req-a", credits=1, source_count=5),
                db_path=db,
            )
            record_tavily_usage(
                _result("req-b", credits=0, source_count=0),
                db_path=db,
            )
            summary = current_month_usage_summary(db_path=db)
            self.assertEqual(summary["credits"], 1.0)
            self.assertEqual(summary["call_count"], 2)
            self.assertEqual(summary["zero_credit_call_count"], 1)
            self.assertEqual(summary["source_returning_call_count"], 1)

    def test_request_id_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "usage.sqlite3"
            row = _result("same-request", credits=1, source_count=5)
            record_tavily_usage(row, db_path=db)
            record_tavily_usage(row, db_path=db)
            summary = current_month_usage_summary(db_path=db)
            self.assertEqual(summary["credits"], 1.0)
            self.assertEqual(summary["call_count"], 1)

    def test_budget_is_optional_environment_configuration(self) -> None:
        with patch.dict(
            os.environ,
            {"TAVILY_MONTHLY_CREDIT_BUDGET": "1000"},
            clear=False,
        ):
            self.assertEqual(tavily_monthly_credit_budget(), 1000.0)
        with patch.dict(
            os.environ,
            {"TAVILY_MONTHLY_CREDIT_BUDGET": "not-a-number"},
            clear=False,
        ):
            self.assertIsNone(tavily_monthly_credit_budget())


if __name__ == "__main__":
    unittest.main()

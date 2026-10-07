from __future__ import annotations

import tempfile
from pathlib import Path

from database.tavily_usage_manager import (
    current_month_usage_summary,
    record_tavily_usage,
)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "usage.sqlite3"
        record_tavily_usage(
            {
                "provider": "tavily",
                "endpoint": "search",
                "provider_request_id": "smoke-request",
                "target_id": "smoke-target",
                "target_type": "technology_identity",
                "target_key": "java",
                "target_label": "Java",
                "provider_query": "Java official documentation",
                "provider_response_time": 0.5,
                "answer": "Java",
                "source_count": 1,
                "usage": {"credits": 1},
                "request": {"search_depth": "basic"},
            },
            db_path=db,
        )
        summary = current_month_usage_summary(db_path=db)
        assert summary["credits"] == 1.0
        assert summary["call_count"] == 1

    print(
        "Tavily local usage ledger smoke PASS: "
        "persistent=sqlite local_scope=true credits=1 calls=1"
    )


if __name__ == "__main__":
    main()

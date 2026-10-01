from __future__ import annotations

import unittest

from taxonomy_discovery.broad_mining import build_broad_mining_queue
from taxonomy_discovery.tavily_research_agent import (
    MAX_BROAD_RESEARCH_BATCH_SEEDS,
    TAVILY_RESEARCH_AGENT_VERSION,
    TAVILY_RESEARCH_MODEL,
    build_broad_research_request,
    research_selected_broad_mining_with_tavily,
    run_broad_research_with_tavily,
)


def _seed() -> dict:
    return next(
        row
        for row in build_broad_mining_queue()
        if row["seed_id"] == "messaging_streaming"
    )


class TavilyResearchAgentTests(unittest.TestCase):
    def test_version_and_model_are_explicit(self) -> None:
        self.assertEqual(
            TAVILY_RESEARCH_AGENT_VERSION,
            "tqd3-tavily-research-agent-v1.0.0",
        )
        self.assertEqual(TAVILY_RESEARCH_MODEL, "mini")

    def test_request_uses_structured_schema(self) -> None:
        payload = build_broad_research_request(_seed())
        self.assertEqual(payload["model"], "mini")
        self.assertFalse(payload["stream"])
        self.assertIn(
            "technologies",
            payload["output_schema"]["properties"],
        )

    def test_completed_task_returns_structured_technologies(self) -> None:
        calls = []

        def fake_transport(method, endpoint, payload, headers, timeout):
            calls.append(method)
            if method == "POST":
                return {
                    "request_id": "research-1",
                    "status": "pending",
                }
            return {
                "request_id": "research-1",
                "status": "completed",
                "content": {
                    "technologies": [
                        {
                            "canonical_name": "Apache Kafka",
                            "entity_type": "event streaming platform",
                            "primary_purpose": "Event streaming",
                            "maintainer_vendor_or_standards_body": (
                                "Apache Software Foundation"
                            ),
                            "adoption_evidence": "Broad production use",
                            "authoritative_source_urls": [
                                "https://kafka.apache.org/"
                            ],
                        }
                    ]
                },
                "sources": [
                    {
                        "title": "Apache Kafka",
                        "url": "https://kafka.apache.org/",
                    }
                ],
            }

        result = run_broad_research_with_tavily(
            _seed(),
            api_key="tvly-test",
            transport=fake_transport,
            sleep_fn=lambda _: None,
        )
        self.assertEqual(result["technology_count"], 1)
        self.assertEqual(
            result["structured_output"]["technologies"][0][
                "canonical_name"
            ],
            "Apache Kafka",
        )
        self.assertEqual(result["source_count"], 1)
        self.assertEqual(calls, ["POST", "GET"])
        self.assertFalse(result["usage_tracking"]["recorded"])

    def test_batch_limit_fails_closed(self) -> None:
        queue = build_broad_mining_queue()
        selected = [
            row["seed_id"]
            for row in queue[: MAX_BROAD_RESEARCH_BATCH_SEEDS + 1]
        ]
        with self.assertRaises(ValueError):
            research_selected_broad_mining_with_tavily(
                queue,
                selected_seed_ids=selected,
                api_key="tvly-test",
                transport=lambda *args: {},
                sleep_fn=lambda _: None,
            )

    def test_schema_descriptions_are_complete(self) -> None:
        from taxonomy_discovery.tavily_research_agent import (
            _validate_tavily_output_schema,
            broad_technology_output_schema,
        )

        schema = broad_technology_output_schema()
        self.assertEqual(
            set(schema),
            {"properties", "required"},
        )
        _validate_tavily_output_schema(schema)

        item = schema["properties"]["technologies"]["items"]
        self.assertEqual(item["type"], "object")
        for name, spec in item["properties"].items():
            with self.subTest(property=name):
                self.assertTrue(
                    str(spec.get("description") or "").strip()
                )



if __name__ == "__main__":
    unittest.main()

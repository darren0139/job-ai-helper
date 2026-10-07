from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from taxonomy_discovery.tavily_research import (
    TAVILY_RESEARCH_VERSION,
    TavilyResearchError,
    build_tavily_search_request,
    normalise_tavily_search_response,
    research_selected_targets_with_tavily,
    research_target_with_tavily,
    tavily_api_key_from_env,
)


def target(
    target_id: str = "target-tech-java",
    *,
    eligible: bool = True,
) -> dict:
    return {
        "target_id": target_id,
        "target_type": "technology_identity",
        "target_key": "java",
        "label": "Java",
        "research_question": (
            "What technology/product/runtime/language/protocol "
            "does the term 'Java' refer to?"
        ),
        "tavily_eligible": eligible,
    }


class TavilyResearchAdapterTests(unittest.TestCase):
    def test_version_is_explicit(self) -> None:
        self.assertEqual(
            TAVILY_RESEARCH_VERSION,
            "tqd3-tavily-research-adapter-v1.0.0",
        )

    def test_request_uses_focused_research_question(self) -> None:
        payload = build_tavily_search_request(target())
        self.assertEqual(
            payload["query"],
            target()["research_question"],
        )
        self.assertEqual(payload["search_depth"], "basic")
        self.assertTrue(payload["include_answer"])
        self.assertTrue(payload["include_usage"])
        self.assertFalse(payload["include_raw_content"])

    def test_request_rejects_noneligible_target(self) -> None:
        with self.assertRaises(ValueError):
            build_tavily_search_request(
                target(eligible=False)
            )

    def test_api_key_reads_environment_only_when_requested(self) -> None:
        with patch.dict(
            os.environ,
            {"TAVILY_API_KEY": "tvly-test"},
            clear=False,
        ):
            self.assertEqual(
                tavily_api_key_from_env(),
                "tvly-test",
            )

    def test_missing_api_key_fails_before_network(self) -> None:
        called = False

        def fake_transport(*args, **kwargs):
            nonlocal called
            called = True
            return {}

        with patch.dict(
            os.environ,
            {"TAVILY_API_KEY": ""},
            clear=False,
        ):
            with self.assertRaises(TavilyResearchError):
                research_target_with_tavily(
                    target(),
                    transport=fake_transport,
                )
        self.assertFalse(called)

    def test_fake_transport_receives_bearer_auth(self) -> None:
        captured = {}

        def fake_transport(endpoint, payload, headers, timeout):
            captured["endpoint"] = endpoint
            captured["payload"] = payload
            captured["headers"] = headers
            captured["timeout"] = timeout
            return {
                "query": payload["query"],
                "answer": "Java is a programming language.",
                "results": [
                    {
                        "title": "Java",
                        "url": "https://example.com/java",
                        "content": "Java language information",
                        "score": 0.91,
                    }
                ],
                "request_id": "req-1",
                "usage": {"credits": 1},
            }

        result = research_target_with_tavily(
            target(),
            api_key="tvly-test",
            transport=fake_transport,
        )
        self.assertEqual(
            captured["headers"]["Authorization"],
            "Bearer tvly-test",
        )
        self.assertEqual(result["target_id"], "target-tech-java")
        self.assertEqual(result["source_count"], 1)
        self.assertTrue(
            result["governance"]["untrusted_research"]
        )
        self.assertEqual(
            result["governance"]["taxonomy_mutations"],
            0,
        )
        self.assertFalse(
            result["governance"]["scoring_influence"]
        )

    def test_normalisation_drops_result_without_url(self) -> None:
        result = normalise_tavily_search_response(
            target=target(),
            request_payload=build_tavily_search_request(
                target()
            ),
            response={
                "results": [
                    {"title": "No URL", "content": "x"},
                    {
                        "title": "Has URL",
                        "url": "https://example.com",
                        "content": "y",
                        "score": 0.5,
                    },
                ]
            },
        )
        self.assertEqual(result["source_count"], 1)

    def test_batch_consumes_exact_selected_target_ids(self) -> None:
        targets = [
            target("target-a"),
            {
                **target("target-b"),
                "label": "Python",
                "target_key": "python",
            },
        ]
        calls = []

        def fake_transport(endpoint, payload, headers, timeout):
            calls.append(payload["query"])
            return {
                "query": payload["query"],
                "results": [],
            }

        results = research_selected_targets_with_tavily(
            targets,
            selected_target_ids=["target-b", "target-a"],
            api_key="tvly-test",
            transport=fake_transport,
        )
        self.assertEqual(
            [row["target_id"] for row in results],
            ["target-b", "target-a"],
        )
        self.assertEqual(len(calls), 2)

    def test_batch_rejects_unknown_target_id(self) -> None:
        with self.assertRaises(ValueError):
            research_selected_targets_with_tavily(
                [target("target-a")],
                selected_target_ids=["missing"],
                api_key="tvly-test",
                transport=lambda *args: {},
            )

    def test_batch_rejects_too_many_targets(self) -> None:
        rows = [
            target(f"target-{index}")
            for index in range(3)
        ]
        with self.assertRaises(ValueError):
            research_selected_targets_with_tavily(
                rows,
                selected_target_ids=[
                    "target-0",
                    "target-1",
                    "target-2",
                ],
                api_key="tvly-test",
                max_batch_targets=2,
                transport=lambda *args: {},
            )

    def test_request_rejects_internal_governance_question(self) -> None:
        bad = target()
        bad["research_question"] = (
            "What does Java refer to, and should it be represented "
            "in the technology registry?"
        )
        with self.assertRaises(ValueError):
            build_tavily_search_request(bad)

    def test_request_prefers_provider_search_query(self) -> None:
        row = target()
        row["search_query"] = (
            '"Java" software engineering technology official documentation'
        )
        payload = build_tavily_search_request(row)
        self.assertEqual(payload["query"], row["search_query"])
        self.assertNotEqual(
            payload["query"],
            row["research_question"],
        )

    def test_normalised_result_preserves_human_question_and_provider_query(
        self,
    ) -> None:
        row = target()
        row["search_query"] = (
            '"Java" software engineering technology official documentation'
        )
        payload = build_tavily_search_request(row)
        result = normalise_tavily_search_response(
            target=row,
            request_payload=payload,
            response={
                "query": payload["query"],
                "results": [],
            },
        )
        self.assertEqual(
            result["research_question"],
            row["research_question"],
        )
        self.assertEqual(
            result["provider_query"],
            row["search_query"],
        )


if __name__ == "__main__":
    unittest.main()

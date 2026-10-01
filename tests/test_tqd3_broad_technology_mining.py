from __future__ import annotations

import unittest

from taxonomy_discovery.broad_mining import (
    BROAD_MINING_QUERY_VERSION,
    BROAD_MINING_QUESTION_VERSION,
    BROAD_MINING_SEED_VERSION,
    BROAD_MINING_VERSION,
    MAX_MINING_BATCH_SEEDS,
    build_broad_mining_queue,
    registry_mentions_for_result,
    research_selected_mining_seeds_with_tavily,
)


class BroadTechnologyMiningTests(unittest.TestCase):
    def test_versions_are_explicit(self) -> None:
        self.assertEqual(
            BROAD_MINING_VERSION,
            "tqd3-broad-technology-mining-v1.1.0",
        )
        self.assertEqual(
            BROAD_MINING_SEED_VERSION,
            "software-technology-seeds-v1.0.0",
        )

    def test_seed_queue_is_stable_and_broad(self) -> None:
        first = build_broad_mining_queue()
        second = build_broad_mining_queue()
        self.assertEqual(first, second)
        self.assertGreaterEqual(len(first), 15)
        self.assertEqual(
            len({row["seed_id"] for row in first}),
            len(first),
        )
        self.assertEqual(
            len({row["target_id"] for row in first}),
            len(first),
        )

    def test_seed_contract_is_external_facts_only(self) -> None:
        for row in build_broad_mining_queue():
            with self.subTest(seed=row["seed_id"]):
                self.assertTrue(row["tavily_eligible"])
                self.assertIn(
                    "Use external facts only",
                    row["research_question"],
                )
                self.assertNotIn(
                    "should be added",
                    row["research_question"].lower(),
                )
                self.assertFalse(row["mutates_taxonomy"])
                self.assertFalse(row["mutates_registry"])
                self.assertFalse(row["influences_scoring"])

    def test_exact_selected_seed_ids_drive_calls(self) -> None:
        seeds = build_broad_mining_queue()
        wanted = [
            "messaging_streaming",
            "observability_monitoring",
        ]
        calls = []

        def fake_transport(endpoint, payload, headers, timeout):
            calls.append(payload["query"])
            return {
                "query": payload["query"],
                "answer": "Apache Kafka, RabbitMQ, Prometheus, Grafana",
                "results": [],
            }

        results = research_selected_mining_seeds_with_tavily(
            seeds,
            selected_seed_ids=wanted,
            api_key="tvly-test",
            transport=fake_transport,
        )
        self.assertEqual(
            [row["seed_id"] for row in results],
            wanted,
        )
        self.assertEqual(len(calls), 2)
        self.assertTrue(
            all(
                row["mining_governance"]["seed_research_only"]
                for row in results
            )
        )

    def test_batch_limit_fails_closed(self) -> None:
        seeds = build_broad_mining_queue()
        selected = [
            row["seed_id"]
            for row in seeds[: MAX_MINING_BATCH_SEEDS + 1]
        ]
        with self.assertRaises(ValueError):
            research_selected_mining_seeds_with_tavily(
                seeds,
                selected_seed_ids=selected,
                api_key="tvly-test",
                transport=lambda *args: {},
            )

    def test_unknown_seed_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            research_selected_mining_seeds_with_tavily(
                build_broad_mining_queue(),
                selected_seed_ids=["not_a_seed"],
                api_key="tvly-test",
                transport=lambda *args: {},
            )

    def test_registry_mentions_are_deterministic(self) -> None:
        matches = registry_mentions_for_result(
            {
                "answer": (
                    "Common technologies include Apache Kafka, RabbitMQ, "
                    "Docker and Kubernetes."
                ),
                "sources": [],
            }
        )
        labels = {row["label"] for row in matches}
        self.assertIn("Apache Kafka", labels)
        self.assertIn("RabbitMQ", labels)
        self.assertIn("Docker", labels)
        self.assertIn("Kubernetes", labels)
    def test_queries_prioritise_concrete_named_technologies(self) -> None:
        queue = build_broad_mining_queue()
        messaging = next(
            row
            for row in queue
            if row["seed_id"] == "messaging_streaming"
        )
        self.assertEqual(
            messaging["research_question_version"],
            BROAD_MINING_QUESTION_VERSION,
        )
        self.assertEqual(
            messaging["research_query_version"],
            BROAD_MINING_QUERY_VERSION,
        )
        self.assertIn(
            "concrete, named technologies",
            messaging["research_question"],
        )
        self.assertIn("message brokers", messaging["search_query"])
        self.assertIn("event streaming", messaging["search_query"])
        self.assertNotIn(
            "developer survey",
            messaging["search_query"].lower(),
        )



if __name__ == "__main__":
    unittest.main()

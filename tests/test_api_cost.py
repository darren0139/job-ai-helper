from __future__ import annotations

import unittest

from api_cost import (
    estimate_call_cost,
    normalise_usage,
    summarise_api_calls,
)
from llm import (
    drain_call_ledger,
    get_call_ledger,
    record_external_usage,
    reset_call_ledger,
)


class ApiCostTests(unittest.TestCase):
    def tearDown(self):
        reset_call_ledger()

    def test_normalise_completion_usage(self):
        usage = normalise_usage(
            {
                "usage": {
                    "prompt_tokens": 1000,
                    "completion_tokens": 250,
                    "prompt_tokens_details": {"cached_tokens": 200},
                }
            }
        )
        self.assertEqual(usage["uncached_input_tokens"], 800)
        self.assertEqual(usage["total_tokens"], 1250)

    def test_embedding_cost_is_available(self):
        metadata = {
            "requested_model": "openai/text-embedding-3-small",
            "usage": {
                "prompt_tokens": 1_000_000,
                "total_tokens": 1_000_000,
            },
        }
        self.assertEqual(estimate_call_cost(metadata), 0.02)

    def test_unknown_pricing_is_partial(self):
        summary = summarise_api_calls(
            [
                {
                    "requested_model": "provider/unknown-model",
                    "usage": {
                        "prompt_tokens": 100,
                        "completion_tokens": 20,
                    },
                }
            ]
        )
        self.assertEqual(summary["unknown_cost_call_count"], 1)
        self.assertFalse(summary["cost_estimate_complete"])

    def test_external_usage_is_added_to_ledger(self):
        reset_call_ledger()
        record_external_usage(
            route="analysis",
            requested_model="openai/text-embedding-3-small",
            response_model="text-embedding-3-small",
            usage={"prompt_tokens": 50, "total_tokens": 50},
            elapsed_seconds=0.25,
            operation="embedding",
        )
        self.assertEqual(len(get_call_ledger()), 1)
        self.assertEqual(len(drain_call_ledger()), 1)
        self.assertEqual(get_call_ledger(), [])


if __name__ == "__main__":
    unittest.main()

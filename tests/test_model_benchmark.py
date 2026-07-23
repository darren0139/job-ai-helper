from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "benchmark_models.py"
)
SPEC = importlib.util.spec_from_file_location("benchmark_models", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class BenchmarkModelsTests(unittest.TestCase):
    def test_normalise_openai_usage(self) -> None:
        usage = MODULE.normalise_usage(
            {
                "usage": {
                    "prompt_tokens": 1000,
                    "completion_tokens": 250,
                    "prompt_tokens_details": {
                        "cached_tokens": 400
                    },
                }
            }
        )
        self.assertEqual(usage["input_tokens"], 1000)
        self.assertEqual(usage["cached_input_tokens"], 400)
        self.assertEqual(usage["uncached_input_tokens"], 600)
        self.assertEqual(usage["output_tokens"], 250)

    def test_cost_estimate(self) -> None:
        cost = MODULE.estimate_cost(
            {
                "uncached_input_tokens": 1000,
                "cached_input_tokens": 500,
                "output_tokens": 250,
                "input_tokens": 1500,
                "total_tokens": 1750,
            },
            {
                "input": 2.5,
                "cached_input": 0.25,
                "output": 15.0,
            },
        )
        self.assertEqual(cost, 0.006375)


if __name__ == "__main__":
    unittest.main()

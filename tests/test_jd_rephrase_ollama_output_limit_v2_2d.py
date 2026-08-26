from __future__ import annotations

import os
import unittest
from unittest.mock import patch

import llm


class OllamaRephraseOutputLimitTests(unittest.TestCase):
    def test_rephrase_output_limit_reaches_final_litellm_kwargs(self):
        with patch.dict(
            os.environ,
            {
                "OLLAMA_API_BASE": "http://127.0.0.1:11434",
                "OLLAMA_REPHRASE_THINK": "false",
            },
            clear=False,
        ):
            kwargs = llm._call_kwargs(
                model="ollama/qwen3:4b",
                messages=[
                    {"role": "system", "content": "x"},
                    {"role": "user", "content": "y"},
                ],
                temperature=0.2,
                max_tokens=540,
                expect_json=True,
                route="rephrase",
                reasoning_effort=None,
                seed=None,
            )

        self.assertEqual(kwargs["model"], "ollama_chat/qwen3:4b")
        self.assertEqual(kwargs["api_base"], "http://127.0.0.1:11434")
        self.assertEqual(kwargs["num_ctx"], 8192)
        self.assertEqual(kwargs["max_tokens"], 540)
        self.assertEqual(kwargs["reasoning_effort"], "none")

    def test_rephrase_output_limit_preserves_requested_budget(self):
        kwargs = llm._call_kwargs(
            model="ollama/qwen3:8b",
            messages=[
                {"role": "system", "content": "x"},
                {"role": "user", "content": "y"},
            ],
            temperature=0.2,
            max_tokens=420,
            expect_json=True,
            route="rephrase",
            reasoning_effort=None,
            seed=None,
        )

        self.assertEqual(kwargs["max_tokens"], 420)


if __name__ == "__main__":
    unittest.main()

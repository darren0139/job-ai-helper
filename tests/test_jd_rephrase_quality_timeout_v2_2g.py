from __future__ import annotations

import os
import unittest
from unittest.mock import patch

import llm
import tailoring.jd_specific_rephrase_preview as rephrase


class RephraseQualityTimeoutTests(unittest.TestCase):
    def _kwargs(self, model: str, route: str = "rephrase") -> dict:
        return llm._call_kwargs(
            model=model,
            messages=[
                {"role": "system", "content": "x"},
                {"role": "user", "content": "y"},
            ],
            temperature=0.2,
            max_tokens=540,
            expect_json=True,
            route=route,
            reasoning_effort=None,
            seed=None,
        )

    def test_ollama_rephrase_uses_separate_240_second_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OLLAMA_REPHRASE_TIMEOUT_SECONDS", None)
            kwargs = self._kwargs("ollama/qwen3:8b")
        self.assertEqual(kwargs["timeout"], 240.0)

    def test_ollama_rephrase_timeout_is_configurable(self):
        with patch.dict(
            os.environ,
            {"OLLAMA_REPHRASE_TIMEOUT_SECONDS": "300"},
            clear=False,
        ):
            kwargs = self._kwargs("ollama/qwen3:8b")
        self.assertEqual(kwargs["timeout"], 300.0)

    def test_cloud_rephrase_keeps_normal_request_timeout(self):
        with patch.object(llm, "REQUEST_TIMEOUT_SECONDS", 120.0):
            kwargs = self._kwargs("openai/gpt-4o-mini")
        self.assertEqual(kwargs["timeout"], 120.0)

    def test_ollama_analysis_route_keeps_normal_timeout(self):
        with patch.object(llm, "REQUEST_TIMEOUT_SECONDS", 120.0):
            kwargs = self._kwargs(
                "ollama/qwen3:4b",
                route="analysis",
            )
        self.assertEqual(kwargs["timeout"], 120.0)

    def test_quality_prompt_teaches_safe_paraphrasing(self):
        prompt = rephrase.JD_REPHRASE_BATCH_PROMPT
        self.assertIn("Safe useful rephrasing guidance:", prompt)
        self.assertIn('"set up" -> "configured"', prompt)
        self.assertIn('"connected" -> "integrated"', prompt)
        self.assertIn("ALLOWED EXAMPLE:", prompt)
        self.assertIn("NOT ALLOWED EXAMPLE:", prompt)
        self.assertIn(
            "Do NOT rewrite merely to make the bullet different",
            prompt,
        )


if __name__ == "__main__":
    unittest.main()

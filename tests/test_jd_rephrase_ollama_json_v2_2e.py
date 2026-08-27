from __future__ import annotations

import os
import unittest
from unittest.mock import patch

import llm
import tailoring.jd_specific_rephrase_preview as rephrase
from tailoring.ollama_performance_settings import DEFAULT_REPHRASE_NUM_CTX


class OllamaRephraseJsonModeTests(unittest.TestCase):
    def test_rephrase_json_mode_reaches_final_litellm_kwargs(self):
        with patch.dict(
            os.environ,
            {
                "OLLAMA_API_BASE": "http://127.0.0.1:11434",
                "OLLAMA_REPHRASE_NUM_CTX": "",
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
        self.assertEqual(kwargs["num_ctx"], DEFAULT_REPHRASE_NUM_CTX)
        self.assertEqual(kwargs["max_tokens"], 540)
        self.assertEqual(kwargs["reasoning_effort"], "none")
        self.assertEqual(
            kwargs["response_format"],
            {"type": "json_object"},
        )

    def test_non_json_rephrase_does_not_force_json_mode(self):
        kwargs = llm._call_kwargs(
            model="ollama/qwen3:4b",
            messages=[
                {"role": "system", "content": "x"},
                {"role": "user", "content": "y"},
            ],
            temperature=0.2,
            max_tokens=200,
            expect_json=False,
            route="rephrase",
            reasoning_effort=None,
            seed=None,
        )

        self.assertNotIn("response_format", kwargs)

    def test_batch_prompt_does_not_teach_literal_string_placeholders(self):
        prompt = rephrase.JD_REPHRASE_BATCH_PROMPT

        self.assertNotIn('"suggested_bullet": "string"', prompt)
        self.assertNotIn('"reason": "short string"', prompt)
        self.assertNotIn('"jd_terms_used": ["string"]', prompt)
        self.assertIn("Never output literal placeholder values", prompt)

    def test_placeholder_suggestion_is_explicitly_blocked(self):
        result = rephrase.validate_rephrase_suggestion(
            context={
                "canonical_bullet": "Built a React help desk application.",
                "current_bullet": "Built a React help desk application.",
                "frozen_project_evidence": [
                    "Built a React help desk application.",
                    "React",
                    "Supabase",
                ],
            },
            suggested_bullet="string",
        )

        self.assertFalse(result["safe_for_lineage_evaluation"])
        self.assertIn("placeholder_output", result["guard_reasons"])


if __name__ == "__main__":
    unittest.main()

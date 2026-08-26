from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

import llm


class DynamicEnvModelCatalogueTests(unittest.TestCase):
    def test_extra_models_support_existing_and_new_providers(self):
        payload = {
            "OpenAI — Extra": "openai/example-model",
            "Anthropic — Extra": "anthropic/example-model",
            "Gemini — Extra": "gemini/example-model",
            "xAI — Grok": "xai/example-model",
            "Groq — Qwen": "groq/example-model",
            "Together — Qwen": "together_ai/example-model",
            "Fireworks — Llama": "fireworks_ai/example-model",
            "Ollama — Extra": "ollama/example-model",
        }

        with patch.dict(
            os.environ,
            {"LLM_EXTRA_MODELS_JSON": json.dumps(payload)},
            clear=False,
        ):
            options = llm._load_extra_model_options()

        self.assertEqual(options, payload)

    def test_invalid_extra_provider_is_ignored(self):
        with patch.dict(
            os.environ,
            {
                "LLM_EXTRA_MODELS_JSON": json.dumps(
                    {
                        "Bad": "unknown_provider/model",
                        "Good": "openai/example-model",
                    }
                )
            },
            clear=False,
        ):
            options = llm._load_extra_model_options()

        self.assertNotIn("Bad", options)
        self.assertEqual(options["Good"], "openai/example-model")

    def test_resolve_model_accepts_all_dynamic_provider_prefixes(self):
        model_ids = [
            "openai/example",
            "anthropic/example",
            "gemini/example",
            "xai/example",
            "groq/example",
            "together_ai/example",
            "fireworks_ai/example",
            "ollama/example",
        ]

        for model_id in model_ids:
            with self.subTest(model_id=model_id):
                self.assertEqual(llm.resolve_model(model_id), model_id)

    def test_provider_api_key_mapping(self):
        expected = {
            "openai/example": "OPENAI_API_KEY",
            "anthropic/example": "ANTHROPIC_API_KEY",
            "gemini/example": "GEMINI_API_KEY",
            "xai/example": "XAI_API_KEY",
            "groq/example": "GROQ_API_KEY",
            "together_ai/example": "TOGETHERAI_API_KEY",
            "fireworks_ai/example": "FIREWORKS_AI_API_KEY",
            "ollama/example": None,
        }

        for model_id, variable in expected.items():
            with self.subTest(model_id=model_id):
                self.assertEqual(
                    llm._required_api_key(model_id),
                    variable,
                )

    def test_fireworks_common_key_name_is_mirrored(self):
        with patch.dict(
            os.environ,
            {
                "FIREWORKS_API_KEY": "secret-value",
                "FIREWORKS_AI_API_KEY": "",
            },
            clear=False,
        ):
            llm._sync_provider_key_aliases()

            self.assertEqual(
                os.environ.get("FIREWORKS_AI_API_KEY"),
                "secret-value",
            )


if __name__ == "__main__":
    unittest.main()

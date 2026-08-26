from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

import llm


ROOT = Path(__file__).resolve().parents[1]


class OllamaRephraseRuntimeTests(unittest.TestCase):
    def _kwargs(self, *, route: str = "rephrase") -> dict:
        return llm._call_kwargs(
            model="ollama/qwen3:8b",
            messages=[
                {"role": "system", "content": "system"},
                {"role": "user", "content": "user"},
            ],
            temperature=0.2,
            max_tokens=1400,
            expect_json=True,
            route=route,
            reasoning_effort=None,
            seed=None,
        )

    def test_rephrase_uses_dedicated_ollama_chat_transport(self):
        with patch.dict(
            os.environ,
            {"OLLAMA_REPHRASE_THINK": "false"},
            clear=False,
        ):
            kwargs = self._kwargs(route="rephrase")

        self.assertEqual(
            kwargs["model"],
            "ollama_chat/qwen3:8b",
        )

    def test_rephrase_thinking_off_maps_to_verified_none_effort(self):
        with patch.dict(
            os.environ,
            {"OLLAMA_REPHRASE_THINK": "false"},
            clear=False,
        ):
            kwargs = self._kwargs(route="rephrase")

        self.assertEqual(
            kwargs.get("reasoning_effort"),
            "none",
        )
        self.assertNotIn("think", kwargs)

    def test_rephrase_thinking_true_does_not_force_none_effort(self):
        with patch.dict(
            os.environ,
            {"OLLAMA_REPHRASE_THINK": "true"},
            clear=False,
        ):
            kwargs = self._kwargs(route="rephrase")

        self.assertEqual(
            kwargs["model"],
            "ollama_chat/qwen3:8b",
        )
        self.assertNotEqual(
            kwargs.get("reasoning_effort"),
            "none",
        )

    def test_non_rephrase_ollama_routes_are_unchanged(self):
        kwargs = self._kwargs(route="analysis")

        self.assertEqual(
            kwargs["model"],
            "ollama/qwen3:8b",
        )
        self.assertNotIn(
            "reasoning_effort",
            kwargs,
        )
        self.assertNotIn("think", kwargs)

    def test_timeout_is_not_misreported_as_server_unreachable(self):
        message = llm._ollama_connection_error_message(
            RuntimeError(
                "OllamaException - litellm.Timeout: "
                "Connection timed out after 120.0 seconds."
            )
        )

        lowered = message.lower()
        self.assertIn("timed out", lowered)
        self.assertIn("server was reached", lowered)
        self.assertNotIn("is `ollama serve` running", lowered)

    def test_rephrase_source_still_supplies_full_jd_and_project_context(self):
        source = (
            ROOT / "tailoring" / "jd_specific_rephrase_preview.py"
        ).read_text(encoding="utf-8")

        self.assertIn("TARGET JD PROFILE:", source)
        self.assertIn("TARGET JD TEXT:", source)
        self.assertIn("PROJECTS AND BULLETS:", source)
        self.assertIn("frozen_project_evidence", source)
        self.assertIn('route="rephrase"', source)


if __name__ == "__main__":
    unittest.main()

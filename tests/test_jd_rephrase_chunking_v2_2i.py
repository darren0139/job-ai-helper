from __future__ import annotations

import os
import unittest
from unittest.mock import patch

import llm
import tailoring.jd_specific_rephrase_preview as rephrase


class RephraseChunkingTests(unittest.TestCase):
    def _contexts(self, count: int) -> list[dict]:
        return [
            {
                "project_index": index // 3,
                "bullet_index": index % 3,
                "current_bullet": f"Bullet {index}",
            }
            for index in range(count)
        ]

    def _fake_single_call(self, calls):
        def fake(
            *,
            contexts,
            model=None,
            previous_suggestions=None,
            attempt_number=1,
        ):
            keys = [
                (
                    int(context["project_index"]),
                    int(context["bullet_index"]),
                )
                for context in contexts
            ]
            calls.append(keys)
            return {
                "batch_preview_version": (
                    rephrase.JD_REPHRASE_BATCH_PREVIEW_VERSION
                ),
                "preview_version": rephrase.JD_REPHRASE_PREVIEW_VERSION,
                "attempt_number": int(attempt_number),
                "suggestion_count": len(contexts),
                "suggestions": [
                    {
                        "project_index": key[0],
                        "bullet_index": key[1],
                        "suggested_bullet": f"Suggested {key}",
                    }
                    for key in keys
                ],
                "historical_phase8_used": False,
                "live_evidence_library_used": False,
            }

        return fake

    def test_local_ollama_large_scope_is_chunked_three_at_a_time(self):
        calls = []

        with patch.dict(
            os.environ,
            {"OLLAMA_REPHRASE_BATCH_MAX_BULLETS": "3"},
            clear=False,
        ), patch.object(
            rephrase,
            "_suggest_jd_specific_rephrases_batch_single_call",
            side_effect=self._fake_single_call(calls),
        ):
            result = rephrase.suggest_jd_specific_rephrases_batch(
                contexts=self._contexts(8),
                model="ollama/qwen3:8b",
            )

        self.assertEqual([len(call) for call in calls], [3, 3, 2])
        self.assertTrue(result["chunked_model_calls"])
        self.assertEqual(result["model_call_count"], 3)
        self.assertEqual(result["suggestion_count"], 8)

    def test_local_ollama_three_bullets_stays_one_call(self):
        calls = []

        with patch.dict(
            os.environ,
            {"OLLAMA_REPHRASE_BATCH_MAX_BULLETS": "3"},
            clear=False,
        ), patch.object(
            rephrase,
            "_suggest_jd_specific_rephrases_batch_single_call",
            side_effect=self._fake_single_call(calls),
        ):
            result = rephrase.suggest_jd_specific_rephrases_batch(
                contexts=self._contexts(3),
                model="ollama/qwen3:8b",
            )

        self.assertEqual([len(call) for call in calls], [3])
        self.assertFalse(result["chunked_model_calls"])
        self.assertEqual(result["model_call_count"], 1)

    def test_non_groq_cloud_provider_keeps_single_call(self):
        calls = []

        with patch.object(
            rephrase,
            "_suggest_jd_specific_rephrases_batch_single_call",
            side_effect=self._fake_single_call(calls),
        ):
            result = rephrase.suggest_jd_specific_rephrases_batch(
                contexts=self._contexts(8),
                model="gemini/gemini-2.5-flash",
            )

        self.assertEqual([len(call) for call in calls], [8])
        self.assertFalse(result["chunked_model_calls"])

    def test_ollama_cloud_keeps_single_call(self):
        calls = []

        with patch.object(
            rephrase,
            "_suggest_jd_specific_rephrases_batch_single_call",
            side_effect=self._fake_single_call(calls),
        ):
            result = rephrase.suggest_jd_specific_rephrases_batch(
                contexts=self._contexts(8),
                model="ollama/glm-5.2:cloud",
            )

        self.assertEqual([len(call) for call in calls], [8])
        self.assertFalse(result["chunked_model_calls"])

    def test_timeout_message_uses_actual_request_timeout(self):
        message = llm._ollama_connection_error_message(
            RuntimeError("request timed out"),
            timeout_seconds=240.0,
        )
        self.assertIn("240 seconds", message)
        self.assertNotIn("after 120 seconds", message)


if __name__ == "__main__":
    unittest.main()

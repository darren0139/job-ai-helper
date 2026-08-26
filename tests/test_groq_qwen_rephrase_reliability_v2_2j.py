from __future__ import annotations

import os
import unittest
from unittest.mock import patch

import llm
import tailoring.jd_specific_rephrase_preview as rephrase


class GroqQwenRephraseReliabilityTests(unittest.TestCase):
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

    def test_groq_qwen_large_scope_chunks_six_six_one(self):
        calls = []

        with patch.dict(
            os.environ,
            {"GROQ_REPHRASE_BATCH_MAX_BULLETS": "6"},
            clear=False,
        ), patch.object(
            rephrase,
            "_suggest_jd_specific_rephrases_batch_single_call",
            side_effect=self._fake_single_call(calls),
        ):
            result = rephrase.suggest_jd_specific_rephrases_batch(
                contexts=self._contexts(13),
                model="groq/qwen/qwen3.6-27b",
            )

        self.assertEqual(
            [len(call) for call in calls],
            [6, 6, 1],
        )
        self.assertTrue(result["chunked_model_calls"])
        self.assertEqual(result["model_call_count"], 3)
        self.assertEqual(result["suggestion_count"], 13)

    def test_groq_qwen_small_scope_stays_one_call(self):
        calls = []

        with patch.dict(
            os.environ,
            {"GROQ_REPHRASE_BATCH_MAX_BULLETS": "6"},
            clear=False,
        ), patch.object(
            rephrase,
            "_suggest_jd_specific_rephrases_batch_single_call",
            side_effect=self._fake_single_call(calls),
        ):
            result = rephrase.suggest_jd_specific_rephrases_batch(
                contexts=self._contexts(3),
                model="groq/qwen/qwen3.6-27b",
            )

        self.assertEqual([len(call) for call in calls], [3])
        self.assertFalse(result["chunked_model_calls"])

    def test_non_groq_cloud_model_keeps_single_call(self):
        calls = []

        with patch.object(
            rephrase,
            "_suggest_jd_specific_rephrases_batch_single_call",
            side_effect=self._fake_single_call(calls),
        ):
            result = rephrase.suggest_jd_specific_rephrases_batch(
                contexts=self._contexts(13),
                model="gemini/gemini-2.5-flash",
            )

        self.assertEqual([len(call) for call in calls], [13])
        self.assertFalse(result["chunked_model_calls"])

    def test_groq_qwen_rephrase_disables_and_hides_reasoning(self):
        kwargs = llm._call_kwargs(
            model="groq/qwen/qwen3.6-27b",
            messages=[{"role": "user", "content": "x"}],
            temperature=0.2,
            max_tokens=1080,
            expect_json=True,
            route="rephrase",
            reasoning_effort=None,
            seed=None,
        )

        self.assertEqual(
            kwargs["response_format"],
            {"type": "json_object"},
        )
        self.assertEqual(
            kwargs["reasoning_effort"],
            "none",
        )
        self.assertEqual(
            kwargs["reasoning_format"],
            "hidden",
        )

    def test_groq_qwen_analysis_does_not_force_rephrase_reasoning_policy(self):
        kwargs = llm._call_kwargs(
            model="groq/qwen/qwen3.6-27b",
            messages=[{"role": "user", "content": "x"}],
            temperature=0.2,
            max_tokens=600,
            expect_json=False,
            route="analysis",
            reasoning_effort=None,
            seed=None,
        )

        self.assertNotIn("reasoning_effort", kwargs)
        self.assertNotIn("reasoning_format", kwargs)

    def test_groq_json_validation_message_is_actionable(self):
        message = llm._groq_json_validation_error_message(
            "groq/qwen/qwen3.6-27b",
            RuntimeError("json_validate_failed"),
        )

        self.assertIn("request reached Groq", message)
        self.assertIn(
            "GROQ_REPHRASE_BATCH_MAX_BULLETS",
            message,
        )
        self.assertIn("json_validate_failed", message)


if __name__ == "__main__":
    unittest.main()

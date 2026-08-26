from __future__ import annotations

import os
import unittest
from unittest.mock import patch

import tailoring.jd_specific_rephrase_preview as rephrase


class MeaningfulOnlyRephraseTests(unittest.TestCase):
    def _contexts(self):
        return [
            {
                "project_index": 0,
                "bullet_index": index,
                "project_title": "QueryAI",
                "canonical_bullet": f"Canonical bullet {index}.",
                "current_bullet": f"Current bullet {index}.",
                "frozen_project_evidence": [
                    f"Evidence supporting current bullet {index}."
                ],
                "jd_profile": {"requirements": ["React"]},
                "raw_jd_text": "Build React applications.",
            }
            for index in range(3)
        ]

    def test_local_output_budget_is_smaller(self):
        with patch.dict(
            os.environ,
            {"OLLAMA_REPHRASE_OUTPUT_TOKENS_PER_BULLET": ""},
            clear=False,
        ):
            self.assertEqual(
                rephrase._batch_rephrase_output_max_tokens(
                    "ollama/qwen3:8b",
                    3,
                ),
                360,
            )

        self.assertEqual(
            rephrase._batch_rephrase_output_max_tokens(
                "openai/gpt-5.4-mini",
                3,
            ),
            rephrase._batch_rephrase_max_tokens(3),
        )

    def test_sparse_local_rows_are_reconstructed_as_unchanged(self):
        contexts = self._contexts()

        result = rephrase._expand_sparse_local_rephrase_result(
            {
                "suggestions": [
                    {
                        "project_index": 0,
                        "bullet_index": 1,
                        "suggested_bullet": (
                            "Current bullet 1 with evidence-backed JD wording."
                        ),
                    }
                ]
            },
            contexts,
        )

        self.assertEqual(len(result["suggestions"]), 3)

        by_index = {
            row["bullet_index"]: row
            for row in result["suggestions"]
        }
        self.assertEqual(
            by_index[0]["suggested_bullet"],
            "Current bullet 0.",
        )
        self.assertEqual(
            by_index[2]["suggested_bullet"],
            "Current bullet 2.",
        )
        self.assertIn(
            "No substantive evidence-backed",
            by_index[0]["reason"],
        )

    def test_local_prompt_uses_changed_only_contract(self):
        contexts = self._contexts()

        with patch.object(
            rephrase,
            "ask_json",
            return_value={"suggestions": []},
        ) as ask:
            result = (
                rephrase
                ._suggest_jd_specific_rephrases_batch_single_call(
                    contexts=contexts,
                    model="ollama/qwen3:8b",
                )
            )

        self.assertEqual(len(result["suggestions"]), 3)
        self.assertEqual(
            ask.call_args.kwargs["max_tokens"],
            360,
        )
        system_prompt = ask.call_args.args[0]
        self.assertIn(
            "MEANINGFUL-CHANGE POLICY",
            system_prompt,
        )
        self.assertIn(
            "Return ONLY bullets whose wording you actually changed",
            system_prompt,
        )

    def test_cloud_prompt_gets_meaningful_policy_but_not_sparse_contract(self):
        contexts = self._contexts()

        with patch.object(
            rephrase,
            "ask_json",
            return_value={
                "suggestions": [
                    {
                        "project_index": 0,
                        "bullet_index": index,
                        "suggested_bullet": f"Current bullet {index}.",
                        "reason": "No substantive rewrite.",
                    }
                    for index in range(3)
                ]
            },
        ) as ask:
            rephrase._suggest_jd_specific_rephrases_batch_single_call(
                contexts=contexts,
                model="openai/gpt-5.4-mini",
            )

        system_prompt = ask.call_args.args[0]
        self.assertIn(
            "MEANINGFUL-CHANGE POLICY",
            system_prompt,
        )
        self.assertNotIn(
            "LOCAL OLLAMA CONCISE OUTPUT OVERRIDE",
            system_prompt,
        )
        self.assertEqual(
            ask.call_args.kwargs["max_tokens"],
            rephrase._batch_rephrase_max_tokens(3),
        )


if __name__ == "__main__":
    unittest.main()

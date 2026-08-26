from __future__ import annotations

import os
import unittest
from unittest.mock import patch

import llm
import tailoring.jd_specific_rephrase_preview as rephrase


class LocalOllamaRephraseSpeedTests(unittest.TestCase):
    def test_local_rephrase_context_defaults_to_4096(self):
        with patch.dict(
            os.environ,
            {"OLLAMA_REPHRASE_NUM_CTX": ""},
            clear=False,
        ):
            kwargs = llm._call_kwargs(
                model="ollama/qwen3:8b",
                messages=[{"role": "user", "content": "x"}],
                temperature=0.2,
                max_tokens=540,
                expect_json=True,
                route="rephrase",
                reasoning_effort=None,
                seed=None,
            )

        self.assertEqual(kwargs["num_ctx"], 4096)

    def test_local_rephrase_context_override_is_preserved(self):
        with patch.dict(
            os.environ,
            {"OLLAMA_REPHRASE_NUM_CTX": "6144"},
            clear=False,
        ):
            kwargs = llm._call_kwargs(
                model="ollama/qwen3:8b",
                messages=[{"role": "user", "content": "x"}],
                temperature=0.2,
                max_tokens=540,
                expect_json=True,
                route="rephrase",
                reasoning_effort=None,
                seed=None,
            )

        self.assertEqual(kwargs["num_ctx"], 6144)

    def test_local_prompt_evidence_defaults_are_smaller(self):
        with patch.dict(
            os.environ,
            {
                "OLLAMA_REPHRASE_PROMPT_EVIDENCE_MAX_ITEMS": "",
                "OLLAMA_REPHRASE_PROMPT_EVIDENCE_MAX_CHARS": "",
            },
            clear=False,
        ):
            limits = rephrase._rephrase_prompt_evidence_limits(
                "ollama/qwen3:8b"
            )

        self.assertEqual(limits, (16, 4000))

    def test_cloud_keeps_existing_prompt_evidence_limits(self):
        self.assertEqual(
            rephrase._rephrase_prompt_evidence_limits(
                "ollama/minimax-m3:cloud"
            ),
            (24, 6000),
        )
        self.assertEqual(
            rephrase._rephrase_prompt_evidence_limits(
                "gemini/gemini-3.6-flash"
            ),
            (24, 6000),
        )

    def test_grouping_honours_explicit_model_facing_limits(self):
        evidence = [
            f"React PostgreSQL evidence record {index} " + ("x" * 80)
            for index in range(20)
        ]
        contexts = [
            {
                "project_index": 0,
                "bullet_index": 0,
                "project_title": "QueryAI",
                "canonical_bullet": "Built a React help desk app.",
                "current_bullet": "Built a React help desk app.",
                "frozen_project_evidence": evidence,
                "jd_profile": {"requirements": ["React", "PostgreSQL"]},
                "raw_jd_text": "Build React apps backed by PostgreSQL.",
            }
        ]

        grouped = rephrase._group_batch_prompt_contexts(
            contexts,
            max_evidence_items=3,
            max_evidence_chars=500,
        )

        selected = grouped[0]["frozen_project_evidence"]
        self.assertLessEqual(len(selected), 3)
        self.assertLessEqual(sum(len(item) for item in selected), 500)


if __name__ == "__main__":
    unittest.main()

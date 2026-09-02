# Regression tests for expanded canonical bullet suggestion coverage.

from __future__ import annotations

import unittest
from unittest.mock import patch

from tailoring.canonical_bullet_suggester import (
    CANONICAL_BULLET_SUGGESTION_PROMPT,
    suggest_canonical_project_bullets,
)


class CanonicalBulletSuggesterExpansionTests(unittest.TestCase):
    def test_prompt_has_no_artificial_three_to_five_limit(self) -> None:
        prompt = CANONICAL_BULLET_SUGGESTION_PROMPT

        self.assertNotIn("Usually generate 3-5 bullets.", prompt)
        self.assertIn(
            "Preserve every materially distinct supported contribution",
            prompt,
        )
        self.assertIn(
            "Do not target an arbitrary small bullet count",
            prompt,
        )
        self.assertIn(
            "the correct count is the number of materially distinct "
            "evidence-backed accomplishments",
            prompt,
        )
        self.assertIn(
            "Fewer bullets are correct when the project evidence contains "
            "fewer distinct accomplishments",
            prompt,
        )
        self.assertIn(
            "Never create filler bullets",
            prompt,
        )
        self.assertIn(
            "If a supported point is merged, omitted, or split",
            prompt,
        )

    @patch("tailoring.canonical_bullet_suggester.ask_json")
    def test_suggester_uses_larger_budget_and_forwards_all_evidence(
        self,
        mocked_ask_json,
    ) -> None:
        mocked_ask_json.return_value = {
            "canonical_bullets": [
                "Built feature A.",
                "Built feature B.",
                "Added tests.",
                "Added CI.",
                "Added persistence.",
                "Added RAG.",
            ],
            "source_coverage": [
                {
                    "source_index": index,
                    "decision": "preserved",
                    "canonical_bullet_indexes": [index],
                    "reason": "",
                }
                for index in range(1, 7)
            ],
            "notes": [],
        }

        result = suggest_canonical_project_bullets(
            title="Large Project",
            period="May 2026 - Aug 2026",
            description=(
                "- Built feature A.\n"
                "- Built feature B.\n"
                "- Added tests.\n"
                "- Added CI.\n"
                "- Added persistence.\n"
                "- Added RAG."
            ),
            skills=["Python", "Testing"],
            tools=["Streamlit", "GitHub Actions"],
            impact="End-to-end project with multiple distinct capabilities.",
        )

        self.assertEqual(
            result["canonical_bullets"],
            [
                "Built feature A.",
                "Built feature B.",
                "Added tests.",
                "Added CI.",
                "Added persistence.",
                "Added RAG.",
            ],
        )
        mocked_ask_json.assert_called_once()

        args, kwargs = mocked_ask_json.call_args
        self.assertEqual(kwargs["max_tokens"], 2000)
        self.assertEqual(kwargs["temperature"], 0.0)

        system_prompt = args[0]
        user_prompt = args[1]

        self.assertIn(
            "Preserve every materially distinct supported contribution",
            system_prompt,
        )
        self.assertIn("Built feature A", user_prompt)
        self.assertIn("Built feature B", user_prompt)
        self.assertIn("Added tests", user_prompt)
        self.assertIn("Added CI", user_prompt)
        self.assertIn("Added persistence", user_prompt)
        self.assertIn("Added RAG", user_prompt)
        self.assertIn("Python", user_prompt)
        self.assertIn("GitHub Actions", user_prompt)
        self.assertIn(
            "SOURCE CONTRIBUTIONS (authoritative 1-based indices):",
            user_prompt,
        )
        self.assertIn(
            "Run a source-coverage ledger before finalising the JSON",
            user_prompt,
        )

    @patch("tailoring.canonical_bullet_suggester.ask_json")
    def test_patch_keeps_canonical_suggestion_jd_agnostic(
        self,
        mocked_ask_json,
    ) -> None:
        mocked_ask_json.return_value = {
            "canonical_bullets": ["Built a supported project feature."],
            "source_coverage": [
                {
                    "source_index": 1,
                    "decision": "preserved",
                    "canonical_bullet_indexes": [1],
                    "reason": "",
                }
            ],
            "notes": [],
        }

        suggest_canonical_project_bullets(
            title="Project",
            description="Built a supported project feature.",
        )

        args, _ = mocked_ask_json.call_args
        self.assertIn(
            "Do not over-tailor to one specific job description.",
            args[0],
        )


if __name__ == "__main__":
    unittest.main()

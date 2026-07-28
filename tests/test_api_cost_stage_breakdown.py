from __future__ import annotations

import unittest

from api_cost import summarise_api_calls_by_action


class ApiCostStageBreakdownTests(unittest.TestCase):
    def test_calls_are_grouped_by_action(self):
        rows = summarise_api_calls_by_action(
            [
                {
                    "action": "analyse_resume",
                    "requested_model": "openai/gpt-5.6-terra",
                    "usage": {
                        "prompt_tokens": 100,
                        "completion_tokens": 20,
                    },
                },
                {
                    "action": "generate_projects",
                    "requested_model": "openai/gpt-5.6-terra",
                    "usage": {
                        "prompt_tokens": 200,
                        "completion_tokens": 40,
                    },
                },
                {
                    "action": "generate_projects",
                    "requested_model": "openai/gpt-5.6-terra",
                    "usage": {
                        "prompt_tokens": 300,
                        "completion_tokens": 60,
                    },
                },
            ],
            action_order=[
                "analyse_resume",
                "generate_projects",
            ],
        )

        self.assertEqual(
            [row["action"] for row in rows],
            ["analyse_resume", "generate_projects"],
        )
        self.assertEqual(rows[0]["call_count"], 1)
        self.assertEqual(rows[1]["call_count"], 2)
        self.assertEqual(rows[1]["input_tokens"], 500)
        self.assertEqual(rows[1]["output_tokens"], 100)
        self.assertEqual(rows[1]["total_tokens"], 600)

    def test_local_fitting_can_be_shown_as_zero_cost(self):
        rows = summarise_api_calls_by_action(
            [],
            zero_actions=[
                {
                    "action": (
                        "generate_and_fit_tailored_resume"
                    ),
                    "label": (
                        "Generate and Fit Tailored Resume"
                    ),
                    "note": "Local deterministic fitting.",
                }
            ],
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["call_count"], 0)
        self.assertEqual(rows[0]["total_tokens"], 0)
        self.assertEqual(
            rows[0]["estimated_total_cost_usd"],
            0.0,
        )


if __name__ == "__main__":
    unittest.main()

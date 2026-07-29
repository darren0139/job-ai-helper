from __future__ import annotations

import unittest

from api_cost_subtotals import (
    build_button_cost_subtotal,
    latest_action_invocation,
)


def call(
    *,
    action: str,
    captured_at: str,
    input_tokens: int,
    output_tokens: int,
) -> dict:
    return {
        "action": action,
        "captured_at": captured_at,
        "requested_model": "openai/gpt-5.6-terra",
        "response_model": "gpt-5.6-terra",
        "usage": {
            "prompt_tokens": input_tokens,
            "completion_tokens": output_tokens,
        },
        "elapsed_seconds": 1.0,
    }


class ApiCostSubtotalTests(unittest.TestCase):
    def test_latest_action_uses_latest_invocation_only(self):
        calls = [
            call(
                action="generate_projects",
                captured_at="2026-07-29T10:00:00",
                input_tokens=100,
                output_tokens=10,
            ),
            call(
                action="generate_projects",
                captured_at="2026-07-29T11:00:00",
                input_tokens=200,
                output_tokens=20,
            ),
        ]
        result = latest_action_invocation(calls, "generate_projects")
        self.assertEqual(result["call_count"], 1)
        self.assertEqual(result["input_tokens"], 200)
        self.assertEqual(result["output_tokens"], 20)

    def test_combined_button_has_projects_and_skills_subtotal(self):
        calls = [
            call(
                action="generate_projects",
                captured_at="2026-07-29T11:00:00",
                input_tokens=200,
                output_tokens=20,
            ),
            call(
                action="generate_skills",
                captured_at="2026-07-29T11:01:00",
                input_tokens=100,
                output_tokens=10,
            ),
        ]
        result = build_button_cost_subtotal(
            calls,
            ["generate_projects", "generate_skills"],
        )
        self.assertEqual(result["call_count"], 2)
        self.assertEqual(result["total_tokens"], 330)
        self.assertGreaterEqual(
            result["estimated_total_cost_usd"],
            0.0,
        )


if __name__ == "__main__":
    unittest.main()

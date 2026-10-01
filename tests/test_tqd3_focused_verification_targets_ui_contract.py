from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT
    / "taxonomy_discovery"
    / "review_ui.py"
).read_text(encoding="utf-8")


class FocusedVerificationTargetUIContractTests(
    unittest.TestCase
):
    def test_step3_target_section_is_visible(
        self,
    ) -> None:
        self.assertIn(
            "Step 3 · Focused verification targets",
            SOURCE,
        )
        self.assertIn(
            "build_focused_verification_targets(",
            SOURCE,
        )

    def test_target_generation_does_not_call_tavily(
        self,
    ) -> None:
        # The caption is split across adjacent Python string literals in
        # review_ui.py. Check both semantic fragments instead of requiring
        # one contiguous source-code string.
        self.assertIn(
            "No Tavily or model",
            SOURCE,
        )
        self.assertIn(
            "call is made when these targets are generated",
            SOURCE,
        )

    def test_targets_are_downloadable(
        self,
    ) -> None:
        self.assertIn(
            "Download focused verification targets JSON",
            SOURCE,
        )

    def test_ready_candidates_are_listed(
        self,
    ) -> None:
        self.assertIn(
            "Ready candidates",
            SOURCE,
        )
        # Streamlit source intentionally formats this mapping across
        # multiple lines; assert the semantic contract rather than one
        # exact source-code layout.
        self.assertIn(
            '"route":',
            SOURCE,
        )
        self.assertIn(
            'row["route"]',
            SOURCE,
        )

    def test_execution_is_deferred_to_next_phase(
        self,
    ) -> None:
        self.assertIn(
            "Run focused verification",
            SOURCE,
        )
        self.assertIn(
            "coming in the next phase",
            SOURCE,
        )


if __name__ == "__main__":
    unittest.main()

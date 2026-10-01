from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT / "taxonomy_discovery" / "review_ui.py"
).read_text(encoding="utf-8")


class GuidedBroadMiningReviewUIContractTests(
    unittest.TestCase
):
    def test_five_step_workflow_is_visible(self) -> None:
        for text in (
            "1. Discover",
            "2. Review recommendations",
            "3. Verify candidates",
            "4. Review proposed changes",
            "5. Publish",
        ):
            with self.subTest(text=text):
                self.assertIn(text, SOURCE)

    def test_user_facing_buckets_are_visible(self) -> None:
        for text in (
            "Already known",
            "Recommended",
            "Needs verification",
            "Parked",
            "Confirmed",
        ):
            with self.subTest(text=text):
                self.assertIn(text, SOURCE)

    def test_strong_batch_confirmation_is_explicit(self) -> None:
        self.assertIn(
            "Confirm all strong recommendations",
            SOURCE,
        )
        self.assertIn(
            "save_broad_mining_candidate_review(",
            SOURCE,
        )

    def test_other_discoveries_are_hidden_by_default(self) -> None:
        self.assertIn(
            "Show all other discoveries",
            SOURCE,
        )
        self.assertIn(
            "value=False",
            SOURCE,
        )

    def test_advanced_table_is_hidden_by_default(self) -> None:
        self.assertIn(
            "Show advanced candidate review queue",
            SOURCE,
        )
        self.assertIn(
            "Advanced assisted review · deterministic Python",
            SOURCE,
        )

    def test_terms_are_explained(self) -> None:
        self.assertIn(
            "Parked does not mean rejected",
            SOURCE,
        )
        self.assertIn(
            "Suggested candidates",
            SOURCE,
        )
        self.assertIn(
            "Other discoveries are still retained and searchable",
            SOURCE,
        )


if __name__ == "__main__":
    unittest.main()

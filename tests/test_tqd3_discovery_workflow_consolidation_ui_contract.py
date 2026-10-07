from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT
    / "taxonomy_discovery"
    / "review_ui.py"
).read_text(encoding="utf-8")


class DiscoveryWorkflowConsolidationUIContractTests(
    unittest.TestCase
):
    def test_primary_terms_are_simple(self) -> None:
        for text in (
            "Already handled",
            "Strong suggestions",
            "Suggested",
            "Other discoveries",
            "Ready to verify",
        ):
            with self.subTest(text=text):
                self.assertIn(text, SOURCE)

    def test_other_discoveries_are_retained(self) -> None:
        self.assertIn(
            "All discoveries are retained",
            SOURCE,
        )
        self.assertIn(
            "Send selected other discoveries to verification",
            SOURCE,
        )

    def test_catalog_is_searchable(self) -> None:
        self.assertIn(
            "Discovery catalog",
            SOURCE,
        )
        self.assertIn(
            "Search all discovered technologies",
            SOURCE,
        )
        self.assertIn(
            "build_discovery_catalog(",
            SOURCE,
        )

    def test_advanced_queue_remains_optional(self) -> None:
        self.assertIn(
            "Show advanced candidate review queue",
            SOURCE,
        )

    def test_verification_routing_does_not_auto_research(self) -> None:
        self.assertIn(
            "only adds it to the verification queue",
            SOURCE,
        )
        self.assertIn(
            "Tavily or change the registry/taxonomy",
            SOURCE,
        )
        self.assertIn(
            "Step 3",
            SOURCE,
        )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT / "taxonomy_discovery" / "review_ui.py"
).read_text(encoding="utf-8")


class BroadResearchAgentUIContractTests(unittest.TestCase):
    def test_broad_tab_delegates_to_research_agent(self) -> None:
        start = SOURCE.index(
            "def _render_tqd3_broad_mining_tab()"
        )
        end = SOURCE.index(
            "\ndef render_capability_discovery_review()",
            start,
        )
        helper = SOURCE[start:end]
        self.assertIn(
            "research_selected_broad_mining_with_tavily(",
            helper,
        )
        self.assertNotIn(
            "research_selected_mining_seeds_with_tavily(",
            helper,
        )
        self.assertIn("structured_output", helper)

    def test_usage_refresh_is_explicit(self) -> None:
        self.assertIn(
            'key="tqd3_refresh_tavily_official_usage"',
            SOURCE,
        )
        self.assertIn(
            "fetch_tavily_account_usage(",
            SOURCE,
        )

    def test_broad_tab_has_no_production_mutation(self) -> None:
        start = SOURCE.index(
            "def _render_tqd3_broad_mining_tab()"
        )
        end = SOURCE.index(
            "\ndef render_capability_discovery_review()",
            start,
        )
        helper = SOURCE[start:end]
        for forbidden in (
            "save_review(",
            "save_proposal_review(",
            "import_proposal_bundle(",
            "build_registry_vnext_preview(",
        ):
            self.assertNotIn(forbidden, helper)


if __name__ == "__main__":
    unittest.main()

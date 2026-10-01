from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT / "taxonomy_discovery" / "review_ui.py"
).read_text(encoding="utf-8")


class TQD3BroadMiningUIContractTests(unittest.TestCase):
    def test_broad_mining_tab_and_table_present(self) -> None:
        for token in (
            '"Broad Mining"',
            "def _render_tqd3_broad_mining_tab()",
            'key="tqd3_broad_mining_table"',
            'selection_mode="multi-row"',
        ):
            with self.subTest(token=token):
                self.assertIn(token, SOURCE)

    def test_explicit_research_action_and_session_state(self) -> None:
        for token in (
            "research_selected_broad_mining_with_tavily(",
            '"tqd3_broad_mining_results_v1"',
            '"Tavily Research ({TAVILY_RESEARCH_MODEL})"',
            '"Download selected broad-mining JSON"',
        ):
            with self.subTest(token=token):
                self.assertIn(token, SOURCE)

    def test_ui_explains_seed_only_governance(self) -> None:
        # review_ui.py intentionally wraps long Streamlit copy across
        # adjacent Python string literals. Assert stable semantic fragments
        # instead of one exact rendered sentence that does not exist
        # contiguously in source text.
        for token in (
            "Candidate extraction",
            "Results are session-only and do not add",
            "Candidate extraction and exact registry dedupe are deterministic",
            "disabled pending human review.",
        ):
            with self.subTest(token=token):
                self.assertIn(token, SOURCE)

    def test_broad_mining_helper_has_no_production_mutation(self) -> None:
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
            "technology_registry_v1.json",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, helper)
    def test_ui_shows_local_tavily_usage_and_planned_credit_estimate(
        self,
    ) -> None:
        for token in (
            "Local tracked Tavily usage",
            "estimated current action",
            "TAVILY_MONTHLY_CREDIT_BUDGET",
            "Local ledger only",
        ):
            with self.subTest(token=token):
                self.assertIn(token, SOURCE)



if __name__ == "__main__":
    unittest.main()

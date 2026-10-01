from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT / "taxonomy_discovery" / "review_ui.py"
).read_text(encoding="utf-8")


class TQD3TavilyResearchUIContractTests(unittest.TestCase):
    def test_explicit_tavily_ui_marker_present(self) -> None:
        self.assertIn(
            'TQD3_TAVILY_RESEARCH_UI_MARKER = '
            '"tqd3-tavily-research-ui-v1.1.0"',
            SOURCE,
        )

    def test_selected_targets_drive_explicit_research_action(self) -> None:
        for token in (
            "def _render_tqd3_tavily_research_controls(",
            '"Planned Tavily calls"',
            '"Research {len(selected_targets)} selected target(s) with Tavily"',
            "research_selected_targets_with_tavily(",
            "selected_target_ids=selected_target_ids",
            "tavily_api_key_from_env()",
        ):
            with self.subTest(token=token):
                self.assertIn(token, SOURCE)

    def test_research_results_are_session_only_and_untrusted(self) -> None:
        for token in (
            '"tqd3_tavily_research_results_v1"',
            '"These are untrusted research results.',
            '"Download selected Tavily research JSON"',
            '"Research diagnostics"',
        ):
            with self.subTest(token=token):
                self.assertIn(token, SOURCE)

    def test_tavily_control_has_no_production_mutation(self) -> None:
        start = SOURCE.index(
            "def _render_tqd3_tavily_research_controls("
        )
        end = SOURCE.index(
            "\ndef _render_tqd3_research_targets_tab(",
            start,
        )
        helper = SOURCE[start:end]
        for forbidden in (
            "save_review(",
            "save_proposal_review(",
            "import_proposal_bundle(",
            "delete_review(",
            "build_registry_vnext_preview(",
            "technology_registry_v1.json",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, helper)

    def test_research_target_tab_delegates_after_selection(self) -> None:
        start = SOURCE.index(
            "def _render_tqd3_research_targets_tab("
        )
        end = SOURCE.index(
            "\ndef render_capability_discovery_review()",
            start,
        )
        helper = SOURCE[start:end]
        self.assertIn(
            "_render_tqd3_tavily_research_controls(selected_targets)",
            helper,
        )
        self.assertNotIn(
            "Tavily remains disabled in TQ-D3 v1.2.x",
            helper,
        )


if __name__ == "__main__":
    unittest.main()

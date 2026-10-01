from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT / "taxonomy_discovery" / "review_ui.py"
).read_text(encoding="utf-8")


class TQD3ResearchTargetUIContractTests(unittest.TestCase):
    def test_research_targets_tab_present(self) -> None:
        self.assertIn(
            'TQD3_RESEARCH_TARGET_UI_MARKER = '
            '"tqd3-research-target-readonly-ui-v1.2.0"',
            SOURCE,
        )
        self.assertIn('"Research Targets"', SOURCE)
        self.assertIn(
            "build_research_target_report(",
            SOURCE,
        )

    def test_tab_has_no_direct_mutation_or_network_execution_controls(self) -> None:
        start = SOURCE.index(
            "def _render_tqd3_research_targets_tab("
        )
        end = SOURCE.find("\ndef ", start + 1)
        self.assertGreater(end, start)
        helper = SOURCE[start:end]
        for token in (
            "save_review(",
            "save_proposal_review(",
            "import_proposal_bundle(",
            "ask_local_ai",
            "st.button(",
            "st.form(",
            "st.file_uploader(",
            "research_selected_targets_with_tavily(",
        ):
            with self.subTest(token=token):
                self.assertNotIn(token, helper)

        self.assertIn(
            "_render_tqd3_tavily_research_controls(selected_targets)",
            helper,
        )

    def test_research_target_diagnostics_present(self) -> None:
        for token in (
            '"Target type"',
            '"Tavily eligible"',
            '"**Research question**"',
            '"**Routing reason**"',
            '"**Source terms**"',
            '"TQ-D3 research-target diagnostics"',
        ):
            with self.subTest(token=token):
                self.assertIn(token, SOURCE)

    def test_target_table_is_multi_row_selectable(self) -> None:
        self.assertIn(
            'TQD3_RESEARCH_TARGET_SELECTION_UI_MARKER = '
            '"tqd3-research-target-clickable-table-v1.2.2"',
            SOURCE,
        )
        self.assertIn(
            'key="tqd3_research_target_table"',
            SOURCE,
        )
        self.assertIn('on_select="rerun"', SOURCE)
        self.assertIn(
            'selection_mode="multi-row"',
            SOURCE,
        )
        self.assertIn(
            '"Target types (multi-select)"',
            SOURCE,
        )
        self.assertNotIn(
            '"Inspect research target"',
            SOURCE,
        )
        self.assertNotIn(
            'key="tqd3_research_target_inspector"',
            SOURCE,
        )


if __name__ == "__main__":
    unittest.main()

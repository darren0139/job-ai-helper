from __future__ import annotations
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "taxonomy_discovery" / "review_ui.py").read_text(
    encoding="utf-8"
)

class TQD3ClassificationUIContractTests(unittest.TestCase):
    def test_tab_and_marker_present(self):
        self.assertIn(
            'TQD3_UI_MARKER = "tqd3-classification-readonly-ui-v1.1.0"',
            SOURCE,
        )
        self.assertIn('"TQ-D3 Classification"', SOURCE)
        self.assertIn("build_classification_report(", SOURCE)

    def test_read_only_helper_has_no_mutation_or_ai_controls(self):
        start = SOURCE.index("def _render_tqd3_classification_tab(")
        end = SOURCE.index(
            "\ndef render_capability_discovery_review()", start
        )
        helper = SOURCE[start:end]
        for token in (
            "save_review(",
            "save_proposal_review(",
            "import_proposal_bundle(",
            "ask_local_ai",
            "st.button(",
            "st.form(",
            "st.file_uploader(",
        ):
            with self.subTest(token=token):
                self.assertNotIn(token, helper)

    def test_expected_diagnostics_present(self):
        for token in (
            '"TQ-D3 class"',
            '"Research eligibility"',
            '"**Recommended next action**"',
            '"Affects scoring"',
            '"TQ-D3 deterministic signals"',
        ):
            with self.subTest(token=token):
                self.assertIn(token, SOURCE)

    def test_classification_table_is_multi_row_selectable(self) -> None:
        self.assertIn('key="tqd3_classification_table"', SOURCE)
        self.assertIn('on_select="rerun"', SOURCE)
        self.assertIn('selection_mode="multi-row"', SOURCE)
        self.assertIn('"TQ-D3 classes (multi-select)"', SOURCE)
        self.assertNotIn('"Inspect TQ-D3 candidate"', SOURCE)
        self.assertNotIn('key="tqd3_candidate_inspector"', SOURCE)


if __name__ == "__main__":
    unittest.main()

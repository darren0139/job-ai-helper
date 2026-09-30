from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT / "taxonomy_discovery" / "review_ui.py"
).read_text(encoding="utf-8")


class TQD3SelectionExportReviewQueueUIContractTests(unittest.TestCase):
    def test_review_queue_uses_single_row_table_selection(self) -> None:
        self.assertIn(
            'key="taxonomy_discovery_review_queue_table"',
            SOURCE,
        )
        self.assertIn('selection_mode="single-row"', SOURCE)
        self.assertIn('on_select="rerun"', SOURCE)
        self.assertNotIn('"Inspect candidate"', SOURCE)

    def test_read_only_selection_export_helper_present(self) -> None:
        self.assertIn(
            "def _render_readonly_selection_export(",
            SOURCE,
        )
        self.assertIn(
            '"Selected rows · debug / export"',
            SOURCE,
        )
        for token in (
            '"CSV"',
            '"Markdown"',
            '"HTML"',
            '"Full JSON"',
        ):
            with self.subTest(token=token):
                self.assertIn(token, SOURCE)

    def test_classification_multi_selection_exports(self) -> None:
        self.assertIn(
            'key_prefix="tqd3_classification_selection"',
            SOURCE,
        )

    def test_research_target_multi_selection_exports(self) -> None:
        self.assertIn(
            'key_prefix="tqd3_research_target_selection"',
            SOURCE,
        )

    def test_export_helper_is_read_only(self) -> None:
        start = SOURCE.index(
            "def _render_readonly_selection_export("
        )
        end = SOURCE.index(
            "\ndef _render_tqd3_classification_tab(",
            start,
        )
        helper = SOURCE[start:end]
        for forbidden in (
            "save_review(",
            "save_proposal_review(",
            "import_proposal_bundle(",
            "ask_local_ai",
            "st.button(",
            "st.form(",
            "st.file_uploader(",
        ):
            with self.subTest(token=forbidden):
                self.assertNotIn(forbidden, helper)


if __name__ == "__main__":
    unittest.main()

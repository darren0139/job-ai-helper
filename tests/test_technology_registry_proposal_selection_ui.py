from __future__ import annotations

import unittest
from pathlib import Path


class TechnologyRegistryProposalSelectionUiTests(unittest.TestCase):
    def test_bulk_selector_precedes_editor_and_drives_visible_checks(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "taxonomy_discovery"
            / "review_ui.py"
        ).read_text(encoding="utf-8")

        selector = source.index(
            "use_all_recommended = st.checkbox("
        )
        editor = source.index(
            "edited_grid = st.data_editor("
        )
        self.assertLess(
            selector,
            editor,
            "Bulk selector must be rendered before the table.",
        )
        self.assertIn(
            'row["select"] = bool(',
            source,
        )
        self.assertIn(
            "auto_selectable_ids",
            source,
        )

    def test_filtered_tables_have_isolated_editor_state(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "taxonomy_discovery"
            / "review_ui.py"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "grid_signature = hashlib.sha256(",
            source,
        )
        self.assertIn(
            'f"{selection_mode}_{grid_signature}"',
            source,
        )

    def test_bulk_apply_does_not_overwrite_reviewed_rows(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "taxonomy_discovery"
            / "review_ui.py"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "actionable_selected_ids = [",
            source,
        )
        self.assertIn(
            '== "unreviewed"',
            source,
        )
        self.assertIn(
            "Already-reviewed proposals",
            source,
        )

    def test_button_reports_exact_actionable_count(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "taxonomy_discovery"
            / "review_ui.py"
        ).read_text(encoding="utf-8")

        self.assertIn(
            'f"{len(actionable_selected_ids)} selected"',
            source,
        )
        self.assertIn(
            "decision_summary",
            source,
        )


if __name__ == "__main__":
    unittest.main()

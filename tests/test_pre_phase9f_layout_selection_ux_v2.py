from __future__ import annotations

import unittest
from pathlib import Path

from docx import Document
from docx.shared import Inches

from resume_builder.docx_projects_skills_replacer import (
    _PAGE_DENSITY_MAX_FILL,
    _apply_margin_profile,
    _normalise_page_density_mode,
)


class PrePhase9FLayoutSelectionUXV2Tests(unittest.TestCase):
    def test_no_density_target_is_supported(self) -> None:
        self.assertEqual(_normalise_page_density_mode("none"), "none")
        self.assertIsNone(_PAGE_DENSITY_MAX_FILL["none"])
        self.assertEqual(_PAGE_DENSITY_MAX_FILL["balanced"], 0.92)
        self.assertEqual(_PAGE_DENSITY_MAX_FILL["maximize"], 0.97)

    def test_margin_compaction_never_expands(self) -> None:
        document = Document()
        section = document.sections[0]
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(0.4)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.6)
        changed = _apply_margin_profile(document, "compact_050")
        self.assertTrue(changed)
        self.assertAlmostEqual(section.top_margin.inches, 0.5, places=2)
        self.assertAlmostEqual(section.bottom_margin.inches, 0.4, places=2)
        self.assertAlmostEqual(section.left_margin.inches, 0.5, places=2)
        self.assertAlmostEqual(section.right_margin.inches, 0.5, places=2)

    def test_source_margin_profile_is_noop(self) -> None:
        document = Document()
        section = document.sections[0]
        before = (
            section.top_margin, section.bottom_margin,
            section.left_margin, section.right_margin,
        )
        self.assertFalse(_apply_margin_profile(document, "source"))
        after = (
            section.top_margin, section.bottom_margin,
            section.left_margin, section.right_margin,
        )
        self.assertEqual(before, after)

    def test_ui_contract(self) -> None:
        root = Path(__file__).resolve().parents[1]
        app = (root / "app.py").read_text(encoding="utf-8")
        phase9e = (root / "tailoring" / "phase9e_blueprint_selection_ui.py").read_text(encoding="utf-8")
        phase9d = (root / "tailoring" / "phase9d_global_blueprint_ui.py").read_text(encoding="utf-8")
        nav_start = app.index("page = st.radio(")
        nav_end = app.index("st.divider()", nav_start)
        nav = app[nav_start:nav_end]
        self.assertLess(nav.index('"Application Sessions"'), nav.index('"Profile & Evidence"'))
        self.assertLess(nav.index('"Profile & Evidence"'), nav.index('"Job Market Insights"'))
        self.assertLess(nav.index('"Job Market Insights"'), nav.index('"Global Blueprints"'))
        self.assertIn('st.header("Tailoring Base")', phase9e)
        self.assertIn('selection_key = st.selectbox(', phase9e)
        self.assertIn('"Fit only"', app)
        self.assertIn('"Allow safe margin compaction before deleting content"', app)
        self.assertNotIn("Required provisional override reason", phase9d)
        self.assertIn("User explicitly acknowledged approval with a provisional ", phase9d)


if __name__ == "__main__":
    unittest.main()

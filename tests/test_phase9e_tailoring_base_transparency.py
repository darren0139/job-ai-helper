from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "tailoring" / "phase9e_blueprint_selection_ui.py"


class Phase9ETailoringBaseTransparencyTests(unittest.TestCase):
    def test_user_facing_source_names_are_clear(self):
        source = UI.read_text(encoding="utf-8")
        self.assertIn("Master résumé", source)
        self.assertIn("Application source résumé", source)
        self.assertIn('" · Alignment "', source)

    def test_exact_scoring_snapshot_preview_is_read_only(self):
        source = UI.read_text(encoding="utf-8")
        self.assertIn(
            'with st.expander("Preview selected résumé"',
            source,
        )
        self.assertIn(
            "build_original_resume_starting_snapshot(baseline_report)",
            source,
        )
        self.assertIn("disabled=True", source)

    def test_internal_identifiers_are_preserved(self):
        source = UI.read_text(encoding="utf-8")
        self.assertIn('"original_resume"', source)
        self.assertIn('"base_resume"', source)
        self.assertIn('"global_blueprint"', source)


if __name__ == "__main__":
    unittest.main()

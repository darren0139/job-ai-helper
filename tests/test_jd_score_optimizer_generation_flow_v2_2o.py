from __future__ import annotations

import unittest
from pathlib import Path


class JDScoreOptimizerGenerationFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path("app.py").read_text(
            encoding="utf-8"
        )

    def test_score_optimizer_controls_are_before_generation_warning(self):
        controls = self.source.index(
            "Optional: Optimize generated project bullets for JD score"
        )
        warning = self.source.index(
            "Projects & Skills may make paid model calls"
        )
        self.assertLess(controls, warning)

    def test_old_manual_find_button_is_removed(self):
        self.assertNotIn(
            '"Find safe score improvements"',
            self.source,
        )

    def test_results_panel_is_post_generation(self):
        self.assertIn(
            "JD score optimization results",
            self.source,
        )

    def test_automatic_trigger_uses_generated_draft(self):
        self.assertIn(
            "score_optimizer_current_fingerprint",
            self.source,
        )
        self.assertIn(
            "current_rephrase_generation",
            self.source,
        )

    def test_style_polish_still_exists(self):
        self.assertIn(
            "Optional: JD-aware style polish "
            "(score increase not guaranteed)",
            self.source,
        )


if __name__ == "__main__":
    unittest.main()

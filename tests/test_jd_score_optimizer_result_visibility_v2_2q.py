from __future__ import annotations

import ast
import unittest
from pathlib import Path


class JDScoreOptimizerResultDiagnosticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path("app.py").read_text(
            encoding="utf-8"
        )
        cls.tree = ast.parse(cls.source, "app.py")

    def test_results_panel_has_enabled_state_guard(self):
        marker = "# jd_score_optimizer_enabled_guard_v2_2q"
        self.assertIn(marker, self.source)
        guard_pos = self.source.index(marker)
        title_pos = self.source.index(
            '"JD score optimization results"'
        )
        self.assertLess(guard_pos, title_pos)
        self.assertIn(
            "jd_score_optimizer_enabled_",
            self.source[guard_pos:title_pos],
        )

    def test_optimizer_copy_uses_optimization_model(self):
        self.assertIn(
            "The selected Optimization model may propose alternatives",
            self.source,
        )
        self.assertNotIn(
            "The selected Rephrase model may propose alternatives",
            self.source,
        )
        self.assertIn(
            "additional Optimization-model calls",
            self.source,
        )

    def test_exact_rejection_diagnostics_exist(self):
        for marker in (
            "Rejected optimization candidates",
            "rejected_candidates = [",
            "no_positive_score_gain",
            "preview_guard_failed",
            "claim_lineage_failed",
            "fresh_score_unavailable",
            "important_regression",
            "guard_reasons",
            "claim_lineage_risks",
            "important_regressions",
        ):
            self.assertIn(marker, self.source)


if __name__ == "__main__":
    unittest.main()

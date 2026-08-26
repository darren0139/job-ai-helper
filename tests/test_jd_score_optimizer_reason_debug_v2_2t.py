from __future__ import annotations

import ast
import unittest
from pathlib import Path


class JDScoreOptimizerReasonDebugTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Path("app.py").read_text(
            encoding="utf-8"
        )
        cls.helper = Path(
            "tailoring/jd_specific_rephrase_preview.py"
        ).read_text(
            encoding="utf-8"
        )
        cls.app_tree = ast.parse(cls.app, "app.py")
        cls.helper_tree = ast.parse(
            cls.helper,
            "tailoring/jd_specific_rephrase_preview.py",
        )

    def test_optimizer_diagnostics_preserve_no_change_reasons(self):
        for marker in (
            '"no_change_details"',
            '"reason_source"',
            "No specific no-change reason was returned by the model",
        ):
            self.assertIn(marker, self.helper)

    def test_ui_displays_suggestion_rows_and_no_change_reasons(self):
        for marker in (
            "Suggestion rows returned",
            "Why bullets were unchanged",
            "Model-provided concise reason",
            "Fallback diagnostic",
            "not hidden chain-of-thought",
        ):
            self.assertIn(marker, self.app)

    def test_debug_bundle_contains_optimizer_reviews(self):
        for marker in (
            '"jd_score_optimizer_debug"',
            "jd_score_optimizer_review_",
            '"review_count"',
            '"reviews"',
        ):
            self.assertIn(marker, self.app)

    def test_debug_bundle_function_still_exists(self):
        functions = [
            node
            for node in self.app_tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "create_full_debug_bundle"
        ]
        self.assertEqual(len(functions), 1)


if __name__ == "__main__":
    unittest.main()

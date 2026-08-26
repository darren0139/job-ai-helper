from __future__ import annotations

import ast
import unittest
from pathlib import Path


class JDScoreOptimizerModelSelectionRepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path("app.py").read_text(
            encoding="utf-8"
        )
        cls.tree = ast.parse(cls.source, "app.py")

    @classmethod
    def _has_optimizer_assignment(cls, route: str) -> bool:
        for node in ast.walk(cls.tree):
            if not isinstance(node, ast.Assign):
                continue
            if len(node.targets) != 1:
                continue

            target = node.targets[0]
            if not (
                isinstance(target, ast.Name)
                and target.id == "score_optimizer_model_id"
            ):
                continue

            value = node.value
            if not isinstance(value, ast.Call):
                continue
            if not (
                isinstance(value.func, ast.Name)
                and value.func.id == "get_active_model"
            ):
                continue
            if len(value.args) != 1:
                continue

            arg = value.args[0]
            if (
                isinstance(arg, ast.Constant)
                and arg.value == route
            ):
                return True

        return False

    def test_optimizer_defaults_to_current_analysis_model(self):
        self.assertIn(
            '"__current_analysis__"',
            self.source,
        )
        self.assertTrue(
            self._has_optimizer_assignment("analysis"),
            "JD optimizer must resolve the current Analysis model.",
        )

    def test_optimizer_can_use_rephrase_model(self):
        self.assertIn(
            '"__current_rephrase__"',
            self.source,
        )
        self.assertTrue(
            self._has_optimizer_assignment("rephrase"),
            "JD optimizer must allow the current Rephrase model.",
        )
        self.assertIn(
            '"Optimization model"',
            self.source,
        )

    def test_catalogue_models_are_available(self):
        self.assertIn(
            "score_optimizer_catalogue = get_model_options()",
            self.source,
        )

    def test_old_optimizer_caption_is_removed(self):
        self.assertNotIn(
            '"Optimization model: "\n'
            '        f"`{get_active_model(\'rephrase\')}`"',
            self.source,
        )

    def test_style_polish_stays_on_rephrase_route(self):
        self.assertIn(
            "Optional: JD-aware style polish "
            "(score increase not guaranteed)",
            self.source,
        )
        self.assertIn(
            'rephrase_model_id = get_active_model("rephrase")',
            self.source,
        )


if __name__ == "__main__":
    unittest.main()

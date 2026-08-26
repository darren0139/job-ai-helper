from __future__ import annotations

import ast
import unittest
from pathlib import Path


class JDScoreOptimizerOneShotTriggerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path("app.py").read_text(
            encoding="utf-8"
        )
        cls.tree = ast.parse(cls.source, "app.py")

    @staticmethod
    def _name(node: ast.AST | None) -> str:
        return node.id if isinstance(node, ast.Name) else ""

    @classmethod
    def _has_assignment(
        cls,
        target_name: str,
        value_name: str,
    ) -> bool:
        for node in ast.walk(cls.tree):
            if not isinstance(node, ast.Assign):
                continue
            if len(node.targets) != 1:
                continue
            target = node.targets[0]
            if not (
                isinstance(target, ast.Name)
                and target.id == target_name
            ):
                continue
            if (
                isinstance(node.value, ast.Name)
                and node.value.id == value_name
            ):
                return True
        return False

    @classmethod
    def _is_pending_pop(cls, node: ast.AST) -> bool:
        if not isinstance(node, ast.Call):
            return False
        func = node.func
        if not (
            isinstance(func, ast.Attribute)
            and func.attr == "pop"
            and isinstance(func.value, ast.Attribute)
            and func.value.attr == "session_state"
            and isinstance(func.value.value, ast.Name)
            and func.value.value.id == "st"
        ):
            return False
        return bool(
            node.args
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id == "score_optimizer_pending_key"
        )

    @classmethod
    def _trigger_if_has_pending_pop(cls) -> bool:
        for node in ast.walk(cls.tree):
            if not isinstance(node, ast.If):
                continue
            if not (
                isinstance(node.test, ast.Name)
                and node.test.id
                == "score_optimizer_generation_triggered"
            ):
                continue
            if any(
                cls._is_pending_pop(child)
                for child in ast.walk(node)
            ):
                return True
        return False

    def test_checkbox_is_only_an_arming_setting(self):
        self.assertIn(
            "score_optimizer_generation_triggered",
            self.source,
        )
        self.assertTrue(
            self._has_assignment(
                "score_optimizer_enabled",
                "score_optimizer_generation_triggered",
            ),
            (
                "Downstream optimizer execution must use the one-shot "
                "generation trigger, not the checkbox value directly."
            ),
        )

    def test_trigger_is_bound_to_exact_generation_id(self):
        for marker in (
            "jd_score_optimizer_pending_generation_",
            "score_optimizer_pending_generation_id",
            "current_rephrase_generation_id",
        ):
            self.assertIn(marker, self.source)

        comparisons = [
            node
            for node in ast.walk(self.tree)
            if isinstance(node, ast.Compare)
            and isinstance(node.left, ast.Name)
            and node.left.id
            == "score_optimizer_pending_generation_id"
            and len(node.ops) == 1
            and isinstance(node.ops[0], ast.Eq)
            and len(node.comparators) == 1
            and isinstance(node.comparators[0], ast.Name)
            and node.comparators[0].id
            == "current_rephrase_generation_id"
        ]
        self.assertEqual(
            len(comparisons),
            1,
            "Pending optimization must match the exact generated Draft ID.",
        )

    def test_pending_trigger_is_consumed_once(self):
        self.assertTrue(
            self._trigger_if_has_pending_pop(),
            (
                "The exact-generation trigger must consume its pending "
                "session-state token before the optimizer model call."
            ),
        )

    def test_unchecking_cancels_pending_trigger(self):
        self.assertIn(
            "and not score_optimizer_enabled",
            self.source,
        )

    def test_combined_generate_success_paths_arm_trigger(self):
        marker = "_arm_jd_score_optimizer_for_generation("
        self.assertGreaterEqual(
            self.source.count(marker),
            2,
            (
                "Expected the helper definition plus at least one "
                "successful Generate Projects + Skills arm call."
            ),
        )
        self.assertIn(
            "# jd_score_optimizer_arm_after_generate_v2_2s",
            self.source,
        )

    def test_optimizer_call_remains_downstream(self):
        self.assertIn(
            "build_jd_score_optimization_review(",
            self.source,
        )


if __name__ == "__main__":
    unittest.main()

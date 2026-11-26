"""Regression pin for B1.4.1 -> B1.4.2 normal-fit timing ordering.

This test deliberately reads the production source without invoking a costly DOCX fit.
"""
from __future__ import annotations
import ast
import unittest
from pathlib import Path

MANAGER = Path(__file__).resolve().parents[1] / "database" / "phase9f_tailoring_execution_manager.py"
POLICY = "+v312b142-timing-order-fixed"
VAR = "v312b141_incumbent_fit_elapsed"

class B142TimingOrder(unittest.TestCase):
    def setUp(self):
        self.text = MANAGER.read_text(encoding="utf-8-sig")
        tree = ast.parse(self.text)
        functions = [x for x in tree.body if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef))
                     and x.name == "run_phase9f_normal_fit"]
        self.assertEqual(len(functions), 1)
        self.fn = functions[0]

    def test_only_new_version_is_active(self):
        self.assertEqual(self.text.count(POLICY), 1)
        self.assertNotIn("+v312b141-fast-quality-gated", self.text)
        self.assertIn("portfolio_quality_b141_final_audit", self.text)

    def test_incumbent_timer_assigned_before_it_is_read(self):
        writes = [n for n in ast.walk(self.fn) if isinstance(n, ast.Name)
                  and n.id == VAR and isinstance(n.ctx, ast.Store)]
        reads = [n for n in ast.walk(self.fn) if isinstance(n, ast.Name)
                 and n.id == VAR and isinstance(n.ctx, ast.Load)]
        self.assertEqual(len(writes), 1)
        self.assertEqual(len(reads), 1)
        self.assertLess(writes[0].lineno, reads[0].lineno)
        self.assertEqual(self.text.count('"incumbent_fit_elapsed_seconds"'), 1)

    def test_assignment_after_incumbent_copy_not_after_comparison(self):
        lines = self.text.splitlines()[self.fn.lineno-1:self.fn.end_lineno]
        i = next(i for i, line in enumerate(lines) if line.strip() == "fit_result = deepcopy(fit_result)"
                 and line.startswith("            "))
        self.assertIn("v312b141_incumbent_fit_elapsed =", lines[i+1])
        self.assertLess(i, next(i for i, line in enumerate(lines)
                        if "chosen, b14_audit = compare_and_select(" in line))
        self.assertEqual(sum("v312b141_incumbent_fit_elapsed =" in x for x in lines), 1)

if __name__ == "__main__":
    unittest.main()

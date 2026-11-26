"""B1.7 source-level contract: no scoring or fit signature mutation."""
from __future__ import annotations
import ast
from pathlib import Path
import unittest

class B17ProgressUi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8-sig")
        cls.tree = ast.parse(cls.src)
        cls.buttons = [node for node in ast.walk(cls.tree)
            if isinstance(node, ast.If) and isinstance(node.test, ast.Call)
            and isinstance(node.test.func, ast.Attribute)
            and isinstance(node.test.func.value, ast.Name)
            and node.test.func.value.id == "st" and node.test.func.attr == "button"
            and any(isinstance(a, ast.Constant) and a.value == "Generate and Fit Tailored Resume DOCX"
                    for a in node.test.args)]

    def test_unique_normal_fit_and_status(self):
        self.assertEqual(len(self.buttons), 1)
        button = self.buttons[0]
        calls = [x for x in ast.walk(button) if isinstance(x, ast.Call)
            and isinstance(x.func, ast.Name) and x.func.id == "run_phase9f_normal_fit"]
        self.assertEqual(len(calls), 1)
        self.assertIn("v312b17_progress_status", self.src)
        self.assertIn("v312b17_progress_status.update(", self.src)
        self.assertIn('state="error"', self.src)
        self.assertIn('state="complete"', self.src)

    def test_no_fabricated_percentages_or_engine_changes(self):
        self.assertIn('"show_time": True', self.src)
        self.assertIn('normal Phase 9F', self.src)
        self.assertNotIn('v312b17_progress_bar', self.src)

    def test_previous_trace_preserved(self):
        self.assertIn('v312b12_fit_trace_key', self.src)
        self.assertIn('normal_fit_returned', self.src)
        self.assertIn('"Generate and Fit Tailored Resume DOCX"', self.src)

if __name__ == "__main__":
    unittest.main()

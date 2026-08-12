from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SavedDocxNoneGuardTests(unittest.TestCase):
    def test_saved_docx_success_banner_is_guarded(self) -> None:
        path = ROOT / "app.py"
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(path))

        target_calls = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "success"
            ):
                continue
            source = ast.get_source_segment(text, node) or ""
            if "Saved DOCX loaded for this session:" in source:
                target_calls.append(node)

        self.assertEqual(
            len(target_calls),
            1,
            "Expected exactly one saved-DOCX success banner.",
        )

        target = target_calls[0]
        guarded = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.If):
                continue
            if not (
                isinstance(node.test, ast.Name)
                and node.test.id == "saved_resume_docx_path"
            ):
                continue
            if any(child is target for child in ast.walk(node)):
                guarded = True
                break

        self.assertTrue(
            guarded,
            "Path(saved_resume_docx_path) must not run when the path is None.",
        )


if __name__ == "__main__":
    unittest.main()

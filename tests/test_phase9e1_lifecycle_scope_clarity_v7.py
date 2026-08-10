from __future__ import annotations

import ast
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _string_fragments(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    values: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            values.add(node.value)
        elif isinstance(node, ast.JoinedStr):
            for value in node.values:
                if (
                    isinstance(value, ast.Constant)
                    and isinstance(value.value, str)
                ):
                    values.add(value.value)
    return values


class Phase9E1LifecycleScopeClarityV7Tests(unittest.TestCase):
    def test_open_draft_is_explicit_active_workflow_target(self):
        path = REPO_ROOT / "tailoring" / "phase9e1_resume_workspace_ui.py"
        fragments = _string_fragments(path)
        self.assertTrue(
            any(
                "is the active workflow target" in value
                for value in fragments
            )
        )
        self.assertTrue(
            any(
                "Phase 9B–9E below will remain waiting" in value
                for value in fragments
            )
        )


    def test_workspace_managed_lower_controls_do_not_duplicate_history(self):
        text = (
            REPO_ROOT / "tailoring" / "generation_controls_ui.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn(
            "Advanced version history and recovery",
            text,
        )
        self.assertIn("if not workspace_managed:", text)
        self.assertIn("Approve current working draft", text)

    def test_phase8_complete_label_is_scoped_to_approved_generation(self):
        app_path = REPO_ROOT / "app.py"
        text = app_path.read_text(encoding="utf-8")
        fragments = _string_fragments(app_path)
        self.assertIn("approved_phase8_short", text)
        self.assertIn("phase8_complete_label", text)
        self.assertTrue(
            any(
                "Phase 8 — Approved résumé " in value
                for value in fragments
            )
        )

    def test_blueprint_lifecycle_names_source_generation_and_candidate(self):
        path = (
            REPO_ROOT
            / "tailoring"
            / "phase9e1_blueprint_lifecycle_ui.py"
        )
        text = path.read_text(encoding="utf-8")
        fragments = _string_fragments(path)
        self.assertIn("source_generation_short", text)
        self.assertIn("candidate_short", text)
        self.assertTrue(
            any(
                "Blueprint lifecycle source:" in value
                for value in fragments
            )
        )


if __name__ == "__main__":
    unittest.main()

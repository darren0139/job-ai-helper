from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PreviousScopeGuidanceClarityTests(unittest.TestCase):
    def test_app_distinguishes_previous_scope_from_normal_approved(self) -> None:
        text = (ROOT / "app.py").read_text(encoding="utf-8")

        self.assertIn("workspace_message_context.get(", text)
        self.assertIn('"previous_scope_approved_generation"', text)

        self.assertIn("belongs to a previous ", text)
        self.assertIn(
            "Tailoring Base and is read-only. Use Start new résumé ",
            text,
        )
        self.assertIn(
            "from current Tailoring Base in the Résumé Workspace ",
            text,
        )

        # Normal current-scope approved sessions keep their revision actions.
        self.assertIn(
            "Revise approved résumé from the Résumé Workspace",
            text,
        )
        self.assertIn(
            "Revise it or create an alternative",
            text,
        )

    def test_build_fit_previous_scope_guidance_is_scope_aware(self) -> None:
        text = (ROOT / "app.py").read_text(encoding="utf-8")
        marker = 'st.subheader("Build and Fit Résumé Document")'
        start = text.index(marker)
        block = text[start:start + 5000]

        self.assertIn("previous_scope_message_approved", block)
        self.assertIn("belongs to a previous ", block)
        self.assertIn(
            "Tailoring Base and is read-only. Use Start new résumé ",
            block,
        )
        self.assertIn(
            "from current Tailoring Base in the Résumé Workspace ",
            block,
        )

    def test_phase9e_guidance_waits_for_explicit_workspace_transition(self) -> None:
        text = (
            ROOT / "tailoring" / "phase9e_blueprint_selection_ui.py"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "previous_scope_approved = workspace.get(",
            text,
        )
        self.assertIn(
            '"previous_scope_approved_generation"',
            text,
        )
        self.assertIn(
            "Before generating, use Start new résumé from current Tailoring Base ",
            text,
        )
        self.assertIn(
            "in the Résumé Workspace. The previous approved result remains ",
            text,
        )
        self.assertIn(
            "preserved until you make that explicit transition.",
            text,
        )


if __name__ == "__main__":
    unittest.main()

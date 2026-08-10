from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class Phase9E1WorkflowGuidanceV9Tests(unittest.TestCase):
    def test_workflow_next_action_is_fit_state_aware(self) -> None:
        text = (
            REPO_ROOT / "tailoring" / "phase9e1_workflow_ui.py"
        ).read_text(encoding="utf-8")

        self.assertIn("Review and approve fitted working draft", text)
        self.assertIn("Continue fitting working draft", text)
        self.assertIn("Finish editing and build/fit working draft", text)
        self.assertNotIn(
            "Continue editing/fitting the working draft, approve it, then",
            text,
        )

    def test_starting_source_guidance_respects_open_draft(self) -> None:
        text = (
            REPO_ROOT
            / "tailoring"
            / "phase9e_blueprint_selection_ui.py"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "def _render_active_original_source_guidance(",
            text,
        )
        self.assertIn(
            "is already generated and fitted",
            text,
        )
        self.assertIn(
            "remains the immutable starting source if you choose",
            text,
        )

    def test_phase9a_collapses_for_active_working_draft(self) -> None:
        app_text = (REPO_ROOT / "app.py").read_text(encoding="utf-8")
        phase9a_text = (
            REPO_ROOT
            / "tailoring"
            / "phase9a_evidence_opportunity_ui.py"
        ).read_text(encoding="utf-8")

        self.assertIn("phase9a_has_working_draft", app_text)
        self.assertIn("phase9a_has_working_draft or", app_text)
        self.assertIn("advisory, zero-cost forecast", phase9a_text)
        self.assertNotIn(
            "optional while the immutable résumé is being reused unchanged",
            phase9a_text,
        )


if __name__ == "__main__":
    unittest.main()

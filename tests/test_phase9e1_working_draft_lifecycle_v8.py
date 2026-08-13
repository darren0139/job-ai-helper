from __future__ import annotations

import ast
import unittest
from pathlib import Path

from tailoring.phase9e1_blueprint_lifecycle_ui import (
    build_working_draft_lifecycle_summary,
)
from tailoring.phase9e1_resume_workspace_ui import (
    should_clear_phase9e_session_state,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


class Phase9E1WorkingDraftLifecycleV8Tests(unittest.TestCase):
    def test_fresh_session_marker_does_not_clear_restored_draft(self) -> None:
        self.assertFalse(
            should_clear_phase9e_session_state(
                previous_marker=None,
                binding_marker="current-binding",
                phase9e_enforced=True,
            )
        )
        self.assertFalse(
            should_clear_phase9e_session_state(
                previous_marker="",
                binding_marker="current-binding",
                phase9e_enforced=True,
            )
        )

    def test_real_binding_change_still_clears_old_generation_state(self) -> None:
        self.assertTrue(
            should_clear_phase9e_session_state(
                previous_marker="old-binding",
                binding_marker="new-binding",
                phase9e_enforced=True,
            )
        )
        self.assertFalse(
            should_clear_phase9e_session_state(
                previous_marker="same-binding",
                binding_marker="same-binding",
                phase9e_enforced=True,
            )
        )

    def test_working_draft_blueprint_stages_are_all_waiting(self) -> None:
        summary = build_working_draft_lifecycle_summary(
            {"generation_id": "2325ec35", "status": "draft"}
        )
        self.assertEqual(summary["current_stage"], "phase8")
        self.assertEqual(
            [row["status"] for row in summary["stages"]],
            ["Waiting", "Waiting", "Waiting", "Waiting"],
        )
        self.assertEqual(
            summary["current_title"],
            "Approve and Verify Working Draft",
        )

    def test_app_routes_working_draft_to_phase8_and_lifecycle(self) -> None:
        text = (REPO_ROOT / "app.py").read_text(encoding="utf-8")
        tree = ast.parse(text)
        names = {
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name)
        }
        self.assertIn("active_workspace_is_draft", names)
        self.assertIn("active_workspace_generation", names)
        self.assertIn("should_clear_phase9e_session_state", names)
        self.assertIn("Phase 8 — Waiting for working draft ", text)
        self.assertIn("working_generation=(", text)

    def test_workflow_overview_reports_loaded_working_draft(self) -> None:
        text = (
            REPO_ROOT / "tailoring" / "phase9e1_workflow_ui.py"
        ).read_text(encoding="utf-8")
        self.assertIn("approval + Phase 8 required", text)
        self.assertIn("get_resume_workspace_context", text)

    def test_pdf_preview_uses_shared_raster_renderer(self) -> None:
        path = (
            REPO_ROOT / "tailoring" / "phase9e1_resume_workspace_ui.py"
        )
        text = path.read_text(encoding="utf-8")
        self.assertNotIn("components.html(", text)
        self.assertNotIn("streamlit.components.v1", text)
        self.assertIn("pdf_to_preview_html(", text)
        self.assertNotIn("st.iframe(", text)
        self.assertNotIn("data:application/pdf;base64,", text)



if __name__ == "__main__":
    unittest.main()

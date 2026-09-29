from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from tailoring.phase9e1_resume_workspace_ui import (
    build_resume_workspace_state,
    start_new_resume_from_current_tailoring_base,
    workspace_state_requires_edit_draft,
)

ROOT = Path(__file__).resolve().parents[1]


def gen(gid: str, status: str, fp: str) -> dict:
    return {
        "generation_id": gid,
        "status": status,
        "phase9e_decision_fingerprint": fp,
        "generation_kind": "fit_only",
        "fit_result": {"page_count": 1},
    }


class PreviousScopeApprovedTransitionTests(unittest.TestCase):
    def test_scope_mismatch_preserves_application_approved_pointer(self):
        approved = gen("approved-old", "approved", "old")
        state = build_resume_workspace_state(
            generations=[approved],
            approved_generation=approved,
            loaded_generation_id="",
            phase9e_binding={"decision_fingerprint": "current"},
        )
        self.assertIsNone(state["approved_generation"])
        self.assertEqual(
            state["application_approved_generation"]["generation_id"],
            "approved-old",
        )
        self.assertEqual(
            state["previous_scope_approved_generation"]["generation_id"],
            "approved-old",
        )
        # Keep the internal audit/history contract; UI de-duplicates it.
        self.assertIn(
            "approved-old",
            [row["generation_id"] for row in state["historical_versions"]],
        )

    def test_current_scope_approved_is_not_previous_scope(self):
        approved = gen("approved-current", "approved", "current")
        state = build_resume_workspace_state(
            generations=[approved],
            approved_generation=approved,
            loaded_generation_id="approved-current",
            phase9e_binding={"decision_fingerprint": "current"},
        )
        self.assertEqual(
            state["approved_generation"]["generation_id"],
            "approved-current",
        )
        self.assertIsNone(state["previous_scope_approved_generation"])

    def test_previous_scope_approval_blocks_mutation_without_working_draft(self):
        self.assertTrue(
            workspace_state_requires_edit_draft(
                {
                    "application_approved_generation": {"generation_id": "old"},
                    "loaded_mode": "none",
                }
            )
        )

    def test_working_draft_allows_mutation(self):
        self.assertFalse(
            workspace_state_requires_edit_draft(
                {
                    "application_approved_generation": {"generation_id": "old"},
                    "loaded_mode": "working_draft",
                }
            )
        )

    @patch(
        "tailoring.phase9e1_resume_workspace_ui._clear_generation_session_state"
    )
    @patch(
        "tailoring.phase9e1_resume_workspace_ui.archive_tailoring_generation"
    )
    def test_start_current_base_transition_reuses_existing_lifecycle(
        self,
        archive_mock,
        clear_mock,
    ):
        result = start_new_resume_from_current_tailoring_base(
            application_id=94,
            previous_scope_generation_id="approved-old",
        )

        self.assertTrue(result["ok"])
        archive_mock.assert_called_once_with(94, "approved-old")
        clear_mock.assert_called_once_with(94)
        self.assertIn("current Tailoring Base", result["message"])
        self.assertIn("remains preserved", result["message"])

    def test_start_current_base_transition_rejects_missing_generation_id(self):
        result = start_new_resume_from_current_tailoring_base(
            application_id=94,
            previous_scope_generation_id="",
        )
        self.assertFalse(result["ok"])
        self.assertIn("identity is missing", result["message"])

    def test_transition_ui_and_debug_contract(self):
        workspace = (ROOT / "tailoring/phase9e1_resume_workspace_ui.py").read_text(
            encoding="utf-8"
        )
        lifecycle = (
            ROOT / "tailoring/phase9e1_blueprint_lifecycle_ui.py"
        ).read_text(encoding="utf-8")
        app = (ROOT / "app.py").read_text(encoding="utf-8")

        self.assertIn(
            "Current application result from previous Tailoring Base",
            workspace,
        )
        self.assertIn("Start new résumé from current Tailoring Base", workspace)
        self.assertIn(
            "start_new_resume_from_current_tailoring_base",
            app,
        )
        self.assertIn(
            "phase9e1_inline_start_current_base_",
            app,
        )
        self.assertIn(
            "previous_scope_generation_id = str(",
            app,
        )
        self.assertIn(
            "previous_scope_short_id = previous_scope_generation_id[:8]",
            app,
        )
        self.assertIn(
            "previous_scope_generation_id=previous_scope_generation_id",
            app,
        )
        self.assertNotIn(
            "previous_scope_generation_id=previous_scope_id",
            app,
        )
        self.assertIn("belongs to a previous ", lifecycle)
        self.assertIn(
            "Tailoring Base. Its old Phase 8 / Blueprint lineage remains ",
            lifecycle,
        )
        self.assertIn(
            'mismatch_state["display_scope"] = "previous_scope_approved"',
            lifecycle,
        )
        self.assertIn('"workspace_provenance_debug"', app)
        self.assertIn('"approved_phase9e_decision_fingerprint"', app)
        self.assertIn("approved_for_phase8_is_current_scope", app)


if __name__ == "__main__":
    unittest.main()

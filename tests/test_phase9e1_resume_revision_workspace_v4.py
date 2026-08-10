"""Tests for Phase 9E.1 résumé revision workspace V4."""

from __future__ import annotations

import unittest
from pathlib import Path

from tailoring.phase9e1_resume_workspace_ui import (
    PHASE9E1_RESUME_WORKSPACE_UI_VERSION,
    _revision_draft_for_approved,
    build_resume_workspace_state,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _binding() -> dict:
    return {
        "scope_activation_status": "active",
        "current_scope_status": "current",
        "decision_fingerprint": "decision-current",
        "starting_snapshot_fingerprint": "snapshot-current",
        "workflow_action_fingerprint": "workflow-current",
    }


def _generation(
    generation_id: str,
    status: str,
    *,
    decision: str = "decision-current",
    kind: str = "projects_skills",
    parent: str = "",
    approved_at: str = "",
) -> dict:
    return {
        "id": 1,
        "generation_id": generation_id,
        "status": status,
        "generation_kind": kind,
        "phase9e_decision_fingerprint": decision,
        "parent_generation_id": parent,
        "restored_from_generation_id": parent,
        "approved_at": approved_at,
        "generation_settings": {
            "phase9e_binding": {
                "decision_fingerprint": decision,
                "starting_snapshot_fingerprint": "snapshot-current",
                "workflow_action_fingerprint": "workflow-current",
            }
        },
        "fit_result": {"page_count": 1},
        "updated_at": "2026-08-07T15:00:00",
    }


class Phase9E1ResumeWorkspaceV4Tests(unittest.TestCase):
    def test_revision_draft_is_reused_not_duplicated(self) -> None:
        approved = _generation("approved-current", "approved")
        revision = _generation(
            "revision-current",
            "draft",
            kind="approved_revision",
            parent="approved-current",
        )
        alternative = _generation(
            "alternative-current",
            "draft",
            kind="alternative_copy",
            parent="approved-current",
        )

        selected = _revision_draft_for_approved(
            approved_generation=approved,
            drafts=[alternative, revision],
        )
        self.assertEqual(
            selected["generation_id"],
            "revision-current",
        )

    def test_archived_previously_approved_remains_browsable_history(
        self,
    ) -> None:
        old_approved = _generation(
            "approved-old",
            "archived",
            approved_at="2026-08-07T14:00:00",
        )
        revision = _generation(
            "revision-current",
            "draft",
            kind="approved_revision",
            parent="approved-old",
        )

        state = build_resume_workspace_state(
            generations=[revision, old_approved],
            approved_generation=None,
            loaded_generation_id="revision-current",
            phase9e_binding=_binding(),
        )

        self.assertEqual(
            state["ui_version"],
            PHASE9E1_RESUME_WORKSPACE_UI_VERSION,
        )
        self.assertIsNone(state["approved_generation"])
        self.assertEqual(state["loaded_mode"], "working_draft")
        self.assertEqual(
            [row["generation_id"] for row in state["current_versions"]],
            ["revision-current"],
        )
        self.assertEqual(
            [row["generation_id"] for row in state["historical_versions"]],
            ["approved-old"],
        )
        self.assertEqual(
            [row["generation_id"] for row in state["browsable_versions"]],
            ["revision-current", "approved-old"],
        )

    def test_other_scope_versions_are_historical(self) -> None:
        approved = _generation("approved-current", "approved")
        old = _generation(
            "old-draft",
            "draft",
            decision="decision-old",
        )
        state = build_resume_workspace_state(
            generations=[approved, old],
            approved_generation=approved,
            loaded_generation_id="",
            phase9e_binding=_binding(),
        )
        self.assertEqual(
            state["historical_versions"][0]["generation_id"],
            "old-draft",
        )

    def test_pdf_preview_falls_back_when_streamlit_pdf_component_missing(self):
        path = (
            REPO_ROOT
            / "tailoring"
            / "phase9e1_resume_workspace_ui.py"
        )
        source = path.read_text(encoding="utf-8")

        # V8 first uses Streamlit's PDF renderer when available, and falls
        # back to the dependency-free iframe path if that renderer cannot run.
        self.assertIn(
            'pdf_renderer = getattr(st, "pdf", None)',
            source,
        )
        self.assertIn(
            "except StreamlitAPIException:",
            source,
        )
        self.assertIn(
            "st.iframe(",
            source,
        )
        self.assertNotIn(
            "components.html(",
            source,
        )
        self.assertNotIn(
            "streamlit.components.v1",
            source,
        )




    def test_workspace_exposes_revise_and_alternative_actions(self) -> None:
        text = (
            REPO_ROOT
            / "tailoring"
            / "phase9e1_resume_workspace_ui.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"Revise approved résumé"', text)
        self.assertIn('"Create alternative copy"', text)
        self.assertIn(
            '"Remove approval and continue editing"',
            text,
        )
        self.assertIn('"Preview selected résumé"', text)
        self.assertIn("archive_tailoring_generation(", text)

    def test_app_gates_mutation_while_approved_is_read_only(self) -> None:
        text = (REPO_ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("workspace_requires_edit_draft(", text)
        self.assertIn("workspace_edit_required", text)
        self.assertIn(
            "Revise approved résumé from the Résumé Workspace",
            text,
        )


if __name__ == "__main__":
    unittest.main()

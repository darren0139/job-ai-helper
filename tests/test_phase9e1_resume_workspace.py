"""Tests for the top Phase 9E.1 Résumé Workspace."""

from __future__ import annotations

import unittest
from pathlib import Path

from tailoring.phase9e1_resume_workspace_ui import (
    PHASE9E1_RESUME_WORKSPACE_UI_VERSION,
    build_resume_workspace_state,
)
from tailoring.phase9e1_workflow_ui import (
    build_application_workflow_overview,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _binding() -> dict:
    return {
        "scope_activation_status": "active",
        "current_scope_status": "current",
        "decision_fingerprint": "decision-current",
        "starting_snapshot_fingerprint": "snapshot-current",
        "workflow_action_fingerprint": "workflow-current",
        "selection": {"selected_source": "original_resume"},
    }


def _generation(
    generation_id: str,
    status: str,
    decision: str = "decision-current",
) -> dict:
    return {
        "generation_id": generation_id,
        "status": status,
        "generation_kind": "projects_skills",
        "generation_settings": {
            "phase9e_binding": {
                "decision_fingerprint": decision,
                "starting_snapshot_fingerprint": "snapshot-current",
                "workflow_action_fingerprint": "workflow-current",
            }
        },
        "fit_result": {"page_count": 1},
    }


class Phase9E1ResumeWorkspaceTests(unittest.TestCase):
    def test_workspace_separates_current_drafts_from_history(self) -> None:
        approved = _generation("approved-current", "approved")
        current_draft = _generation("draft-current", "draft")
        old_draft = _generation(
            "draft-old",
            "draft",
            decision="decision-old",
        )

        state = build_resume_workspace_state(
            generations=[current_draft, old_draft, approved],
            approved_generation=approved,
            loaded_generation_id="approved-current",
            phase9e_binding=_binding(),
        )

        self.assertEqual(
            state["ui_version"],
            PHASE9E1_RESUME_WORKSPACE_UI_VERSION,
        )
        self.assertEqual(state["loaded_mode"], "approved_read_only")
        self.assertEqual(
            [row["generation_id"] for row in state["current_drafts"]],
            ["draft-current"],
        )
        self.assertEqual(len(state["historical_versions"]), 1)

    def test_metadata_decision_fingerprint_marks_current_scope(
        self,
    ) -> None:
        approved = _generation(
            "approved-current",
            "approved",
            decision="old-settings-decision",
        )
        approved["phase9e_decision_fingerprint"] = "decision-current"

        state = build_resume_workspace_state(
            generations=[approved],
            approved_generation=approved,
            loaded_generation_id="",
            phase9e_binding=_binding(),
        )

        self.assertEqual(
            state["approved_generation"]["generation_id"],
            "approved-current",
        )
        self.assertEqual(len(state["historical_versions"]), 0)

    def test_metadata_decision_mismatch_stays_historical(self) -> None:
        old = _generation(
            "old-generation",
            "approved",
            decision="decision-current",
        )
        old["phase9e_decision_fingerprint"] = "decision-old"

        state = build_resume_workspace_state(
            generations=[old],
            approved_generation=old,
            loaded_generation_id="",
            phase9e_binding=_binding(),
        )

        self.assertIsNone(state["approved_generation"])
        self.assertEqual(len(state["historical_versions"]), 1)

    def test_active_phase9e_approved_result_is_not_called_optional_legacy(
        self,
    ) -> None:
        overview = build_application_workflow_overview(
            application_id=92,
            application_record={
                "job_title": "Associate, Configuration & QA",
                "company": "Garena",
            },
            baseline_report={},
            exact_jd={"source_version_id": "jdv-92"},
            current_decision=_binding(),
            current_result=None,
            legacy_approved_generation={
                "generation_id": "0d534ecf",
                "status": "approved",
                "fit_result": {"page_count": 1},
            },
            legacy_verification={
                "verification_id": "phase8-92",
            },
        )

        self.assertEqual(
            overview["workflow_mode"],
            "Phase 9E tailored workflow",
        )
        self.assertEqual(overview["phase9e_status"], "Active")
        self.assertIn("Approved · 1 page", overview["current_result"])

    def test_top_workspace_has_no_approval_action(self) -> None:
        text = (
            REPO_ROOT
            / "tailoring"
            / "phase9e1_resume_workspace_ui.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn('"Approve Selected"', text)
        self.assertNotIn('"Approve this', text)
        self.assertIn(
            '"Open read-only"',
            text,
        )
        self.assertIn(
            '"Revise approved résumé"',
            text,
        )
        self.assertIn(
            '"Create alternative copy"',
            text,
        )

    def test_clone_preserves_phase9e_identity_metadata(self) -> None:
        text = (
            REPO_ROOT
            / "database"
            / "tailoring_generation_control.py"
        ).read_text(encoding="utf-8")
        clone_start = text.index(
            "def restore_tailoring_generation_as_draft("
        )
        clone = text[clone_start:]
        for field in (
            "source_application_result_id",
            "base_content_fingerprint",
            "content_fingerprint",
            "content_changed",
            "phase9e_decision_fingerprint",
        ):
            self.assertIn(f"{field}=source.get(", clone)


if __name__ == "__main__":
    unittest.main()

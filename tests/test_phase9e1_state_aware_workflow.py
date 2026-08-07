"""Acceptance tests for Phase 9E.1 state-aware workflow presentation."""

from __future__ import annotations

import unittest
from pathlib import Path

from tailoring.phase9e1_workflow_ui import (
    PHASE9E1_WORKFLOW_UI_VERSION,
    build_application_workflow_overview,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _pending_original_decision() -> dict:
    return {
        "decision_id": "decision-92",
        "decision_fingerprint": "d" * 64,
        "scope_activation_status": "pending_confirmation",
        "current_scope_status": "legacy_current",
        "recommended_tailoring": "full_regeneration",
        "selection": {
            "selected_source": "original_resume",
            "selection_mode": "original_resume",
        },
        "starting_snapshot": {
            "source_fidelity": "persisted_profile_only",
        },
        "semantic_identity": {
            "role_family_classification": {
                "role_family_label": (
                    "Game Operations, Configuration & QA"
                ),
                "confidence": "high",
            },
        },
    }


class Phase9E1StateAwareWorkflowTests(unittest.TestCase):
    def test_legacy_approved_result_outranks_missing_phase9e_source(self) -> None:
        overview = build_application_workflow_overview(
            application_id=91,
            application_record={
                "job_title": "Associate, Configuration & QA",
                "company": "Garena",
            },
            baseline_report={},
            exact_jd={"source_version_id": "jdv-91"},
            current_decision=None,
            current_result=None,
            legacy_approved_generation={
                "generation_id": "44111645",
                "status": "approved",
                "fit_result": {"page_count": 1},
            },
            legacy_verification={
                "verification_id": "phase8-91",
                "blueprint_ready": True,
            },
        )

        self.assertEqual(
            overview["ui_version"],
            PHASE9E1_WORKFLOW_UI_VERSION,
        )
        self.assertEqual(
            overview["workflow_mode"],
            "Legacy approved workflow",
        )
        self.assertEqual(
            overview["current_source"],
            "Legacy approved résumé",
        )
        self.assertEqual(
            overview["current_result"],
            "Approved · 1 page · Phase 8 verified",
        )
        self.assertEqual(
            overview["phase9e_status"],
            "Optional — not selected",
        )
        self.assertIn(
            "Review or download",
            overview["next_action"],
        )

    def test_pending_source_is_proposed_not_current(self) -> None:
        overview = build_application_workflow_overview(
            application_id=92,
            application_record={},
            baseline_report={},
            exact_jd={"source_version_id": "jdv-92"},
            current_decision=_pending_original_decision(),
            current_result=None,
        )

        self.assertEqual(
            overview["current_source"],
            "Legacy generation scope",
        )
        self.assertEqual(
            overview["proposed_source"],
            "Original résumé",
        )
        self.assertEqual(
            overview["phase9e_status"],
            "Waiting for confirmation",
        )
        self.assertEqual(
            overview["next_action"],
            "Confirm the proposed starting-source change.",
        )

    def test_pending_migration_preserves_approved_current_result(self) -> None:
        overview = build_application_workflow_overview(
            application_id=91,
            application_record={},
            baseline_report={},
            exact_jd={"source_version_id": "jdv-91"},
            current_decision=_pending_original_decision(),
            current_result=None,
            legacy_approved_generation={
                "generation_id": "44111645",
                "status": "approved",
                "fit_result": {"page_count": 1},
            },
            legacy_verification={"verification_id": "phase8-91"},
        )

        self.assertEqual(
            overview["current_result"],
            "Approved · 1 page · Phase 8 verified",
        )
        self.assertEqual(
            overview["phase9e_status"],
            "Waiting for confirmation",
        )
        self.assertIn(
            "current approved résumé",
            overview["next_action"],
        )

    def test_main_flow_places_legacy_result_before_optional_migration(self) -> None:
        text = (REPO_ROOT / "app.py").read_text(encoding="utf-8")
        flow_start = text.index(
            "        has_current_legacy_result = False"
        )
        flow = text[flow_start:]
        legacy_result = flow.index(
            "render_current_legacy_resume_result("
        )
        optional_migration = flow.index(
            '"Optional Phase 9E source migration"'
        )
        phase9a = flow.index("render_evidence_opportunity_analysis(")

        self.assertLess(legacy_result, optional_migration)
        self.assertLess(optional_migration, phase9a)

    def test_generation_stages_have_user_facing_names(self) -> None:
        text = (REPO_ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn(
            'st.header("Tailor Résumé Content")',
            text,
        )
        self.assertIn(
            'st.subheader("Build and Fit Résumé Document")',
            text,
        )
        self.assertNotIn(
            'st.header("Tailor Resume for This Job")',
            text,
        )
        self.assertNotIn(
            'st.subheader("Generate Edited Resume Copy")',
            text,
        )

    def test_blueprint_lifecycle_is_state_aware(self) -> None:
        text = (REPO_ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn(
            "render_state_aware_blueprint_lifecycle(",
            text,
        )
        self.assertNotIn(
            '"Advanced: Blueprint lifecycle"',
            text,
        )

    def test_legacy_preview_diagnostics_are_collapsed(self) -> None:
        text = (
            REPO_ROOT
            / "tailoring"
            / "phase9e_blueprint_selection_ui.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "Workflow transition",
            text,
        )
        self.assertIn(
            "Review proposed source diagnostics",
            text,
        )


if __name__ == "__main__":
    unittest.main()

"""Regression tests for Phase 9E.1 workflow ordering and scope gating."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from tailoring.phase9e1_blueprint_lifecycle_ui import (
    load_blueprint_lifecycle_state,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class Phase9E1WorkflowStageOrderTests(unittest.TestCase):
    def test_main_flow_is_generate_fit_approve_verify_lifecycle(self) -> None:
        text = (REPO_ROOT / "app.py").read_text(encoding="utf-8")
        flow = text[text.index('st.header("Tailor Résumé Content")'):]

        tailor = flow.index('st.header("Tailor Résumé Content")')
        build = flow.index('st.subheader("Build and Fit Résumé Document")')
        approve = flow.index('st.subheader("Approve and Verify Résumé")')
        controls = flow.index("render_tailoring_generation_controls(", approve)
        phase8 = flow.index("render_phase8_verification(", controls)
        lifecycle = flow.index(
            "render_state_aware_blueprint_lifecycle(",
            phase8,
        )

        self.assertLess(tailor, build)
        self.assertLess(build, approve)
        self.assertLess(approve, controls)
        self.assertLess(controls, phase8)
        self.assertLess(phase8, lifecycle)

    def test_approval_panel_is_gated_by_fitted_output(self) -> None:
        text = (REPO_ROOT / "app.py").read_text(encoding="utf-8")
        flow = text[text.index('st.subheader("Build and Fit Résumé Document")'):]
        self.assertIn("has_fitted_output", flow)
        self.assertIn(
            "Generate and fit the résumé document before approving",
            flow,
        )

    @patch(
        "tailoring.phase9e1_blueprint_lifecycle_ui."
        "list_global_blueprints",
        return_value=[],
    )
    @patch(
        "tailoring.phase9e1_blueprint_lifecycle_ui."
        "list_blueprint_evaluations",
        return_value=[],
    )
    @patch(
        "tailoring.phase9e1_blueprint_lifecycle_ui."
        "list_blueprint_candidates",
        return_value=[],
    )
    @patch(
        "tailoring.phase9e1_blueprint_lifecycle_ui."
        "get_latest_tailoring_verification",
        return_value={"generation_id": "gen", "blueprint_ready": True},
    )
    @patch(
        "tailoring.phase9e1_blueprint_lifecycle_ui."
        "blueprint_candidate_eligibility",
    )
    @patch(
        "tailoring.phase9e1_blueprint_lifecycle_ui."
        "get_application_generation_control",
    )
    def test_normal_phase9e_generation_gets_current_scope_flag(
        self,
        get_control,
        eligibility,
        _verification,
        _candidates,
        _evaluations,
        _blueprints,
    ) -> None:
        get_control.return_value = {
            "approved_generation": {
                "generation_id": "gen",
                "status": "approved",
                "phase9e_decision_fingerprint": "decision-current",
                "source_application_result_id": "",
            }
        }

        def capture(*, generation_state, verification):
            self.assertIsNotNone(verification)
            self.assertTrue(generation_state["phase9e_scope_matches"])
            return {"eligible": True, "reasons": {}}

        eligibility.side_effect = capture

        state = load_blueprint_lifecycle_state(
            application_id=92,
            current_phase9e_decision_fingerprint="decision-current",
        )
        self.assertEqual(state["summary"]["current_stage"], "phase9b")

    @patch(
        "tailoring.phase9e1_blueprint_lifecycle_ui."
        "list_global_blueprints",
        return_value=[],
    )
    @patch(
        "tailoring.phase9e1_blueprint_lifecycle_ui."
        "list_blueprint_evaluations",
        return_value=[],
    )
    @patch(
        "tailoring.phase9e1_blueprint_lifecycle_ui."
        "list_blueprint_candidates",
        return_value=[],
    )
    @patch(
        "tailoring.phase9e1_blueprint_lifecycle_ui."
        "get_latest_tailoring_verification",
        return_value={"generation_id": "gen", "blueprint_ready": True},
    )
    @patch(
        "tailoring.phase9e1_blueprint_lifecycle_ui."
        "blueprint_candidate_eligibility",
    )
    @patch(
        "tailoring.phase9e1_blueprint_lifecycle_ui."
        "get_application_generation_control",
    )
    def test_different_phase9e_decision_still_fails_closed(
        self,
        get_control,
        eligibility,
        _verification,
        _candidates,
        _evaluations,
        _blueprints,
    ) -> None:
        get_control.return_value = {
            "approved_generation": {
                "generation_id": "gen",
                "status": "approved",
                "phase9e_decision_fingerprint": "decision-old",
                "source_application_result_id": "",
            }
        }

        def capture(*, generation_state, verification):
            self.assertFalse(generation_state["phase9e_scope_matches"])
            return {
                "eligible": False,
                "reasons": {"matches_current_phase9e_scope": False},
            }

        eligibility.side_effect = capture

        state = load_blueprint_lifecycle_state(
            application_id=92,
            current_phase9e_decision_fingerprint="decision-current",
        )
        self.assertEqual(state["summary"]["current_stage"], "phase8")


if __name__ == "__main__":
    unittest.main()

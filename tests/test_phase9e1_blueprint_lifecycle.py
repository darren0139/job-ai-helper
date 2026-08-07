# Tests for the Phase 9E.1 Blueprint Lifecycle stepper.

from __future__ import annotations

import unittest
from pathlib import Path

from tailoring.phase9e1_blueprint_lifecycle_ui import (
    PHASE9E1_BLUEPRINT_LIFECYCLE_UI_VERSION,
    build_blueprint_lifecycle_summary,
    resolve_blueprint_lifecycle_stage,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


class Phase9E1BlueprintLifecycleTests(unittest.TestCase):
    def test_phase8_when_candidate_is_not_eligible(self) -> None:
        self.assertEqual(
            resolve_blueprint_lifecycle_stage(
                candidate_eligible=False,
                candidate=None,
                evaluation=None,
                active_blueprint=None,
            ),
            "phase8",
        )

    def test_phase9b_opens_after_phase8_readiness(self) -> None:
        self.assertEqual(
            resolve_blueprint_lifecycle_stage(
                candidate_eligible=True,
                candidate=None,
                evaluation=None,
                active_blueprint=None,
            ),
            "phase9b",
        )

    def test_phase9c_opens_after_candidate_creation(self) -> None:
        self.assertEqual(
            resolve_blueprint_lifecycle_stage(
                candidate_eligible=True,
                candidate={"candidate_id": "candidate"},
                evaluation=None,
                active_blueprint=None,
            ),
            "phase9c",
        )

    def test_phase9d_opens_after_current_evaluation(self) -> None:
        self.assertEqual(
            resolve_blueprint_lifecycle_stage(
                candidate_eligible=True,
                candidate={"candidate_id": "candidate"},
                evaluation={"evaluation_id": "evaluation"},
                active_blueprint=None,
            ),
            "phase9d",
        )

    def test_phase9e_is_available_after_blueprint_activation(self) -> None:
        stage = resolve_blueprint_lifecycle_stage(
            candidate_eligible=True,
            candidate={"candidate_id": "candidate"},
            evaluation={"evaluation_id": "evaluation"},
            active_blueprint={"blueprint_id": "blueprint"},
        )
        self.assertEqual(stage, "phase9e")
        summary = build_blueprint_lifecycle_summary(
            current_stage=stage,
            candidate={"candidate_id": "candidate"},
            evaluation={"evaluation_id": "evaluation"},
            active_blueprint={"blueprint_id": "blueprint"},
        )
        self.assertEqual(
            summary["ui_version"],
            PHASE9E1_BLUEPRINT_LIFECYCLE_UI_VERSION,
        )
        self.assertEqual(
            [row["status"] for row in summary["stages"]],
            ["Complete", "Complete", "Complete", "Current"],
        )

    def test_app_uses_stepper_instead_of_blanket_collapse(self) -> None:
        text = (REPO_ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("render_state_aware_blueprint_lifecycle(", text)
        self.assertNotIn('"Advanced: Blueprint lifecycle"', text)


if __name__ == "__main__":
    unittest.main()

"""Tests for the Phase 9E.1 workflow overview model."""

from __future__ import annotations

import unittest

from tailoring.phase9e1_workflow_ui import (
    build_application_workflow_overview,
)


def decision(*, scope: str = "current", activation: str = "active") -> dict:
    return {
        "decision_id": "decision-1",
        "decision_fingerprint": "d" * 64,
        "scope_activation_status": activation,
        "current_scope_status": scope,
        "recommended_tailoring": "reuse_approved_source",
        "selection": {
            "selected_source": "global_blueprint",
            "selected_blueprint": {
                "display_name": "AI & Full-Stack — Primary Blueprint",
                "role_family_label": (
                    "AI & Full-Stack Software Engineering"
                ),
                "version_number": 1,
            },
        },
        "semantic_identity": {
            "role_family_classification": {
                "role_family_label": (
                    "AI & Full-Stack Software Engineering"
                ),
                "confidence": "high",
            }
        },
    }


class Phase9E1WorkflowOverviewTests(unittest.TestCase):
    def test_unbound_application_recommends_source_selection(self) -> None:
        overview = build_application_workflow_overview(
            application_id=92,
            application_record={"job_title": "QA Associate"},
            baseline_report={},
            exact_jd={"source_version_id": "jdv-92"},
            current_decision=None,
            current_result=None,
        )
        self.assertEqual(overview["current_source"], "Not selected")
        self.assertEqual(
            overview["next_action"],
            "Choose and confirm a starting résumé.",
        )

    def test_exact_source_result_is_presented_as_immutable(self) -> None:
        overview = build_application_workflow_overview(
            application_id=94,
            application_record={
                "job_title": "Software Engineer",
                "company": "Example",
            },
            baseline_report={},
            exact_jd={"source_version_id": "jdv-94"},
            current_decision=decision(),
            current_result={
                "application_result_id": "result-94",
                "result_fingerprint": "r" * 64,
                "initial_status": "reused_approved",
                "state": {},
            },
        )
        self.assertEqual(
            overview["current_source"],
            "AI & Full-Stack — Primary Blueprint",
        )
        self.assertEqual(
            overview["current_result"],
            "Reused approved blueprint",
        )
        self.assertIn("Review or download", overview["next_action"])

    def test_pending_result_requests_verification(self) -> None:
        overview = build_application_workflow_overview(
            application_id=95,
            application_record={},
            baseline_report={},
            exact_jd={"source_version_id": "jdv-95"},
            current_decision=decision(),
            current_result={
                "initial_status": (
                    "reused_unchanged_pending_application_verification"
                ),
                "state": {"current_verification_id": ""},
            },
        )
        self.assertIn(
            "Run deterministic current-JD verification",
            overview["next_action"],
        )

    def test_stale_source_recommends_reevaluation(self) -> None:
        overview = build_application_workflow_overview(
            application_id=96,
            application_record={},
            baseline_report={},
            exact_jd={"source_version_id": "jdv-96"},
            current_decision=decision(scope="stale"),
            current_result=None,
        )
        self.assertEqual(
            overview["current_result"],
            "Starting source is stale",
        )
        self.assertIn("Re-evaluate", overview["next_action"])


if __name__ == "__main__":
    unittest.main()

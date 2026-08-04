from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database import tailoring_version_manager as base_manager
from database.blueprint_evaluation_manager import (
    get_blueprint_evaluation_by_id,
    list_blueprint_evaluations,
)
from database.global_blueprint_manager import (
    approve_persisted_phase9c_evaluation,
    get_active_global_blueprint,
    list_global_blueprint_audit_events,
    list_global_blueprints,
    update_global_blueprint_display_metadata,
)
from tests.phase9d_test_support import (
    persist_historical_v2_evaluation,
    persist_non_provisional_evaluation,
    seed_phase9d_database,
)


OVERRIDE = {
    "accepted": True,
    "reason": "Source parity is strong while more target JDs are collected.",
}


class GlobalBlueprintManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.old_path = base_manager.DB_PATH
        self.database_path = Path(self.temporary.name) / "phase9d.sqlite"
        self.state = seed_phase9d_database(self.database_path)
        self.provisional = self.state["provisional_evaluation"]

    def tearDown(self) -> None:
        base_manager.DB_PATH = self.old_path
        self.temporary.cleanup()

    def approve_provisional(self):
        return approve_persisted_phase9c_evaluation(
            evaluation_id=self.provisional["evaluation_id"],
            evaluation_fingerprint=self.provisional["evaluation_fingerprint"],
            provisional_override=OVERRIDE,
            display_name="AI Engineering Blueprint",
            notes="Test metadata",
            actor_label="Test approver",
        )

    def source_rows(self):
        connection = sqlite3.connect(self.database_path)
        try:
            return {
                "candidate": connection.execute(
                    "SELECT snapshot_json FROM global_blueprint_candidates"
                ).fetchall(),
                "evaluation": connection.execute(
                    "SELECT evaluation_json FROM blueprint_cross_jd_evaluations "
                    "ORDER BY evaluation_id"
                ).fetchall(),
                "jds": connection.execute(
                    "SELECT id, raw_text, jd_profile_json FROM job_descriptions "
                    "ORDER BY id"
                ).fetchall(),
            }
        finally:
            connection.close()

    def test_exact_approval_is_persisted_once_and_reused_with_audit(self):
        before = self.source_rows()
        first = self.approve_provisional()
        second = self.approve_provisional()
        self.assertEqual(first["cache_status"], "miss")
        self.assertEqual(second["cache_status"], "hit_active")
        self.assertEqual(
            first["blueprint"]["blueprint_id"],
            second["blueprint"]["blueprint_id"],
        )
        self.assertEqual(first["blueprint"]["version_number"], 1)
        self.assertEqual(len(list_global_blueprints()), 1)
        events = list_global_blueprint_audit_events(
            blueprint_id=first["blueprint"]["blueprint_id"]
        )
        self.assertEqual(
            {event["event_type"] for event in events},
            {"approved_new", "exact_reuse"},
        )
        self.assertTrue(
            all(event["provisional_override"]["accepted"] for event in events)
        )
        self.assertEqual(before, self.source_rows())

    def test_new_version_supersedes_and_exact_old_version_reactivates(self):
        first = self.approve_provisional()["blueprint"]
        non_provisional = persist_non_provisional_evaluation(self.state)
        second_result = approve_persisted_phase9c_evaluation(
            evaluation_id=non_provisional["evaluation_id"],
            evaluation_fingerprint=non_provisional["evaluation_fingerprint"],
            actor_label="Test approver",
        )
        second = second_result["blueprint"]
        self.assertEqual(second["version_number"], 2)
        self.assertNotEqual(first["blueprint_id"], second["blueprint_id"])
        versions = list_global_blueprints()
        self.assertEqual(
            {row["blueprint_id"]: row["status"] for row in versions},
            {first["blueprint_id"]: "superseded", second["blueprint_id"]: "active"},
        )

        reactivated_result = self.approve_provisional()
        reactivated = reactivated_result["blueprint"]
        self.assertEqual(reactivated_result["cache_status"], "hit_reactivated")
        self.assertEqual(reactivated["blueprint_id"], first["blueprint_id"])
        self.assertEqual(reactivated["version_number"], 1)
        self.assertEqual(len(list_global_blueprints()), 2)
        versions = list_global_blueprints()
        self.assertEqual(
            [row["blueprint_id"] for row in versions if row["status"] == "active"],
            [first["blueprint_id"]],
        )
        events = list_global_blueprint_audit_events(
            role_family_id=first["role_family_id"]
        )
        self.assertEqual(len(events), 3)
        self.assertIn(
            "reactivated_exact_version",
            {event["event_type"] for event in events},
        )

    def test_audit_failure_rolls_back_reactivation_and_supersession(self):
        first = self.approve_provisional()["blueprint"]
        non_provisional = persist_non_provisional_evaluation(self.state)
        second = approve_persisted_phase9c_evaluation(
            evaluation_id=non_provisional["evaluation_id"],
            evaluation_fingerprint=non_provisional["evaluation_fingerprint"],
        )["blueprint"]
        with patch(
            "database.global_blueprint_manager._insert_audit_event",
            side_effect=RuntimeError("audit insert failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "audit insert failed"):
                self.approve_provisional()
        active = get_active_global_blueprint(first["role_family_id"])
        self.assertEqual(active["blueprint_id"], second["blueprint_id"])
        states = {
            row["blueprint_id"]: row["status"]
            for row in list_global_blueprints()
        }
        self.assertEqual(states[first["blueprint_id"]], "superseded")
        self.assertEqual(states[second["blueprint_id"]], "active")

    def test_display_metadata_does_not_change_identity(self):
        original = self.approve_provisional()["blueprint"]
        updated = update_global_blueprint_display_metadata(
            blueprint_id=original["blueprint_id"],
            display_name="Edited name",
            notes="Edited notes",
            actor_label="Metadata editor",
        )["blueprint"]
        self.assertEqual(
            updated["blueprint_fingerprint"], original["blueprint_fingerprint"]
        )
        self.assertEqual(updated["semantic_identity"], original["semantic_identity"])
        self.assertEqual(updated["display_name"], "Edited name")
        events = list_global_blueprint_audit_events(
            blueprint_id=original["blueprint_id"]
        )
        self.assertIn(
            "display_metadata_updated",
            {event["event_type"] for event in events},
        )

    def test_historical_evaluations_remain_listed_but_are_not_approvable(self):
        historical = persist_historical_v2_evaluation(self.provisional)
        listed = list_blueprint_evaluations()
        self.assertEqual(
            {row["evaluation_id"] for row in listed},
            {self.provisional["evaluation_id"], historical["evaluation_id"]},
        )
        self.assertEqual(
            get_blueprint_evaluation_by_id(historical["evaluation_id"]),
            historical,
        )
        with self.assertRaisesRegex(ValueError, "inspection-only"):
            approve_persisted_phase9c_evaluation(
                evaluation_id=historical["evaluation_id"],
                evaluation_fingerprint=historical["evaluation_fingerprint"],
                provisional_override=OVERRIDE,
            )


if __name__ == "__main__":
    unittest.main()

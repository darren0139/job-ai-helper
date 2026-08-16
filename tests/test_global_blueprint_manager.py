from __future__ import annotations

import hashlib
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
    PHASE9D_AVAILABILITY_EVENT_VERSION,
    PHASE9D_AVAILABILITY_POLICY_VERSION,
    approve_persisted_phase9c_evaluation,
    get_active_global_blueprint,
    init_global_blueprint_registry,
    list_active_global_blueprints_read_only,
    list_global_blueprint_audit_events,
    list_global_blueprints,
    list_reusable_global_blueprints,
    remove_global_blueprint_from_reuse,
    restore_global_blueprint_to_reuse,
    update_global_blueprint_display_metadata,
)
from tailoring.phase9d_global_blueprint import Phase9DApprovalError
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

    def test_remove_restore_is_exact_idempotent_and_preserves_identity(self):
        before_sources = self.source_rows()
        original = self.approve_provisional()["blueprint"]
        original_identity = original["semantic_identity"]
        original_snapshot = original["blueprint_snapshot"]
        original_activated_at = original["activated_at"]

        removed = remove_global_blueprint_from_reuse(
            blueprint_id=original["blueprint_id"],
            blueprint_fingerprint=original["blueprint_fingerprint"],
            acknowledged=True,
            actor_label="Lifecycle tester",
            reason="Retire this test source from future recommendations.",
        )
        self.assertEqual(removed["cache_status"], "removed")
        self.assertEqual(removed["blueprint"]["status"], "active")
        self.assertEqual(
            removed["blueprint"]["availability_status"], "removed"
        )
        self.assertFalse(removed["blueprint"]["is_reusable"])
        self.assertEqual(list_reusable_global_blueprints(), [])
        self.assertEqual(list_active_global_blueprints_read_only(), [])
        self.assertEqual(removed["blueprint"]["semantic_identity"], original_identity)
        self.assertEqual(removed["blueprint"]["blueprint_snapshot"], original_snapshot)
        self.assertEqual(removed["blueprint"]["activated_at"], original_activated_at)

        event_count = len(
            list_global_blueprint_audit_events(
                blueprint_id=original["blueprint_id"]
            )
        )
        repeated_remove = remove_global_blueprint_from_reuse(
            blueprint_id=original["blueprint_id"],
            blueprint_fingerprint=original["blueprint_fingerprint"],
            acknowledged=True,
        )
        self.assertEqual(repeated_remove["cache_status"], "hit_removed")
        self.assertEqual(
            len(
                list_global_blueprint_audit_events(
                    blueprint_id=original["blueprint_id"]
                )
            ),
            event_count,
        )
        with self.assertRaisesRegex(Phase9DApprovalError, "explicit Restore"):
            self.approve_provisional()

        restored = restore_global_blueprint_to_reuse(
            blueprint_id=original["blueprint_id"],
            blueprint_fingerprint=original["blueprint_fingerprint"],
            actor_label="Lifecycle tester",
        )
        self.assertEqual(restored["cache_status"], "restored")
        self.assertEqual(restored["blueprint"]["status"], "active")
        self.assertEqual(
            restored["blueprint"]["availability_status"], "available"
        )
        self.assertTrue(restored["blueprint"]["is_reusable"])
        self.assertEqual(restored["blueprint"]["activated_at"], original_activated_at)
        self.assertEqual(
            list_reusable_global_blueprints()[0]["blueprint_id"],
            original["blueprint_id"],
        )
        restored_event_count = len(
            list_global_blueprint_audit_events(
                blueprint_id=original["blueprint_id"]
            )
        )
        repeated_restore = restore_global_blueprint_to_reuse(
            blueprint_id=original["blueprint_id"],
            blueprint_fingerprint=original["blueprint_fingerprint"],
        )
        self.assertEqual(repeated_restore["cache_status"], "hit_available")
        self.assertEqual(
            len(
                list_global_blueprint_audit_events(
                    blueprint_id=original["blueprint_id"]
                )
            ),
            restored_event_count,
        )
        event_types = {
            event["event_type"]
            for event in list_global_blueprint_audit_events(
                blueprint_id=original["blueprint_id"]
            )
        }
        self.assertIn("removed_from_reuse", event_types)
        self.assertIn("restored_to_reuse", event_types)
        availability_events = [
            event
            for event in list_global_blueprint_audit_events(
                blueprint_id=original["blueprint_id"]
            )
            if event["event_type"]
            in {"removed_from_reuse", "restored_to_reuse"}
        ]
        self.assertEqual(len(availability_events), 2)
        self.assertEqual(
            {
                event["lifecycle_change"]["transition_number"]
                for event in availability_events
            },
            {1, 2},
        )
        self.assertTrue(
            all(
                event["event_version"]
                == PHASE9D_AVAILABILITY_EVENT_VERSION
                for event in availability_events
            )
        )
        self.assertTrue(
            all(
                event["lifecycle_change"][
                    "availability_policy_version"
                ]
                == PHASE9D_AVAILABILITY_POLICY_VERSION
                for event in availability_events
            )
        )
        self.assertEqual(before_sources, self.source_rows())

    def test_removed_v1_new_v2_is_available_and_old_restore_fails_closed(self):
        first = self.approve_provisional()["blueprint"]
        remove_global_blueprint_from_reuse(
            blueprint_id=first["blueprint_id"],
            blueprint_fingerprint=first["blueprint_fingerprint"],
            acknowledged=True,
        )
        non_provisional = persist_non_provisional_evaluation(self.state)
        second = approve_persisted_phase9c_evaluation(
            evaluation_id=non_provisional["evaluation_id"],
            evaluation_fingerprint=non_provisional["evaluation_fingerprint"],
        )["blueprint"]
        versions = {
            row["blueprint_id"]: row for row in list_global_blueprints()
        }
        self.assertEqual(versions[first["blueprint_id"]]["status"], "superseded")
        self.assertEqual(
            versions[first["blueprint_id"]]["availability_status"], "removed"
        )
        self.assertEqual(versions[second["blueprint_id"]]["status"], "active")
        self.assertEqual(
            versions[second["blueprint_id"]]["availability_status"], "available"
        )
        self.assertEqual(
            [row["blueprint_id"] for row in list_reusable_global_blueprints()],
            [second["blueprint_id"]],
        )
        with self.assertRaisesRegex(Phase9DApprovalError, "superseded"):
            restore_global_blueprint_to_reuse(
                blueprint_id=first["blueprint_id"],
                blueprint_fingerprint=first["blueprint_fingerprint"],
            )

    def test_remove_event_failure_rolls_back_projection(self):
        original = self.approve_provisional()["blueprint"]
        before_events = list_global_blueprint_audit_events(
            blueprint_id=original["blueprint_id"]
        )
        with patch(
            "database.global_blueprint_manager._insert_audit_event",
            side_effect=RuntimeError("availability audit failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "availability audit failed"):
                remove_global_blueprint_from_reuse(
                    blueprint_id=original["blueprint_id"],
                    blueprint_fingerprint=original["blueprint_fingerprint"],
                    acknowledged=True,
                )
        current = list_global_blueprints()[0]
        self.assertEqual(current["availability_status"], "available")
        self.assertTrue(current["is_reusable"])
        self.assertEqual(
            list_global_blueprint_audit_events(
                blueprint_id=original["blueprint_id"]
            ),
            before_events,
        )

    def test_restore_event_failure_rolls_back_projection(self):
        original = self.approve_provisional()["blueprint"]
        remove_global_blueprint_from_reuse(
            blueprint_id=original["blueprint_id"],
            blueprint_fingerprint=original["blueprint_fingerprint"],
            acknowledged=True,
        )
        before_events = list_global_blueprint_audit_events(
            blueprint_id=original["blueprint_id"]
        )
        with patch(
            "database.global_blueprint_manager._insert_audit_event",
            side_effect=RuntimeError("restore audit failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "restore audit failed"):
                restore_global_blueprint_to_reuse(
                    blueprint_id=original["blueprint_id"],
                    blueprint_fingerprint=original["blueprint_fingerprint"],
                )
        current = list_global_blueprints()[0]
        self.assertEqual(current["availability_status"], "removed")
        self.assertFalse(current["is_reusable"])
        self.assertEqual(
            list_global_blueprint_audit_events(
                blueprint_id=original["blueprint_id"]
            ),
            before_events,
        )

    def test_availability_migration_is_additive_and_idempotent(self):
        original = self.approve_provisional()["blueprint"]
        connection = sqlite3.connect(self.database_path)
        try:
            version_before = connection.execute(
                "SELECT * FROM global_blueprint_versions"
            ).fetchall()
            audit_before = connection.execute(
                "SELECT * FROM global_blueprint_audit_events"
            ).fetchall()
            connection.execute("DROP TABLE global_blueprint_availability")
            connection.commit()
        finally:
            connection.close()
        self.assertEqual(
            list_active_global_blueprints_read_only()[0]["blueprint_id"],
            original["blueprint_id"],
        )
        init_global_blueprint_registry()
        init_global_blueprint_registry()
        connection = sqlite3.connect(self.database_path)
        try:
            version_schema = connection.execute(
                """
                SELECT sql FROM sqlite_master
                WHERE type = 'table' AND name = 'global_blueprint_versions'
                """
            ).fetchone()[0]
            audit_schema = connection.execute(
                """
                SELECT sql FROM sqlite_master
                WHERE type = 'table' AND name = 'global_blueprint_audit_events'
                """
            ).fetchone()[0]
            availability_schema = connection.execute(
                """
                SELECT sql FROM sqlite_master
                WHERE type = 'table' AND name = 'global_blueprint_availability'
                """
            ).fetchone()[0]
            availability_rows = connection.execute(
                "SELECT COUNT(*) FROM global_blueprint_availability"
            ).fetchone()[0]
            version_after = connection.execute(
                "SELECT * FROM global_blueprint_versions"
            ).fetchall()
            audit_after = connection.execute(
                "SELECT * FROM global_blueprint_audit_events"
            ).fetchall()
        finally:
            connection.close()
        self.assertIn("'active', 'superseded'", version_schema)
        self.assertNotIn("'removed'", version_schema)
        self.assertNotIn("CHECK (event_type", audit_schema)
        self.assertIn("availability_status", availability_schema)
        self.assertEqual(availability_rows, 0)
        self.assertEqual(version_after, version_before)
        self.assertEqual(audit_after, audit_before)
        self.assertEqual(
            list_reusable_global_blueprints()[0]["blueprint_id"],
            original["blueprint_id"],
        )

    def test_passive_lifecycle_browsing_is_read_only(self):
        original = self.approve_provisional()["blueprint"]
        before = hashlib.sha256(self.database_path.read_bytes()).hexdigest()
        self.assertEqual(len(list_global_blueprints()), 1)
        self.assertEqual(len(list_reusable_global_blueprints()), 1)
        self.assertEqual(len(list_active_global_blueprints_read_only()), 1)
        self.assertIsNotNone(get_active_global_blueprint(original["role_family_id"]))
        self.assertGreaterEqual(
            len(
                list_global_blueprint_audit_events(
                    blueprint_id=original["blueprint_id"]
                )
            ),
            1,
        )
        after = hashlib.sha256(self.database_path.read_bytes()).hexdigest()
        self.assertEqual(after, before)

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

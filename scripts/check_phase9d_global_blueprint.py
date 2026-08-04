"""Real zero-cost Phase 9D smoke check using a temporary SQLite database."""

from __future__ import annotations

import tempfile
from pathlib import Path

from database import tailoring_version_manager as base_manager
from database.global_blueprint_manager import (
    approve_persisted_phase9c_evaluation,
    list_global_blueprint_audit_events,
    list_global_blueprints,
)
from tests.phase9d_test_support import (
    persist_non_provisional_evaluation,
    seed_phase9d_database,
)


OVERRIDE = {
    "accepted": True,
    "reason": "Source parity is strong while more target JDs are collected.",
}


def main() -> None:
    old_path = base_manager.DB_PATH
    try:
        with tempfile.TemporaryDirectory() as temporary:
            state = seed_phase9d_database(
                Path(temporary) / "phase9d-smoke.sqlite"
            )
            provisional = state["provisional_evaluation"]
            first = approve_persisted_phase9c_evaluation(
                evaluation_id=provisional["evaluation_id"],
                evaluation_fingerprint=provisional["evaluation_fingerprint"],
                provisional_override=OVERRIDE,
                actor_label="Phase 9D smoke",
            )
            exact = approve_persisted_phase9c_evaluation(
                evaluation_id=provisional["evaluation_id"],
                evaluation_fingerprint=provisional["evaluation_fingerprint"],
                provisional_override=OVERRIDE,
                actor_label="Phase 9D smoke",
            )
            non_provisional = persist_non_provisional_evaluation(state)
            second = approve_persisted_phase9c_evaluation(
                evaluation_id=non_provisional["evaluation_id"],
                evaluation_fingerprint=non_provisional[
                    "evaluation_fingerprint"
                ],
                actor_label="Phase 9D smoke",
            )
            reactivated = approve_persisted_phase9c_evaluation(
                evaluation_id=provisional["evaluation_id"],
                evaluation_fingerprint=provisional["evaluation_fingerprint"],
                provisional_override=OVERRIDE,
                actor_label="Phase 9D smoke",
            )
            first_blueprint = first["blueprint"]
            assert first["cache_status"] == "miss"
            assert exact["cache_status"] == "hit_active"
            assert second["blueprint"]["version_number"] == 2
            assert reactivated["cache_status"] == "hit_reactivated"
            assert reactivated["blueprint"]["blueprint_id"] == (
                first_blueprint["blueprint_id"]
            )
            assert reactivated["blueprint"]["version_number"] == 1
            assert provisional["aggregate_result"]["mean_score"] == 92.0
            snapshot = first_blueprint["blueprint_snapshot"]
            assert snapshot["frozen_resume_snapshot"][
                "resume_profile_snapshot"
            ] == state["candidate"]["resume_profile_snapshot"]
            assert snapshot["frozen_resume_snapshot"][
                "resume_text_snapshot"
            ] == state["candidate"]["resume_text_snapshot"]
            versions = list_global_blueprints()
            assert len(versions) == 2
            assert sum(row["status"] == "active" for row in versions) == 1
            events = list_global_blueprint_audit_events(
                role_family_id=first_blueprint["role_family_id"]
            )
            assert len(events) == 4
            print(
                "Phase 9D smoke PASS:",
                "source=92",
                f"v1={first_blueprint['blueprint_id'][:12]}",
                f"v2={second['blueprint']['blueprint_id'][:12]}",
                "exact_reuse=hit_active",
                "reactivation=hit_reactivated",
                f"audit_events={len(events)}",
            )
    finally:
        base_manager.DB_PATH = old_path


if __name__ == "__main__":
    main()

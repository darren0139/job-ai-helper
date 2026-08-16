"""Zero-cost smoke check for additive Blueprint Remove/Restore lifecycle."""

from __future__ import annotations

import tempfile
from pathlib import Path

from database import tailoring_version_manager as base_manager
from database.global_blueprint_manager import (
    approve_persisted_phase9c_evaluation,
    list_active_global_blueprints_read_only,
    list_global_blueprints,
    remove_global_blueprint_from_reuse,
    restore_global_blueprint_to_reuse,
)
from tailoring.phase9d_global_blueprint import Phase9DApprovalError
from tests.phase9d_test_support import (
    persist_non_provisional_evaluation,
    seed_phase9d_database,
)


OVERRIDE = {
    "accepted": True,
    "reason": "Smoke check accepts the provisional deterministic fixture.",
}


def main() -> None:
    original_path = base_manager.DB_PATH
    try:
        with tempfile.TemporaryDirectory(prefix="phase9d_availability_") as name:
            database_path = Path(name) / "availability.sqlite"
            state = seed_phase9d_database(database_path)
            evaluation = state["provisional_evaluation"]
            first = approve_persisted_phase9c_evaluation(
                evaluation_id=evaluation["evaluation_id"],
                evaluation_fingerprint=evaluation["evaluation_fingerprint"],
                provisional_override=OVERRIDE,
            )["blueprint"]
            remove_global_blueprint_from_reuse(
                blueprint_id=first["blueprint_id"],
                blueprint_fingerprint=first["blueprint_fingerprint"],
                acknowledged=True,
            )
            assert list_active_global_blueprints_read_only() == []
            try:
                approve_persisted_phase9c_evaluation(
                    evaluation_id=evaluation["evaluation_id"],
                    evaluation_fingerprint=evaluation["evaluation_fingerprint"],
                    provisional_override=OVERRIDE,
                )
            except Phase9DApprovalError as exc:
                assert "Restore" in str(exc)
            else:
                raise AssertionError("Removed exact approval did not fail closed.")

            restore_global_blueprint_to_reuse(
                blueprint_id=first["blueprint_id"],
                blueprint_fingerprint=first["blueprint_fingerprint"],
            )
            assert list_active_global_blueprints_read_only()[0][
                "blueprint_id"
            ] == first["blueprint_id"]
            remove_global_blueprint_from_reuse(
                blueprint_id=first["blueprint_id"],
                blueprint_fingerprint=first["blueprint_fingerprint"],
                acknowledged=True,
            )
            next_evaluation = persist_non_provisional_evaluation(state)
            second = approve_persisted_phase9c_evaluation(
                evaluation_id=next_evaluation["evaluation_id"],
                evaluation_fingerprint=next_evaluation[
                    "evaluation_fingerprint"
                ],
            )["blueprint"]
            versions = {
                row["blueprint_id"]: row for row in list_global_blueprints()
            }
            assert versions[first["blueprint_id"]]["status"] == "superseded"
            assert (
                versions[first["blueprint_id"]]["availability_status"]
                == "removed"
            )
            assert versions[second["blueprint_id"]]["status"] == "active"
            assert (
                versions[second["blueprint_id"]]["availability_status"]
                == "available"
            )
            print(
                "Blueprint availability smoke passed:",
                "remove=excluded",
                "restore=reused",
                "exact_reapproval=blocked",
                "new_version=available",
                "model_calls=0",
                "embedding_calls=0",
                "chroma_reads=0",
                "chroma_writes=0",
            )
    finally:
        base_manager.DB_PATH = original_path


if __name__ == "__main__":
    main()

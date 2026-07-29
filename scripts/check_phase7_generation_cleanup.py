from __future__ import annotations

import tempfile
from pathlib import Path

from database import tailoring_version_manager as base
from database.tailoring_generation_control import (
    approve_tailoring_generation,
    clear_tailoring_drafts,
    delete_tailoring_generation,
    get_application_generation_control,
    list_tailoring_generations,
    record_generation_metadata,
    set_tailoring_section_locks,
)


def _save(application_id: int, generation_id: str) -> None:
    base.save_application_tailoring_generation(
        application_id=application_id,
        generation_id=generation_id,
        projects={"recommended_projects": [{"title": generation_id}]},
        skills={
            "skill_lines": [
                {"category": "Programming", "items": ["Python"]}
            ]
        },
    )
    record_generation_metadata(
        application_id=application_id,
        generation_id=generation_id,
        input_fingerprint=f"fp-{generation_id}",
        generation_kind="projects_skills",
    )


def main() -> int:
    old_db = base.DB_PATH
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            base.DB_PATH = Path(temp_dir) / "applications.db"
            _save(77, "approved")
            _save(77, "draft-one")
            _save(77, "draft-two")
            _save(77, "archived")

            approve_tailoring_generation(77, "approved")
            from database.tailoring_generation_control import (
                archive_tailoring_generation,
            )
            archive_tailoring_generation(77, "archived")
            set_tailoring_section_locks(
                application_id=77,
                lock_projects=True,
                lock_skills=False,
            )

            delete_tailoring_generation(
                application_id=77,
                generation_id="archived",
            )
            cleared = clear_tailoring_drafts(application_id=77)
            remaining = list_tailoring_generations(77)
            lock_state = get_application_generation_control(77)

            passed = (
                cleared["deleted_count"] == 2
                and len(remaining) == 1
                and remaining[0]["status"] == "approved"
                and lock_state["lock_projects"] is True
                and bool(lock_state["updated_at"])
            )
            print("Drafts deleted:", cleared["deleted_count"])
            print(
                "Remaining:",
                [
                    (row["generation_id"], row["status"])
                    for row in remaining
                ],
            )
            print(
                "Saved locks:",
                lock_state["lock_projects"],
                lock_state["lock_skills"],
                lock_state["updated_at"],
            )
            print(
                "PHASE 7G GENERATION CLEANUP SMOKE TEST:",
                "PASS" if passed else "FAIL",
            )
            return 0 if passed else 1
    finally:
        base.DB_PATH = old_db


if __name__ == "__main__":
    raise SystemExit(main())

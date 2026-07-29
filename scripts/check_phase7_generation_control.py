from __future__ import annotations

import tempfile
from pathlib import Path

from database import tailoring_version_manager as base
from database.tailoring_generation_control import (
    approve_tailoring_generation,
    find_cached_tailoring_generation,
    get_application_generation_control,
    record_generation_metadata,
    restore_tailoring_generation_as_draft,
    set_tailoring_section_locks,
)


def main() -> int:
    old_db = base.DB_PATH
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            base.DB_PATH = Path(temp_dir) / "applications.db"
            base.save_application_tailoring_generation(
                application_id=7,
                generation_id="gen-approved",
                projects={"recommended_projects": [{"title": "QueryAI"}]},
                skills={
                    "skill_lines": [
                        {"category": "Languages", "items": ["Python"]}
                    ]
                },
            )
            record_generation_metadata(
                application_id=7,
                generation_id="gen-approved",
                input_fingerprint="fingerprint-7",
                generation_kind="projects_skills",
            )
            approve_tailoring_generation(7, "gen-approved")
            set_tailoring_section_locks(
                application_id=7,
                lock_projects=True,
                lock_skills=True,
            )
            cached = find_cached_tailoring_generation(
                application_id=7,
                input_fingerprint="fingerprint-7",
                generation_kind="projects_skills",
            )
            restored = restore_tailoring_generation_as_draft(
                application_id=7,
                source_generation_id="gen-approved",
                new_generation_id="gen-restored",
            )
            state = get_application_generation_control(7)

            passed = (
                cached is not None
                and cached["generation_id"] == "gen-approved"
                and state["lock_projects"] is True
                and state["lock_skills"] is True
                and restored["status"] == "draft"
            )
            print("Cache hit:", cached["generation_id"] if cached else None)
            print("Approved locks:", state["lock_projects"], state["lock_skills"])
            print("Restored status:", restored["status"])
            print("PHASE 7 SMOKE TEST:", "PASS" if passed else "FAIL")
            return 0 if passed else 1
    finally:
        base.DB_PATH = old_db


if __name__ == "__main__":
    raise SystemExit(main())

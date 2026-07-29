from __future__ import annotations

from tailoring.generation_cleanup_ui_model import (
    build_cleanup_rows,
    filter_cleanup_versions,
    selected_cleanup_versions,
)


def main() -> int:
    versions = [
        {
            "generation_id": "approved",
            "status": "approved",
            "generation_kind": "projects_skills",
            "updated_at": "2026-07-29T10:00:00",
        },
        {
            "generation_id": "draft-one",
            "status": "draft",
            "generation_kind": "projects_skills",
            "updated_at": "2026-07-29T11:00:00",
        },
        {
            "generation_id": "archived-one",
            "status": "archived",
            "generation_kind": "projects_skills",
            "updated_at": "2026-07-29T12:00:00",
        },
    ]

    visible = filter_cleanup_versions(versions, "All deletable")
    selected = selected_cleanup_versions(
        visible,
        ["draft-one", "archived-one"],
    )
    rows = build_cleanup_rows(
        selected,
        loaded_generation_id="draft-one",
    )

    passed = (
        len(visible) == 2
        and len(selected) == 2
        and rows[0]["Loaded"] == "Yes"
        and all(row["Status"] != "Approved" for row in rows)
    )

    print("Visible deletable versions:", len(visible))
    print("Selected versions:", len(selected))
    print("Rows:", rows)
    print(
        "PHASE 7G BULK CLEANUP UI SMOKE TEST:",
        "PASS" if passed else "FAIL",
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""
Live-style Phase 6B.2.1 shortened-title fallback check.

This script loads an existing Job AI Helper debug bundle, changes one selected
project from its full title to a shortened writer title, removes stronger
identity fields, and regenerates the Skills section.

It confirms that:
- QueryAI skills are still recognised as selected-project skills through
  ``unique_base_title``.
- Skills belonging only to the unselected Workout Buddy project are not
  incorrectly marked as selected-project support.

Run from the Job-AI-Helper repository root:

    python -m scripts.check_shortened_title_fallback ^
    "C:\\Users\\Admin\\Downloads\\app_82_openai_gpt-5.6-terra_debug_bundle_20260724_232117.json"

Note:
    ``tailor_skills_section`` makes one real analysis-model API call.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from tailoring.skills_section_tailor import tailor_skills_section


QUERYAI_SKILLS = {
    "react",
    "supabase",
    "postgresql",
    "postgrest",
    "row-level security",
}

UNSELECTED_WORKOUT_BUDDY_SKILLS = {
    "kotlin",
    "android studio",
    "coil",
}

IDENTITY_FIELDS_TO_REMOVE = {
    "project_id",
    "stable_project_id",
    "canonical_project_id",
    "display_title",
    "canonical_title",
}


def normalise(value: Any) -> str:
    """Normalise text for case-insensitive comparisons."""
    return " ".join(str(value or "").split()).strip().casefold()


def load_debug_bundle(path: Path) -> dict[str, Any]:
    """Load and validate the minimum debug-bundle structure used by this check."""
    if not path.exists():
        raise FileNotFoundError(f"Debug bundle not found: {path}")

    if not path.is_file():
        raise ValueError(f"Debug bundle path is not a file: {path}")

    try:
        bundle = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Debug bundle is not valid JSON: {exc}"
        ) from exc

    required_sections = (
        "analysis_report",
        "tailored_projects_result",
        "project_tailoring_inputs",
    )

    missing_sections = [
        section
        for section in required_sections
        if not isinstance(bundle.get(section), dict)
    ]

    if missing_sections:
        raise ValueError(
            "Debug bundle is missing required object section(s): "
            + ", ".join(missing_sections)
        )

    evidence_items = (
        bundle["project_tailoring_inputs"].get("evidence_items")
    )

    if not isinstance(evidence_items, list):
        raise ValueError(
            "project_tailoring_inputs.evidence_items must be a list."
        )

    return bundle


def find_selected_project(
    selected_projects_result: dict[str, Any],
    base_title: str,
) -> dict[str, Any] | None:
    """Find a selected project by the start of its title."""
    base_key = normalise(base_title)

    for project in selected_projects_result.get(
        "recommended_projects",
        [],
    ) or []:
        if not isinstance(project, dict):
            continue

        project_title = normalise(
            project.get("display_title")
            or project.get("title")
        )

        if project_title == base_key or project_title.startswith(
            f"{base_key} "
        ) or project_title.startswith(f"{base_key}("):
            return project

    return None


def priority_rows_by_skill(
    skills_result: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Index skill-priority rows by normalised skill name."""
    rows: dict[str, dict[str, Any]] = {}

    for row in skills_result.get("skill_priorities", []) or []:
        if not isinstance(row, dict):
            continue

        skill_key = normalise(row.get("skill"))
        if skill_key:
            rows[skill_key] = row

    return rows


def print_identity(project: dict[str, Any]) -> None:
    """Print the identity fields relevant to the fallback test."""
    print(
        json.dumps(
            {
                "project_id": project.get("project_id"),
                "stable_project_id": project.get(
                    "stable_project_id"
                ),
                "canonical_project_id": project.get(
                    "canonical_project_id"
                ),
                "title": project.get("title"),
                "display_title": project.get(
                    "display_title"
                ),
                "canonical_title": project.get(
                    "canonical_title"
                ),
            },
            indent=2,
            ensure_ascii=False,
        )
    )


def run_check(bundle_path: Path) -> int:
    """Run the shortened-title fallback check."""
    bundle = load_debug_bundle(bundle_path)

    report = bundle["analysis_report"]

    selected_projects_result = copy.deepcopy(
        bundle["tailored_projects_result"]
    )

    evidence_items = bundle[
        "project_tailoring_inputs"
    ]["evidence_items"]

    queryai_project = find_selected_project(
        selected_projects_result,
        "QueryAI",
    )

    if queryai_project is None:
        print(
            "FAIL: QueryAI was not found among "
            "tailored_projects_result.recommended_projects."
        )
        return 1

    print("Original QueryAI identity:")
    print_identity(queryai_project)

    # Force the fallback path:
    #
    # 1. Remove stable/canonical IDs.
    # 2. Remove the full display/canonical title.
    # 3. Leave only the shortened writer title "QueryAI".
    for field in IDENTITY_FIELDS_TO_REMOVE:
        queryai_project.pop(field, None)

    queryai_project["title"] = "QueryAI"

    print("\nForced shortened identity:")
    print_identity(queryai_project)

    print(
        "\nRegenerating the Skills section. "
        "This makes one real analysis-model API call..."
    )

    skills_result = tailor_skills_section(
        resume_profile=report.get("resume_profile", {}),
        jd_profile=report.get("jd_profile", {}),
        evidence_items=evidence_items,
        stable_analysis=report.get(
            "stable_analysis",
            {},
        ),
        selected_projects_result=selected_projects_result,
    )

    priorities = priority_rows_by_skill(skills_result)
    failures: list[str] = []

    print("\nQueryAI selected-project support:")

    for skill_name in sorted(QUERYAI_SKILLS):
        row = priorities.get(skill_name)

        if row is None:
            failures.append(
                f"{skill_name}: missing from skill priorities"
            )
            print(f"FAIL  {skill_name}: missing")
            continue

        supported = bool(
            row.get("selected_project_support")
        )
        methods = [
            str(method)
            for method in (
                row.get(
                    "selected_project_support_methods",
                    [],
                )
                or []
            )
        ]

        print(
            f"{'PASS' if supported else 'FAIL'}  "
            f"{row.get('skill')}: "
            f"supported={supported}, methods={methods}"
        )

        if not supported:
            failures.append(
                f"{skill_name}: "
                "selected_project_support was false"
            )

        if "unique_base_title" not in methods:
            failures.append(
                f"{skill_name}: unique_base_title was not used; "
                f"methods={methods}"
            )

    print("\nUnselected Workout Buddy checks:")

    for skill_name in sorted(
        UNSELECTED_WORKOUT_BUDDY_SKILLS
    ):
        row = priorities.get(skill_name)

        if row is None:
            print(
                f"PASS  {skill_name}: "
                "not included in skill priorities"
            )
            continue

        supported = bool(
            row.get("selected_project_support")
        )
        methods = [
            str(method)
            for method in (
                row.get(
                    "selected_project_support_methods",
                    [],
                )
                or []
            )
        ]

        print(
            f"{'FAIL' if supported else 'PASS'}  "
            f"{row.get('skill')}: "
            f"supported={supported}, methods={methods}"
        )

        if supported:
            failures.append(
                f"{skill_name}: incorrectly treated as "
                "coming from a selected project"
            )

    identity_debug = skills_result.get(
        "selected_project_identity_debug",
        {},
    )

    print("\nSelected-project identity debug:")
    print(
        json.dumps(
            identity_debug,
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )

    if failures:
        print("\nSHORTENED-TITLE FALLBACK: FAIL")

        for failure in failures:
            print(f"- {failure}")

        return 1

    print("\nSHORTENED-TITLE FALLBACK: PASS")
    print(
        "QueryAI was matched to "
        "'QueryAI (React, Team of 4)' through "
        "unique_base_title."
    )

    return 0


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Test Phase 6B.2.1 shortened-project-title "
            "fallback using an existing debug bundle."
        )
    )
    parser.add_argument(
        "debug_bundle",
        type=Path,
        help="Path to an app debug-bundle JSON file.",
    )
    return parser


def main() -> int:
    """CLI entry point."""
    args = build_parser().parse_args()

    try:
        return run_check(args.debug_bundle)
    except (FileNotFoundError, ValueError, KeyError) as exc:
        print(f"ERROR: {exc}")
        return 2
    except RuntimeError as exc:
        print(f"LLM/API ERROR: {exc}")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())

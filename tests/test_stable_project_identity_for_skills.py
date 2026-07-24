from __future__ import annotations

import unittest

from tailoring.project_identity import (
    PROJECT_IDENTITY_VERSION,
    build_selected_project_identity_index,
    match_evidence_project_to_selected,
)
from tailoring.stable_tailoring_ranking import (
    build_deterministic_skills_result,
)


def _stable_analysis() -> dict:
    return {
        "canonical_requirements": [
            {
                "requirement_id": "req_config",
                "text": "gaming product configuration",
                "atomic_focus": "configuration",
                "importance": "core",
                "group_weight_fraction": 1.0,
                "explicit_only_requirement": False,
            }
        ]
    }


def _resume_profile() -> dict:
    return {
        "skills": {
            "languages": ["Python"],
            "tools": ["Git"],
        }
    }


def _queryai_evidence() -> list[dict]:
    return [
        {
            "title": "QueryAI (React, Team of 4)",
            "skills": ["backend integration", "access control"],
            "tools": [
                "React",
                "PostgreSQL",
                "PostgREST",
                "Row-Level Security",
            ],
        },
        {
            "title": "Workout Buddy (Android Studio, Team of 5)",
            "skills": ["mobile app development"],
            "tools": ["Kotlin", "Coil"],
        },
    ]


def _build(selected: dict) -> dict:
    return build_deterministic_skills_result(
        raw_result={"skill_lines": [], "skill_priorities": [], "notes": []},
        resume_profile=_resume_profile(),
        evidence_items=_queryai_evidence(),
        stable_analysis=_stable_analysis(),
        selected_projects_result={"recommended_projects": [selected]},
        max_items=20,
    )


def _ranking_row(result: dict, skill: str) -> dict:
    return next(
        row
        for row in result["deterministic_skill_ranking"]
        if row["skill"].lower() == skill.lower()
    )


class StableProjectIdentityForSkillsTests(unittest.TestCase):
    def test_display_title_is_preferred_over_short_writer_title(self) -> None:
        result = _build(
            {
                "title": "QueryAI",
                "display_title": "QueryAI (React, Team of 4)",
                "project_id": "project_ad61f25e3416",
            }
        )

        row = _ranking_row(result, "PostgREST")
        self.assertTrue(row["selected_project_support"])
        self.assertIn(
            "exact_display_title",
            row["selected_project_support_methods"],
        )
        self.assertEqual(
            result["project_identity_version"],
            PROJECT_IDENTITY_VERSION,
        )

    def test_unique_base_title_matches_when_display_title_is_missing(self) -> None:
        result = _build({"title": "QueryAI"})

        row = _ranking_row(result, "Row-Level Security")
        self.assertTrue(row["selected_project_support"])
        self.assertIn(
            "unique_base_title",
            row["selected_project_support_methods"],
        )

    def test_short_and_full_selected_titles_produce_same_skill_lines(self) -> None:
        short_result = _build({"title": "QueryAI"})
        full_result = _build(
            {
                "title": "QueryAI (React, Team of 4)",
                "display_title": "QueryAI (React, Team of 4)",
            }
        )

        self.assertEqual(
            short_result["skill_lines"],
            full_result["skill_lines"],
        )
        self.assertEqual(
            [row["skill"] for row in short_result["skill_priorities"]],
            [row["skill"] for row in full_result["skill_priorities"]],
        )

    def test_project_id_can_match_a_renamed_evidence_item(self) -> None:
        selected = [
            {
                "title": "Old Internal Name",
                "display_title": "Old Internal Name",
                "project_id": "project_shared",
            }
        ]
        evidence = [
            {
                "title": "Renamed Public Project",
                "project_id": "project_shared",
            }
        ]

        index = build_selected_project_identity_index(
            selected_projects=selected,
            evidence_items=evidence,
        )
        matched, method = match_evidence_project_to_selected(
            evidence[0],
            index,
        )

        self.assertTrue(matched)
        self.assertEqual(method, "project_id")

    def test_ambiguous_base_title_is_not_assumed_selected(self) -> None:
        selected = [{"title": "Portal"}]
        evidence = [
            {"title": "Portal (React)"},
            {"title": "Portal (Vue)"},
        ]

        index = build_selected_project_identity_index(
            selected_projects=selected,
            evidence_items=evidence,
        )

        self.assertEqual(
            match_evidence_project_to_selected(evidence[0], index),
            (False, ""),
        )
        self.assertEqual(
            match_evidence_project_to_selected(evidence[1], index),
            (False, ""),
        )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest
from copy import deepcopy
from unittest.mock import patch

from tailoring.project_section_tailor import (
    PROJECT_BULLET_WRITING_PROMPT,
    PROJECT_CANDIDATE_SCORING_PROMPT,
    tailor_projects_section,
)
from tailoring.stable_tailoring_ranking import (
    PROJECT_RELEVANCE_METADATA_VERSION,
    apply_low_confidence_project_override,
    build_project_selection_preview,
    rank_projects_deterministically,
    select_complementary_projects,
)


def _requirement(
    requirement_id: str,
    text: str,
    *,
    importance: str = "required",
) -> dict:
    return {
        "requirement_id": requirement_id,
        "text": text,
        "atomic_focus": text,
        "importance": importance,
        "group_weight_fraction": 1.0,
        "explicit_only_requirement": False,
    }


def _candidate(title: str, bullet: str, *, tools: list[str] | None = None) -> dict:
    return {
        "title": title,
        "display_title": title,
        "currently_in_resume": True,
        "in_evidence_library": True,
        "resume_evidence": {"bullets": [bullet]},
        "evidence_library_evidence": {
            "bullets": [bullet],
            "skills": [],
            "tools": list(tools or []),
        },
    }


def _neutral_rows(candidates: list[dict]) -> list[dict]:
    return [
        {
            "title": candidate["title"],
            "display_title": candidate["display_title"],
            "final_score": 0,
            "requirement_matches": [],
            "matched_jd_requirements": [],
            "transferable_jd_requirements": [],
            "reason": "Model diagnostics are not authoritative.",
        }
        for candidate in candidates
    ]


def _rank(requirements: list[dict], candidates: list[dict], rows: list[dict] | None = None) -> list[dict]:
    ranked, _ = rank_projects_deterministically(
        ranked_rows=rows or _neutral_rows(candidates),
        project_candidates=candidates,
        stable_analysis={"canonical_requirements": requirements},
    )
    return ranked


def _relationship(row: dict, requirement_id: str) -> dict:
    return next(
        item
        for item in row["project_relevance"]["requirement_relationships"]
        if item["requirement_id"] == requirement_id
    )


class CapabilityAwareProjectRelevanceTests(unittest.TestCase):
    def test_workout_buddy_has_grounded_android_coverage_but_tokens_and_title_do_not(self):
        requirement = _requirement(
            "req_android",
            "Experience working with Android app development and Kotlin",
        )
        candidates = [
            _candidate(
                "Workout Buddy",
                "Led frontend implementation for a GPS-based Android application using Kotlin and Jetpack Compose.",
            ),
            _candidate("Kotlin Only", "Implemented a backend utility in Kotlin."),
            _candidate(
                "Android Studio Only",
                "Configured Android Studio tooling for a sample workspace.",
                tools=["Android Studio"],
            ),
            _candidate(
                "Android Kotlin Showcase",
                "Built a desktop scheduling tool in Python.",
            ),
        ]

        ranked = _rank([requirement], candidates)
        by_title = {row["title"]: row for row in ranked}
        workout = by_title["Workout Buddy"]
        workout_relationship = _relationship(workout, "req_android")

        self.assertEqual("Workout Buddy", ranked[0]["title"])
        self.assertEqual("direct", workout_relationship["match_label"])
        self.assertEqual(
            "mobile.android_development",
            workout_relationship["capability_id"],
        )
        self.assertTrue(workout_relationship["supporting_evidence_ids"])
        self.assertIn(
            "GPS-based Android application",
            workout_relationship["supporting_evidence_snippets"][0],
        )
        self.assertTrue(workout_relationship["contributes_to_ranking"])
        self.assertEqual(
            "supported_canonical_jd_coverage",
            workout["project_relevance"]["relevance_basis"],
        )
        self.assertEqual(
            ["mobile.android_development"],
            workout["project_relevance"]["recognized_requirement_capability_ids"],
        )
        self.assertEqual(
            ["mobile.android_development"],
            workout["project_relevance"]["supported_capability_ids"],
        )
        self.assertEqual(
            PROJECT_RELEVANCE_METADATA_VERSION,
            workout["project_relevance"]["metadata_version"],
        )

        for title in (
            "Kotlin Only",
            "Android Studio Only",
            "Android Kotlin Showcase",
        ):
            relationship = _relationship(by_title[title], "req_android")
            self.assertEqual("none", relationship["match_label"], title)
            self.assertEqual([], relationship["supporting_evidence_ids"], title)
            self.assertFalse(relationship["contributes_to_ranking"], title)
            self.assertEqual(0, by_title[title]["final_score"], title)
            self.assertEqual(
                ["mobile.android_development"],
                by_title[title]["project_relevance"][
                    "recognized_requirement_capability_ids"
                ],
                title,
            )
            self.assertEqual(
                [],
                by_title[title]["project_relevance"]["supported_capability_ids"],
                title,
            )

    def test_false_positive_guards_remain_none_in_complete_relationship_table(self):
        cases = (
            (
                _requirement("req_dsa", "Strong foundation in data structures and algorithms"),
                _candidate("Generic Data", "Built data queries for business dashboards."),
            ),
            (
                _requirement("req_graphics", "Experience with OpenGL and/or Vulkan"),
                _candidate("Generic Graphics", "Built graphics features for a game engine."),
            ),
            (
                _requirement("req_memory", "Memory and cache optimisation"),
                _candidate("Generic Performance", "Improved application performance."),
            ),
            (
                _requirement("req_cpp", "Experience developing software in C++"),
                _candidate("C Sharp Tool", "Implemented a desktop tool in C#."),
            ),
        )

        for requirement, candidate in cases:
            with self.subTest(requirement=requirement["requirement_id"]):
                row = _rank([requirement], [candidate])[0]
                relationship = _relationship(row, requirement["requirement_id"])
                self.assertEqual("none", relationship["match_label"])
                self.assertEqual([], relationship["supporting_evidence_ids"])
                self.assertEqual(0.0, relationship["coverage_points"])
                self.assertEqual(
                    "deterministic_fallback_suitability_only",
                    row["project_relevance"]["relevance_basis"],
                )
                self.assertEqual(
                    [relationship["capability_id"]],
                    row["project_relevance"][
                        "recognized_requirement_capability_ids"
                    ],
                )
                self.assertEqual(
                    [],
                    row["project_relevance"]["supported_capability_ids"],
                )

    def test_zero_coverage_preview_is_deterministic_and_override_does_not_create_evidence(self):
        requirement = _requirement("req_graphics", "Experience with OpenGL and/or Vulkan")
        candidates = [
            _candidate("CyberSphere", "Built an authentication dashboard and API."),
            _candidate("Job AI Helper", "Built resume workflow automation."),
        ]

        first = build_project_selection_preview(
            project_candidates=candidates,
            stable_analysis={"canonical_requirements": [requirement]},
            selected_count=1,
        )
        second = build_project_selection_preview(
            project_candidates=list(reversed(candidates)),
            stable_analysis={"canonical_requirements": [deepcopy(requirement)]},
            selected_count=1,
        )

        self.assertEqual(first["preview_fingerprint"], second["preview_fingerprint"])
        self.assertEqual(
            first["system_selected_projects"],
            second["system_selected_projects"],
        )
        self.assertTrue(first["low_confidence_selection"]["active"])
        for item in first["low_confidence_selection"]["eligible_low_confidence_candidates"]:
            self.assertEqual("none", item["jd_coverage"])
            self.assertFalse(item["has_proven_jd_coverage"])
            self.assertEqual(
                "deterministic_fallback_suitability_only",
                item["selection_basis"],
            )

        for row in _rank([requirement], candidates):
            relevance = row["project_relevance"]
            self.assertEqual(
                ["graphics.opengl_vulkan"],
                relevance["recognized_requirement_capability_ids"],
            )
            self.assertEqual([], relevance["supported_capability_ids"])
            self.assertEqual(
                "deterministic_fallback_suitability_only",
                relevance["relevance_basis"],
            )

        ranked = _rank([requirement], candidates)
        ranked, _ = select_complementary_projects(
            ranked_rows=ranked,
            selected_count=1,
        )
        default_id = first["low_confidence_selection"]["default_low_confidence_project_ids"][0]
        alternative_id = next(
            item["project_id"]
            for item in first["low_confidence_selection"]["eligible_low_confidence_candidates"]
            if item["project_id"] != default_id
        )
        overridden, debug = apply_low_confidence_project_override(
            ranked_rows=ranked,
            selected_count=1,
            override_project_ids=[alternative_id],
        )
        self.assertEqual("user_override", debug["selection_source"])
        self.assertEqual(alternative_id, overridden[0]["project_id"])
        self.assertEqual(0.0, overridden[0]["deterministic_coverage_score"])
        self.assertEqual([], overridden[0]["requirement_matches"])

    def test_public_generation_uses_existing_fallback_when_all_projects_have_zero_coverage(self):
        requirement = _requirement("req_graphics", "Experience with OpenGL and/or Vulkan")
        resume_profile = {
            "projects": [
                {"title": "CyberSphere", "bullets": ["Built an authentication dashboard and API."]},
                {"title": "Job AI Helper", "bullets": ["Built resume workflow automation."]},
            ]
        }

        def fake_ask_json(system_prompt: str, _user_prompt: str, **_kwargs) -> dict:
            if system_prompt == PROJECT_CANDIDATE_SCORING_PROMPT:
                return {
                    "candidate_project_scores": [
                        {
                            "title": title,
                            "requirement_matches": [],
                            "matched_jd_requirements": [],
                            "transferable_jd_requirements": [],
                            "reason": "Model diagnostics are not authoritative.",
                        }
                        for title in ("CyberSphere", "Job AI Helper")
                    ]
                }
            self.assertEqual(PROJECT_BULLET_WRITING_PROMPT, system_prompt)
            return {"project_bullet_plans": [], "notes_for_user": []}

        with patch(
            "tailoring.project_section_tailor.ask_json",
            side_effect=fake_ask_json,
        ) as ask_json:
            result = tailor_projects_section(
                resume_profile=resume_profile,
                jd_profile={"title": "Graphics developer"},
                evidence_items=[],
                max_projects=1,
                max_bullets_per_project=1,
                raw_jd_text=requirement["text"],
                stable_analysis={"canonical_requirements": [requirement]},
                model="unit-test-model",
            )

        self.assertEqual(2, ask_json.call_count)
        self.assertTrue(result["low_confidence_selection"]["active"])
        self.assertEqual(1, result["low_confidence_selection"]["fallback_slot_count"])
        self.assertEqual(1, len(result["recommended_projects"]))
        self.assertEqual(
            PROJECT_RELEVANCE_METADATA_VERSION,
            result["project_relevance_metadata_version"],
        )
        selected = result["recommended_projects"][0]
        self.assertEqual([], selected["requirement_matches"])
        self.assertFalse(selected["project_relevance"]["has_proven_jd_coverage"])

    def test_complementary_selection_exposes_unique_and_repeated_coverage(self):
        requirements = [
            _requirement("req_kotlin", "Kotlin"),
            _requirement("req_cpp", "C++"),
        ]
        candidates = [
            _candidate("Alpha Kotlin", "Built an Android application using Kotlin."),
            _candidate("Beta Kotlin", "Implemented a Kotlin application."),
            _candidate("C Plus Plus", "Built a C++ asset manager."),
        ]
        ranked = _rank(requirements, candidates)
        selected, _ = select_complementary_projects(
            ranked_rows=ranked,
            selected_count=2,
        )

        self.assertEqual(
            {"Alpha Kotlin", "C Plus Plus"},
            {row["title"] for row in selected[:2]},
        )
        selected_by_title = {row["title"]: row for row in selected}
        self.assertEqual(
            ["req_kotlin"],
            selected_by_title["Alpha Kotlin"]["project_relevance"][
                "unique_coverage_requirement_ids"
            ],
        )
        self.assertEqual(
            ["req_cpp"],
            selected_by_title["C Plus Plus"]["project_relevance"][
                "unique_coverage_requirement_ids"
            ],
        )
        repeated = selected_by_title["Beta Kotlin"]
        self.assertEqual(
            ["req_kotlin"],
            repeated["project_relevance"]["overlapping_coverage_requirement_ids"],
        )

    def test_contradictory_model_payloads_do_not_change_relevance_metadata(self):
        requirement = _requirement(
            "req_android",
            "Experience working with Android app development and Kotlin",
        )
        candidates = [
            _candidate(
                "Workout Buddy",
                "Led Android application implementation using Kotlin and Jetpack Compose.",
            ),
            _candidate("QueryAI", "Built database access workflows."),
        ]
        claimed = {
            "requirement_id": "req_android",
            "match_label": "direct",
            "evidence_snippets": ["Unsupported model claim."],
        }
        first_rows = _neutral_rows(candidates)
        first_rows[1]["requirement_matches"] = [claimed]
        first_rows[1]["final_score"] = 99
        second_rows = list(reversed(_neutral_rows(candidates)))
        second_rows[1]["requirement_matches"] = [deepcopy(claimed)]
        second_rows[1]["final_score"] = 99

        first = _rank([requirement], candidates, first_rows)
        second = _rank([requirement], candidates, second_rows)
        first_projection = [
            (row["title"], row["final_score"], row["project_relevance"])
            for row in first
        ]
        second_projection = [
            (row["title"], row["final_score"], row["project_relevance"])
            for row in second
        ]
        self.assertEqual(first_projection, second_projection)


if __name__ == "__main__":
    unittest.main()

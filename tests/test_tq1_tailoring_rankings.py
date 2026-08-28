from __future__ import annotations

import unittest
from unittest.mock import patch

from tailoring.project_section_tailor import (
    _build_complete_ranked_rows,
    build_project_candidate_pool,
    tailor_projects_section,
)

from tailoring.stable_tailoring_ranking import (
    PROJECT_RANKING_VERSION,
    SKILL_RANKING_VERSION,
    build_deterministic_skills_result,
    rank_projects_deterministically,
)


def _requirement(requirement_id: str, text: str) -> dict:
    return {
        "requirement_id": requirement_id,
        "text": text,
        "atomic_focus": text,
        "importance": "required",
        "group_weight_fraction": 1.0,
        "explicit_only_requirement": False,
    }


def _candidate(title: str, *bullets: str) -> dict:
    return {
        "title": title,
        "display_title": title,
        "currently_in_resume": True,
        "in_evidence_library": True,
        "resume_evidence": {"bullets": list(bullets)},
        "evidence_library_evidence": {
            "bullets": list(bullets),
            "skills": [],
            "tools": [],
        },
    }


def _raw_row(candidate: dict, requirement_id: str, *, model_claim: bool = False) -> dict:
    return {
        "title": candidate["title"],
        "display_title": candidate["display_title"],
        "final_score": 99 if model_claim else 1,
        "reason": "Model diagnostic only.",
        "requirement_matches": (
            [
                {
                    "requirement_id": requirement_id,
                    "match_label": "direct",
                    "evidence_snippets": ["Generic model claim."],
                }
            ]
            if model_claim
            else []
        ),
        "matched_jd_requirements": [],
        "transferable_jd_requirements": [],
    }


def _model_scoring_payload(rows: list[dict]) -> dict:
    """Return an intentionally model-authored Stage 1 scoring response."""
    return {"candidate_project_scores": rows}


def _contradictory_model_row(
    title: str,
    requirement_id: str,
    *,
    claim_match: bool,
    score: int,
    reason: str,
) -> dict:
    """Build a model row whose claims contradict a different model response."""
    return {
        "title": title,
        "must_have_match_score": score,
        "responsibility_match_score": score,
        "tool_domain_match_score": score,
        "evidence_strength_score": score,
        "impact_scope_score": score,
        "matched_jd_requirements": (
            ["Model-authored requirement phrase"] if claim_match else []
        ),
        "transferable_jd_requirements": (
            [] if claim_match else ["Different model-authored transferable claim"]
        ),
        "requirement_matches": (
            [
                {
                    "requirement_id": requirement_id,
                    "match_label": "direct",
                    "evidence_snippets": ["Model-authored relevance claim."],
                }
            ]
            if claim_match
            else []
        ),
        "reason": reason,
    }


def _deterministic_project_projection(rows: list[dict]) -> list[dict]:
    """Keep only final Python-owned project ranking fields for comparison."""
    return [
        {
            "title": row["title"],
            "final_score": row["final_score"],
            "requirement_matches": row["requirement_matches"],
            "reason": row["reason"],
            "ranking_explanation": row["ranking_explanation"],
            "matched_jd_requirements": row["matched_jd_requirements"],
            "transferable_jd_requirements": row["transferable_jd_requirements"],
        }
        for row in rows
    ]


def _rank(
    requirements: list[dict],
    candidates: list[dict],
    *,
    model_claim_titles: set[str] | None = None,
) -> list[dict]:
    model_claim_titles = model_claim_titles or set()
    rows, _ = rank_projects_deterministically(
        ranked_rows=[
            _raw_row(
                candidate,
                requirements[0]["requirement_id"],
                model_claim=candidate["title"] in model_claim_titles,
            )
            for candidate in candidates
        ],
        project_candidates=candidates,
        stable_analysis={"canonical_requirements": requirements},
    )
    return rows


class TQ1ProjectRankingTests(unittest.TestCase):
    def test_android_kotlin_explicit_evidence_outranks_generic_model_claim(self):
        requirement = _requirement(
            "req_android_kotlin",
            "Experience working with Android app development and Kotlin",
        )
        workout_buddy = _candidate(
            "Workout Buddy",
            "Led frontend implementation for a GPS-based Android application using Kotlin and Jetpack Compose.",
        )
        query_ai = _candidate(
            "QueryAI",
            "Implemented data queries and database access for a help-desk application.",
        )

        ranked = _rank(
            [requirement],
            [query_ai, workout_buddy],
            model_claim_titles={"QueryAI"},
        )

        self.assertEqual("Workout Buddy", ranked[0]["title"])
        # The bullet explicitly establishes Android and Kotlin, but it does
        # not itself state the complete experience/development requirement.
        # This is therefore the same conservative transferable label used by
        # stable evidence scoring for incomplete atomic-focus coverage.
        self.assertEqual("transferable", ranked[0]["requirement_matches"][0]["match_label"])
        self.assertEqual(
            "python_unrecognised_single_record_evidence",
            ranked[0]["requirement_matches"][0]["source"],
        )
        self.assertIn("Android app development and Kotlin", ranked[0]["reason"])
        self.assertIn("GPS-based Android application", ranked[0]["reason"])
        self.assertEqual([], ranked[1]["requirement_matches"])
        self.assertIn("No direct canonical JD requirement", ranked[1]["reason"])
        self.assertEqual(PROJECT_RANKING_VERSION, ranked[0]["ranking_version"])

    def test_data_word_alone_cannot_outrank_algorithms_evidence(self):
        requirement = _requirement(
            "req_algorithms",
            "Strong foundation in data structures and algorithms",
        )
        algorithm_lab = _candidate(
            "Algorithm Lab",
            "Implemented graph algorithms using efficient data structures for pathfinding.",
        )
        query_ai = _candidate(
            "QueryAI",
            "Built data queries and database workflows for users.",
        )

        ranked = _rank(
            [requirement],
            [query_ai, algorithm_lab],
            model_claim_titles={"QueryAI"},
        )

        self.assertEqual(["Algorithm Lab", "QueryAI"], [row["title"] for row in ranked])
        # One concrete evidence row covers data, structures, and algorithms:
        # 3/5 explicit stable-scoring tokens, above the shared direct boundary.
        self.assertEqual("direct", ranked[0]["requirement_matches"][0]["match_label"])
        self.assertEqual([], ranked[1]["requirement_matches"])
        self.assertEqual(0, ranked[1]["final_score"])

    def test_cpp_engine_evidence_is_transferable_without_claiming_unsupported_performance(self):
        requirement = _requirement(
            "req_cpp_native",
            "C++ high-performance native code for systems-oriented work",
        )
        engine = _candidate(
            "The Great Migration",
            "Built a C++ asset manager for a custom game engine and integrated FMOD.",
        )
        unrelated = _candidate(
            "Marketing Dashboard",
            "Built a software application with user-facing dashboards.",
        )

        ranked = _rank([requirement], [unrelated, engine])

        self.assertEqual("The Great Migration", ranked[0]["title"])
        match = ranked[0]["requirement_matches"][0]
        self.assertEqual("transferable", match["match_label"])
        self.assertIn("C++ asset manager", ranked[0]["reason"])
        self.assertEqual([], ranked[1]["requirement_matches"])

    def test_punctuation_adjacent_cpp_requirement_variants_preserve_explicit_cpp_evidence(self):
        migration = _candidate(
            "The Great Migration",
            "Built a C++ asset manager for a custom game engine and integrated FMOD.",
        )
        query_ai = _candidate(
            "QueryAI",
            "Built data queries and database workflows for users.",
        )

        for index, requirement_text in enumerate(
            (
                "Good foundation in modern C/C++programming",
                "Good foundation in modern C/C++ programming",
                "Good foundation in modern C++programming",
                "Good foundation in modern C++ programming",
            )
        ):
            with self.subTest(requirement_text=requirement_text):
                requirement = _requirement(f"req_cpp_{index}", requirement_text)
                ranked = _rank([requirement], [query_ai, migration])

                self.assertEqual("The Great Migration", ranked[0]["title"])
                self.assertGreater(ranked[0]["final_score"], 0)
                self.assertEqual(
                    "transferable",
                    ranked[0]["requirement_matches"][0]["match_label"],
                )
                self.assertEqual(
                    requirement["requirement_id"],
                    ranked[0]["requirement_matches"][0]["requirement_id"],
                )
                self.assertIn("C++ asset manager", ranked[0]["reason"])
                self.assertEqual([], ranked[1]["requirement_matches"])

    def test_unrelated_generic_project_has_no_inflated_rank(self):
        requirement = _requirement(
            "req_android_kotlin",
            "Experience working with Android app development and Kotlin",
        )
        unrelated = _candidate(
            "Generic Software Project",
            "Developed a software application and integrated system services.",
        )

        ranked = _rank([requirement], [unrelated], model_claim_titles={unrelated["title"]})

        self.assertEqual(0, ranked[0]["final_score"])
        self.assertEqual([], ranked[0]["requirement_matches"])
        self.assertIn("No direct canonical JD requirement", ranked[0]["reason"])

    def test_equal_scores_have_stable_evidence_tie_breaking(self):
        requirement = _requirement("req_kotlin", "Kotlin")
        alpha = _candidate("Alpha Android", "Built an Android application using Kotlin.")
        beta = _candidate("Beta Android", "Built an Android application using Kotlin.")

        first = _rank([requirement], [beta, alpha])
        second = _rank([requirement], [alpha, beta])

        self.assertEqual(["Alpha Android", "Beta Android"], [row["title"] for row in first])
        self.assertEqual(
            [row["title"] for row in first],
            [row["title"] for row in second],
        )
        self.assertEqual(
            [row["reason"] for row in first],
            [row["reason"] for row in second],
        )

    def test_contradictory_model_claims_cannot_change_final_project_ranking(self):
        """Stage 1 model prose is diagnostic; frozen facts own the final rank."""
        requirement = _requirement(
            "req_android_kotlin",
            "Experience working with Android app development and Kotlin",
        )
        workout_buddy = _candidate(
            "Workout Buddy",
            "Led frontend implementation for a GPS-based Android application using Kotlin and Jetpack Compose.",
        )
        query_ai = _candidate(
            "QueryAI",
            "Implemented data queries and database access for a help-desk application.",
        )
        candidates = [workout_buddy, query_ai]

        first_model_payload = _model_scoring_payload(
            [
                _contradictory_model_row(
                    "QueryAI",
                    requirement["requirement_id"],
                    claim_match=True,
                    score=5,
                    reason="QueryAI is the definitive Android/Kotlin match.",
                ),
                _contradictory_model_row(
                    "Workout Buddy",
                    requirement["requirement_id"],
                    claim_match=False,
                    score=0,
                    reason="Workout Buddy is unrelated.",
                ),
            ]
        )
        second_model_payload = _model_scoring_payload(
            [
                _contradictory_model_row(
                    "Workout Buddy",
                    requirement["requirement_id"],
                    claim_match=True,
                    score=5,
                    reason="Workout Buddy is unrelated despite its Android claim.",
                ),
                _contradictory_model_row(
                    "QueryAI",
                    requirement["requirement_id"],
                    claim_match=False,
                    score=0,
                    reason="QueryAI is the definitive Android/Kotlin match.",
                ),
            ]
        )

        first_input = _build_complete_ranked_rows(
            scoring_result=first_model_payload,
            project_candidates=candidates,
        )
        second_input = _build_complete_ranked_rows(
            scoring_result=second_model_payload,
            project_candidates=candidates,
        )
        first_ranked, _ = rank_projects_deterministically(
            ranked_rows=first_input,
            project_candidates=candidates,
            stable_analysis={"canonical_requirements": [requirement]},
        )
        second_ranked, _ = rank_projects_deterministically(
            ranked_rows=second_input,
            project_candidates=candidates,
            stable_analysis={"canonical_requirements": [requirement]},
        )

        self.assertEqual(
            _deterministic_project_projection(first_ranked),
            _deterministic_project_projection(second_ranked),
        )
        self.assertEqual(
            ["Workout Buddy", "QueryAI"],
            [row["title"] for row in first_ranked],
        )
        self.assertEqual("transferable", first_ranked[0]["requirement_matches"][0]["match_label"])
        self.assertEqual([], first_ranked[1]["requirement_matches"])
        self.assertNotEqual(
            first_ranked[0]["ai_diagnostic_final_score"],
            second_ranked[0]["ai_diagnostic_final_score"],
        )


class TQ1ProjectCandidateSetDeterminismTests(unittest.TestCase):
    def test_factual_candidate_pool_is_sorted_and_ignores_model_candidate_order(self):
        resume_profile = {
            "projects": [
                {
                    "title": "Workout Buddy",
                    "bullets": ["Built Android features with Kotlin."],
                },
                {
                    "title": "QueryAI",
                    "bullets": ["Built database access for a help-desk workflow."],
                },
            ]
        }
        pool = build_project_candidate_pool(
            resume_profile=resume_profile,
            evidence_items=[],
        )
        requirement = _requirement("req_kotlin", "Kotlin")

        model_rows = _build_complete_ranked_rows(
            scoring_result=_model_scoring_payload(
                [
                    _contradictory_model_row(
                        "Unknown model project",
                        requirement["requirement_id"],
                        claim_match=True,
                        score=5,
                        reason="This row must not create a candidate.",
                    ),
                    _contradictory_model_row(
                        "QueryAI",
                        requirement["requirement_id"],
                        claim_match=True,
                        score=5,
                        reason="Model order must not own the pool.",
                    ),
                    _contradictory_model_row(
                        "Workout Buddy",
                        requirement["requirement_id"],
                        claim_match=False,
                        score=0,
                        reason="Model order must not own the pool.",
                    ),
                ]
            ),
            project_candidates=pool,
        )

        self.assertEqual(["QueryAI", "Workout Buddy"], [item["title"] for item in pool])
        self.assertEqual(["QueryAI", "Workout Buddy"], [item["title"] for item in model_rows])

    def test_model_omission_fails_closed_before_subset_ranking(self):
        """The public orchestration retries once, then refuses a subset ranking."""
        requirement = _requirement("req_kotlin", "Kotlin")
        resume_profile = {
            "projects": [
                {
                    "title": "Workout Buddy",
                    "bullets": ["Built Android features with Kotlin."],
                },
                {
                    "title": "QueryAI",
                    "bullets": ["Built database access for a help-desk workflow."],
                },
            ]
        }
        omitted_response = _model_scoring_payload(
            [
                _contradictory_model_row(
                    "Workout Buddy",
                    requirement["requirement_id"],
                    claim_match=True,
                    score=5,
                    reason="Only one factual project returned.",
                )
            ]
        )

        with patch(
            "tailoring.project_section_tailor.ask_json",
            side_effect=[omitted_response, _model_scoring_payload([])],
        ) as ask_json:
            with self.assertRaisesRegex(
                RuntimeError,
                "Project scoring remained incomplete after one retry",
            ):
                tailor_projects_section(
                    resume_profile=resume_profile,
                    jd_profile={"title": "Android developer"},
                    evidence_items=[],
                    raw_jd_text="Kotlin",
                    stable_analysis={"canonical_requirements": [requirement]},
                    model="unit-test-model",
                )

        self.assertEqual(2, ask_json.call_count)


class TQ1SkillRankingTests(unittest.TestCase):
    def test_explicit_technical_skills_rank_above_generic_data_overlap(self):
        requirements = [
            _requirement("req_kotlin", "Kotlin"),
            _requirement("req_android", "Android application development"),
            _requirement("req_cpp", "C++"),
            _requirement("req_algorithms", "data structures and algorithms"),
        ]
        result = build_deterministic_skills_result(
            raw_result={},
            resume_profile={
                "skills": {
                    "languages": ["Kotlin", "C++"],
                    "platforms": ["Android"],
                    "concepts": ["Data", "Communication"],
                }
            },
            evidence_items=[],
            stable_analysis={"canonical_requirements": requirements},
        )
        rows = {row["skill"]: row for row in result["deterministic_skill_ranking"]}
        direct_priorities = [
            rows[skill]["deterministic_priority_score"]
            for skill in ("Kotlin", "Android", "C++")
        ]

        self.assertTrue(all(rows[skill]["required_match"] for skill in ("Kotlin", "Android", "C++")))
        self.assertTrue(all(score > rows["Data"]["deterministic_priority_score"] for score in direct_priorities))
        self.assertEqual([], rows["Data"]["matched_requirement_ids"])
        self.assertIn("No direct canonical JD requirement", rows["Data"]["reason"])
        self.assertIn("Kotlin", rows["Kotlin"]["reason"])
        self.assertEqual(SKILL_RANKING_VERSION, result["skill_ranking_version"])

    def test_cpp_skill_matches_punctuation_adjacent_cpp_requirement_above_unrelated_data(self):
        requirement = _requirement(
            "req_cpp",
            "Good foundation in modern C/C++programming",
        )
        result = build_deterministic_skills_result(
            raw_result={},
            resume_profile={
                "skills": {
                    "languages": ["C++"],
                    "concepts": ["Data"],
                }
            },
            evidence_items=[],
            stable_analysis={"canonical_requirements": [requirement]},
        )
        rows = {row["skill"]: row for row in result["deterministic_skill_ranking"]}

        self.assertTrue(rows["C++"]["required_match"])
        self.assertEqual(
            [requirement["requirement_id"]],
            rows["C++"]["matched_requirement_ids"],
        )
        self.assertGreater(
            rows["C++"]["deterministic_priority_score"],
            rows["Data"]["deterministic_priority_score"],
        )
        self.assertEqual([], rows["Data"]["matched_requirement_ids"])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import copy
import unittest
from pathlib import Path

from tailoring.phase9f_starting_source_ranking import (
    canonical_json,
    order_scored_candidates,
    ranking_policy_identity,
    rank_starting_resume_sources,
)
from tailoring.phase9f_starting_source_transparency import (
    MAX_EVIDENCE_SNIPPET_CHARS,
    build_ranking_transparency,
    build_requirement_comparison_csv,
    compact_requirement_transparency,
)
from tests.test_phase9f_starting_source_ranking import (
    make_base,
    make_blueprint,
    make_exact_jd,
    metric_candidate,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _metric_result(rows: list[dict]) -> dict:
    ordered = order_scored_candidates(rows)
    return {
        "ranking_input_fingerprint": "ranking-input",
        "ranking_fingerprint": "ranking-result",
        "semantic_identity": {"ranking_policy": ranking_policy_identity()},
        "source_provenance": [],
        "ranked_candidates": ordered,
        "recommended_source": copy.deepcopy(ordered[0]),
    }


class Phase9FStartingSourceTransparencyTests(unittest.TestCase):
    def test_material_winner_explains_first_decisive_rule_and_failed_prior(self):
        base = metric_candidate(
            "Base Resume",
            "neutral_base_resume",
            {
                "overall": 48,
                "required_core": 46,
                "preferred": 49,
                "evidence": 59,
                "important_gaps": 3,
                "deal_breaker_gaps": 0,
            },
            "high",
        )
        same_family = metric_candidate(
            "AI Blueprint",
            "same_family",
            {
                "overall": 44,
                "required_core": 41,
                "preferred": 47,
                "evidence": 61,
                "important_gaps": 5,
                "deal_breaker_gaps": 0,
            },
            "high",
        )
        result = _metric_result([same_family, base])
        transparency = build_ranking_transparency(result)

        explanation = transparency["winner_explanation"]
        self.assertEqual(explanation["winner_name"], "Base Resume")
        self.assertEqual(
            explanation["deciding_rule"],
            "required_core_coverage_score",
        )
        self.assertEqual(explanation["near_tie_status"], "outside_tolerance")
        failed = {
            row["metric_key"]
            for row in explanation["failed_near_tie_checks"]
        }
        self.assertIn("required_core_coverage_score", failed)
        self.assertIn("deterministic_alignment_score", failed)
        self.assertIn("important_gap_count", failed)

    def test_genuine_canonical_tie_explains_same_family_prior(self):
        values = {
            "overall": 7,
            "required_core": 2,
            "preferred": 10,
            "evidence": 40,
            "important_gaps": 12,
            "deal_breaker_gaps": 0,
        }
        cross = metric_candidate("Cross", "cross_family", values, "high")
        same = metric_candidate("Same", "same_family", values, "high")
        cross["normalized_source_fingerprint"] = "0" * 64
        same["normalized_source_fingerprint"] = "f" * 64
        transparency = build_ranking_transparency(
            _metric_result([cross, same])
        )

        pairwise = transparency["pairwise_comparison"]
        self.assertEqual(pairwise["winner_name"], "Same")
        self.assertTrue(pairwise["canonical_metrics_equal"])
        self.assertTrue(pairwise["all_candidates_canonical_metrics_equal"])
        self.assertTrue(pairwise["role_family_prior_applied"])
        self.assertTrue(pairwise["winner_role_family_prior_eligible"])
        self.assertEqual(pairwise["near_tie_status"], "applied")
        self.assertEqual(pairwise["failed_near_tie_checks"], [])
        self.assertIn("every calibrated near-tie check passed", pairwise["role_family_prior_reason"])
        self.assertIn(
            "calibrated near tie",
            transparency["winner_explanation"]["headline"],
        )
        self.assertIn(
            "All eligible candidates",
            " ".join(transparency["winner_explanation"]["summary_lines"]),
        )

    def test_same_family_candidate_outside_tolerance_is_explicit(self):
        cross = metric_candidate(
            "Cross",
            "cross_family",
            {
                "overall": 70,
                "required_core": 70,
                "preferred": 70,
                "evidence": 70,
                "important_gaps": 0,
                "deal_breaker_gaps": 0,
            },
            "high",
        )
        same = metric_candidate(
            "Same",
            "same_family",
            {
                "overall": 60,
                "required_core": 60,
                "preferred": 60,
                "evidence": 60,
                "important_gaps": 1,
                "deal_breaker_gaps": 0,
            },
            "high",
        )
        explanation = build_ranking_transparency(
            _metric_result([same, cross])
        )["winner_explanation"]
        self.assertEqual(explanation["near_tie_status"], "outside_tolerance")
        self.assertGreater(len(explanation["failed_near_tie_checks"]), 0)

    def test_requirement_comparison_preserves_semantic_results_and_ids(self):
        exact_jd = make_exact_jd()
        base, artifact = make_base(strong=False)
        blueprint = make_blueprint(
            strong=True,
            role_family_id="ai_fullstack_software_engineering",
            role_family_label="AI & Full-Stack Software Engineering",
            marker="transparency",
        )
        result = rank_starting_resume_sources(
            exact_jd=exact_jd,
            current_base_resume=base,
            current_base_artifact=artifact,
            global_blueprints=[blueprint],
        )
        transparency = build_ranking_transparency(result)
        rows = transparency["requirement_comparison"]
        expected_ids = set(exact_jd["canonical_requirement_ids"])

        self.assertEqual({row["requirement_id"] for row in rows}, expected_ids)
        for candidate in result["ranked_candidates"]:
            semantic = {
                row["requirement_id"]: (
                    row["match_label"],
                    row["evidence_strength"],
                )
                for row in candidate["canonical_requirement_results"]
            }
            displayed = {
                row["requirement_id"]: (
                    row["match_label"],
                    row["evidence_strength"],
                )
                for row in rows
                if row["source_name"] == candidate["source_display_name"]
            }
            self.assertEqual(displayed, semantic)

    def test_supporting_evidence_is_candidate_scoped_and_clipped(self):
        long_text = "Evidence " + ("specific detail " * 40)
        first = compact_requirement_transparency(
            [
                {
                    "requirement_id": "req_1",
                    "text": "Build an application",
                    "importance": "core",
                    "match_label": "direct",
                    "evidence_strength": 5,
                    "evidence": [
                        {
                            "section": "projects",
                            "source": "resume_profile.projects[0].bullets[0]",
                            "text": long_text,
                            "reason": "Exact visible evidence",
                        }
                    ],
                }
            ],
            [],
        )
        second = compact_requirement_transparency(
            [
                {
                    "requirement_id": "req_1",
                    "text": "Build an application",
                    "importance": "core",
                    "match_label": "none",
                    "evidence_strength": 0,
                    "evidence": [],
                }
            ],
            [],
        )
        snippet = first[0]["supporting_evidence"][0]["text"]
        self.assertLessEqual(len(snippet), MAX_EVIDENCE_SNIPPET_CHARS)
        self.assertEqual(second[0]["supporting_evidence"], [])
        first[0]["supporting_evidence"][0]["text"] = "mutated"
        self.assertEqual(second[0]["supporting_evidence"], [])

    def test_base_resume_has_uniform_current_context_without_fake_history(self):
        exact_jd = make_exact_jd()
        base, artifact = make_base(strong=True)
        blueprint = make_blueprint(
            strong=False,
            role_family_id="backend_cloud_software_engineering",
            role_family_label="Backend & Cloud Software Engineering",
            marker="history",
        )
        result = rank_starting_resume_sources(
            exact_jd=exact_jd,
            current_base_resume=base,
            current_base_artifact=artifact,
            global_blueprints=[blueprint],
        )
        transparency = build_ranking_transparency(result)
        base_context = next(
            row
            for row in transparency["source_context"]
            if row["source_type"] == "base_resume"
        )
        blueprint_context = next(
            row
            for row in transparency["source_context"]
            if row["source_type"] == "global_blueprint"
        )
        self.assertEqual(
            base_context["historical_blueprint_score_label"],
            "Not applicable",
        )
        self.assertFalse(
            base_context["historical_blueprint_provenance_applicable"]
        )
        self.assertTrue(
            blueprint_context["historical_blueprint_provenance_applicable"]
        )
        self.assertNotIn("phase8_verification", base_context)
        self.assertNotIn("phase9c_evaluation", base_context)

    def test_transparency_and_keyword_display_do_not_change_fingerprints(self):
        exact_jd = make_exact_jd()
        base, artifact = make_base(strong=True)
        blueprint = make_blueprint(
            strong=True,
            role_family_id="ai_fullstack_software_engineering",
            role_family_label="AI & Full-Stack Software Engineering",
            marker="fingerprint",
        )
        result = rank_starting_resume_sources(
            exact_jd=exact_jd,
            current_base_resume=base,
            current_base_artifact=artifact,
            global_blueprints=[blueprint],
        )
        before = canonical_json(result)
        fingerprint = result["ranking_fingerprint"]
        comparison_fingerprints = [
            row["comparison_result_fingerprint"]
            for row in result["ranked_candidates"]
        ]

        first = build_ranking_transparency(result)
        second = build_ranking_transparency(result)

        repeated_display_only = copy.deepcopy(result)
        for candidate in repeated_display_only["ranked_candidates"]:
            for row in candidate.get("canonical_requirement_transparency", []):
                row["matched_keyword"] = (
                    str(row.get("matched_keyword") or "") + " Python" * 20
                ).strip()
        repeated = build_ranking_transparency(repeated_display_only)

        self.assertEqual(first, second)
        self.assertEqual(canonical_json(result), before)
        self.assertEqual(result["ranking_fingerprint"], fingerprint)
        self.assertEqual(
            [
                row["comparison_result_fingerprint"]
                for row in result["ranked_candidates"]
            ],
            comparison_fingerprints,
        )
        self.assertEqual(
            repeated["winner_explanation"],
            first["winner_explanation"],
        )
        self.assertEqual(
            repeated["pairwise_comparison"],
            first["pairwise_comparison"],
        )
        self.assertEqual(
            repeated_display_only["ranking_fingerprint"],
            fingerprint,
        )

    def test_requirement_comparison_csv_is_deterministic(self):
        transparency = {
            "requirement_comparison": [
                {
                    "requirement_id": "req_1",
                    "requirement_text": "Build secure backend APIs",
                    "importance": "core",
                    "source_rank": 1,
                    "source_name": "Base Resume",
                    "source_type": "base_resume",
                    "match_label": "transferable",
                    "evidence_strength": 4,
                    "evidence_section": "projects",
                    "evidence_source": "resume_profile.projects[0].bullets[0]",
                    "supporting_evidence": (
                        "Implemented Row-Level Security policies and PostgREST "
                        "data access."
                    ),
                    "matched_keyword": "Row-Level Security",
                    "deterministic_reason_code": "taxonomy_cap",
                    "deterministic_reason": "Evidence is related but bounded.",
                    "taxonomy_cap_status": "applied",
                    "capability_id": "backend_access_control",
                }
            ]
        }

        first = build_requirement_comparison_csv(transparency)
        second = build_requirement_comparison_csv(copy.deepcopy(transparency))

        self.assertEqual(first, second)
        self.assertTrue(first.startswith("Requirement ID,Requirement,"))
        self.assertIn("Matched keyword", first)
        self.assertIn("Row-Level Security", first)
        self.assertIn("Implemented Row-Level Security policies", first)
        self.assertIn("backend_access_control", first)

    def test_transparency_is_zero_cost_and_has_no_scoring_path(self):
        source = (
            REPO_ROOT
            / "tailoring"
            / "phase9f_starting_source_transparency.py"
        ).read_text(encoding="utf-8")
        for prohibited in (
            "build_stable_analysis",
            "build_deterministic_keyword_match",
            "global_blueprint_manager",
            "global_master_resume_manager",
            "sqlite3",
            "jd_chroma",
            "import llm",
        ):
            self.assertNotIn(prohibited, source)
        transparency = build_ranking_transparency(
            _metric_result(
                [
                    metric_candidate(
                        "Only",
                        "neutral_base_resume",
                        {
                            "overall": 1,
                            "required_core": 1,
                            "preferred": 1,
                            "evidence": 1,
                            "important_gaps": 0,
                            "deal_breaker_gaps": 0,
                        },
                        "low",
                    )
                ]
            )
        )
        self.assertEqual(
            transparency["zero_cost_diagnostics"],
            {
                "model_call_count": 0,
                "embedding_call_count": 0,
                "chroma_read_count": 0,
                "chroma_write_count": 0,
                "persistence_write_count": 0,
            },
        )


if __name__ == "__main__":
    unittest.main()

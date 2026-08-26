from __future__ import annotations

import unittest
from unittest.mock import patch

import tailoring.jd_specific_rephrase_preview as preview


class JDScoreOptimizationReviewTests(unittest.TestCase):
    def _generation(self):
        return {
            "projects": {
                "recommended_projects": [
                    {
                        "project_id": "p1",
                        "title": "Project One",
                        "draft_bullets": [
                            "Built a backend service.",
                            "Implemented a user workflow.",
                        ],
                    }
                ]
            }
        }

    def _contexts(self):
        return [
            {
                "project_index": 0,
                "bullet_index": 0,
                "project_title": "Project One",
                "current_bullet": "Built a backend service.",
            },
            {
                "project_index": 0,
                "bullet_index": 1,
                "project_title": "Project One",
                "current_bullet": "Implemented a user workflow.",
            },
        ]

    @patch.object(
        preview,
        "build_rephrase_batch_contexts",
    )
    @patch.object(
        preview,
        "suggest_jd_specific_rephrases_batch",
    )
    @patch.object(
        preview,
        "evaluate_rephrase_candidate",
    )
    def test_only_positive_safe_score_gain_is_exposed(
        self,
        evaluate,
        suggest,
        build_contexts,
    ):
        build_contexts.return_value = self._contexts()
        suggest.return_value = {
            "suggestion_count": 2,
            "suggestions": [
                {
                    "project_index": 0,
                    "bullet_index": 0,
                    "suggested_bullet": (
                        "Built a PostgreSQL-backed backend service."
                    ),
                    "safe_for_lineage_evaluation": True,
                },
                {
                    "project_index": 0,
                    "bullet_index": 1,
                    "suggested_bullet": (
                        "Implemented a polished user workflow."
                    ),
                    "safe_for_lineage_evaluation": True,
                },
            ],
        }
        evaluate.side_effect = [
            {
                "safe_to_accept": True,
                "fresh_score_comparison": {
                    "available": True,
                    "before_score": 13,
                    "after_score": 19,
                    "score_delta": 6,
                    "important_regressions": [],
                },
            },
            {
                "safe_to_accept": True,
                "fresh_score_comparison": {
                    "available": True,
                    "before_score": 19,
                    "after_score": 19,
                    "score_delta": 0,
                    "important_regressions": [],
                },
            },
        ]

        result = preview.build_jd_score_optimization_review(
            generation=self._generation(),
            baseline_report={"jd_profile": {}},
            model="openai/gpt-5.4-mini",
        )

        self.assertEqual(result["opportunity_count"], 1)
        self.assertEqual(
            result["opportunities"][0][
                "fresh_score_comparison"
            ]["score_delta"],
            6,
        )
        self.assertEqual(
            result["rejected_candidates"][0]["reason"],
            "no_positive_score_gain",
        )

    @patch.object(
        preview,
        "build_rephrase_batch_contexts",
        return_value=[],
    )
    def test_empty_contexts_make_no_model_call(
        self,
        _contexts,
    ):
        with patch.object(
            preview,
            "suggest_jd_specific_rephrases_batch",
        ) as suggest:
            result = preview.build_jd_score_optimization_review(
                generation=self._generation(),
                baseline_report={},
                model="ollama/qwen3:8b",
            )

        suggest.assert_not_called()
        self.assertEqual(result["opportunity_count"], 0)

    @patch.object(
        preview,
        "build_rephrase_batch_contexts",
    )
    @patch.object(
        preview,
        "suggest_jd_specific_rephrases_batch",
    )
    @patch.object(
        preview,
        "evaluate_rephrase_candidate",
    )
    def test_regression_is_never_exposed(
        self,
        evaluate,
        suggest,
        build_contexts,
    ):
        build_contexts.return_value = [self._contexts()[0]]
        suggest.return_value = {
            "suggestion_count": 1,
            "suggestions": [
                {
                    "project_index": 0,
                    "bullet_index": 0,
                    "suggested_bullet": (
                        "Built a PostgreSQL-backed backend service."
                    ),
                    "safe_for_lineage_evaluation": True,
                }
            ],
        }
        evaluate.return_value = {
            "safe_to_accept": True,
            "fresh_score_comparison": {
                "available": True,
                "before_score": 13,
                "after_score": 14,
                "score_delta": 1,
                "important_regressions": ["required coverage fell"],
            },
        }

        result = preview.build_jd_score_optimization_review(
            generation=self._generation(),
            baseline_report={},
        )

        self.assertEqual(result["opportunity_count"], 0)
        self.assertEqual(
            result["rejected_candidates"][0]["reason"],
            "important_regression",
        )


if __name__ == "__main__":
    unittest.main()

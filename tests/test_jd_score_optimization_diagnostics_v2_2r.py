from __future__ import annotations

import unittest
from unittest.mock import patch

import tailoring.jd_specific_rephrase_preview as preview


class JDScoreOptimizationDiagnosticsTests(unittest.TestCase):
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
                            "Added tests.",
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
            {
                "project_index": 0,
                "bullet_index": 2,
                "project_title": "Project One",
                "current_bullet": "Added tests.",
            },
        ]

    @patch.object(preview, "build_rephrase_batch_contexts")
    @patch.object(preview, "suggest_jd_specific_rephrases_batch")
    @patch.object(preview, "evaluate_rephrase_candidate")
    def test_diagnostics_distinguish_changed_and_unchanged(
        self,
        evaluate,
        suggest,
        build_contexts,
    ):
        build_contexts.return_value = self._contexts()
        suggest.return_value = {
            "suggestion_count": 3,
            "model_call_count": 2,
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
                    "suggested_bullet": "Implemented a user workflow.",
                    "safe_for_lineage_evaluation": True,
                },
                {
                    "project_index": 0,
                    "bullet_index": 2,
                    "suggested_bullet": "Added tests.",
                    "safe_for_lineage_evaluation": True,
                },
            ],
        }
        evaluate.return_value = {
            "safe_to_accept": True,
            "fresh_score_comparison": {
                "available": True,
                "before_score": 13,
                "after_score": 19,
                "score_delta": 6,
                "important_regressions": [],
            },
        }

        result = preview.build_jd_score_optimization_review(
            generation=self._generation(),
            baseline_report={},
            model="openai/gpt-5.6-luna",
        )

        diagnostics = result["diagnostics"]
        self.assertEqual(diagnostics["reviewed_bullet_count"], 3)
        self.assertEqual(diagnostics["changed_proposal_count"], 1)
        self.assertEqual(diagnostics["unchanged_or_no_change_count"], 2)
        self.assertEqual(diagnostics["positive_opportunity_count"], 1)
        self.assertEqual(diagnostics["rejected_changed_proposal_count"], 0)
        self.assertEqual(diagnostics["model_call_count"], 2)

    @patch.object(preview, "build_rephrase_batch_contexts")
    @patch.object(preview, "suggest_jd_specific_rephrases_batch")
    def test_zero_changed_proposals_are_visible_in_diagnostics(
        self,
        suggest,
        build_contexts,
    ):
        contexts = self._contexts()
        build_contexts.return_value = contexts
        suggest.return_value = {
            "suggestion_count": 3,
            "model_call_count": 1,
            "suggestions": [
                {
                    "project_index": 0,
                    "bullet_index": index,
                    "suggested_bullet": context["current_bullet"],
                    "safe_for_lineage_evaluation": True,
                }
                for index, context in enumerate(contexts)
            ],
        }

        result = preview.build_jd_score_optimization_review(
            generation=self._generation(),
            baseline_report={},
        )

        diagnostics = result["diagnostics"]
        self.assertEqual(diagnostics["changed_proposal_count"], 0)
        self.assertEqual(diagnostics["unchanged_or_no_change_count"], 3)
        self.assertEqual(result["opportunity_count"], 0)
        self.assertEqual(len(result["rejected_candidates"]), 0)


if __name__ == "__main__":
    unittest.main()

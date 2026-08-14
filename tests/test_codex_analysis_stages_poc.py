"""Offline tests for the staged Codex analysis evaluator."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from experimental.ai_backend_core import (
    get_active_ai_backend,
    set_runtime_ai_backend,
)
from experimental.analysis_stage_contracts import (
    AnalysisStageContractError,
    validate_bullets_result,
    validate_degree_result,
    validate_summary_result,
)
from scripts.evaluate_codex_analysis_stages import (
    STAGES,
    _run_once,
    _stage_call,
)


FIXTURE = {
    "resume_text": "RESUME",
    "jd_text": "JD",
    "degree_program": "IMGD",
    "actual_page_count": 1,
    "resume_profile": {
        "projects": [
            {
                "title": "Project",
                "date": "",
                "bullets": ["Built API."],
            }
        ],
        "experience": [],
    },
    "jd_profile": {
        "job_title": "Full Stack Developer",
    },
    "summary_report": {
        "overall_score": 80,
    },
    "expected_anchors": {},
}


class AnalysisStageContractTests(unittest.TestCase):
    def test_bullet_contract_requires_verbatim_source_set(self) -> None:
        result = {
            "bullets": [
                {
                    "source": "projects",
                    "parent_title": "Project",
                    "bullet_text": "Rewritten API bullet.",
                    "has_action_verb": True,
                    "has_specific_technology": True,
                    "has_result_or_scope": True,
                    "has_numeric_metric": False,
                    "grammar_or_tense_issue": "",
                    "level": "L2_BETTER",
                    "what_is_missing": "",
                }
            ],
            "bullet_quality_avg": 67,
        }
        with self.assertRaisesRegex(
            AnalysisStageContractError,
            "preserve every source bullet",
        ):
            validate_bullets_result(
                result,
                expected_bullets=[
                    "Built API."
                ],
            )

    def test_degree_contract_rejects_out_of_range_score(self) -> None:
        result = {
            "student_degree": "IMGD",
            "jd_title": "Full Stack Developer",
            "title_on_suggested_list": True,
            "matched_against": "IMGD",
            "fit_commentary": "Fits well.",
            "degree_alignment_score": 101,
        }
        with self.assertRaisesRegex(
            AnalysisStageContractError,
            "between 0 and 100",
        ):
            validate_degree_result(result)

    def test_summary_requires_exactly_three_markdown_bullets(self) -> None:
        self.assertEqual(
            validate_summary_result(
                "- One\n- Two\n- Three"
            ),
            "- One\n- Two\n- Three",
        )
        with self.assertRaisesRegex(
            AnalysisStageContractError,
            "exactly 3",
        ):
            validate_summary_result(
                "- One\n- Two"
            )


class AnalysisStageDispatchTests(unittest.TestCase):
    def setUp(self) -> None:
        set_runtime_ai_backend(
            "api",
            route="analysis",
        )

    def tearDown(self) -> None:
        set_runtime_ai_backend(
            "api",
            route="analysis",
        )

    def test_stage_catalog_has_no_all_option(self) -> None:
        self.assertNotIn(
            "all",
            STAGES,
        )
        self.assertEqual(
            set(STAGES),
            {
                "keyword",
                "bullets",
                "jargon",
                "structure",
                "degree",
                "summary",
            },
        )

    def test_keyword_dispatch_calls_only_keyword_function(self) -> None:
        with (
            patch(
                "scripts.evaluate_codex_analysis_stages.analyse_keyword_match",
                return_value={"keyword": True},
            ) as keyword,
            patch(
                "scripts.evaluate_codex_analysis_stages.analyse_bullets"
            ) as bullets,
            patch(
                "scripts.evaluate_codex_analysis_stages.analyse_jargon"
            ) as jargon,
            patch(
                "scripts.evaluate_codex_analysis_stages.analyse_structure"
            ) as structure,
            patch(
                "scripts.evaluate_codex_analysis_stages.analyse_degree_alignment"
            ) as degree,
            patch(
                "scripts.evaluate_codex_analysis_stages.summarise_overall"
            ) as summary,
        ):
            result = _stage_call(
                "keyword",
                FIXTURE,
            )

        self.assertEqual(
            result,
            {"keyword": True},
        )
        keyword.assert_called_once()
        bullets.assert_not_called()
        jargon.assert_not_called()
        structure.assert_not_called()
        degree.assert_not_called()
        summary.assert_not_called()

    def test_runner_switches_backend_and_restores_it(self) -> None:
        observed: list[str] = []

        def fake_call(
            stage,
            fixture,
        ):
            observed.append(
                get_active_ai_backend(
                    "analysis"
                )
            )
            return "- A\n- B\n- C"

        with (
            patch(
                "scripts.evaluate_codex_analysis_stages._stage_call",
                side_effect=fake_call,
            ),
            patch(
                "scripts.evaluate_codex_analysis_stages._validate_stage",
                side_effect=lambda stage, value, fixture: value,
            ),
            patch(
                "scripts.evaluate_codex_analysis_stages._anchor_checks",
                return_value={"passed": True},
            ),
            patch(
                "scripts.evaluate_codex_analysis_stages.get_last_codex_call_metadata",
                return_value={
                    "backend": "codex"
                },
            ),
        ):
            result = _run_once(
                stage="summary",
                backend="codex",
                fixture=FIXTURE,
            )

        self.assertTrue(result["ok"])
        self.assertEqual(
            observed,
            ["codex"],
        )
        self.assertEqual(
            get_active_ai_backend(
                "analysis"
            ),
            "api",
        )


if __name__ == "__main__":
    unittest.main()

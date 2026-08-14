"""Offline tests for Codex/API resume extraction evaluation."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from experimental.ai_backend_core import (
    get_active_ai_backend,
    set_runtime_ai_backend,
)
from experimental.resume_profile_contract import (
    ResumeProfileContractError,
    validate_resume_profile_contract,
)
from scripts.evaluate_codex_resume_extraction import (
    _repeat_backend,
    _run_backend_once,
    compare_backend_results,
    evaluate_expected_anchors,
)


VALID_PROFILE = {
    "name": "Alex Lim",
    "contact": {
        "email": "alex@example.com",
        "phone": "",
        "linkedin": "",
        "github": "",
        "portfolio": "",
    },
    "summary": "Software engineer.",
    "education": [
        {
            "school": "Example Institute",
            "degree": "BSc Computer Science",
            "graduation_date": "2026",
            "courses": ["Data Structures"],
        }
    ],
    "projects": [
        {
            "title": "QueryAI (React, Team of 4)",
            "date": "May 2025 - Jul 2025",
            "bullets": ["Built authentication workflows."],
        }
    ],
    "experience": [
        {
            "title": "Software Engineer Intern",
            "company": "Harbour Analytics Pte Ltd",
            "date": "May 2025 - Apr 2026",
            "bullets": ["Built Python data pipelines."],
        }
    ],
    "skills": {
        "languages": ["Python"],
        "frameworks": ["React"],
        "tools": ["Docker"],
        "concepts": ["REST API"],
        "platforms": ["Linux"],
    },
}


class ResumeProfileContractTests(unittest.TestCase):
    def test_accepts_exact_contract(self) -> None:
        self.assertEqual(
            validate_resume_profile_contract(
                VALID_PROFILE
            ),
            VALID_PROFILE,
        )

    def test_rejects_missing_nested_contact_field(self) -> None:
        candidate = {
            **VALID_PROFILE,
            "contact": {
                key: value
                for key, value in VALID_PROFILE[
                    "contact"
                ].items()
                if key != "phone"
            },
        }
        with self.assertRaisesRegex(
            ResumeProfileContractError,
            "missing fields: phone",
        ):
            validate_resume_profile_contract(candidate)

    def test_rejects_unexpected_nested_field(self) -> None:
        candidate = {
            **VALID_PROFILE,
            "skills": {
                **VALID_PROFILE["skills"],
                "certifications": [],
            },
        }
        with self.assertRaisesRegex(
            ResumeProfileContractError,
            "unexpected fields: certifications",
        ):
            validate_resume_profile_contract(candidate)

    def test_rejects_non_string_nested_list_item(self) -> None:
        candidate = {
            **VALID_PROFILE,
            "projects": [
                {
                    **VALID_PROFILE["projects"][0],
                    "bullets": ["Good", 3],
                }
            ],
        }
        with self.assertRaisesRegex(
            ResumeProfileContractError,
            r"bullets\[1\] must be a string",
        ):
            validate_resume_profile_contract(candidate)


class ResumeExtractionEvaluatorTests(unittest.TestCase):
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

    def test_anchor_checks_cover_identity_projects_company_and_skills(self) -> None:
        checks = evaluate_expected_anchors(
            VALID_PROFILE,
            {
                "name": "Alex Lim",
                "email": "alex@example.com",
                "project_titles": [
                    "QueryAI (React, Team of 4)"
                ],
                "experience_companies": [
                    "Harbour Analytics Pte Ltd"
                ],
                "skills": [
                    "Python",
                    "React",
                    "Docker",
                    "REST API",
                    "Linux",
                ],
            },
        )
        self.assertTrue(checks["passed"])
        self.assertEqual(
            checks["passed_count"],
            checks["total_count"],
        )

    def test_runner_switches_backend_then_restores_previous_backend(self) -> None:
        observed: list[str] = []

        def fake_extract(_text: str):
            observed.append(
                get_active_ai_backend("analysis")
            )
            return VALID_PROFILE

        set_runtime_ai_backend(
            "api",
            route="analysis",
        )

        with patch(
            "scripts.evaluate_codex_resume_extraction.extract_resume_profile",
            side_effect=fake_extract,
        ):
            result = _run_backend_once(
                "resume text",
                backend="codex",
                expected_anchors={},
            )

        self.assertTrue(result["ok"])
        self.assertEqual(observed, ["codex"])
        self.assertEqual(
            get_active_ai_backend("analysis"),
            "api",
        )

    def test_single_successful_run_does_not_claim_repeatability(self) -> None:
        with patch(
            "scripts.evaluate_codex_resume_extraction._run_backend_once",
            return_value={
                "ok": True,
                "profile": VALID_PROFILE,
                "schema_valid": True,
            },
        ):
            result = _repeat_backend(
                "resume text",
                backend="codex",
                repeat=1,
                expected_anchors={},
            )

        self.assertEqual(
            result["successful_run_count"],
            1,
        )
        self.assertIsNone(
            result["exact_output_deterministic"]
        )

    def test_comparison_marks_skipped_side_as_none(self) -> None:
        api = {
            "status": "not_run",
            "runs": [],
        }
        codex = {
            "status": "completed",
            "runs": [
                {
                    "ok": True,
                    "schema_valid": True,
                    "profile": VALID_PROFILE,
                    "anchor_checks": {
                        "passed": True
                    },
                }
            ],
        }

        comparison = compare_backend_results(
            api,
            codex,
        )

        self.assertIsNone(
            comparison["schema_validity"]["api"]
        )
        self.assertTrue(
            comparison["schema_validity"]["codex"]
        )
        self.assertIsNone(
            comparison["exact_profile_equal"]
        )


if __name__ == "__main__":
    unittest.main()

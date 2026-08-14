"""Offline contract tests for the isolated Codex JD extraction POC."""

from __future__ import annotations

import json
import sys
import types
import unittest
from unittest.mock import patch

from experimental.codex_jd_extraction import (
    CodexJDExtractionError,
    extract_job_description_with_codex_result,
    validate_jd_profile_contract,
)
from scripts.evaluate_codex_jd_extraction import (
    _not_run_backend_result,
    compare_profiles,
)


VALID_PROFILE = {
    "job_title": "Software Engineer",
    "company": "Example Corp",
    "location": "Singapore",
    "experience_level": "Junior",
    "required_skills": ["Python"],
    "preferred_skills": ["Docker"],
    "tools_technologies": ["Python", "Docker"],
    "responsibilities": ["Build APIs"],
    "soft_skills": ["Communication"],
    "buzzwords": ["REST APIs"],
    "deal_breakers": [],
}


class CodexJDExtractionContractTests(unittest.TestCase):
    def test_rejects_missing_or_unexpected_fields(self) -> None:
        missing = dict(VALID_PROFILE)
        del missing["company"]
        with self.assertRaisesRegex(CodexJDExtractionError, "missing fields: company"):
            validate_jd_profile_contract(missing)

        unexpected = {**VALID_PROFILE, "score": 99}
        with self.assertRaisesRegex(CodexJDExtractionError, "unexpected fields: score"):
            validate_jd_profile_contract(unexpected)

    def test_rejects_non_string_list_entries(self) -> None:
        invalid = {**VALID_PROFILE, "required_skills": ["Python", 3]}
        with self.assertRaisesRegex(CodexJDExtractionError, "list of strings"):
            validate_jd_profile_contract(invalid)

    def _sdk_module(self, response: str) -> types.ModuleType:
        state: dict[str, object] = {}

        class FakeThread:
            def run(self, prompt: str, **kwargs):
                state["prompt"] = prompt
                state["run_kwargs"] = kwargs
                return types.SimpleNamespace(final_response=response)

        class FakeCodex:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def thread_start(self, **kwargs):
                state["thread_kwargs"] = kwargs
                return FakeThread()

        module = types.ModuleType("openai_codex")
        module.Codex = FakeCodex
        module.Sandbox = types.SimpleNamespace(read_only="read-only")
        module.state = state
        return module

    def test_uses_sdk_with_read_only_sandbox(self) -> None:
        fake_sdk = self._sdk_module(json.dumps(VALID_PROFILE))
        with patch.dict(sys.modules, {"openai_codex": fake_sdk}):
            result = extract_job_description_with_codex_result("Python required.")

        self.assertEqual(result.profile, VALID_PROFILE)
        thread_kwargs = fake_sdk.state["thread_kwargs"]
        self.assertEqual(thread_kwargs["sandbox"], "read-only")
        self.assertTrue(thread_kwargs["ephemeral"])
        self.assertIn("codex-jd-extraction-", thread_kwargs["cwd"])
        self.assertEqual(fake_sdk.state["run_kwargs"], {"sandbox": "read-only"})
        self.assertIn("Python required.", fake_sdk.state["prompt"])
        self.assertIn("experience_level is for an explicitly stated seniority", fake_sdk.state["prompt"])
        self.assertEqual(result.metadata.model, "sdk-configured-default")

    def test_records_explicit_codex_model(self) -> None:
        fake_sdk = self._sdk_module(json.dumps(VALID_PROFILE))
        with patch.dict(sys.modules, {"openai_codex": fake_sdk}):
            result = extract_job_description_with_codex_result(
                "Python required.",
                model="example-model",
            )

        self.assertEqual(result.metadata.model, "example-model")
        self.assertEqual(fake_sdk.state["thread_kwargs"]["model"], "example-model")

    def test_fails_closed_on_invalid_json(self) -> None:
        fake_sdk = self._sdk_module("not json")
        with patch.dict(sys.modules, {"openai_codex": fake_sdk}):
            with self.assertRaisesRegex(CodexJDExtractionError, "invalid or missing JSON"):
                extract_job_description_with_codex_result("Python required.")

    def test_comparison_surfaces_requested_fields_and_missing_values(self) -> None:
        codex_profile = {**VALID_PROFILE, "company": "", "required_skills": []}
        comparison = compare_profiles(
            "Example Corp needs a Junior Software Engineer with Python. Docker preferred. Build APIs.",
            {"ok": True, "schema_valid": True, "profile": VALID_PROFILE},
            {"ok": True, "schema_valid": True, "profile": codex_profile},
        )
        self.assertIn("company", comparison["codex_missing_fields"])
        self.assertIn("required_skills", comparison["fields"])
        self.assertIn("tools_technologies", comparison["fields"])

    def test_skipped_api_reports_not_run_instead_of_failure(self) -> None:
        skipped_api = _not_run_backend_result()
        comparison = compare_profiles(
            "Python required.",
            {},
            {"ok": True, "schema_valid": True, "profile": VALID_PROFILE},
        )

        self.assertEqual(skipped_api["status"], "not_run")
        self.assertIsNone(skipped_api["deterministic_across_successful_runs"])
        self.assertIsNone(comparison["schema_validity"]["api"])
        self.assertTrue(comparison["schema_validity"]["codex"])
        self.assertIsNone(comparison["api_missing_fields"])
        self.assertIsNone(comparison["api_potentially_unsupported_fields"])
        self.assertIsNotNone(comparison["codex_missing_fields"])



if __name__ == "__main__":
    unittest.main()

'''Offline regressions for the optional Codex JD backend POC.'''

from __future__ import annotations

import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from experimental.jd_extraction_backend import (
    JD_EXTRACTION_BACKEND_API,
    JD_EXTRACTION_BACKEND_CODEX,
    extract_jd_profile_with_backend,
    get_configured_jd_extraction_backend,
    normalise_jd_extraction_backend,
)


class OptionalCodexJDBackendTests(unittest.TestCase):
    def test_normalise_backend_defaults_to_api_and_accepts_codex(self) -> None:
        self.assertEqual(normalise_jd_extraction_backend(""), JD_EXTRACTION_BACKEND_API)
        self.assertEqual(
            normalise_jd_extraction_backend("API (existing)"),
            JD_EXTRACTION_BACKEND_API,
        )
        self.assertEqual(
            normalise_jd_extraction_backend("Codex (Local / Experimental)"),
            JD_EXTRACTION_BACKEND_CODEX,
        )
        with self.assertRaisesRegex(ValueError, "Unsupported JD extraction backend"):
            normalise_jd_extraction_backend("automatic")

    def test_env_default_is_api(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                get_configured_jd_extraction_backend(),
                JD_EXTRACTION_BACKEND_API,
            )

    def test_api_dispatch_uses_existing_api_extractor_only(self) -> None:
        api_calls: list[str] = []

        fake_analyzer = types.ModuleType("analyzer")

        def fake_extract(jd_text: str):
            api_calls.append(jd_text)
            return {"source": "api"}

        fake_analyzer.extract_jd_profile = fake_extract

        with patch.dict(sys.modules, {"analyzer": fake_analyzer}):
            result = extract_jd_profile_with_backend(
                "same jd",
                backend="api",
            )

        self.assertEqual(result, {"source": "api"})
        self.assertEqual(api_calls, ["same jd"])

    def test_codex_dispatch_uses_codex_and_optional_model(self) -> None:
        calls: list[tuple[str, str | None]] = []

        fake_codex_adapter = types.ModuleType(
            "experimental.codex_jd_extraction"
        )

        def fake_extract(jd_text: str, *, model: str | None = None):
            calls.append((jd_text, model))
            return {"source": "codex"}

        fake_codex_adapter.extract_job_description_with_codex = fake_extract

        with (
            patch.dict(
                sys.modules,
                {"experimental.codex_jd_extraction": fake_codex_adapter},
            ),
            patch.dict(os.environ, {"CODEX_JD_MODEL": "test-model"}, clear=False),
        ):
            result = extract_jd_profile_with_backend(
                "same jd",
                backend="codex",
            )

        self.assertEqual(result, {"source": "codex"})
        self.assertEqual(calls, [("same jd", "test-model")])

    def test_codex_failure_does_not_fall_back_to_api(self) -> None:
        api_calls: list[str] = []

        fake_analyzer = types.ModuleType("analyzer")

        def fake_api(jd_text: str):
            api_calls.append(jd_text)
            return {"source": "api"}

        fake_analyzer.extract_jd_profile = fake_api

        fake_codex_adapter = types.ModuleType(
            "experimental.codex_jd_extraction"
        )

        def fail_codex(jd_text: str, *, model: str | None = None):
            raise RuntimeError("codex unavailable")

        fake_codex_adapter.extract_job_description_with_codex = fail_codex

        with patch.dict(
            sys.modules,
            {
                "analyzer": fake_analyzer,
                "experimental.codex_jd_extraction": fake_codex_adapter,
            },
        ):
            with self.assertRaisesRegex(RuntimeError, "codex unavailable"):
                extract_jd_profile_with_backend(
                    "same jd",
                    backend="codex",
                )

        self.assertEqual(api_calls, [])

    def test_app_wires_backend_into_execution_metadata_and_cache_key(self) -> None:
        app_text = Path("app.py").read_text(encoding="utf-8")

        self.assertIn(
            "extract_jd_profile_with_backend(",
            app_text,
        )
        self.assertIn(
            "analysis_backend=analysis_backend,",
            app_text,
        )
        self.assertIn(
            '"analysis_backend": analysis_backend',
            app_text,
        )
        self.assertIn(
            '"jd_extraction_backend": (',
            app_text,
        )
        self.assertIn(
            "Codex applies to Analyze Resume and Projects/Skills generation.",
            app_text,
        )
        self.assertNotIn(
            '"JD extraction backend"',
            app_text,
        )


if __name__ == "__main__":
    unittest.main()

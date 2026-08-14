"""Source-level regressions for the Analysis Backend UI POC."""

from __future__ import annotations

import unittest
from pathlib import Path


class AnalysisBackendUIRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app_text = Path("app.py").read_text(encoding="utf-8")

    def test_sidebar_exposes_analysis_backend_and_removes_jd_only_selector(self) -> None:
        self.assertIn('"Analysis backend"', self.app_text)
        self.assertIn("get_ai_backend_options()", self.app_text)
        self.assertNotIn('"JD extraction backend"', self.app_text)
        self.assertIn(
            "Codex applies to the Analyze Resume pipeline.",
            self.app_text,
        )

    def test_codex_analysis_is_scoped_and_restores_api_route(self) -> None:
        self.assertIn(
            "def run_resume_analysis_with_backend(",
            self.app_text,
        )
        self.assertIn(
            'set_runtime_ai_backend(\n        AI_BACKEND_API,\n        route="analysis",',
            self.app_text,
        )
        self.assertIn(
            'set_runtime_ai_backend(\n            previous_backend,\n            route="analysis",',
            self.app_text,
        )

    def test_backend_identity_is_in_cache_and_metadata(self) -> None:
        self.assertIn(
            '"analysis_backend": analysis_backend',
            self.app_text,
        )
        self.assertIn(
            '["analysis_backend"] = selected_backend',
            self.app_text,
        )
        self.assertIn(
            "model_id=_analysis_backend_model_id(analysis_backend),",
            self.app_text,
        )
        self.assertIn(
            "analysis_model=_analysis_backend_model_id(analysis_backend),",
            self.app_text,
        )

    def test_codex_analysis_does_not_record_fake_api_usage(self) -> None:
        self.assertIn(
            'if analysis_backend == AI_BACKEND_CODEX:',
            self.app_text,
        )
        self.assertIn(
            "Codex analysis completed; no provider API billing calls",
            self.app_text,
        )

    def test_chat_route_remains_separate(self) -> None:
        self.assertIn('route="chat",', self.app_text)
        self.assertIn('"Chatbot model"', self.app_text)


if __name__ == "__main__":
    unittest.main()

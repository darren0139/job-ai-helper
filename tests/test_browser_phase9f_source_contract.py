from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BrowserPhase9FSourceContractTests(unittest.TestCase):
    def test_phase9f_intake_allows_browser_source(self) -> None:
        text = (
            ROOT / "tailoring" / "phase9f_jd_intake.py"
        ).read_text(encoding="utf-8")

        self.assertIn(
            '{"pasted", "uploaded", "browser", "saved"}',
            text,
        )
        self.assertIn(
            '{"pasted", "uploaded", "browser"}',
            text,
        )

    def test_orchestrator_exposes_browser_capture_source(self) -> None:
        text = (
            ROOT / "tailoring" / "phase9f_orchestrator_ui.py"
        ).read_text(encoding="utf-8")

        self.assertIn('"Choose browser capture": "browser"', text)
        self.assertIn('elif source_type == "browser":', text)
        self.assertIn("browser_capture_to_phase9f_input", text)
        self.assertIn("list_browser_job_captures", text)

    def test_app_auto_starts_streamlit_managed_bridge(self) -> None:
        text = (ROOT / "app.py").read_text(encoding="utf-8")

        self.assertIn(
            "from browser_integration.streamlit_runtime import "
            "ensure_streamlit_browser_bridge",
            text,
        )
        self.assertIn(
            "_browser_bridge_resource = ensure_streamlit_browser_bridge()",
            text,
        )


if __name__ == "__main__":
    unittest.main()

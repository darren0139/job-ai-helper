from __future__ import annotations

import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


REPO_ROOT = Path(__file__).resolve().parents[1]
HARNESS = REPO_ROOT / "tests" / (
    "phase9f_tailoring_intensity_streamlit_harness.py"
)


def _contains(elements, text: str) -> bool:
    return any(text in str(item.value) for item in elements)


class Phase9FTailoringIntensityStreamlitTests(unittest.TestCase):
    def test_current_recommendation_renders_once_and_reuses_on_rerun(self):
        app = AppTest.from_file(str(HARNESS), default_timeout=20).run()
        self.assertEqual(app.exception, [])
        result = app.session_state["phase9f_c_test_result"]
        fingerprint = result["recommendation_fingerprint"]
        self.assertEqual(result["recommended_intensity"], "reuse")
        self.assertEqual(
            sum(
                "Recommended tailoring: Reuse" in str(item.value)
                for item in app.markdown
            ),
            1,
        )
        self.assertTrue(
            _contains(app.caption, "Preferred coverage: 20%")
        )
        app.run()
        self.assertEqual(app.exception, [])
        self.assertEqual(
            app.session_state["phase9f_c_test_result"][
                "recommendation_fingerprint"
            ],
            fingerprint,
        )

    def test_insufficient_scope_renders_fail_closed_without_category(self):
        app = AppTest.from_file(str(HARNESS), default_timeout=20).run()
        selector = next(
            item for item in app.selectbox if item.key == "phase9f_c_harness_scope"
        )
        selector.select("preferred_only").run()
        self.assertEqual(app.exception, [])
        result = app.session_state["phase9f_c_test_result"]
        self.assertEqual(result["status"], "fail_closed")
        self.assertIsNone(result["recommended_intensity"])
        self.assertEqual(
            result["failure_code"],
            "insufficient_important_requirement_scope",
        )
        self.assertTrue(_contains(app.error, "failed closed"))
        self.assertFalse(
            any("Recommended tailoring:" in str(item.value) for item in app.markdown)
        )

    def test_passive_render_and_diagnostics_are_zero_cost(self):
        app = AppTest.from_file(str(HARNESS), default_timeout=20).run()
        self.assertEqual(app.exception, [])
        for marker in (
            "MODEL_CALLS=0",
            "EMBEDDING_CALLS=0",
            "CHROMA_READS=0",
            "CHROMA_WRITES=0",
            "PERSISTENCE_WRITES=0",
        ):
            self.assertTrue(_contains(app.markdown, marker))
        labels = {item.label for item in app.get("download_button")}
        self.assertIn(
            "Download Phase 9F-C recommendation JSON",
            labels,
        )
        self.assertTrue(
            any(
                item.label
                == "Phase 9F-C deterministic policy and diagnostics"
                for item in app.expander
            )
        )


if __name__ == "__main__":
    unittest.main()


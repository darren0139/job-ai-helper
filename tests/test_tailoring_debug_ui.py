from __future__ import annotations

import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


REPO_ROOT = Path(__file__).resolve().parents[1]
HARNESS = REPO_ROOT / "tests" / "tailoring_debug_ui_harness.py"


class TailoringDebugUiTests(unittest.TestCase):
    @staticmethod
    def _button(app: AppTest, label: str):
        return next(button for button in app.button if button.label == label)

    def test_full_debug_bundle_and_fitting_json_are_explicitly_lazy(self) -> None:
        app = AppTest.from_file(str(HARNESS), default_timeout=30).run()

        self.assertEqual(app.exception, [])
        self.assertTrue(
            any(button.label == "Prepare Full Debug Bundle" for button in app.button)
        )
        self.assertTrue(
            any(box.label == "Show technical fitting debug" for box in app.checkbox)
        )
        self.assertTrue(
            any("DEBUG_BUNDLE_BUILDER_CALLS=0" in str(item.value) for item in app.markdown)
        )
        self.assertEqual(list(app.json), [])

        prepared = self._button(app, "Prepare Full Debug Bundle").click().run()
        self.assertEqual(prepared.exception, [])
        self.assertTrue(
            any("DEBUG_BUNDLE_BUILDER_CALLS=1" in str(item.value) for item in prepared.markdown)
        )
        self.assertTrue(
            any(
                button.label == "Download Full Debug Bundle JSON"
                for button in prepared.download_button
            )
        )
        self.assertTrue(
            any("Full Debug Bundle prepared" in str(item.value) for item in prepared.caption)
        )
        stored = prepared.session_state["tailor_resume_full_debug_bundle_77"]
        self.assertEqual(stored["bytes"], b'{"bundle":"prepared"}')
        self.assertEqual(stored["filename"], "prepared-debug-bundle.json")
        self.assertTrue(stored["prepared_at"])

        passive_rerun = prepared.run()
        self.assertEqual(passive_rerun.exception, [])
        self.assertTrue(
            any("DEBUG_BUNDLE_BUILDER_CALLS=1" in str(item.value) for item in passive_rerun.markdown)
        )
        self.assertTrue(
            any(button.label == "Refresh Full Debug Bundle" for button in passive_rerun.button)
        )

        refreshed = self._button(
            passive_rerun, "Refresh Full Debug Bundle"
        ).click().run()
        self.assertEqual(refreshed.exception, [])
        self.assertTrue(
            any("DEBUG_BUNDLE_BUILDER_CALLS=2" in str(item.value) for item in refreshed.markdown)
        )

        technical = next(
            box for box in refreshed.checkbox if box.label == "Show technical fitting debug"
        ).set_value(True).run()
        self.assertEqual(technical.exception, [])
        payloads = [str(item.value) for item in technical.json]
        self.assertTrue(any("attempt payload" in payload for payload in payloads))
        self.assertTrue(any("project payload" in payload for payload in payloads))
        self.assertTrue(any("skills payload" in payload for payload in payloads))


if __name__ == "__main__":
    unittest.main()

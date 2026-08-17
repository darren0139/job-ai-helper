from __future__ import annotations

import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


REPO_ROOT = Path(__file__).resolve().parents[1]
HARNESS = REPO_ROOT / "tests" / (
    "phase9f_application_confirmation_streamlit_harness.py"
)


def _contains(elements, text: str) -> bool:
    return any(text in str(item.value) for item in elements)


class Phase9FApplicationConfirmationStreamlitTests(unittest.TestCase):
    def test_passive_confirmation_is_read_only_and_shows_recommendations(self):
        app = AppTest.from_file(str(HARNESS), default_timeout=20).run()
        self.assertEqual(app.exception, [])
        self.assertTrue(_contains(app.subheader, "Create Application Session"))
        for marker in (
            "MODEL_CALLS=0",
            "EMBEDDING_CALLS=0",
            "CHROMA_READS=0",
            "CHROMA_WRITES=0",
            "PERSISTENCE_WRITES=0",
        ):
            self.assertTrue(_contains(app.markdown, marker))
        self.assertEqual(
            app.session_state["phase9f_d_harness_persistence_writes"], 0
        )
        confirm = next(
            item
            for item in app.button
            if item.label == "Confirm and create Application Session"
        )
        self.assertFalse(confirm.disabled)

    def test_nonwinner_requires_explicit_intensity_and_keeps_winner_recommendation(self):
        app = AppTest.from_file(str(HARNESS), default_timeout=20).run()
        ranking = app.session_state["phase9f_d_harness_ranking"]
        base = next(
            row
            for row in ranking["ranked_candidates"]
            if row["source_type"] == "base_resume"
        )
        source = next(
            item
            for item in app.selectbox
            if str(item.key).startswith("phase9f_d_source_")
        )
        source.select(base["normalized_source_fingerprint"]).run()
        self.assertEqual(app.exception, [])
        self.assertTrue(
            _contains(app.warning, "recommendation above remains tied")
        )
        intensity = next(
            item
            for item in app.selectbox
            if str(item.key).startswith("phase9f_d_intensity_")
        )
        self.assertIsNone(intensity.value)
        confirm = next(
            item
            for item in app.button
            if item.label == "Confirm and create Application Session"
        )
        self.assertTrue(confirm.disabled)

    def test_cross_family_source_has_warning_but_no_acknowledgement(self):
        app = AppTest.from_file(str(HARNESS), default_timeout=20).run()
        ranking = app.session_state["phase9f_d_harness_ranking"]
        cross = next(
            row
            for row in ranking["ranked_candidates"]
            if row["role_family_relationship"] == "cross_family"
        )
        source = next(
            item
            for item in app.selectbox
            if str(item.key).startswith("phase9f_d_source_")
        )
        source.select(cross["normalized_source_fingerprint"]).run()
        self.assertEqual(app.exception, [])
        self.assertTrue(_contains(app.warning, "different role family"))
        self.assertEqual(len(app.checkbox), 0)


if __name__ == "__main__":
    unittest.main()

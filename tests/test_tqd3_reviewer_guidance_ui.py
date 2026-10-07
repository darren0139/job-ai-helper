from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT / "taxonomy_discovery" / "review_ui.py"
).read_text(encoding="utf-8")


class TQD3ReviewerGuidanceUIContractTests(unittest.TestCase):
    def test_reviewer_guidance_is_present(self) -> None:
        for token in (
            "def _render_reviewer_guidance(",
            '"Reviewer Guidance · how to decide"',
            "What makes a good review",
            "Decision guide",
            "Defer is a valid conservative outcome",
        ):
            with self.subTest(token=token):
                self.assertIn(token, SOURCE)

    def test_all_human_routes_have_guidance(self) -> None:
        for label in (
            "Existing taxonomy near miss",
            "Research candidate",
            "Decomposition issue",
            "Scope review",
            "Defer",
        ):
            with self.subTest(label=label):
                self.assertIn(label, SOURCE)

    def test_python_assisted_review_how_to_is_present(self) -> None:
        self.assertIn(
            '"How to use deterministic Python-assisted review"',
            SOURCE,
        )
        self.assertIn("rule-based Python assistance", SOURCE)
        self.assertIn("Accept selected suggestions", SOURCE)

    def test_guidance_has_no_automatic_action(self) -> None:
        start = SOURCE.index("def _render_reviewer_guidance(")
        end = SOURCE.index(
            "\ndef _render_tqd3_classification_tab(",
            start,
        )
        helper = SOURCE[start:end]
        for forbidden in (
            "save_review(",
            "save_proposal_review(",
            "delete_review(",
            "ask_local_ai",
            "ask_text(",
            "st.button(",
            "st.form(",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, helper)

    def test_review_queue_calls_guidance(self) -> None:
        self.assertGreaterEqual(
            SOURCE.count("_render_reviewer_guidance("),
            2,
        )
        self.assertIn("classification_by_candidate_id", SOURCE)

    def test_decision_guide_uses_expandable_cards(self) -> None:
        start = SOURCE.index(
            'st.markdown("**Decision guide**")'
        )
        end = SOURCE.index(
            'st.caption(',
            start,
        )
        block = SOURCE[start:end]
        self.assertIn("for guide in _REVIEW_DECISION_GUIDE:", block)
        self.assertIn("with st.expander(", block)
        self.assertIn('st.markdown("**Choose when**")', block)
        self.assertIn('st.markdown("**Avoid when**")', block)
        self.assertIn('st.markdown("**Effect**")', block)
        self.assertIn("expanded=bool(", block)
        self.assertNotIn(
            "st.dataframe(\n            _REVIEW_DECISION_GUIDE",
            block,
        )


if __name__ == "__main__":
    unittest.main()

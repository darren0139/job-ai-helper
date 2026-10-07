from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT / "taxonomy_discovery" / "review_ui.py"
).read_text(encoding="utf-8")


class BroadMiningCandidateUIContractTests(unittest.TestCase):
    def test_candidate_report_is_rendered(self) -> None:
        self.assertIn(
            "build_broad_mining_candidate_report(",
            SOURCE,
        )
        self.assertIn(
            '"**Mining candidates**"',
            SOURCE,
        )
        self.assertIn(
            '"possible_new_technology"',
            SOURCE,
        )
        self.assertIn(
            '"already_known"',
            SOURCE,
        )

    def test_ui_explains_exact_match_contract(self) -> None:
        for token in (
            "exact canonical technology name",
            "registry label/alias",
            "It does not scan purpose or",
            "adoption prose, use fuzzy matching",
        ):
            with self.subTest(token=token):
                self.assertIn(token, SOURCE)

    def test_candidate_ui_has_no_promotion_action(self) -> None:
        start = SOURCE.index(
            'st.markdown("**Mining candidates**")'
        )
        end = SOURCE.index(
            'st.markdown("**Sources**")',
            start,
        )
        helper = SOURCE[start:end]
        for forbidden in (
            "save_proposal_review(",
            "build_registry_vnext_preview(",
            "technology_registry_v1.json",
            "automatic_promotion",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, helper)

    def test_sources_render_independently_of_candidates(self) -> None:
        start = SOURCE.index(
            "def _render_tqd3_broad_mining_tab()"
        )
        end = SOURCE.index(
            "\ndef render_capability_discovery_review()",
            start,
        )
        helper = SOURCE[start:end]
        self.assertIn("sources = [", helper)
        self.assertIn("if sources:", helper)
        self.assertIn('st.markdown("**Sources**")', helper)
        self.assertNotIn(
            "mentions = registry_mentions_for_result(result)",
            helper,
        )



if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT / "taxonomy_discovery" / "review_ui.py"
).read_text(encoding="utf-8")


class BroadMiningCandidateReviewUIContractTests(
    unittest.TestCase
):
    def test_queue_is_derived_from_saved_research(self) -> None:
        self.assertIn(
            "Mined candidate review queue",
            SOURCE,
        )
        self.assertIn(
            "load_latest_broad_mining_research_results(",
            SOURCE,
        )
        self.assertIn(
            "build_broad_mining_candidate_report(",
            SOURCE,
        )

    def test_only_reviewable_statuses_enter_queue(self) -> None:
        self.assertIn(
            '"possible_new_technology"',
            SOURCE,
        )
        self.assertIn(
            '"ambiguous_registry_match"',
            SOURCE,
        )
        self.assertIn(
            "Already-known candidates are excluded",
            SOURCE,
        )

    def test_review_decisions_are_human_only(self) -> None:
        for text in (
            "Research further",
            "Defer",
            "Reject",
            "Save candidate review",
        ):
            with self.subTest(text=text):
                self.assertIn(text, SOURCE)

    def test_review_does_not_call_tavily_or_create_proposal(
        self,
    ) -> None:
        start = SOURCE.index(
            'st.markdown("### Mined candidate review queue")'
        )
        end = SOURCE.index(
            'hide_researched = st.toggle(',
            start,
        )
        queue = SOURCE[start:end]
        self.assertNotIn(
            "research_selected_broad_mining_with_tavily(",
            queue,
        )
        self.assertNotIn(
            "save_proposal_review(",
            queue,
        )
        self.assertNotIn(
            "build_registry_vnext_preview(",
            queue,
        )
        self.assertIn(
            "does not call",
            queue,
        )
        self.assertIn(
            "Tavily",
            queue,
        )

    def test_source_authority_evidence_is_visible(self) -> None:
        self.assertIn(
            "Source authority evidence",
            SOURCE,
        )
        self.assertIn(
            "Source authority evidence",
            SOURCE,
        )
        self.assertIn(
            '"source_authority"',
            SOURCE,
        )

    def test_assisted_batch_review_requires_explicit_accept(
        self,
    ) -> None:
        self.assertIn(
            "Advanced assisted review · deterministic Python",
            SOURCE,
        )
        self.assertIn(
            "Accept selected deterministic suggestions",
            SOURCE,
        )
        self.assertIn(
            "never save ",
            SOURCE,
        )
        self.assertIn(
            "automatically",
            SOURCE,
        )
        self.assertIn(
            "Confidence measures routing-evidence strength",
            SOURCE,
        )
        self.assertIn(
            "taxonomy-covered technology",
            SOURCE,
        )
        self.assertIn(
            "never save automatically",
            SOURCE,
        )

    def test_export_ui_exposes_full_debug_bundle(
        self,
    ) -> None:
        self.assertIn(
            "Broad Mining export / debug",
            SOURCE,
        )
        self.assertIn(
            "Download full debug ZIP",
            SOURCE,
        )
        self.assertIn(
            "Candidate summary CSV",
            SOURCE,
        )
        self.assertIn(
            "Candidate reviews JSON",
            SOURCE,
        )

    def test_ollama_is_explicit_and_advisory(
        self,
    ) -> None:
        self.assertIn(
            "Ask Ollama for candidate second opinion",
            SOURCE,
        )
        self.assertIn(
            "does not save a review automatically",
            SOURCE,
        )


if __name__ == "__main__":
    unittest.main()

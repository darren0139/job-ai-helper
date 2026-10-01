from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT / "taxonomy_discovery" / "review_ui.py"
).read_text(encoding="utf-8")


class BroadMiningPersistenceUIContractTests(unittest.TestCase):
    def test_session_results_are_persisted_without_live_assignment_anchor(
        self,
    ) -> None:
        self.assertIn(
            "save_broad_mining_research_results(",
            SOURCE,
        )
        self.assertIn(
            "tqd3_broad_mining_persisted_signature_v1",
            SOURCE,
        )

    def test_saved_results_reload_without_tavily(self) -> None:
        self.assertIn(
            "load_latest_broad_mining_research_results(",
            SOURCE,
        )
        self.assertIn(
            "Saved broad-mining research",
            SOURCE,
        )
        self.assertIn(
            "No Tavily call is made when loading saved research",
            SOURCE,
        )

    def test_existing_sqlite_layer_is_reused(self) -> None:
        self.assertIn(
            "database.taxonomy_discovery_review_manager",
            SOURCE,
        )
    def test_dict_backed_broad_mining_state_is_supported(
        self,
    ) -> None:
        self.assertIn(
            "if isinstance(raw_persist_state, dict):",
            SOURCE,
        )
        self.assertIn(
            "raw_persist_state.values()",
            SOURCE,
        )
        self.assertIn(
            "reloaded_state = {",
            SOURCE,
        )
        self.assertIn(
            'row.get("target_id")',
            SOURCE,
        )

    def test_persisted_seed_status_and_default_hide(
        self,
    ) -> None:
        self.assertIn(
            'enriched["research_status"] = "Researched"',
            SOURCE,
        )
        self.assertIn(
            '"Hide already researched domains"',
            SOURCE,
        )
        self.assertIn(
            "value=True",
            SOURCE,
        )
        self.assertIn(
            '"saved_technologies"',
            SOURCE,
        )
        self.assertIn(
            '"saved_sources"',
            SOURCE,
        )
        self.assertIn(
            '"last_researched"',
            SOURCE,
        )

    def test_saved_results_auto_restore_without_manual_reload(
        self,
    ) -> None:
        self.assertIn(
            "auto_saved_results = (",
            SOURCE,
        )
        self.assertIn(
            "load_latest_broad_mining_research_results(",
            SOURCE,
        )
        self.assertIn(
            '"tqd3_broad_mining_results_v1"',
            SOURCE,
        )
        self.assertIn(
            "no Tavily/network/model call",
            SOURCE,
        )

    def test_reresearch_requires_explicit_visibility(
        self,
    ) -> None:
        self.assertIn(
            "Selecting one and running",
            SOURCE,
        )
        self.assertIn(
            "will make a new Tavily Research call",
            SOURCE,
        )

    def test_researched_domains_panel_and_coverage_metrics(
        self,
    ) -> None:
        self.assertIn(
            'st.markdown("### Researched domains")',
            SOURCE,
        )
        self.assertIn(
            '"Total domains"',
            SOURCE,
        )
        self.assertIn(
            '"Researched"',
            SOURCE,
        )
        self.assertIn(
            '"Remaining"',
            SOURCE,
        )
        self.assertIn(
            '"View saved result"',
            SOURCE,
        )
        self.assertIn(
            '"Research again"',
            SOURCE,
        )

    def test_view_saved_result_is_local_only(
        self,
    ) -> None:
        self.assertIn(
            '"Loaded the saved result locally. "',
            SOURCE,
        )
        self.assertIn(
            '"No Tavily call was made."',
            SOURCE,
        )

    def test_research_again_only_prepares_domain(
        self,
    ) -> None:
        self.assertIn(
            '"tqd3_reresearch_prepared_seed_v1"',
            SOURCE,
        )
        self.assertIn(
            '"No Tavily call has been made yet."',
            SOURCE,
        )
        self.assertIn(
            '"tqd3_broad_mining_search"',
            SOURCE,
        )

    def test_latest_persisted_artifact_wins_per_seed(
        self,
    ) -> None:
        self.assertIn(
            "not in persisted_seed_metadata",
            SOURCE,
        )
        self.assertIn(
            "newest-first",
            SOURCE,
        )

    def test_session_only_banner_is_removed(
        self,
    ) -> None:
        self.assertNotIn(
            "Results are session-only",
            SOURCE,
        )



if __name__ == "__main__":
    unittest.main()

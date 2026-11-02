from __future__ import annotations

from pathlib import Path
import unittest


class JobFinderV16LightweightUIContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = Path("job_discovery/ui.py").read_text(
            encoding="utf-8"
        )

    def test_admin_sections_are_explicitly_lazy(self) -> None:
        self.assertIn(
            "job_finder_load_source_management_v16",
            self.text,
        )
        self.assertIn(
            "job_finder_load_diagnostics_v16",
            self.text,
        )
        self.assertIn(
            "job_finder_load_hide_manager_v16",
            self.text,
        )

    def test_unresolved_requirements_are_not_presented_as_proven_gaps(self) -> None:
        self.assertNotIn('"Taxonomy gaps"', self.text)
        self.assertNotIn('"**Important taxonomy gaps**"', self.text)
        self.assertIn('"Unresolved capability requirements"', self.text)
        self.assertIn('"**Important unresolved capability requirements**"', self.text)
        self.assertIn('"proven capability gaps. Technology identity, relationships, "', self.text)
        # Retain the saved summary contract; presentation must not alter ranking.
        self.assertIn('match_summary.get("taxonomy_gap_count", 0)', self.text)

    def test_query_index_is_cached(self) -> None:
        self.assertIn(
            "def _cached_query_jobs_v16(",
            self.text,
        )
        self.assertIn(
            "query_jobs = _cached_query_jobs_v16(",
            self.text,
        )

    def test_every_page_result_has_an_expandable_card_and_selected_actions(self) -> None:
        self.assertIn('st.write("### Page results")', self.text)
        self.assertIn('for card_offset, card_job in enumerate(page_jobs, start=1):', self.text)
        self.assertIn('with st.container(border=True):', self.text)
        self.assertIn('Full job description · #', self.text)
        self.assertIn('job_finder_select_card_v17_', self.text)
        self.assertNotIn('"Open job details"', self.text)
        self.assertIn('job = page_job_by_id[selected_job_id]', self.text)

    def test_page_navigation_sets_busy_overlay_flag(self) -> None:
        self.assertIn(
            "_job_finder_navigation_busy_v16",
            self.text,
        )
        self.assertIn(
            "Loading the requested Job Finder page",
            self.text,
        )


if __name__ == "__main__":
    unittest.main()

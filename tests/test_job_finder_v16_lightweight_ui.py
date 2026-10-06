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

    def test_query_index_is_cached(self) -> None:
        self.assertIn(
            "def _cached_query_jobs_v16(",
            self.text,
        )
        self.assertIn(
            "query_jobs = _cached_query_jobs_v16(",
            self.text,
        )

    def test_full_job_cards_are_replaced_by_one_selected_detail(self) -> None:
        self.assertIn(
            'st.write("### Page results")',
            self.text,
        )
        self.assertIn(
            '"Open job details"',
            self.text,
        )
        self.assertNotIn(
            "for page_offset, job in enumerate(page_jobs, start=1):",
            self.text,
        )

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

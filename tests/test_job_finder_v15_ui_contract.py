from __future__ import annotations

from pathlib import Path
import unittest


class JobFinderV15UIContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = Path("job_discovery/ui.py").read_text(
            encoding="utf-8"
        )

    def test_atomic_filter_form_exists(self) -> None:
        self.assertIn(
            "job_finder_filters_form_v15",
            self.text,
        )
        self.assertIn(
            "Apply filters",
            self.text,
        )

    def test_atomic_view_form_exists(self) -> None:
        self.assertIn(
            "job_finder_view_form_v15",
            self.text,
        )
        self.assertIn(
            "Apply sort / page size",
            self.text,
        )

    def test_old_page_number_input_removed(self) -> None:
        self.assertNotIn(
            'key="job_finder_page_v14"',
            self.text,
        )
        self.assertIn(
            'key="job_finder_prev_page_v15"',
            self.text,
        )
        self.assertIn(
            'key="job_finder_next_page_v15"',
            self.text,
        )

    def test_batch_busy_overlay_exists(self) -> None:
        self.assertIn(
            "render_busy_overlay(",
            self.text,
        )
        self.assertIn(
            "job_finder_batch_form_v17",
            self.text,
        )


if __name__ == "__main__":
    unittest.main()

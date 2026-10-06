from __future__ import annotations

from pathlib import Path
import unittest


class JobFinderLocationDisplayContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = Path("job_discovery/ui.py").read_text(
            encoding="utf-8"
        )

    def test_page_results_use_display_location(self) -> None:
        self.assertIn(
            '"Location": display_job_location(result_job)',
            self.text,
        )

    def test_selected_job_metadata_uses_display_location(self) -> None:
        self.assertIn(
            "display_job_location(job)",
            self.text,
        )


if __name__ == "__main__":
    unittest.main()

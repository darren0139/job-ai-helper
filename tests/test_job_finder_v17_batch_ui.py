from __future__ import annotations

from pathlib import Path
import unittest


class JobFinderV17BatchUIContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = Path("job_discovery/ui.py").read_text(
            encoding="utf-8"
        )

    def test_coverage_is_visible(self) -> None:
        self.assertIn(
            "Candidate Match coverage",
            self.text,
        )
        self.assertIn(
            '"Not analyzed"',
            self.text,
        )
        self.assertIn(
            '"Not analyzable"',
            self.text,
        )

    def test_batch_only_targets_missing_or_stale(self) -> None:
        self.assertIn(
            "select_pending_batch_jobs(",
            self.text,
        )
        self.assertIn(
            "Analyze next missing/stale batch",
            self.text,
        )
        self.assertIn(
            "Analyze all missing/stale",
            self.text,
        )

    def test_internal_status_is_normalized_for_table(self) -> None:
        self.assertIn(
            "match_display_label(",
            self.text,
        )


if __name__ == "__main__":
    unittest.main()

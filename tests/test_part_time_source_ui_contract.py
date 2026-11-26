from __future__ import annotations

from pathlib import Path
import unittest


class PartTimeSourceUIContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = Path("job_discovery/ui.py").read_text(encoding="utf-8")

    def test_part_time_sources_are_visible(self) -> None:
        for source in ("fastjobs", "workjio", "staffie"):
            self.assertIn(f'"{source}"', self.text)

    def test_fastjobs_one_off_url_control_exists(self) -> None:
        self.assertIn("job_targets_fastjobs_v1", self.text)
        self.assertIn("FastJobs job/search URLs", self.text)


if __name__ == "__main__":
    unittest.main()

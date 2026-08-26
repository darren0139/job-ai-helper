from __future__ import annotations

import unittest
from pathlib import Path


class JDScoreOptimizationDiagnosticsUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path("app.py").read_text(encoding="utf-8")

    def test_diagnostic_metrics_are_rendered(self):
        for marker in (
            "Optimization diagnostic",
            "Bullets reviewed",
            "Changed proposals",
            "Positive improvements",
            "Unchanged / no-change",
            "Rejected changed proposals",
            "Optimization model calls",
        ):
            self.assertIn(marker, self.source)

    def test_zero_changed_explanation_is_rendered(self):
        self.assertIn(
            "meaningfully changed proposal",
            self.source,
        )


if __name__ == "__main__":
    unittest.main()

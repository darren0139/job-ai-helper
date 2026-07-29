from __future__ import annotations

import unittest

from analysis_stability.analysis_cache_mode import (
    ANALYSIS_CACHE_MODE_OPTIONS,
    FORCE_FRESH_ANALYSIS_MODE,
    REUSE_EXACT_ANALYSIS_MODE,
    resolve_analysis_cache_mode,
)


class AnalysisCacheModeTests(unittest.TestCase):
    def test_reuse_mode_enables_only_reuse(self):
        reuse, force_fresh = resolve_analysis_cache_mode(
            REUSE_EXACT_ANALYSIS_MODE
        )
        self.assertTrue(reuse)
        self.assertFalse(force_fresh)

    def test_force_fresh_mode_enables_only_force_fresh(self):
        reuse, force_fresh = resolve_analysis_cache_mode(
            FORCE_FRESH_ANALYSIS_MODE
        )
        self.assertFalse(reuse)
        self.assertTrue(force_fresh)

    def test_exactly_one_flag_is_true_for_every_mode(self):
        for mode in ANALYSIS_CACHE_MODE_OPTIONS:
            reuse, force_fresh = resolve_analysis_cache_mode(mode)
            self.assertNotEqual(reuse, force_fresh)

    def test_invalid_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            resolve_analysis_cache_mode("both")


if __name__ == "__main__":
    unittest.main()

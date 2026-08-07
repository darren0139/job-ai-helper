# Tests for Phase 9B promotion scope matching.

from __future__ import annotations

import unittest

from tailoring.phase9b_blueprint_ui import (
    _with_current_phase9e_scope,
)


class Phase9BPromotionScopeTests(unittest.TestCase):
    def test_normal_phase9e_generation_matches_current_decision(self) -> None:
        generation = {
            "generation_id": "gen-1",
            "phase9e_decision_fingerprint": "decision-current",
            "source_application_result_id": "",
        }
        scoped = _with_current_phase9e_scope(
            generation,
            "decision-current",
        )
        self.assertIsNot(scoped, generation)
        self.assertTrue(scoped["phase9e_scope_matches"])

    def test_different_phase9e_decision_fails_closed(self) -> None:
        generation = {
            "generation_id": "gen-1",
            "phase9e_decision_fingerprint": "decision-old",
            "source_application_result_id": "",
        }
        scoped = _with_current_phase9e_scope(
            generation,
            "decision-current",
        )
        self.assertFalse(scoped["phase9e_scope_matches"])

    def test_application_result_fork_still_uses_same_rule(self) -> None:
        generation = {
            "generation_id": "gen-2",
            "phase9e_decision_fingerprint": "decision-current",
            "source_application_result_id": "result-1",
        }
        scoped = _with_current_phase9e_scope(
            generation,
            "decision-current",
        )
        self.assertTrue(scoped["phase9e_scope_matches"])

    def test_legacy_generation_without_phase9e_identity_is_unchanged(self) -> None:
        generation = {
            "generation_id": "legacy",
            "phase9e_decision_fingerprint": "",
            "source_application_result_id": "",
        }
        scoped = _with_current_phase9e_scope(
            generation,
            "decision-current",
        )
        self.assertIs(scoped, generation)
        self.assertNotIn("phase9e_scope_matches", scoped)


if __name__ == "__main__":
    unittest.main()

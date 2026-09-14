from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from tailoring.phase8_auto_verification import (
    phase8_verification_is_current,
    phase8_verification_refresh_reason,
)
from tailoring.phase8_verification import (
    PHASE8_PREAPPROVAL_GATE_VERSION,
    PHASE8_VERIFICATION_VERSION,
)


class Phase8AutoVerificationTests(unittest.TestCase):
    def setUp(self):
        self.generation = {"generation_id": "g1", "fit_result": {"fit_one_page": True, "page_count": 1}}
        self.verification = {
            "phase8_version": PHASE8_VERIFICATION_VERSION,
            "approval_gate_version": PHASE8_PREAPPROVAL_GATE_VERSION,
            "verified_generation_snapshot_fingerprint": "snap1",
        }

    @patch(
        "tailoring.phase8_auto_verification.build_phase8_generation_snapshot_fingerprint",
        return_value="snap1",
    )
    def test_exact_snapshot_is_current(self, _mocked):
        self.assertTrue(phase8_verification_is_current(self.verification, self.generation))
        self.assertEqual(
            phase8_verification_refresh_reason(self.verification, self.generation),
            "current",
        )

    @patch(
        "tailoring.phase8_auto_verification.build_phase8_generation_snapshot_fingerprint",
        return_value="snap2",
    )
    def test_changed_snapshot_is_stale(self, _mocked):
        self.assertFalse(phase8_verification_is_current(self.verification, self.generation))
        self.assertEqual(
            phase8_verification_refresh_reason(self.verification, self.generation),
            "fitted_snapshot_changed",
        )

    def test_ui_contract_auto_verifies_without_auto_approve(self):
        ui = Path("tailoring/phase8_verification_ui.py").read_text(encoding="utf-8")
        app = Path("app.py").read_text(encoding="utf-8")
        self.assertIn("Automatically verifying the exact fitted résumé", ui)
        self.assertIn("Re-run Phase 8 verification", ui)
        self.assertNotIn("Verify Selected Tailored Résumé", ui)
        self.assertNotIn("approve_tailoring_generation(", ui)
        self.assertIn('["After fitting", "Before fitting"]', app)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from database import tailoring_version_manager as base
from database.tailoring_verification_manager import (
    get_latest_tailoring_verification,
    list_tailoring_verifications,
    save_tailoring_verification,
)


class TailoringVerificationManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db = base.DB_PATH
        base.DB_PATH = Path(self.temp_dir.name) / "applications.db"

    def tearDown(self):
        base.DB_PATH = self.old_db
        self.temp_dir.cleanup()

    def test_round_trip_and_exact_cache(self):
        result = {
            "phase8_version": "phase8-before-after-verification-v1",
            "verification_mode": "zero_cost_deterministic",
            "verification_fingerprint": "fingerprint-a",
            "generation_id": "generation-a",
            "verdict": "maintained",
        }
        first = save_tailoring_verification(
            application_id=1,
            generation_id="generation-a",
            result=result,
        )
        second = save_tailoring_verification(
            application_id=1,
            generation_id="generation-a",
            result=result,
        )
        self.assertEqual(first["cache_status"], "miss")
        self.assertEqual(second["cache_status"], "hit")
        self.assertEqual(
            first["verification_id"],
            second["verification_id"],
        )

        latest = get_latest_tailoring_verification(
            1,
            "generation-a",
        )
        self.assertEqual(latest["verdict"], "maintained")
        self.assertEqual(len(list_tailoring_verifications(1)), 1)


if __name__ == "__main__":
    unittest.main()

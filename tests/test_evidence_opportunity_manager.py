from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from database import tailoring_version_manager as base
from database.evidence_opportunity_manager import (
    delete_application_evidence_opportunities,
    get_latest_evidence_opportunity,
    save_evidence_opportunity,
)


class EvidenceOpportunityManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_path = base.DB_PATH
        base.DB_PATH = Path(self.temp.name) / "applications.db"

    def tearDown(self):
        base.DB_PATH = self.old_path
        self.temp.cleanup()

    def test_exact_fingerprint_is_reused(self):
        result = {
            "opportunity_fingerprint": "fingerprint-a",
            "phase9a_version": "phase9a-evidence-opportunity-v1",
            "baseline_score": 20,
            "potential_score": 60,
        }
        first = save_evidence_opportunity(
            application_id=1,
            result=result,
        )
        second = save_evidence_opportunity(
            application_id=1,
            result=result,
        )
        self.assertEqual(first["cache_status"], "miss")
        self.assertEqual(second["cache_status"], "hit")
        self.assertEqual(
            first["opportunity_id"],
            second["opportunity_id"],
        )
        self.assertEqual(
            get_latest_evidence_opportunity(1)["potential_score"],
            60,
        )

    def test_application_cleanup_removes_saved_opportunities(self):
        save_evidence_opportunity(
            application_id=2,
            result={
                "opportunity_fingerprint": "fingerprint-b",
                "potential_score": 50,
            },
        )
        self.assertEqual(
            delete_application_evidence_opportunities(2),
            1,
        )
        self.assertIsNone(
            get_latest_evidence_opportunity(2)
        )


if __name__ == "__main__":
    unittest.main()

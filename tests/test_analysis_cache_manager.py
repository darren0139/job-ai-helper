from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from database import db_manager
from database.analysis_cache_manager import (
    activate_analysis_snapshot,
    build_analysis_input_fingerprint,
    find_cached_analysis,
    list_analysis_snapshots,
    save_analysis_snapshot,
)


class AnalysisCacheManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_path = db_manager.DB_PATH
        db_manager.DB_PATH = Path(self.temp_dir.name) / "applications.db"

    def tearDown(self):
        db_manager.DB_PATH = self.old_path
        self.temp_dir.cleanup()

    def fingerprint(self, model: str = "model-a") -> str:
        return build_analysis_input_fingerprint(
            resume_text="Candidate\nPROJECTS\nQueryAI",
            jd_text="Backend engineer",
            degree="IMGD",
            actual_page_count=1,
            model_id=model,
            retrieval_config={"mode": "lexical"},
        )

    def test_same_raw_inputs_have_same_fingerprint(self):
        first = self.fingerprint()
        second = build_analysis_input_fingerprint(
            resume_text=" Candidate \r\nPROJECTS\r\nQueryAI ",
            jd_text=" Backend   engineer ",
            degree="IMGD",
            actual_page_count=1,
            model_id="model-a",
            retrieval_config={"mode": "lexical"},
        )
        self.assertEqual(first, second)

    def test_model_change_causes_cache_miss(self):
        self.assertNotEqual(
            self.fingerprint("model-a"),
            self.fingerprint("model-b"),
        )

    def test_snapshot_round_trip_and_activation(self):
        first = save_analysis_snapshot(
            application_id=1,
            input_fingerprint=self.fingerprint(),
            report={"overall_score": 10},
            analysis_model="model-a",
            resume_filename="resume.docx",
            analysis_id="analysis-a",
        )
        self.assertEqual(first["status"], "active")

        cached = find_cached_analysis(
            application_id=1,
            input_fingerprint=self.fingerprint(),
        )
        self.assertEqual(cached["analysis_id"], "analysis-a")
        self.assertEqual(cached["report"]["overall_score"], 10)

        save_analysis_snapshot(
            application_id=1,
            input_fingerprint=self.fingerprint("model-b"),
            report={"overall_score": 20},
            analysis_model="model-b",
            analysis_id="analysis-b",
        )
        versions = list_analysis_snapshots(1)
        self.assertEqual(len(versions), 2)

        activated = activate_analysis_snapshot(
            application_id=1,
            analysis_id="analysis-a",
        )
        self.assertEqual(activated["status"], "active")


if __name__ == "__main__":
    unittest.main()

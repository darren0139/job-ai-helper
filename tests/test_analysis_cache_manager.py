from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from database import db_manager
from database.analysis_cache_manager import (
    activate_analysis_snapshot,
    build_analysis_input_fingerprint,
    find_cached_analysis,
    find_reusable_analysis,
    list_analysis_snapshots,
    prepare_reusable_analysis_report,
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

    def test_exact_snapshot_is_reusable_across_applications(self):
        fingerprint = self.fingerprint()
        source = save_analysis_snapshot(
            application_id=1,
            input_fingerprint=fingerprint,
            report={
                "overall_score": 10,
                "api_cost_summary": {
                    "call_count": 9,
                    "estimated_total_cost_usd": 0.08,
                },
                "meta": {
                    "analysis_cache": {
                        "status": "miss",
                        "analysis_id": "analysis-a",
                    },
                    "jd_user_inputs": {
                        "preferred_requirement_overrides": [],
                    },
                },
            },
            analysis_model="model-a",
            resume_filename="resume.docx",
            analysis_id="analysis-a",
        )

        self.assertIsNone(
            find_cached_analysis(
                application_id=2,
                input_fingerprint=fingerprint,
            )
        )

        reusable = find_reusable_analysis(
            input_fingerprint=fingerprint,
            exclude_application_id=2,
        )
        self.assertIsNotNone(reusable)
        self.assertEqual(reusable["application_id"], 1)
        self.assertEqual(
            reusable["analysis_id"],
            source["analysis_id"],
        )

        prepared = prepare_reusable_analysis_report(reusable)
        self.assertEqual(prepared["overall_score"], 10)
        self.assertNotIn("api_cost_summary", prepared)
        self.assertNotIn(
            "analysis_cache",
            prepared.get("meta", {}),
        )
        self.assertIn(
            "jd_user_inputs",
            prepared.get("meta", {}),
        )

        # Preparing another application's report must never mutate the source.
        self.assertIn("api_cost_summary", source["report"])
        self.assertIn(
            "analysis_cache",
            source["report"].get("meta", {}),
        )

        # The reused report can be attached as a new application-owned snapshot.
        attached = save_analysis_snapshot(
            application_id=2,
            input_fingerprint=fingerprint,
            report=prepared,
            analysis_model="model-a",
            resume_filename="resume.docx",
            analysis_id="analysis-b",
        )
        self.assertEqual(attached["application_id"], 2)
        self.assertEqual(attached["analysis_id"], "analysis-b")
        self.assertEqual(
            find_cached_analysis(
                application_id=2,
                input_fingerprint=fingerprint,
            )["analysis_id"],
            "analysis-b",
        )
        self.assertEqual(
            find_cached_analysis(
                application_id=1,
                input_fingerprint=fingerprint,
            )["analysis_id"],
            "analysis-a",
        )

    def test_cross_application_reuse_requires_exact_fingerprint(self):
        save_analysis_snapshot(
            application_id=1,
            input_fingerprint=self.fingerprint("model-a"),
            report={"overall_score": 10},
            analysis_model="model-a",
            analysis_id="analysis-a",
        )

        self.assertIsNone(
            find_reusable_analysis(
                input_fingerprint=self.fingerprint("model-b"),
                exclude_application_id=2,
            )
        )
        self.assertIsNone(
            find_reusable_analysis(
                input_fingerprint=self.fingerprint("model-a"),
                exclude_application_id=1,
            )
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

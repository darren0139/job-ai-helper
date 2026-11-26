from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import database.browser_capture_manager as capture_manager
from job_discovery.browser_capture_ingest import ingest_browser_capture_to_job_finder


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "browser_extension"


def _payload(*, capture_mode: str = "automatic") -> dict:
    selected = (
        "Responsibilities\n"
        "Build and maintain software services for customers and internal teams.\n"
        "Requirements\n"
        "Experience with Python, APIs, SQL, testing, Git, and cloud deployment.\n"
        "Work with engineers to troubleshoot production issues and improve reliability.\n"
    )
    strategy = "user_selection_v1" if capture_mode == "user_selection" else "fastjobs_visible_job_v1"
    return {
        "schema_version": 2,
        "source": {
            "captured_at": "2026-11-19T08:00:00Z",
            "url": "https://www.fastjobs.sg/singapore-job-ad/2646942/example/",
            "host": "www.fastjobs.sg",
            "document_title": "Software Engineer",
            "source_type": "browser_extension",
            "site_adapter": "fastjobs",
            "site_adapter_version": "fastjobs-browser-adapter-v1",
            "capture_mode": capture_mode,
        },
        "capture": {
            "headings": ["Software Engineer", "Responsibilities", "Requirements"],
            "raw_visible_text": "Header\n" + selected + "\nFooter",
            "selected_text": selected if capture_mode == "user_selection" else "",
        },
        "job": {
            "job_title": "Software Engineer",
            "company": "Example Company",
            "location": "Singapore",
            "jd_text": selected,
            "employment_type": "Full-time",
            "cleaning_strategy": strategy,
            "cleaning_confidence": "user_confirmed" if capture_mode == "user_selection" else "high",
        },
    }


class BrowserManualSelectionCaptureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_capture_db = capture_manager.DB_PATH
        capture_manager.DB_PATH = Path(self.tempdir.name) / "applications.db"

    def tearDown(self) -> None:
        capture_manager.DB_PATH = self.original_capture_db
        self.tempdir.cleanup()

    def test_extension_exposes_manual_selection_action_and_provenance(self) -> None:
        content = (EXTENSION / "content.js").read_text(encoding="utf-8")
        popup_html = (EXTENSION / "popup.html").read_text(encoding="utf-8")
        popup_js = (EXTENSION / "popup.js").read_text(encoding="utf-8")

        self.assertIn('JOB_AI_EXTRACT_SELECTION', content)
        self.assertIn('capture_mode = "user_selection"', content)
        self.assertIn('user_selection_v1', content)
        self.assertIn('selected_text', content)
        self.assertIn('selectiveExtractButton', popup_html)
        self.assertIn('Extract highlighted JD text', popup_html)
        self.assertIn('JOB_AI_EXTRACT_SELECTION', popup_js)

    def test_manual_and_automatic_captures_same_url_coexist(self) -> None:
        automatic = capture_manager.save_browser_job_capture(_payload())
        manual = capture_manager.save_browser_job_capture(
            _payload(capture_mode="user_selection")
        )

        self.assertNotEqual(automatic["id"], manual["id"])
        pending = capture_manager.list_browser_job_captures(
            limit=10,
            status="pending",
        )
        self.assertEqual(len(pending), 2)
        self.assertEqual(
            {row["capture_mode"] for row in pending},
            {"automatic", "user_selection"},
        )

    def test_manual_capture_is_withheld_from_automatic_job_finder_index(self) -> None:
        payload = _payload(capture_mode="user_selection")
        with patch(
            "job_discovery.browser_capture_ingest.upsert_discovered_jobs"
        ) as upsert:
            result = ingest_browser_capture_to_job_finder(
                payload,
                {"id": 7, "capture_hash": "manual"},
            )

        self.assertEqual(result["status"], "withheld_user_selection")
        self.assertEqual(result["capture_mode"], "user_selection")
        upsert.assert_not_called()

    def test_explicit_promotion_indexes_exact_selected_text(self) -> None:
        payload = _payload(capture_mode="user_selection")
        expected = payload["job"]["jd_text"].strip()
        with patch(
            "job_discovery.browser_capture_ingest.upsert_discovered_jobs",
            return_value={
                "new": 1,
                "changed": 0,
                "unchanged": 0,
                "reactivated": 0,
            },
        ) as upsert:
            result = ingest_browser_capture_to_job_finder(
                payload,
                {"id": 8, "capture_hash": "manual"},
                allow_user_selection=True,
            )

        self.assertEqual(result["status"], "indexed")
        self.assertTrue(result["manual_selection_promoted"])
        indexed_job = upsert.call_args.args[0][0]
        self.assertEqual(indexed_job.description, expected)
        self.assertEqual(
            indexed_job.raw_payload["capture_mode"],
            "user_selection",
        )
        self.assertTrue(indexed_job.raw_payload["manual_selection_promoted"])

    def test_automatic_capture_still_indexes_normally(self) -> None:
        payload = _payload()
        with patch(
            "job_discovery.browser_capture_ingest.upsert_discovered_jobs",
            return_value={
                "new": 1,
                "changed": 0,
                "unchanged": 0,
                "reactivated": 0,
            },
        ) as upsert:
            result = ingest_browser_capture_to_job_finder(
                payload,
                {"id": 9, "capture_hash": "auto"},
            )

        self.assertEqual(result["status"], "indexed")
        self.assertEqual(result["capture_mode"], "automatic")
        upsert.assert_called_once()

    def test_queue_ui_requires_explicit_manual_promotion(self) -> None:
        ui = (ROOT / "tailoring" / "browser_capture_ui.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("Manual selection", ui)
        self.assertIn("Promote selection to Job Finder", ui)
        self.assertIn("allow_user_selection=True", ui)
        self.assertIn("withheld from automatic Job Finder indexing", ui)

    def test_extension_version_is_bumped_for_manual_selection_feature(self) -> None:
        chrome = json.loads(
            (EXTENSION / "manifest.json").read_text(encoding="utf-8")
        )
        firefox = json.loads(
            (EXTENSION / "manifest.firefox.json").read_text(encoding="utf-8")
        )
        self.assertEqual(chrome["version"], "0.4.6.9")
        self.assertEqual(firefox["version"], "0.4.6.9")


if __name__ == "__main__":
    unittest.main()

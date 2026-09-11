from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import database.browser_capture_manager as manager


def _payload() -> dict:
    return {
        "schema_version": 2,
        "source": {
            "captured_at": "2026-09-09T08:20:30.630Z",
            "url": "https://jobs.careers.gov.sg/jobs/hrp/example",
            "host": "jobs.careers.gov.sg",
            "document_title": "Example Role | Careers@Gov",
            "source_type": "browser_extension",
            "site_adapter": "careers_gov",
        },
        "capture": {
            "headings": ["Example Role", "What the role is"],
            "raw_visible_text": "Header\nWhat the role is\nClean JD\nFooter",
        },
        "job": {
            "job_title": "Example Role",
            "company": "Example Agency",
            "location": "",
            "jd_text": "What the role is\nClean JD",
            "posting_notes": [
                "All new hires are appointed on a two-year contract."
            ],
            "discarded_tracking_tags": ["#LI-HL1"],
            "cleaning_strategy": "careers_gov_sections_v2",
            "cleaning_confidence": "high",
        },
    }


class BrowserCaptureManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_db_path = manager.DB_PATH
        manager.DB_PATH = Path(self.tempdir.name) / "applications.db"

    def tearDown(self) -> None:
        manager.DB_PATH = self.original_db_path
        self.tempdir.cleanup()

    def test_save_and_list_pending_capture(self) -> None:
        saved = manager.save_browser_job_capture(_payload())

        self.assertEqual(saved["status"], "pending")
        self.assertEqual(saved["job_title"], "Example Role")
        self.assertEqual(saved["company"], "Example Agency")
        self.assertEqual(
            saved["jd_text"],
            "What the role is\nClean JD",
        )

        rows = manager.list_browser_job_captures(limit=10)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], saved["id"])

    def test_save_persists_excluded_notes_and_tracking_tags(self) -> None:
        saved = manager.save_browser_job_capture(_payload())

        self.assertIn("two-year contract", saved["posting_notes_json"])
        self.assertIn("#LI-HL1", saved["discarded_tracking_tags_json"])

    def test_new_cleaning_for_same_url_supersedes_old_pending_capture(self) -> None:
        first = manager.save_browser_job_capture(_payload())

        changed = _payload()
        changed["job"]["jd_text"] = (
            "What the role is\nClean JD after cleaner update"
        )
        second = manager.save_browser_job_capture(changed)

        self.assertNotEqual(first["id"], second["id"])

        pending = manager.list_browser_job_captures(
            limit=10,
            status="pending",
        )
        self.assertEqual([row["id"] for row in pending], [second["id"]])

        all_rows = manager.list_browser_job_captures(limit=10)
        statuses = {row["id"]: row["status"] for row in all_rows}
        self.assertEqual(statuses[first["id"]], "superseded")
        self.assertEqual(statuses[second["id"]], "pending")

    def test_exact_capture_is_deduplicated(self) -> None:
        first = manager.save_browser_job_capture(_payload())
        second = manager.save_browser_job_capture(_payload())

        self.assertEqual(first["id"], second["id"])
        self.assertEqual(len(manager.list_browser_job_captures(limit=10)), 1)

    def test_capture_requires_clean_jd_text(self) -> None:
        payload = _payload()
        payload["job"]["jd_text"] = ""

        with self.assertRaisesRegex(ValueError, "job.jd_text"):
            manager.save_browser_job_capture(payload)

    def test_capture_requires_http_source_url(self) -> None:
        payload = _payload()
        payload["source"]["url"] = "file:///tmp/job.html"

        with self.assertRaisesRegex(ValueError, "HTTP"):
            manager.save_browser_job_capture(payload)


if __name__ == "__main__":
    unittest.main()

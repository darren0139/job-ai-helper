from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import database.browser_capture_manager as manager


def _payload(url: str, jd_text: str = "Role\nBuild reliable software.") -> dict:
    return {
        "schema_version": 2,
        "source": {
            "captured_at": "2026-09-15T10:00:00.000Z",
            "url": url,
            "host": "example.com",
            "document_title": "Software Engineer",
            "source_type": "browser_extension",
            "site_adapter": "generic",
        },
        "capture": {
            "headings": ["Software Engineer"],
            "raw_visible_text": jd_text,
        },
        "job": {
            "job_title": "Software Engineer",
            "company": "Example Company",
            "location": "Singapore",
            "jd_text": jd_text,
            "posting_notes": [],
            "discarded_tracking_tags": [],
            "cleaning_strategy": "generic_visible_main_text",
            "cleaning_confidence": "medium",
        },
    }


class BrowserCaptureUrlCanonicalizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_db_path = manager.DB_PATH
        manager.DB_PATH = Path(self.tempdir.name) / "applications.db"

    def tearDown(self) -> None:
        manager.DB_PATH = self.original_db_path
        self.tempdir.cleanup()

    def test_removes_utm_and_fragment(self) -> None:
        canonical = manager.canonicalize_browser_source_url(
            "https://EXAMPLE.com/jobs/123?"
            "utm_source=chatgpt.com&utm_medium=referral#details"
        )
        self.assertEqual(canonical, "https://example.com/jobs/123")

    def test_removes_greenhouse_and_linkedin_tracking_params(self) -> None:
        canonical = manager.canonicalize_browser_source_url(
            "https://example.com/jobs/123?"
            "gh_src=abc&trackingId=xyz&refId=hello&keep=yes"
        )
        self.assertEqual(
            canonical,
            "https://example.com/jobs/123?keep=yes",
        )

    def test_linkedin_direct_job_uses_numeric_identity_across_hosts(
        self,
    ) -> None:
        urls = [
            (
                "https://www.linkedin.com/jobs/view/"
                "software-engineer-at-example-4460000000/"
            ),
            (
                "https://sg.linkedin.com/jobs/view/"
                "software-engineer-at-example-4460000000"
                "?utm_source=chatgpt.com"
            ),
            "https://linkedin.com/jobs/view/4460000000/",
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(
                    manager.canonicalize_browser_source_url(url),
                    "https://www.linkedin.com/jobs/view/4460000000",
                )

    def test_linkedin_split_pane_uses_same_numeric_identity(self) -> None:
        canonical = manager.canonicalize_browser_source_url(
            "https://www.linkedin.com/jobs/search/?"
            "currentJobId=4460000000&keywords=software"
            "&utm_source=chatgpt.com"
        )
        self.assertEqual(
            canonical,
            "https://www.linkedin.com/jobs/view/4460000000",
        )

    def test_linkedin_search_without_selected_job_remains_distinct(self) -> None:
        canonical = manager.canonicalize_browser_source_url(
            "https://www.linkedin.com/jobs/search/?"
            "keywords=software&utm_source=chatgpt.com"
        )
        self.assertEqual(
            canonical,
            "https://www.linkedin.com/jobs/search/?keywords=software",
        )

    def test_linkedin_regional_variants_reuse_same_capture(self) -> None:
        first = manager.save_browser_job_capture(
            _payload(
                "https://sg.linkedin.com/jobs/view/"
                "software-engineer-at-example-4460000000"
            )
        )
        second = manager.save_browser_job_capture(
            _payload(
                "https://www.linkedin.com/jobs/view/"
                "software-engineer-at-example-4460000000/"
                "?utm_source=chatgpt.com"
            )
        )

        self.assertEqual(first["id"], second["id"])
        self.assertEqual(
            second["canonical_source_url"],
            "https://www.linkedin.com/jobs/view/4460000000",
        )
        pending = manager.list_browser_job_captures(
            limit=10,
            status="pending",
        )
        self.assertEqual(len(pending), 1)

    def test_schema_backfills_linkedin_regional_identity(self) -> None:
        manager.init_browser_capture_schema()
        connection = manager._connect()
        try:
            now = "2026-09-17T10:00:00"
            rows = [
                (
                    "old-www",
                    (
                        "https://www.linkedin.com/jobs/view/"
                        "software-engineer-at-example-4460000000/"
                    ),
                    (
                        "https://www.linkedin.com/jobs/view/"
                        "software-engineer-at-example-4460000000/"
                    ),
                ),
                (
                    "old-sg",
                    (
                        "https://sg.linkedin.com/jobs/view/"
                        "software-engineer-at-example-4460000000"
                    ),
                    (
                        "https://sg.linkedin.com/jobs/view/"
                        "software-engineer-at-example-4460000000"
                    ),
                ),
            ]
            connection.executemany(
                """
                INSERT INTO browser_job_captures (
                    capture_hash,
                    status,
                    source_url,
                    canonical_source_url,
                    jd_text,
                    first_received_at,
                    last_received_at,
                    payload_json
                )
                VALUES (?, 'cleared', ?, ?, 'JD', ?, ?, '{}')
                """,
                [
                    (
                        capture_hash,
                        source_url,
                        canonical_url,
                        now,
                        now,
                    )
                    for capture_hash, source_url, canonical_url in rows
                ],
            )
            connection.commit()
        finally:
            connection.close()

        manager.init_browser_capture_schema()
        all_rows = manager.list_browser_job_captures(limit=10)
        self.assertEqual(len(all_rows), 2)
        self.assertEqual(
            {
                row["canonical_source_url"]
                for row in all_rows
            },
            {"https://www.linkedin.com/jobs/view/4460000000"},
        )

    def test_tracking_variant_of_exact_capture_reuses_row(self) -> None:
        first = manager.save_browser_job_capture(
            _payload("https://example.com/jobs/123")
        )
        second = manager.save_browser_job_capture(
            _payload(
                "https://example.com/jobs/123?"
                "utm_source=chatgpt.com"
            )
        )

        self.assertEqual(first["id"], second["id"])
        pending = manager.list_browser_job_captures(
            limit=10,
            status="pending",
        )
        self.assertEqual(len(pending), 1)

    def test_changed_cleaner_supersedes_tracking_variant(self) -> None:
        old = manager.save_browser_job_capture(
            _payload(
                "https://example.com/jobs/123?"
                "utm_source=chatgpt.com",
                jd_text="Header\nOld noisy JD\nFooter",
            )
        )
        new = manager.save_browser_job_capture(
            _payload(
                "https://example.com/jobs/123",
                jd_text="Clean JD",
            )
        )

        self.assertNotEqual(old["id"], new["id"])

        pending = manager.list_browser_job_captures(
            limit=10,
            status="pending",
        )
        self.assertEqual([row["id"] for row in pending], [new["id"]])

        all_rows = manager.list_browser_job_captures(limit=10)
        statuses = {row["id"]: row["status"] for row in all_rows}
        self.assertEqual(statuses[old["id"]], "superseded")
        self.assertEqual(statuses[new["id"]], "pending")

    def test_schema_backfills_existing_canonical_url(self) -> None:
        saved = manager.save_browser_job_capture(
            _payload(
                "https://example.com/jobs/123?"
                "utm_source=chatgpt.com"
            )
        )
        row = manager.get_browser_job_capture(saved["id"])
        self.assertEqual(
            row["canonical_source_url"],
            "https://example.com/jobs/123",
        )


if __name__ == "__main__":
    unittest.main()

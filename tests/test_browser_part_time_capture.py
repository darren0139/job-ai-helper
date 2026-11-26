from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from job_discovery.browser_capture_ingest import (
    ingest_browser_capture_to_job_finder,
    normalized_browser_discovery_job,
)


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "browser_extension"


def _payload(*, adapter: str, url: str) -> dict:
    return {
        "schema_version": 2,
        "source": {
            "captured_at": "2026-11-17T09:00:00Z",
            "url": url,
            "host": url.split("/")[2],
            "document_title": "Part-Time Event Crew",
            "source_type": "browser_extension",
            "site_adapter": adapter,
            "site_adapter_version": f"{adapter}-browser-adapter-v1",
        },
        "capture": {
            "headings": ["Part-Time Event Crew"],
            "raw_visible_text": "Part time\n" + ("Job details " * 80),
        },
        "job": {
            "job_title": "Part-Time Event Crew",
            "company": "Example Company",
            "location": "Singapore",
            "jd_text": "Support customers and operations. " * 12,
            "employment_type": "Part-time",
            "cleaning_strategy": f"{adapter}_visible_job_v1",
            "cleaning_confidence": "high",
        },
    }


class BrowserPartTimeCaptureTests(unittest.TestCase):
    def test_fastjobs_projects_to_existing_normalized_job(self) -> None:
        payload = _payload(
            adapter="fastjobs",
            url=(
                "https://www.fastjobs.sg/singapore-job-ad/"
                "2646942/concert-staff-event/?utm_source=test"
            ),
        )
        job = normalized_browser_discovery_job(
            payload, {"id": 9, "capture_hash": "abc"}
        )
        self.assertIsNotNone(job)
        self.assertEqual(job.source, "fastjobs")
        self.assertEqual(job.source_job_id, "2646942")
        self.assertEqual(job.source_platform, "browser_extension")
        self.assertNotIn("utm_source", job.source_url)
        self.assertEqual(
            job.raw_payload["provenance"],
            "browser_extension_capture",
        )

    def test_workjio_uses_job_slug_identity(self) -> None:
        payload = _payload(
            adapter="workjio",
            url="https://www.workjio.com/jobs/part-time-retail-assistant-abc123",
        )
        job = normalized_browser_discovery_job(
            payload, {"id": 10, "capture_hash": "def"}
        )
        self.assertIsNotNone(job)
        self.assertEqual(
            job.source_job_id,
            "part-time-retail-assistant-abc123",
        )

    def test_wrong_host_is_not_promoted(self) -> None:
        payload = _payload(
            adapter="fastjobs",
            url="https://example.com/singapore-job-ad/2646942/fake/",
        )
        self.assertIsNone(
            normalized_browser_discovery_job(
                payload, {"id": 11, "capture_hash": "ghi"}
            )
        )

    def test_other_adapters_remain_inbox_only(self) -> None:
        payload = _payload(
            adapter="linkedin",
            url="https://www.linkedin.com/jobs/view/123456789",
        )
        with patch(
            "job_discovery.browser_capture_ingest.upsert_discovered_jobs"
        ) as upsert:
            result = ingest_browser_capture_to_job_finder(
                payload, {"id": 12, "capture_hash": "jkl"}
            )
        self.assertEqual(result["status"], "not_applicable")
        upsert.assert_not_called()

    def test_supported_capture_uses_existing_upsert(self) -> None:
        payload = _payload(
            adapter="fastjobs",
            url=(
                "https://www.fastjobs.sg/singapore-job-ad/"
                "2646942/concert-staff-event/"
            ),
        )
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
                payload, {"id": 13, "capture_hash": "mno"}
            )
        self.assertEqual(result["status"], "indexed")
        self.assertEqual(result["source_job_id"], "2646942")
        self.assertEqual(
            upsert.call_args.kwargs["source_scope"],
            "browser:fastjobs",
        )

    def test_extension_injects_part_time_adapters(self) -> None:
        popup = (EXTENSION / "popup.js").read_text(encoding="utf-8")
        for filename in (
            '"adapters/fastjobs.js"',
            '"adapters/workjio.js"',
        ):
            self.assertIn(filename, popup)
            self.assertLess(popup.index(filename), popup.index('"content.js"'))

    def test_adapters_are_capture_only_and_domain_scoped(self) -> None:
        fastjobs = (
            EXTENSION / "adapters" / "fastjobs.js"
        ).read_text(encoding="utf-8")
        workjio = (
            EXTENSION / "adapters" / "workjio.js"
        ).read_text(encoding="utf-8")

        self.assertIn('id: "fastjobs"', fastjobs)
        self.assertIn("fastjobs.sg", fastjobs)
        self.assertIn("singapore-job-ad", fastjobs)
        self.assertIn("captureOnly: true", fastjobs)

        self.assertIn('id: "workjio"', workjio)
        self.assertIn("workjio.com", workjio)
        self.assertIn(r"^\/jobs\/[^/]+\/?$", workjio)
        self.assertIn("captureOnly: true", workjio)

    def test_bridge_indexes_after_capture_save(self) -> None:
        bridge = (
            ROOT / "browser_integration" / "bridge_server.py"
        ).read_text(encoding="utf-8")
        save_pos = bridge.index("saved = save_browser_job_capture(payload)")
        ingest_pos = bridge.index(
            "job_finder_index = ingest_browser_capture_to_job_finder("
        )
        self.assertLess(save_pos, ingest_pos)
        self.assertIn('"job_finder_index": job_finder_index', bridge)

    def test_direct_refresh_ui_excludes_blocked_sources(self) -> None:
        ui = (ROOT / "job_discovery" / "ui.py").read_text(encoding="utf-8")
        self.assertIn("DIRECT_REFRESH_EXCLUDED_SOURCES", ui)
        self.assertIn('"fastjobs"', ui)
        self.assertIn('"workjio"', ui)
        self.assertIn("browser extension", ui.lower())


if __name__ == "__main__":
    unittest.main()

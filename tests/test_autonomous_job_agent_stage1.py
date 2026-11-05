"""Stage 1 tests: fail closed without requiring a browser or network."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from job_agent.browser_stage1 import Stage1Error, _ensure_extension_files, safe_summary, validate_target
from job_agent.stage1_fixture import FIXTURE_HTML, start_fixture


class Stage1URLTests(unittest.TestCase):
    def test_local_fixture_requires_loopback(self):
        self.assertEqual("127.0.0.1", validate_target("http://127.0.0.1:1234/jobs/demo", fixture=True))
        for url in ("http://localhost:1234/", "http://example.com:1234/", "https://127.0.0.1:1234/"):
            with self.subTest(url=url), self.assertRaises(Stage1Error):
                validate_target(url, fixture=True)

    def test_live_requires_https_exact_host(self):
        self.assertEqual("boards.greenhouse.io", validate_target(
            "https://boards.greenhouse.io/demo/jobs/123", allowed_host="boards.greenhouse.io"))
        for url, allow in (
            ("http://boards.greenhouse.io/demo", "boards.greenhouse.io"),
            ("https://boards.greenhouse.io.evil.test/demo", "boards.greenhouse.io"),
            ("https://boards.greenhouse.io/demo", "greenhouse.io"),
            ("https://user:password@boards.greenhouse.io/demo", "boards.greenhouse.io"),
            ("https://boards.greenhouse.io/demo#fragment", "boards.greenhouse.io"),
            ("https://boards.greenhouse.io/demo", ""),
            ("file:///etc/passwd", ""),
        ):
            with self.subTest(url=url), self.assertRaises(Stage1Error):
                validate_target(url, allowed_host=allow)

    def test_fixture_server_serves_job_only(self):
        import urllib.request
        server, thread, url = start_fixture()
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                page = response.read().decode("utf-8")
                self.assertEqual(200, response.status)
            self.assertIn("Platform Engineer", page)
            self.assertIn('type="hidden"', page)
            self.assertIn('type="submit"', page)
            self.assertEqual(page, FIXTURE_HTML)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


class Stage1ExtensionContracts(unittest.TestCase):
    def test_extension_preserves_host_permissions_and_is_read_only(self):
        root = Path(__file__).resolve().parents[1] / "browser_extension"
        _ensure_extension_files(root)
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual({"https://*/*", "http://*/*"}, set(manifest["optional_host_permissions"]))
        probe = (root / "agent_probe.js").read_text(encoding="utf-8")
        popup = (root / "popup.js").read_text(encoding="utf-8")
        import re
        files = re.findall(r'"([^"\\]*\.js)"', probe.split("const SCRIPT_FILES")[1].split("]);", 1)[0])
        popup_files = re.findall(r'"([^"\\]*\.js)"', popup.split("files: [", 1)[1].split("],", 1)[0])
        self.assertEqual(popup_files, files)
        self.assertIn('type: "JOB_AI_EXTRACT_PAGE"', probe)
        self.assertIn('type: "JOB_AI_SCAN_FIELDS"', probe)
        self.assertNotIn('type: "JOB_AI_AUTOFILL"', probe)
        self.assertNotIn(".click()", probe)
        self.assertIn("chrome.permissions.request", probe)
        self.assertIn("chrome.scripting.executeScript", probe)

    def test_redaction_drops_sensitive_text_and_raw_fields(self):
        raw = {
            "ok": True, "content_version": "browser-content-v4.2",
            "extraction": {"source": {"site_adapter": "generic", "url": "https://example.test/?secret=yes"},
                           "job": {"job_title": "Engineer", "company": "Example", "jd_character_count": 500,
                                   "jd_text": "private job content", "capture_quality": "accepted"},
                           "capture": {"raw_visible_text": "private personal data"}},
            "scan": {"site_adapter": "generic", "standard_control_count": 2,
                     "visible_standard_control_count": 1, "mapped_field_count": 1,
                     "unmatched_visible_count": 0,
                     "fields": [{"kind": "email", "visible": True, "required": True,
                                 "matched_key": "email", "label": "Secret label", "nearby_text": "SSN",
                                 "value": "a@example.com"}]},
        }
        output = safe_summary(raw)
        serialized = json.dumps(output)
        for value in ("private", "secret", "SSN", "a@example.com", "jd_text", "nearby_text", "label"):
            self.assertNotIn(value, serialized)
        self.assertEqual(1, len(output["sample_fields"]))
        self.assertEqual("generic", output["adapter"])

    def test_refuses_incomplete_or_mixed_extension_output(self):
        for item in ({}, {"ok": False}, {"ok": True, "content_version": "old", "scan": {"fields": []}},
                     {"ok": True, "content_version": "browser-content-v4.2",
                      "extraction": {"source": {"site_adapter": "greenhouse"}},
                      "scan": {"site_adapter": "generic", "fields": []}}):
            with self.subTest(item=item), self.assertRaises(Stage1Error):
                safe_summary(item)


if __name__ == "__main__":
    unittest.main()

"""Stage 1 Firefox add-on packaging and fail-closed read-only checks."""
from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from job_agent.browser_firefox_stage1 import (
    _call_probe,
    _form_digest,
    _install_temp_addon,
    _probe_window,
    make_firefox_bundle,
    Stage1Error,
)
from job_agent.browser_stage1 import EXTENSION_ROOT, validate_target


class FakeDriver:
    def __init__(self):
        self.calls = []

    def install_web_extension(self, file_path, *, permanent):
        self.calls.append(("install_web_extension", file_path, permanent))

    def execute_async_script(self, script, *args):
        self.calls.append(("execute_async_script", script, args))
        return {"ok": True, "result": True, "value": "a" * 64}


class FirefoxStage1Tests(unittest.TestCase):
    def test_builds_temporary_firefox_manifest_without_touching_chromium(self):
        before = (EXTENSION_ROOT / "manifest.json").read_bytes()
        with tempfile.TemporaryDirectory() as temp:
            bundle = Path(temp) / "firefox.xpi"
            result = make_firefox_bundle(EXTENSION_ROOT, bundle)
            with zipfile.ZipFile(bundle) as z:
                manifest = json.loads(z.read("manifest.json"))
                names = set(z.namelist())
            self.assertEqual(manifest["background"], {"scripts": ["agent_background_firefox.js"]})
            self.assertNotIn("service_worker", manifest["background"])
            self.assertIn("browser_specific_settings", manifest)
            chromium = json.loads(before)
            for key in ("permissions", "host_permissions", "optional_permissions", "optional_host_permissions", "action"):
                self.assertEqual(manifest[key], chromium[key])
            self.assertIn("adapters/greenhouse.js", names)
            self.assertIn("adapters/mycareersfuture.js", names)
            self.assertIn("adapters/careers_gov.js", names)
            self.assertIn("agent_probe.js", names)
            self.assertNotIn("browser_extension/tests/agent_probe_self_test.js", names)
            self.assertGreaterEqual(result["file_count"], 20)
        self.assertEqual(before, (EXTENSION_ROOT / "manifest.json").read_bytes())

    def test_firefox_background_opens_only_own_probe(self):
        source = (EXTENSION_ROOT / "agent_background_firefox.js").read_text()
        self.assertIn('browser.runtime.getURL("agent_probe.html")', source)
        self.assertIn("browser.runtime.onInstalled", source)
        for name in ("JOB_AI_AUTOFILL", "JOB_AI_SUBMIT", "fetch(", "apply_url", "user_data"):
            self.assertNotIn(name, source)

    def test_does_not_allow_unknown_or_mutating_probe_commands(self):
        driver = FakeDriver()
        for action in ("autofill", "submit", "click", "navigate"):
            with self.assertRaises(Stage1Error):
                _call_probe(driver, action)
        self.assertFalse(driver.calls)
        self.assertIs(_call_probe(driver, "hasAccess"), True)

    def test_unsigned_install_is_always_temporary(self):
        driver = FakeDriver()
        _install_temp_addon(driver, Path("/tmp/test-addon.xpi"))
        self.assertEqual(driver.calls[-1][0], "install_web_extension")
        self.assertIs(driver.calls[-1][2], False)

    def test_fallback_unsigned_install_is_temporary(self):
        class OlderDriver:
            def install_addon(self, path, temporary=False):
                self.args = (path, temporary)
        d = OlderDriver()
        _install_temp_addon(d, Path("/tmp/test-addon.xpi"))
        self.assertTrue(d.args[1])

    def test_probe_fails_closed_if_no_extension_window(self):
        class NoProbe:
            window_handles = ["main"]
        with patch("job_agent.browser_firefox_stage1.time.monotonic", side_effect=[0, 50]):
            with self.assertRaisesRegex(Stage1Error, "probe tab"):
                _probe_window(NoProbe(), "main", timeout_seconds=2)

    def test_probe_only_accepts_proper_extension_origin(self):
        class Stub:
            window_handles = ["main", "evil", "probe"]
            current_url = ""
            switch_to = None
            def __init__(self):
                self.switch_to = SimpleNamespace(window=self.switch)
            def switch(self, handle):
                urls = {
                    "evil": "https://attacker.example/agent_probe.html",
                    "probe": "moz-extension://12345678-1234-1234-1234-123456789abc/agent_probe.html",
                }
                self.current_url = urls.get(handle, "")
        self.assertEqual(_probe_window(Stub(), "main", timeout_seconds=1), "probe")

    def test_form_integrity_only_transmits_sha256(self):
        d = FakeDriver()
        # FakeDriver's generic response has value=sha, as required.
        self.assertEqual(_form_digest(d), "a" * 64)
        self.assertIn("crypto.subtle.digest", d.calls[-1][1])

    def test_host_approval_reuses_exact_chromium_policy(self):
        self.assertEqual(validate_target("https://job-boards.greenhouse.io/okx/jobs/8045415003", allowed_host="job-boards.greenhouse.io"), "job-boards.greenhouse.io")
        for url,host in [
            ("http://job-boards.greenhouse.io/a", "job-boards.greenhouse.io"),
            ("https://job-boards.greenhouse.io.evil.test/a", "job-boards.greenhouse.io"),
            ("https://127.0.0.1/a", "127.0.0.1"),
        ]:
            with self.assertRaises(Stage1Error):
                validate_target(url, allowed_host=host)

    def test_rejects_symlink_sources_before_archiving(self):
        import shutil
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "extension"
            shutil.copytree(EXTENSION_ROOT, source)
            try:
                (source / "untrusted.js").symlink_to(source / "popup.js")
            except (NotImplementedError, OSError):
                self.skipTest("Host does not allow unprivileged symlinks")
            with self.assertRaisesRegex(Stage1Error, "Symlink"):
                make_firefox_bundle(source, Path(temp) / "bundle.xpi")

    def test_bundle_excludes_unrelated_json_secrets(self):
        import shutil
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "extension"
            shutil.copytree(EXTENSION_ROOT, source)
            (source / "secrets.json").write_text('{"token":"should-not-ship"}')
            (source / "data.db").write_bytes(b"private-db")
            (source / "tests" / "private.js").write_text("very-private")
            output = Path(temp) / "bundle.xpi"
            make_firefox_bundle(source, output)
            with zipfile.ZipFile(output) as archive:
                names = set(archive.namelist())
            self.assertNotIn("secrets.json", names)
            self.assertNotIn("data.db", names)
            self.assertNotIn("tests/private.js", names)


if __name__ == "__main__":
    unittest.main()

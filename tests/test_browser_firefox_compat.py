from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from browser_integration.bridge_server import _allowed_extension_origin

ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "browser_extension"
BUILD_SCRIPT = ROOT / "scripts" / "build_browser_extension.py"


class BrowserFirefoxCompatibilityTests(unittest.TestCase):
    def test_firefox_manifest_preserves_shared_permission_contract(self) -> None:
        chrome_manifest = json.loads(
            (EXTENSION / "manifest.json").read_text(encoding="utf-8")
        )
        firefox_manifest = json.loads(
            (EXTENSION / "manifest.firefox.json").read_text(encoding="utf-8")
        )

        for key in (
            "manifest_version",
            "name",
            "version",
            "description",
            "permissions",
            "optional_permissions",
            "host_permissions",
            "optional_host_permissions",
            "action",
        ):
            self.assertEqual(firefox_manifest[key], chrome_manifest[key])

        self.assertEqual(firefox_manifest["manifest_version"], 3)
        self.assertNotIn("<all_urls>", json.dumps(firefox_manifest))

        gecko = firefox_manifest["browser_specific_settings"]["gecko"]
        self.assertEqual(
            gecko["id"],
            "job-ai-helper-browser@job-ai-helper.local",
        )
        self.assertEqual(
            gecko["data_collection_permissions"]["required"],
            ["none"],
        )

    def test_bridge_accepts_chromium_and_firefox_extension_origins(self) -> None:
        self.assertTrue(
            _allowed_extension_origin("chrome-extension://abcdefghijklmnop")
        )
        self.assertTrue(
            _allowed_extension_origin("moz-extension://01234567-89ab-cdef")
        )
        self.assertFalse(_allowed_extension_origin("https://example.com"))
        self.assertFalse(_allowed_extension_origin("http://127.0.0.1:8501"))
        self.assertFalse(_allowed_extension_origin("evil-moz-extension://abc"))

    def test_firefox_build_uses_firefox_manifest_without_forking_js(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [
                    sys.executable,
                    str(BUILD_SCRIPT),
                    "--target",
                    "firefox",
                    "--output-dir",
                    directory,
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

            built = Path(directory) / "firefox"
            built_manifest = json.loads(
                (built / "manifest.json").read_text(encoding="utf-8")
            )
            source_manifest = json.loads(
                (EXTENSION / "manifest.firefox.json").read_text(encoding="utf-8")
            )
            self.assertEqual(built_manifest, source_manifest)
            self.assertTrue((built / "popup.js").is_file())
            self.assertTrue((built / "content.js").is_file())
            self.assertTrue((built / "adapters" / "linkedin.js").is_file())
            self.assertFalse((built / "manifest.firefox.json").exists())
            self.assertFalse((built / "README.md").exists())
            self.assertFalse((built / "tests").exists())
            self.assertEqual(
                (built / "popup.js").read_bytes(),
                (EXTENSION / "popup.js").read_bytes(),
            )
            self.assertEqual(
                (built / "content.js").read_bytes(),
                (EXTENSION / "content.js").read_bytes(),
            )

    def test_chrome_build_keeps_chrome_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [
                    sys.executable,
                    str(BUILD_SCRIPT),
                    "--target",
                    "chrome",
                    "--output-dir",
                    directory,
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

            built_manifest = json.loads(
                (Path(directory) / "chrome" / "manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            source_manifest = json.loads(
                (EXTENSION / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(built_manifest, source_manifest)
            self.assertNotIn("browser_specific_settings", built_manifest)


if __name__ == "__main__":
    unittest.main()

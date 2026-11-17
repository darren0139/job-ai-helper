from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts import build_firefox_unlisted_release as release


ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "browser_extension"


class BrowserExtensionFirefoxReleaseTests(unittest.TestCase):
    def test_firefox_manifest_has_release_privacy_contract(self) -> None:
        manifest = json.loads(
            (EXT / "manifest.firefox.json").read_text(encoding="utf-8")
        )
        gecko = manifest["browser_specific_settings"]["gecko"]

        self.assertEqual(
            gecko["id"],
            "job-ai-helper-browser@job-ai-helper.local",
        )
        self.assertGreaterEqual(
            tuple(
                int(part)
                for part in gecko["strict_min_version"].split(".")
            ),
            (142, 0),
        )

        required = set(
            gecko["data_collection_permissions"]["required"]
        )
        self.assertNotIn("none", required)
        self.assertTrue(
            {
                "authenticationInfo",
                "browsingActivity",
                "personallyIdentifyingInfo",
                "websiteContent",
            }.issubset(required)
        )

    def test_firefox_common_manifest_values_match_chrome(self) -> None:
        chrome = json.loads(
            (EXT / "manifest.json").read_text(encoding="utf-8")
        )
        firefox = json.loads(
            (EXT / "manifest.firefox.json").read_text(encoding="utf-8")
        )
        for key in release.COMMON_KEYS:
            self.assertEqual(firefox.get(key), chrome.get(key), key)

        self.assertNotIn("browser_specific_settings", chrome)

    def test_builder_validates_offline(self) -> None:
        report = release.validate_release_inputs()
        self.assertEqual(report["version"], "0.4.6.7")
        self.assertIn("websiteContent", report["required_data"])

    def test_built_zip_uses_firefox_manifest_at_archive_root(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            archive_path = release.build_archive(Path(tempdir))
            with zipfile.ZipFile(archive_path, "r") as archive:
                names = set(archive.namelist())
                packaged = json.loads(
                    archive.read("manifest.json").decode("utf-8")
                )

        self.assertIn("manifest.json", names)
        self.assertIn("popup.js", names)
        self.assertIn("content.js", names)
        self.assertIn("adapters/linkedin.js", names)
        self.assertNotIn("manifest.firefox.json", names)
        self.assertNotIn("README.md", names)
        self.assertNotIn("PRIVACY.md", names)
        self.assertFalse(any(name.startswith("tests/") for name in names))

        source = json.loads(
            (EXT / "manifest.firefox.json").read_text(encoding="utf-8")
        )
        self.assertEqual(packaged, source)

    def test_privacy_notice_mentions_actual_data_paths(self) -> None:
        privacy = (EXT / "PRIVACY.md").read_text(encoding="utf-8").casefold()
        for phrase in (
            "localhost",
            "browsing activity",
            "website content",
            "personally identifying",
            "pairing token",
            "does not automatically submit",
        ):
            self.assertIn(phrase, privacy)


if __name__ == "__main__":
    unittest.main()

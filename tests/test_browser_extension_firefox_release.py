from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

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
        self.assertEqual(report["version"], "0.4.6.9")
        self.assertIn("websiteContent", report["required_data"])

    def test_built_zip_uses_firefox_manifest_at_archive_root(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            archive_path = release.build_archive(Path(tempdir))
            with zipfile.ZipFile(archive_path, "r") as archive:
                names = set(archive.namelist())
                for name in ("app_capture.js", "app_capture_background.js"):
                    self.assertIn(name, names)
                    self.assertEqual(archive.read(name), (EXT / name).read_bytes())
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

    def test_manifest_capture_assets_are_required_without_popup_references(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            chrome = root / "manifest.json"
            firefox = root / "manifest.firefox.json"
            chrome.write_bytes((EXT / "manifest.json").read_bytes())
            firefox.write_bytes((EXT / "manifest.firefox.json").read_bytes())
            for name in release.BASE_RUNTIME | {"PRIVACY.md"}:
                (root / name).write_text("", encoding="utf-8")
            capture = {"app_capture.js", "app_capture_background.js"}
            for name in capture:
                (root / name).write_text("// capture fixture", encoding="utf-8")
            with patch.multiple(release, EXT=root, CHROME=chrome, FIREFOX=firefox):
                report = release.validate_release_inputs()
                self.assertTrue(capture <= {name for name, _ in report["members"]})
                for name in sorted(capture):
                    with self.subTest(missing=name):
                        asset = root / name
                        original = asset.read_bytes()
                        asset.unlink()
                        try:
                            with self.assertRaisesRegex(RuntimeError, "Missing runtime file"):
                                release.validate_release_inputs()
                        finally:
                            asset.write_bytes(original)

    def test_manifest_paths_reject_escape(self) -> None:
        for name in ("../outside.js", "/absolute.js", "C:/outside.js", "a\\b.js"):
            with self.subTest(name=name):
                with self.assertRaisesRegex(RuntimeError, "Invalid manifest runtime path"):
                    release._manifest_runtime_files({"background": {"scripts": [name]}})

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

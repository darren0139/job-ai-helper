from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import database.browser_bridge_settings as settings


class BrowserBridgeSettingsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_db_path = settings.DB_PATH
        settings.DB_PATH = Path(self.tempdir.name) / "applications.db"

    def tearDown(self) -> None:
        settings.DB_PATH = self.original_db_path
        self.tempdir.cleanup()

    def test_pairing_token_is_stable_until_rotated(self) -> None:
        first = settings.get_or_create_browser_bridge_token()
        second = settings.get_or_create_browser_bridge_token()

        self.assertTrue(first)
        self.assertEqual(first, second)

        rotated = settings.rotate_browser_bridge_token()
        self.assertTrue(rotated)
        self.assertNotEqual(rotated, first)
        self.assertEqual(
            settings.get_or_create_browser_bridge_token(),
            rotated,
        )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import tempfile
import unittest
import urllib.request
from pathlib import Path

import database.browser_bridge_settings as settings
from browser_integration.bridge_runtime import start_browser_bridge_runtime
from browser_integration.bridge_server import TOKEN_HEADER


class BrowserBridgeRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_db_path = settings.DB_PATH
        settings.DB_PATH = Path(self.tempdir.name) / "applications.db"

    def tearDown(self) -> None:
        settings.DB_PATH = self.original_db_path
        self.tempdir.cleanup()

    def test_runtime_starts_on_loopback_and_answers_health(self) -> None:
        runtime = start_browser_bridge_runtime(port=0)
        try:
            self.assertTrue(runtime.is_alive)
            self.assertEqual(runtime.host, "127.0.0.1")
            self.assertGreater(runtime.port, 0)

            request = urllib.request.Request(
                f"{runtime.url}/health",
                headers={TOKEN_HEADER: runtime.token},
            )
            with urllib.request.urlopen(request, timeout=2.0) as response:
                self.assertEqual(response.status, 200)
                self.assertIn(
                    b"job-ai-helper-browser-bridge",
                    response.read(),
                )
        finally:
            runtime.stop()

        self.assertFalse(runtime.is_alive)


if __name__ == "__main__":
    unittest.main()

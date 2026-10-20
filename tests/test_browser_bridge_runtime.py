from __future__ import annotations

import tempfile
import unittest
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import database.browser_bridge_settings as settings
from browser_integration.bridge_runtime import start_browser_bridge_runtime
from browser_integration.bridge_server import TOKEN_HEADER
from scripts.offline_loopback import loopback_http_scope


class BrowserBridgeRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.enterContext(patch.object(
            settings, "DB_PATH", Path(self.tempdir.name) / "applications.db"
        ))

    @contextmanager
    def running_bridge(self):
        # HTTPServer's display-only server_name lookup must not perform DNS.
        # Binding, serving, authentication and HTTP requests remain real.
        with loopback_http_scope(), patch("socket.getfqdn", side_effect=lambda host: host):
            runtime = start_browser_bridge_runtime(port=0)
            try:
                yield runtime
            finally:
                runtime.stop()
                self.assertFalse(runtime.is_alive)
                self.assertFalse(runtime.thread.is_alive())
                self.assertEqual(runtime.server.socket.fileno(), -1)

    def request_health(self, runtime, *, token=None, origin=None):
        headers = {TOKEN_HEADER: runtime.token if token is None else token}
        if origin is not None:
            headers["Origin"] = origin
        request = urllib.request.Request(f"{runtime.url}/health", headers=headers)
        # Avoid inheriting machine proxy configuration for local-only tests.
        return urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
            request, timeout=2.0
        )

    def test_runtime_starts_on_loopback_and_answers_health(self) -> None:
        with self.running_bridge() as runtime:
            self.assertTrue(runtime.is_alive)
            self.assertEqual(runtime.host, "127.0.0.1")
            self.assertGreater(runtime.port, 0)

            with self.request_health(runtime) as response:
                self.assertEqual(response.status, 200)
                self.assertIn(
                    b"job-ai-helper-browser-bridge",
                    response.read(),
                )
        self.assertFalse(runtime.is_alive)

    def test_real_http_authentication_and_origin_guards(self):
        with self.running_bridge() as runtime:
            for token, origin, expected in (
                ("", None, 401), ("wrong-token", None, 401),
                (runtime.token, "https://example.invalid", 403),
            ):
                with self.subTest(status=expected, origin=origin):
                    with self.assertRaises(urllib.error.HTTPError) as caught:
                        self.request_health(runtime, token=token, origin=origin)
                    self.assertEqual(caught.exception.code, expected)
                    caught.exception.close()
            with self.request_health(runtime, origin="chrome-extension://synthetic") as response:
                self.assertEqual(response.status, 200)

    def test_sequential_runs_and_exception_close_listener_and_thread(self):
        for _ in range(2):
            with self.assertRaisesRegex(ValueError, "synthetic failure"):
                with self.running_bridge() as runtime:
                    with self.request_health(runtime) as response:
                        self.assertEqual(response.status, 200)
                    raise ValueError("synthetic failure")
            self.assertFalse(runtime.thread.is_alive())
            self.assertEqual(runtime.server.socket.fileno(), -1)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import http.client
import threading
import unittest

from browser_integration.bridge_server import (
    DEFAULT_HOST, TOKEN_HEADER, JobAIBridgeServer, _allowed_extension_origin,
)


class BrowserBridgeOriginTests(unittest.TestCase):
    def test_complete_extension_origins(self) -> None:
        for origin in (
            "chrome-extension://abcdefghijklmnopabcdefghijklmnop",
            "moz-extension://01234567-89ab-cdef-0123-456789abcdef",
        ):
            with self.subTest(origin=origin):
                self.assertTrue(_allowed_extension_origin(origin))

    def test_malformed_and_web_origins(self) -> None:
        for origin in (
            "", "null", "https://example.com", "http://127.0.0.1:8501",
            "evil-moz-extension://abc", "moz-extension://abc/path",
            "moz-extension://abc?x=1", "moz-extension://abc#fragment",
            "moz-extension://user@abc", "moz-extension://user:pass@abc",
            "moz-extension://abc:8765", "chrome-extension://abc/path",
            "moz-extension://", "moz-extension://abc:", "moz-extension://abc:bad",
            "moz-extension://[", "moz-extension://abc/", "moz-extension://abc?",
            "moz-extension://abc#", "moz-extension://a\nbc", " moz-extension://abc",
            "moz-extension://abc ", "moz-extension://abc\\path",
        ):
            with self.subTest(origin=origin):
                self.assertFalse(_allowed_extension_origin(origin))

    def test_http_guard_keeps_token_required_and_cli_supported(self) -> None:
        server = JobAIBridgeServer((DEFAULT_HOST, 0), "test-only-token")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for origin in (None, "chrome-extension://abc", "moz-extension://generated-uuid"):
                for token in (None, "wrong", "test-only-token"):
                    with self.subTest(origin=origin, token=token):
                        headers = {}
                        if origin is not None:
                            headers["Origin"] = origin
                        if token is not None:
                            headers[TOKEN_HEADER] = token
                        connection = http.client.HTTPConnection(*server.server_address, timeout=2)
                        try:
                            connection.request("GET", "/health", headers=headers)
                            response = connection.getresponse()
                            self.assertEqual(response.status, 200 if token == "test-only-token" else 401)
                            self.assertEqual(response.getheader("Access-Control-Allow-Origin"), origin)
                            response.read()
                        finally:
                            connection.close()
            for origin in ("https://example.com", "moz-extension://abc/path"):
                connection = http.client.HTTPConnection(*server.server_address, timeout=2)
                try:
                    connection.request("GET", "/health", headers={"Origin": origin, TOKEN_HEADER: "test-only-token"})
                    response = connection.getresponse()
                    self.assertEqual(response.status, 403)
                    self.assertIsNone(response.getheader("Access-Control-Allow-Origin"))
                    response.read()
                finally:
                    connection.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

from __future__ import annotations

import unittest

from browser_integration.bridge_server import (
    DEFAULT_HOST,
    TOKEN_HEADER,
    _allowed_extension_origin,
)


class BrowserBridgeContractTests(unittest.TestCase):
    def test_bridge_binds_to_loopback_by_default(self) -> None:
        self.assertEqual(DEFAULT_HOST, "127.0.0.1")

    def test_bridge_uses_explicit_token_header(self) -> None:
        self.assertEqual(TOKEN_HEADER, "X-Job-AI-Bridge-Token")

    def test_only_chrome_extension_origins_are_allowed(self) -> None:
        self.assertTrue(
            _allowed_extension_origin(
                "chrome-extension://abcdefghijklmnop"
            )
        )
        self.assertFalse(
            _allowed_extension_origin("https://example.com")
        )
        self.assertFalse(
            _allowed_extension_origin("http://localhost:8501")
        )


if __name__ == "__main__":
    unittest.main()

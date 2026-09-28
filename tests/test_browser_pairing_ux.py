from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "browser_extension"


class BrowserPairingUxTests(unittest.TestCase):
    def test_popup_exposes_pairing_visibility_and_clear_controls(self) -> None:
        html = (EXTENSION / "popup.html").read_text(encoding="utf-8")
        popup = (EXTENSION / "popup.js").read_text(encoding="utf-8")

        self.assertIn('id="showBridgeTokenButton"', html)
        self.assertIn('id="clearPairingButton"', html)
        self.assertIn("Pairing is stored separately in each browser", html)
        self.assertIn("Firefox does not inherit", html)

        self.assertIn("refreshBridgeTokenControls", popup)
        self.assertIn('bridgeToken.type = reveal ? "text" : "password"', popup)
        self.assertIn("chrome.storage.local.remove(BRIDGE_TOKEN_KEY)", popup)
        self.assertIn("clear_browser_bridge_pairing", popup)

    def test_wrong_token_gets_browser_specific_diagnostic(self) -> None:
        popup = (EXTENSION / "popup.js").read_text(encoding="utf-8")

        self.assertIn("response.status === 401", popup)
        self.assertIn("Pairing token was rejected", popup)
        self.assertIn(
            "Firefox, Chrome, and Edge store extension pairing separately",
            popup,
        )

    def test_pairing_is_persisted_only_after_bridge_validation(self) -> None:
        popup = (EXTENSION / "popup.js").read_text(encoding="utf-8")

        function_start = popup.index("async function connectAndLoadProfile")
        function_end = popup.index(
            'showBridgeTokenButton.addEventListener',
            function_start,
        )
        function_text = popup[function_start:function_end]

        health_index = function_text.index('bridgeFetch("/health")')
        profile_index = function_text.index(
            'bridgeFetch("/api/v1/application-profile")'
        )
        storage_index = function_text.index("chrome.storage.local.set")

        self.assertLess(health_index, storage_index)
        self.assertLess(profile_index, storage_index)

    def test_clear_pairing_does_not_delete_profile_or_jd_data(self) -> None:
        popup = (EXTENSION / "popup.js").read_text(encoding="utf-8")

        listener_start = popup.index(
            'clearPairingButton.addEventListener'
        )
        listener_end = popup.index(
            'connectButton.addEventListener',
            listener_start,
        )
        listener = popup[listener_start:listener_end]

        self.assertIn(
            "chrome.storage.local.remove(BRIDGE_TOKEN_KEY)",
            listener,
        )
        self.assertNotIn(
            "chrome.storage.local.remove(PROFILE_STORAGE_KEY)",
            listener,
        )
        self.assertNotIn("/api/v1/jd-captures", listener)


if __name__ == "__main__":
    unittest.main()

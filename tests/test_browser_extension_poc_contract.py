from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "browser_extension"


class BrowserExtensionPocContractTests(unittest.TestCase):
    def test_manifest_keeps_batch_site_access_optional(self) -> None:
        manifest = json.loads(
            (EXTENSION / "manifest.json").read_text(encoding="utf-8")
        )

        self.assertEqual(manifest["manifest_version"], 3)
        self.assertIn("activeTab", manifest["permissions"])
        self.assertIn("scripting", manifest["permissions"])
        self.assertIn("storage", manifest["permissions"])
        self.assertNotIn("tabs", manifest["permissions"])
        self.assertIn("tabs", manifest.get("optional_permissions", []))

        host_permissions = set(manifest.get("host_permissions", []))
        self.assertEqual(
            host_permissions,
            {
                "http://127.0.0.1/*",
                "http://localhost/*",
            },
        )

        optional_hosts = set(manifest.get("optional_host_permissions", []))
        self.assertEqual(
            optional_hosts,
            {
                "http://*/*",
                "https://*/*",
            },
        )
        self.assertNotIn("<all_urls>", json.dumps(manifest))

    def test_popup_exposes_review_only_batch_controls(self) -> None:
        html = (EXTENSION / "popup.html").read_text(encoding="utf-8")
        popup = (EXTENSION / "popup.js").read_text(encoding="utf-8")

        self.assertIn("Discover open tabs", html)
        self.assertIn("Capture selected JDs to Job AI Helper", html)
        self.assertIn("Autofill safe fields in selected tabs", html)
        self.assertIn("batch_tabs.js", html)

        self.assertIn("chrome.permissions.request", popup)
        self.assertIn("chrome.tabs.query", popup)
        self.assertIn("batch_capture_selected_tabs", popup)
        self.assertIn("batch_autofill_selected_tabs", popup)
        self.assertIn("model_calls: 0", popup)

    def test_batch_helper_filters_local_and_non_http_tabs(self) -> None:
        helper = (EXTENSION / "batch_tabs.js").read_text(encoding="utf-8")

        self.assertIn("capturableTabs", helper)
        self.assertIn("permissionPatterns", helper)
        self.assertIn("isLocalAppUrl", helper)
        self.assertIn("127.0.0.1", helper)
        self.assertIn("localhost", helper)

    def test_content_script_has_no_submit_navigation_action(self) -> None:
        content = (EXTENSION / "content.js").read_text(encoding="utf-8")

        self.assertNotIn('querySelector("button[type=\\"submit\\"]")', content)
        self.assertNotIn(".submit()", content)
        self.assertIn(
            "This POC never clicks submit/navigation buttons",
            content,
        )

    def test_mapping_whitelist_excludes_high_risk_application_fields(self) -> None:
        mapping = (EXTENSION / "mapping.js").read_text(encoding="utf-8")

        self.assertIn('"full_name"', mapping)
        self.assertIn('"notice_period"', mapping)
        self.assertIn('"requires_sponsorship"', mapping)

        self.assertNotIn('"salary_expectation"', mapping)
        self.assertNotIn('"work_authorization"', mapping)
        self.assertNotIn('"willing_to_relocate"', mapping)

    def test_popup_has_local_bridge_and_json_fallback(self) -> None:
        popup = (EXTENSION / "popup.js").read_text(encoding="utf-8")

        self.assertIn("chrome.storage.local", popup)
        self.assertIn("/api/v1/application-profile", popup)
        self.assertIn("/api/v1/jd-captures", popup)
        self.assertIn("jobAiHelperProfilePayload", popup)
        self.assertNotIn("api.openai.com", popup)

    def test_popup_injects_adapter_framework_before_content(self) -> None:
        popup = (EXTENSION / "popup.js").read_text(encoding="utf-8")

        for required_file in (
            '"adapters/registry.js"',
            '"adapters/generic.js"',
            '"adapters/careers_gov.js"',
            '"adapters/greenhouse.js"',
        ):
            self.assertIn(required_file, popup)
        self.assertLess(
            popup.index('"adapters/greenhouse.js"'),
            popup.index('"content.js"'),
        )

    def test_careers_gov_cleaner_separates_scoring_text_from_notes(self) -> None:
        cleaner = (EXTENSION / "jd_cleaning.js").read_text(encoding="utf-8")

        self.assertIn("careers_gov_sections_v2", cleaner)
        self.assertIn("postingNotes", cleaner)
        self.assertIn("discardedTrackingTags", cleaner)
        self.assertIn("two-year contract", cleaner)
        self.assertIn("#LI", cleaner)

    def test_adapter_framework_has_generic_careers_gov_and_greenhouse(self) -> None:
        registry = (EXTENSION / "adapters" / "registry.js").read_text(
            encoding="utf-8"
        )
        greenhouse = (EXTENSION / "adapters" / "greenhouse.js").read_text(
            encoding="utf-8"
        )
        careers = (EXTENSION / "adapters" / "careers_gov.js").read_text(
            encoding="utf-8"
        )

        self.assertIn("adapter-framework-v1", registry)
        self.assertIn('id: "greenhouse"', greenhouse)
        self.assertIn('id: "careers_gov"', careers)
        self.assertIn("gh_jid", greenhouse)
        self.assertIn("embedded_application_iframe", greenhouse)

    def test_content_keeps_raw_capture_separate_from_clean_jd(self) -> None:
        content = (EXTENSION / "content.js").read_text(encoding="utf-8")

        self.assertIn("raw_visible_text", content)
        self.assertIn("jd_text", content)
        self.assertIn("JobAIJDCleaning", content)

    def test_readme_documents_zero_credit_scope(self) -> None:
        readme = (EXTENSION / "README.md").read_text(encoding="utf-8")

        self.assertIn("does **not** call OpenAI", readme)
        self.assertIn("Clean JD text", readme)
        self.assertIn("Careers@Gov", readme)
        self.assertIn("v4 adapter framework", readme)
        self.assertIn("Application Profile v2", readme)
        self.assertIn("v4.1 batch prepare", readme)
        self.assertIn("optional_host_permissions", readme)
        self.assertIn("zero model/OpenAI calls", readme)


if __name__ == "__main__":
    unittest.main()

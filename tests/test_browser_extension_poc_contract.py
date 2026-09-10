from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "browser_extension"


class BrowserExtensionPocContractTests(unittest.TestCase):
    def test_manifest_uses_active_tab_and_localhost_only_host_permissions(self) -> None:
        manifest = json.loads(
            (EXTENSION / "manifest.json").read_text(encoding="utf-8")
        )

        self.assertEqual(manifest["manifest_version"], 3)
        self.assertIn("activeTab", manifest["permissions"])
        self.assertIn("scripting", manifest["permissions"])
        self.assertIn("storage", manifest["permissions"])

        host_permissions = set(manifest.get("host_permissions", []))
        self.assertEqual(
            host_permissions,
            {
                "http://127.0.0.1/*",
                "http://localhost/*",
            },
        )
        self.assertNotIn("<all_urls>", json.dumps(manifest))

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

    def test_popup_injects_dedicated_jd_cleaner_before_content(self) -> None:
        popup = (EXTENSION / "popup.js").read_text(encoding="utf-8")

        self.assertIn(
            'files: ["mapping.js", "jd_cleaning.js", "content.js"]',
            popup,
        )

    def test_careers_gov_cleaner_separates_scoring_text_from_notes(self) -> None:
        cleaner = (EXTENSION / "jd_cleaning.js").read_text(encoding="utf-8")

        self.assertIn("careers_gov_sections_v2", cleaner)
        self.assertIn("postingNotes", cleaner)
        self.assertIn("discardedTrackingTags", cleaner)
        self.assertIn("two-year contract", cleaner)
        self.assertIn("#LI", cleaner)

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


if __name__ == "__main__":
    unittest.main()

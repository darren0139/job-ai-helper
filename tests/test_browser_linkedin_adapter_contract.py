from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "browser_extension"


class BrowserLinkedInAdapterContractTests(unittest.TestCase):
    def test_linkedin_adapter_is_capture_only(self) -> None:
        text = (EXTENSION / "adapters" / "linkedin.js").read_text(
            encoding="utf-8"
        )
        self.assertIn('id: "linkedin"', text)
        self.assertIn('version: "linkedin-adapter-v5"', text)
        self.assertIn("captureOnly: true", text)
        self.assertIn("linkedin_job_posting_jsonld_v1", text)
        self.assertIn("linkedin_job_description_dom_v1", text)
        self.assertNotIn("chrome.", text)
        self.assertNotIn("window.location", text)

    def test_content_script_respects_capture_only_adapter(self) -> None:
        text = (EXTENSION / "content.js").read_text(encoding="utf-8")
        self.assertIn("adapter?.captureOnly === true", text)

    def test_content_script_rejects_not_ready_capture(self) -> None:
        text = (EXTENSION / "content.js").read_text(encoding="utf-8")
        self.assertIn("adapted?.notReady", text)
        self.assertIn("Job page is not ready for capture yet.", text)

    def test_linkedin_rejects_shell_identity_and_split_pane_raw_fallback(
        self,
    ) -> None:
        text = (EXTENSION / "adapters" / "linkedin.js").read_text(
            encoding="utf-8"
        )
        self.assertIn(r"^\d+\s+notifications?$", text)
        self.assertIn("hasReliableIdentity", text)
        self.assertIn("LinkedIn selected-job panel is not ready", text)
        self.assertIn("if (isSplitPane)", text)


    def test_linkedin_supports_logged_in_document_title_shape(self) -> None:
        text = (EXTENSION / "adapters" / "linkedin.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("document_title_pipe", text)
        self.assertIn("const pipeParts = title", text)
        self.assertIn('.split("|")', text)
        self.assertIn("document_title_parse", text)
        self.assertIn("title_candidates", text)
        self.assertIn("company_candidates", text)
        self.assertIn("description_selectors_found", text)

    def test_linkedin_logged_in_raw_fallback_has_shell_boundary(
        self,
    ) -> None:
        text = (EXTENSION / "adapters" / "linkedin.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("this job alert is", text.lower())
        self.assertIn(r"(?:…|\.\.\.)\s*more", text)

    def test_popup_injects_linkedin_adapter(self) -> None:
        text = (EXTENSION / "popup.js").read_text(encoding="utf-8")
        self.assertIn('"adapters/linkedin.js"', text)

    def test_linkedin_adapter_requires_a_specific_job_context(self) -> None:
        text = (EXTENSION / "adapters" / "linkedin.js").read_text(
            encoding="utf-8"
        )
        self.assertIn(r"/\/jobs\/view\//i", text)
        self.assertIn("currentJobId", text)
        self.assertIn("splitPaneJobUrl", text)
        self.assertIn("jobContextUrl", text)
        self.assertIn(r"/^\d{5,}$/", text)


if __name__ == "__main__":
    unittest.main()

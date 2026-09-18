from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "browser_extension"


class BrowserExtractionQualityContractTests(unittest.TestCase):
    def test_workday_quality_cleanup_is_present(self) -> None:
        text = (EXTENSION / "adapters" / "workday.js").read_text(
            encoding="utf-8"
        )
        self.assertIn('version: "workday-adapter-v2"', text)
        self.assertIn("cleanWorkdayDescription", text)
        self.assertIn("workday_job_posting_jsonld_v2", text)

    def test_phenom_quality_cleanup_is_present(self) -> None:
        text = (EXTENSION / "adapters" / "phenom.js").read_text(
            encoding="utf-8"
        )
        self.assertIn('version: "phenom-adapter-v2"', text)
        self.assertIn("cleanPhenomDescription", text)
        self.assertIn("phenom_job_posting_jsonld_v2", text)

    def test_successfactors_quality_cleanup_is_present(self) -> None:
        text = (EXTENSION / "adapters" / "successfactors.js").read_text(
            encoding="utf-8"
        )
        self.assertIn('version: "successfactors-adapter-v4"', text)
        self.assertIn("cleanSuccessFactorsDescription", text)
        self.assertIn("successfactors_job_description_dom_v4", text)

    def test_smartrecruiters_quality_cleanup_is_present(self) -> None:
        text = (EXTENSION / "adapters" / "smartrecruiters.js").read_text(
            encoding="utf-8"
        )
        self.assertIn('version: "smartrecruiters-adapter-v4"', text)
        self.assertIn("markerLength", text)
        self.assertIn("locationFromRawText", text)
        self.assertIn("smartrecruiters_sections_v4", text)

    def test_greenhouse_role_boundary_cleanup_is_present(self) -> None:
        text = (EXTENSION / "adapters" / "greenhouse.js").read_text(
            encoding="utf-8"
        )
        self.assertIn('version: "greenhouse-adapter-v2"', text)
        self.assertIn("trimCompanyPrelude", text)
        self.assertIn("greenhouse_job_description_dom_v2", text)


if __name__ == "__main__":
    unittest.main()

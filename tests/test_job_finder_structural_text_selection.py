from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from database import job_discovery_manager as manager
from job_discovery import pipeline
from job_discovery.browser_capture_ingest import (
    ingest_browser_capture_to_job_finder,
    normalized_browser_discovery_job,
)
from job_discovery.models import NormalizedJob
from job_discovery.sources.mycareersfuture import MyCareersFutureSource
from job_discovery.sources.smartrecruiters import SmartRecruitersSource
from job_discovery.structural_text_selection import (
    PROVENANCE_KEY,
    STRUCTURAL_TEXT_SELECTION_VERSION,
    select_job_description,
    select_structural_jd_text,
)


FULL = """About us
We build products for businesses around the world.

Responsibilities
- Build and maintain services supporting our customers.
- Investigate incidents and document operational procedures.

Requirements
- Knowledge of unusual spectrometry equipment is essential.
- A licence to handle archaeological specimens is required.

Preferred qualifications
- Familiarity with ancient manuscript conservation is an advantage.

Benefits
- Annual leave and medical cover.
- Staff discounts and wellness activities.

Eligibility
- Applicants must hold valid work authorisation in Singapore.

Working hours
- Weekend and night shifts are required for this role.

Privacy notice
We process application data under our published privacy policy.

How to apply
Please submit your CV using the company website.
"""


def job(description=FULL, raw=None):
    return NormalizedJob(
        source="mycareersfuture", source_job_id="test-1",
        title="Service Engineer", company="Example",
        description=description, location="Singapore",
        raw_payload={"html": "<article>Full source retained</article>"} if raw is None else raw,
    )


def browser_payload(adapter):
    url = "https://www.fastjobs.sg/singapore-job-ad/123/engineer/"
    if adapter == "workjio":
        url = "https://www.workjio.com/jobs/service-engineer"
    return {
        "source": {"site_adapter": adapter, "url": url, "captured_at": "2026-11-19T00:00:00Z"},
        "capture": {"raw_visible_text": FULL + "\nOther page navigation"},
        "job": {"job_title": "Service Engineer", "company": "Example",
                "location": "Singapore", "jd_text": FULL, "employment_type": "Part-time"},
    }


class StructuralTextSelectionTests(unittest.TestCase):
    def test_confident_sections_keep_role_requirements_and_preferred(self):
        result = select_structural_jd_text(FULL)
        self.assertEqual(result["strategy"], "conservative_section_selection")
        self.assertEqual(result["fallback_reason"], "")
        for text in ("Build and maintain", "Investigate incidents", "spectrometry",
                     "archaeological", "Preferred qualifications", "manuscript conservation"):
            self.assertIn(text, result["selected_description"])

    def test_work_eligibility_constraints_and_compensation_are_retained(self):
        result = select_structural_jd_text(FULL + "\nSalary\nS$4,000 per month.\n")
        for text in ("work authorisation", "Weekend and night shifts", "S$4,000"):
            self.assertIn(text, result["selected_description"])
        self.assertEqual(result["fallback_reason"], "")

    def test_clear_company_benefits_legal_and_application_sections_are_removed(self):
        result = select_structural_jd_text(FULL)
        for text in ("products for businesses", "Annual leave", "wellness activities",
                     "published privacy policy", "submit your CV"):
            self.assertNotIn(text, result["selected_description"])
        self.assertEqual(
            [section["heading"] for section in result["discarded_sections"]],
            ["About us", "Benefits", "Privacy notice", "How to apply"],
        )

    def test_weak_or_unheaded_text_falls_back_exactly(self):
        values = [
            "  Build software.\r\nBenefits include medical cover.\r\n ",
            "Requirements\nPython\nBenefits\nTea",
            "Benefits\nAnnual leave and medical cover.\nHow to apply\nSend your CV.",
            "",
        ]
        for text in values:
            with self.subTest(text=text):
                result = select_structural_jd_text(text)
                self.assertEqual(result["selected_description"], text)
                self.assertEqual(result["strategy"], "full_description_fallback")
                self.assertTrue(result["fallback_reason"])
                self.assertEqual(result["discarded_sections"], [])

    def test_unusual_requirements_are_not_filtered_by_relevance(self):
        original = FULL.replace(
            "A licence to handle archaeological specimens is required.",
            "Applicants must decipher medieval shorthand and operate a glass harmonica.",
        )
        selected = select_structural_jd_text(original)["selected_description"]
        self.assertIn("medieval shorthand", selected)
        self.assertIn("glass harmonica", selected)

    def test_requirement_like_content_in_excluded_section_forces_full_fallback(self):
        original = FULL.replace("Annual leave and medical cover.", "Knowledge of pensions legislation is required.")
        result = select_structural_jd_text(original)
        self.assertEqual(result["selected_description"], original)
        self.assertEqual(result["fallback_reason"], "possible_requirement_in_non_jd_section")

    def test_unknown_heading_in_excluded_section_forces_full_fallback(self):
        original = FULL.replace("Annual leave and medical cover.", "Special obligations:\nCarry sealed specimens between sites.")
        result = select_structural_jd_text(original)
        self.assertEqual(result["selected_description"], original)
        self.assertEqual(result["fallback_reason"], "ambiguous_heading_in_non_jd_section")

    def test_inferred_child_list_is_reused_but_cannot_alone_authorize_deletion(self):
        original = """Your daily mission
- Build reliable systems for our customers.
- Maintain services and investigate incidents.

Benefits
Annual leave and medical cover.
"""
        result = select_structural_jd_text(original)
        self.assertEqual(result["selected_description"], original)
        self.assertEqual(result["fallback_reason"], "no_confident_jd_structure")
        self.assertEqual(result["included_sections"][0]["detection"], "inferred_child_list")

    def test_unheaded_prefix_is_preserved(self):
        original = "Service Engineer, Singapore\n\n" + FULL
        result = select_structural_jd_text(original)
        self.assertTrue(result["selected_description"].startswith("Service Engineer, Singapore"))
        self.assertEqual(result["fallback_reason"], "")

    def test_diagnostics_reference_original_offsets_and_version(self):
        result = select_structural_jd_text(FULL)
        self.assertEqual(result["version"], STRUCTURAL_TEXT_SELECTION_VERSION)
        self.assertEqual(result["original_description"], FULL)
        self.assertTrue(result["section_inference_version"])
        for section in result["included_sections"] + result["discarded_sections"]:
            segment = FULL[section["start"]:section["end"]]
            self.assertTrue(segment.startswith(section["heading"]))
            self.assertIn(section["action"], {"include", "discard"})

    def test_full_payload_and_input_object_are_preserved(self):
        raw = {"html": "<div>all original content</div>", "nested": {"values": [1, 2]}}
        original = job(raw=raw)
        frozen = deepcopy(original.to_record())
        selected = select_job_description(original)
        self.assertEqual(original.to_record(), frozen)
        self.assertEqual(selected.raw_payload["html"], raw["html"])
        self.assertEqual(selected.raw_payload["nested"], raw["nested"])
        self.assertEqual(selected.raw_payload[PROVENANCE_KEY]["original_description"], FULL)
        self.assertIsNot(selected.raw_payload["nested"], original.raw_payload["nested"])

    def test_repeated_transformation_and_persisted_reuse_are_identical(self):
        first = select_job_description(job())
        self.assertEqual(select_job_description(first), first)
        self.assertEqual(select_job_description(first).content_hash, first.content_hash)
        row = first.to_record()
        row["raw_payload_json"] = json.dumps(row.pop("raw_payload"))
        reused = SmartRecruitersSource._known_job(row)
        self.assertIsNotNone(reused)
        self.assertEqual(select_job_description(reused), first)

    def test_updated_description_is_selected_again(self):
        first = select_job_description(job())
        changed = NormalizedJob(
            source=first.source, source_job_id=first.source_job_id,
            title=first.title, company=first.company,
            description=FULL.replace("spectrometry", "astronomy"),
            raw_payload=first.raw_payload,
        )
        second = select_job_description(changed)
        self.assertIn("astronomy", second.description)
        self.assertNotIn("spectrometry", second.description)
        self.assertEqual(select_job_description(second), second)

    def test_source_provenance_key_collision_is_recoverable_and_idempotent(self):
        original = job(raw={PROVENANCE_KEY: {"source_field": "original value"}})
        selected = select_job_description(original)
        self.assertEqual(selected.raw_payload[PROVENANCE_KEY]["source_provenance_value"],
                         original.raw_payload[PROVENANCE_KEY])
        self.assertEqual(select_job_description(selected), selected)

    def test_html_without_normalized_headings_falls_back_unchanged(self):
        original = "<h2>Requirements</h2><p>Build tools</p><h2>Benefits</h2><p>Tea</p>"
        self.assertEqual(select_structural_jd_text(original)["selected_description"], original)


class StructuralSelectionIntegrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.db = Path(temporary.name) / "applications.db"
        database_patch = patch.object(manager, "DB_PATH", self.db)
        database_patch.start()
        self.addCleanup(database_patch.stop)
        manager.init_job_discovery_schema()

    def test_source_refresh_fetches_full_text_then_persists_shared_selection(self):
        class Client:
            def __init__(self):
                self.calls = []

            def get_json(self, url, **kwargs):
                self.calls.append((url, kwargs))
                return {"results": [{"uuid": "direct-1", "title": "Service Engineer",
                                     "description": FULL, "postedCompany": {"name": "Example"}}]}

            def pause(self, _seconds):
                pass

        client = Client()
        source = MyCareersFutureSource(client=client)
        with patch.object(pipeline, "_build_sources", return_value=[source]):
            receipt = pipeline.refresh_job_sources(query="", selected_sources=["mycareersfuture"],
                                                   min_refresh_interval_minutes=0)
            self.assertEqual(receipt[0]["status"], "ok")
            second = pipeline.refresh_job_sources(query="", selected_sources=["mycareersfuture"],
                                                  min_refresh_interval_minutes=0)
        self.assertEqual(second[0]["unchanged"], 1)
        self.assertEqual(len(client.calls), 2)
        row = manager.list_discovered_jobs()[0]
        normalized = MyCareersFutureSource.normalize({
            "uuid": "direct-1", "title": "Service Engineer", "description": FULL,
            "postedCompany": {"name": "Example"},
        })
        expected = select_structural_jd_text(normalized.description)
        self.assertEqual(row["description"], expected["selected_description"])
        raw = json.loads(row["raw_payload_json"])
        self.assertEqual(raw[PROVENANCE_KEY], expected)
        self.assertEqual(raw["description"], FULL)

    def test_fastjobs_and_workjio_use_same_selector_and_keep_capture_payload(self):
        expected = select_structural_jd_text(FULL.strip())
        for adapter in ("fastjobs", "workjio"):
            with self.subTest(adapter=adapter):
                payload = browser_payload(adapter)
                original = deepcopy(payload)
                normalized = normalized_browser_discovery_job(payload, {"id": 1})
                self.assertEqual(normalized.description, expected["selected_description"])
                self.assertEqual(normalized.raw_payload[PROVENANCE_KEY], expected)
                receipt = ingest_browser_capture_to_job_finder(payload, {"id": 1})
                self.assertEqual(receipt["status"], "indexed")
                repeat = ingest_browser_capture_to_job_finder(payload, {"id": 1})
                self.assertEqual(repeat["stats"]["unchanged"], 1)
                self.assertEqual(payload, original)
        rows = manager.list_discovered_jobs()
        self.assertEqual(len(rows), 2)
        for row in rows:
            raw = json.loads(row["raw_payload_json"])
            self.assertEqual(raw[PROVENANCE_KEY]["original_description"], FULL.strip())
            self.assertEqual(raw["capture_payload"]["job"]["jd_text"], FULL)
            self.assertIn("Other page navigation", raw["capture_payload"]["capture"]["raw_visible_text"])

    def test_unrelated_browser_adapter_is_not_promoted(self):
        payload = browser_payload("fastjobs")
        payload["source"]["site_adapter"] = "linkedin"
        self.assertIsNone(normalized_browser_discovery_job(payload, {"id": 1}))

    def test_direct_persistence_and_registry_behavior_are_unchanged(self):
        original = job()
        manager.upsert_discovered_jobs([original])
        self.assertEqual(manager.list_discovered_jobs()[0]["description"], FULL)
        self.assertEqual(manager.list_target_companies(include_disabled=True), [])
        manager.upsert_target_company(company_name="NCS", ats_provider="smartrecruiters", ats_identifier="NCS3")
        before = manager.export_target_company_registry()
        ingest_browser_capture_to_job_finder(browser_payload("fastjobs"), {"id": 1})
        self.assertEqual(manager.export_target_company_registry(), before)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

import fitz
from docx import Document

from llm import summarise_call_usage
from tailoring.phase9f_jd_intake import (
    Phase9FJDIntakeError,
    build_phase9f_analysis_diagnostics,
    build_reused_exact_jd_snapshot,
    build_transient_exact_jd_snapshot,
    extract_job_description_file,
    phase9f_analysis_diagnostics_json,
    phase9f_jd_input_fingerprint,
)
from tailoring.jd_user_input_overrides import JD_USER_OVERRIDE_POLICY_VERSION


RAW_JD = """
Junior AI Full-Stack Engineer
Example Company
Responsibilities
Build and maintain full-stack user-facing applications using Python, React,
TypeScript, PostgreSQL, authentication workflows, and secure database access.
Collaborate with engineers to test, deploy, and operate reliable services.
Requirements
Strong Python and React skills are required. PostgreSQL experience is required.
Preferred qualifications
Experience with cloud deployment and automated testing is preferred.
""".strip()


def profile() -> dict:
    return {
        "job_title": "Junior AI Full-Stack Engineer",
        "company": "Example Company",
        "location": "Singapore",
        "experience_level": "Junior",
        "responsibilities": [
            "Build and maintain full-stack user-facing applications."
        ],
        "required_skills": ["Python", "React", "PostgreSQL"],
        "preferred_skills": ["Cloud deployment", "Automated testing"],
        "tools_technologies": ["Python", "React", "TypeScript", "PostgreSQL"],
        "soft_skills": ["Collaboration"],
        "buzzwords": [],
        "deal_breakers": [],
    }


class Phase9FJDIntakeTests(unittest.TestCase):
    def test_snapshot_is_deterministic_and_contains_no_final_seed(self):
        first = build_transient_exact_jd_snapshot(
            raw_text=RAW_JD,
            jd_profile=profile(),
            source_type="pasted",
            extraction_model_id="test-model",
            model_calls=[{"model": "test-model"}],
        )
        second = build_transient_exact_jd_snapshot(
            raw_text=RAW_JD,
            jd_profile=profile(),
            source_type="pasted",
            source_url="https://example.test/display-only",
            extraction_model_id="test-model",
            model_calls=[{"model": "test-model", "elapsed_seconds": 9}],
        )
        self.assertEqual(first["raw_jd_sha256"], second["raw_jd_sha256"])
        self.assertEqual(
            first["structured_profile_fingerprint"],
            second["structured_profile_fingerprint"],
        )
        self.assertEqual(
            first["canonical_requirement_fingerprint"],
            second["canonical_requirement_fingerprint"],
        )
        self.assertEqual(first["role_family"], second["role_family"])
        self.assertEqual(
            first["snapshot_fingerprint"], second["snapshot_fingerprint"]
        )
        self.assertTrue(first["canonical_requirements"])
        self.assertNotIn("final_scoring_seed", first)
        self.assertEqual(first["embedding_call_count"], 0)

    def test_explicit_metadata_precedes_extraction(self):
        snapshot = build_transient_exact_jd_snapshot(
            raw_text=RAW_JD,
            jd_profile=profile(),
            source_type="pasted",
            title="AI & Full-Stack Software Engineer",
            company="Explicit Company",
            location="Remote",
        )
        self.assertEqual(
            snapshot["job_title"], "AI & Full-Stack Software Engineer"
        )
        self.assertEqual(snapshot["company"], "Explicit Company")
        self.assertEqual(snapshot["location"], "Remote")
        self.assertEqual(
            snapshot["role_family"]["role_family_id"],
            "ai_fullstack_software_engineering",
        )

    def test_source_url_does_not_invalidate_analysis_input(self):
        baseline = phase9f_jd_input_fingerprint(
            source_type="pasted",
            raw_text=RAW_JD,
            title="Engineer",
            company="Example",
            extraction_model_id="test-model",
        )
        same = phase9f_jd_input_fingerprint(
            source_type="pasted",
            raw_text=RAW_JD,
            title="Engineer",
            company="Example",
            extraction_model_id="test-model",
        )
        self.assertEqual(baseline, same)

    def test_preferred_requirement_override_is_local_and_changes_snapshot_identity(self):
        requirement = "Experience with Android app development and Kotlin"
        baseline = build_transient_exact_jd_snapshot(
            raw_text=RAW_JD,
            jd_profile=profile(),
            source_type="pasted",
        )
        overridden = build_transient_exact_jd_snapshot(
            raw_text=RAW_JD,
            jd_profile=profile(),
            source_type="pasted",
            preferred_requirements=[requirement],
        )
        reordered = build_transient_exact_jd_snapshot(
            raw_text=RAW_JD,
            jd_profile=profile(),
            source_type="pasted",
            preferred_requirements=[f"  {requirement}  ", requirement],
        )

        self.assertNotEqual(
            baseline["snapshot_fingerprint"],
            overridden["snapshot_fingerprint"],
        )
        self.assertEqual(
            overridden["snapshot_fingerprint"],
            reordered["snapshot_fingerprint"],
        )
        self.assertEqual(overridden["raw_text"], RAW_JD)
        self.assertEqual(overridden["jd_profile"], profile())
        inputs = overridden["application_local_jd_user_inputs"]
        self.assertEqual(inputs["policy_version"], JD_USER_OVERRIDE_POLICY_VERSION)
        self.assertEqual(inputs["canonical_preferred_matches"], [])
        self.assertEqual(inputs["supplemental_preferred_requirements"], [requirement])
        supplemental = [
            row
            for row in overridden["canonical_requirements"]
            if row.get("application_requirement_scope") == "application_local"
        ]
        self.assertEqual(len(supplemental), 1)
        self.assertEqual(supplemental[0]["importance"], "preferred")
        self.assertEqual(supplemental[0]["importance_source"], "user_supplied")
        self.assertFalse(supplemental[0]["canonical_shared"])

    def test_each_semantic_source_change_invalidates_input(self):
        baseline = phase9f_jd_input_fingerprint(
            source_type="uploaded",
            raw_text=RAW_JD,
            title="Engineer",
            company="Example",
            library_jd_id=12,
            source_version_id_value="version-a",
            source_artifact_sha256="artifact-a",
            extraction_model_id="test-model",
        )
        changes = (
            {"raw_text": RAW_JD + " Revised."},
            {"source_artifact_sha256": "artifact-b"},
            {"library_jd_id": 13},
            {"source_version_id_value": "version-b"},
            {"extraction_model_id": "other-model"},
        )
        for change in changes:
            values = {
                "source_type": "uploaded",
                "raw_text": RAW_JD,
                "title": "Engineer",
                "company": "Example",
                "library_jd_id": 12,
                "source_version_id_value": "version-a",
                "source_artifact_sha256": "artifact-a",
                "extraction_model_id": "test-model",
            }
            values.update(change)
            with self.subTest(change=change):
                self.assertNotEqual(
                    baseline,
                    phase9f_jd_input_fingerprint(**values),
                )

    def test_uploaded_snapshot_records_source_artifact_identity(self):
        snapshot = build_transient_exact_jd_snapshot(
            raw_text=RAW_JD,
            jd_profile=profile(),
            source_type="uploaded",
            source_filename="job.pdf",
            source_artifact_sha256="artifact-sha",
        )
        self.assertEqual(snapshot["source_artifact_sha256"], "artifact-sha")
        self.assertEqual(
            snapshot["semantic_identity"]["source"][
                "source_artifact_sha256"
            ],
            "artifact-sha",
        )

    def test_diagnostics_allowlist_contains_provenance_without_secrets(self):
        snapshot = build_transient_exact_jd_snapshot(
            raw_text=RAW_JD,
            jd_profile=profile(),
            source_type="uploaded",
            source_filename="job.pdf",
            source_artifact_sha256="artifact-sha",
            extraction_model_id="test-model",
            model_calls=[
                {
                    "model": "test-model",
                    "authorization": "Bearer diagnostic-secret",
                    "usage": {
                        "prompt_tokens": 1200,
                        "completion_tokens": 300,
                        "total_tokens": 1500,
                        "prompt_tokens_details": {
                            "cached_tokens": 200,
                        },
                    },
                    "response_cost_usd": 0.0042,
                }
            ],
        )
        snapshot["api_key"] = "diagnostic-secret"
        snapshot["source_url"] = (
            "https://example.test/job?token=diagnostic-secret"
        )
        receipt = {
            "analysis_snapshot_fingerprint": snapshot["snapshot_fingerprint"],
            "job_description_id": 42,
            "source_version_id": snapshot["source_version_id"],
            "created_new_job": False,
            "created_new_version": False,
            "needs_chroma_index": False,
            "chroma_indexing_attempted": False,
            "chroma_indexing_occurred": False,
            "authorization": "Bearer diagnostic-secret",
        }
        unchanged = deepcopy(snapshot)

        diagnostics = build_phase9f_analysis_diagnostics(
            snapshot,
            save_receipt=receipt,
        )
        rendered = phase9f_analysis_diagnostics_json(
            snapshot,
            save_receipt=receipt,
        )
        decoded = json.loads(rendered)

        self.assertEqual(snapshot, unchanged)
        self.assertEqual(decoded, diagnostics)
        self.assertEqual(diagnostics["source"]["mode"], "uploaded")
        self.assertEqual(
            diagnostics["source"]["uploaded_artifact_sha256"],
            "artifact-sha",
        )
        self.assertEqual(diagnostics["source"]["saved_jd_id"], 42)
        self.assertEqual(
            diagnostics["fingerprints"]["transient_snapshot"],
            snapshot["snapshot_fingerprint"],
        )
        self.assertEqual(
            diagnostics["format_version"],
            "phase9f-jd-intake-diagnostics-v3",
        )
        self.assertEqual(diagnostics["extraction"]["model"], "test-model")
        self.assertEqual(diagnostics["extraction"]["model_call_count"], 1)
        self.assertEqual(
            diagnostics["extraction"]["embedding_call_count"], 0
        )
        api_usage = diagnostics["extraction"]["api_usage"]
        self.assertEqual(api_usage["call_count"], 1)
        self.assertEqual(api_usage["costed_call_count"], 1)
        self.assertEqual(api_usage["prompt_tokens"], 1200)
        self.assertEqual(api_usage["cached_prompt_tokens"], 200)
        self.assertEqual(api_usage["completion_tokens"], 300)
        self.assertEqual(api_usage["total_tokens"], 1500)
        self.assertAlmostEqual(api_usage["estimated_cost_usd"], 0.0042)
        self.assertTrue(api_usage["cost_is_estimate"])
        self.assertEqual(
            diagnostics["most_recent_save"]["outcome"],
            "exact_existing_jd_version_reused",
        )
        lowered = rendered.lower()
        for forbidden in (
            "diagnostic-secret",
            "api_key",
            "authorization",
            "bearer",
            "source_url",
            "model_calls",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, lowered)

    def test_call_usage_summary_never_fabricates_missing_cost(self):
        summary = summarise_call_usage(
            [
                {
                    "usage": {
                        "prompt_tokens": 10,
                        "completion_tokens": 2,
                        "total_tokens": 12,
                    }
                }
            ]
        )
        self.assertEqual(summary["call_count"], 1)
        self.assertEqual(summary["costed_call_count"], 0)
        self.assertEqual(summary["uncosted_call_count"], 1)
        self.assertIsNone(summary["estimated_cost_usd"])
        self.assertEqual(summary["total_tokens"], 12)

    def test_exact_saved_profile_can_be_reused_for_pasted_intake_without_calls(self):
        stored_snapshot = build_transient_exact_jd_snapshot(
            raw_text=RAW_JD,
            jd_profile=profile(),
            source_type="saved",
            library_jd_id=42,
            saved_source_version_id="",
            model_calls=[],
        )
        saved = {
            "library_jd_id": 42,
            "raw_text": stored_snapshot["raw_text"],
            "raw_jd_sha256": stored_snapshot["raw_jd_sha256"],
            "source_version_id": stored_snapshot["source_version_id"],
            "jd_profile": stored_snapshot["jd_profile"],
            "source_url": "https://example.test/original",
        }

        reused = build_reused_exact_jd_snapshot(
            saved,
            source_type="pasted",
            title="Explicit AI Engineer",
            company="Explicit Company",
            location="Remote",
        )
        diagnostics = build_phase9f_analysis_diagnostics(reused)

        self.assertEqual(reused["source_type"], "pasted")
        self.assertEqual(reused["library_jd_id"], 42)
        self.assertEqual(reused["model_call_count"], 0)
        self.assertEqual(reused["embedding_call_count"], 0)
        self.assertTrue(reused["reused_exact_saved_version"])
        self.assertEqual(reused["job_title"], "Explicit AI Engineer")
        self.assertEqual(reused["company"], "Explicit Company")
        self.assertEqual(reused["location"], "Remote")
        self.assertEqual(
            reused["extraction_provenance"]["method"],
            "stored_exact_version_profile_reuse",
        )
        self.assertEqual(
            diagnostics["extraction"]["api_usage"]["call_count"],
            0,
        )
        self.assertTrue(
            diagnostics["extraction"]["reused_exact_saved_version"]
        )

    def test_meaningless_input_fails_closed(self):
        with self.assertRaises(Phase9FJDIntakeError):
            build_transient_exact_jd_snapshot(
                raw_text="too short",
                jd_profile=profile(),
                source_type="pasted",
            )

    def test_docx_and_pdf_extract_locally_without_ocr(self):
        with tempfile.TemporaryDirectory() as temp_name:
            docx_path = Path(temp_name) / "job.docx"
            document = Document()
            document.add_paragraph(RAW_JD)
            document.save(docx_path)
            docx_text = extract_job_description_file(
                filename=docx_path.name,
                content=docx_path.read_bytes(),
            )

            pdf = fitz.open()
            page = pdf.new_page()
            page.insert_textbox(
                fitz.Rect(40, 40, page.rect.width - 40, page.rect.height - 40),
                RAW_JD,
                fontsize=10,
            )
            pdf_bytes = pdf.tobytes()
            pdf.close()
            pdf_text = extract_job_description_file(
                filename="job.pdf",
                content=pdf_bytes,
            )

        self.assertIn("Junior AI Full-Stack Engineer", docx_text)
        self.assertIn("Junior AI Full-Stack Engineer", pdf_text)
        with self.assertRaises(Phase9FJDIntakeError):
            extract_job_description_file(filename="job.png", content=b"image")


if __name__ == "__main__":
    unittest.main()

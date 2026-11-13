"""No-write focused tests for Phase 9F exact selected-source visual tab."""
from __future__ import annotations

import hashlib
import sys
import types
import unittest
from unittest.mock import patch

from tailoring.phase9f_selected_base_visual_ui import (
    SelectedBasePreviewUnavailable, _verified_artifact_rows,
    validate_bound_visual_source, render_verified_source_pdf,
    render_selected_base_visual_tab,
)


def _artifact(kind="pdf", content=None):
    if content is None:
        content = b"%PDF-1.4\nconfirmed" if kind == "pdf" else b"PK\x03\x04confirmed"
    return {"artifact_type": kind, "artifact_bytes": content,
            "sha256": hashlib.sha256(content).hexdigest(),
            "byte_size": len(content), "provenance_label": "saved original"}


def _facts():
    fingerprint = "confirmed-source-fingerprint"
    selected = {
        "source_type": "base_resume", "source_id": "base-v8",
        "source_fingerprint": "version-fingerprint",
        "source_content_fingerprint": "content-fingerprint",
        "normalized_source_fingerprint": fingerprint,
        "source_display_name": "Base Technical V8",
    }
    decision = {
        "decision_fingerprint": "bound-decision",
        "starting_snapshot": {
            "starting_snapshot_fingerprint": "bound-snapshot",
            "source_identity": dict(selected),
        },
    }
    confirmation = {
        "confirmation_id": "confirmed-12",
        "phase9e_decision_fingerprint": "bound-decision",
        "starting_snapshot_fingerprint": "bound-snapshot",
    }
    bundle = {"source_type": "base_resume", "artifacts": [_artifact("pdf"), _artifact("docx")]}
    return dict(confirmation=confirmation, decision=decision, selected=selected, bundle=bundle)


class SelectedBaseVisualV1Tests(unittest.TestCase):
    def test_exact_frozen_source_prefers_existing_saved_pdf(self):
        result = validate_bound_visual_source(**_facts())
        self.assertEqual("pdf", result["format"])
        self.assertEqual("Base Technical V8", result["source_name"])
        self.assertEqual("confirmed-12", result["confirmation_id"])

    def test_missing_pdf_converts_source_docx_only(self):
        facts = _facts()
        facts["bundle"]["artifacts"] = [_artifact("docx")]
        result = validate_bound_visual_source(**facts)
        self.assertEqual("docx", result["format"])
        self.assertTrue(result["source_bytes"].startswith(b"PK"))

    def test_different_current_decision_is_rejected(self):
        facts = _facts()
        facts["decision"]["decision_fingerprint"] = "new-decision"
        with self.assertRaisesRegex(SelectedBasePreviewUnavailable, "decision"):
            validate_bound_visual_source(**facts)

    def test_different_source_id_is_rejected(self):
        facts = _facts()
        facts["decision"]["starting_snapshot"]["source_identity"]["source_id"] = "other"
        with self.assertRaisesRegex(SelectedBasePreviewUnavailable, "source_id"):
            validate_bound_visual_source(**facts)

    def test_foreign_source_type_is_rejected(self):
        facts = _facts()
        facts["bundle"]["source_type"] = "global_blueprint"
        with self.assertRaisesRegex(SelectedBasePreviewUnavailable, "source type"):
            validate_bound_visual_source(**facts)

    def test_original_source_hash_mismatch_blocks_preview(self):
        facts = _facts()
        facts["bundle"]["artifacts"][0]["sha256"] = "00"
        with self.assertRaisesRegex(SelectedBasePreviewUnavailable, "SHA-256"):
            validate_bound_visual_source(**facts)

    def test_two_pdf_candidates_are_ambiguous_and_blocked(self):
        facts = _facts()
        facts["bundle"]["artifacts"].append(_artifact("pdf"))
        with self.assertRaisesRegex(SelectedBasePreviewUnavailable, "ambiguous"):
            validate_bound_visual_source(**facts)

    def test_frozen_f_fitting_docx_must_match_exact_source_bytes(self):
        facts = _facts()
        execution = {"source_artifact": {"sha256": _artifact("docx")["sha256"],
                                          "byte_size": _artifact("docx")["byte_size"]}}
        self.assertEqual("pdf", validate_bound_visual_source(**facts, execution=execution)["format"])
        execution["source_artifact"]["sha256"] = "different"
        with self.assertRaisesRegex(SelectedBasePreviewUnavailable, "frozen Phase 9F fitting source"):
            validate_bound_visual_source(**facts, execution=execution)

    def test_valid_pdf_can_be_rasterized_in_temp_without_mutating_repo(self):
        mod = types.ModuleType("resume_builder.docx_projects_skills_replacer")
        observed = []
        def pdf_renderer(path, **kwargs):
            observed.append(path.read_bytes())
            self.assertFalse(kwargs["include_download"])
            return "<div>confirmed immutable image</div>"
        mod.pdf_to_preview_html = pdf_renderer
        mod._find_libreoffice_executable = lambda: None
        package = types.ModuleType("resume_builder")
        package.__path__ = []
        receipt = validate_bound_visual_source(**_facts())
        with patch.dict(sys.modules, {"resume_builder": package,
                                      "resume_builder.docx_projects_skills_replacer": mod}):
            html, pdf_bytes, method = render_verified_source_pdf(receipt)
        self.assertIn("confirmed immutable image", html)
        self.assertEqual(observed, [pdf_bytes])
        self.assertIn("Stored", method)

    def test_docx_preview_conversion_is_disposable_and_uses_exact_bytes(self):
        mod = types.ModuleType("resume_builder.docx_projects_skills_replacer")
        observed = []
        def pdf_renderer(path, **kwargs):
            self.assertTrue(path.is_file())
            self.assertFalse(kwargs["include_download"])
            return "<div>exact selected DOCX image</div>"
        mod.pdf_to_preview_html = pdf_renderer
        mod._find_libreoffice_executable = lambda: "soffice"
        package = types.ModuleType("resume_builder")
        package.__path__ = []
        facts = _facts()
        facts["bundle"]["artifacts"] = [_artifact("docx")]
        receipt = validate_bound_visual_source(**facts)
        def fake_run(argv, **kwargs):
            source_docx = __import__("pathlib").Path(argv[-1])
            observed.append(source_docx.read_bytes())
            (source_docx.parent / (source_docx.stem + ".pdf")).write_bytes(b"%PDF-1.4\nconverted")
            return types.SimpleNamespace(returncode=0)
        with patch.dict(sys.modules, {"resume_builder": package,
                                      "resume_builder.docx_projects_skills_replacer": mod}), \
             patch("tailoring.phase9f_selected_base_visual_ui.subprocess.run", side_effect=fake_run):
            html, pdf_bytes, method = render_verified_source_pdf(receipt)
        self.assertIn("exact selected DOCX image", html)
        self.assertEqual(observed, [receipt["source_bytes"]])
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
        self.assertIn("converted from exact", method)

    def test_selected_base_auto_loads_and_uses_exact_verified_artifact(self):
        class FakeSt:
            messages = []
            def caption(self, value): self.messages.append(value)
            def write(self, value): self.messages.append(value)
            def markdown(self, value, **kwargs): self.messages.append(value)
            def download_button(self, *args, **kwargs): pass
        from tailoring import phase9f_selected_base_visual_ui as module
        artifact={"source_name":"Selected V8", "confirmation_id":"a" * 32,
                  "source_bytes": b"verified", "format":"pdf"}
        with patch.object(module, "load_confirmed_visual_artifact", return_value=artifact) as load:
            with patch.object(module, "render_verified_source_pdf", return_value=("<img>", b"%PDF mock", "Verified")) as render:
                render_selected_base_visual_tab(FakeSt(), 12)
                load.assert_called_once_with(12)
                render.assert_called_once_with(artifact)


if __name__ == "__main__":
    unittest.main()

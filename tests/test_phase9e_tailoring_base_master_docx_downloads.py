from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import fitz

from analysis_stability.stable_evidence_scoring import SCORING_VERSION
from tailoring.phase9e_tailoring_base_visual_preview import (
    PHASE9E_TAILORING_BASE_VISUAL_PREVIEW_VERSION,
    build_tailoring_base_visual_preview,
)


ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "tailoring" / "phase9e_blueprint_selection_ui.py"


class Phase9ETailoringBaseMasterDocxDownloadTests(unittest.TestCase):
    def _write_pdf(self, path: Path) -> None:
        document = fitz.open()
        page = document.new_page()
        page.insert_text((72, 72), "Formatted resume preview")
        document.save(str(path))
        document.close()

    def test_ui_only_upgrade_keeps_scoring_identity(self):
        self.assertEqual(
            SCORING_VERSION,
            "stable-evidence-v1.14-phase6d20",
        )
        self.assertEqual(
            PHASE9E_TAILORING_BASE_VISUAL_PREVIEW_VERSION,
            "phase9e-tailoring-base-visual-preview-v3",
        )

    def test_master_original_docx_is_converted_for_visual_preview(self):
        source_bytes = b"PK\\x03\\x04master-docx"

        def fake_artifact(master_version_id: str, kind: str):
            self.assertEqual(master_version_id, "master-123")
            if kind == "preview_pdf":
                return None
            if kind == "original":
                return {
                    "artifact_bytes": source_bytes,
                    "filename": "Darren Master Resume.docx",
                    "media_type": (
                        "application/vnd.openxmlformats-officedocument."
                        "wordprocessingml.document"
                    ),
                }
            return None

        def fake_convert(docx_path: Path):
            pdf_path = Path(docx_path).with_suffix(".pdf")
            self._write_pdf(pdf_path)
            return pdf_path

        with patch(
            "tailoring.phase9e_tailoring_base_visual_preview."
            "get_global_master_resume_artifact",
            side_effect=fake_artifact,
        ), patch(
            "tailoring.phase9e_tailoring_base_visual_preview."
            "convert_docx_to_pdf_if_possible",
            side_effect=fake_convert,
        ):
            preview = build_tailoring_base_visual_preview(
                selected_source="base_resume",
                resume_text="fallback",
                application_id=149,
                base_resume_starting_snapshot={
                    "source_identity": {
                        "source_id": "master-123",
                    }
                },
            )

        self.assertEqual(
            preview["mode"],
            "converted_master_docx",
        )
        self.assertEqual(
            preview["source_kind"],
            "master_original_docx",
        )
        self.assertIn(
            "data:image/png;base64,",
            preview["html"],
        )
        self.assertEqual(
            preview["download_bytes"],
            source_bytes,
        )
        self.assertEqual(
            preview["download_name"],
            "Darren Master Resume.docx",
        )

    def test_application_source_exposes_original_docx_download(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            saved_docx = root / "app_149_original.docx"
            source_bytes = b"PK\\x03\\x04application-docx"
            saved_docx.write_bytes(source_bytes)

            def fake_convert(docx_path: Path):
                pdf_path = Path(docx_path).with_suffix(".pdf")
                self._write_pdf(pdf_path)
                return pdf_path

            with patch(
                "tailoring.phase9e_tailoring_base_visual_preview."
                "get_latest_saved_docx_for_application",
                return_value=saved_docx,
            ), patch(
                "tailoring.phase9e_tailoring_base_visual_preview."
                "convert_docx_to_pdf_if_possible",
                side_effect=fake_convert,
            ):
                preview = build_tailoring_base_visual_preview(
                    selected_source="original_resume",
                    resume_text="normalized scoring text",
                    application_id=149,
                )

        self.assertEqual(
            preview["download_bytes"],
            source_bytes,
        )
        self.assertEqual(
            preview["download_name"],
            saved_docx.name,
        )
        self.assertEqual(
            preview["download_label"],
            "Download application source résumé",
        )

    def test_master_preview_pdf_still_downloads_original_source_when_available(self):
        original_bytes = b"PK\\x03\\x04master-source"
        with tempfile.TemporaryDirectory() as name:
            pdf_path = Path(name) / "preview.pdf"
            self._write_pdf(pdf_path)
            preview_bytes = pdf_path.read_bytes()

        def fake_artifact(master_version_id: str, kind: str):
            if kind == "preview_pdf":
                return {
                    "artifact_bytes": preview_bytes,
                    "filename": "master-preview.pdf",
                    "media_type": "application/pdf",
                }
            if kind == "original":
                return {
                    "artifact_bytes": original_bytes,
                    "filename": "master-source.docx",
                    "media_type": (
                        "application/vnd.openxmlformats-officedocument."
                        "wordprocessingml.document"
                    ),
                }
            return None

        with patch(
            "tailoring.phase9e_tailoring_base_visual_preview."
            "get_global_master_resume_artifact",
            side_effect=fake_artifact,
        ):
            preview = build_tailoring_base_visual_preview(
                selected_source="base_resume",
                resume_text="fallback",
                base_resume_starting_snapshot={
                    "source_identity": {
                        "source_id": "master-123",
                    }
                },
            )

        self.assertEqual(
            preview["mode"],
            "stored_master_pdf",
        )
        self.assertEqual(
            preview["download_bytes"],
            original_bytes,
        )
        self.assertEqual(
            preview["download_name"],
            "master-source.docx",
        )

    def test_ui_renders_download_button_for_available_source_artifact(self):
        source = UI.read_text(encoding="utf-8")
        self.assertIn("st.download_button(", source)
        self.assertIn(
            'f"phase9e_tailoring_base_download_"',
            source,
        )
        self.assertIn(
            '"**Download artifact:** "',
            source,
        )


if __name__ == "__main__":
    unittest.main()

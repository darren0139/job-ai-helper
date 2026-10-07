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


class Phase9ETailoringBaseOriginalDocxPreviewTests(unittest.TestCase):
    def _write_pdf(self, path: Path) -> None:
        document = fitz.open()
        page = document.new_page()
        page.insert_text(
            (72, 72),
            "Original application resume formatting",
        )
        document.save(str(path))
        document.close()

    def test_ui_only_upgrade_keeps_scoring_identity(self):
        self.assertEqual(
            SCORING_VERSION,
            "stable-evidence-v1.12-phase6d18",
        )
        self.assertEqual(
            PHASE9E_TAILORING_BASE_VISUAL_PREVIEW_VERSION,
            "phase9e-tailoring-base-visual-preview-v3",
        )

    def test_application_source_prefers_saved_original_docx(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            saved_docx = root / "app_149_original_resume.docx"
            saved_docx.write_bytes(b"PK\\x03\\x04placeholder-docx")
            converted_pdf = root / "converted.pdf"
            self._write_pdf(converted_pdf)

            with patch(
                "tailoring.phase9e_tailoring_base_visual_preview."
                "get_latest_saved_docx_for_application",
                return_value=saved_docx,
            ), patch(
                "tailoring.phase9e_tailoring_base_visual_preview."
                "convert_docx_to_pdf_if_possible",
                return_value=converted_pdf,
            ):
                preview = build_tailoring_base_visual_preview(
                    selected_source="original_resume",
                    resume_text=(
                        "Software Engineer Intern\\n"
                        "Built backend integrations."
                    ),
                    application_id=149,
                )

            self.assertEqual(
                preview["mode"],
                "saved_application_docx",
            )
            self.assertEqual(
                preview["source_kind"],
                "application_saved_docx",
            )
            self.assertEqual(
                preview["artifact_name"],
                saved_docx.name,
            )
            self.assertIn(
                "data:image/png;base64,",
                preview["html"],
            )
            self.assertIn(
                "deterministic alignment still uses the normalized text",
                preview["note"],
            )
            self.assertFalse(converted_pdf.exists())

    def test_application_source_falls_back_when_saved_docx_missing(self):
        with patch(
            "tailoring.phase9e_tailoring_base_visual_preview."
            "get_latest_saved_docx_for_application",
            return_value=None,
        ):
            preview = build_tailoring_base_visual_preview(
                selected_source="original_resume",
                resume_text=(
                    "Software Engineer Intern\\n"
                    "Built backend integrations."
                ),
                application_id=149,
            )

        self.assertEqual(
            preview["mode"],
            "derived_scoring_text",
        )
        self.assertEqual(
            preview["source_kind"],
            "exact_scoring_text",
        )
        self.assertIn(
            "data:image/png;base64,",
            preview["html"],
        )

    def test_master_behavior_still_uses_existing_path(self):
        with patch(
            "tailoring.phase9e_tailoring_base_visual_preview."
            "_stored_master_pdf_preview",
            return_value={
                "html": "<img />",
                "mode": "stored_master_pdf",
                "source_kind": "master_preview_pdf",
                "note": "stored",
            },
        ):
            preview = build_tailoring_base_visual_preview(
                selected_source="base_resume",
                resume_text="fallback",
                application_id=149,
                base_resume_starting_snapshot={
                    "source_identity": {
                        "source_id": "master-1",
                    }
                },
            )

        self.assertEqual(
            preview["mode"],
            "stored_master_pdf",
        )

    def test_ui_passes_application_id_and_shows_artifact_name(self):
        source = UI.read_text(encoding="utf-8")
        self.assertIn(
            "application_id=application_id,",
            source,
        )
        self.assertIn(
            '"**Visual artifact:** "',
            source,
        )


if __name__ == "__main__":
    unittest.main()

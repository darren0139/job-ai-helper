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


REPO_ROOT = Path(__file__).resolve().parents[1]
UI_PATH = REPO_ROOT / "tailoring" / "phase9e_blueprint_selection_ui.py"


class Phase9ETailoringBaseVisualPreviewTests(unittest.TestCase):
    def test_ui_only_upgrade_keeps_scoring_identity(self):
        self.assertEqual(
            SCORING_VERSION,
            "stable-evidence-v1.13-phase6d20",
        )
        self.assertEqual(
            PHASE9E_TAILORING_BASE_VISUAL_PREVIEW_VERSION,
            "phase9e-tailoring-base-visual-preview-v3",
        )

    def test_application_source_uses_derived_scoring_text_visual(self):
        preview = build_tailoring_base_visual_preview(
            selected_source="original_resume",
            resume_text=(
                "Software Engineer Intern\n"
                "Built backend API integrations with Python.\n"
                "PROJECTS\n"
                "Built a C++ asset manager."
            ),
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
        self.assertIn(
            "not the original uploaded document formatting",
            preview["note"],
        )

    def test_master_prefers_stored_preview_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = Path(tmp) / "master.pdf"
            document = fitz.open()
            page = document.new_page()
            page.insert_text((72, 72), "Master resume visual")
            document.save(str(pdf_path))
            document.close()
            pdf_bytes = pdf_path.read_bytes()

        def fake_artifact(master_version_id: str, kind: str):
            self.assertEqual(master_version_id, "master-123")
            if kind == "preview_pdf":
                return {
                    "artifact_bytes": pdf_bytes,
                    "filename": "master-preview.pdf",
                    "media_type": "application/pdf",
                }
            return None

        with patch(
            "tailoring.phase9e_tailoring_base_visual_preview."
            "get_global_master_resume_artifact",
            side_effect=fake_artifact,
        ):
            preview = build_tailoring_base_visual_preview(
                selected_source="base_resume",
                resume_text="PROJECTS\nFallback text",
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
            preview["source_kind"],
            "master_preview_pdf",
        )
        self.assertIn(
            "data:image/png;base64,",
            preview["html"],
        )

    def test_master_falls_back_to_derived_visual_without_pdf(self):
        with patch(
            "tailoring.phase9e_tailoring_base_visual_preview."
            "get_global_master_resume_artifact",
            return_value=None,
        ):
            preview = build_tailoring_base_visual_preview(
                selected_source="base_resume",
                resume_text=(
                    "EDUCATION\n"
                    "Bachelor of Science\n"
                    "PROJECTS\n"
                    "Built a Streamlit application."
                ),
                base_resume_starting_snapshot={
                    "source_identity": {
                        "source_id": "master-456",
                    }
                },
            )

        self.assertEqual(
            preview["mode"],
            "derived_scoring_text",
        )
        self.assertIn(
            "data:image/png;base64,",
            preview["html"],
        )

    def test_ui_has_visual_scoring_and_details_tabs(self):
        source = UI_PATH.read_text(encoding="utf-8")
        self.assertIn(
            '"Visual résumé"',
            source,
        )
        self.assertIn(
            '"Exact scoring text"',
            source,
        )
        self.assertIn(
            '"Source details"',
            source,
        )
        self.assertIn(
            "build_tailoring_base_visual_preview(",
            source,
        )
        self.assertIn(
            "unsafe_allow_html=True",
            source,
        )


if __name__ == "__main__":
    unittest.main()

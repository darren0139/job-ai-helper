from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import fitz

from resume_builder.docx_projects_skills_replacer import (
    pdf_to_preview_pngs,
)
from tailoring.deterministic_bullet_allocation import (
    BULLET_ALLOCATION_VERSION,
    LEAD_BULLET_POLICY_VERSION,
    _selected_display_order_key,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class PdfPreviewRegressionTests(unittest.TestCase):
    def test_pdf_preview_pages_render_as_png_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = Path(tmp) / "preview.pdf"
            document = fitz.open()
            page = document.new_page()
            page.insert_text((72, 72), "Resume preview")
            document.save(str(pdf_path))
            document.close()

            pages = pdf_to_preview_pngs(
                pdf_path,
                zoom=1.0,
                max_pages=3,
            )

        self.assertEqual(len(pages), 1)
        self.assertTrue(pages[0].startswith(b"\x89PNG\r\n\x1a\n"))


class LeadBulletPresentationRegressionTests(unittest.TestCase):
    def test_first_canonical_bullet_is_first_when_selected(self) -> None:
        selected = [
            {
                "bullet_index": 1,
                "evidence_priority": 1,
                "bullet_id": "bullet_relevant",
            },
            {
                "bullet_index": 0,
                "evidence_priority": 99,
                "bullet_id": "bullet_lead",
            },
            {
                "bullet_index": 2,
                "evidence_priority": 2,
                "bullet_id": "bullet_other",
            },
        ]
        ordered = sorted(
            selected,
            key=_selected_display_order_key,
        )
        self.assertEqual(ordered[0]["bullet_id"], "bullet_lead")
        self.assertEqual(
            [row["bullet_id"] for row in ordered[1:]],
            ["bullet_relevant", "bullet_other"],
        )

    def test_policy_versions_are_explicit(self) -> None:
        self.assertEqual(
            BULLET_ALLOCATION_VERSION,
            "phase6b2-deterministic-bullet-allocation-v5",
        )
        self.assertEqual(
            LEAD_BULLET_POLICY_VERSION,
            "phase6b2-first-canonical-lead-v1",
        )


class TailoringUiStructureRegressionTests(unittest.TestCase):
    def test_update_scope_controls_live_before_project_controls(self) -> None:
        source = (REPO_ROOT / "app.py").read_text(encoding="utf-8")
        scope_index = source.index(
            "render_tailoring_section_update_scope("
        )
        max_projects_index = source.index(
            "max_projects = st.slider(",
            scope_index,
        )
        self.assertLess(scope_index, max_projects_index)
        self.assertIn(
            "update_scope_dirty",
            source[scope_index:max_projects_index + 2000],
        )

    def test_approval_scope_is_read_only(self) -> None:
        source = (
            REPO_ROOT / "tailoring" / "generation_controls_ui.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"Update Projects"', source)
        self.assertIn('"Update Skills"', source)
        self.assertIn('"Save Update Scope"', source)
        self.assertNotIn('"Lock approved Projects"', source)
        self.assertNotIn('"Lock approved Skills"', source)
        self.assertNotIn('"Save Section Locks"', source)
        self.assertIn(
            "Change this scope in Tailor Résumé Content before generating.",
            source,
        )

    def test_evidence_page_explains_lead_bullet_rule(self) -> None:
        source = (REPO_ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn(
            "The first canonical bullet is the project lead",
            source,
        )
        self.assertIn("**Lead:** {cleaned_line}", source)

    def test_app_uses_png_pdf_preview_not_native_iframe(self) -> None:
        source = (REPO_ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("pdf_to_preview_html(", source)
        self.assertNotIn(
            "pdf_preview_pages = pdf_to_preview_pngs(",
            source,
        )
        self.assertNotIn(
            "pdf_to_iframe_html(pdf_preview_path",
            source,
        )

    def test_generation_cache_contract_is_bumped(self) -> None:
        source = (
            REPO_ROOT
            / "tailoring"
            / "tailoring_generation_fingerprint.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            '"generator_contract_version": "phase7-projects-skills-cache-v3"',
            source,
        )


if __name__ == "__main__":
    unittest.main()

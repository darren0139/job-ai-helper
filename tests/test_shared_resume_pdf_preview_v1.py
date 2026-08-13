from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import fitz

from llm import get_call_ledger, reset_call_ledger
from resume_builder.docx_projects_skills_replacer import (
    pdf_to_iframe_html,
    pdf_to_preview_html,
)
from tailoring.phase9e1_resume_workspace_ui import _render_pdf_preview


REPO_ROOT = Path(__file__).resolve().parents[1]


class SharedPdfPreviewTests(unittest.TestCase):
    def _make_pdf(self, directory: str) -> Path:
        path = Path(directory) / "resume-preview.pdf"
        document = fitz.open()
        page = document.new_page()
        page.insert_text((72, 72), "Resume preview")
        document.save(str(path))
        document.close()
        return path

    def test_shared_preview_rasterizes_centers_and_offers_download(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            html = pdf_to_preview_html(self._make_pdf(tmp))

        self.assertIn("data:image/png;base64,", html)
        self.assertIn("data:application/pdf;base64,", html)
        self.assertIn('download="resume-preview.pdf"', html)
        self.assertIn("justify-content:center", html)
        self.assertIn("max-width:820px", html)
        self.assertNotIn("<iframe", html.lower())

    def test_compatibility_wrapper_no_longer_emits_iframe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            html = pdf_to_iframe_html(self._make_pdf(tmp), height=800)

        self.assertIn("data:image/png;base64,", html)
        self.assertIn("Download PDF", html)
        self.assertNotIn("<iframe", html.lower())

    def test_workspace_renderer_uses_shared_preview_without_duplicate_link(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = self._make_pdf(tmp)
            with patch(
                "tailoring.phase9e1_resume_workspace_ui.st.markdown"
            ) as markdown:
                _render_pdf_preview({"pdf_path": str(pdf_path)})

        markdown.assert_called_once()
        rendered = markdown.call_args.args[0]
        self.assertIn("data:image/png;base64,", rendered)
        self.assertNotIn("data:application/pdf;base64,", rendered)
        self.assertTrue(
            markdown.call_args.kwargs.get("unsafe_allow_html")
        )

    def test_all_workspace_preview_routes_share_one_safe_renderer(self) -> None:
        source = (
            REPO_ROOT
            / "tailoring"
            / "phase9e1_resume_workspace_ui.py"
        ).read_text(encoding="utf-8")

        self.assertEqual(source.count("_render_pdf_preview("), 4)
        self.assertIn('"Preview current application result"', source)
        self.assertIn('"Preview selected résumé"', source)
        self.assertIn('"Preview historical résumé"', source)
        self.assertIn("pdf_to_preview_html(", source)
        self.assertNotIn("st.iframe(", source)
        self.assertNotIn('getattr(st, "pdf", None)', source)

    def test_build_and_fit_uses_shared_renderer_and_keeps_docx_download(
        self,
    ) -> None:
        source = (REPO_ROOT / "app.py").read_text(encoding="utf-8")

        self.assertIn("pdf_to_preview_html(", source)
        self.assertNotIn(
            "pdf_preview_pages = pdf_to_preview_pngs(",
            source,
        )
        self.assertIn('"Download Tailored Resume Copy"', source)

    def test_previewing_makes_no_model_or_embedding_calls(self) -> None:
        reset_call_ledger()
        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = self._make_pdf(tmp)
            with (
                patch(
                    "litellm.completion",
                    side_effect=AssertionError("model call attempted"),
                ),
                patch(
                    "litellm.embedding",
                    side_effect=AssertionError("embedding call attempted"),
                ),
            ):
                html = pdf_to_preview_html(pdf_path)

        self.assertIn("data:image/png;base64,", html)
        self.assertEqual(get_call_ledger(), [])


if __name__ == "__main__":
    unittest.main()

"""Focused source-format/Auto-header regressions; no paid API calls or DB writes."""
from __future__ import annotations

import copy
import unittest
from pathlib import Path

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.shared import Pt

from resume_builder.docx_projects_skills_replacer import (
    _auto_inline_project_header_budget_allows,
    replace_skills_section,
)


def _new_source(*, style_name: str, with_list: bool = False) -> Document:
    doc = Document()
    doc.add_heading("EDUCATION", 1)
    doc.add_paragraph("Original education content remains unchanged")
    doc.add_heading("WORK EXPERIENCE", 1)
    doc.add_paragraph("Original work experience remains unchanged")
    doc.add_heading("SKILLS", 1)
    if style_name not in doc.styles:
        doc.styles.add_style(style_name, WD_STYLE_TYPE.PARAGRAPH)
    p = doc.add_paragraph(style=style_name)
    p.paragraph_format.line_spacing = 1.15
    p.paragraph_format.space_after = Pt(0.5)
    p.add_run("Programming: Python, C++")
    return doc


class SourceFormatPreservationV1Tests(unittest.TestCase):
    def test_custom_v8_like_nonbullet_style_is_preserved(self):
        source = _new_source(style_name="Resume Skill")
        preserved = [p.text for p in source.paragraphs if p.text.startswith("Original")]
        replace_skills_section(source, {"skill_lines": [
            {"category": "Programming", "items": ["Python", "C++"]},
            {"category": "Tools", "items": ["Git"]},
        ]})
        rows = [p for p in source.paragraphs if p.text.startswith(("Programming:", "Tools:"))]
        self.assertEqual(len(rows), 2)
        self.assertEqual([p.style.name for p in rows], ["Resume Skill", "Resume Skill"])
        self.assertTrue(all(p.paragraph_format.line_spacing == 1.15 for p in rows))
        self.assertTrue(all(p._p.pPr is None or p._p.pPr.numPr is None for p in rows))
        self.assertEqual([p.text for p in source.paragraphs if p.text.startswith("Original")], preserved)

    def test_v6_like_normal_style_and_spacing_are_preserved(self):
        doc = _new_source(style_name="Normal")
        replace_skills_section(doc, {"skill_lines": [{"category": "AI & Data", "items": ["RAG"]}]})
        p = next(p for p in doc.paragraphs if p.text.startswith("AI & Data:"))
        self.assertEqual(p.style.name, "Normal")
        self.assertEqual(p.paragraph_format.line_spacing, 1.15)
        self.assertAlmostEqual(p.paragraph_format.space_after.pt, 0.5)

    def test_existing_bullet_style_remains_bulleted(self):
        doc = _new_source(style_name="List Bullet", with_list=True)
        replace_skills_section(doc, {"skill_lines": [{"category": "Tools", "items": ["Docker"]}]})
        p = next(p for p in doc.paragraphs if p.text.startswith("Tools:"))
        self.assertEqual(p.style.name, "List Bullet")

    def test_no_template_does_not_invent_list_bullet(self):
        doc = Document()
        doc.add_heading("SKILLS", 1)
        replace_skills_section(doc, {"skill_lines": [{"category": "Tools", "items": ["Docker"]}]})
        p = next(p for p in doc.paragraphs if p.text.startswith("Tools:"))
        self.assertNotEqual(p.style.name, "List Bullet")

    def test_auto_inline_guard_rejects_long_headers(self):
        app12 = {"recommended_projects": [{
            "title": "RequestFlow — IT Service Request Tracker",
            "resume_header_tools": ["Python", "TypeScript", "React", "FastAPI", "Docker", "Kubernetes"],
            "resume_header_context": ["Individual Project"],
            "period": "June 2026 – Aug 2026",
        }]}
        self.assertFalse(_auto_inline_project_header_budget_allows(app12, metadata_style="pipes"))
        short = {"recommended_projects": [{"title": "QueryAI", "period": "2025"}]}
        self.assertTrue(_auto_inline_project_header_budget_allows(short, metadata_style="pipes"))
        self.assertTrue(_auto_inline_project_header_budget_allows(None, metadata_style="pipes"))


if __name__ == "__main__":
    unittest.main()

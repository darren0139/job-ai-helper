# Formatting source-template and half-point controls; no provider calls.
from __future__ import annotations
import math
import unittest
from pathlib import Path

class FormattingSourceDecimalV1(unittest.TestCase):
    def test_half_point_setting_and_integer_compatibility(self):
        from database.phase9f_tailoring_execution_manager import _half_point_setting, Phase9FFExecutionError
        self.assertEqual(_half_point_setting(4.5, name="project_spacing_pt"), 4.5)
        self.assertEqual(_half_point_setting(10, name="project_spacing_pt"), 10)
        self.assertIsInstance(_half_point_setting(10.0, name="project_spacing_pt"), int)
        for bad in (-1, 20.5, 3.25, None, True, float("nan"), float("inf")):
            with self.subTest(bad=bad), self.assertRaises(Phase9FFExecutionError):
                _half_point_setting(bad, name="project_spacing_pt")

    def test_fit_settings_accept_source_and_decimals(self):
        from database.phase9f_tailoring_execution_manager import _canonical_fit_settings
        result = _canonical_fit_settings({"spacing_mode": "source_template", "project_spacing_pt": 4.5, "after_projects_spacing_pt": 7.5})
        self.assertEqual(result["spacing_mode"], "source_template")
        self.assertEqual(result["project_spacing_pt"], 4.5)
        self.assertEqual(result["after_projects_spacing_pt"], 7.5)
        legacy = _canonical_fit_settings({"spacing_mode":"paragraph_spacing", "project_spacing_pt":10, "after_projects_spacing_pt":10})
        self.assertEqual(legacy["project_spacing_pt"], 10)
        self.assertIsInstance(legacy["project_spacing_pt"], int)

    def test_docx_template_mode_keeps_source_title_spacing(self):
        from docx import Document
        from docx.shared import Pt
        from resume_builder.docx_projects_skills_replacer import replace_projects_section
        doc = Document()
        doc.add_paragraph("PROJECTS")
        old_title = doc.add_paragraph("Old Example Project")
        old_title.paragraph_format.space_before = Pt(3.5)
        old_bullet = doc.add_paragraph("• did work")
        old_bullet.paragraph_format.space_after = Pt(2.5)
        doc.add_paragraph("SKILLS")
        doc.add_paragraph("Python")
        payload = {"recommended_projects": [{"title":"Replacement Project", "draft_bullets":["Replaced work"]}]}
        replace_projects_section(doc,payload,max_projects=1,max_bullets_per_project=1,spacing_mode="source_template",project_spacing_pt=10,after_projects_spacing_pt=10)
        heading = [p for p in doc.paragraphs if "Replacement Project" in p.text]
        self.assertEqual(len(heading),1)
        self.assertEqual(heading[0].paragraph_format.space_before,Pt(3.5))
        bullets = [p for p in doc.paragraphs if "Replaced work" in p.text]
        self.assertEqual(len(bullets),1)
        self.assertEqual(bullets[0].paragraph_format.space_after,Pt(2.5))

if __name__ == "__main__":
    unittest.main()

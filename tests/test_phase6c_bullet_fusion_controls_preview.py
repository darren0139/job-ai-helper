from __future__ import annotations

import inspect
import unittest
from pathlib import Path

from resume_builder.docx_projects_skills_replacer import (
    generate_tailored_resume_copy_fit_one_page,
    prepare_fitting_input_snapshot,
)


class Phase6CBulletFusionControlsPreviewTests(unittest.TestCase):
    def test_fusion_defaults_on_for_direct_fitter(self):
        generate_signature = inspect.signature(
            generate_tailored_resume_copy_fit_one_page
        )
        prepare_signature = inspect.signature(
            prepare_fitting_input_snapshot
        )
        self.assertIs(
            generate_signature.parameters["allow_bullet_fusion"].default,
            True,
        )
        self.assertIs(
            prepare_signature.parameters["allow_bullet_fusion"].default,
            True,
        )

    def test_app_exposes_default_on_fusion_control_and_comparison_preview(self):
        app = Path("app.py").read_text(encoding="utf-8")
        self.assertIn('"Allow safe bullet fusion"', app)
        self.assertIn('"allow_bullet_fusion"', app)
        self.assertIn('"Before fitting"', app)
        self.assertIn('"After fitting"', app)
        self.assertIn('"before_fitting_pdf_path"', app)

    def test_phase9f_canonical_fit_settings_include_fusion(self):
        manager = Path(
            "database/phase9f_tailoring_execution_manager.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            '"allow_bullet_fusion": bool(',
            manager,
        )
        self.assertIn(
            'allow_bullet_fusion=canonical_fit["allow_bullet_fusion"]',
            manager,
        )


if __name__ == "__main__":
    unittest.main()

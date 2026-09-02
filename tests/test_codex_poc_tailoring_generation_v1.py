"""Regressions for Codex tailoring-generation routing v1."""

import unittest
from pathlib import Path


class CodexTailoringGenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Path("app.py").read_text(encoding="utf-8")
        cls.projects = Path("tailoring/project_section_tailor.py").read_text(encoding="utf-8")
        cls.skills = Path("tailoring/skills_section_tailor.py").read_text(encoding="utf-8")

    def test_projects_route_all_semantic_calls(self):
        self.assertIn("backend: str | None = None,", self.projects)
        self.assertEqual(self.projects.count("backend=backend,"), 3)
        for operation in (
            "tailor-project-scoring",
            "tailor-project-scoring-retry",
            "tailor-project-bullets",
        ):
            self.assertIn(f'operation="{operation}"', self.projects)

    def test_skills_routes_semantic_call(self):
        self.assertIn("backend: str | None = None,", self.skills)
        self.assertEqual(self.skills.count("backend=backend,"), 1)
        self.assertIn('operation="tailor-skills"', self.skills)

    def test_app_passes_selected_backend(self):
        self.assertEqual(self.app.count("tailor_projects_section("), 2)
        self.assertEqual(self.app.count("tailor_skills_section("), 2)
        self.assertGreaterEqual(self.app.count("backend=analysis_backend,"), 8)

    def test_generation_cache_separates_api_and_codex(self):
        for kind in ("projects_skills", "projects", "skills"):
            start = self.app.index(f'generation_kind="{kind}",')
            window = self.app[start:start + 500]
            self.assertIn(
                "model_id=_analysis_backend_model_id(analysis_backend),",
                window,
            )

    def test_codex_generation_has_zero_provider_api_usage(self):
        self.assertIn("def record_semantic_backend_usage(", self.app)
        self.assertIn(
            "Codex semantic generation completed; no provider API billing calls",
            self.app,
        )

    def test_ui_explains_backend_scope(self):
        self.assertIn(
            "Codex applies to Analyze Resume and Projects/Skills generation.",
            self.app,
        )
        self.assertIn(
            '"API model for cover letters / remaining generation"',
            self.app,
        )
        self.assertIn(
            "disabled=(analysis_backend == AI_BACKEND_CODEX),",
            self.app,
        )

    def test_fit_remains_deterministic(self):
        self.assertIn("generate_tailored_resume_copy_fit_one_page(", self.app)
        self.assertIn('generation_kind="fit_only"', self.app)
        self.assertIn('model_id="deterministic-local-fit"', self.app)


if __name__ == "__main__":
    unittest.main()

"""Regressions for Codex backend provenance/debug clarity v2."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path


class CodexBackendProvenanceV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app_path = Path("app.py")
        cls.app = cls.app_path.read_text(encoding="utf-8")

    def test_app_parses(self) -> None:
        ast.parse(self.app, filename=str(self.app_path))

    def test_tailoring_provenance_is_persisted_in_existing_json(self) -> None:
        self.assertTrue(
            (
                'persisted_generation_settings["backend_provenance"] ='
                in self.app
            )
            or (
                "def _merge_tailoring_generation_backend_provenance("
                in self.app
                and 'persisted_settings["backend_provenance"] = provenance'
                in self.app
            ),
            (
                "Backend provenance must be persisted directly or through "
                "the v3 provenance merge helper."
            ),
        )
        self.assertIn(
            "generation_settings=persisted_generation_settings,",
            self.app,
        )
        self.assertIn('"semantic_backend": backend,', self.app)
        self.assertIn(
            '"semantic_model": _analysis_backend_model_id(backend),',
            self.app,
        )

    def test_fit_provenance_is_deterministic(self) -> None:
        self.assertIn('if kind == "fit_only":', self.app)
        self.assertIn(
            '"execution_backend": "deterministic-python",',
            self.app,
        )
        self.assertIn('"semantic_backend": "none",', self.app)
        self.assertIn(
            '"fit_backend": "deterministic-python",',
            self.app,
        )

    def test_debug_meta_separates_configured_api_from_actual_backends(self) -> None:
        for marker in (
            '"configured_api_model": active_model,',
            '"active_model_note": (',
            '"analysis_backend": recorded_analysis_backend,',
            '"analysis_backend_model": recorded_analysis_backend_model,',
            '"tailoring_backend": selected_tailoring_backend,',
            '"tailoring_backend_model": selected_tailoring_backend_model,',
            '"tailoring_backend_note": (',
        ):
            self.assertIn(marker, self.app)

    def test_saved_generation_rows_expose_provenance(self) -> None:
        for marker in (
            '"execution_backend": row_backend.get(',
            '"semantic_backend": row_backend.get(',
            '"semantic_model": row_backend.get(',
            '"fit_backend": row_backend.get(',
            '"backend_provenance_status": row_backend.get(',
        ):
            self.assertIn(marker, self.app)

    def test_old_semantic_generations_are_not_guessed(self) -> None:
        self.assertIn('"unknown_legacy"', self.app)
        self.assertIn('"legacy_missing"', self.app)

    def test_filename_is_backend_neutral(self) -> None:
        self.assertIn(
            'f"app_{app_label}_debug_bundle_{timestamp}.json"',
            self.app,
        )
        tree = ast.parse(self.app)
        bundle_fn = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "create_full_debug_bundle"
        )
        block = "\n".join(
            self.app.splitlines()[
                bundle_fn.lineno - 1: bundle_fn.end_lineno
            ]
        )
        self.assertNotIn("model_slug", block)

    def test_no_db_schema_change(self) -> None:
        self.assertNotIn(
            "backend_provenance TEXT",
            self.app,
        )


if __name__ == "__main__":
    unittest.main()

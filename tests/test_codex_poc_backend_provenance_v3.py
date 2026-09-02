"""Regression tests for backend provenance preservation v3."""
from __future__ import annotations

import ast
import unittest
from copy import deepcopy
from pathlib import Path


class BackendProvenanceV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app_path = Path("app.py")
        cls.app = cls.app_path.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.app, filename=str(cls.app_path))

    def _fn(self, name: str) -> ast.FunctionDef:
        matches = [
            node for node in self.tree.body
            if isinstance(node, ast.FunctionDef) and node.name == name
        ]
        self.assertEqual(len(matches), 1)
        return matches[0]

    def _merge(self):
        node = self._fn("_merge_tailoring_generation_backend_provenance")
        mod = ast.Module(body=[node], type_ignores=[])
        ast.fix_missing_locations(mod)
        ns = {
            "deepcopy": deepcopy,
            "_SEMANTIC_TAILORING_GENERATION_KINDS": {
                "projects_skills", "projects", "skills"
            },
            "_tailoring_generation_backend_provenance": lambda kind: {
                "provenance_version": "test",
                "execution_backend": "codex",
                "semantic_backend": "codex",
                "semantic_model": "codex:test",
                "fit_backend": "not_applicable",
            },
        }
        exec(compile(mod, "<merge-helper>", "exec"), ns)
        return ns["_merge_tailoring_generation_backend_provenance"]

    def test_fit_preserves_codex_semantic_backend(self) -> None:
        merge = self._merge()
        settings, kind = merge(
            existing_generation={
                "generation_kind": "projects_skills",
                "generation_settings": {
                    "backend_provenance": {
                        "provenance_version": "v2",
                        "execution_backend": "codex",
                        "semantic_backend": "codex",
                        "semantic_model": "codex:sdk-configured-default",
                        "fit_backend": "not_applicable",
                    }
                },
            },
            generation_settings={"max_projects": 4},
            generation_kind="fit_only",
        )
        self.assertEqual(kind, "projects_skills")
        p = settings["backend_provenance"]
        self.assertEqual(p["execution_backend"], "mixed")
        self.assertEqual(p["semantic_backend"], "codex")
        self.assertEqual(p["semantic_model"], "codex:sdk-configured-default")
        self.assertEqual(p["fit_backend"], "deterministic-python")
        self.assertEqual(p["last_operation_kind"], "fit_only")

    def test_fit_does_not_guess_legacy_semantic_backend(self) -> None:
        merge = self._merge()
        settings, kind = merge(
            existing_generation={
                "generation_kind": "projects_skills",
                "generation_settings": {},
            },
            generation_settings={},
            generation_kind="fit_only",
        )
        self.assertEqual(kind, "projects_skills")
        p = settings["backend_provenance"]
        self.assertEqual(p["semantic_backend"], "unknown_legacy")
        self.assertEqual(p["semantic_model"], "unknown_legacy")
        self.assertEqual(p["fit_backend"], "deterministic-python")

    def test_new_semantic_generation_records_backend(self) -> None:
        merge = self._merge()
        settings, kind = merge(
            existing_generation=None,
            generation_settings={},
            generation_kind="projects_skills",
        )
        self.assertEqual(kind, "projects_skills")
        p = settings["backend_provenance"]
        self.assertEqual(p["semantic_backend"], "codex")
        self.assertEqual(p["semantic_model"], "codex:test")
        self.assertEqual(p["last_operation_kind"], "projects_skills")

    def test_persistence_uses_effective_generation_kind(self) -> None:
        node = self._fn("_persist_current_tailoring_state")
        block = "\n".join(self.app.splitlines()[node.lineno - 1:node.end_lineno])
        self.assertIn("existing_generation = get_tailoring_generation(", block)
        self.assertIn("generation_kind=effective_generation_kind,", block)
        self.assertIn("generation_settings=persisted_generation_settings,", block)

    def test_debug_exposes_last_operation_kind(self) -> None:
        self.assertIn('"last_operation_kind": row_backend.get(', self.app)


if __name__ == "__main__":
    unittest.main()

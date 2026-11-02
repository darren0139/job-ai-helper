"""Job Finder Profile & Evidence reference additions (no scorer changes)."""
import ast
from pathlib import Path
import unittest

from tailoring.profile_evidence_jobfinder_work_ui import (
    make_skill_evidence, make_work_evidence,
)

ROOT = Path(__file__).resolve().parents[1]


class JobFinderEvidenceReferencesTests(unittest.TestCase):
    def test_standalone_skill_no_project_needed(self):
        row = make_skill_evidence(name=" NVIDIA cuDF ", used_for="Used cuDF to preprocess real datasets")
        self.assertEqual(row["category"], "Skill")
        self.assertEqual(row["skills"], [])  # Skill.title is indexed by Job Finder
        self.assertEqual(row["source_type"], "manual")
        self.assertNotIn("project_id", row)

    def test_optional_work_reference_is_descriptive_not_automatic_proof(self):
        ref = {"category":"Work Experience", "id":42, "title":"Software Engineer Intern", "subtitle":"Example Org"}
        row = make_skill_evidence(name="NVIDIA cuDF", used_for="Used at work", work_reference=ref)
        self.assertIn("#42", row["subtitle"])
        self.assertEqual(row["description"], "Used at work")
        with self.assertRaises(ValueError):
            make_skill_evidence(name="NVIDIA cuDF", used_for="Used at work", work_reference={"category":"Project", "id":12})

    def test_work_reference_preserves_truth_and_separate_bullets(self):
        row = make_work_evidence(role="Engineer Intern", employer="Example Org", period="2025-2026", description="Used cuDF.\nAnalyzed datasets.", skills="Python, NVIDIA cuDF, python", tools="cuDF")
        self.assertEqual(row["category"], "Work Experience")
        self.assertEqual(row["description"], "Used cuDF.\nAnalyzed datasets.")
        self.assertEqual(row["skills"], ["Python", "NVIDIA cuDF"])
        self.assertNotIn("source_project_id", row)

    def test_no_unsubstantiated_blank_evidence(self):
        with self.assertRaises(ValueError):
            make_skill_evidence(name="NVIDIA cuDF", used_for=" ")
        with self.assertRaises(ValueError):
            make_work_evidence(role="Engineer", employer=" ", period="", description="Used tools")

    def test_job_finder_projects_work_as_experience_not_projects(self):
        source = (ROOT / "job_discovery" / "matching.py").read_text(encoding="utf-8")
        module = ast.parse(source)
        wanted = {"_clean", "_description_lines", "build_profile_evidence_context"}
        funcs = [node for node in module.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
        self.assertEqual(len(funcs), 3)
        import typing
        scope = {
            "Any": typing.Any,
            "build_candidate_context": lambda profile, items: {"evidence_library": items},
            "fingerprint_evidence_items": lambda items: "test-fingerprint",
        }
        exec(compile(ast.Module(body=funcs, type_ignores=[]), "<matching-pure-functions>", "exec"), scope)
        make_context = scope["build_profile_evidence_context"]
        evidence = [
            {"id":1,"category":"Work Experience", "title":"Engineer Intern", "subtitle":"Example Org",
             "period":"2025", "description":"Used NVIDIA cuDF to transform tables", "skills":["NVIDIA cuDF"], "tools":[]},
            {"id":2, "category":"Skill", "title":"NVIDIA cuDF", "description":"Used for tabular operations", "skills":[], "tools":[]},
        ]
        ctx = make_context(evidence)
        self.assertEqual(len(ctx["resume_profile"]["experience"]), 1)
        self.assertEqual(len(ctx["resume_profile"]["projects"]), 0)
        self.assertIn("NVIDIA cuDF", ctx["resume_profile"]["skills"]["evidence_2_claims"])
        self.assertIn("Used NVIDIA cuDF to transform tables", ctx["raw_resume_text"])
        self.assertEqual(ctx["evidence_item_count"], 2)

    def test_profile_page_hook_and_edit_category(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("render_job_finder_evidence_quick_add()", source)
        self.assertIn('"Work Experience",', source)
        ast.parse(source)


if __name__ == "__main__":
    unittest.main()

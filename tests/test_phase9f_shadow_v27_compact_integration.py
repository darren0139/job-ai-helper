"""Scoped UI linkage tests; source stays read-only and uses only the preexisting shadow module."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "tailoring" / "phase9f_final_evidence_comparison_v2_4.py"

class FakeStreamlit:
    def __init__(self, selected):
        self.selected = selected
        self.expanders = []
    def expander(self, label, **kwargs):
        self.expanders.append(label)
        return self
    def popover(self, *args, **kwargs): return self
    def container(self, *args, **kwargs): return self
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def caption(self, *_, **__): pass
    def markdown(self, *_, **__): pass
    def checkbox(self, label, *_, **__):
        return label.startswith("Show advanced — original bullet tables")
    def info(self, *_, **__): pass
    def dataframe(self, *_, **__): pass
    def write(self, *_, **__): pass
    def code(self, *_, **__): pass
    def multiselect(self, *_, **__): return self.selected

class CompactShadowLinkageTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("v27_compact_candidate_under_test", SOURCE)
        self.ui = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.ui)
        self.row = {"project": "Job AI Helper", "base": [], "library": [], "final": [],
                    "changes": [], "base_count": 0, "library_count": 0, "final_count": 0}
        self.audit = {"verified": True, "projects": [self.row], "notice": "Verified", 
                      "generation_id": "g1", "docx_sha256": "abc"}
        self.calls = []
        bound = types.ModuleType("tailoring.phase9f_project_bullet_sources_v2_3")
        bound._bound_candidate_sources = lambda *_: ([], "")
        shadow = types.ModuleType("tailoring.phase9f_bullet_quality_shadow_v2_5")
        def render(st, **kw): self.calls.append(kw)
        shadow.render_shadow_bullet_quality_trial = render
        pandas = types.ModuleType("pandas")
        pandas.DataFrame = lambda rows: rows
        # This test isolates the shadow entry point. Other newer, read-only
        # panels have their own tests and must not need their fixtures here.
        multi = types.ModuleType("tailoring.phase9f_multi_project_evidence_v36")
        multi.render_multi_project_evidence = lambda *_, **__: None
        explorer = types.ModuleType("tailoring.phase9f_decision_explorer_v28")
        explorer.render_decision_explorer = lambda *_, **__: False
        proxy = types.ModuleType("tailoring.phase9f_final_base_coverage_check_v1")
        proxy.build_final_vs_base_project_coverage = lambda *_, **__: {
            "status": "unavailable", "reason": "Out of scope for shadow linkage test"
        }
        self.fake_modules = {
            bound.__name__: bound, shadow.__name__: shadow, "pandas": pandas,
            multi.__name__: multi, explorer.__name__: explorer, proxy.__name__: proxy,
        }
        self.ui.build_final_evidence_audit = lambda *args, **kw: self.audit
    def render(self, selected):
        st = FakeStreamlit(selected)
        with patch.dict(sys.modules, self.fake_modules):
            result = self.ui.render_final_evidence_audit(st, application_id=149, projects={"receipt": True},
                fit={}, execution=None, decision=None, generation_id="g1", repo_root=Path("."))
        return st, result
    def test_selected_verified_project_links_only_expected_shadow(self):
        st, result = self.render([0])
        self.assertTrue(result)
        self.assertEqual(self.calls, [{"audit_project": self.row, "projects": {"receipt": True}, "application_id": 149}])
        self.assertIn("Optional JD coverage shadow (read-only)", st.expanders)
    def test_no_inspection_selection_no_shadow_computation(self):
        st, result = self.render([])
        self.assertTrue(result)
        self.assertEqual(self.calls, [])
        self.assertNotIn("Optional JD coverage shadow (read-only)", st.expanders)
    def test_unverified_receipt_cannot_reach_shadow(self):
        self.audit = {"verified": False, "projects": [], "notice": "Unverified"}
        st, result = self.render([0])
        self.assertFalse(result)
        self.assertEqual(self.calls, [])
    def test_patch_does_not_reintroduce_old_shadow_tabs(self):
        text = SOURCE.read_text(encoding="utf-8-sig")
        self.assertIn("Optional JD coverage shadow (read-only)", text)
        self.assertNotIn("tab_final, tab_base, tab_library, tab_fit, tab_quality", text)
        self.assertEqual(text.count("render_shadow_bullet_quality_trial("), 1)

if __name__ == "__main__": unittest.main()

"""UI-only visibility and messaging contract; never score or alter documents."""
from __future__ import annotations
import ast
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / 'tailoring' / 'phase9f_final_evidence_comparison_v2_4.py'

class FinalProxyVisibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text(encoding='utf-8')
        cls.tree=ast.parse(cls.source,filename=str(SOURCE))
        cls.fn=next(x for x in cls.tree.body if isinstance(x,ast.FunctionDef) and x.name=='render_final_evidence_audit')
    def test_final_audit_is_an_optional_advanced_view(self):
        text=ast.get_source_segment(self.source,self.fn)
        self.assertIn('"Fitting and source audit (advanced)", expanded=False',text)
    def test_proxy_visible_before_optional_advanced(self):
        text=ast.get_source_segment(self.source,self.fn)
        self.assertEqual(text.count('build_final_vs_base_project_coverage('),1)
        self.assertLess(text.index('**Final vs Selected Base — project-bullet JD coverage (diagnostic)**'),
                        text.index('Show advanced — original bullet tables'))
        self.assertIn('with st.container(border=True)',text)
    def test_no_full_resume_quality_claim(self):
        text=ast.get_source_segment(self.source,self.fn)
        self.assertIn('project-only proxy cannot verify overall résumé improvement',text)
        self.assertIn('Review Phase 8',text)
    def test_build_fitting_still_read_only(self):
        self.assertNotIn('render_automatic_bestof',self.source)
        self.assertNotIn('mark_fit_request',self.source)
        self.assertNotIn('INSERT INTO',self.source)
        self.assertNotIn('UPDATE tailoring',self.source)

if __name__=='__main__':unittest.main()

"""Prove that independent analysis render instances cannot register duplicate CSV keys.

Test runs independently, using exact source files staged from the uploaded ZIP.
It does not import Streamlit or query a database.
"""
from __future__ import annotations
import ast
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT=(Path(__file__).resolve().parents[1]/'tailoring')
if not (ROOT/'initial_score_breakdown_ui.py').is_file():
    ROOT=Path(__file__).resolve().parents[1]/'keyfix_sources'

class FakeST:
    def __init__(self, advanced=False):
        self.keys=[];self.advanced=advanced
    def __enter__(self):return self
    def __exit__(self,*a):return False
    def expander(self,*a,**k):return self
    def markdown(self,*a,**k):pass
    def code(self,*a,**k):pass
    def caption(self,*a,**k):pass
    def warning(self,*a,**k):pass
    def dataframe(self,*a,**k):pass
    def checkbox(self,*a,**k):
        self._take(k.get('key'))
        return self.advanced
    def download_button(self,*a,**k):self._take(k.get('key'))
    def _take(self,key):
        if not key:raise AssertionError('Unnamed control')
        if key in self.keys:raise AssertionError('Duplicate Streamlit widget key: '+key)
        self.keys.append(key)

def run_with_mocked_renderer(callback):
    fake_pkg=types.ModuleType('tailoring');fake_pkg.__path__=[]
    score=types.ModuleType('tailoring.phase8_score_explainability')
    score.build_score_breakdown=lambda native:native
    score.build_score_receipt=lambda breakdown:dict(breakdown)
    tables=types.ModuleType('tailoring.score_component_tables_ui')
    def fake_tables(st,receipt,*,breakdown,key_prefix,origin,legacy_csv):
        for category in ('required_core','preferred','evidence_strength','overall'):
            st.download_button('CSV',data=b'x',key=f'{key_prefix}_{category}_score_csv')
        st.download_button('ZIP',data=b'x',key=f'{key_prefix}_score_component_zip')
    tables.render_component_tables=fake_tables
    with patch.dict(sys.modules, {'tailoring':fake_pkg,
                                  'tailoring.phase8_score_explainability':score,
                                  'tailoring.score_component_tables_ui':tables}):
        spec=importlib.util.spec_from_file_location('_test_initial_score_breakdown',ROOT/'initial_score_breakdown_ui.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        return callback(mod)

def synthetic_view():
    return {'contribution_status':'available','stable_analysis':{'score_parity':True,
        'component_subtotal_parity':True,'requirement_subtotal_parity':True,
        'maximum_score_parity':True,'jd_requirement_max_total_parity':True,
        'stored_scorer_score':32,'components':[{'label':'Core','score':40.,'weight':.8,'weighted_points':32.}],
        'subtotal_before_rounding':32.,'maximum_score':100.,'jd_requirements':[],
        'pools':[],'requirement_subtotal':32.,'jd_requirement_max_total':100.},
        'score':32,'provenance':'PHASE9F_CONFIRMED_SELECTED_BASE'}

class WidgetNamespaceTests(unittest.TestCase):
    def test_initial_score_math_still_returns_original_receipt(self):
        view=synthetic_view()
        value=run_with_mocked_renderer(lambda mod: mod.initial_score_math(view)['stored_scorer_score'])
        self.assertEqual(value,32)
    def test_two_distinct_analyses_register_all_unique_controls(self):
        st=FakeST(advanced=True);v=synthetic_view()
        def render(mod):
            mod.render_initial_score_math(st,v,key_prefix='analysis_receipt_initial_123')
            mod.render_initial_score_math(st,v,key_prefix='analysis_receipt_phase9f_base_456')
        run_with_mocked_renderer(render)
        self.assertEqual(len(st.keys),14) # Five exports, one toggle and one map CSV per render
        self.assertEqual(len(st.keys),len(set(st.keys)))
    def test_repeat_same_instance_is_detected_by_test_double(self):
        st=FakeST();v=synthetic_view()
        def render(mod):
            mod.render_initial_score_math(st,v,key_prefix='same')
            with self.assertRaisesRegex(AssertionError,'Duplicate Streamlit widget key'):
                mod.render_initial_score_math(st,v,key_prefix='same')
        run_with_mocked_renderer(render)
    def test_key_prefix_passed_through_receipt(self):
        s=(ROOT/'initial_analysis_explainer_ui.py').read_text()
        self.assertIn('render_initial_score_math(st, view, key_prefix="analysis_receipt_" + receipt_key)',s)
        self.assertIn('str(widget_namespace or "default")',s)
    def test_previously_offending_hardcoded_key_removed(self):
        s=(ROOT/'initial_score_breakdown_ui.py').read_text()
        self.assertNotIn('key_prefix="initial_job_match", origin=',s)
        self.assertNotIn('key="initial_score_advanced_map_v1"',s)
    def test_preview_has_distinct_location_namespace(self):
        s=(ROOT/'phase9f_base_vs_tailored_explainer.py').read_text()
        self.assertIn('widget_namespace=f"phase9f_selected_base_preview_',s)
    def test_other_exports_have_scoped_keys(self):
        s=(ROOT/'initial_analysis_explainer_ui.py').read_text()
        self.assertIn('key="analysis_receipt_diagnostics_download_" + receipt_key',s)
        self.assertIn('key="analysis_receipt_csv_" + receipt_key',s)
    def test_all_syntax_and_source_scope(self):
        for name in ('initial_analysis_explainer_ui.py','initial_score_breakdown_ui.py',
                     'phase9f_base_vs_tailored_explainer.py'):
            ast.parse((ROOT/name).read_text(),filename=name)
        self.assertIn('widget_namespace="historical_reconstructed_profile"',
                      (ROOT/'initial_analysis_explainer_ui.py').read_text())

if __name__=='__main__':unittest.main()

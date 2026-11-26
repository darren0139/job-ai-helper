"""V3.2 action placement, source provenance and receipt-explanation regressions."""
from __future__ import annotations
import json
import unittest
from contextlib import nullcontext
from pathlib import Path

from tailoring.phase9f_auto_optimize_v31 import build_flexible_optimization
from tailoring.phase9f_automatic_bestof_v30_ui import (
    configured_mode, mark_fit_request, render_optimizer_mode_selector,
    source_wording_label, _source_comparison_rows, _render_source_comparison,
)
from tests.test_phase9f_auto_optimize_v31 import fixture, evaluator


class FakeStreamlit:
    def __init__(self, initial=None):
        self.session_state = dict(initial or {})
        self.record = []
        self.downloads = []
    def radio(self, title, options, **kwargs):
        self.record.append(('radio', title, options, kwargs))
        return self.session_state.setdefault(kwargs['key'], options[kwargs.get('index', 0)])
    def caption(self, text): self.record.append(('caption', text))
    def markdown(self, text): self.record.append(('markdown', text))
    def warning(self, text): self.record.append(('warning', text))
    def expander(self, label, **kwargs):
        self.record.append(('expander', label, kwargs))
        return nullcontext()
    def dataframe(self, rows, **kwargs):
        self.record.append(('table', rows))
    def download_button(self, label, **kwargs):
        self.downloads.append((label, kwargs))


class ConfigTests(unittest.TestCase):
    def test_default_and_legacy_checked_migration(self):
        st=FakeStreamlit({'v312b214_working_controls_40': {}})
        self.assertEqual(render_optimizer_mode_selector(st,40),'v37-same-work')
        self.assertEqual(st.session_state['phase9f_bestof_next_mode_40'],'v37-same-work')
        old=FakeStreamlit({'phase9f_v31_flexible_mode_41':True, 'v312b214_working_controls_41': {}})
        self.assertEqual(render_optimizer_mode_selector(old,41),'v37-same-work')
        self.assertEqual(old.session_state['phase9f_bestof_next_mode_41'],'v37-same-work')

    def test_mode_is_snapshotted_at_successful_fit_and_unaffected_by_later_change(self):
        st=FakeStreamlit({'phase9f_bestof_next_mode_3':'v31-flexible'})
        mark_fit_request(st,3,'g-one')
        st.session_state['phase9f_bestof_next_mode_3']='v26-fixed'
        self.assertEqual(st.session_state['phase9f_auto_bestof_run_mode_3'],
                         {'generation_id':'g-one','mode':'v37-same-work'})
        mark_fit_request(st,3,'g-two')
        self.assertEqual(st.session_state['phase9f_auto_bestof_run_mode_3'],
                         {'generation_id':'g-two','mode':'v26-fixed'})

    def test_app_control_is_before_build_button_and_result_is_read_only(self):
        root=Path(__file__).resolve().parents[1]
        app=(root/'app.py').read_text(encoding='utf-8')
        self.assertEqual(app.count('render_optimizer_mode_selector(st, int(current_application_id))'),1)
        self.assertLess(app.index('render_optimizer_mode_selector(st, int(current_application_id))'),
                        app.index('"Generate and Fit Tailored Resume DOCX",'))
        result=(root/'tailoring/phase9f_automatic_bestof_v30_ui.py').read_text(encoding='utf-8')
        self.assertNotIn("st.checkbox('Use V3.1 flexible bullet-count Auto-optimize",result)
        self.assertEqual(app.count('mark_fit_request(st, int(current_application_id)'),3)


class SelectionTests(unittest.TestCase):
    def test_exact_source_membership_is_not_false_winner(self):
        self.assertEqual(source_wording_label(['Current final','Selected Base','Evidence Library']),
                         'Base bullet and Library bullet (identical wording)')
        self.assertEqual(source_wording_label(['Current final']),
                         'Existing fitted résumé wording (source unconfirmed)')
        self.assertEqual(source_wording_label(['Evidence Library']),'Library bullet')

    def test_proposal_lists_both_selected_and_unselected_alternatives(self):
        a,p=fixture()
        got=build_flexible_optimization(a,p,evaluator=evaluator)
        self.assertEqual(got['status'],'candidate')
        rows=_source_comparison_rows(got)
        self.assertTrue(rows)
        selected=[r for r in rows if r['In optimized alternative']=='Yes']
        rejected=[r for r in rows if r['In optimized alternative']=='No']
        self.assertTrue(selected)
        self.assertTrue(rejected)
        self.assertTrue(any(r['Found in']=='Library bullet' for r in selected))
        self.assertTrue(any(r['In existing fitted résumé']=='Yes' for r in rejected))
        self.assertIn('not proof',got['source_comparison']['meaning'])
        self.assertFalse(got['selection_receipt']['verified_fitting_explanation'])

    def test_no_challenger_still_exposes_source_comparison(self):
        a,p=fixture();a['projects'][0]['library']=[]
        got=build_flexible_optimization(a,p,evaluator=evaluator)
        self.assertEqual(got['status'],'no_proxy_gain')
        self.assertTrue(_source_comparison_rows(got))

    def test_json_debug_exports_unverified_source_status_without_promotion(self):
        a,p=fixture()
        got=build_flexible_optimization(a,p,evaluator=evaluator)
        st=FakeStreamlit()
        result={'status':'needs_review','reason':'Base factual review pending',
                'winner':'existing_final','proposal':got}
        _render_source_comparison(st, application_id=7,context='abc123',run_mode='v31-flexible',
                                  result=result,audit={**a,'docx_sha256':'d'*64})
        self.assertEqual(len(st.downloads),1)
        payload=json.loads(st.downloads[0][1]['data'])
        self.assertFalse(payload['head_to_head_base_library_winner_recorded'])
        self.assertEqual(payload['comparison_status'],'needs_review')
        self.assertEqual(payload['optimizer_mode_used'],'v31-flexible')
        self.assertEqual(payload['proposal']['status'],'candidate')
        self.assertTrue(payload['candidate_wording_diagnostics'])
        self.assertTrue(payload['existing_fitting_audit']['projects'])
        self.assertFalse(any(r[0]=='table' for r in st.record))


if __name__=='__main__':
    unittest.main()

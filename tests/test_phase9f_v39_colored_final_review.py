"""V3.9 visual restoration: read-only final-only picker, receipt truth, colours, detail."""
from __future__ import annotations
import sys
import types
import unittest
from contextlib import nullcontext
from unittest.mock import patch

from tailoring import phase9f_v39_final_bullet_review as ui

PROJECT = 'Job AI Helper — AI-Powered Resume Tailoring System'
BASE = 'Built 30-job corpus regression/audit tooling and GitHub Actions CI across Windows/Ubuntu to validate scoring, taxonomy resolution, sessions, and UI workflows.'
LIB = 'Added automated unit tests and GitHub Actions CI across Ubuntu and Windows, running dependency checks, compilation, the full test suite, and a Streamlit startup health check.'


def doc():
    return {'status': 'verified_fitted', 'role': 'fitted', 'bullets': [{'project': PROJECT, 'bullet': LIB}], 'docx_sha256': 'a'*64}


def receipt():
    return {'version': 'phase9f-v39-pre-fit-dedupe-v1', 'status': 'removed_before_fit', 'removals': [{
        'project': PROJECT, 'removed': BASE, 'retained': LIB, 'removed_sources': ['Base Resume'],
        'retained_sources': ['Evidence Library'], 'removed_saved_evidence_points': 9.0,
        'retained_saved_evidence_points': 9.0,
        'selection_reason': 'Equal recorded JD evidence; deterministic source/order tie break',
        'recorded_at_stage': 'pre_fitting',
    }]}


class FakeStreamlit:
    def __init__(self): self.calls=[]; self.session_state={}
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def _capture(self, method, *v, **kw): self.calls.append((method, v, kw))
    def container(self, **kw): self._capture('container', **kw); return nullcontext()
    def columns(self, n):return [self for _ in range(n)]
    def button(self,label,**kw): self._capture('button',label,**kw); return False
    def checkbox(self,label,*,key,value=False,**kw):
        self._capture('checkbox',label,key=key,**kw)
        return self.session_state.setdefault(key,value)
    def expander(self, label, **kw): self._capture('expander', label, **kw); return nullcontext()
    def markdown(self, value, **kw): self._capture('markdown', value, **kw)
    def caption(self, value, **kw):self._capture('caption',value,**kw)
    def write(self, value, **kw):self._capture('write',value,**kw)
    def metric(self, *args, **kw):self._capture('metric',*args,**kw)
    def info(self, value, **kw):self._capture('info',value,**kw)
    def warning(self,value, **kw):self._capture('warning',value,**kw)
    def success(self,value, **kw):self._capture('success',value,**kw)
    def selectbox(self,label, options, **kw):self._capture('selectbox',label, list(options),**kw);return options[0]
    def radio(self,label, options, **kw):
        self._capture('radio',label,list(options),**kw)
        return self.session_state.get(kw.get('key'),options[0])


def stub_facts(row,catalog):
    text=row['bullet']
    return {'words':len(text.split()), 'technologies':['GitHub Actions'],
        'strengths':['Concrete implemented CI work'], 'limits':['Application deployment is not established'],
        'phrases': {'features':[], 'team':[], 'release':[], 'ci':['GitHub Actions CI']},
        'requirements':[{'id':'r1', 'importance':'core', 'text':'Using build automation tools',
                         'relevant':True,'phrases':['GitHub Actions CI'],
                         'kind':'Related tooling', 'reason':'Deployment not established.'}]}


class RestorationTests(unittest.TestCase):
    def test_exact_tie_receipt_is_not_native_score_claim(self):
        got=ui._verified_prefit_pair(selected={'project':PROJECT,'bullet':LIB},chosen=doc(),receipt=receipt())
        self.assertEqual(9.0,got['retained_saved_evidence_points'])
        self.assertIn('tie break',got['selection_reason'])

    def test_dont_show_removal_if_bullet_still_present(self):
        chosen=doc();chosen['bullets'].append({'project':PROJECT,'bullet':BASE})
        self.assertIsNone(ui._verified_prefit_pair(selected={'project':PROJECT,'bullet':LIB},chosen=chosen,receipt=receipt()))
        other=receipt();other['version']='wrong';self.assertIsNone(ui._verified_prefit_pair(selected={'project':PROJECT,'bullet':LIB},chosen=doc(),receipt=other))
        other=receipt();other['removals'][0]['recorded_at_stage']='proposal';self.assertIsNone(ui._verified_prefit_pair(selected={'project':PROJECT,'bullet':LIB},chosen=doc(),receipt=other))

    def test_challenger_cannot_show_prefit_fitted_selection(self):
        d=doc();d['status']='verified_challenger'
        self.assertIsNone(ui._verified_prefit_pair(selected={'project':PROJECT,'bullet':LIB},chosen=d,receipt=receipt()))

    def test_full_comparison_keeps_selector_and_colours(self):
        st=FakeStreamlit()
        facts=types.ModuleType('tailoring.phase9f_wording_explanation_ui')
        facts.wording_facts=stub_facts
        def comp(table, headings, rows): table._capture('comparison_table',list(headings),list(rows))
        facts._comparison_table=comp
        estimator=types.ModuleType('tailoring.bullet_choice_estimated')
        estimator.estimate_pair=lambda a,b,requirements:{'outcome':'Library stronger (estimated)','reason':'More testing wording'}
        pair={'source':'library','base':{'project':PROJECT,'bullet':BASE,'sources':['Selected Base'],'jd_links':[]},
              'library':{'project':PROJECT,'bullet':LIB,'sources':['Evidence Library'],'jd_links':[]},
              'reason':'Auto-related pair'}
        proposal={'v38_bullet_score_receipt': {'status':'available','bullets':[
            {'project':PROJECT,'wording':BASE,'standalone_weighted_points':9.0,'saved_jd_ids':['r1']},
            {'project':PROJECT,'wording':LIB,'standalone_weighted_points':9.0,'saved_jd_ids':['r1']}]}}
        with patch.object(ui,'chosen_document',return_value=doc()),patch.object(ui,'explain_pair',return_value=pair),patch.dict(sys.modules,{
                'tailoring.phase9f_wording_explanation_ui':facts,'tailoring.bullet_choice_estimated':estimator}):
            ok=ui.render_verified_final_bullets(st,audit={},result={'status':'verified','winner':'existing_final'},
                 proposal=proposal,ranked=[],catalog={'r1':{'text':'Using build automation tools','importance':'core'}},
                 application_id=156,context='test',prefit_receipt=receipt())
        self.assertTrue(ok)
        labels=[c[1][0] for c in st.calls if c[0] in ('checkbox','radio')]
        self.assertEqual([PROJECT,'Select one final résumé bullet'],labels)
        self.assertEqual([c[1][0] for c in st.calls if c[0]=='button'],['Select all','Clear all'])
        radio=next(c for c in st.calls if c[0]=='radio')
        self.assertEqual(radio[1][1],[LIB])
        self.assertEqual(radio[2]['format_func'](LIB),LIB+' · JD 9.000 pts')
        md=[c[1][0] for c in st.calls if c[0]=='markdown']
        self.assertEqual(2,md.count('**:green[Strengths]**'))
        self.assertEqual(2,md.count('**:red[Weaknesses / limits]**'))
        self.assertIn('##### JD requirements & keyword evidence',md)
        self.assertIn('##### Keyword comparison at a glance',md)
        self.assertIn('##### JD relevance and wording trade-offs (estimated)',md)
        self.assertTrue(any(c[0]=='success' and 'Base 9.000 vs Library 9.000' in c[1][0] for c in st.calls))
        self.assertEqual(2,len([c for c in st.calls if c[0]=='metric']))
        self.assertEqual(3,len([c for c in st.calls if c[0]=='comparison_table']))
        self.assertFalse(any(c[0]=='warning' and 'overlapping bullets remain' in c[1][0] for c in st.calls))

if __name__=='__main__':unittest.main()

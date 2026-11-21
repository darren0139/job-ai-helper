"""Isolated negative controls for the exact-data, JD-first Decision Explorer."""
from __future__ import annotations
import copy,importlib.util,sys,types,unittest
from pathlib import Path
from unittest.mock import patch
PATH=Path(__file__).resolve().parents[1]/'tailoring/phase9f_decision_explorer_v28.py'
spec=importlib.util.spec_from_file_location('v28_under_test',PATH)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

BASE='Built help-desk workflows with working frontend ticket operations.'
LIB='Built full-stack help-desk workflows in React and PostgreSQL database-backed service.'
REQ='Experience in frontend and backend web application development'

def fixture():
    saved={'projects':[{'project':'QueryAI', 'base_bullets':[{'#':1,'Base Resume bullet':BASE}],
      'library_bullets':[{'#':1,'Evidence Library bullet':LIB}],
      'draft_bullets':[{'Generated draft bullet':LIB},{'Generated draft bullet':BASE}],
      'rank':1,'bullet_source_policy_version':'phase9f-combined-project-bullet-sources-v2.7',
      'bullet_decision_receipts':[
        {'bullet_id':'b','bullet':BASE,'sources':['base'],'selected':True,'reason':'all_canonical_before_fitting_fill',
         'supported_requirement_ids':[],'weak_requirement_ids':[],'direct_requirement_ids':[]},
        {'bullet_id':'l','bullet':LIB,'sources':['library'],'selected':True,'reason':'minimum_project_coverage',
         'supported_requirement_ids':['req-1'],'weak_requirement_ids':[], 'direct_requirement_ids':['req-1']}],
      }]}
    project={'recommended_projects':[{'title':'QueryAI','display_title':'QueryAI'}],
      'candidate_project_ranking':[{'title':'QueryAI','requirement_matches':[
        {'requirement_id':'req-1','requirement_text':REQ,'importance':'preferred','match_label':'direct'}]}],
      'deterministic_rule_debug':{'bullet_allocation':{'allocation_mode':'all_canonical_before_fitting'}}}
    fitted={'verified':True,'generation_id':'g1', 'projects':[{'project':'QueryAI','final':[{'text':LIB}],
      'changes':[{'action':'Removed during fitting','text':BASE,'reason':'contains no unique protected requirement evidence'}]}]}
    return saved,project,fitted

class ExplorerTests(unittest.TestCase):
    def run_builder(self,saved=None,project=None,fit=None):
        good=fixture();src=saved or good[0];p=project or good[1];f=fit or good[2]
        fake=types.ModuleType('tailoring.phase9f_project_bullet_sources_v2_3')
        fake.build_project_bullet_source_view=lambda *args:src
        with patch.dict(sys.modules, {'tailoring':types.ModuleType('tailoring'),fake.__name__:fake}):
            return m.build_decision_explorer(p,[{'name':'frozen'}],f)
    def test_verified_final_and_removed_fit_are_separate_stages(self):
        d=self.run_builder();self.assertEqual(d['status'],'ok')
        self.assertEqual(d['count_candidates'],2);self.assertEqual(d['count_final'],1)
        b={x['sources'][0]:x for x in d['projects'][0]['bullets']}
        self.assertEqual(b['library']['status'],'retained')
        self.assertEqual(b['base']['status'],'removed_fitting')
        self.assertIn('unique protected',b['base']['fit_reason'])
        self.assertEqual(b['library']['links']['req-1'],'direct')
        self.assertEqual(m.evidence_label(b['base'],'req-1'),'no_saved_bullet_link')
    def test_actual_saved_fitting_reason_is_used(self):
        d=self.run_builder();b=next(x for x in d['projects'][0]['bullets'] if 'base' in x['sources'])
        self.assertIn('Recorded fitting removal',m.display_reason(b,mode='all_canonical_before_fitting'))
    def test_kept_library_is_not_called_head_to_head_winner(self):
        d=self.run_builder();b=next(x for x in d['projects'][0]['bullets'] if 'library' in x['sources'])
        self.assertIn('no head-to-head',m.display_reason(b,mode='all_canonical_before_fitting').lower())
    def test_unverified_or_unbound_docx_refused(self):
        a,p,f=fixture();f['verified']=False
        self.assertEqual(self.run_builder(a,p,f)['status'],'withheld')
        f['verified']=True;f['generation_id']=''
        self.assertEqual(self.run_builder(a,p,f)['status'],'withheld')
    def test_identity_drift_refused(self):
        a,p,f=fixture();f['projects'][0]['project']='Other'
        self.assertEqual(self.run_builder(a,p,f)['status'],'withheld')
    def test_forged_owners_refused(self):
        a,p,f=fixture();a['projects'][0]['bullet_decision_receipts'][0]['sources']=['library']
        self.assertEqual(self.run_builder(a,p,f)['status'],'withheld')
    def test_foreign_requirement_refused(self):
        a,p,f=fixture();a['projects'][0]['bullet_decision_receipts'][1]['supported_requirement_ids']=['outside']
        self.assertEqual(self.run_builder(a,p,f)['status'],'withheld')
    def test_duplicate_receipt_refused(self):
        a,p,f=fixture();a['projects'][0]['bullet_decision_receipts'].append(copy.deepcopy(a['projects'][0]['bullet_decision_receipts'][1]))
        self.assertEqual(self.run_builder(a,p,f)['status'],'withheld')
    def test_changed_final_is_unattributed_not_library(self):
        a,p,f=fixture();f['projects'][0]['final']=[{'text':'Completely rewritten sentence'}]
        d=self.run_builder(a,p,f)
        self.assertEqual(d['projects'][0]['unattributed_final'],1)
        self.assertNotEqual(d['projects'][0]['bullets'][1]['status'],'retained')
    def test_tokens_are_exact_not_semantic(self):
        self.assertIn('frontend',m.terms(REQ))
        self.assertNotIn('react',m.terms(REQ))
    def test_markdown_does_not_render_tags(self):
        s=m.highlight_words('<script>alert(1)</script> frontend *fake*',{'frontend'})
        self.assertIn('**frontend**',s)
        self.assertNotIn('<script>',s)
    def test_build_does_not_mutate_inputs(self):
        a,p,f=fixture();original=copy.deepcopy((a,p,f));self.run_builder(a,p,f)
        self.assertEqual((a,p,f),original)
    def test_native_render_has_jd_and_both_source_columns(self):
        a,p,f=fixture()
        class FakeUI:
            def __init__(self):self.session_state={};self.output=[]
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def columns(self,n):return [self for _ in range(len(n) if isinstance(n,(list,tuple)) else n)]
            def container(self,**kwargs):return self
            def selectbox(self,label,options,**kwargs):return options[0]
            def metric(self,*args,**kwargs):pass
            def caption(self,*args,**kwargs):pass
            def info(self,*args,**kwargs):pass
            def warning(self,*args,**kwargs):pass
            def write(self,*args,**kwargs):pass
            def checkbox(self,*args,**kwargs):return False
            def button(self,*args,**kwargs):return False
            def markdown(self,value,*args,**kwargs):self.output.append(str(value))
        mock=FakeUI()
        fake=types.ModuleType('tailoring.phase9f_project_bullet_sources_v2_3')
        fake.build_project_bullet_source_view=lambda *args:a
        with patch.dict(sys.modules, {'tailoring':types.ModuleType('tailoring'),fake.__name__:fake}):
            self.assertTrue(m.render_decision_explorer(mock,application_id=156,projects=p,
                                                       candidates=[],final_audit=f))
        self.assertTrue(any('Selected Base résumé' in s for s in mock.output))
        self.assertTrue(any('Evidence Library' in s for s in mock.output))
        self.assertTrue(any(r'full\-stack' in s or 'full-stack' in s for s in mock.output))

    def test_missing_jd_rows_refused(self):
        a,p,f=fixture();p['candidate_project_ranking']=[]
        self.assertEqual(self.run_builder(a,p,f)['status'],'withheld')
    def test_lexical_words_not_auto_upgraded_to_direct(self):
        a,p,f=fixture();a['projects'][0]['bullet_decision_receipts'][0]['weak_requirement_ids']=['req-1']
        d=self.run_builder(a,p,f);base=d['projects'][0]['bullets'][0]
        self.assertEqual(base['links']['req-1'],'weak')
        self.assertNotEqual(base['links']['req-1'],'direct')

if __name__=='__main__':unittest.main()

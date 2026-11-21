"""Isolated JD-first pre-fit explorer source-contract tests."""
from __future__ import annotations
import unittest,copy,json
from pathlib import Path
from tailoring.phase9f_pre_fit_decision_explorer_v281 import (
    build_pre_fit_decisions,render_pre_fit_decision_explorer,_highlight,_badge)

FIXTURE=Path('/mnt/data/app_156_openai_gpt-5.6-luna_debug_bundle_20261117_173155.json')
# Installer tests cannot use an external debug fixture; embedded minimal contract.
BASE='Built help-desk workflows with working frontend ticket operations.'
LIB='Built full-stack frontend and backend workflows using React and PostgreSQL.'
REQ='Experience in frontend and backend web application development'
REQ2='Execute unit, integration, system and user acceptance testing'

def fixture():
    pool=[{'title':'QueryAI','currently_in_resume':True,'in_evidence_library':True,
           'resume_evidence':{'bullets':[BASE]},'evidence_library_evidence':{'bullets':[LIB]}}]
    project={'title':'QueryAI','display_title':'QueryAI', 'project_id':'p', 'source':'both',
             'selected_blueprint_bullets':[BASE,LIB], 'selected_bullet_sources':[['base'],['library']],
             'bullet_source_policy_version':'phase9f-combined-project-bullet-sources-v2.7',
             'draft_bullets':[LIB,BASE], 'bullet_decision_receipts':[
                 {'bullet_id':'a','bullet':BASE,'sources':['base'],'selected':True,'reason':'fit_all',
                  'supported_requirement_ids':[],'direct_requirement_ids':[],'weak_requirement_ids':[]},
                 {'bullet_id':'b','bullet':LIB,'sources':['library'],'selected':True,'reason':'coverage',
                  'supported_requirement_ids':['r1'],'direct_requirement_ids':['r1'],'weak_requirement_ids':[]},]}
    rank={'title':'QueryAI','display_title':'QueryAI','source':'both','project_id':'p','selection_rank':1,
           'requirement_matches':[{'requirement_id':'r1','requirement_text':REQ,'importance':'preferred','match_label':'direct'}]}
    projects={'recommended_projects':[project],'candidate_project_ranking':[rank]}
    stable={'canonical_requirements':[{'requirement_id':'r1','text':REQ,'importance':'preferred'},
                                      {'requirement_id':'r2','text':REQ2,'importance':'core'}]}
    return projects,pool,stable

class FakeUI:
    def __init__(self):self.session_state={};self.output=[]
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def columns(self,n):return [self for _ in range(n if isinstance(n,int) else len(n))]
    def container(self,**k):return self
    def selectbox(self,label,opts,**kw):return opts[0]
    def checkbox(self,*a,**kw):return False
    def button(self,*a,**kw):return False
    def markdown(self,s,**kw):self.output.append(s)
    def caption(self,s,**kw):self.output.append(s)
    def info(self,s,**kw):self.output.append(s)
    def write(self,s,**kw):self.output.append(s)

class PrefitTests(unittest.TestCase):
    def test_real_source_contract(self):
        p,c,s=fixture();view=build_pre_fit_decisions(p,c,s)
        self.assertEqual(view['status'],'ok',view.get('reason'))
        self.assertEqual(len(view['requirements']),2)
        rows=view['projects'][0]['bullets']
        self.assertEqual(len(rows),2)
        self.assertEqual(next(r for r in rows if 'library' in r['sources'])['links']['r1'],'direct')
    def test_missing_canonical_remains_unlinked_not_hidden(self):
        p,c,s=fixture();view=build_pre_fit_decisions(p,c,s)
        self.assertIn('r2',{r['id'] for r in view['requirements']})
        self.assertTrue(all('r2' not in row['links'] for row in view['projects'][0]['bullets']))
    def test_does_not_mutate_saved_input(self):
        p,c,s=fixture();frozen=copy.deepcopy((p,c,s));build_pre_fit_decisions(p,c,s)
        self.assertEqual((p,c,s),frozen)
    def test_foreign_jd_requirement_refused(self):
        p,c,s=fixture();p['recommended_projects'][0]['bullet_decision_receipts'][1]['direct_requirement_ids']=['evil']
        self.assertEqual(build_pre_fit_decisions(p,c,s)['status'],'withheld')
    def test_forged_ownership_refused(self):
        p,c,s=fixture();p['recommended_projects'][0]['bullet_decision_receipts'][1]['sources']=['base']
        self.assertEqual(build_pre_fit_decisions(p,c,s)['status'],'withheld')
    def test_canonical_identity_drift_refused(self):
        p,c,s=fixture();s['canonical_requirements'][0]['text']='fake JD'
        self.assertEqual(build_pre_fit_decisions(p,c,s)['status'],'withheld')
    def test_escaped_highlight(self):
        self.assertNotIn('<script>',_highlight('<script>React</script>',{'react'}))
        self.assertIn('<mark',_highlight('React',{ 'react' }))
        self.assertIn('&lt;script&gt;',_highlight('<script>',{'test'}))
        self.assertIn('&lt;',_badge('<',kind='direct'))
    def test_render_has_buttons_and_both_source_columns(self):
        p,c,s=fixture();ui=FakeUI()
        self.assertTrue(render_pre_fit_decision_explorer(ui,projects=p,candidates=c,application_id=4,stable_analysis=s))
        self.assertTrue(any('Selected Base' in o for o in ui.output))
        self.assertTrue(any('Evidence Library' in o for o in ui.output))
        self.assertTrue(any('JD requirement coverage' in o for o in ui.output))
    def test_legacy_no_receipts_does_not_fake_allocation(self):
        p,c,s=fixture();p['recommended_projects'][0]['bullet_decision_receipts']=[]
        view=build_pre_fit_decisions(p,c,s)
        self.assertEqual(view['status'],'ok',view.get('reason'))
        self.assertTrue(all(r['allocated'] is None for r in view['projects'][0]['bullets']))

if __name__=='__main__':unittest.main()

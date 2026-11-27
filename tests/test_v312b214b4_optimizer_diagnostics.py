import copy
import json
import unittest
from hashlib import sha256
from tailoring.phase9f_optimizer_diagnostics_v312b214b4 import build_report, from_bundle, render_diagnostics

G='g123'; DOC=b'docx fixture'; JD='exact JD'; TEXT='Built React features'; LOST='Implemented SQLite persistence'

def project(*bullets):
    return {'title':'P','draft_bullets':list(bullets)}

def inputs():
    projects={'recommended_projects':[{**project(TEXT, LOST),'bullet_decision_receipts':[{'bullet':LOST,'selected':True,'sources':['library'],'supported_requirement_ids':['r'],'reason':'saved selection'}]}]}
    fit={'generation_id':G,'fitting_input_snapshot':{'caller_input':{'projects':projects},'prepared_initial_state':{'projects':{'recommended_projects':[project(TEXT, LOST)]}}},'tailored_projects_used':{'recommended_projects':[project(TEXT)]},'remaining_active_reductions':[{'project':'P','change_type':'remove_bullet','removed_bullet':LOST,'evidence_loss_reason':'saved reason'}]}
    audit={'generation_id':G,'verified':True,'docx_sha256':sha256(DOC).hexdigest(),'projects':[{'project':'P','base':[{'text':TEXT}],'library':[{'text':LOST}],'final':[{'text':TEXT}]}]}
    phase8={'application_id':158,'generation_id':G,'comparison_valid':True,'document_analysis':{'final_document_sha256':sha256(DOC).hexdigest(),'final':{'jd_text_sha256':sha256(JD.encode()).hexdigest()}},'after_stable_analysis':{'scoring_version':'new','canonical_requirements':[{'requirement_id':'r','score_eligible':True,'match_label':'none','text':'Database proficiency'}]}}
    return dict(application_id=158,generation_id=G,projects=projects,fit=fit,audit=audit,result={'status':'verified','scoring_version':'old','proposal':{'v38_bullet_score_receipt':{'status':'available','bullets':[{'standalone_weighted_points':9,'marginal_in_proposal_points':0}]}}},baseline_report={'stable_analysis':{'scoring_version':'new'}},raw_jd_text=JD,phase8=phase8,docx_bytes=DOC)

class DiagnosticsTests(unittest.TestCase):
    def test_stages_and_saved_reasons(self):
        k=inputs(); before=copy.deepcopy(k); r=build_report(**k); self.assertEqual(k,before)
        p=r['project_stages'][0]; self.assertEqual([p[x] for x in ('generated_or_caller','fitter_start','saved_fitted','actual_readback')],[2,2,1,1])
        l=next(x for x in r['bullet_stages'] if x['wording']==LOST); self.assertEqual(l['outcome'],'Active exact-wording removal recorded'); self.assertEqual(l['active_removal_reasons'],['saved reason'])
        self.assertEqual(len(r['native_gap_clues'][0]['historical_saved_link_candidates']),1)
    def test_preparation_disappearance_needs_an_exact_saved_event(self):
        from tailoring.phase9f_lead_intro_v310 import VERSION as LEAD
        from tailoring.phase9f_prefit_dedupe_v39 import VERSION as DEDUPE

        k = inputs()
        fit = k['fit']
        fit['fitting_input_snapshot']['prepared_initial_state']['projects']['recommended_projects'] = [project(TEXT)]
        fit['remaining_active_reductions'] = []
        fit['v39_auto_dedupe'] = {'version': DEDUPE, 'status': 'checked_no_duplicates', 'removals': []}

        def preparation():
            trace = build_report(**k)['decision_trace']
            row = next(row for row in trace['wordings'] if row['wording'] == LOST)
            return next(stage for stage in row['stages'] if stage['stage'] == 'Preparation')

        self.assertEqual(preparation()['certainty'], 'Cause unknown')
        fit['v310_lead_intro'] = {'version': LEAD, 'removals': [
            {'project': 'P', 'removed': LOST, 'retained': TEXT, 'reason': 'saved lead decision'},
        ]}
        stage = preparation()
        self.assertEqual(stage['certainty'], 'Recorded')
        self.assertEqual(stage['details'][0]['name'], 'Project lead selection')
        self.assertEqual(stage['details'][0]['reason'], 'saved lead decision')

    def test_optimizer_trace_requires_same_generation_jd_and_document(self):
        k = inputs()
        k['result'] = {'status': 'withheld', 'verification_stage': 'materialize_and_render_b',
                       'reason': 'Saved malformed challenger'}
        k['optimizer_scope'] = {'application_id': 158, 'generation_id': G,
                                'jd_sha256': sha256(JD.encode()).hexdigest(),
                                'docx_sha256': sha256(DOC).hexdigest()}
        scope = build_report(**k)['decision_trace']['whole_document']
        self.assertEqual(scope[0]['details']['stage'], 'materialize_and_render_b')
        self.assertEqual(scope[1]['certainty'], 'Unavailable')
        k['optimizer_scope']['docx_sha256'] = 'foreign'
        self.assertEqual(build_report(**k)['decision_trace']['whole_document'][0]['certainty'], 'Unavailable')

    def test_receipt_identity(self):
        for key,val in [('application_id',99),('generation_id','other'),('raw_jd_text','different'),('docx_bytes',b'changed')]:
            k=inputs(); k[key]=val; self.assertIsNone(build_report(**k)['native_phase8'])
    def test_missing_readback_not_zero(self):
        k=inputs();k['audit']={};r=build_report(**k);self.assertFalse(r['actual_readback_available']);self.assertIsNone(r['project_stages'][0]['actual_readback'])
    def test_missing_fit_not_zero(self):
        k=inputs();k['fit']={};r=build_report(**k);self.assertFalse(r['fit_bound']);self.assertEqual(r['project_stages'],[]);self.assertIsNone(r['native_phase8'])
    def test_duplicate_titles_withheld(self):
        k=inputs();k['fit']['tailored_projects_used']['recommended_projects'].append(project(TEXT));r=build_report(**k);self.assertIsNone(r['project_stages'][0]['saved_fitted'])
    def test_rewording_is_not_deletion(self):
        k=inputs();k['fit']['remaining_active_reductions']=[];r=build_report(**k);self.assertEqual(next(x for x in r['bullet_stages'] if x['wording']==LOST)['outcome'],'Not found as exact final wording')
    def test_version_and_proxies(self):
        r=build_report(**inputs());self.assertIn('different scorer versions',r['optimizer']['version_comparison']);self.assertEqual(r['optimizer']['saved_bullet_score_receipt']['bullets'][0]['marginal_in_proposal_points'],0)
        k=inputs();k['result']['scoring_version']='new';self.assertIn('cache validity not established',build_report(**k)['optimizer']['version_comparison'])
    def test_cycles_no_mutation(self):
        k=inputs();p=k['result']['proposal'];p['candidate_variants']=[p];r=build_report(**k);json.dumps(r,allow_nan=False);self.assertIs(p['candidate_variants'][0],p)
    def test_actual_readback_wrong_generation(self):
        k=inputs();k['audit']['generation_id']='other';self.assertFalse(build_report(**k)['actual_readback_available'])
    def test_offline_missing_receipts(self):
        r=from_bundle({'debug_meta':{'application_id':158}});self.assertFalse(r['fit_bound']);self.assertIsNone(r['native_phase8'])
    def test_ui_only_display(self):
        class Fake:
            def __init__(self): self.calls=[]
            def __getattr__(self,name):
                if name not in ('markdown','caption','dataframe','write','download_button'): raise AssertionError(name)
                def call(*args,**kw):self.calls.append((name,args,kw))
                return call
        k=inputs();k.pop('phase8');k.pop('docx_bytes');s=Fake();render_diagnostics(s,**k,run_mode='v37-same-work',context='fixture');downloads=[x for x in s.calls if x[0]=='download_button'];self.assertEqual(len(downloads),1);self.assertEqual(json.loads(downloads[0][2]['data'])['generation_id'],G)


class HistoricalWiringTests(unittest.TestCase):
    def test_history_distinct_from_active_and_not_promoted(self):
        k=inputs(); k['result']={'status':'not_run'}; k['run_mode']='unknown'
        k['optimizer_history']=[{'Mode':'v37-same-work','Status':'verified','Scorer':'old','Request':'Build and Fit'}]
        r=build_report(**k)
        self.assertEqual(r['optimizer']['status'],'not_run')
        self.assertIsNone(r['optimizer']['saved_native_scores']['a_score'])
        self.assertEqual(r['historical_optimizer_records'][0]['Mode'],'v37-same-work')
        self.assertIn('different scorer versions',r['historical_optimizer_records'][0]['version_comparison'])
        k['audit']['generation_id']='wrong';self.assertEqual(build_report(**k)['historical_optimizer_records'],[])
    def test_standalone_scope_and_zero_preserved(self):
        k=inputs(); k['independent_scores']={'status':'available','native_score_claim':False,'optimizer_search_performed':False,
            'scope':{'generation_id':G,'a_docx_sha256':sha256(DOC).hexdigest(),'raw_jd_sha256':sha256(JD.encode()).hexdigest()},
            'bullets':[{'wording':LOST,'standalone_weighted_points':0,'marginal_in_proposal_points':None}]}
        r=build_report(**k);self.assertEqual(r['independent_bullet_scores']['bullets'][0]['standalone_weighted_points'],0)
        self.assertIsNone(r['independent_bullet_scores']['bullets'][0]['marginal_in_proposal_points'])
        for key in ('generation_id','a_docx_sha256','raw_jd_sha256'):
            changed=copy.deepcopy(k);changed['independent_scores']['scope'][key]='wrong'
            self.assertEqual(build_report(**changed)['independent_bullet_scores']['status'],'unavailable')
    def test_no_fake_history_or_native_points(self):
        k=inputs();k['optimizer_history']=[{'Mode':'v37-same-work','Status':'not_run','Scorer':'old'}]
        r=build_report(**k);self.assertEqual(r['historical_optimizer_records'],[])
        self.assertEqual(r['independent_bullet_scores']['status'],'unavailable')

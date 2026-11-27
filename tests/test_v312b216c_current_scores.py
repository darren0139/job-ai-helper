import unittest
from copy import deepcopy
from tailoring.phase9f_score_authority_v312b216a import fp, sha, METRICS
from tailoring.phase9f_current_score_v312b216c import project_current_scores, sidebar_score_label, load_active_score


def fixture():
    raw='Requirements:\nPython'
    scope='scope-fingerprint'; identity={'scoring_version':'native-v1','taxonomy_version':'tax-v1','registry_version':'reg-v1','jd_fingerprint':sha(raw)}
    row={'requirement_id':'r1','text':'Python','importance':'core','match_label':'direct','match_value':1.0,'evidence_strength':5,'score_eligible':True,'group_weight_fraction':1.0,'evidence':[]}
    def stable(values):
        return {**dict(zip(METRICS,values)), 'canonical_requirements':[deepcopy(row)],'scoring_version':'native-v1'}
    historical=stable([25,17,50,67]);before=stable([30,21,50,80]);after=stable([31,23,50,72])
    ctx={'decision_fingerprint':'decision','starting_snapshot_fingerprint':'snapshot'}
    def authority(st, text):
        a={'input_authority':'ACTUAL_RESUME_DOCUMENT','jd_text_sha256':sha(raw),'resume_text_sha256':sha(text),'stable_analysis_fingerprint':fp(st),'identity':deepcopy(identity),'canonical_requirement_fingerprint':scope};a['fingerprint']=fp(a);return a
    ba,fa=authority(before,'base'),authority(after,'final')
    src='a'*64; final='b'*64
    receipt={'application_id':159,'generation_id':'gen','verification_id':'verification','comparison_valid':True,'starting_document_contract':{'mode':'selected_base_docx_only','selected_base_docx_sha256':src,'selected_base_document_analysis_fingerprint':ba['fingerprint'],'selected_base_resume_text_sha256':ba['resume_text_sha256']},'before_stable_analysis':before,'after_stable_analysis':after,'document_analysis':{'initial':ba,'final':fa,'final_document_sha256':final},'selected_base_analysis':{'document_analysis':deepcopy(ba),'stable_analysis':deepcopy(before),'starting_context':ctx},'comparison':{'before_score':30,'after_score':31,'score_delta':1,'required_core_coverage_delta':2}}
    return dict(application_id=159,historical_report={'raw_jd_text':raw,'stable_analysis':historical,'meta':{'phase9e_starting_context':ctx}},decision={'application_id':159,'scope_activation_status':'active','current_scope_status':'current','decision_fingerprint':'decision','starting_snapshot':{'starting_snapshot_fingerprint':'snapshot'}},generation={'application_id':159,'generation_id':'gen','status':'draft','generation_settings':{'phase9e_binding':deepcopy(ctx)}},receipt=receipt,exact_jd={'application_id':159,'raw_text':raw,'raw_jd_sha256':sha(raw),'canonical_requirement_fingerprint':scope,'canonical_requirement_ids':['r1']},runtime_identity=identity,source_sha256=src,verification_current=True)

class ProjectionTests(unittest.TestCase):
    def test_current_base_final_historical_distinct(self):
        x=fixture();old=deepcopy(x);p=project_current_scores(**x)
        self.assertEqual((25,30,31,1),(p['historical'][METRICS[0]],p['base'][METRICS[0]],p['final'][METRICS[0]],p['delta']))
        self.assertEqual(x,old);self.assertEqual(sidebar_score_label(25,p),'Verified draft 31/100 · Base 30')
        self.assertNotIn('approval_ready',p)
    def test_approved_and_saved_labels(self):
        x=fixture();x['generation']['status']='approved';p=project_current_scores(**x)
        self.assertEqual(sidebar_score_label(25,p),'Verified approved 31/100 · Base 30')
        self.assertEqual(sidebar_score_label(25,None),'Saved score 25/100');self.assertEqual(sidebar_score_label(None,None),'')
    def test_scope_status_and_ownership_rejected(self):
        for key,value in [('current_scope_status','stale'),('scope_activation_status','pending_confirmation'),('application_id',160),('decision_fingerprint','other')]:
            with self.subTest(key=key):
                x=fixture();x['decision'][key]=value
                with self.assertRaises(ValueError):project_current_scores(**x)
    def test_wrong_generation_and_archive_rejected(self):
        for key,value in [('generation_id','other'),('status','archived'),('application_id',160)]:
            with self.subTest(key=key):
                x=fixture();x['generation'][key]=value
                with self.assertRaises(ValueError):project_current_scores(**x)
    def test_stale_receipt_source_and_runtime_rejected(self):
        for key,value in [('verification_current',False),('source_sha256','c'*64),('runtime_identity',{'scoring_version':'old'})]:
            with self.subTest(key=key):
                x=fixture();x[key]=value
                with self.assertRaises(ValueError):project_current_scores(**x)
    def test_changed_exact_jd_or_scope_rejected(self):
        for key,value in [('application_id',160),('raw_text','changed'),('canonical_requirement_fingerprint','other'),('canonical_requirement_ids',['r2'])]:
            with self.subTest(key=key):
                x=fixture();x['exact_jd'][key]=value
                with self.assertRaises(ValueError):project_current_scores(**x)
    def test_tampered_scores_and_preview_rejected(self):
        x=fixture();x['receipt']['after_stable_analysis'][METRICS[0]]=99
        with self.assertRaises(ValueError):project_current_scores(**x)
        x=fixture();x['receipt'].pop('verification_id')
        with self.assertRaises(ValueError):project_current_scores(**x)
    def test_adopted_scope_and_negative_delta_not_approval(self):
        x=fixture();x['decision']['scoring_policy_transition']={'acceptance_fingerprint':'accepted'};x['historical_report']['stable_analysis']['canonical_requirements'].append({'requirement_id':'removed'})
        p=project_current_scores(**x);self.assertEqual(p['base'][METRICS[0]],30)
        x=fixture();a=x['receipt']['after_stable_analysis'];a[METRICS[0]]=29;fa=x['receipt']['document_analysis']['final'];fa['stable_analysis_fingerprint']=fp(a);fa['fingerprint']=fp({k:v for k,v in fa.items() if k!='fingerprint'});x['receipt']['comparison'].update(after_score=29,score_delta=-1)
        p=project_current_scores(**x);self.assertEqual(p['delta'],-1);self.assertNotIn('approval_ready',p)
    def test_no_active_generation_no_db_lookup(self):
        d={};self.assertIsNone(load_active_score(159,{},d));self.assertIn('binding',d['reason']);self.assertIsNone(load_active_score(159,{'phase9e_binding':fixture()['decision']}))

class ProductionLoaderTests(unittest.TestCase):
    def test_production_loader_uses_active_generation_and_native_gate(self):
        from contextlib import ExitStack
        from unittest.mock import patch
        x=fixture();g=x['generation'];w={'phase9e_binding':x['decision'],'loaded_generation':g,'approved_generation':{'generation_id':'not-active'}}
        functions={
            'database.db_manager.get_application_by_id':{'report':x['historical_report']},
            'database.jd_library_manager.get_exact_job_description_for_application':x['exact_jd'],
            'database.tailoring_verification_manager.get_latest_tailoring_verification':x['receipt'],
            'database.phase9f_tailoring_execution_manager.get_phase9f_application_confirmation':{'confirmed':True},
            'database.phase9f_tailoring_execution_manager.get_phase9f_tailoring_execution':{'source_artifact':{'sha256':x['source_sha256']}},
            'database.phase9f_tailoring_execution_manager._resolve_prepared_source_artifact':{'sha256':x['source_sha256']},
            'tailoring.phase8_auto_verification.phase8_verification_is_current':True,
            'tailoring.job_match_ab_analysis.current_ab_identity':x['runtime_identity'],
        }
        with ExitStack() as stack:
            mocks={k:stack.enter_context(patch(k,return_value=v)) for k,v in functions.items()}
            p=load_active_score(159,w);self.assertIsNotNone(p);self.assertEqual(p['generation_id'],'gen')
            mocks['database.tailoring_verification_manager.get_latest_tailoring_verification'].assert_called_once_with(159,'gen')
            gate=mocks['tailoring.phase8_auto_verification.phase8_verification_is_current'];gate.assert_called_once_with(x['receipt'],g)
            gate.return_value=False
            self.assertIsNone(load_active_score(159,w))
            self.assertEqual(mocks['database.phase9f_tailoring_execution_manager._resolve_prepared_source_artifact'].call_count,1)

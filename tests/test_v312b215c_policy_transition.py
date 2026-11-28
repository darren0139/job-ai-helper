"""Transition proof, negative controls, and real native DOCX recheck."""
import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tailoring import phase9f_policy_transition_v312b215c as transition


def _row(rid, text, importance='core'):
    return {'requirement_id':rid,'text':text,'importance':importance,'atomic_group_id':'grp_'+rid,'group_weight_fraction':1.0}


def _snapshot(rows, raw='Requirements\nPython\nAdditional information\nCompany values'):
    rows=copy.deepcopy(rows)
    compact=[{'requirement_id':str(r.get('requirement_id') or ''),'text':' '.join(str(r.get('text') or '').split()),'importance':str(r.get('importance') or ''),'atomic_group_id':str(r.get('atomic_group_id') or ''),'group_weight_fraction':r.get('group_weight_fraction')} for r in rows]
    return {'library_jd_id':1,'canonical_jd_id':'job1','source_version_id':'jdv1','raw_jd_sha256':hashlib.sha256(raw.encode()).hexdigest(),
            'source_application_link':{'application_id':1,'source_version_id':'jdv1'},'raw_text':raw,'jd_profile':{'company':'Synthetic'},
            'canonical_requirements':rows,'canonical_requirement_ids':sorted(r['requirement_id'] for r in rows),'canonical_requirement_fingerprint':transition._fingerprint(compact)}


def _decision(old):
    return {'scope_activation_status':'active','current_scope_status':'stale','current_jd_snapshot':copy.deepcopy(old),
            'semantic_identity':{'current_jd':{k:copy.deepcopy(old[k]) for k in (*transition.JD_FIELDS,*transition.SCOPE_FIELDS)}},
            'comparison':{'stable_analysis_snapshot':{'scoring_version':'stable-evidence-v1.16-phase6d20','canonical_requirements':copy.deepcopy(old['canonical_requirements'])}}}


class PureTransitionTests(unittest.TestCase):
    def setUp(self):
        self.real=_row('a','Python');self.invalid=_row('b','Company values')
        self.old=_snapshot([self.real,self.invalid]);self.new=_snapshot([self.real]);self.decision=_decision(self.old)
    def classify(self):
        return transition.classify_transition(decision=self.decision,current_jd=self.new,active_scorer=transition.CURRENT_SCORER)
    def test_removal_only_and_immutable_inputs(self):
        before=copy.deepcopy((self.decision,self.new));r=self.classify()
        self.assertEqual(r['previous_count'],2);self.assertEqual(r['current_count'],1);self.assertEqual(r['historical_requirement_ids'],['a','b']);self.assertEqual(r['surviving_requirement_ids'],['a']);self.assertEqual((self.decision,self.new),before)
    def test_exact_text_profile_and_link_changes_rejected(self):
        for key,value in [('raw_text','Changed'),('jd_profile',{}),('source_version_id','other'),('source_application_link',{'application_id':9})]:
            with self.subTest(key=key):
                self.new=_snapshot([self.real]);self.new[key]=value
                with self.assertRaises(ValueError):self.classify()
    def test_new_or_changed_rows_rejected(self):
        for rows in ([self.real,_row('c','Java')],[_row('a','Python','required')],[self.real,self.invalid],[]):
            with self.subTest(rows=rows):
                self.new=_snapshot(rows)
                with self.assertRaises(ValueError):self.classify()
    def test_wrong_policy_reviewed_and_unconfirmed_rejected(self):
        with self.assertRaises(ValueError):transition.classify_transition(decision=self.decision,current_jd=self.new,active_scorer='future')
        self.decision['comparison']['stable_analysis_snapshot']['matching_policy_identity']={'review':'custom'}
        with self.assertRaises(ValueError):self.classify()
        self.decision=_decision(self.old);self.decision['scope_activation_status']='pending_confirmation'
        with self.assertRaises(ValueError):self.classify()
    def test_tampered_fingerprint_rejected(self):
        self.new['canonical_requirement_fingerprint']='0'*64
        with self.assertRaises(ValueError):self.classify()
    def test_final_hash_generation_and_snapshot_rejected(self):
        generation={'application_id':1,'generation_id':'a','status':'draft','fit_result':{'fit_one_page':True,'page_count':1}}
        prior={'application_id':1,'generation_id':'a','comparison_valid':True,'verified_generation_snapshot_fingerprint':'snap','document_analysis':{'final_document_sha256':'a'*64}}
        def verify():transition.authenticate_final(generation=generation,prior=prior,snapshot_fingerprint='snap',final_sha='a'*64)
        verify()
        for key,value in [('generation_id','b'),('application_id',2),('verified_generation_snapshot_fingerprint','changed'),('document_analysis',{'final_document_sha256':'b'*64}),('comparison_valid',False)]:
            saved=copy.deepcopy(prior);prior[key]=value
            with self.assertRaises(ValueError):verify()
            prior=saved
    def test_execution_evidence_scope_and_source_integrity(self):
        fp=transition._fingerprint
        evidence={'policy_version':'p','rows':[{'id':1}]};evidence['snapshot_fingerprint']=fp(evidence)
        section={'policy_version':'p','selected_evidence_fingerprint':fp([]),'selected_evidence':[],'opportunity':{}}
        section['scope_fingerprint']=fp({k:v for k,v in section.items() if k not in ('selected_evidence','opportunity')})
        artifact={'policy_version':'p','artifact_type':'docx','sha256':'a'*64,'byte_size':1}
        scope={'application_id':1,'confirmation_fingerprint':'c','phase9e_decision_fingerprint':'d','starting_snapshot_fingerprint':'s','source':{'id':1},'exact_jd':{'id':1},'frozen_content':{'id':1}}
        identity={k:copy.deepcopy(scope[k]) for k in ('source','exact_jd','frozen_content')}
        identity.update(evidence_snapshot={k:evidence[k] for k in ('policy_version','snapshot_fingerprint')},section_scope={k:section[k] for k in ('scope_fingerprint','selected_evidence_fingerprint')},source_artifact=copy.deepcopy(artifact))
        e={**scope,'semantic_identity':identity,'execution_fingerprint':fp(identity),'evidence_snapshot':evidence,'evidence_snapshot_fingerprint':evidence['snapshot_fingerprint'],'section_scope':section,'section_scope_fingerprint':section['scope_fingerprint'],'source_artifact':artifact}
        transition.authenticate_execution(e,scope)
        for field,mutator in [('evidence_snapshot',lambda x:x['rows'].append({'id':2})),('section_scope',lambda x:x.update(policy_version='changed')),('source_artifact',lambda x:x.update(sha256='b'*64)),('semantic_identity',lambda x:x.update(exact_jd={'id':2}))]:
            bad=copy.deepcopy(e);mutator(bad[field]);
            with self.assertRaises(ValueError):transition.authenticate_execution(bad,scope)


class NativeTransitionTests(unittest.TestCase):
    def test_real_ncs_native_recheck_keeps_document_and_history(self):
        from analysis_stability import stable_evidence_scoring as scorer
        from tailoring.phase8_verification import build_phase8_generation_snapshot_fingerprint
        from tests.test_v312b215_jd_eligibility import JD, PROFILE, OLD, REMOVED, make_handoff_fixture_docx
        from tests.b213_policy_support import ACTIVE_B222D1
        self.assertEqual(scorer.SCORING_VERSION,ACTIVE_B222D1)
        with patch.object(scorer,'_V312A17_RUNTIME_ACTIVE',False):
            old_rows=scorer.canonicalise_requirements(PROFILE,JD)['requirements']
        new_rows=scorer.canonicalise_requirements(PROFILE,JD)['requirements']
        old=_snapshot(old_rows,JD);new=_snapshot(new_rows,JD)
        old['jd_profile']=copy.deepcopy(PROFILE);new['jd_profile']=copy.deepcopy(PROFILE)
        decision=_decision(old);decision['comparison']['stable_analysis_snapshot']['scoring_version']=OLD
        t=transition.classify_transition(decision=decision,current_jd=new,active_scorer=scorer.SCORING_VERSION)
        self.assertEqual([r['requirement_id'] for r in t['removed_requirements']],REMOVED)
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp)/'base.docx';final=Path(temp)/'final.docx';text=make_handoff_fixture_docx(base);final.write_bytes(base.read_bytes());data=base.read_bytes();sha=hashlib.sha256(data).hexdigest()
            profile={'name':'Synthetic Software Engineer','skills':{'Tools':['Unity','C#']},'projects':[],'education':[],'experience':[]}
            baseline={'raw_jd_text':JD,'jd_profile':PROFILE,'raw_resume_text':text,'resume_profile':profile,'stable_analysis':{'scoring_version':OLD,'canonical_requirements':old_rows},'meta':{}}
            gen={'application_id':1,'generation_id':'synthetic-fitted','status':'draft','projects':{'recommended_projects':[]},'skills':{'skill_lines':[{'category':'Tools','items':['Unity','C#']}]},'fit_result':{'docx_path':str(final),'fit_one_page':True,'page_count':1}}
            prior={'application_id':1,'generation_id':gen['generation_id'],'comparison_valid':True,'verified_generation_snapshot_fingerprint':build_phase8_generation_snapshot_fingerprint(gen),'document_analysis':{'final_document_sha256':sha},'starting_document_contract':{'selected_base_docx_sha256':sha},'before_stable_analysis':baseline['stable_analysis'],'after_stable_analysis':baseline['stable_analysis']}
            before=copy.deepcopy((baseline,gen,prior));result=transition.build_preview(transition=t,baseline_report=baseline,generation=gen,source_artifact={'artifact_type':'docx','artifact_bytes':data,'sha256':sha,'byte_size':len(data)},prior=prior)
            self.assertEqual(result['status'],'native_preview_completed');self.assertEqual(len(result['native_after_analysis']['canonical_requirements']),12)
            self.assertFalse(result['approval_ready']);self.assertFalse(result['saved_as_phase8']);self.assertFalse(result['blueprint_ready']);self.assertEqual((baseline,gen,prior),before);self.assertEqual(final.read_bytes(),data);self.assertEqual(base.read_bytes(),data)
            self.assertEqual(result['native_after_analysis']['scoring_version'],ACTIVE_B222D1)

if __name__=='__main__':unittest.main()

import copy
import unittest
from tailoring.phase9f_score_authority_v312b216a import compare, inspect_receipt, fp, sha, METRICS


def fixture():
    def analysis(score,version):
        return dict(zip(METRICS,(score,25,50,67)),scoring_version=version,canonical_requirements=[{'requirement_id':'r1','text':'Python','importance':'core','match_value':0.55}])
    before,after=analysis(30,'new'),analysis(31,'new')
    ctx={'decision_fingerprint':'d','starting_snapshot_fingerprint':'s'}
    auth={'input_authority':'ACTUAL_RESUME_DOCUMENT','jd_text_sha256':sha('Python'),'resume_text_sha256':'t'*64,'stable_analysis_fingerprint':fp(before)};auth['fingerprint']=fp(auth)
    final_auth=copy.deepcopy(auth);final_auth.pop('fingerprint');final_auth['stable_analysis_fingerprint']=fp(after);final_auth['fingerprint']=fp(final_auth)
    hist={'meta':{'phase9e_starting_context':ctx},'stable_analysis':analysis(32,'old'),'raw_jd_text':'Python'}
    receipt={'application_id':156,'generation_id':'g','comparison_valid':True,'starting_document_contract':{'mode':'selected_base_docx_only','selected_base_docx_sha256':'a'*64,'selected_base_resume_text_sha256':'t'*64,'selected_base_document_analysis_fingerprint':auth['fingerprint']},'document_analysis':{'initial':auth,'final':final_auth,'final_document_sha256':'b'*64},'selected_base_analysis':{'document_analysis':copy.deepcopy(auth),'stable_analysis':copy.deepcopy(before),'starting_context':copy.deepcopy(ctx)},'before_stable_analysis':before,'after_stable_analysis':after,'comparison':{'before_score':30,'after_score':31,'score_delta':1,'required_core_coverage_delta':2}}
    return hist,receipt

class AuthorityTests(unittest.TestCase):
    def inspect(self,h,r):return inspect_receipt(historical_report=h,receipt=r,application_id=156,generation_id='g',expected_decision='d')
    def test_distinct_historical_and_native_delta_immutable(self):
        h,r=fixture();saved=copy.deepcopy((h,r));a=self.inspect(h,r);self.assertEqual(a['historical_to_current_base']['before_metrics'][METRICS[0]],32);self.assertEqual(a['native_score_delta'],1);self.assertEqual((h,r),saved)
    def test_other_application_or_jd(self):
        h,r=fixture();r['application_id']=158
        with self.assertRaises(ValueError):self.inspect(h,r)
        h,r=fixture();h['raw_jd_text']='Java'
        with self.assertRaises(ValueError):self.inspect(h,r)
    def test_changed_decision(self):
        h,r=fixture();h['meta']['phase9e_starting_context']['decision_fingerprint']='other'
        with self.assertRaises(ValueError):self.inspect(h,r)
    def test_tampered_authority_or_score(self):
        h,r=fixture();r['before_stable_analysis'][METRICS[0]]=99
        with self.assertRaises(ValueError):self.inspect(h,r)
        h,r=fixture();r['comparison']['score_delta']=100
        with self.assertRaises(ValueError):self.inspect(h,r)
    def test_removed_added_and_changed_rows(self):
        h,r=fixture();old=h['stable_analysis'];new=r['before_stable_analysis'];old['canonical_requirements'].append({'requirement_id':'old'});new['canonical_requirements'].append({'requirement_id':'new'});new['canonical_requirements'][0]['match_value']=1
        a=compare(old,new);self.assertEqual(a['removed_ids'],['old']);self.assertEqual(a['added_ids'],['new']);self.assertEqual(a['changed_rows'][0]['changed_fields'],['match_value'])
    def test_native_scope_or_policy_mismatch(self):
        h,r=fixture();r['after_stable_analysis']['scoring_version']='other'
        with self.assertRaises(ValueError):self.inspect(h,r)
        h,r=fixture();r['after_stable_analysis']['canonical_requirements'].append({'requirement_id':'other'})
        with self.assertRaises(ValueError):self.inspect(h,r)
    def test_duplicate_ids(self):
        h,r=fixture();h['stable_analysis']['canonical_requirements']*=2
        with self.assertRaises(ValueError):self.inspect(h,r)

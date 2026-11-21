from __future__ import annotations
import copy,hashlib,importlib.util, tempfile, unittest
from pathlib import Path

P=Path(__file__).resolve().parents[1]/'tailoring'/'phase9f_verified_best_of_v291.py'
if not P.is_file():P=Path(__file__).with_name('phase9f_verified_best_of_v291.py')
spec=importlib.util.spec_from_file_location('phase9f_verified_best_of_v291',P)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def result(sha,score,match='direct',version='scorer-v1',selected_valid=True):
    return {'comparison_valid':True,'fit_one_page':True,
       'document_analysis':{'initial':{'sealed':True},'final':{'sealed':True},'final_document_sha256':sha},
       'job_match_ab':{'comparable':True},
       'selected_base_analysis':{'same_as_initial':False},
       'selected_base_job_match_ab':{'comparable':selected_valid},
       'after_stable_analysis':{'scoring_version':version,'deterministic_alignment_score':score,
            'canonical_requirements':[{'requirement_id':'req-core','importance':'core','match_label':match},
                                      {'requirement_id':'req-opt','importance':'preferred','match_label':'weak'}]},
       'claim_lineage':{'claim_review_required_count':0},'important_regressions':[], 'verdict':'improved'}

class VerifiedBestOfTests(unittest.TestCase):
    def setUp(self):
        self.a='a'*64;self.b='b'*64
    def test_higher_score_candidate_wins(self):
        r=m.compare_native_phase8(original=result(self.a,32),candidate=result(self.b,43),original_sha=self.a,candidate_sha=self.b)
        self.assertEqual(r['winner'],'optimized_candidate');self.assertTrue(r['status']=='verified');self.assertFalse(r['candidate_approved'])
    def test_equal_score_returns_original(self):
        r=m.compare_native_phase8(original=result(self.a,32),candidate=result(self.b,32),original_sha=self.a,candidate_sha=self.b)
        self.assertEqual(r['winner'],'existing_final')
    def test_lower_score_returns_original(self):
        r=m.compare_native_phase8(original=result(self.a,45),candidate=result(self.b,30),original_sha=self.a,candidate_sha=self.b)
        self.assertEqual(r['winner'],'existing_final')
    def test_hard_evidence_regression_blocks_promotion(self):
        r=m.compare_native_phase8(original=result(self.a,32,match='direct'),candidate=result(self.b,44,match='weak'),original_sha=self.a,candidate_sha=self.b)
        self.assertEqual(r['winner'],'existing_final');self.assertEqual(r['hard_regressed_ids'],['req-core'])
    def test_scorer_version_mismatch_refused(self):
        r=m.compare_native_phase8(original=result(self.a,32),candidate=result(self.b,44,version='v17'),original_sha=self.a,candidate_sha=self.b)
        self.assertEqual(r['status'],'withheld')
    def test_source_docx_identity_refused(self):
        r=m.compare_native_phase8(original=result(self.a,32),candidate=result('f'*64,44),original_sha=self.a,candidate_sha=self.b)
        self.assertEqual(r['status'],'withheld')
    def test_selected_base_comparison_missing_is_held(self):
        r=m.compare_native_phase8(original=result(self.a,32),candidate=result(self.b,44,selected_valid=False),original_sha=self.a,candidate_sha=self.b)
        self.assertEqual(r['status'],'withheld')
    def test_claim_review_refused(self):
        b=result(self.b,44);b['claim_lineage']['claim_review_required_count']=3
        r=m.compare_native_phase8(original=result(self.a,32),candidate=b,original_sha=self.a,candidate_sha=self.b)
        self.assertEqual(r['status'],'withheld')
    def test_native_comparability_refused(self):
        a=result(self.a,32);a['job_match_ab']['comparable']=False
        r=m.compare_native_phase8(original=a,candidate=result(self.b,44),original_sha=self.a,candidate_sha=self.b)
        self.assertEqual(r['winner'],'none')
    def test_missing_source_requirements_held(self):
        b=result(self.b,44);b['after_stable_analysis']['canonical_requirements'][0]['requirement_id']='other'
        r=m.compare_native_phase8(original=result(self.a,32),candidate=b,original_sha=self.a,candidate_sha=self.b)
        self.assertEqual(r['status'],'withheld')
    def test_boolean_or_nan_score_refused(self):
        for score in (True,float('nan'),-1,110):
            b=result(self.b,score)
            r=m.compare_native_phase8(original=result(self.a,32),candidate=b,original_sha=self.a,candidate_sha=self.b)
            self.assertEqual(r['status'],'withheld')
    def test_beats_both_source_baselines_when_receipts_are_comparable(self):
        a=result(self.a,35);b=result(self.b,50)
        for row in (a,b):
            initial=result(self.a,27)['after_stable_analysis']
            base=result(self.a,30)['after_stable_analysis']
            row['before_stable_analysis']=initial
            row['selected_base_analysis']['stable_analysis']=base
        x=m.compare_native_phase8(original=a,candidate=b,original_sha=self.a,candidate_sha=self.b)
        self.assertTrue(x['improved_vs_both_baselines'])
        self.assertEqual(x['baseline_deltas']['Selected Base'],20)
    def test_improved_vs_current_but_not_both_baselines(self):
        a=result(self.a,35);b=result(self.b,40)
        for row in (a,b):
            row['before_stable_analysis']=result(self.a,30)['after_stable_analysis']
            row['selected_base_analysis']['stable_analysis']=result(self.a,48)['after_stable_analysis']
        x=m.compare_native_phase8(original=a,candidate=b,original_sha=self.a,candidate_sha=self.b)
        self.assertEqual(x['winner'],'optimized_candidate')
        self.assertFalse(x['improved_vs_both_baselines'])
        self.assertEqual(x['baseline_deltas']['Selected Base'],-8)

    def test_clone_enforces_exact_fitted_bullet_identity(self):
        before={'generation_id':'g1','fit_result':{'fit_one_page':True,'docx_path':'old.docx',
            'tailored_projects_used':{'recommended_projects':[{'title':'Project 1','draft_bullets':['a','b']}]}},'projects':{}}
        proposal={'status':'candidate','projects':[{'project':'Project 1','before':['a','b'],'after':['c','d']}]}
        output={'status':'generated','pages':1,'docx_path':'new.docx','pdf_path':'new.pdf'}
        copy_before=copy.deepcopy(before)
        result=m.build_candidate_scoring_state(original=before,proposal=proposal,output=output)
        self.assertEqual(before,copy_before)
        self.assertEqual(result['fit_result']['tailored_projects_used']['recommended_projects'][0]['draft_bullets'],['c','d'])
        proposal['projects'][0]['before']=['wrong','b']
        with self.assertRaises(ValueError):m.build_candidate_scoring_state(original=before,proposal=proposal,output=output)
    def test_generation_fits_from_bounded_source_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); out=root/'outputs'/'tailored_resumes';out.mkdir(parents=True)
            old=out/'app_156_current.docx';old.write_bytes(b'original docx example')
            audit={'verified':True,'generation_id':'g1','docx_sha256':hashlib.sha256(old.read_bytes()).hexdigest()}
            fit={'fit_one_page':True,'docx_path':str(old)}
            gen={'generation_id':'g1','fit_result':{**fit,
                'tailored_projects_used':{'recommended_projects':[{'title':'Project 1','draft_bullets':['alpha']}]}}}
            prop={'status':'candidate','version':'v26','requires_base_review':False,
                  'projects':[{'project':'Project 1','before':['alpha'],'after':['beta']}]}
            calls=[]
            def optimizer(a,p):calls.append('optimize');return prop
            def generator(**kw):
                calls.append('render');target=out/'optimizations'/'app_156_b.docx';target.parent.mkdir()
                target.write_bytes(b'candidate docx example')
                return {'status':'generated','pages':1,'docx_path':str(target),'pdf_path':str(target.with_suffix('.pdf'))}
            def scorer(*,baseline_report,generation_state,raw_jd_text):
                calls.append('score');d=Path(generation_state['fit_result']['docx_path'])
                return result(hashlib.sha256(d.read_bytes()).hexdigest(),35 if d==old else 44)
            out_result=m.evaluate_existing_vs_candidate(audit=audit,projects={},fit=fit,generation=gen,
                     baseline_report={'meta':{'document_analysis':{ 'signed':True}}},raw_jd_text='role',
                     source_docx=old,repo_root=root,application_id=156,generator=generator,scorer=scorer,optimizer=optimizer)
            self.assertEqual(out_result['winner'],'optimized_candidate');self.assertEqual(calls,['optimize','score','render','score'])
            self.assertEqual(old.read_bytes(),b'original docx example')
    def test_no_document_baseline_never_generates(self):
        calls=[]
        x=m.evaluate_existing_vs_candidate(audit={},projects={},fit={},generation={},baseline_report={},raw_jd_text='',
             source_docx=Path('/missing'),repo_root=Path('/tmp'),application_id=2,
             generator=lambda **kw:calls.append('write'),scorer=lambda **kw:None,optimizer=lambda *a:calls.append('opt'))
        self.assertEqual(x['status'],'withheld');self.assertFalse(calls)
    def test_base_only_requires_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);out=root/'outputs'/'tailored_resumes';out.mkdir(parents=True)
            old=out/'app_156_a.docx';old.write_bytes(b'abcd')
            props={'status':'candidate','requires_base_review':True}
            x=m.evaluate_existing_vs_candidate(audit={'verified':True,'generation_id':'g','docx_sha256':hashlib.sha256(b'abcd').hexdigest()},
              projects={},fit={'fit_one_page':True,'docx_path':str(old)},generation={'generation_id':'g','fit_result':{'docx_path':str(old)}},
              baseline_report={'meta':{'document_analysis':{'sealed':True}}},raw_jd_text='job',source_docx=old,repo_root=root,
              application_id=156,generator=lambda **kw:None,scorer=lambda **kw:None,optimizer=lambda *args:props)
            self.assertEqual(x['status'],'needs_base_review')

if __name__=='__main__':unittest.main()

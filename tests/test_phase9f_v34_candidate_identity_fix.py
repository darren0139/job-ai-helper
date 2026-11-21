"""V3.4 regression: variable-count candidate is scoreable without weakening identity guards."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from tailoring.phase9f_verified_best_of_v291 import build_candidate_scoring_state
from tailoring.phase9f_automatic_bestof_v30 import evaluate_auto
from tailoring.phase9f_auto_optimize_v31 import VERSION as V31_VERSION
from tailoring.phase9f_evidence_optimizer_v33 import VERSION as V33_VERSION


def fixture(version=V33_VERSION, variable=True):
    counts = (6, 4, 1, 1, 1)
    titles = ('Job AI Helper', 'QueryAI', 'Workout Buddy', 'The Great Migration', 'CyberSphere')
    entries = [{'title': title, 'draft_bullets': [f'{title} original bullet {i}' for i in range(count)]}
               for title,count in zip(titles,counts)]
    before = [list(x['draft_bullets']) for x in entries]
    after = deepcopy(before)
    # Similar to App 156: drop one duplicate-looking QueryAI bullet, 13 -> 12.
    after[1].pop(2)
    project_rows=[{'project': e['title'], 'before': b, 'after': a,
                   'before_count':len(b), 'after_count':len(a)}
                  for e,b,a in zip(entries,before,after)]
    generation={'generation_id':'generation156', 'fit_result':{'fit_one_page':True,
                 'docx_path':'original.docx','pdf_path':'original.pdf',
                 'fitting_input_snapshot':{'old':True},
                 'remaining_active_reductions':[{'removed':True}],
                 'tailored_projects_used':{'recommended_projects':entries}}}
    proposal={'version':version,'status':'candidate','changed':True,
              'variable_bullet_counts':variable,'project_set_unchanged':True,
              'projects':project_rows,'requires_base_review':False,
              'recorded_edits':[{'project':'QueryAI','reason':'redundancy_reduction'}]}
    output={'status':'generated','pages':1,'docx_path':'candidate.docx','pdf_path':'candidate.pdf'}
    return generation,proposal,output


class CandidateIdentity(unittest.TestCase):
    def test_app156_13_to_12_keeps_exact_starting_identity_and_original_immutable(self):
        generation,proposal,output=fixture()
        saved=deepcopy((generation,proposal,output))
        changed=build_candidate_scoring_state(original=generation,proposal=proposal,output=output)
        self.assertEqual((generation,proposal,output),saved)
        proj=changed['fit_result']['tailored_projects_used']['recommended_projects']
        self.assertEqual([len(x['draft_bullets']) for x in proj],[6,3,1,1,1])
        self.assertEqual(changed['fit_result']['docx_path'],'candidate.docx')
        self.assertFalse(changed['fit_result']['candidate_is_approved'])
        self.assertNotIn('fitting_input_snapshot',changed['fit_result'])
        self.assertEqual(changed['fit_result']['remaining_active_reductions'],[])

    def test_v31_variable_count_uses_same_strict_authority(self):
        gen,p,o=fixture(version=V31_VERSION)
        p['projects'][1]['after'].append('QueryAI other relevant bullet')
        p['projects'][1]['after_count']=4
        out=build_candidate_scoring_state(original=gen,proposal=p,output=o)
        self.assertEqual(len(out['fit_result']['tailored_projects_used']['recommended_projects'][1]['draft_bullets']),4)

    def test_v26_stays_fixed_count(self):
        gen,p,o=fixture(variable=False)
        with self.assertRaisesRegex(ValueError,'Fixed-count'):
            build_candidate_scoring_state(original=gen,proposal=p,output=o)

    def test_unauthorized_variable_modes_fail_closed(self):
        for mutate in (
            lambda p:p.update(version='forged'),
            lambda p:p.update(project_set_unchanged=False),
            lambda p:p.pop('project_set_unchanged'),
        ):
            gen,p,o=fixture();mutate(p)
            with self.subTest(proposal=p):
                with self.assertRaisesRegex(ValueError,'ownership authority'):
                    build_candidate_scoring_state(original=gen,proposal=p,output=o)

    def test_stale_or_reordered_starting_bullets_fail_closed(self):
        for change in ('bad text','reorder'):
            gen,p,o=fixture()
            if change=='bad text':p['projects'][1]['before'][0]='foreign bullet'
            else:p['projects'][1]['before'].reverse()
            with self.subTest(change=change):
                with self.assertRaisesRegex(ValueError,'starting bullet text/order'):
                    build_candidate_scoring_state(original=gen,proposal=p,output=o)

    def test_project_set_cannot_change_or_duplicate(self):
        gen,p,o=fixture();p['projects'][1]['project']='different project'
        with self.assertRaisesRegex(ValueError,'project identities'):
            build_candidate_scoring_state(original=gen,proposal=p,output=o)
        gen,p,o=fixture();p['projects'][1]['project']=p['projects'][0]['project']
        with self.assertRaisesRegex(ValueError,'count changed|ownership'):
            build_candidate_scoring_state(original=gen,proposal=p,output=o)

    def test_count_receipt_and_limits_fail_closed(self):
        gen,p,o=fixture();p['projects'][1]['after_count']=4
        with self.assertRaisesRegex(ValueError,'count receipts'):
            build_candidate_scoring_state(original=gen,proposal=p,output=o)
        gen,p,o=fixture();p['projects'][1]['after']=[];p['projects'][1]['after_count']=0
        with self.assertRaisesRegex(ValueError,'out-of-range'):
            build_candidate_scoring_state(original=gen,proposal=p,output=o)
        gen,p,o=fixture();p['projects'][1]['after']=['a']*9;p['projects'][1]['after_count']=9
        with self.assertRaisesRegex(ValueError,'out-of-range'):
            build_candidate_scoring_state(original=gen,proposal=p,output=o)

    def test_legacy_equal_count_still_supported(self):
        gen,p,o=fixture(variable=False)
        p['projects'][1]['after']=list(p['projects'][1]['before'])
        p['projects'][1]['after_count']=len(p['projects'][1]['after'])
        out=build_candidate_scoring_state(original=gen,proposal=p,output=o)
        self.assertEqual(out['fit_result']['fit_one_page'],True)


class RunnerReceipts(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        base=self.root/'outputs'/'tailored_resumes';base.mkdir(parents=True)
        self.a=base/'app_156_fit.docx';self.a.write_bytes(b'original-docx')
        self.a_sha=sha256(self.a.read_bytes()).hexdigest()
        self.g,self.p,self.o=fixture()
        self.g['fit_result']['docx_path']=str(self.a)
        self.fit=self.g['fit_result']
        self.audit={'verified':True,'generation_id':self.g['generation_id'],'docx_sha256':self.a_sha}
        self.baseline={'raw_jd_text':'Qualifications: React','stable_analysis':{
            'canonical_requirements':[{'requirement_id':'r1','importance':'core'},
                                      {'requirement_id':'r2','importance':'preferred'}]}}
    def run_flow(self, proposal=None):
        def generator(**kwargs):
            d=self.root/'outputs'/'tailored_resumes'/'optimizations';d.mkdir(exist_ok=True)
            b=d/'app_156_b.docx';b.write_bytes(b'candidate-docx')
            pdf=d/'app_156_b.pdf';pdf.write_bytes(b'fake-pdf-for-runner-test')
            return {'status':'generated','pages':1,'docx_path':str(b),'pdf_path':str(pdf)}
        def scorer(**kwargs):
            generation_state=kwargs['generation_state']
            if Path(kwargs['docx_path'])!=self.a:
                self.assertEqual(len(generation_state['fit_result']['tailored_projects_used']['recommended_projects'][1]['draft_bullets']),3)
            return {'actual_docx_evidence':True,'docx_sha256':kwargs['expected_sha256'],
                    'claim_review_required_count':0,'scoring_version':'scorer-v1',
                    'deterministic_alignment_score':33 if Path(kwargs['docx_path'])==self.a else 37,
                    'canonical_requirements':[
                        {'requirement_id':'r1','importance':'core','match_label':'direct'},
                        {'requirement_id':'r2','importance':'preferred','match_label':'weak'}]}
        return evaluate_auto(audit=deepcopy(self.audit),projects={},fit=deepcopy(self.fit),
               generation=deepcopy(self.g),baseline_report=deepcopy(self.baseline),
               raw_jd_text='Qualifications: React',source_docx=self.a,repo_root=self.root,
               application_id=156,optimizer=lambda a,p:deepcopy(self.p if proposal is None else proposal),
               generator=generator,scorer=scorer)

    def test_app156_variable_count_reaches_native_score_and_verdict(self):
        saved=deepcopy(self.g)
        res=self.run_flow()
        self.assertEqual(res['status'],'verified',res)
        self.assertEqual(res['winner'],'optimized_candidate')
        self.assertEqual(res['delta'],4)
        self.assertFalse(res['candidate_approved'])
        self.assertEqual(self.g,saved)
        self.assertEqual(self.a.read_bytes(),b'original-docx')

    def test_withheld_identity_mismatch_preserves_proposal_and_stage(self):
        p=deepcopy(self.p)
        p['projects'][1]['before'][0]='wrong source line'
        res=self.run_flow(proposal=p)
        self.assertEqual(res['status'],'withheld')
        self.assertEqual(res['winner'],'existing_final')
        self.assertEqual(res['verification_stage'],'verify_candidate_scoring_state')
        self.assertEqual(res['proposal'],p)
        self.assertFalse(res['candidate_verified'])
        self.assertEqual(self.a.read_bytes(),b'original-docx')


class UIContract(unittest.TestCase):
    def test_manual_retry_only_on_user_click_with_full_guarded_runner(self):
        ui=Path(__file__).resolve().parents[1]/'tailoring'/'phase9f_automatic_bestof_v30_ui.py'
        body=ui.read_text(encoding='utf-8')
        self.assertIn("result.get('status')=='withheld' and run_mode in ('v33-evidence','v35-relevance')",body)
        self.assertIn('Retry native comparison using the existing fitted résumé',body)
        self.assertIn('retry=evaluate_auto(audit=audit,projects=projects,fit=fit,',body)
        self.assertIn("'verification_stage': result.get('verification_stage') or ''",body)
        self.assertIn('Compare the existing fitted résumé with a JD-aware alternative',body)
        self.assertIn("'manual_existing_fit_trial':True",body)
        self.assertIn("mode_receipt.get('manual_existing_fit_trial') is True",body)


if __name__=='__main__':unittest.main()

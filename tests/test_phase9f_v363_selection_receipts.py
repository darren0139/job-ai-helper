"""V3.6.3 transparent receipts and adversarial weak-resume negative controls.

The synthetic fixture tests the *proxy*. Real scorer/one-page comparisons require
additional repository-native fixtures and must not be marked as proven here.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from tailoring.phase9f_v363_selection_receipts import build_bullet_selection_calculation
from tailoring.phase9f_v361_approval_floor import assess_phase9f_approval_floor
from tailoring.phase9f_certified_selection_v36 import _solve

FIXTURE = Path(__file__).parent / 'fixtures' / 'phase9f_v363_weak_resume_challenge.json'


def sample():
    return {'source_comparison':{'projects':[{'project':'Synthetic API Project','candidates':[
        {'text':'Weak Base task description','source_labels':['Selected Base'],
         'in_original_a':True,'selected_for_proposed_b':False,'saved_jd_ids':['req_testing'],
         'v35_jd_term_hits':[],'word_count':8,'standalone_saved_coverage_points':9},
        {'text':'Built Python unit tests and automated CI','source_labels':['Evidence Library'],
         'in_original_a':False,'selected_for_proposed_b':True,'saved_jd_ids':['req_testing','req_ci'],
         'v35_jd_term_hits':['python','unit','ci'],'word_count':8,
         'standalone_saved_coverage_points':21},
        {'text':'Python Python unit testing CI deployment testing','source_labels':['Evidence Library'],
         'in_original_a':False,'selected_for_proposed_b':False,'saved_jd_ids':['req_testing'],
         'v35_jd_term_hits':['python','unit','ci','deployment'],'word_count':8,
         'standalone_saved_coverage_points':9}
    ]}]},'baseline_points':9,'proposed_points':21,'baseline_words':8,'proposed_words':8,
      'mathematical_certificate':{'status':'optimal_proxy','solver':'SciPy MILP / HiGHS',
      'optimality_gap':0.0,'phase_receipts':[
          {'priority':'weighted_saved_JD_coverage','minimization_objective':-21000,'status':'optimal'},
          {'priority':'distinct_JD_terms_minus_overlap','minimization_objective':-30,'status':'optimal'},
          {'priority':'membership_changes','minimization_objective':1,'status':'optimal'},
          {'priority':'source_bullet_words','minimization_objective':8,'status':'optimal'}]}}


class SelectionReceipts(unittest.TestCase):
    def test_every_source_row_explains_unique_and_unselected_coverage(self):
        proposal=sample();before=copy.deepcopy(proposal)
        result={'status':'verified','winner':'existing_final','reason':'Scores tie; keep A.',
                'v35_trial_receipts':[{'trial':1,'status':'verified','a_score':31,
                                       'b_score':31,'native_delta':0,'winner':'existing_final'}],
                'a_vs_starting':{'status':'verified','initial_comparison_status':'unavailable',
                                 'selected_base_comparison_status':'unavailable'}}
        receipt=build_bullet_selection_calculation(proposal,result)
        self.assertEqual(receipt['status'],'available')
        self.assertEqual(receipt['objective_stages'][0]['interpreted_maximum_or_cost'],21.0)
        self.assertEqual(receipt['summary']['saved_jd_ids_in_b'],['req_ci','req_testing'])
        self.assertEqual(receipt['rows'][1]['exclusive_jd_ids_in_b'],['req_ci','req_testing'])
        self.assertFalse(receipt['rows'][2]['potential_new_jd_ids'])
        self.assertEqual(receipt['actual_verification']['winner'],'existing_final')
        self.assertTrue(receipt['proxy_is_not_native_optimality'])
        self.assertEqual(proposal,before)
        json.dumps(receipt)

    def test_no_made_up_head_to_head_cause_or_native_score(self):
        proposal=sample()
        proposal['source_comparison']['projects'][0]['candidates'][1]['saved_jd_ids']=['req_testing']
        proposal['source_comparison']['projects'][0]['candidates'][0]['selected_for_proposed_b']=True
        receipt=build_bullet_selection_calculation(proposal,{'status':'not_run'})
        self.assertEqual(receipt['rows'][1]['shared_jd_ids_in_b'],['req_testing'])
        self.assertFalse(receipt['source_competitions'][0]['conclusion'].startswith('Library wins'))
        self.assertEqual(receipt['actual_verification']['trials'],[])

    def test_missing_proposal_is_withheld_not_invented(self):
        got=build_bullet_selection_calculation({}, {'status':'no_proxy_gain'})
        self.assertEqual(got['status'],'unavailable')
        self.assertEqual(got['rows'],[])

    def test_synthetic_worse_final_is_blocked_even_with_valid_document_hash(self):
        """Score-floor negative control, not a test of real DOCX rendering."""
        digest = 'b'*64
        def ab(before,after):
            one={'requirement_id':'req_testing','importance':'core','final_match':'weak'}
            return {'comparable':True,
                'summary':{'initial_score':before,'tailored_score':after,
                           'score_delta':after-before},
                'requirements':[{'requirement_id':'req_testing','initial':dict(one),
                                 'tailored':dict(one)}]}
        data={'generation_id':'test-synthetic','fit_one_page':True,
              'comparison_valid':True,'approval_ready':True,'verdict':'maintained',
              'document_analysis':{'final_document_sha256':digest},
              'job_match_ab':ab(40,39),
              'selected_base_analysis':{'same_as_initial':False},
              'selected_base_job_match_ab':ab(41,39)}
        refused=assess_phase9f_approval_floor(
            data,generation_id='test-synthetic',docx_sha256=digest)
        self.assertFalse(refused['ready'])
        self.assertIn('regressed',refused['reason'])

    def test_missing_vs_wrong_hash_phase8_floor_reasons_are_distinct(self):
        case={'generation_id':'g','fit_one_page':True,'comparison_valid':True,'approval_ready':True}
        missing=assess_phase9f_approval_floor(case,generation_id='g',docx_sha256='a'*64)
        self.assertIn('Missing Phase 8 actual fitted DOCX',missing['reason'])
        case['document_analysis']={'final_document_sha256':'b'*64}
        mismatch=assess_phase9f_approval_floor(case,generation_id='g',docx_sha256='a'*64)
        self.assertIn('differs',mismatch['reason'])
        self.assertFalse(missing['ready']);self.assertFalse(mismatch['ready'])


class PoorResumeSolverChallenge(unittest.TestCase):
    def test_exact_solver_prefers_grounded_coverage_over_keyword_stuffing(self):
        fixture=json.loads(FIXTURE.read_text('utf-8'))
        self.assertTrue(fixture['synthetic_only'])
        bullets=[]
        for idx,row in enumerate(fixture['bullets']):
            bullets.append({'index':idx,'project_index':0,'project':fixture['project'],
                'text':row['text'],'source_labels':[row['source']],
                'ids':frozenset(row['saved_jd_ids']),
                'words':row['words'],'terms':set(row['jd_terms']),
                'original':row['in_fitted_a']})
        model={'bullets':bullets,'groups':[({'project':fixture['project']},{},[0,1,2],(0,))],
           'weights':{r['id']:r['proxy_points'] for r in fixture['jd_requirements']},
           'req_ids':tuple(r['id'] for r in fixture['jd_requirements']),
           'terms':('python','unit','testing','ci','deployment'), 'pairs':[],
           'baseline_indices':frozenset({0}),'baseline_ids':frozenset({'req_testing'}),
           'baseline_count':1,'baseline_words':8,'max_words':fixture['word_proxy_cap']}
        proof=_solve(model,[],time_limit=12)
        self.assertEqual(proof['status'],'optimal_proxy',proof)
        chosen=[fixture['bullets'][i]['id'] for i in proof['selected_indices']]
        self.assertEqual(chosen,[fixture['expected_proxy_choice']])
        self.assertEqual(proof['optimality_gap'],0.0)
        self.assertEqual(proof['phase_receipts'][0]['minimization_objective'],-21000)

    def test_keyword_stuffing_without_corroborated_jd_identity_is_not_proven(self):
        """Negative control: the fixture cannot certify real JD evidence from words alone."""
        fixture=json.loads(FIXTURE.read_text('utf-8'))
        spam=next(b for b in fixture['bullets'] if b['id']=='keyword_stuffed')
        self.assertNotIn('req_ci',spam['saved_jd_ids'])
        self.assertIn('ci',spam['jd_terms'])
        self.assertIn('actual one-page DOCX', ' '.join(fixture['limitations']))


if __name__=='__main__': unittest.main()

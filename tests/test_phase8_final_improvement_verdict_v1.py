"""Fail-closed, file-local tests; no app/database imports or side effects."""
import copy
import importlib.util
import sys
import unittest
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / 'tailoring' / 'phase8_final_improvement_verdict_v1.py'
if not PATH.exists():
    PATH = Path(__file__).resolve().with_name('phase8_final_improvement_verdict_v1.py')
spec = importlib.util.spec_from_file_location('verdict_v1_under_test', PATH)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def analysis(score, labels=('none', 'none')):
    return {
        'scoring_version': 'stable-evidence-v1.16-phase6d20',
        'deterministic_alignment_score': score,
        'canonical_requirements': [
            {'requirement_id': 'req_core', 'text': 'Python', 'importance': 'core', 'match_label': labels[0]},
            {'requirement_id': 'req_optional', 'text': 'RAG', 'importance': 'preferred', 'match_label': labels[1]},
        ],
    }


def ab(before, final):
    return {'comparable': True, 'summary': {'initial_score': before['deterministic_alignment_score'],
            'tailored_score': final['deterministic_alignment_score'],
            'score_delta': final['deterministic_alignment_score']-before['deterministic_alignment_score']}}


def fixture():
    initial = analysis(30, ('weak','none'))
    base = analysis(35, ('weak','weak'))
    final = analysis(40, ('direct','weak'))
    return {
        'document_analysis': {'initial': {'sealed':True}, 'final': {'sealed':True}, 'final_document_sha256':'a'*64},
        'comparison_valid': True, 'fit_one_page': True,
        'before_stable_analysis': initial, 'after_stable_analysis': final,
        'job_match_ab': ab(initial, final),
        'selected_base_analysis': {'same_as_initial':False, 'stable_analysis':base},
        'selected_base_job_match_ab': ab(base, final),
        'claim_lineage': {'claim_review_required_count': 0},
    }


class FinalImprovementVerdictV1Tests(unittest.TestCase):
    def test_actual_final_improved_against_both(self):
        verdict = m.build_final_improvement_verdict(fixture())
        self.assertEqual(verdict['status'], 'improved_vs_both')
        self.assertTrue(verdict['certified_improved'])
        self.assertEqual(verdict['comparisons']['Selected Base']['delta'], 5)

    def test_initial_improves_but_selected_base_declines(self):
        x = fixture()
        x['selected_base_analysis']['stable_analysis']['deterministic_alignment_score'] = 45
        x['selected_base_job_match_ab'] = ab(x['selected_base_analysis']['stable_analysis'], x['after_stable_analysis'])
        verdict=m.build_final_improvement_verdict(x)
        self.assertEqual(verdict['status'],'worse_against_a_baseline')
        self.assertFalse(verdict['certified_improved'])

    def test_base_equal_cannot_claim_improved(self):
        x=fixture()
        x['selected_base_analysis']['stable_analysis']['deterministic_alignment_score']=40
        x['selected_base_job_match_ab']=ab(x['selected_base_analysis']['stable_analysis'], x['after_stable_analysis'])
        self.assertEqual(m.build_final_improvement_verdict(x)['status'], 'not_improved_vs_both')

    def test_hard_regression_blocks_even_if_score_rises(self):
        x=fixture()
        x['before_stable_analysis']['canonical_requirements'][0]['match_label']='direct'
        x['selected_base_analysis']['stable_analysis']['canonical_requirements'][0]['match_label']='direct'
        x['after_stable_analysis']['canonical_requirements'][0]['match_label']='weak'
        y=m.build_final_improvement_verdict(x)
        self.assertEqual(y['status'], 'required_core_regression')
        self.assertTrue(y['comparisons']['Initial']['hard_regressions'])

    def test_preferred_regression_not_hard(self):
        x=fixture()
        x['before_stable_analysis']['canonical_requirements'][1]['match_label']='direct'
        self.assertEqual(m.build_final_improvement_verdict(x)['status'], 'improved_vs_both')

    def test_no_initial_or_selected_base_inferred_for_legacy(self):
        x=fixture();x['document_analysis']=None
        y=m.build_final_improvement_verdict(x,baseline_mode='selected_base')
        self.assertEqual(y['status'],'partial_comparison_only')
        self.assertFalse(y['actual_document'])
        self.assertFalse(y['certified_improved'])

    def test_missing_selected_base_withheld(self):
        x=fixture();x['selected_base_analysis']=None
        y=m.build_final_improvement_verdict(x)
        self.assertEqual(y['status'],'partial_comparison_only')
        self.assertFalse(y['comparisons']['Selected Base']['verified'])

    def test_explicit_same_base_as_initial_is_allowed(self):
        x=fixture();x['selected_base_analysis']={'same_as_initial':True}
        y=m.build_final_improvement_verdict(x)
        self.assertEqual(y['status'],'improved_vs_both')
        self.assertEqual(y['comparisons']['Selected Base']['alias_of'],'Initial')

    def test_missing_actual_docx_hash_blocks_full(self):
        x=fixture();x['document_analysis']['final_document_sha256']='bad'
        y=m.build_final_improvement_verdict(x)
        self.assertEqual(y['status'],'partial_comparison_only')

    def test_frozen_jd_identity_must_be_comparable(self):
        x=fixture();x['job_match_ab']['comparable']=False
        y=m.build_final_improvement_verdict(x)
        self.assertFalse(y['certified_improved'])

    def test_wrong_version_holds_selected_base(self):
        x=fixture();x['selected_base_analysis']['stable_analysis']['scoring_version']='old'
        y=m.build_final_improvement_verdict(x)
        self.assertEqual(y['status'],'partial_comparison_only')
        self.assertIn('Scoring versions', y['comparisons']['Selected Base']['reason'])

    def test_changed_requirement_ids_refused(self):
        x=fixture();x['after_stable_analysis']['canonical_requirements'][0]['requirement_id']='other'
        y=m.build_final_improvement_verdict(x)
        self.assertFalse(y['certified_improved'])
        self.assertFalse(y['comparisons']['Initial']['verified'])

    def test_changed_importance_refused(self):
        x=fixture();x['after_stable_analysis']['canonical_requirements'][0]['importance']='supporting'
        self.assertFalse(m.build_final_improvement_verdict(x)['certified_improved'])

    def test_ab_score_disagreement_refused(self):
        x=fixture();x['job_match_ab']['summary']['tailored_score']=98
        y=m.build_final_improvement_verdict(x)
        self.assertFalse(y['comparisons']['Initial']['verified'])
        self.assertFalse(y['certified_improved'])

    def test_invalid_or_unavailable_score_refused(self):
        x=fixture();x['after_stable_analysis']['deterministic_alignment_score']=None
        self.assertFalse(m.build_final_improvement_verdict(x)['certified_improved'])

    def test_claim_review_blocks_praise(self):
        x=fixture();x['claim_lineage']['claim_review_required_count']=2
        self.assertEqual(m.build_final_improvement_verdict(x)['status'],'review_required')

    def test_missing_claim_count_blocks_praise(self):
        x=fixture();x['claim_lineage']={}
        self.assertFalse(m.build_final_improvement_verdict(x)['certified_improved'])

    def test_malformed_claim_lineage_fails_closed(self):
        x=fixture();x['claim_lineage']=['not a dict']
        y=m.build_final_improvement_verdict(x)
        self.assertEqual(y['status'], 'review_required')
        self.assertFalse(y['certified_improved'])

    def test_unverified_fit_blocks(self):
        x=fixture();x['fit_one_page']=False
        self.assertFalse(m.build_final_improvement_verdict(x)['certified_improved'])

    def test_no_input_mutation(self):
        x=fixture(); original=copy.deepcopy(x)
        m.build_final_improvement_verdict(x)
        self.assertEqual(x,original)

if __name__ == '__main__': unittest.main()

from __future__ import annotations
import unittest
from copy import deepcopy
from tailoring.phase9f_bullet_comparison_detail_v1 import compare_saved_source_bullets, _marked
from tailoring.phase9f_final_base_coverage_check_v1 import build_final_vs_base_project_coverage

BASE = 'Built CI regression tooling in Python on Windows.'
LIB = 'Implemented unit tests with GitHub Actions CI in Python.'


def decision(mode='adaptive'):
    return {'selected':True, 'bullet_id':'a', 'bullet':LIB,
            'reason':'minimum_project_coverage',
            'decision_context':{'version':'phase9f-v27-bullet-selection-explanation-v1',
                'mode':mode,
                'selected':{'bullet_id':'a','bullet':LIB,'sources':['library'],'word_count':9,
                            'strong_requirement_ids':['r1'], 'rank_tuple':[1]},
                'best_opposite_source_peer_at_step':{'bullet_id':'b','bullet':BASE,
                    'sources':['base'],'word_count':8,'strong_requirement_ids':['r2'],'rank_tuple':[0]}}}
LABELS = {'r1':{'text':'Execute unit tests using Python','match':'direct'},
          'r2':{'text':'Maintain CI tooling in Python','match':'transferable'}}


class ComparisonTests(unittest.TestCase):
    def test_keyword_differences_not_conflated_with_scoring(self):
        x=compare_saved_source_bullets(decision(),LABELS)
        self.assertEqual(x['status'],'ok')
        self.assertIn('unit',x['chosen_only_terms'])
        self.assertIn('tooling',x['peer_only_terms'])
        self.assertIn('python',x['common_terms'])
        self.assertTrue(x['allocation_has_quality_winner'])
        self.assertEqual(x['requirements'][0]['project_match'],'direct')
    def test_all_canonical_cannot_claim_win(self):
        x=compare_saved_source_bullets(decision('all_canonical_before_fitting'),LABELS)
        self.assertEqual(x['status'],'ok')
        self.assertFalse(x['allocation_has_quality_winner'])
    def test_legacy_no_invented_alternative(self):
        d=decision();d['decision_context']={}
        self.assertEqual(compare_saved_source_bullets(d,LABELS)['status'],'withheld')
    def test_missing_requirement_text_refused(self):
        self.assertEqual(compare_saved_source_bullets(decision(),{'r1':LABELS['r1']})['status'],'withheld')
    def test_forged_source_or_identity_refused(self):
        d=decision();d['decision_context']['selected']['bullet_id']='fake'
        self.assertEqual(compare_saved_source_bullets(d,LABELS)['status'],'withheld')
        d=decision();d['decision_context']['best_opposite_source_peer_at_step']['sources']=['library']
        self.assertEqual(compare_saved_source_bullets(d,LABELS)['status'],'withheld')
    def test_markdown_escaped(self):
        s=_marked('<img src=x onerror=alert(1)> [CI] CI',{'ci'})
        self.assertNotIn('<img',s)
        self.assertIn('**CI**',s)
    def test_same_word_counts_not_ranking(self):
        x=compare_saved_source_bullets(decision(),LABELS)
        self.assertNotIn('word',x['selection_reason'].lower())


def audit():
    return {'verified':True,'generation_id':'gen','docx_sha256':'abc', 'projects':[
       {'project':'My Project', 'base':[{'text':BASE}], 'final':[{'text':LIB}]}]}
def ranks():
    return {'candidate_project_ranking':[{'title':'My Project','requirement_matches':[
      {'requirement_id':'r1','match_label':'direct','importance':'required','coverage_points':8},
      {'requirement_id':'r2','match_label':'transferable','importance':'core','coverage_points':5}]}]}
def evaluator(*,bullets,ranking_row):
    return [{'bullet_index':i,'bullet_text':x,'supported_requirement_ids':(['r1'] if x==LIB else ['r2'])}
            for i,x in enumerate(bullets)]

class FinalComparisonTests(unittest.TestCase):
    def test_gain_does_not_claim_complete_resume_improvement(self):
        x=build_final_vs_base_project_coverage(audit(),ranks(),evaluator=evaluator)
        self.assertEqual(x['status'],'comparable_project_proxy')
        self.assertEqual((x['base_points'],x['final_points'],x['delta']),(5,8,3))
        self.assertIn('r2',x['lost_required_core_ids'])
        self.assertEqual(x['verdict'],'higher_total_proxy_but_primary_coverage_loss')
        self.assertFalse(x['is_verified_overall_improvement'])
    def test_unverified_docx_refused(self):
        x=audit();x['verified']=False
        self.assertEqual(build_final_vs_base_project_coverage(x,ranks(),evaluator=evaluator)['status'],'withheld')
    def test_saved_rank_requirement_missing_refused(self):
        def bad(*,bullets,ranking_row):
            return [{'bullet_index':i,'bullet_text':b,'supported_requirement_ids':['invented']} for i,b in enumerate(bullets)]
        self.assertEqual(build_final_vs_base_project_coverage(audit(),ranks(),evaluator=bad)['status'],'withheld')
    def test_writer_changed_bullet_refused(self):
        def bad(*,bullets,ranking_row):
            return [{'bullet_index':i,'bullet_text':'wrong','supported_requirement_ids':[]} for i,_ in enumerate(bullets)]
        self.assertEqual(build_final_vs_base_project_coverage(audit(),ranks(),evaluator=bad)['status'],'withheld')
    def test_exact_no_gain_and_no_false_praise(self):
        x=audit();x['projects'][0]['final']=[{'text':BASE}]
        res=build_final_vs_base_project_coverage(x,ranks(),evaluator=evaluator)
        self.assertEqual(res['verdict'],'no_project_coverage_proxy_gain')
        self.assertFalse(res['is_verified_overall_improvement'])
    def test_no_base_withheld(self):
        x=audit();x['projects'][0]['base']=[]
        self.assertEqual(build_final_vs_base_project_coverage(x,ranks(),evaluator=evaluator)['status'],'withheld')
    def test_duplicate_project_identity_withheld(self):
        x=audit();x['projects'].append(deepcopy(x['projects'][0]))
        self.assertEqual(build_final_vs_base_project_coverage(x,ranks(),evaluator=evaluator)['status'],'withheld')
    def test_invalid_score_weight_refused(self):
        x=ranks();x['candidate_project_ranking'][0]['requirement_matches'][0]['coverage_points']=float('inf')
        self.assertEqual(build_final_vs_base_project_coverage(audit(),x,evaluator=evaluator)['status'],'withheld')

if __name__ == '__main__': unittest.main()

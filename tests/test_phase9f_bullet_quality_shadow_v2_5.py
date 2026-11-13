"""Focused, no model/database side effects V2.5 shadow coverage trial tests."""
import importlib
import unittest
from copy import deepcopy

from tailoring.phase9f_bullet_quality_shadow_v2_5 import build_shadow_bullet_quality_trial, MAX_POOL


def row(title, bullets, source):
    return {'project': title, source: [{'number': i, 'text': b} for i,b in enumerate(bullets, 1)]}


def fixture():
    audit = {'project': 'Job AI Helper',
             'base': [{'number': 1, 'text': 'Built a verified Python testing harness.'},
                      {'number': 2, 'text': 'Deployed a React dashboard.'}],
             'library': [{'number': 1, 'text': 'Built a reusable Python tool.'},
                         {'number': 2, 'text': 'Wrote extensive documentation for multiple users.'}],
             'final': [{'number': 1, 'text': 'Built a reusable Python tool.'},
                       {'number': 2, 'text': 'Wrote extensive documentation for multiple users.'}]}
    project = {'candidate_project_ranking':[{'title':'Job AI Helper',
        'requirement_matches':[
            {'requirement_id':'req_test', 'match_label':'direct','coverage_points':5, 'requirement_text':'Testing'},
            {'requirement_id':'req_react', 'match_label':'transferable','coverage_points':2, 'requirement_text':'React'}]}]}
    return audit, project


def builder(*, bullets, ranking_row):
    out=[]
    for i, b in enumerate(bullets):
        ids=[]
        if 'test' in b.lower(): ids.append('req_test')
        if 'react' in b.lower(): ids.append('req_react')
        out.append({'bullet_index':i,'bullet_text':b,'supported_requirement_ids':ids})
    return out


class ShadowCoverageV25Tests(unittest.TestCase):
    def test_equal_count_and_word_budget_can_reveal_base_candidate_signal(self):
        audit, projects=fixture()
        result=build_shadow_bullet_quality_trial(audit,projects,priority_builder=builder)
        self.assertEqual(result['status'],'potential_coverage_gain')
        self.assertGreater(result['shadow_signal_points'],result['final_signal_points'])
        self.assertLessEqual(result['shadow_words'],result['final_word_budget'])
        self.assertEqual(len(result['shadow_slate']),len(audit['final']))
        self.assertIn('Built a verified Python testing harness.',result['base_promotions_needed'])
        self.assertIn('REQUIRED',result['reason'])
        self.assertNotIn('best possible',result['reason'].lower())

    def test_existing_coverage_is_counted_once_across_duplicate_requirements(self):
        audit, projects=fixture()
        audit['base'][1]['text']='Tested another backend service.'
        result=build_shadow_bullet_quality_trial(audit,projects,priority_builder=builder)
        self.assertLessEqual(result.get('shadow_signal_points',0),5)

    def test_same_budget_blocks_longer_alternative(self):
        audit, projects=fixture()
        audit['base'][0]['text']='Built a fantastic and comprehensive test harness with lots and lots of detailed evidence.'
        audit['base'][1]['text']='Deployed a React dashboard with many many extra words that cannot fit under current limitations.'
        result=build_shadow_bullet_quality_trial(audit,projects,priority_builder=builder)
        self.assertEqual(result['status'],'no_coverage_gain_signal')
        self.assertEqual(result['signal_delta'],0)

    def test_no_supported_requirement_is_not_winner(self):
        a,p=fixture();p['candidate_project_ranking'][0]['requirement_matches']=[]
        result=build_shadow_bullet_quality_trial(a,p,priority_builder=builder)
        self.assertEqual(result['status'],'no_supported_requirements')

    def test_other_project_cannot_inherit_rank(self):
        a,p=fixture();a['project']='Unrelated Project'
        self.assertEqual(build_shadow_bullet_quality_trial(a,p,priority_builder=builder)['status'],'withheld')

    def test_duplicate_rank_identity_is_blocked(self):
        a,p=fixture();p['candidate_project_ranking'].append(deepcopy(p['candidate_project_ranking'][0]))
        self.assertEqual(build_shadow_bullet_quality_trial(a,p,priority_builder=builder)['status'],'withheld')

    def test_malformed_source_bullets_blocked(self):
        a,p=fixture();a['library'].append({'number':3, 'text':99})
        self.assertEqual(build_shadow_bullet_quality_trial(a,p,priority_builder=builder)['status'],'withheld')

    def test_builder_foreign_requirement_rejected(self):
        a,p=fixture()
        def foreign(**kw):
            rows=builder(**kw);rows[0]['supported_requirement_ids']=['req_other'];return rows
        self.assertEqual(build_shadow_bullet_quality_trial(a,p,priority_builder=foreign)['status'],'withheld')

    def test_builder_wrong_bullet_identity_rejected(self):
        a,p=fixture()
        def wrong(**kw):
            rows=builder(**kw);rows[0]['bullet_text']='other project';return rows
        self.assertEqual(build_shadow_bullet_quality_trial(a,p,priority_builder=wrong)['status'],'withheld')

    def test_single_source_bullet_fewer_than_final_count_blocks(self):
        a,p=fixture();a['base']=[];a['library']=a['library'][:1]
        self.assertEqual(build_shadow_bullet_quality_trial(a,p,priority_builder=builder)['status'],'withheld')

    def test_pool_exceeding_limit_blocks(self):
        a,p=fixture()
        a['base']=[{'number':i,'text':'Test '+str(i)} for i in range(MAX_POOL+1)]
        self.assertEqual(build_shadow_bullet_quality_trial(a,p,priority_builder=builder)['status'],'withheld')

    def test_no_feasible_source_slate_is_explicit(self):
        a,p=fixture()
        a['final']=[{'number':1,'text':'x'},{'number':2,'text':'y'}]
        result=build_shadow_bullet_quality_trial(a,p,priority_builder=builder)
        self.assertEqual(result['status'],'no_feasible_source_slate')

    def test_unknown_match_value_blocks(self):
        a,p=fixture();p['candidate_project_ranking'][0]['requirement_matches'][0]['coverage_points']='nan'
        self.assertEqual(build_shadow_bullet_quality_trial(a,p,priority_builder=builder)['status'],'withheld')

    def test_copy_only_no_mutations(self):
        a,p=fixture();ac=deepcopy(a);pc=deepcopy(p)
        build_shadow_bullet_quality_trial(a,p,priority_builder=builder)
        self.assertEqual(a,ac)
        self.assertEqual(p,pc)

    def test_exact_shared_bullet_deduplicated_and_has_both_sources(self):
        a,p=fixture();a['base'][0]['text']=a['library'][0]['text']
        result=build_shadow_bullet_quality_trial(a,p,priority_builder=builder)
        rows=[r for r in result['candidates'] if r['text']==a['base'][0]['text']]
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['sources'],['Selected Base','Evidence Library'])

    def test_duplicate_coverage_value_not_double_counted(self):
        a,p=fixture();a['base'][1]['text']='Another testing harness.'
        result=build_shadow_bullet_quality_trial(a,p,priority_builder=builder)
        self.assertEqual(result['shadow_signal_points'],5.0)


if __name__=='__main__':unittest.main()

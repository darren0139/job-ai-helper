"""Scalable newer-mode search, no private benchmark or persisted data."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch
from tailoring.phase9f_auto_optimize_v31 import build_flexible_optimization
from tailoring.phase9f_large_pool_v312b214b2 import prepare_sources, MAX_LARGE_PROJECT_POOL, LOCAL_WIDTH
from tailoring.phase9f_jd_relevance_optimizer_v35 import build_jd_relevance_optimization
from tailoring.phase9f_certified_selection_v36 import build_certified_optimization, _matrix_program, _solve, _fallback
from tailoring.phase9f_same_work_selection_v37 import build_same_work_optimization, selected_conflicts
from tailoring.phase9f_joint_resume_optimizer_v2_6 import _source_pool

BASE = 'Implemented Python backend service authentication and session workflows.'
SECOND = 'Created React frontend forms with validation and error handling.'
RARE = 'Configured PostgreSQL database replication and verified recovery.'

def fixture(n):
    # The rare, useful candidate is intentionally last, after many candidates
    # with higher individual coverage than the rare candidate.
    library = [f'Implemented Python backend authentication workflow number {i}.' for i in range(n-3)] + [RARE]
    def rows(values): return [{'text':x} for x in values]
    audit = {'verified':True,'generation_id':'synthetic','docx_sha256':'a'*64,
             'projects':[{'project':'Service','base':rows([BASE,SECOND]),'library':rows(library),'final':rows([BASE,SECOND])}]}
    def req(rid, text, pts, snippets, importance='core'):
        return {'requirement_id':rid,'requirement_text':text,'match_label':'direct',
                'coverage_points':pts,'importance':importance,'evidence_snippets':snippets,
                'evidence_ids':['synthetic'],'mapping_similarity':1.0,'capability_id':None}
    projects={'candidate_project_ranking':[{'display_title':'Service','requirement_matches':[
        req('backend','Python backend authentication',30,[BASE]+library[:-1]),
        req('frontend','React frontend validation',20,[SECOND]),
        req('database','PostgreSQL database recovery',3,[RARE],'preferred')]}]}
    return audit,projects

def evaluator(*,bullets,ranking_row):
    return [{'bullet_index':i,'bullet_text':t,'supported_requirement_ids':[
        r['requirement_id'] for r in ranking_row['requirement_matches'] if t in r['evidence_snippets']
    ]} for i,t in enumerate(bullets)]

def prepare(a,p,ev=evaluator):
    return prepare_sources(a,p,evaluator=ev,legacy_builder=build_flexible_optimization)

class LargePoolTests(unittest.TestCase):
    def test_small_source_path_is_exact_legacy(self):
        a,p=fixture(16)
        self.assertEqual(prepare(a,p),build_flexible_optimization(a,p,evaluator=evaluator))
        self.assertEqual(len(_source_pool(a['projects'][0])[0]),16)

    def test_complete_pool_at_17_31_64_128(self):
        for n in (17,31,64,128):
            with self.subTest(n=n):
                a,p=fixture(n); frozen=deepcopy((a,p))
                result=prepare_sources(a,p,evaluator=evaluator,legacy_builder=lambda *a,**k:self.fail('legacy search called'))
                self.assertEqual(result['status'],'no_proxy_gain',result)
                comp=result['source_comparison']; rows=comp['projects'][0]['candidates']
                self.assertEqual(len(rows),n)
                self.assertEqual(rows[-1]['text'],RARE)
                self.assertEqual(rows[-1]['saved_jd_ids'],['database'])
                self.assertEqual(comp['large_pool_preparation']['source_candidates_discarded'],0)
                self.assertEqual((a,p),frozen)

    def test_scope_rejects_oversize_and_corrupt_links(self):
        a,p=fixture(129);self.assertEqual(prepare(a,p)['status'],'withheld')
        a,p=fixture(31);a['verified']=False;self.assertEqual(prepare(a,p)['status'],'withheld')
        a,p=fixture(31);self.assertEqual(prepare(a,p,lambda **kw:[])['status'],'withheld')
        a,p=fixture(31);p['candidate_project_ranking'][0]['requirement_matches'].append(deepcopy(p['candidate_project_ranking'][0]['requirement_matches'][0]))
        self.assertEqual(prepare(a,p)['status'],'withheld')
        a,p=fixture(100)
        for name in ('Second','Third'):
            row=deepcopy(a['projects'][0]);row['project']=name;a['projects'].append(row)
            rank=deepcopy(p['candidate_project_ranking'][0]);rank['display_title']=name;p['candidate_project_ranking'].append(rank)
        self.assertIn('total limit',prepare(a,p)['reason'])

    def test_v35_large_search_keeps_rare_and_baseline_links(self):
        for n in (17,31,64,128):
            with self.subTest(n=n):
                a,p=fixture(n); before=deepcopy((a,p))
                result=build_jd_relevance_optimization(a,p,evaluator=evaluator)
                self.assertEqual(result['status'],'candidate',result.get('reason'))
                self.assertIn(RARE,result['projects'][0]['after'])
                self.assertEqual(result['lost_jd_ids'],[])
                self.assertEqual(result['proposed_points'],53)
                group=result['source_comparison']['projects'][0]
                self.assertEqual(len(group['candidates']),n)
                receipt=group['large_pool_search']
                self.assertEqual(receipt['singleton_candidates_evaluated'],n)
                self.assertLessEqual(receipt['local_slate_evaluations'],n+7*LOCAL_WIDTH*n+9)
                self.assertFalse(receipt['global_optimum_claim'])
                self.assertEqual((a,p),before)
                json.dumps(result,allow_nan=False)

    def test_repeat_and_fallback_certificate(self):
        a,p=fixture(31)
        one=build_jd_relevance_optimization(a,p,evaluator=evaluator)
        two=build_jd_relevance_optimization(a,p,evaluator=evaluator)
        self.assertEqual(one,two)
        with patch('tailoring.phase9f_certified_selection_v36._solve',side_effect=RuntimeError('synthetic unavailable')):
            out=build_same_work_optimization(a,p,evaluator=evaluator)
        self.assertEqual(out['mathematical_certificate']['status'],'not_proven')
        self.assertIn(out['status'],('candidate','no_proxy_gain'))
        for trial in out.get('candidate_variants',[]):
            self.assertFalse(selected_conflicts(trial))
            self.assertEqual(trial['lost_jd_ids'],[])
        self.assertEqual(out['v38_bullet_score_receipt']['status'],'available')

    def test_milp_receives_entire_pool_and_keeps_legacy_cap(self):
        a,p=fixture(31);model=_matrix_program(a,prepare(a,p),p,same_work_guard=True)
        self.assertEqual(len(model['bullets']),31)
        self.assertEqual(model['baseline_ids'],{'backend','frontend'})
        a,p=fixture(128)
        with self.assertRaisesRegex(ValueError,'exact-solver scope'):
            _matrix_program(a,prepare(a,p),p,same_work_guard=True)
        out=build_same_work_optimization(a,p,evaluator=evaluator)
        self.assertEqual(out['mathematical_certificate']['status'],'not_proven')
        self.assertEqual(len(out['source_comparison']['projects'][0]['candidates']),128)

    def test_cross_project_geometry_and_large_eight_bullet_incumbent(self):
        a,p=fixture(31)
        # Four projects with the observed 31/7/5/4 source-pool geometry;
        # distinct synthetic project ownership, no private applicant text.
        a['projects'][0]['final'] += deepcopy(a['projects'][0]['library'][:3])
        for i,n in enumerate((7,5,4),1):
            aa,pp=fixture(n); section=aa['projects'][0]; rank=pp['candidate_project_ranking'][0]
            section['project']=rank['display_title']=f'Other project {i}'
            section['final']=section['final'][:1]
            a['projects'].append(section);p['candidate_project_ranking'].append(rank)
        frozen=prepare(a,p);self.assertEqual(frozen['source_comparison']['large_pool_preparation']['total_candidates'],47)
        result=build_jd_relevance_optimization(a,p,evaluator=evaluator)
        self.assertIn(result['status'],('candidate','no_proxy_gain'),result.get('reason'))
        self.assertEqual(len(result['source_comparison']['projects']),4)
        for candidate in result.get('candidate_variants',[]):
            self.assertEqual(candidate['lost_jd_ids'],[])
            self.assertEqual(len(candidate['projects']),4)
        a,p=fixture(128)
        a['projects'][0]['final'] += deepcopy(a['projects'][0]['library'][:6])
        result=build_jd_relevance_optimization(a,p,evaluator=evaluator)
        self.assertIn(result['status'],('candidate','no_proxy_gain'),result.get('reason'))
        receipt=result['source_comparison']['projects'][0]['large_pool_search']
        self.assertLessEqual(receipt['local_slate_evaluations'],128+7*LOCAL_WIDTH*128+9)
        for variant in result.get('candidate_variants',[]):
            self.assertEqual(variant['lost_jd_ids'],[])
            self.assertLessEqual(len(variant['projects'][0]['after']),8)

class ExactSolverTests(unittest.TestCase):
    def test_real_milp_31_and_64(self):
        import scipy.optimize  # no silent skip: full apply must have solver
        for n in (31,64):
            a,p=fixture(n); model=_matrix_program(a,prepare(a,p),p,same_work_guard=True)
            out=_solve(model,[],time_limit=12)
            self.assertEqual(out['status'],'optimal_proxy',out)
            selected=[model['bullets'][i] for i in out['selected_indices']]
            self.assertIn(RARE,[x['text'] for x in selected])
            self.assertEqual(set().union(*(x['ids'] for x in selected)),{'backend','frontend','database'})
            self.assertEqual(len(model['bullets']),n)

class NativeEvaluatorTests(unittest.TestCase):
    def test_actual_saved_link_evaluator_large_pool(self):
        from tests.test_v312b214b_independent_bullet_scores import fixture as native_fixture
        from tailoring.stable_tailoring_ranking import build_bullet_evidence_priorities
        a,p,_=native_fixture(); result=prepare(a,p,build_bullet_evidence_priorities)
        self.assertEqual(result['status'],'no_proxy_gain',result)
        self.assertEqual(result['source_comparison']['large_pool_preparation']['total_candidates'],33)
        rows=result['source_comparison']['projects'][0]['candidates']
        self.assertEqual(len(rows),31)
        self.assertTrue(rows[0]['saved_jd_ids'])

if __name__=='__main__':unittest.main()

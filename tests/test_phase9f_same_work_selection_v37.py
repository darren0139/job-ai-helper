"""Synthetic V3.7: no real resume, database, API or native verification calls."""
from copy import deepcopy
import unittest

from tailoring.phase9f_certified_selection_v36 import (_matrix_program, _solve,
    build_certified_optimization)
from tailoring.phase9f_auto_optimize_v31 import build_flexible_optimization
from tailoring.phase9f_evidence_optimizer_v33 import _metadata
from tailoring.phase9f_same_work_selection_v37 import (
    VERSION, build_same_work_optimization, conflict_indices, selected_conflicts,
    vet_fallback, verified_tie_dedupe)

BASE = ('Built 30-job corpus regression/audit tooling and GitHub Actions CI '
        'across Windows/Ubuntu to validate scoring, taxonomy resolution, sessions, and UI workflows.')
LIB = ('Added automated unit tests and GitHub Actions CI across Ubuntu and Windows, '
       'running dependency checks, compilation, the full test suite, and a Streamlit startup health check.')
DB1 = 'Implemented SQL database reporting queries with parameterized access.'
DB2 = 'Implemented Row-Level Security policies and PostgREST database access to protect customer records.'


def fixture(a=BASE, b=LIB, ids_a=('ci',), ids_b=('ci',)):
    """Verified frozen source + production-shaped saved requirement ranking.

    Deliberately no _weights/_texts shortcuts or fabricated _source receipts.
    A deterministic test evaluator supplies ONLY the explicitly pinned JD links,
    exactly as the production support evaluator contract requires.
    """
    if a == b:
        raise ValueError('Synthetic fixture needs distinguishable source wordings.')
    ids = tuple(sorted(set(ids_a) | set(ids_b)))
    audit = {'verified': True, 'projects': [{
        'project': 'Synthetic project',
        'base': [{'text': a}],
        'library': [{'text': b}],
        'final': [{'text': a}, {'text': b}],
    }]}
    rank = {
        'display_title': 'Synthetic project',
        'requirement_matches': [{
            'requirement_id': rid,
            'requirement_text': 'CI testing validation' if rid == 'ci' else 'JD ' + rid,
            'importance': 'core',
            'match_label': 'direct',
            'coverage_points': 1.0,
        } for rid in ids],
    }
    projects = {'candidate_project_ranking': [rank]}
    return audit, projects


def frozen_evaluator(*, bullets, ranking_row):
    """Deterministic, identity-preserving v31 evidence receipt (no LLM)."""
    # Same-project tests have one exact Base and one exact Library wording.
    # The test determines the support mapping in its fixture, NOT via lexical
    # inference; the real saved requirements still come from project ranking.
    support = ranking_row['_fixture_support']
    return [{
        'bullet_index': i,
        'bullet_text': text,
        'supported_requirement_ids': list(support[text]),
    } for i, text in enumerate(bullets)]


def prepared(a=BASE, b=LIB, ids_a=('ci',), ids_b=('ci',)):
    audit, projects = fixture(a, b, ids_a, ids_b)
    rank = projects['candidate_project_ranking'][0]
    rank['_fixture_support'] = {a: tuple(ids_a), b: tuple(ids_b)}
    frozen = build_flexible_optimization(audit, projects, evaluator=frozen_evaluator)
    assert frozen.get('status') != 'withheld', frozen
    assert isinstance(frozen.get('source_comparison'), dict), frozen
    return audit, projects, frozen


class SameWorkSelectionTests(unittest.TestCase):
    def test_fixture_uses_real_frozen_project_ranking_contract(self):
        audit, projects, frozen = prepared()
        self.assertTrue(audit['verified'])
        self.assertEqual(projects['candidate_project_ranking'][0]['display_title'],
                         audit['projects'][0]['project'])
        weights, texts, error = _metadata(projects, frozen['source_comparison'])
        self.assertEqual(error, '')
        self.assertEqual(weights, {'ci': 1.0})
        self.assertIn('ci', texts)
        rows = frozen['source_comparison']['projects'][0]['candidates']
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row['in_original_a'] for row in rows))
        self.assertEqual([row['saved_jd_ids'] for row in rows], [['ci'], ['ci']])

    def test_missing_rank_or_unverified_final_is_still_withheld(self):
        audit, projects, _ = prepared()
        missing = deepcopy(projects)
        missing.pop('candidate_project_ranking')
        self.assertEqual(build_same_work_optimization(audit, missing,
            evaluator=frozen_evaluator, max_trials=1)['status'], 'withheld')
        stale = deepcopy(audit)
        stale['verified'] = False
        self.assertEqual(build_same_work_optimization(stale, projects,
            evaluator=frozen_evaluator, max_trials=1)['status'], 'withheld')

    def test_concrete_ci_example_generates_one_of_two_constraint(self):
        audit, projects, frozen=prepared()
        model=_matrix_program(audit,frozen,projects,same_work_guard=True)
        self.assertEqual(model['same_work_conflicts'],((0,1),))
        solved=_solve(model,[],time_limit=4)
        self.assertEqual(solved['status'],'optimal_proxy',solved)
        self.assertLessEqual(len(solved['selected_indices']),1)
        model_old=_matrix_program(audit,frozen,projects)
        self.assertEqual(model_old['same_work_conflicts'],())

    def test_selected_base_floor_does_not_claim_tie_as_score_improvement(self):
        from tailoring.phase9f_certified_selection_v36 import selected_base_floor_gate
        receipt={'status':'verified','winner':'optimized_candidate','delta':0,
                 'same_work_verified_tie_break':'nonregressed_simplification_v37'}
        held=selected_base_floor_gate(receipt,{'status':'unavailable'})
        self.assertEqual(held['winner'],'existing_final')
        self.assertFalse(held['verified_better_than_a_only'])
        self.assertEqual(held['base_floor_verdict'],'not_proven')
        self.assertEqual(receipt['winner'],'optimized_candidate')

    def test_unrelated_same_project_bullets_are_not_mutually_exclusive(self):
        audit,projects,frozen=prepared(DB1,DB2)
        model=_matrix_program(audit,frozen,projects,same_work_guard=True)
        self.assertFalse(model['same_work_conflicts'])

    def test_unique_baseline_evidence_must_not_be_discarded_to_dedupe(self):
        audit,projects,frozen=prepared(ids_a=('a',),ids_b=('b',))
        model=_matrix_program(audit,frozen,projects,same_work_guard=True)
        self.assertEqual(model['same_work_conflicts'],((0,1),))
        # Both JD IDs are protected. The model must be infeasible rather than
        # silently discarding Required/Core identity.
        solved=_solve(model,[],time_limit=4)
        self.assertNotEqual(solved['status'],'optimal_proxy',solved)

    def test_legacy_optimizer_signature_does_not_gain_constraint(self):
        audit,projects,frozen=prepared()
        model=_matrix_program(audit,frozen,projects)
        self.assertFalse(model['same_work_conflicts'])
        original=build_certified_optimization(audit,projects,evaluator=frozen_evaluator,max_trials=1)
        self.assertNotIn('same_work_policy',original)

    def test_new_mode_only_proposes_against_unchanged_fitted_a(self):
        audit,projects,_=prepared()
        original=deepcopy(audit)
        out=build_same_work_optimization(audit,projects,evaluator=frozen_evaluator,max_trials=1)
        self.assertEqual(audit,original)
        self.assertEqual(out['same_work_selector_version'],VERSION)
        self.assertEqual(out['version'],'phase9f-jd-relevance-v3.5-v1')
        self.assertEqual(out['same_work_policy']['candidate_rule'],'at_most_one')
        if out.get('status')=='candidate':
            self.assertEqual(len(out['projects'][0]['after']),1)
            self.assertFalse(selected_conflicts(out))
            self.assertTrue(out['same_work_policy']['native_document_and_selected_base_floors_required'])

    def test_fallback_filters_out_duplicate_alternatives_without_editing_them(self):
        _,projects=fixture()
        bad={'status':'candidate','changed':True, 'projects':[{'project':'Synthetic project',
            'after':[BASE,LIB],'sources':[['Selected Base'],['Evidence Library']]}]}
        original=deepcopy(bad)
        screened=vet_fallback(bad)
        self.assertEqual(screened['status'],'no_proxy_gain')
        self.assertEqual(bad,original)
        good={'status':'candidate','changed':True,'projects':[{'project':'Synthetic project',
            'after':[BASE], 'sources':[['Selected Base']]}]}
        multiple=deepcopy(bad);multiple['candidate_variants']=[bad,good]
        screened=vet_fallback(multiple)
        self.assertEqual(screened['status'],'candidate')
        self.assertEqual(screened['projects'],good['projects'])
        self.assertEqual(screened['shortlist_size'],1)

    def test_native_tie_prefers_only_verified_same_work_reduction(self):
        audit,projects,_=prepared()
        out=build_same_work_optimization(audit,projects,evaluator=frozen_evaluator,max_trials=1)
        self.assertEqual(out['status'],'candidate',out)
        rows=[{'requirement_id':'ci','importance':'core','match_label':'direct',
               'evidence_strength':3}]
        a={'canonical_requirements':deepcopy(rows)}
        b={'canonical_requirements':deepcopy(rows)}
        self.assertTrue(verified_tie_dedupe(
            audit=audit,proposal=out,original_score=a,alternative_score=b))
        b['canonical_requirements'][0]['evidence_strength']=2
        self.assertFalse(verified_tie_dedupe(
            audit=audit,proposal=out,original_score=a,alternative_score=b))
        b['canonical_requirements'][0]['evidence_strength']=3
        b['canonical_requirements'][0]['match_label']='weak'
        self.assertFalse(verified_tie_dedupe(
            audit=audit,proposal=out,original_score=a,alternative_score=b))
        b['canonical_requirements'][0]['match_label']='direct'
        legacy=deepcopy(out);legacy.pop('same_work_policy')
        self.assertFalse(verified_tie_dedupe(
            audit=audit,proposal=legacy,original_score=a,alternative_score=b))

    def test_native_tie_needs_exact_frozen_source_provenance(self):
        audit,projects,_=prepared()
        out=build_same_work_optimization(audit,projects,evaluator=frozen_evaluator,max_trials=1)
        rows=[{'requirement_id':'ci','importance':'core','match_label':'direct'}]
        scores={'canonical_requirements':rows}
        changed=deepcopy(audit)
        changed['projects'][0]['final'][0]['text']='Unrelated unsaved sentence'
        self.assertFalse(verified_tie_dedupe(
            audit=changed,proposal=out,original_score=scores,
            alternative_score=scores))

    def test_selected_conflicts_are_cross_source_per_project_only(self):
        p={'projects':[{'project':'One', 'after':[BASE,LIB],
                        'sources':[['Selected Base'],['Evidence Library']]}]}
        self.assertEqual(len(selected_conflicts(p)),1)
        p['projects'][0]['sources']=[['Selected Base'],['Selected Base']]
        self.assertEqual(selected_conflicts(p),[])
        p['projects']=[{'project':'One','after':[BASE],'sources':[['Selected Base']]},
                       {'project':'Two','after':[LIB],'sources':[['Evidence Library']]}]
        self.assertEqual(selected_conflicts(p),[])


if __name__=='__main__':unittest.main()

"""Synthetic cross-user regression: no private benchmark or application DB."""
from copy import deepcopy
from contextlib import nullcontext
from pathlib import Path
from types import ModuleType
import sys
import unittest
from unittest.mock import patch

from tailoring.phase9f_independent_bullet_scores_v312b214b import build_independent_bullet_scores as build
from tailoring.phase9f_joint_resume_optimizer_v2_6 import _source_pool, _support
from tailoring import phase9f_v39_final_bullet_review as ui

PYTHON = 'Developed Python REST API endpoints for reporting.'
LIBRARY = 'Built Python data processing utilities for reporting.'
ZERO = 'Designed game levels using a custom engine.'
P1, P2, P3 = 'Large source pool', 'Library-only project', 'Base-only project'
JD = 'Proficiency in Python. Experience with database systems.'


def fixture():
    canonical = [dict(requirement_id='python', text='Proficiency in Python', importance='core', score_eligible=True),
                 dict(requirement_id='db', text='Experience with database systems', importance='preferred', score_eligible=True)]
    def match(rid, points, snippets):
        r = next(x for x in canonical if x['requirement_id']==rid)
        return dict(requirement_id=rid, requirement_text=r['text'], importance=r['importance'],
                    match_label='direct', coverage_points=points, evidence_snippets=snippets,
                    evidence_ids=['synthetic'], mapping_similarity=1.0, capability_id=None)
    def texts(*items): return [{'text': x} for x in items]
    audit = {'verified': True, 'generation_id': 'synthetic-generation', 'docx_sha256': 'a'*64, 'projects': [
        {'project': P1, 'base': texts(PYTHON), 'library': texts(*[f'Implemented synthetic workflow number {i}.' for i in range(30)]), 'final': texts(PYTHON)},
        {'project': P2, 'base': [], 'library': texts(LIBRARY), 'final': texts(LIBRARY)},
        {'project': P3, 'base': texts(ZERO), 'library': [], 'final': texts(ZERO)},
    ]}
    projects = {'candidate_project_ranking': [
        {'display_title': P1, 'requirement_matches': [match('python', 6.0, [PYTHON])]},
        {'display_title': P2, 'requirement_matches': [match('python', 9.0, [LIBRARY])]},
        {'display_title': P3, 'requirement_matches': []},
    ], '_v39_auto_dedupe': {'project_scores': [{'project': P1, 'bullets': [{'text': PYTHON, 'saved_evidence_points': 999}]}]}}
    report = {'raw_jd_text': JD, 'stable_analysis': {'canonical_requirements': canonical}}
    return audit, projects, report


def evaluator(*, bullets, ranking_row):
    return [{'bullet_index': i, 'bullet_text': b, 'supported_requirement_ids': [
        r['requirement_id'] for r in ranking_row['requirement_matches'] if b in r['evidence_snippets']
    ]} for i, b in enumerate(bullets)]


def score(receipt, project, wording):
    return ui.scored_wording({'v38_bullet_score_receipt': receipt}, project, wording)


class IndependentScoreTests(unittest.TestCase):
    def test_large_pool_does_not_change_optimizer_search_limit(self):
        audit, projects, report = fixture()
        before = deepcopy((audit, projects, report))
        rows, error = _source_pool(audit['projects'][0])
        self.assertEqual(rows, [])
        self.assertIn('31 > 16', error)
        receipt = build(audit, projects, report, JD, evaluator=evaluator)
        self.assertEqual(receipt['status'], 'available', receipt)
        self.assertEqual(receipt['bullet_count'], 33)
        self.assertEqual(score(receipt, P1, PYTHON)['standalone_weighted_points'], 9.0)
        self.assertEqual(score(receipt, P2, LIBRARY)['standalone_weighted_points'], 9.0)
        self.assertEqual(score(receipt, P3, ZERO)['standalone_weighted_points'], 0.0)
        self.assertEqual(score(receipt, P1, 'Implemented synthetic workflow number 0.')['standalone_weighted_points'], 0.0)
        self.assertFalse(receipt['optimizer_search_performed'])
        self.assertFalse(receipt['native_score_claim'])
        self.assertEqual((audit, projects, report), before)
        self.assertEqual(build(audit, projects, report, JD, evaluator=evaluator), receipt)

    def test_not_prefit_points_or_proposal_membership(self):
        a,p,r=fixture(); result=build(a,p,r,JD,evaluator=evaluator)
        row=score(result,P1,PYTHON)
        self.assertEqual(row['standalone_weighted_points'],9.0)
        self.assertIsNone(row['native_per_bullet_score'])
        self.assertIsNone(row['marginal_in_proposal_points'])
        self.assertNotIn('selected_for_proposed_b',row)
        self.assertIsNone(score(result,P2,PYTHON))
        self.assertIsNone(score(result,P1,PYTHON+' changed'))

    def test_shared_wording_deduplicates_links_and_sources(self):
        a,p,r=fixture();a['projects'][0]['library'].append({'text':PYTHON})
        got=build(a,p,r,JD,evaluator=evaluator);row=score(got,P1,PYTHON)
        self.assertEqual(got['bullet_count'],33)
        self.assertEqual(set(row['sources']),{'Selected Base','Evidence Library','Current final'})
        self.assertEqual(row['saved_jd_ids'],['python'])
        self.assertEqual(row['standalone_weighted_points'],9.0)

    def test_stale_or_unavailable_scope_does_not_become_zero(self):
        for mutate in (lambda a,p,r:a.update(verified=False),
                       lambda a,p,r:a.update(generation_id=''),
                       lambda a,p,r:a.update(docx_sha256='changed'),
                       lambda a,p,r:r.update(raw_jd_text='different JD'),
                       lambda a,p,r:r['stable_analysis'].update(canonical_requirements=[]),
                       lambda a,p,r:p['candidate_project_ranking'].pop(),
                       lambda a,p,r:p['candidate_project_ranking'][0].pop('requirement_matches'),
                       lambda a,p,r:p['candidate_project_ranking'][0]['requirement_matches'][0].update(requirement_id='other'),
                       lambda a,p,r:p['candidate_project_ranking'][0]['requirement_matches'][0].update(requirement_text='different'),
                       lambda a,p,r:p['candidate_project_ranking'][0]['requirement_matches'][0].update(importance='preferred'),
                       lambda a,p,r:p['candidate_project_ranking'][0]['requirement_matches'][0].update(coverage_points=float('nan')),
                       lambda a,p,r:a['projects'][0].pop('library')):
            a,p,r=fixture(); mutate(a,p,r)
            got=build(a,p,r,JD,evaluator=evaluator)
            self.assertEqual(got['status'],'unavailable',got)
            self.assertTrue(got['reason']); self.assertIsNone(score(got,P1,PYTHON))

    def test_empty_but_complete_rank_is_known_zero(self):
        a,p,r=fixture()
        for row in p['candidate_project_ranking']:row['requirement_matches']=[]
        def should_not_run(**kwargs): raise AssertionError('no positive weights')
        got=build(a,p,r,JD,evaluator=should_not_run)
        self.assertEqual(got['status'],'available',got)
        self.assertTrue(all(row['standalone_weighted_points']==0 for row in got['bullets']))

    def test_unknown_ids_or_reordered_evaluator_fail_closed(self):
        a,p,r=fixture()
        for bad in (lambda **kw: [], lambda **kw:[{'bullet_index': i, 'bullet_text': b, 'supported_requirement_ids':['fake']} for i,b in enumerate(kw['bullets'])]):
            got=build(a,p,r,JD,evaluator=bad)
            self.assertEqual(got['status'],'unavailable',got)
            self.assertFalse(got['bullets'])

    def test_scope_changes_when_source_ranking_or_document_changes(self):
        a,p,r=fixture(); first=build(a,p,r,JD,evaluator=evaluator)['scope']
        p['candidate_project_ranking'][0]['requirement_matches'][0]['coverage_points']=7.0
        self.assertNotEqual(first['source_and_ranking_sha256'],build(a,p,r,JD,evaluator=evaluator)['scope']['source_and_ranking_sha256'])
        a['docx_sha256']='b'*64
        self.assertEqual(build(a,p,r,JD,evaluator=evaluator)['scope']['a_docx_sha256'],'b'*64)

    def test_final_review_renders_independent_score_without_proposal(self):
        a,p,r=fixture(); receipt=build(a,p,r,JD,evaluator=evaluator)
        class FakeUI:
            def __init__(self):self.session_state={};self.labels=[];self.captions=[]
            def markdown(self,*args,**kw):pass
            def caption(self,value):self.captions.append(value)
            def info(self,*args,**kw):pass
            def warning(self,*args,**kw):pass
            def container(self,**kw):return nullcontext()
            def columns(self,n):return [nullcontext() for _ in range(n)]
            def radio(self,label,options,**kw):
                self.labels.extend(kw['format_func'](x) for x in options);return options[0]
        checks=ModuleType('tailoring.phase9f_multi_project_evidence_v36')
        checks.project_checkboxes=lambda st,names,**kw:names
        with patch.dict(sys.modules,{checks.__name__:checks}),patch.object(ui,'_show_panel'),patch.object(ui,'_render_detailed_comparison'):
            st=FakeUI(); self.assertTrue(ui.render_verified_final_bullets(st,audit=a,result={'status':'withheld'},proposal={},ranked=[],catalog={},application_id=21,context='synthetic',independent_scores=receipt))
            self.assertEqual(st.labels,[PYTHON+' · JD 9.000 pts',LIBRARY+' · JD 9.000 pts',ZERO+' · JD 0.000 pts'])
            # A stale independent receipt must not fall back to even a positive legacy proposal.
            st=FakeUI();a['generation_id']='new-generation'
            ui.render_verified_final_bullets(st,audit=a,result={},proposal={'v38_bullet_score_receipt':receipt},ranked=[],catalog={},application_id=21,context='other',independent_scores=receipt)
            self.assertTrue(all(x.endswith('JD points unavailable') for x in st.labels))
            self.assertTrue(any('does not match the fitted generation' in x for x in st.captions))

    def test_production_wiring_preserves_selection_gate_and_exports_separate_receipt(self):
        root=Path(__file__).resolve().parents[1]
        bestof=(root/'tailoring/phase9f_automatic_bestof_v30_ui.py').read_text(encoding='utf-8')
        explorer=(root/'tailoring/phase9f_v364_decision_explorer.py').read_text(encoding='utf-8')
        self.assertIn('build_independent_bullet_scores(audit, projects, baseline_report, raw_jd_text)',bestof)
        self.assertIn("'independent_bullet_scores': independent_scores",bestof)
        self.assertIn('proposal=(proposal if pair_recorded else {})',explorer)
        self.assertIn('independent_scores=independent_scores',explorer)
        self.assertIn("elif independent_scores.get('status') == 'available':",bestof)


class NativeEvaluatorTests(unittest.TestCase):
    def test_real_saved_link_evaluator_uses_same_weights_and_large_pool(self):
        # Run only in the repository's full runtime, not the installer sandbox.
        from tailoring.stable_tailoring_ranking import build_bullet_evidence_priorities
        a,p,r=fixture(); got=build(a,p,r,JD)
        self.assertEqual(got['status'],'available',got)
        self.assertEqual(got['bullet_count'],33)
        for section, rank in zip(a['projects'],p['candidate_project_ranking']):
            pool,error=_source_pool(section,max_pool=512);self.assertFalse(error)
            if not rank['requirement_matches']:continue
            ids,error=_support(pool,rank,build_bullet_evidence_priorities)
            self.assertIsNotNone(ids,error)
            for entry, linked in zip(pool,ids):
                self.assertEqual(score(got,section['project'],entry['text'])['saved_jd_ids'],sorted(linked))
        self.assertEqual(score(got,P3,ZERO)['standalone_weighted_points'],0.0)

if __name__=='__main__': unittest.main()

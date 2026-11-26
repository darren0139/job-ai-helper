"""Focused V3.9 before-fitting dedupe tests; pure, without database or DOCX mutation."""
from __future__ import annotations
import unittest
from copy import deepcopy
from tailoring.phase9f_prefit_dedupe_v39 import (
    dedupe_prepared_projects, _same_work, _metadata, _rank, VERSION)

CI_BASE = ('Built 30-job corpus regression/audit tooling and GitHub Actions CI '
           'across Windows/Ubuntu to validate scoring, taxonomy resolution, sessions, and UI workflows.')
CI_LIB = ('Added automated unit tests and GitHub Actions CI across Ubuntu and Windows, '
          'running dependency checks, compilation, the full test suite, and a Streamlit startup health check.')
COVER = 'Added tailored cover letter generation and follow-up revision support grounded in the resume and job description.'
DB_BASE = 'Implemented PostgREST data access and Row-Level Security policies to support real-time queries while controlling database access.'
DB_LIB = 'Implemented backend data access through PostgREST and applied Row-Level Security policies to secure database operations.'


def project(title, bullets, sources, points=None):
    return {'display_title': title, 'draft_bullets': list(bullets),
            'selected_blueprint_bullets': list(bullets),
            'selected_bullet_sources': [list(s) for s in sources],
            'bullet_decision_receipts': [
                {'bullet': b, 'sources': list(s)} for b, s in zip(bullets, sources)],
            'bullet_evidence_priorities': [
                {'bullet_text': b, 'evidence_value': points[i] if points else 0.0,
                 'supported_requirement_ids': ['testing'] if i < 2 else [],
                 'protect_during_fitting': False}
                for i, b in enumerate(bullets)]}


class PrefitDedupeTests(unittest.TestCase):
    def test_ci_auto_removes_base_on_tie(self):
        raw={'recommended_projects': [project('Job AI Helper', [CI_LIB, CI_BASE, COVER],
                        [['library'], ['base'], ['library']], [9, 9, 0])]}
        snapshot=deepcopy(raw)
        result=dedupe_prepared_projects(raw)
        self.assertEqual(raw, snapshot)
        self.assertEqual(result['recommended_projects'][0]['draft_bullets'], [CI_LIB, COVER])
        record=result['_v39_auto_dedupe']
        self.assertEqual(record['status'], 'removed_before_fit')
        self.assertEqual(record['removals'][0]['removed'], CI_BASE)
        self.assertEqual(record['removals'][0]['retained'], CI_LIB)
        self.assertEqual(record['removals'][0]['removed_saved_evidence_points'], 9.0)

    def test_queryai_rls(self):
        raw={'recommended_projects': [project('QueryAI', [DB_LIB, DB_BASE],
                        [['library'], ['base']], [9, 9])]}
        result=dedupe_prepared_projects(raw)
        self.assertEqual(result['recommended_projects'][0]['draft_bullets'], [DB_LIB])
        self.assertEqual(len(result['_v39_auto_dedupe']['removals']), 1)

    def test_higher_score_wins_even_if_base(self):
        raw={'recommended_projects': [project('Job AI Helper', [CI_LIB, CI_BASE],
                        [['library'], ['base']], [3, 12])]}
        result=dedupe_prepared_projects(raw)
        self.assertEqual(result['recommended_projects'][0]['draft_bullets'], [CI_BASE])

    def test_distinct_work_kept(self):
        raw={'recommended_projects': [project('Job AI Helper', [CI_LIB, COVER],
                        [['library'], ['library']], [9, 0])]}
        self.assertEqual(dedupe_prepared_projects(raw)['recommended_projects'][0]['draft_bullets'], [CI_LIB, COVER])

    def test_shared_keyword_same_source_kept(self):
        raw={'recommended_projects': [project('Job AI Helper', [CI_LIB, CI_BASE],
                        [['library'], ['library']], [9, 9])]}
        self.assertEqual(len(dedupe_prepared_projects(raw)['recommended_projects'][0]['draft_bullets']), 2)

    def test_no_pair_across_projects(self):
        raw={'recommended_projects': [project('One', [CI_LIB], [['library']]),
                                      project('Two', [CI_BASE], [['base']])]}
        self.assertEqual(dedupe_prepared_projects(raw)['_v39_auto_dedupe']['removals'], [])

    def test_identical_wording_dedupes_without_source_tags(self):
        raw={'recommended_projects': [project('One', [CI_BASE, CI_BASE], [[], []])]}
        result=dedupe_prepared_projects(raw)
        self.assertEqual(result['recommended_projects'][0]['draft_bullets'], [CI_BASE])

    def test_unlabelled_nonidentical_refused(self):
        raw={'recommended_projects': [project('One', [CI_LIB, CI_BASE], [[], []])]}
        self.assertEqual(len(dedupe_prepared_projects(raw)['recommended_projects'][0]['draft_bullets']), 2)

    def test_locked_skips(self):
        raw={'recommended_projects': [project('One', [CI_LIB, CI_BASE], [['library'], ['base']])]}
        result=dedupe_prepared_projects(raw, enabled=False)
        self.assertEqual(len(result['recommended_projects'][0]['draft_bullets']), 2)
        self.assertEqual(result['_v39_auto_dedupe']['status'], 'projects_locked')

    def test_preserves_compact_index_alignment(self):
        raw={'recommended_projects': [project('One', [CI_LIB, CI_BASE], [['library'], ['base']], [9, 9])]}
        raw['recommended_projects'][0]['compact_bullets']=['compact lib','compact base']
        got=dedupe_prepared_projects(raw)['recommended_projects'][0]
        self.assertEqual(got['compact_bullets'], ['compact lib'])

    def test_all_project_final_scores_recorded(self):
        raw={'recommended_projects': [project('One', [CI_LIB, CI_BASE, COVER],
                                         [['library'], ['base'], ['library']], [9, 9, 0])]}
        got=dedupe_prepared_projects(raw)['_v39_auto_dedupe']['project_scores'][0]
        self.assertEqual([i['saved_evidence_points'] for i in got['bullets']], [9.0, 0.0])

    def test_numerical_high_unknown_protected(self):
        p=project('One',[CI_LIB, CI_BASE],[['library'],['base']],[9, 2])
        p['bullet_evidence_priorities'][1]['protect_during_fitting']=True
        got=dedupe_prepared_projects({'recommended_projects':[p]})
        self.assertEqual(got['recommended_projects'][0]['draft_bullets'], [CI_BASE])

if __name__=='__main__': unittest.main()

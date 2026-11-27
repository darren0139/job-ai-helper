"""Guarded V3.9 browser: exact final membership, related-only pair, scores."""
from __future__ import annotations

import hashlib
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from tailoring.phase9f_v39_final_bullet_review import (
    chosen_document, explain_pair, scored_wording,
)

BASE = 'Built 30-job regression audit tooling and GitHub Actions CI across Windows Ubuntu to validate scoring and taxonomy workflows.'
LIB = 'Added automated unit tests and GitHub Actions CI across Ubuntu and Windows with compilation and full test suite checks.'
COVER = 'Added tailored cover letter generation grounded in the job description.'
PROJECT = 'Job AI Helper'


def audit():
    return {'verified': True, 'docx_sha256': 'a'*64, 'generation_id': 'gen1',
            'projects': [{'project': PROJECT, 'final': [{'text': LIB}, {'text': BASE}, {'text': COVER}]}]}


def proposal():
    return {'projects': [{'project': PROJECT, 'after': [LIB, COVER]}],
            'v38_bullet_score_receipt': {'status': 'available', 'bullets': [
                {'project': PROJECT, 'wording': BASE, 'standalone_weighted_points': 9.0,
                 'saved_jd_ids': ['req_a'], 'marginal_in_proposal_points': None},
                {'project': PROJECT, 'wording': LIB, 'standalone_weighted_points': 13.0,
                 'saved_jd_ids': ['req_a','req_b'], 'marginal_in_proposal_points': 4.0}]}}


class FinalBulletReviewTests(unittest.TestCase):
    def test_existing_file_keeps_both_even_if_b_was_proposed(self):
        got = chosen_document(audit(), {'status': 'verified', 'winner': 'existing_final',
                                        'proposal': proposal()})
        self.assertEqual('verified_fitted', got['status'])
        self.assertEqual(3, len(got['bullets']))
        self.assertEqual([], got['removed'])
        self.assertEqual('not_applied', got['deduplication_status'])

    def test_challenger_hash_generation_and_readback_gate(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            candidate = root/'outputs'/'tailored_resumes'/'optimizations'/'out.docx'
            candidate.parent.mkdir(parents=True)
            candidate.write_bytes(b'FAKE-DOCX-BYTES')
            digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
            receipt = {'status': 'verified', 'winner': 'optimized_candidate',
                       'generation_id': 'gen1', 'a_docx_sha256': 'a'*64,
                       'b_docx_sha256': digest, 'candidate_file': str(candidate),
                       'proposal': proposal()}
            stub = types.ModuleType('tailoring.phase9f_final_evidence_comparison_v2_4')
            stub._read_exact_docx_bullets = lambda _path,_names: ({PROJECT: [LIB, COVER]}, '')
            with patch.dict(sys.modules, {'tailoring.phase9f_final_evidence_comparison_v2_4': stub}):
                got = chosen_document(audit(), receipt, repo_root=root)
                self.assertEqual('verified_challenger', got['status'])
                self.assertEqual([BASE], [x['bullet'] for x in got['removed']])
                self.assertEqual([LIB, COVER], [x['bullet'] for x in got['bullets']])
                candidate.write_bytes(b'TAMPERED')
                self.assertEqual('unavailable', chosen_document(audit(), receipt, repo_root=root)['status'])
                candidate.write_bytes(b'FAKE-DOCX-BYTES')
                stub._read_exact_docx_bullets = lambda _path,_names: ({PROJECT: [LIB, BASE]}, '')
                self.assertEqual('unavailable', chosen_document(audit(), receipt, repo_root=root)['status'])
            receipt['generation_id'] = 'gen2'
            self.assertEqual('unavailable', chosen_document(audit(), receipt, repo_root=root)['status'])

    def test_missing_audit_never_renders_proposal_as_final(self):
        got = chosen_document({'verified': False}, {'winner': 'optimized_candidate'})
        self.assertEqual('unavailable', got['status'])
        self.assertFalse(got['bullets'])

    def test_saved_weights_per_exact_bullet_only(self):
        p = proposal()
        self.assertEqual(9.0, scored_wording(p, PROJECT, BASE)['standalone_weighted_points'])
        self.assertEqual(13.0, scored_wording(p, PROJECT, LIB)['standalone_weighted_points'])
        self.assertIsNone(scored_wording(p, 'Another project', BASE))
        self.assertIsNone(scored_wording(p, PROJECT, COVER))
        p['v38_bullet_score_receipt']['status'] = 'unavailable'
        self.assertIsNone(scored_wording(p, PROJECT, LIB))

    def test_related_ci_not_covered_by_unrelated_cover_letter(self):
        ranked = [
            {'project': PROJECT, 'bullet': BASE, 'sources': ['Selected Base']},
            {'project': PROJECT, 'bullet': LIB, 'sources': ['Evidence Library']},
            {'project': PROJECT, 'bullet': COVER, 'sources': ['Evidence Library']},
            {'project': 'Another project', 'bullet': LIB, 'sources': ['Evidence Library']},
        ]
        pair = explain_pair(final={'project': PROJECT, 'bullet': BASE}, ranked=ranked, proposal=proposal())
        self.assertEqual(BASE, pair['base']['bullet'])
        self.assertEqual(LIB, pair['library']['bullet'])
        self.assertNotIn(COVER, str(pair))

    def test_related_request_tracker_is_not_a_same_work_pair(self):
        from tailoring.phase9f_same_work_selection_v37 import _confident_same_work
        from tailoring.phase9f_v39_final_bullet_review import RELATED_EVIDENCE

        base = 'Built a full-stack IT service request tracker with JWT authentication, role-based access control, request workflows, comments, and admin-only internal notes.'
        library = 'Built a full-stack IT service request tracker with React, TypeScript, FastAPI, and PostgreSQL, spanning application development, database design, and RESTful APIs.'
        ranked = [
            {'project': 'RequestFlow', 'bullet': base, 'sources': ['Selected Base']},
            {'project': 'RequestFlow', 'bullet': library, 'sources': ['Evidence Library']},
            {'project': 'Different project', 'bullet': library, 'sources': ['Evidence Library']},
        ]
        final = {'project': 'RequestFlow', 'bullet': base}
        self.assertFalse(_confident_same_work(base, library))
        self.assertIsNone(explain_pair(final=final, ranked=ranked, proposal={})['library'])
        pair = explain_pair(final=final, ranked=ranked, proposal={}, mode=RELATED_EVIDENCE)
        self.assertEqual(ranked[1], pair['library'])
        self.assertFalse(pair['overlap'])
        self.assertIn('1 eligible of 1', pair['reason'])

    def test_manual_comparison_keeps_independent_project_widgets_and_scores(self):
        from streamlit.testing.v1 import AppTest

        second = 'Another project'
        unrelated_base = 'Configured JWT authentication for a private admin workflow.'
        unrelated_library = 'Designed a database schema with PostgreSQL and wrote data migration scripts.'
        fitted = audit()
        fitted['projects'][0].update(base=[{'text': BASE}], library=[{'text': LIB}])
        fitted['projects'].append({'project': second, 'base': [{'text': unrelated_base}],
                                   'library': [{'text': unrelated_library}],
                                   'final': [{'text': unrelated_library}]})
        current = proposal()['v38_bullet_score_receipt']
        current['scope'] = {'generation_id': 'gen1', 'a_docx_sha256': 'a'*64, 'raw_jd_sha256': 'b'*64}
        current['bullets'].append({'project': second, 'wording': unrelated_library,
                                   'saved_jd_ids': ['req_c'], 'standalone_weighted_points': 12.0})
        script = f"""
import streamlit as st
from tailoring.phase9f_v39_final_bullet_review import render_verified_final_bullets
render_verified_final_bullets(st, audit={fitted!r}, result={{}}, proposal={{}},
                              ranked=[], catalog={{}}, application_id=22,
                              context='headless', independent_scores={current!r})
"""
        app = AppTest.from_string(script, default_timeout=30).run()
        self.assertFalse(app.exception)
        next(control for control in app.checkbox if control.label == second).check().run()
        for control in list(app.selectbox):
            if control.label == 'Comparison mode':
                app.selectbox(key=control.key).set_value('Manual comparison').run()
        self.assertFalse(app.exception)
        keys = [control.key for control in app.selectbox]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertIn('12.000', [metric.value for metric in app.metric])
        self.assertEqual(3, len(app.metric))
        self.assertTrue(any('Weighted JD score unavailable' in caption.value for caption in app.caption))
        self.assertTrue(any('Exact wording absent' in caption.value for caption in app.caption))

    def test_partial_testing_explanation_agrees_with_saved_links(self):
        from tailoring.phase9f_v39_final_bullet_review import _show_shared_saved_links

        notes = []
        st = types.SimpleNamespace(caption=notes.append)
        inputs = {'base': {'bullet': BASE}, 'library': {'bullet': LIB}}
        saved = proposal()
        rows = saved['v38_bullet_score_receipt']['bullets']
        rows[0].update(saved_jd_ids=[], standalone_weighted_points=0)
        rows[1].update(saved_jd_ids=['req_a'], standalone_weighted_points=9)
        catalog = {'req_a': {'text': 'Execute unit, integration, system and user acceptance testing',
                             'importance': 'core'}}
        _show_shared_saved_links(st, inputs, saved, PROJECT, catalog)
        self.assertIn('Base Resume wording does not establish these requested test types · user acceptance, integration, system, unit.', notes)
        self.assertIn('Evidence Library wording does not establish these requested test types · user acceptance, integration, system.', notes)

    def test_exact_same_wording_does_not_compete_against_itself(self):
        ranked = [{'project': PROJECT, 'bullet': LIB, 'sources': ['Selected Base','Evidence Library']}]
        pair = explain_pair(final={'project': PROJECT,'bullet': LIB}, ranked=ranked, proposal={})
        self.assertEqual('shared', pair['source'])
        self.assertIs(pair['base'], pair['library'])

    def test_unverified_source_does_not_infer_competitor(self):
        pair = explain_pair(final={'project': PROJECT, 'bullet': LIB}, ranked=[], proposal=proposal())
        self.assertEqual('unknown', pair['source'])
        self.assertIsNone(pair['base'])

if __name__ == '__main__':
    unittest.main()

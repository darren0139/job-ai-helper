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

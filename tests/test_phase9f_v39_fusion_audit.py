"""Regression tests for Phase 9F final-DOCX evidence audit and saved bullet fusion."""
from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from tailoring.phase9f_final_evidence_comparison_v2_4 import (
    _expected_final_counts, build_final_evidence_audit,
)

TITLE = 'Example Help Desk — App'
A = 'Implemented secure database access using a service.'
B = 'Added row-level security for database operations.'
MERGED = 'Implemented secure database access and row-level security.'


def fusion(project=TITLE):
    return {
        'change_type': 'bullet_fusion',
        'section': 'projects',
        'project': project,
        'project_index': 0,
        'source_bullet_indexes': [0, 1],
        'merged_bullet_index': 0,
        'source_bullets': [A, B],
        'merged_bullet': MERGED,
        'source_bullet_count': 2,
        'merged_bullet_count': 1,
    }


def fitted(events, bullets=None):
    return {
        'fitting_input_snapshot': {
            'prepared_initial_state': {
                'projects': {'recommended_projects': [
                    {'display_title': TITLE, 'draft_bullets': bullets or [A, B]},
                ]},
            },
        },
        'remaining_active_reductions': events,
    }


class FittingAuditFusionTests(unittest.TestCase):
    def test_fusion_counts_as_one_less_bullet(self):
        counts, events, reason = _expected_final_counts(fitted([fusion()]), [TITLE])
        self.assertEqual(reason, '')
        self.assertEqual(counts, {TITLE: 1})
        self.assertEqual([e['change_type'] for e in events[TITLE]], ['bullet_fusion'])

    def test_unrelated_skill_event_ignored(self):
        rows = [fusion(), {'change_type': 'reduce_skill', 'section': 'skills'}]
        counts, events, reason = _expected_final_counts(fitted(rows), [TITLE])
        self.assertEqual((reason, counts), ('', {TITLE: 1}))
        self.assertEqual(len(events[TITLE]), 1)

    def test_unknown_project_still_blocked(self):
        counts, _, reason = _expected_final_counts(fitted([fusion('Another project')]), [TITLE])
        self.assertIsNone(counts)
        self.assertIn('known project', reason)

    def test_unknown_action_still_blocked(self):
        bad = {**fusion(), 'change_type': 'unreviewed_fitting_action'}
        counts, _, reason = _expected_final_counts(fitted([bad]), [TITLE])
        self.assertIsNone(counts)
        self.assertIn('known project', reason)

    def test_bad_fusion_receipts_refused(self):
        cases = [
            {'source_bullet_indexes': [1, 0]},
            {'source_bullet_indexes': [0, 2]},
            {'source_bullet_indexes': [0, True]},
            {'source_bullet_count': 3},
            {'merged_bullet_count': 2},
            {'merged_bullet': ''},
            {'source_bullets': [A]},
            {'source_bullets': [A, '']},
            {'merged_bullet_index': 1},
            {'section': 'education'},
        ]
        for replacement in cases:
            with self.subTest(replacement=replacement):
                counts, _, reason = _expected_final_counts(fitted([{**fusion(), **replacement}]), [TITLE])
                self.assertIsNone(counts)
                self.assertIn('fusion', reason.lower())

    def test_underrun_fusion_refused(self):
        counts, _, reason = _expected_final_counts(fitted([fusion()], [A]), [TITLE])
        self.assertIsNone(counts)
        self.assertIn('fusion', reason.lower())

    def _run_docx(self, *, actual_bullets):
        from docx import Document
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / 'outputs' / 'tailored_resumes'
            out.mkdir(parents=True)
            path = out / 'app_156_audit_fusion_fixture.docx'
            document = Document()
            document.add_paragraph('PROJECTS')
            document.add_paragraph(TITLE)
            for text in actual_bullets:
                document.add_paragraph(text, style='List Bullet')
            document.add_paragraph('SKILLS')
            document.save(path)
            fit = {
                **fitted([fusion()]),
                'docx_path': str(path),
                'fit_one_page': True, 'fit_status': 'verified_one_page',
                'page_count': 1, 'generation_id': 'fixture-generation',
            }
            source_view = {'projects': [{
                'project': TITLE, 'base_bullets': [], 'library_bullets': [],
                'draft_bullets': [], 'source': 'fixture', 'rank': 1,
                'bullet_source_policy_version': 'phase9f-combined-project-bullet-sources-v2.7',
            }]}
            stub = types.ModuleType('tailoring.phase9f_project_bullet_sources_v2_3')
            stub.build_project_bullet_source_view = lambda projects, candidates: source_view
            with patch.dict(sys.modules, {'tailoring.phase9f_project_bullet_sources_v2_3': stub}):
                result = build_final_evidence_audit(
                    projects={'recommended_projects': []}, fit=fit,
                    candidates=[], repo_root=root, application_id=156,
                    expected_generation_id='fixture-generation',
                )
            return result

    def test_full_docx_audit_accepts_fusion_with_real_readback(self):
        result = self._run_docx(actual_bullets=[MERGED])
        self.assertTrue(result['verified'], result.get('notice'))
        self.assertEqual(result['projects'][0]['final_count'], 1)
        changes = result['projects'][0]['changes']
        self.assertEqual(len(changes), 1)
        self.assertIn('Fused', changes[0]['action'])
        self.assertEqual(changes[0]['text'], MERGED)
        self.assertEqual(changes[0]['source_bullets'], [A, B])

    def test_actual_docx_count_mismatch_still_withheld(self):
        result = self._run_docx(actual_bullets=[A, B])
        self.assertFalse(result['verified'])
        self.assertIn('bullet counts disagree', result['notice'])


if __name__ == '__main__':
    unittest.main()

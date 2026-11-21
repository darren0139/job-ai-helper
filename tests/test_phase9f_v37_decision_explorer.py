"""Focused read-only contracts for the decision summary and evidence ranking."""
from __future__ import annotations

import unittest

from tailoring.phase9f_v363_selection_receipts import build_bullet_selection_calculation
from tailoring.phase9f_v364_decision_explorer import (
    ALL, CHANGES, INCLUDED, _verified_coverage_changes, render_compact_decision_explorer,
)
from tailoring.phase9f_v365_jd_evidence import audit_fragment, rank_bullets, requirement_catalog
from tests.test_phase9f_v365_explainability import FakeStreamlit


RAW = 'Use Python for unit testing.\nMaintain\u202fPostgreSQL databases.\nDevelop and deploy services.'


def requirement(rid, text, importance, **fields):
    return {'requirement_id': rid, 'text': text, 'parent_text': text, 'importance': importance, **fields}


BASELINE = {
    'raw_jd_text': RAW,
    'stable_analysis': {'canonical_requirements': [
        requirement('testing', 'Use Python for unit testing', 'core'),
        requirement('db', 'Maintain PostgreSQL databases', 'preferred',
                    scoring_parent_occurrence_id='source-db', group_weight_fraction=0.5,
                    source_provenance=[{'grounding': {'span_id': 'db-span', 'line_index': 2}}]),
    ]},
}


def candidate(text, sources, ids, *, existing=False, selected=False):
    return {'text': text, 'source_labels': sources, 'saved_jd_ids': ids,
            'word_count': len(text.split()), 'in_original_a': existing, 'selected_for_proposed_b': selected}


def calculation(candidates):
    return build_bullet_selection_calculation(
        {'source_comparison': {'projects': [{'project': 'Project one', 'candidates': candidates}]}}, {})


class DecisionExplorer(unittest.TestCase):
    def test_native_whole_document_change_requires_both_matching_receipts(self):
        catalog = requirement_catalog(BASELINE, {})
        result = {'a_docx_sha256': 'before', 'b_docx_sha256': 'after', 'native_document_evidence': {
            'existing': {'docx_sha256': 'before', 'requirements': [
                {'requirement_id': 'testing', 'match_label': 'weak'},
                {'requirement_id': 'db', 'match_label': 'none'},
            ]},
            'alternative': {'docx_sha256': 'after', 'requirements': [
                {'requirement_id': 'testing', 'match_label': 'weak'},
                {'requirement_id': 'db', 'match_label': 'transferable'},
            ]},
        }}
        self.assertEqual(_verified_coverage_changes(result, catalog), [
            {'text': 'Maintain PostgreSQL databases', 'importance': 'preferred',
             'before': 'none', 'after': 'transferable'},
        ])
        self.assertEqual(_verified_coverage_changes({**result, 'a_docx_sha256': 'changed'}, catalog), [])

    def test_exact_dual_provenance_and_distinct_wording(self):
        exact = 'Added Python unit tests.'
        similar = 'Added Python unit tests for the API.'
        calc = calculation([
            candidate(exact, ['Selected Base'], ['testing'], existing=True),
            candidate(exact, ['Evidence Library'], ['testing'], selected=True),
            candidate(similar, ['Evidence Library'], ['testing']),
        ])
        self.assertEqual(len(calc['rows']), 2)
        shared, different = calc['rows']
        self.assertEqual(shared['sources'], ['Selected Base', 'Evidence Library'])
        self.assertTrue(shared['in_actual_a'] and shared['in_proposed_b'])
        self.assertEqual(shared['saved_jd_ids'], ['testing'])
        self.assertEqual(different['bullet'], similar)

    def test_native_evidence_excerpts_are_distinct_from_lexical_and_impact(self):
        exact = 'Added Python unit tests.'
        calc = calculation([
            candidate('Used Python for unit testing in a test harness.', ['Selected Base'], ['testing'], selected=True),
            candidate(exact, ['Evidence Library'], ['testing'], selected=True),
            candidate('Maintained PostgreSQL databases.', ['Evidence Library'], ['db']),
            candidate('Refactored the settings dialog.', ['Selected Base'], ['testing']),
        ])
        snap = {'docx_sha256': 'verified-hash', 'requirements': [
            {'requirement_id': 'testing', 'match_label': 'weak', 'evidence_strength': 2,
             'evidence': [{'section': 'projects', 'text': exact}]},
        ]}
        result = {'status': 'verified', 'b_docx_sha256': 'verified-hash',
                  'native_document_evidence': {'alternative': snap}}
        catalog = requirement_catalog(BASELINE, {})
        ranked = rank_bullets(calc['rows'], catalog, raw_jd_text=RAW, result=result)
        self.assertEqual(ranked[0]['bullet'], exact)
        self.assertEqual(ranked[0]['jd_links'][0]['status'], 'Native document evidence')
        self.assertEqual(ranked[0]['jd_links'][0]['native_evidence']['alternative']['strength'], 2)
        self.assertEqual(ranked[0]['native_impact_status'], 'unknown')
        self.assertEqual(ranked[0]['coverage']['Saved links with lexical cues']['Shared in alternative'], [catalog['testing']])
        self.assertEqual(ranked[2]['coverage']['Saved links with lexical cues']['Absent from alternative'], [catalog['db']])
        self.assertEqual(ranked[-1]['jd_links'][0]['status'], 'Questionable saved link')
        self.assertEqual(ranked[-1]['traceable_lexical_link_ids'], [])
        stale = rank_bullets(calc['rows'], catalog, raw_jd_text=RAW, result={**result, 'b_docx_sha256': 'different'})
        self.assertTrue(all(not row['native_requirement_ids'] for row in stale))

    def test_source_warnings_are_independent_of_grammar_and_keep_parent_allocation(self):
        req = requirement_catalog(BASELINE, {})['db']
        normalized = audit_fragment(req['text'], parent_sentence=req['parent'], raw_jd_text=RAW)
        self.assertEqual(normalized['source_status'], 'text_normalization_difference')
        self.assertTrue(normalized['eligible_for_bonus_explanation'])
        self.assertEqual(req['group_weight_fraction'], 0.5)
        self.assertEqual(req['source_provenance'][0]['grounding']['span_id'], 'db-span')
        mismatch = audit_fragment(req['text'], parent_sentence=req['parent'],
                                  raw_jd_text='A different JD.', expected_jd_text=RAW)
        self.assertEqual(mismatch['source_status'], 'source_identity_mismatch')
        self.assertEqual(mismatch['grammar_status'], 'no_boundary_warning')
        self.assertEqual(audit_fragment('deploy services')['source_status'], 'missing_source')
        clipped = audit_fragment('and deploy services', parent_sentence='Develop and deploy services', raw_jd_text=RAW)
        self.assertEqual(clipped['grammar_status'], 'clipped_boundary')
        self.assertFalse(clipped['eligible_for_bonus_explanation'])

    def test_compact_render_names_filters_and_unknown_impact_once(self):
        class UI(FakeStreamlit):
            def __init__(self):
                super().__init__()
                self.filters = {}

            def selectbox(self, label, options, **kwargs):
                self.filters[label] = list(options)
                return CHANGES if label == 'Show bullets' else list(options)[0]

            def dataframe(self, *args, **kwargs):
                raise AssertionError('Decision Explorer should display compact, expandable bullet rows')

        bullet = 'Performed automated Python unit testing in the project'
        calc = calculation([candidate(bullet, ['Selected Base'], ['testing'], existing=True),
                            candidate('Added Python unit tests.', ['Evidence Library'], ['testing'], selected=True)])
        ui = UI()
        render_compact_decision_explorer(
            ui, calc=calc, result={'status': 'verified', 'winner': 'existing_final', 'a_score': 31, 'b_score': 31},
            proposal={}, audit={}, projects={}, application_id=1, context='fixture',
            baseline_report=BASELINE, raw_jd_text=RAW,
        )
        self.assertEqual(ui.filters['Show bullets'], [ALL, CHANGES, INCLUDED])
        labels = [label for label, _ in ui.expander_args]
        self.assertTrue(any('Base bullet' in label for label in labels))
        self.assertTrue(any('Library bullet' in label for label in labels))
        rendered = ' '.join(ui.logs)
        self.assertIn(bullet, rendered)
        self.assertIn('Optimized alternative 31', rendered)
        self.assertEqual(rendered.count('Native per-bullet impact is unknown'), 1)
        self.assertNotIn('A/B', rendered)


if __name__ == '__main__':
    unittest.main()

"""Independent Stage 2I delta; historical inputs and oracles stay immutable."""
import json
from copy import deepcopy
import types
import unittest
from unittest.mock import patch

import streamlit as st

from analysis_stability import stable_evidence_scoring as native
from scripts import coordinated_conflict_acceptance as preview
from scripts import coordinated_batch_dashboard as dashboard
from tests.test_coordinated_batch_dashboard import app_test
from analysis_stability.coordinated_runtime import assert_analysis_publishable


class ConflictAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.batch = preview.run_batch(dashboard.revision_key())

    def test_all_38_independent_deltas_and_withholding(self):
        fixture = json.loads(preview.EXPECTATIONS.read_text(encoding='utf-8'))
        self.assertEqual(len(self.batch['rows']), 38)
        self.assertEqual(len({r['Case'] for r in self.batch['rows']}), 38)
        self.assertEqual(self.batch['errors'], [])
        self.assertEqual(self.batch['expectation_mismatches'], [])
        self.assertEqual(self.batch['counts'], fixture['expected_realistic_counts'])
        self.assertEqual(self.batch['withheld'], fixture['expected_realistic_withheld'])
        changed = [r['Case'] for r in self.batch['rows'] if r['Actual'] != r['Stage 2H actual']]
        self.assertEqual(changed, fixture['changed_selected_cases'])
        quarantined = [r['Case'] for r in self.batch['rows'] if r['Conflicted parents']]
        self.assertEqual(set(quarantined), set(changed+fixture['changed_companion_cases']))

    def test_terminal_quarantine_preserves_original_receipts_and_no_numeric_credit(self):
        for case_id in ('E04', 'E05', 'B05', 'E24', 'C03'):
            analysis = self.batch['details'][case_id]['after']
            self.assertIsNone(analysis['deterministic_alignment_score'])
            affected = [r for r in analysis['canonical_requirements']
                        if (r.get('coordinated_action_receipt', {}).get('scoped_conflict') or {}).get('quarantine')]
            self.assertEqual(len(affected), 1)
            row = affected[0]
            receipt = row['coordinated_action_receipt']
            self.assertEqual(receipt['disposition'], 'REVIEW_REQUIRED')
            self.assertIsNone(row['match_label'])
            self.assertIsNone(receipt['synthetic_parent_contribution'])
            self.assertEqual(row['evidence'], [])
            self.assertEqual(receipt['stages'][-1]['stage'], 'terminal_scoped_conflict_quarantine')
            conflict = receipt['scoped_conflict']
            self.assertEqual(conflict['status'], 'PROVEN_CONFLICT')
            self.assertTrue(conflict['selected_positive']['text'])
            self.assertTrue(conflict['findings'][0]['negative_original']['original_text'])
            self.assertEqual(conflict['findings'][0]['relationship'], 'SAME_ORIGINAL_CONTAINER')

    def test_duplicate_occurrences_survive_without_fallback_or_union(self):
        analysis = self.batch['details']['E24']['after']
        ledger = analysis['original_source_occurrence_ledger']['occurrences']
        bullets = [r for r in ledger if r['kind'] == 'BULLET']
        duplicates = [r for r in bullets if r['text'] == bullets[0]['text']]
        self.assertEqual(len(duplicates), 2)
        self.assertEqual(len({r['occurrence_id'] for r in duplicates}), 2)
        conflict = self.batch['details']['E24']['after_rows'][0]['coordinated_action_receipt']['scoped_conflict']
        self.assertEqual(conflict['selected_positive']['source'], 'resume_profile.projects[0].bullets[0]')
        self.assertEqual(conflict['selection_policy'], 'UNCHANGED_NATIVE_SELECTION_NO_LEDGER_FALLBACK')
        for case_id in ('E03', 'B02', 'E06'):
            self.assertIsNone(self.batch['details'][case_id]['after_rows'][0]['match_label'])

    def test_uncertain_scope_is_terminal_in_actual_pipeline_and_identity_is_guarded(self):
        parent = next(p for p in dashboard.acceptance.parents() if p['obligation']['object_family'] == 'embedded')
        for relation, tail, expected in (('same', ' before 2020', None),
                                         ('summary', '', None), ('different', '', 'direct')):
            profile = deepcopy(self.batch['details']['E01']['original_profile'])
            denial = 'Never maintained '+parent['obligation']['object']+tail+'.'
            if relation == 'summary':
                profile['summary'] = denial
            elif relation == 'different':
                profile['projects'][1]['bullets'].append(denial)
            else:
                profile['projects'][0]['bullets'].append(denial)
            analysis = native.build_stable_analysis(jd_profile={}, keyword_match={}, resume_profile=profile,
                raw_resume_text='', raw_jd_text=parent['raw_jd'], retrieval_mode_override='off',
                coordinated_actions_enabled=True)
            row = next(r for r in analysis['canonical_requirements'] if
                       r.get('scoring_parent_occurrence_id') == parent['parent_occurrence_id'])
            self.assertEqual(row['match_label'], expected)
            if expected is None:
                self.assertIsNone(analysis['deterministic_alignment_score'])
                self.assertEqual(row['coordinated_action_receipt']['scoped_conflict']['status'], 'UNCERTAIN_SCOPE')
        analysis = self.batch['details']['E01']['after']
        self.assertEqual(analysis['scoring_version'], 'stable-evidence-v1.20-phase6d24')
        with self.assertRaisesRegex(ValueError, 'cannot be persisted'):
            assert_analysis_publishable({'scoring_version': analysis['scoring_version']})

    def test_dashboard_retains_batch_and_exposes_conflicting_originals(self):
        with patch.object(native, 'build_stable_analysis', wraps=native.build_stable_analysis) as builder:
            app = app_test().run()
            self.assertFalse(app.toggle[0].value)
            app.button(key='run_realistic_batch').click().run(timeout=240)
            self.assertFalse(app.exception)
            calls = builder.call_count
            app.selectbox(key='realistic_inspect').set_value('E24').run()
            self.assertFalse(app.exception)
            self.assertEqual(builder.call_count, calls)
            self.assertTrue(any('Scoped conflict' in w.value for w in app.warning))
            tables = [d.value for d in app.dataframe]
            self.assertTrue(any('Original text' in t.columns for t in tables))
            table = next(t for t in tables if {'Case', 'Actual', 'Alignment %'} <= set(t.columns))
            self.assertEqual(set(table.loc[table['Withheld'], 'Alignment %']), {'Unavailable'})
            app.multiselect(key='realistic_jobs').set_value(['359 / embedded']).run()
            self.assertEqual(builder.call_count, calls)
            self.assertFalse(app.exception)
            self.assertTrue(all(not e.proto.expanded for e in app.expander))
            # Native dataframe event boundary: AppTest cannot itself click rows.
            app.multiselect(key='realistic_jobs').set_value([]).run()
            original = st.dataframe
            index = next(i for i, r in enumerate(self.batch['rows']) if r['Case'] == 'C03')
            def selection(*args, **kwargs):
                result = original(*args, **kwargs)
                if str(kwargs.get('key', '')).startswith('realistic_grid_'):
                    return types.SimpleNamespace(selection=types.SimpleNamespace(rows=[index]))
                return result
            with patch.object(st, 'dataframe', side_effect=selection):
                app.run()
            self.assertFalse(app.exception)
            self.assertEqual(app.selectbox(key='realistic_inspect').value, 'C03')
            self.assertTrue(any('Scoped conflict' in w.value for w in app.warning))
            self.assertEqual(builder.call_count, calls)

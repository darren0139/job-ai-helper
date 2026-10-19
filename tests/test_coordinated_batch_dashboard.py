"""One real 60-case AppTest batch, then UI-only interactions over retained receipts."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import types
import unittest
import uuid
from unittest.mock import patch

import streamlit as st
from analysis_stability import stable_evidence_scoring as n
from database import job_match_manager, analysis_cache_manager
from scripts import coordinated_batch_dashboard as dashboard


def app_test():
    folder = Path(tempfile.gettempdir())/('batch-ui-streamlit-'+uuid.uuid4().hex)
    folder.mkdir()
    with patch('tempfile.TemporaryDirectory', return_value=types.SimpleNamespace(name=str(folder))):
        from streamlit.testing.v1 import AppTest
    return AppTest.from_file(str(dashboard.ROOT/'coordinated_actions_preview.py'), default_timeout=240)


class BatchDashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patches = [patch.object(n, 'build_stable_analysis', wraps=n.build_stable_analysis),
            patch.object(dashboard.acceptance, 'comparison', wraps=dashboard.acceptance.comparison),
            patch.object(job_match_manager, 'save_job_match_snapshot', side_effect=AssertionError('No persistence')),
            patch.object(analysis_cache_manager, 'save_analysis_snapshot', side_effect=AssertionError('No persistence')),
            patch.object(analysis_cache_manager, 'persist_explicit_application_analysis', side_effect=AssertionError('No persistence'))]
        cls.builder, cls.comparison, *cls.savers = [p.start() for p in cls.patches]
        cls.app = app_test().run()
        cls.initial_gate_values = [c.kwargs.get('coordinated_actions_enabled', False) for c in cls.builder.call_args_list]
        cls.initial_comparisons = cls.comparison.call_count
        cls.app.button(key='run_acceptance_batch').click().run(timeout=240)
        if cls.app.exception:
            raise AssertionError([e.message for e in cls.app.exception])
        cls.batch = cls.app.session_state['acceptance_batch']
        cls.batch_builder_count = cls.builder.call_count
        cls.batch_comparison_count = cls.comparison.call_count

    @classmethod
    def tearDownClass(cls):
        for p in reversed(cls.patches):
            p.stop()

    def setUp(self):
        for key in ('batch_jobs', 'batch_scenarios', 'batch_dispositions'):
            self.app.multiselect(key=key).set_value([])
        self.app.run()

    def table(self):
        return next(frame.value for frame in self.app.dataframe
                    if {'Scenario', 'P3', 'Before rows'} <= set(frame.value.columns)
                    and 'Expected' not in frame.value.columns)  # historical delta grid is separate

    def key(self, family, scenario):
        return next(r['Case'] for r in self.batch['rows']
                    if r['Job'].endswith('/ '+family) and r['Scenario'] == scenario)

    def test_batch_represents_all_60_once_and_reference_agreement(self):
        self.assertEqual(self.batch_comparison_count, 60)
        self.assertEqual(len(self.batch['rows']), 60)
        self.assertEqual(len({r['Case'] for r in self.batch['rows']}), 60)
        self.assertEqual(len(self.table()), 60)
        stats = dashboard.totals(self.batch)
        reference = json.loads(dashboard.R1_EXPECTATIONS.read_text(encoding='utf-8'))
        self.assertEqual({k: stats[k] for k in reference['expected_counts']}, reference['expected_counts'])
        self.assertEqual(stats['reference_mismatches'], 14)
        self.assertEqual(stats['current_mismatches'], 0)
        self.assertEqual(stats['unexpected_historical_changes'], 0)
        self.assertEqual(stats['exceptions'], 0)
        self.assertGreater(stats['independent_checks'], 0)
        self.assertEqual(stats['independent_checks'], stats['independent_agreements'])
        self.assertLess(stats['independent_covered_cases'], 60)
        self.assertEqual(set(self.table()['P3']), {'DIRECT', 'WEAK', 'NONE', 'REVIEW_REQUIRED'})

    def test_default_off_and_no_database_persistence(self):
        self.assertEqual(self.initial_comparisons, 0)
        self.assertTrue(self.initial_gate_values)
        self.assertFalse(any(self.initial_gate_values))
        self.assertFalse(self.app.toggle[0].value)
        for saver in self.savers:
            saver.assert_not_called()

    def test_activity_declaration_is_preserved_when_requirement_asks_for_deploy(self):
        result = self.batch['details'][self.key('cloud', 'Maintenance only')]
        checks = dashboard.independent_checks(result, 'cloud')
        oracle = next(c for c in checks if c['authority'] == 'Stage 2B independent action oracle')
        self.assertEqual(oracle['declared_activities'], ['maintain'])
        self.assertEqual(oracle['mandatory_actions'], ['deploy', 'design', 'develop'])
        self.assertEqual(oracle['expected'], [])
        self.assertEqual(oracle['actual'], [])
        self.assertTrue(oracle['agrees'])

    def test_filters_and_inspection_do_not_recompute(self):
        builders, comparisons = self.builder.call_count, self.comparison.call_count
        self.app.multiselect(key='batch_jobs').set_value(['359 / embedded']).run()
        self.assertEqual(len(self.table()), 12)
        self.app.multiselect(key='batch_scenarios').set_value(['Maintenance only']).run()
        self.assertEqual(len(self.table()), 1)
        self.app.multiselect(key='batch_dispositions').set_value(['REVIEW_REQUIRED']).run()
        self.assertEqual(len(self.table()), 1)
        self.app.multiselect(key='batch_dispositions').set_value(['COMPLETE']).run()
        self.assertTrue(any('No scenarios match' in info.value for info in self.app.info))
        self.assertEqual(self.builder.call_count, builders)
        self.assertEqual(self.comparison.call_count, comparisons)

    def test_selection_details_cover_labels_and_original_sources(self):
        builders, comparisons = self.builder.call_count, self.comparison.call_count
        for family, scenario, effective in [
            ('embedded', 'Maintenance only', None), ('embedded', 'Design and development', 'weak'),
            ('embedded', 'All mandatory actions', 'direct'), ('fullstack', 'Design and development', 'none'),
            ('embedded', 'Complete alternative second bullet', 'direct')]:
            key = self.key(family, scenario)
            self.app.selectbox(key='batch_inspect').select(key).run()
            self.assertFalse(self.app.exception)
            result = self.batch['details'][key]
            self.assertEqual(result['after_rows'][0]['match_label'], effective)
            self.assertTrue(any(scenario in c.value for c in self.app.caption))
            sources = next(frame.value for frame in self.app.dataframe if 'Evidence ID' in frame.value.columns)
            expected = result['after_rows'][0]['coordinated_action_receipt']['proofs']
            self.assertEqual(set(sources['Evidence ID']), set(expected))
            if scenario == 'Complete alternative second bullet':
                chosen = sources[sources['Selected']]
                self.assertEqual(chosen.iloc[0]['Source'], 'resume_profile.projects[0].bullets[1]')
            if result['after']['deterministic_alignment_score'] is None:
                self.assertTrue(any('alignment unavailable' in w.value for w in self.app.warning))
                self.assertFalse(any(m.label == 'Synthetic whole-JD alignment' for m in self.app.metric))
            else:
                self.assertTrue(any(m.label == 'Synthetic whole-JD alignment' for m in self.app.metric))
        self.assertEqual(self.builder.call_count, builders)
        self.assertEqual(self.comparison.call_count, comparisons)

    def test_dataframe_selection_event_routes_to_stored_case(self):
        # AppTest cannot click a dataframe row. Render the real native table,
        # then inject its documented event shape at the widget boundary.
        index = next(i for i, row in enumerate(self.batch['rows']) if row['Case'] == self.key('embedded', 'All mandatory actions'))
        original = st.dataframe
        def selection(*args, **kwargs):
            result = original(*args, **kwargs)
            if str(kwargs.get('key', '')).startswith('batch_grid_'):
                return types.SimpleNamespace(selection=types.SimpleNamespace(rows=[index]))
            return result
        with patch.object(st, 'dataframe', side_effect=selection):
            self.app.run()
        self.assertFalse(self.app.exception)
        self.assertEqual(self.app.selectbox(key='batch_inspect').value, self.batch['rows'][index]['Case'])
        self.assertTrue(any('All mandatory actions' in c.value for c in self.app.caption))

    def test_withheld_percentages_are_unavailable_and_diagnostics_collapsed(self):
        table = self.table()
        withheld = table[table['Withheld'] == 'Yes']
        self.assertEqual(len(withheld), 31)
        self.assertEqual(set(withheld['Alignment %']), {'Unavailable'})
        self.assertFalse(self.app.checkbox(key='batch_full_json').value)
        full_panel = next(e for e in self.app.expander if 'Full source-selection' in e.label)
        self.assertFalse(full_panel.proto.expanded)

    def test_r1_receipts_and_two_expectation_generations_without_recomputation(self):
        builders, comparisons = self.builder.call_count, self.comparison.call_count
        self.app.selectbox(key='batch_inspect').select(self.key('embedded', 'API consumption')).run()
        self.assertFalse(self.app.exception)
        self.assertTrue(any('Current Stage 2G expectations: 0 mismatches' in c.value for c in self.app.caption))
        self.assertTrue(any('Historical Stage 2E reference: 14 differences' in c.value for c in self.app.caption))
        self.assertFalse(self.app.error)
        panel = next(p for p in self.app.expander if p.label == 'R1 exact original source receipts')
        self.assertFalse(panel.proto.expanded)
        receipts = [json.loads(j.value) for j in self.app.json if 'complete_supplied_index_verified' in j.value]
        self.assertTrue(receipts)
        self.assertTrue(receipts[0]['eligible'])
        self.assertTrue(all(r['source_verified'] for r in receipts[0]['records']))
        self.assertEqual(self.builder.call_count, builders)
        self.assertEqual(self.comparison.call_count, comparisons)

    def test_exception_and_reference_mismatch_are_visible_separately(self):
        native = {(r['parent_occurrence_id'], r['scenario']): r for r in self.batch['details'].values()}
        def fail_one(parent, scenario):
            if parent['job_id'] == 359 and scenario == 'Maintenance only':
                raise RuntimeError('Synthetic exception control')
            return deepcopy(native[(parent['parent_occurrence_id'], scenario)])
        with patch.object(dashboard.acceptance, 'comparison', side_effect=fail_one):
            failed = dashboard.run_batch(self.batch['revision'])
        self.assertEqual(len(failed['rows']), 60)
        self.assertEqual(len(failed['errors']), 1)
        self.assertEqual(dashboard.totals(failed)['REVIEW_REQUIRED'], 25)
        failed['rows'][0]['Stage 2E reference'] = 'MISMATCH'
        app = app_test().run()
        with patch.object(dashboard, 'run_batch', return_value=failed):
            app.button(key='run_acceptance_batch').click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any('expectations have not been updated' in e.value for e in app.error))
        self.assertTrue(any('Scenario exceptions' in e.value for e in app.error))
        error_key = failed['errors'][0]['Case']
        app.selectbox(key='batch_inspect').select(error_key).run()
        self.assertTrue(any('Synthetic exception control' in e.value for e in app.error))

    def test_revision_change_invalidates_retained_batch_without_running_it(self):
        app = app_test().run()
        stale = dict(self.batch, revision='old-source-identity')
        app.session_state['acceptance_batch'] = stale
        comparisons = self.comparison.call_count
        app.run()
        self.assertNotIn('acceptance_batch', app.session_state)
        self.assertTrue(any('Run the batch again' in w.value for w in app.warning))
        self.assertEqual(self.comparison.call_count, comparisons)
        key = dashboard.revision_key()
        with patch.object(dashboard, 'IDENTITIES', {**dashboard.IDENTITIES, 'revision_probe': 'changed'}):
            self.assertNotEqual(dashboard.revision_key(), key)


class BatchDashboardUnitTests(unittest.TestCase):
    def test_review_details_explain_unentered_stages_without_an_empty_grid(self):
        revision = dashboard.revision_key()
        dashboard.prepare_revision(revision)
        parent = next(p for p in dashboard.acceptance.parents() if p['job_id'] == 359)
        result = dashboard.acceptance.comparison(parent, 'Maintenance only')
        summary, checks = dashboard.summarize(result, 'embedded')
        key = summary['Case']
        app = app_test().run()
        app.session_state['acceptance_batch'] = {'revision': revision, 'rows': [summary],
            'details': {key: result}, 'expectations': {key: checks}, 'errors': []}
        app.run()
        self.assertFalse(app.exception)
        self.assertTrue(any('No admissible source' in i.value for i in app.info))
        self.assertTrue(all(not frame.value.empty for frame in app.dataframe))
        self.assertTrue(any('**REVIEW_REQUIRED 1**' in text.value for text in app.markdown))

    def test_revision_hash_tracks_source_and_synthetic_fixture_bytes(self):
        baseline = dashboard.revision_key()
        original = Path.read_bytes
        for target in (dashboard.ROOT/'scripts/coordinated_acceptance.py',
                       dashboard.ROOT/'tests/fixtures/per_jd_scoring_audit.json',
                       dashboard.ROOT/'analysis_stability/coordinated_r1.py',
                       dashboard.R1_EXPECTATIONS):
            def changed(path):
                data = original(path)
                return data+b'cache revision probe' if path == target else data
            with patch.object(Path, 'read_bytes', new=changed):
                self.assertNotEqual(dashboard.revision_key(), baseline)
        self.assertEqual(dashboard.revision_key(), baseline)

    def test_progress_and_all_exception_outcomes_have_no_numeric_score(self):
        progress = []
        with patch.object(dashboard.acceptance, 'comparison', side_effect=RuntimeError('Injected control')):
            batch = dashboard.run_batch(dashboard.revision_key(),
                                        lambda done, total, name: progress.append((done, total)))
        self.assertEqual(progress, [(i, 60) for i in range(1, 61)])
        self.assertEqual(len({r['Case'] for r in batch['rows']}), 60)
        self.assertEqual(dashboard.totals(batch)['exceptions'], 60)
        self.assertEqual(dashboard.totals(batch)['REVIEW_REQUIRED'], 0)
        self.assertTrue(all(r['Alignment %'] is None for r in batch['rows']))
        self.assertTrue(all(r['Withheld'] == 'Unknown (exception)' for r in batch['rows']))


if __name__ == '__main__':
    unittest.main()

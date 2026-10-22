"""Phase 1 independent boundary contracts and actual-adapter Streamlit tests."""
from contextlib import ExitStack, contextmanager
import importlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from analysis_stability import stable_evidence_scoring as native
from analysis_stability.coordinated_runtime import assert_analysis_publishable
from job_discovery import developer_comparison as a, coordinated_preview as controller
from job_discovery import matching
from database import analysis_cache_manager as cache, job_match_manager as matches
from tests.test_coordinated_job_match_preview_ui import app_test


class AdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch.dict(os.environ, {a.GATE: '1'}):
            cls.result = a.evaluate('E04', session_enabled=True)

    def test_execution_gate_is_not_just_visibility(self):
        for env, session in [('', True), ('true', True), ('1', False)]:
            with self.subTest(env=env, session=session), patch.dict(os.environ, {a.GATE: env}), patch.object(controller, 'run_comparison') as build:
                with self.assertRaises(ValueError): a.evaluate('E04', session_enabled=session)
                build.assert_not_called()

    def test_unknown_example_fails_closed(self):
        with patch.dict(os.environ, {a.GATE: '1'}), self.assertRaises(ValueError):
            a.evaluate('LIVE_APPLICATION', session_enabled=True)

    def test_published_identity_and_isolation(self):
        c = self.result['comparison']
        self.assertEqual(c.published.scoring_version, native.SCORING_VERSION)
        self.assertEqual(native.SCORING_VERSION, 'stable-evidence-v1.17-phase6d21')
        self.assertFalse(c.published.ranking_eligible)
        self.assertEqual(c.gated.scoring_version, 'stable-evidence-v1.21-phase6d25')
        with self.assertRaises(ValueError): assert_analysis_publishable(c.gated_analysis)

    def test_conflict_expectation_is_independent(self):
        rows = [r for r in self.result['comparison'].gated.requirements if r.conflict and r.conflict.get('quarantine')]
        self.assertTrue(rows)
        for r in rows:
            self.assertEqual(r.label.value, 'REVIEW_REQUIRED')
            self.assertIsNone(r.contribution)
            self.assertTrue(r.evidence)
            self.assertTrue(r.conflict['findings'])

    def test_withheld_is_null(self):
        c = self.result['comparison']
        self.assertFalse(c.gated.score_available)
        self.assertIsNone(c.gated.alignment)
        self.assertTrue(c.published.score_available)

    def test_exact_ids_no_text_geometry_join(self):
        c = self.result['comparison']
        rows = a.requirement_rows(c)
        self.assertEqual(len(rows), len({r.requirement_id for v in (c.published, c.gated) for r in v.requirements}))
        self.assertEqual(len(rows), len({r['Requirement ID'] for r in rows}))
        self.assertTrue(any('Different requirement geometry' in r['Difference'] for r in rows))

    def test_zero_is_not_unavailable(self):
        c = self.result['comparison']
        rows = a.requirement_rows(c)
        self.assertTrue(any(r['Published credit'] == 0 for r in rows))
        self.assertTrue(any(r['Experimental'] == 'REVIEW_REQUIRED' and r['Experimental credit'] is None for r in rows))

    def test_fixture_and_source_change_invalidate(self):
        with self.assertRaises(ValueError): a.require_current(self.result, 'E01')
        with patch.object(a, 'selection_identity', return_value='new-code'), self.assertRaises(ValueError):
            a.require_current(self.result, 'E04')

    def test_metadata_is_authentic_classification_not_scores(self):
        from analysis_stability import jd_metadata_policy as v22, jd_metadata_v123 as v23
        raw = controller.prepare_comparison(**a.fixtures.preview_inputs('E04')).raw_jd_text
        for module in (v22, v23):
            self.assertEqual(self.result['metadata'][module.SCORER_VERSION], module.classify(raw))

    def test_default_export_allowlist(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'SECRET_SENTINEL'}):
            result = dict(self.result, unrelated_application={'resume': 'PRIVATE_SENTINEL'}, path='C:/private')
            text = a.diagnostic_export(result, 'E04')
        data = json.loads(text)
        self.assertNotIn('SECRET_SENTINEL', text)
        self.assertNotIn('PRIVATE_SENTINEL', text)
        self.assertNotIn('C:/private', text)
        self.assertNotIn('raw_text', text)
        self.assertNotIn('raw_resume_text', text)
        self.assertIsNone(data['experimental']['alignment'])
        self.assertFalse(data['persistence_eligible'])
        self.assertEqual(data['input_fingerprint'], self.result['comparison'].identity)
        self.assertTrue(data['experimental_evidence'])

    def test_explicit_text_export_and_stale_rejection(self):
        data = json.loads(a.diagnostic_export(self.result, 'E04', include_synthetic_text=True))
        self.assertTrue(data['source_text_included'])
        self.assertTrue(any('raw_text' in r for r in next(iter(data['metadata_classifications'].values()))))
        with self.assertRaises(ValueError): a.diagnostic_export(self.result, 'E01')

    def test_fixed_synthetic_evaluation_is_deterministic(self):
        with patch.dict(os.environ, {a.GATE: '1'}):
            again = a.evaluate('E04', session_enabled=True)
        self.assertEqual(a.diagnostic_export(again, 'E04'), a.diagnostic_export(self.result, 'E04'))

    def test_no_loader_writer_network_route(self):
        # Execution above ran under the offline guard; separately enforce no
        # application loads/writes for this same real boundary evaluation.
        targets = [patch.object(matches, '_connect', side_effect=AssertionError('DB forbidden')),
                   patch.object(cache, '_connect', side_effect=AssertionError('DB forbidden')),
                   patch.object(matching, 'current_evidence_context', side_effect=AssertionError('Live evidence forbidden')),
                   patch.object(matching, 'analyze_job_match', side_effect=AssertionError('Saved matching forbidden'))]
        mocks = [p.start() for p in targets]
        try:
            with patch.dict(os.environ, {a.GATE: '1'}): result = a.evaluate('E02', session_enabled=True)
            selected = next(r for r in result['comparison'].gated.requirements if r.receipt.get('obligation', {}).get('object_family') == 'embedded')
            self.assertEqual(selected.label.value, 'WEAK')
            for mock in mocks: mock.assert_not_called()
        finally:
            for p in reversed(targets): p.stop()


def page_test(main=False):
    app = app_test()  # uses the repository's Windows temporary-dir compatibility
    from streamlit.testing.v1 import AppTest
    return AppTest.from_file(str(controller.ROOT/('app.py' if main else 'tests/developer_comparison_harness.py')), default_timeout=240)


@contextmanager
def disposable_main_application():
    """Redirect existing startup storage; never relax the offline guard."""
    with ExitStack() as stack:
        folder = Path(tempfile.mkdtemp(prefix='developer-main-app-'))
        names = ('db_manager', 'job_discovery_manager', 'job_match_manager', 'chat_history_manager',
                 'application_profile_manager', 'browser_capture_manager', 'application_tracking_manager',
                 'user_profile_manager', 'browser_bridge_settings', 'tailoring_version_manager', 'jd_library_manager')
        for name in names:
            module = importlib.import_module('database.'+name)
            stack.enter_context(patch.object(module, 'DB_PATH', folder/'applications.db'))
        from browser_integration.streamlit_runtime import StreamlitBrowserBridgeResource
        stack.enter_context(patch('browser_integration.streamlit_runtime.ensure_streamlit_browser_bridge',
                                 return_value=StreamlitBrowserBridgeResource(None, 'Offline UI test')))
        yield


class UITests(unittest.TestCase):
    def test_disabled_page_no_evaluation(self):
        with patch.dict(os.environ, {a.GATE: ''}), patch.object(a, 'evaluate') as run:
            app = page_test().run()
            self.assertFalse(app.exception)
            self.assertFalse(app.button)
            run.assert_not_called()

    def test_actual_page_evaluation_rerun_filters_export_and_switch(self):
        with patch.dict(os.environ, {a.GATE: '1'}), patch.object(a, 'evaluate', wraps=a.evaluate) as run:
            app = page_test()
            app.session_state['current_application_id'] = 123
            app.session_state['latest_report'] = {'sentinel': 'original'}
            app.run()
            app.selectbox(key='developer_job_match_ui_v1_case').set_value('E04').run()
            app.toggle[0].set_value(True).run()
            run.assert_not_called()
            app.button(key='developer_job_match_ui_v1_run').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(run.call_count, 1)
            result = app.session_state[a.STATE]
            self.assertEqual(len(app.metric), 1)
            self.assertTrue(any('unavailable' in x.value for x in app.warning))
            app.selectbox(key='developer_job_match_ui_v1_filter').set_value('REVIEW_REQUIRED').run()
            table = app.dataframe[0].value
            self.assertTrue(all(table['Experimental credit'].isna()))
            rid = table['Requirement ID'].iloc[0]
            app.selectbox(key='developer_job_match_ui_v1_requirement').set_value(rid).run()
            self.assertTrue(any('Source' in str(d.value) or 'source' in str(d.value) for d in app.dataframe))
            app.checkbox(key='developer_job_match_ui_v1_export_text').set_value(True).run()
            self.assertEqual(run.call_count, 1)
            self.assertEqual(app.session_state['current_application_id'], 123)
            self.assertEqual(app.session_state['latest_report'], {'sentinel': 'original'})
            import streamlit as st
            with patch.object(a, 'diagnostic_export', wraps=a.diagnostic_export) as export, \
                    patch.object(st, 'download_button', wraps=st.download_button) as download:
                app.run()
                self.assertEqual(export.call_args.args[0]['identity'], result['identity'])
                self.assertEqual(export.call_args.args[1], 'E04')
                payload = json.loads(download.call_args.args[1])
                self.assertEqual(payload['input_fingerprint'], result['comparison'].identity)
                self.assertEqual(payload['published'], result['comparison'].published.summary())
                self.assertEqual(payload['experimental'], result['comparison'].gated.summary())
                self.assertTrue(payload['source_text_included'])
            app.selectbox(key='developer_job_match_ui_v1_case').set_value('E01').run()
            self.assertNotIn(a.STATE, app.session_state)
            self.assertFalse(app.metric)
            self.assertEqual(run.call_count, 1)

    def test_controlled_failure_and_retry(self):
        with patch.dict(os.environ, {a.GATE: '1'}):
            app = page_test().run()
            app.toggle[0].set_value(True).run()
            with patch.object(a, 'evaluate', side_effect=ValueError('SECRET_INTERNAL_PATH')):
                app.button(key='developer_job_match_ui_v1_run').click().run()
            self.assertFalse(app.exception)
            self.assertIn('EVALUATION_FAILED', app.error[0].value)
            self.assertNotIn('SECRET_INTERNAL_PATH', app.error[0].value)
            self.assertNotIn(a.STATE, app.session_state)

    def test_main_app_default_navigation_and_opt_in(self):
        with disposable_main_application():
            self.check_main_navigation()

    def check_main_navigation(self):
        with patch.dict(os.environ, {a.GATE: ''}), patch.object(a, 'evaluate') as run:
            app = page_test(main=True).run()
            self.assertFalse(app.exception, [e.message for e in app.exception])
            options = list(app.radio(key='navigation_page').options)
            self.assertNotIn(a.PAGE, options)
            self.assertIn('Job Finder', options)
            run.assert_not_called()
        with patch.dict(os.environ, {a.GATE: '1'}), patch.object(a, 'evaluate', wraps=a.evaluate) as run:
            app.radio(key='navigation_page')  # preserve public navigation key
            app.run()
            self.assertEqual(app.radio(key='navigation_page').options[:-1], options)
            app.radio(key='navigation_page').set_value(a.PAGE).run()
            self.assertFalse(app.exception, [e.message for e in app.exception])
            self.assertTrue(app.toggle(key='developer_job_match_ui_v1_enabled'))
            run.assert_not_called()
            app.toggle(key='developer_job_match_ui_v1_enabled').set_value(True).run()
            run.assert_not_called()
            app.button(key='developer_job_match_ui_v1_run').click().run()
            self.assertFalse(app.exception, [e.message for e in app.exception])
            self.assertFalse(app.error)
            result = app.session_state[a.STATE]
            embedded = next(r for r in result['comparison'].gated.requirements
                            if r.receipt.get('obligation', {}).get('object_family') == 'embedded')
            self.assertEqual(embedded.label.value, 'DIRECT')
            self.assertEqual(run.call_count, 1)
            app.run()
            self.assertEqual(run.call_count, 1)
        with patch.dict(os.environ, {a.GATE: ''}):
            app.run()
            self.assertFalse(app.exception)
            self.assertEqual(app.radio(key='navigation_page').value, 'Tailor Resume')

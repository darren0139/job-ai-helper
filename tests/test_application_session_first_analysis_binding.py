"""Explicit first-analysis lifecycle using isolated SQLite and saved native results."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import ast
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from database import db_manager
from database import analysis_cache_manager as cache
from tailoring import initial_analysis_explainer as explainer
from tests.test_initial_analysis_explainer import analysis


class FirstAnalysisBindingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / 'applications.db'
        patcher = patch.object(db_manager, 'DB_PATH', self.path)
        patcher.start()
        self.addCleanup(patcher.stop)
        db_manager.init_db()
        cache.init_analysis_cache()
        self.app_id = db_manager.create_empty_application_session()
        self.jd = 'Required direct\nCore transferable\nPreferred weak'
        self.report = {'raw_jd_text': self.jd, 'raw_resume_text': 'Frozen resume',
                       'jd_profile': {'job_title': 'Engineer', 'company': 'Example'},
                       'stable_analysis': analysis(), 'overall_score': 73, 'meta': {}}
        for name in ('litellm.completion', 'litellm.embedding', 'socket.create_connection'):
            guard = patch(name, side_effect=AssertionError('No paid/network calls'))
            mock = guard.start()
            self.addCleanup(guard.stop)
            if name == 'litellm.completion':
                self.model = mock

    def persist(self, **changes):
        args = dict(application_id=self.app_id, input_fingerprint='exact-input',
                    report=deepcopy(self.report), raw_jd_text=self.jd,
                    resume_filename='resume.docx', analysis_model='fake-model')
        args.update(changes)
        return cache.persist_explicit_application_analysis(**args)

    def binding(self):
        with closing(db_manager._connect()) as conn:
            row = conn.execute('SELECT initial_analysis_id,initial_analysis_binding_json FROM applications WHERE id=?', (self.app_id,)).fetchone()
        return row[0], json.loads(row[1] or '{}')

    def seed(self, app_id=None, **changes):
        args = dict(application_id=app_id or self.app_id, input_fingerprint='exact-input',
                    report=deepcopy(self.report), analysis_model='fake-model', resume_filename='resume.docx')
        args.update(changes)
        return cache.save_analysis_snapshot(**args)

    def test_blank_and_legacy_passive_reads_never_guess_initial(self):
        self.assertEqual(self.binding(), (None, {}))
        for legacy in (False, True):
            if legacy:
                self.seed()
            before = self.path.read_bytes()
            with self.assertRaisesRegex(ValueError, 'No authoritative'):
                explainer.load_application_initial(self.app_id)
            self.assertEqual(self.path.read_bytes(), before)
            self.assertEqual(self.binding(), (None, {}))

    def test_fresh_persistence_freezes_native_receipt_and_identity(self):
        saved = self.persist()
        initial_id, reference = self.binding()
        self.assertEqual(initial_id, saved['analysis_id'])
        self.assertEqual(reference['origin'], 'FRESH_ANALYSIS')
        self.assertEqual(reference['input_fingerprint'], 'exact-input')
        self.assertTrue(reference['canonical_requirement_fingerprint'])
        self.assertTrue(reference['identity']['taxonomy_fingerprint'])
        self.assertTrue(reference['identity']['registry_fingerprint'])
        view = explainer.load_application_initial(self.app_id)
        self.assertEqual(view['stable_analysis'], self.report['stable_analysis'])
        self.assertEqual(view['score'], 73)
        self.assertEqual(view['raw_jd_text'], self.jd)
        self.assertEqual(view['identity']['saved_snapshot_id'], saved['id'])

    def test_owned_cache_hit_and_legacy_explicit_bind_exact_receipt_without_model(self):
        saved = self.seed()
        before = saved['report']
        result = self.persist(reused_snapshot=saved)
        self.assertEqual(result['analysis_id'], saved['analysis_id'])
        self.assertEqual(result['id'], saved['id'])
        self.assertEqual(result['report'], before)
        self.assertEqual(len(cache.list_analysis_snapshots(self.app_id)), 1)
        self.assertEqual(self.binding()[1]['origin'], 'EXACT_SAVED_REUSE')
        self.model.assert_not_called()

    def test_historical_collapsed_jd_cache_keeps_exact_id_and_bound_input_text(self):
        historical = deepcopy(self.report)
        historical['raw_jd_text'] = ' '.join(self.jd.split())
        saved = self.seed(report=historical)
        result = self.persist(reused_snapshot=saved)
        self.assertEqual(result['analysis_id'], saved['analysis_id'])
        self.assertEqual(result['report'], historical)
        self.assertEqual(explainer.load_application_initial(self.app_id)['raw_jd_text'], self.jd)

    def test_native_requirement_fixture_cache_with_local_preference_preserves_scope(self):
        from tailoring.jd_user_input_overrides import apply_application_session_jd_user_inputs
        bundle = json.loads((Path(__file__).parent / 'fixtures' / 'per_jd_scoring_audit.json').read_text(encoding='utf-8'))
        job = next(j for j in bundle['snapshot']['audit']['corpus']['jobs'] if j['job_id'] == 493)
        inputs = job['frozen_inputs']
        native = {'stable_analysis': job['baseline_stable_analysis'], **inputs, 'meta': {},
                  'jd_profile': {'required_skills': [r['text'] for r in job['baseline_stable_analysis']['canonical_requirements']]},
                  'resume_profile': {'skills': {}, 'experience': [], 'projects': [], 'education': []}}
        for overrides in ([], ['Experience with Kubernetes']):
            with self.subTest(overrides=overrides):
                app_id = db_manager.create_empty_application_session()
                def prepare(report):
                    result = apply_application_session_jd_user_inputs(report,
                        raw_jd_text=inputs['raw_jd_text'], raw_resume_text='',
                        preferred_requirements=overrides)
                    result['raw_jd_text'] = inputs['raw_jd_text']
                    return result
                report = prepare(native)
                saved = self.seed(app_id, report=report)
                prepared = prepare(saved['report'])
                attached = self.persist(application_id=app_id, report=prepared,
                    raw_jd_text=inputs['raw_jd_text'], reused_snapshot=saved)
                self.assertEqual(attached['analysis_id'], saved['analysis_id'])
                self.assertEqual(attached['report']['stable_analysis'], saved['report']['stable_analysis'])

    def test_explicit_cross_application_reuse_attaches_owned_receipt(self):
        source_id = db_manager.create_empty_application_session()
        source = self.seed(source_id)
        attached = self.persist(reused_snapshot=source)
        self.assertNotEqual(attached['analysis_id'], source['analysis_id'])
        self.assertEqual(attached['application_id'], self.app_id)
        self.assertEqual(attached['report']['stable_analysis'], source['report']['stable_analysis'])
        self.assertEqual(self.binding()[1]['source_snapshot_id'], source['id'])
        self.assertEqual(explainer.load_application_initial(self.app_id)['provenance'], 'EXACT_SAVED_REUSE')
        self.model.assert_not_called()

    def test_repeat_cache_and_fresh_current_resume_refresh_preserve_initial(self):
        first = self.persist()
        before = explainer.load_application_initial(self.app_id)
        self.persist(reused_snapshot=first)
        changed = deepcopy(self.report)
        changed['raw_resume_text'] = 'Updated resume'
        changed['stable_analysis']['deterministic_alignment_score'] = 99
        changed['overall_score'] = 99
        second = self.persist(report=changed, input_fingerprint='new-resume-currentness')
        self.assertNotEqual(second['analysis_id'], first['analysis_id'])
        self.assertEqual(explainer.load_application_initial(self.app_id), before)
        self.assertEqual(db_manager.get_application_by_id(self.app_id)['report']['overall_score'], 99)
        same = explainer.compare_analysis_receipts(before, before)
        self.assertTrue(same['comparable'])

    def test_scorer_refresh_and_different_jd_do_not_replace_historical_initial(self):
        first = self.persist()
        before = explainer.load_application_initial(self.app_id)
        from tailoring.job_match_ab_analysis import current_ab_identity
        versions = current_ab_identity('New job')
        versions['scoring_version'] = 'future-scorer'
        future = deepcopy(self.report)
        future['raw_jd_text'] = 'New job'
        future['stable_analysis']['scoring_version'] = 'future-scorer'
        with patch('tailoring.job_match_ab_analysis.current_ab_identity', return_value=versions):
            self.persist(report=future, raw_jd_text='New job', input_fingerprint='future-input')
        self.assertEqual(self.binding()[0], first['analysis_id'])
        self.assertEqual(explainer.load_application_initial(self.app_id), before)

    def test_double_click_and_competing_fresh_operations_first_commit_wins(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.persist(), range(2)))
        self.assertIn(self.binding()[0], {r['analysis_id'] for r in results})
        before = self.binding()
        for result in results:
            self.persist(reused_snapshot=cache.find_cached_analysis(application_id=self.app_id, input_fingerprint='exact-input'))
            self.assertEqual(self.binding(), before)

    def test_persistence_failure_rolls_back_receipt_pointer_and_current_report(self):
        original = db_manager.update_application_report
        def fail(**kwargs):
            original(**kwargs)
            raise RuntimeError('Injected failure after pointer and report update')
        with patch.object(db_manager, 'update_application_report', side_effect=fail):
            with self.assertRaisesRegex(RuntimeError, 'Injected'):
                self.persist()
        self.assertEqual(self.binding(), (None, {}))
        self.assertEqual(cache.list_analysis_snapshots(self.app_id), [])
        self.assertIsNone(db_manager.get_application_by_id(self.app_id)['report'])

    def test_wrong_jd_and_existing_application_jd_fail_closed(self):
        with self.assertRaisesRegex(ValueError, 'JD identity'):
            self.persist(raw_jd_text='Other JD')
        old = deepcopy(self.report)
        old['raw_jd_text'] = 'Existing bound job'
        db_manager.update_application_report(application_id=self.app_id, resume_filename='', report=old)
        with self.assertRaisesRegex(ValueError, 'Application JD differs'):
            self.persist()
        self.assertEqual(self.binding(), (None, {}))

    def test_incompatible_cache_input_scope_ownership_and_staleness_fail_closed(self):
        saved = self.seed()
        changed = deepcopy(self.report)
        changed['stable_analysis']['canonical_requirements'][0]['text'] = 'Different scope'
        for kwargs in ({'input_fingerprint': 'wrong'}, {'report': changed},
                       {'reused_snapshot': {**saved, 'application_id': 999}},
                       {'reused_snapshot': {**saved, 'pipeline_contract_version': 'stale'}}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.persist(**{'reused_snapshot': saved, **kwargs})
        stale = deepcopy(self.report)
        stale['stable_analysis']['scoring_version'] = 'old'
        with self.assertRaisesRegex(ValueError, 'stale'):
            self.persist(report=stale)
        self.assertEqual(self.binding(), (None, {}))

    def test_frozen_cache_row_cannot_be_overwritten_and_corrupt_binding_fails_closed(self):
        first = self.persist()
        with self.assertRaisesRegex(ValueError, 'cannot be overwritten'):
            self.seed(analysis_id=first['analysis_id'])
        with closing(db_manager._connect()) as conn, conn:
            conn.execute("UPDATE applications SET initial_analysis_binding_json='{}' WHERE id=?", (self.app_id,))
        with self.assertRaises(ValueError):
            explainer.load_application_initial(self.app_id)

    def test_delete_removes_binding_with_application(self):
        self.persist()
        db_manager.delete_application_session(self.app_id)
        with self.assertRaisesRegex(ValueError, 'Application unavailable'):
            explainer.load_application_initial(self.app_id)

    def test_ui_blank_origins_and_exact_bound_jd_are_passive(self):
        from streamlit.testing.v1 import AppTest
        code = '''
import streamlit as st
from tailoring.initial_analysis_explainer_ui import render_application_bound_jd, render_application_initial_analysis
render_application_bound_jd(st, st.session_state['application_id'])
render_application_initial_analysis(st, st.session_state['application_id'])
'''
        app = AppTest.from_string(code, default_timeout=30)
        app.session_state['application_id'] = self.app_id
        before = self.path.read_bytes()
        app.run()
        self.assertFalse(app.exception)
        self.assertIn('Not established yet', [m.value for m in app.markdown])
        self.assertEqual(self.path.read_bytes(), before)
        saved = self.persist()
        before = self.path.read_bytes()
        with patch('tailoring.initial_analysis_explainer_ui.render_jd_taxonomy_status', return_value=None):
            app.run()
        self.assertFalse(app.exception)
        self.assertIn(self.jd, [t.value for t in app.text])
        self.assertIn('Analysis origin: Fresh analysis', [c.value for c in app.caption])
        self.assertEqual(self.path.read_bytes(), before)
        self.model.assert_not_called()
        # Both origins use the common receipt renderer, including diagnostics.
        view = explainer.load_application_initial(self.app_id)
        from tailoring.initial_analysis_explainer_ui import render_application_initial_analysis
        st = Mock()
        st.expander.return_value.__enter__ = Mock()
        st.expander.return_value.__exit__ = Mock(return_value=False)
        view['provenance'] = 'EXACT_SAVED_REUSE'
        with patch('tailoring.initial_analysis_explainer_ui.load_application_initial', return_value=view), patch('tailoring.initial_analysis_explainer_ui.render_analysis_receipt') as renderer:
            render_application_initial_analysis(st, self.app_id)
        renderer.assert_called_once_with(st, view)
        st.caption.assert_any_call('Analysis origin: Reused exact saved analysis')

    def test_normal_event_binding_is_inside_explicit_analyze_branch_only(self):
        source = (Path(__file__).resolve().parents[1] / 'app.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'persist_explicit_application_analysis']
        self.assertEqual(len(calls), 1)
        explicit = next(n for n in ast.walk(tree) if isinstance(n, ast.If) and isinstance(n.test, ast.Name) and n.test.id == 'analyze_clicked')
        self.assertIn(calls[0], list(ast.walk(explicit)))

    def test_explicit_streamlit_cache_and_fake_fresh_actions_bind_once(self):
        from streamlit.testing.v1 import AppTest
        code = '''
import streamlit as st
from copy import deepcopy
from database.analysis_cache_manager import persist_explicit_application_analysis, find_cached_analysis
from tailoring.initial_analysis_explainer_ui import render_application_initial_analysis, render_application_bound_jd
force = st.checkbox('Force fresh AI analysis')
if st.button('Analyze Resume'):
    cached = None if force else find_cached_analysis(application_id=st.session_state['application_id'], input_fingerprint='exact-input')
    # Fresh provider transport is deliberately fake; the production save/bind
    # and common read-only renderer are used for both explicit origins.
    report = deepcopy(st.session_state['provider_report'])
    if cached is None:
        st.session_state['fake_fresh_calls'] += 1
    persist_explicit_application_analysis(application_id=st.session_state['application_id'],
        input_fingerprint='exact-input', report=report, raw_jd_text=report['raw_jd_text'],
        analysis_model='fake-model', resume_filename='resume.docx', reused_snapshot=cached)
render_application_bound_jd(st, st.session_state['application_id'])
render_application_initial_analysis(st, st.session_state['application_id'])
'''
        for cached in (True, False):
            with self.subTest(cached=cached):
                app_id = db_manager.create_empty_application_session()
                if cached:
                    self.seed(app_id)
                app = AppTest.from_string(code, default_timeout=30)
                app.session_state['application_id'] = app_id
                app.session_state['provider_report'] = deepcopy(self.report)
                app.session_state['fake_fresh_calls'] = 0
                with patch('tailoring.initial_analysis_explainer_ui.render_jd_taxonomy_status', return_value=None):
                    app.run()
                    with self.assertRaisesRegex(ValueError, 'No authoritative'):
                        explainer.load_application_initial(app_id)
                    if not cached:
                        app.checkbox[0].check()
                    app.button[0].click().run()
                    self.assertFalse(app.exception)
                    initial = explainer.load_application_initial(app_id)
                    self.assertEqual(initial['provenance'], 'EXACT_SAVED_REUSE' if cached else 'FRESH_ANALYSIS')
                    self.assertEqual(app.session_state['fake_fresh_calls'], 0 if cached else 1)
                    app.button[0].click().run()
                    self.assertFalse(app.exception)
                    self.assertEqual(explainer.load_application_initial(app_id), initial)
                    self.assertIn(self.jd, [t.value for t in app.text])
                self.model.assert_not_called()


class JobFinderFirstAnalysisInvariantTests(unittest.TestCase):
    from tests.test_shared_application_session_identity import SharedApplicationSessionIdentityTests as _support
    setUp = _support.setUp
    draft = _support.draft

    def test_normal_explicit_analysis_preserves_exact_job_finder_initial(self):
        app_id = self.draft()
        before = explainer.load_application_initial(app_id)
        report = {'raw_jd_text': before['raw_jd_text'],
                  'stable_analysis': deepcopy(before['stable_analysis']),
                  'jd_profile': deepcopy(self.original_jd['jd_profile']),
                  'overall_score': before['score'], 'meta': {}}
        with patch('litellm.completion', side_effect=AssertionError('No model')) as model:
            current = cache.persist_explicit_application_analysis(application_id=app_id,
                input_fingerprint='normal-explicit-analysis', report=report,
                raw_jd_text=before['raw_jd_text'], analysis_model='fake-model', resume_filename='new-resume.docx')
        self.assertNotEqual(current['analysis_id'], before['identity']['initial_analysis_id'])
        self.assertEqual(explainer.load_application_initial(app_id), before)
        self.assertEqual(before['identity']['saved_snapshot_id'], self.snapshot['id'])
        self.assertEqual(before['score'], self.snapshot['stable_analysis']['deterministic_alignment_score'])
        model.assert_not_called()


if __name__ == '__main__':
    unittest.main()

"""Working controls never change a saved generation; historical preview is read-only."""
import ast
from copy import deepcopy
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from tailoring import phase9f_working_settings_v312b214 as settings
from database import phase9f_bestof_review_state as review

ROOT = Path(__file__).resolve().parents[1]

class WidgetUI:
    def __init__(self):
        self.session_state = {}
        self.identities = {}
    def radio(self, title, options, *, key, index=0, **kw):
        return self._widget(key, options[index], tuple(options))
    def checkbox(self, title, *, key, value=False, **kw):
        return self._widget(key, value, ())
    def multiselect(self, title, options, *, key, default=None, **kw):
        return self._widget(key, list(default or []), tuple(options))
    def _widget(self, key, default, options):
        # Model the Streamlit identity reset when defining parameters change.
        identity = (deepcopy(default), options)
        if self.identities.get(key) != identity or key not in self.session_state:
            self.session_state[key] = deepcopy(default)
        self.identities[key] = identity
        return self.session_state[key]


def generation():
    return {'application_id': 156, 'generation_id': 'old', 'generation_settings': {
        'max_projects': 4, 'phase9f_f_normal_lifecycle': {
            'model': 'saved-model', 'settings': {'max_projects': 5, 'max_bullets': 3},
            'fit': {'status': 'completed', 'settings': {'adaptive_projects_mode': 'portfolio_quality',
                'page_density_mode': 'maximize', 'allow_bullet_fusion': True}}}},
        'fit_result': {'fitting_input_snapshot': {'fitter_invocation': {'max_projects': 5, 'max_bullets_per_project': 10}}}}

class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'prefs.sqlite'
        def connect():
            db = sqlite3.connect(self.path); db.row_factory = sqlite3.Row; return db
        self.connect = connect
        patcher = patch.object(review, '_connect', connect); patcher.start(); self.addCleanup(patcher.stop)
        self.ui = WidgetUI()
    def radio(self, index=0, app=156):
        return settings.settings_widget(self.ui, app, 'radio', 'Project policy',
            ['Balanced (up to 5)', 'Portfolio Quality Optimization (preview)'],
            key=f'adaptive_project_fit_mode_{app}', index=index)
    def test_recorded_nested_settings_and_effective_ceiling_are_separate(self):
        g = generation(); before = deepcopy(g)
        r = settings.saved_settings(g)
        self.assertEqual(r['generation']['max_projects'], 5)
        self.assertEqual(r['generation']['max_bullets'], 3)
        self.assertEqual(r['effective_fitting']['max_bullets_per_project'], 10)
        self.assertEqual(r['fitting']['adaptive_projects_mode'], 'portfolio_quality')
        self.assertEqual(g, before)
    def test_missing_and_unfitted_settings_are_not_invented(self):
        self.assertEqual(settings.saved_settings({})['fitting'], {})
        g = generation(); g['generation_settings']['phase9f_f_normal_lifecycle']['fit'] = {'status': 'not_started'}
        self.assertEqual(settings.saved_settings(g)['fitting'], {})
    def test_restore_defaults_do_not_reset_user_selected_mode(self):
        self.assertEqual(self.radio(), 'Balanced (up to 5)')
        self.ui.session_state['adaptive_project_fit_mode_156'] = 'Portfolio Quality Optimization (preview)'
        self.assertEqual(self.radio(index=1), 'Portfolio Quality Optimization (preview)')
        self.assertEqual(self.radio(index=0), 'Portfolio Quality Optimization (preview)')
        self.ui.session_state.pop('adaptive_project_fit_mode_156')
        self.assertEqual(self.radio(), 'Portfolio Quality Optimization (preview)')
    def test_explicit_restore_and_restart_are_application_local(self):
        self.radio(); g = generation(); before = deepcopy(g)
        self.assertTrue(settings.queue_saved_settings(self.ui, 156, g))
        self.assertEqual(self.radio(), 'Portfolio Quality Optimization (preview)')
        self.assertEqual(self.radio(app=158), 'Balanced (up to 5)')
        settings.persist_working(self.ui, 156)
        self.ui = WidgetUI()
        self.assertEqual(self.radio(), 'Portfolio Quality Optimization (preview)')
        self.assertEqual(g, before)
    def test_checkbox_and_hidden_control_rehydrate(self):
        key = 'allow_bullet_fusion_156'
        def show(value, disabled=False):
            return settings.settings_widget(self.ui, 156, 'checkbox', 'Fusion', key=key, value=value, disabled=disabled)
        self.assertTrue(show(True)); self.ui.session_state[key] = False
        self.assertFalse(show(True)); self.ui.session_state.pop(key)
        self.assertFalse(show(True))
        show(True, disabled=True)
        self.assertFalse(show(True))
    def test_manual_keys_intersect_new_evidence_options_without_selecting_all(self):
        key='adaptive_project_fit_manual_156'
        def show(options):
            return settings.settings_widget(self.ui,156,'multiselect','Manual',options,key=key,default=options)
        self.assertEqual(show(['a','b']), ['a','b']); self.ui.session_state[key]=['b']
        self.assertEqual(show(['a','b']), ['b'])
        self.assertEqual(show(['b','c']), ['b'])
        self.assertEqual(show(['c']), [])
    def test_preview_lookup_does_not_create_tables_or_change_working_values(self):
        self.assertEqual(settings.working_values(self.ui,156), {})
        self.assertEqual(settings.recorded_optimizer(156,generation()), {})
        with closing(self.connect()) as db:
            self.assertEqual(db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall(), [])
    def test_historical_mode_document_hash_app_and_checksum_bound(self):
        from hashlib import sha256
        doc = Path(self.tmp.name)/'a.docx'; doc.write_bytes(b'exact document')
        digest=sha256(doc.read_bytes()).hexdigest(); g=generation(); g['docx_path']=str(doc)
        kw=dict(application_id=156,generation_id='old',context='c1',docx_sha256=digest,
                raw_jd_text='JD',scorer_version='legacy',run_mode='v35-relevance',
                mode_receipt={'generation_id':'old','mode':'v35-relevance'},result={'status':'verified'})
        self.assertTrue(review.save_bestof_display_receipt(**kw))
        self.assertEqual(settings.recorded_optimizer(156,g)['mode'],'v35-relevance')
        self.assertEqual(settings.recorded_optimizer(158,g),{})
        doc.write_bytes(b'changed'); self.assertEqual(settings.recorded_optimizer(156,g),{})
        doc.write_bytes(b'exact document')
        with closing(self.connect()) as db, db:
            db.execute("UPDATE phase9f_bestof_display_receipts SET result_json='{}'")
        self.assertEqual(settings.recorded_optimizer(156,g),{})
    def test_inferred_v26_is_not_historical_provenance(self):
        kw=dict(application_id=156,generation_id='old',context='c1',docx_sha256='a'*64,
                raw_jd_text='JD',scorer_version='legacy',run_mode='v26-fixed',
                mode_receipt={'generation_id':'old','mode':'v26-fixed','legacy_mode_inferred_for_display':True},result={'status':'verified'})
        self.assertTrue(review.save_bestof_display_receipt(**kw))
        self.assertEqual(review.load_historical_optimizer_settings(156,'old','a'*64), {})
    def test_captured_mode_survives_restoration_and_invalid_mode_does_not_arm(self):
        # Execute the actual helper definitions without importing native scorer dependencies.
        source=(ROOT/'tailoring/phase9f_automatic_bestof_v30_ui.py').read_text(encoding='utf-8')
        tree=ast.parse(source); nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('_mode_key','configured_mode','mark_fit_request')]
        ns={'Any':object,'ACTIVE_MODES':('v35-relevance','v37-same-work','v26-fixed')}
        exec(compile(ast.Module(body=nodes,type_ignores=[]),'<actual mode functions>','exec'),ns)
        self.ui.session_state['phase9f_bestof_next_mode_156']='v26-fixed'
        ns['mark_fit_request'](self.ui,156,'new',requested_mode='v37-same-work')
        self.assertEqual(self.ui.session_state['phase9f_auto_bestof_run_mode_156']['mode'],'v37-same-work')
        ns['mark_fit_request'](self.ui,156,'new',requested_mode='invalid')
        self.assertNotIn('phase9f_auto_bestof_pending_156', self.ui.session_state)
    def test_actual_app_click_capture_precedes_three_dispatches(self):
        app=(ROOT/'app.py').read_text(encoding='utf-8')
        self.assertEqual(app.count('requested_mode=_b214_requested_optimizer'),3)
        self.assertLess(app.index('_b214_requested_optimizer = configured_mode'),app.index('normal_fit = run_phase9f_normal_fit('))
        self.assertEqual(app.count('_b214_settings_widget(st, current_application_id,'),22)

try:
    from streamlit.testing.v1 import AppTest
except ImportError:
    AppTest=None

@unittest.skipIf(AppTest is None, 'Streamlit not installed in this test environment')
class ActualStreamlitTests(unittest.TestCase):
    def test_widget_reruns_and_explicit_restore(self):
        # No DB, real Streamlit widget identity/reruns, same helper as production.
        script = '''import streamlit as st
from tailoring.phase9f_working_settings_v312b214 import settings_widget, queue_saved_settings
from unittest.mock import patch
st.session_state.setdefault('v312b214_working_controls_156', {})
flip = st.checkbox('Restore changed defaults')
settings_widget(st,156,'radio','Policy',['Balanced (up to 5)','Portfolio Quality Optimization (preview)'],key='adaptive_project_fit_mode_156',index=int(flip))
if st.button('Load older draft'):
    with patch('tailoring.phase9f_working_settings_v312b214.persist_working'):
        queue_saved_settings(st,156,{'generation_id':'old','generation_settings':{'phase9f_f_normal_lifecycle':{'fit':{'status':'completed','settings':{'adaptive_projects_mode':'balanced'}}}}})
    st.rerun()
'''
        at=AppTest.from_string(script).run()
        self.assertFalse(at.exception)
        at.radio[0].set_value('Portfolio Quality Optimization (preview)').run()
        at.checkbox[0].set_value(True).run()
        self.assertFalse(at.exception)
        self.assertEqual(at.radio[0].value,'Portfolio Quality Optimization (preview)')
        at.button[0].click().run()
        self.assertFalse(at.exception)
        self.assertEqual(at.radio[0].value,'Balanced (up to 5)')

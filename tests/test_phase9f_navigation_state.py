"""Focused editable-navigation contracts; no production data/model calls."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from streamlit.testing.v1 import AppTest
from database import jd_library_manager as manager
from tailoring.phase9f_navigation_state import (
    STATE_KEY, MAX_PREFERENCES, navigation_selectbox,
)
from tests.test_phase9f_streamlit_acceptance import RAW_JD, _profile


class FakeWidgets:
    def __init__(self):
        self.session_state = {}

    def selectbox(self, label, options, *, key, index=0, **kwargs):
        value = self.session_state.get(key, options[index] if index is not None else None)
        self.session_state[key] = value
        return value


class PreferenceContracts(unittest.TestCase):
    def test_identity_restores_fresh_records_not_cached_row_payload(self):
        st = FakeWidgets()
        navigation_selectbox(st, "Saved JD", [{'id': 2, 'text': 'old'}],
                             key='jd', identity=lambda row: row['id'])
        del st.session_state['jd']  # Streamlit removes page-scoped widget state.
        row = {'id': 2, 'text': 'changed current text'}
        self.assertIs(navigation_selectbox(st, "Saved JD", [row], key='jd',
                                          identity=lambda row: row['id']), row)
        self.assertEqual(st.session_state[STATE_KEY]['jd']['value'], 2)
        self.assertNotIn('text', str(st.session_state[STATE_KEY]))

    def test_missing_source_or_saved_jd_never_resurrects_old_record(self):
        st = FakeWidgets()
        navigation_selectbox(st, 'Source', ['A'], key='source', scope='rank1')
        del st.session_state['source']
        self.assertEqual(navigation_selectbox(st, 'Source', ['B'], key='source', scope='rank1'), 'B')
        self.assertNotEqual(st.session_state['source'], 'A')

    def test_changed_artifact_evidence_ranking_scope_rejects_preference(self):
        st = FakeWidgets()
        st.session_state['source'] = 'A'
        navigation_selectbox(st, 'Source', ['B', 'A'], key='source', scope='old-source-fingerprint')
        self.assertEqual(navigation_selectbox(st, 'Source', ['B', 'A'], key='source',
                                             scope='changed-artifact-or-evidence-fingerprint'), 'B')

    def test_deliberate_new_source_survives_widget_cleanup_without_confirming(self):
        st = FakeWidgets()
        frozen = {'selected_base': 'A', 'scores': [31, 31], 'approval': 'draft'}
        st.session_state['frozen_generation'] = deepcopy(frozen)
        navigation_selectbox(st, 'Source', ['A', 'B'], key='source', scope='rank')
        st.session_state['source'] = 'B'
        navigation_selectbox(st, 'Source', ['A', 'B'], key='source', scope='rank')
        del st.session_state['source']
        self.assertEqual(navigation_selectbox(st, 'Source', ['A', 'B'], key='source', scope='rank'), 'B')
        self.assertEqual(st.session_state['frozen_generation'], frozen)

    def test_no_history_does_not_override_target_default_with_none(self):
        st = FakeWidgets()
        self.assertEqual(navigation_selectbox(st, 'Target', [None, 7], key='target', index=1), 7)

    def test_preference_store_is_bounded_and_does_not_copy_analysis(self):
        st = FakeWidgets()
        analysis = {'canonical_requirements': [{'id': 'frozen'}]}
        st.session_state['analysis'] = analysis
        for i in range(MAX_PREFERENCES + 4):
            navigation_selectbox(st, 'Source', ['A'], key=f'source{i}')
        self.assertEqual(len(st.session_state[STATE_KEY]), MAX_PREFERENCES)
        self.assertIs(st.session_state['analysis'], analysis)
        self.assertNotIn('canonical_requirements', str(st.session_state[STATE_KEY]))


HARNESS = '''
import streamlit as st
from database import jd_library_manager as manager
from tailoring import phase9f_orchestrator_ui as ui
manager.DB_PATH = __DB__
page = st.radio('Route', ['Tailor Resume', 'Application Sessions'], key='route')
ui.extract_jd_profile = lambda *_: (_ for _ in ()).throw(AssertionError('No model call allowed'))
if page == 'Tailor Resume':
    ui.render_phase9f_jd_intake()
else:
    st.write('Application Sessions — navigation only')
'''


class NavigationLifecycle(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.old_db = manager.DB_PATH
        self.addCleanup(setattr, manager, 'DB_PATH', self.old_db)
        self.path = Path(self.tmp.name) / 'navigation.sqlite'
        manager.DB_PATH = self.path
        manager.init_jd_library()
        self.saved = manager.save_job_description_to_library(raw_text=RAW_JD, jd_profile=_profile())
        code = 'from pathlib import Path\n' + HARNESS.replace('__DB__', f'Path({str(self.path)!r})')
        self.app = AppTest.from_string(code, default_timeout=30).run()

    def widget(self, kind, key):
        return next(v for v in getattr(self.app, kind) if v.key == key)

    def saved_analysis(self):
        self.widget('selectbox', 'phase9f_jd_source_mode').set_value('Choose saved JD').run()
        self.widget('button', 'phase9f_analyse_jd').click().run()
        self.assertFalse(self.app.exception)

    def roundtrip(self):
        self.widget('radio', 'route').set_value('Application Sessions').run()
        self.assertNotIn('phase9f_jd_source_mode', self.app.session_state)
        self.assertIn(STATE_KEY, self.app.session_state)
        self.widget('radio', 'route').set_value('Tailor Resume').run()

    def test_saved_identity_valid_analysis_survive_real_widget_cleanup(self):
        self.saved_analysis()
        before = deepcopy(self.app.session_state['phase9f_jd_analysis'])
        self.roundtrip()
        self.assertFalse(self.app.exception)
        self.assertEqual(self.widget('selectbox', 'phase9f_jd_source_mode').value, 'Choose saved JD')
        self.assertEqual(self.widget('selectbox', 'phase9f_saved_jd_version').value['source_version_id'], self.saved['source_version_id'])
        self.assertEqual(self.app.session_state['phase9f_jd_analysis'], before)
        self.assertEqual(self.app.session_state['phase9f_jd_intake_state'], 'analysis_current')
        self.assertFalse(any('previous analysis is historical/stale' in str(v.value) for v in self.app.warning))

    def test_deliberate_paste_mode_is_not_overridden_by_last_analysis(self):
        self.saved_analysis()
        self.widget('selectbox', 'phase9f_jd_source_mode').set_value('Paste job description').run()
        self.widget('text_area', 'phase9f_pasted_jd_text').set_value('A deliberately different draft job description.').run()
        self.roundtrip()
        self.assertEqual(self.widget('selectbox', 'phase9f_jd_source_mode').value, 'Paste job description')
        self.assertEqual(self.widget('text_area', 'phase9f_pasted_jd_text').value, 'A deliberately different draft job description.')
        self.assertEqual(self.app.session_state['phase9f_jd_intake_state'], 'stale')

    def test_different_saved_jd_does_not_restore_previous_valid_analysis(self):
        self.saved_analysis()
        profile = {**_profile(), 'job_title': 'Different Java Engineer', 'company': 'Different Synthetic Lab'}
        other = manager.save_job_description_to_library(
            raw_text='Different Java Engineer\nDifferent Synthetic Lab\nMaintain Java transaction systems.',
            jd_profile=profile,
        )
        self.assertNotEqual(other['job_description_id'], self.saved['job_description_id'])
        self.app.run()
        options = manager.get_recent_job_descriptions(limit=200)
        row = next(v for v in options if v[0] == other['job_description_id'])
        self.widget('selectbox', 'phase9f_saved_jd').set_value(row).run()
        self.roundtrip()
        self.assertEqual(self.widget('selectbox', 'phase9f_saved_jd').value[0], other['job_description_id'])
        self.assertEqual(self.app.session_state['phase9f_jd_intake_state'], 'stale')
        self.assertEqual(self.app.session_state['phase9f_jd_analysis']['source_version_id'], self.saved['source_version_id'])

    def test_stale_analysis_fingerprint_remains_stale_after_navigation(self):
        self.saved_analysis()
        self.app.session_state['phase9f_jd_analysis_input_fingerprint'] = 'stale-analysis-fingerprint'
        self.roundtrip()
        self.assertEqual(self.app.session_state['phase9f_jd_intake_state'], 'stale')
        self.assertTrue(any('historical/stale' in str(v.value) for v in self.app.warning))

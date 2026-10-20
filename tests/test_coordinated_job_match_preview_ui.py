"""Actual standalone preview AppTest: nullable UX and retained receipt isolation."""
from pathlib import Path
import tempfile
import types
import unittest
import uuid
from unittest.mock import patch

import streamlit as st
from analysis_stability import stable_evidence_scoring as native
from database import analysis_cache_manager as cache, job_match_manager as matches
from job_discovery import coordinated_preview as controller
from job_discovery import matching


def app_test():
    folder=Path(tempfile.gettempdir())/('comparison-ui-'+uuid.uuid4().hex)
    folder.mkdir()
    with patch('tempfile.TemporaryDirectory',return_value=types.SimpleNamespace(name=str(folder))):
        from streamlit.testing.v1 import AppTest
    return AppTest.from_file(str(controller.ROOT/'coordinated_job_match_preview.py'),default_timeout=240)


class DeveloperComparisonUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patches=[patch.object(controller,'run_comparison',wraps=controller.run_comparison),
            patch.object(native,'build_stable_analysis',wraps=native.build_stable_analysis),
            patch.object(cache,'_connect',side_effect=AssertionError('DB forbidden')),
            patch.object(matches,'_connect',side_effect=AssertionError('DB forbidden')),
            patch.object(matching,'current_evidence_context',side_effect=AssertionError('Live candidate forbidden')),
            patch('tailoring.jd_user_input_overrides.refresh_application_session_analysis_report',side_effect=AssertionError('No application refresh'))]
        cls.compare_call,cls.builder,*cls.forbidden=[p.start() for p in cls.patches]
        cls.app=app_test()
        cls.app.session_state['current_application_id']=123
        cls.app.session_state['latest_report']={'initial_analysis':'frozen synthetic authority'}
        cls.app.run()
        cls.off=not cls.app.toggle(key='developer_preview_enabled').value
        cls.off_calls=cls.builder.call_count
        cls.app.selectbox(key='developer_case').set_value('E04').run()
        cls.app.toggle(key='developer_preview_enabled').set_value(True).run()
        cls.before_button_calls=cls.builder.call_count
        cls.app.button(key='run_developer_comparison').click().run(timeout=240)
        if cls.app.exception:raise AssertionError([e.message for e in cls.app.exception])
        cls.result=cls.app.session_state[controller.PREVIEW_SESSION_KEY]

    @classmethod
    def tearDownClass(cls):
        for p in reversed(cls.patches):p.stop()

    def setUp(self):
        self.app.radio(key='developer_receipt_side').set_value('Gated').run()
        self.app.multiselect(key='developer_label_filter').set_value([]).run()

    def table(self):
        return next(frame.value for frame in self.app.dataframe if 'Credit display' in frame.value.columns)

    def test_default_off_and_explicit_comparison_only(self):
        self.assertTrue(self.off)
        self.assertEqual(self.off_calls,0)
        self.assertEqual(self.before_button_calls,0)
        self.assertEqual(self.compare_call.call_count,1)
        for forbidden in self.forbidden:forbidden.assert_not_called()
        self.assertEqual(self.app.session_state['current_application_id'],123)
        self.assertEqual(self.app.session_state['latest_report'],{'initial_analysis':'frozen synthetic authority'})

    def test_review_has_unavailable_credit_and_no_gated_percentage(self):
        self.assertIsNone(self.result.gated.alignment)
        self.assertEqual(len(self.app.metric),1)  # published OFF only
        self.assertTrue(any('Whole-JD alignment unavailable' in w.value for w in self.app.warning))
        self.app.multiselect(key='developer_label_filter').set_value(['REVIEW_REQUIRED']).run()
        table=self.table()
        self.assertEqual(set(table['Credit display']),{'Unavailable'})
        self.assertTrue(table['Credit'].isna().all())
        self.assertTrue(any('Contribution unavailable' in w.value for w in self.app.warning))
        self.assertTrue(any('Scoped contradiction' in w.value for w in self.app.warning))
        contrary=next(d.value for d in self.app.dataframe if 'Relationship' in d.value.columns)
        self.assertEqual(set(contrary['Relationship']),{'SAME_ORIGINAL_CONTAINER'})
        self.assertTrue(any('Never maintained' in str(text) for text in contrary['Original text']))
        self.assertTrue(all(not e.proto.expanded for e in self.app.expander))

    def test_filters_side_and_selection_never_recompute(self):
        calls=self.builder.call_count
        self.app.multiselect(key='developer_label_filter').set_value(['REVIEW_REQUIRED']).run()
        self.app.selectbox(key='developer_inspect').set_value(self.table()['Requirement ID'].iloc[0]).run()
        self.app.radio(key='developer_receipt_side').set_value('Published OFF').run()
        self.app.multiselect(key='developer_label_filter').set_value([]).run()
        self.assertEqual(self.builder.call_count,calls)
        self.assertEqual(self.compare_call.call_count,1)
        self.assertFalse(self.app.exception)

    def test_native_row_selection_uses_retained_details(self):
        calls=self.builder.call_count
        rows=self.result.gated.requirements
        index=next(i for i,r in enumerate(rows) if r.label.value=='REVIEW_REQUIRED')
        original=st.dataframe
        def select(*args,**kwargs):
            result=original(*args,**kwargs)
            if str(kwargs.get('key','')).startswith('developer_grid_'):
                return types.SimpleNamespace(selection=types.SimpleNamespace(rows=[index]))
            return result
        with patch.object(st,'dataframe',side_effect=select):self.app.run()
        self.assertFalse(self.app.exception)
        self.assertEqual(self.app.selectbox(key='developer_inspect').value,rows[index].requirement_id)
        self.assertEqual(self.builder.call_count,calls)

    def test_z_revision_invalidates_without_running_analysis(self):
        calls=self.builder.call_count
        with patch.object(controller,'source_revision',return_value='changed-preview-source'):
            self.app.run()
        self.assertFalse(self.app.exception)
        with self.assertRaises(KeyError):self.app.session_state[controller.PREVIEW_SESSION_KEY]
        self.assertEqual(self.builder.call_count,calls)
        self.assertTrue(any('Explicitly run' in item.value for item in self.app.info))

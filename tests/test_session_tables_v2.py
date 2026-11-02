"""Pure/offline Session Tables V2 display-policy tests."""
from __future__ import annotations
import unittest
from unittest.mock import MagicMock
from contextlib import contextmanager
from tailoring.session_table_ui_v2 import (
    render_session_table, SCROLL, PAGED, INTERACTIVE, MODE_KEY,
)

class FakeST:
    def __init__(self, mode=SCROLL):
        self.session_state={MODE_KEY:mode};self.tables=[];self.dataframes=[]
        self.pages=[];self.captions=[]
    @contextmanager
    def container(self, **kwargs):
        yield
    def table(self, rows):self.tables.append(rows)
    def dataframe(self, rows, **kwargs):self.dataframes.append((rows,kwargs))
    def number_input(self, label, **kwargs):
        self.pages.append(kwargs);return 1
    def caption(self, msg):self.captions.append(msg)

class SessionTablesV2Tests(unittest.TestCase):
    def setUp(self):self.rows=[{'Requirement':f'Req {i}','Points':float(i)} for i in range(75)]
    def test_scrollable_is_default_and_skips_canvas(self):
        st=FakeST();render_session_table(st,self.rows,key='a')
        self.assertEqual(len(st.tables),1);self.assertEqual(len(st.tables[0]),40)
        self.assertFalse(st.dataframes);self.assertEqual(len(st.pages),1)
    def test_paginated_limits_to_twelve(self):
        st=FakeST(PAGED);render_session_table(st,self.rows,key='b')
        self.assertEqual(len(st.tables[0]),12);self.assertFalse(st.dataframes)
    def test_interactive_is_opt_in(self):
        st=FakeST(INTERACTIVE);render_session_table(st,self.rows,key='c')
        self.assertFalse(st.tables);self.assertEqual(len(st.dataframes),1)
        self.assertEqual(st.dataframes[0][0],self.rows)
    def test_missing_session_control_preserves_legacy_interactive_table(self):
        st=FakeST()
        st.session_state.clear()
        render_session_table(st,self.rows[:4],key='missing-control')
        self.assertFalse(st.tables)
        self.assertEqual(len(st.dataframes),1)
    def test_unconfigured_mock_streamlit_preserves_legacy_interactive_table(self):
        st=MagicMock()
        render_session_table(st,self.rows[:4],key='mock')
        st.dataframe.assert_called_once()
        st.table.assert_not_called()
    def test_unknown_mode_defaults_to_static(self):
        st=FakeST('unknown');render_session_table(st,self.rows[:4],key='d')
        self.assertEqual(st.tables[0],self.rows[:4]);self.assertFalse(st.dataframes)
    def test_empty_is_safe(self):
        st=FakeST();render_session_table(st,[],key='empty')
        self.assertFalse(st.tables);self.assertFalse(st.dataframes)
    def test_view_does_not_mutate_rows(self):
        st=FakeST();before=[r.copy() for r in self.rows]
        render_session_table(st,self.rows,key='immutable')
        self.assertEqual(self.rows,before)
    def test_comparison_labels_get_separate_widget_keys(self):
        from unittest.mock import patch
        from tailoring import session_table_ui_v2 as tables
        collected=[]
        def compare(label):
            tables.render_session_dataframe(FakeST(), self.rows, height=240)
        with patch.object(tables, 'render_session_table',
                          side_effect=lambda st, rows, **kw: collected.append(kw['key'])):
            compare('Initial vs Final')
            compare('Selected Base vs Final')
        self.assertEqual(len(collected),2)
        self.assertNotEqual(collected[0],collected[1])

if __name__=='__main__':unittest.main()

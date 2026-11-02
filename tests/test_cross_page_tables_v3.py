"""Cross-page read-only table display contracts; zero DB, model, or network calls."""
from __future__ import annotations

import copy
import unittest
from unittest.mock import Mock

from tailoring import session_table_ui_v2 as ui


class _Box:
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False


class _FakeStreamlit:
    def __init__(self, values=None):
        self.session_state = dict(values or {})
        self.tables = []
        self.dataframes = []
        self.pages = []
        self.captions = []
        self.radios = []
    def table(self, data):
        self.tables.append(data)
    def dataframe(self, data, **kwargs):
        self.dataframes.append((data, kwargs))
    def container(self, **kwargs):
        return _Box()
    def number_input(self, label, **kwargs):
        self.pages.append((label, kwargs))
        return kwargs.get('value', 1)
    def caption(self, text):
        self.captions.append(str(text))
    def radio(self, label, options, *, key, **kwargs):
        self.radios.append((label, key, tuple(options)))
        return self.session_state.setdefault(key, options[0])


class CrossPageTablesV3Tests(unittest.TestCase):
    def setUp(self):
        self.rows = [{'Requirement': f'r{i}', 'Match': 'none'} for i in range(55)]
    def test_missing_cross_page_control_defaults_scrollable(self):
        st = _FakeStreamlit()
        ui.render_cross_page_table(st, self.rows, key='test')
        self.assertEqual(len(st.tables), 1)
        self.assertEqual(len(st.tables[0]), 40)
        self.assertEqual(st.dataframes, [])
    def test_cross_page_paginated_twelve(self):
        st = _FakeStreamlit({ui.CROSS_PAGE_MODE_KEY: ui.PAGED})
        ui.render_cross_page_table(st, self.rows, key='test')
        self.assertEqual(len(st.tables[0]), 12)
    def test_cross_page_interactive_opt_in(self):
        st = _FakeStreamlit({ui.CROSS_PAGE_MODE_KEY: ui.INTERACTIVE})
        ui.render_cross_page_table(st, self.rows, key='test')
        self.assertEqual(st.tables, [])
        self.assertEqual(len(st.dataframes), 1)
    def test_invalid_cross_page_mode_safe_static(self):
        st = _FakeStreamlit({ui.CROSS_PAGE_MODE_KEY: 'untrusted'})
        ui.render_cross_page_table(st, self.rows, key='test')
        self.assertEqual(len(st.tables), 1)
    def test_cross_page_controls_share_one_key(self):
        st = _FakeStreamlit()
        self.assertEqual(ui.render_cross_page_table_controls(st), ui.SCROLL)
        self.assertEqual(st.radios[0][1], ui.CROSS_PAGE_MODE_KEY)
    def test_cross_page_does_not_change_session_setting(self):
        st = _FakeStreamlit({ui.MODE_KEY: ui.INTERACTIVE})
        ui.render_cross_page_table(st, self.rows, key='test')
        self.assertEqual(len(st.tables), 1)
        self.assertEqual(st.session_state[ui.MODE_KEY], ui.INTERACTIVE)
    def test_session_mode_unchanged(self):
        st = _FakeStreamlit({ui.MODE_KEY: ui.INTERACTIVE})
        ui.render_session_table(st, self.rows, key='session')
        self.assertEqual(len(st.dataframes), 1)
    def test_empty_safe(self):
        st = _FakeStreamlit()
        ui.render_cross_page_table(st, [], key='empty')
        self.assertEqual(st.dataframes, [])
        self.assertEqual(st.tables, [])
    def test_read_only_no_mutations(self):
        st = _FakeStreamlit()
        before = copy.deepcopy(self.rows)
        ui.render_cross_page_table(st, self.rows, key='test')
        self.assertEqual(self.rows, before)
    def test_minimal_mock_uses_legacy(self):
        st = Mock()
        ui.render_cross_page_table(st, [{'Name': 'x'}], key='mock')
        st.dataframe.assert_called_once()
    def test_unique_widget_keys(self):
        st = _FakeStreamlit()
        ui.render_cross_page_table(st, self.rows, key='job_finder')
        ui.render_cross_page_table(st, self.rows, key='taxonomy')
        self.assertNotEqual(st.pages[0][1]['key'], st.pages[1][1]['key'])


if __name__ == '__main__':
    unittest.main()

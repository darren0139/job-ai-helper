"""Exercise the production search handler with in-memory UI and I/O boundaries."""

from __future__ import annotations

import ast
from pathlib import Path
from types import ModuleType
import unittest
from unittest.mock import MagicMock, Mock, patch


class ResultsReached(Exception):
    """Stop after the handler hands the submitted query to the index reader."""


class JobFinderSearchRefreshTests(unittest.TestCase):
    def render(self, *, clicked=True, query="retail", sources=None, advanced=False,
               manual_refresh=False, state=None, summaries=None):
        # Compile the unchanged renderer body to avoid importing unrelated model
        # integrations. Only UI and external I/O boundaries are supplied below.
        path = Path("job_discovery/ui.py")
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = {"render_job_finder", "_split_identifiers"}
        constants = {"SOURCE_LABELS", "DIRECT_REFRESH_EXCLUDED_SOURCES", "ATS_PROVIDER_LABELS"}
        nodes = [
            node for node in tree.body
            if (isinstance(node, ast.FunctionDef) and node.name in names)
            or (isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id in constants for t in node.targets))
        ]
        namespace = {}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
        st = MagicMock()
        st.session_state = dict(state or {})
        st.text_input.return_value = query
        st.form_submit_button.return_value = clicked
        st.checkbox.side_effect = lambda label, **kw: (
            advanced if label == "Load source management & refresh"
            else kw.get("value", False)
        )
        st.multiselect.side_effect = lambda label, **kw: (
            list(kw["default"] if sources is None else sources)
            if label == "Sources to search" else []
        )
        st.number_input.side_effect = lambda label, **kw: kw["value"]
        st.slider.side_effect = lambda label, **kw: kw["value"]
        st.text_area.return_value = ""
        st.columns.side_effect = lambda sizes: [
            MagicMock() for _ in range(sizes if isinstance(sizes, int) else len(sizes))
        ]
        st.button.return_value = manual_refresh
        events = Mock()
        refresh = Mock(return_value=summaries or [])
        cached = Mock(side_effect=ResultsReached)
        events.attach_mock(refresh, "fetch")
        events.attach_mock(cached.clear, "invalidate")
        events.attach_mock(cached, "read")
        namespace.update(
            st=st,
            init_job_discovery_schema=Mock(),
            init_job_match_schema=Mock(),
            mark_expired_jobs=Mock(),
            list_target_companies=Mock(return_value=[]),
            _render_target_company_registry=Mock(),
            refresh_job_sources=refresh,
            _cached_query_jobs_v16=cached,
        )
        coverage = ModuleType("taxonomy_discovery.coverage_presentation")
        coverage.render_confirmed_coverage = Mock()
        with patch.dict("sys.modules", {"taxonomy_discovery.coverage_presentation": coverage}):
            try:
                namespace["render_job_finder"]()
            except ResultsReached:
                pass
        return st, refresh, cached, events

    def test_search_fetches_before_reading_index_with_advanced_controls_closed(self):
        st, refresh, cached, events = self.render()
        self.assertEqual(refresh.call_count, 1)
        self.assertEqual(refresh.call_args.kwargs["query"], "retail")
        self.assertEqual(
            refresh.call_args.kwargs["selected_sources"],
            ["mycareersfuture", "careers_gov", "staffie"],
        )
        self.assertEqual([c[0] for c in events.mock_calls], ["fetch", "invalidate", "read"])
        cached.assert_called_once_with("retail")
        self.assertEqual(st.session_state["job_finder_page_v15"], 1)
        options = next(c.kwargs["options"] for c in st.multiselect.call_args_list
                       if c.args[0] == "Sources to search")
        self.assertNotIn("fastjobs", options)
        self.assertNotIn("workjio", options)

    def test_selected_sources_and_saved_settings_are_used(self):
        _, refresh, _, _ = self.render(sources=["staffie"], state={
            "job_finder_max_pages_v124": 2,
            "job_finder_refresh_workers_v124": 3,
            "job_finder_refresh_min_interval_v124": 5,
        })
        self.assertEqual(refresh.call_args.kwargs["selected_sources"], ["staffie"])
        self.assertEqual(refresh.call_args.kwargs["max_pages"], 2)
        self.assertEqual(refresh.call_args.kwargs["max_workers"], 3)
        self.assertEqual(refresh.call_args.kwargs["min_refresh_interval_minutes"], 5)

    def test_filter_or_page_rerun_does_not_fetch(self):
        _, refresh, cached, _ = self.render(clicked=False, state={
            "job_finder_active_query_v123": "retail",
        })
        refresh.assert_not_called()
        cached.assert_called_once_with("retail")

    def test_blank_search_does_not_fetch(self):
        _, refresh, cached, _ = self.render(query=" ")
        refresh.assert_not_called()
        cached.assert_not_called()

    def test_no_sources_keeps_local_search_available(self):
        _, refresh, cached, _ = self.render(sources=[])
        refresh.assert_not_called()
        cached.assert_called_once_with("retail")

    def test_manual_refresh_still_uses_shared_pipeline(self):
        _, refresh, cached, _ = self.render(clicked=False, advanced=True,
                                          manual_refresh=True, sources=["staffie"],
                                          state={"job_finder_active_query_v123": "retail"})
        refresh.assert_called_once()
        cached.assert_called_once_with("retail")

    def test_source_failure_is_visible_and_index_is_still_read(self):
        st, refresh, cached, _ = self.render(summaries=[{
            "source_key": "staffie", "status": "error", "error": "Source unavailable",
        }])
        refresh.assert_called_once()
        st.warning.assert_called_once_with("staffie: Source unavailable")
        cached.assert_called_once_with("retail")


if __name__ == "__main__":
    unittest.main()

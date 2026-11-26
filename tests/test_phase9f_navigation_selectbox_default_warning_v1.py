"""Regression for Streamlit's duplicate selectbox default/session-state warning."""
import unittest
from tailoring.phase9f_navigation_state import navigation_selectbox, STATE_KEY


class StrictStreamlit:
    """Rejects the duplicate initialization Streamlit warns about."""
    def __init__(self):
        self.session_state = {}
        self.calls = []

    def selectbox(self, label, options, **kwargs):
        key = kwargs["key"]
        self.calls.append((key, dict(kwargs)))
        if key in self.session_state and "index" in kwargs:
            raise AssertionError("selectbox default index and Session State set together")
        if key in self.session_state:
            return self.session_state[key]
        index = kwargs.get("index", 0)
        value = None if index is None else options[index]
        self.session_state[key] = value
        return value


class NavigationSelectboxDefaultTests(unittest.TestCase):
    def test_first_load_honors_caller_default_index(self):
        st = StrictStreamlit()
        self.assertEqual(navigation_selectbox(st, "Intensity", ["Reuse", "Minor", "Full"],
                                              key="intensity", scope="ranking1", index=2), "Full")
        self.assertEqual(st.calls[-1][1].get("index"), 2)

    def test_rerun_does_not_pass_index_over_restored_session_state(self):
        st = StrictStreamlit()
        self.assertEqual(navigation_selectbox(st, "Intensity", ["Reuse", "Minor", "Full"],
                                              key="intensity", scope="ranking1", index=2), "Full")
        self.assertEqual(navigation_selectbox(st, "Intensity", ["Reuse", "Minor", "Full"],
                                              key="intensity", scope="ranking1", index=0), "Full")
        self.assertNotIn("index", st.calls[-1][1])

    def test_widget_cleanup_restores_identity_without_second_default(self):
        st = StrictStreamlit()
        navigation_selectbox(st, "Source", ["Base", "Library"], key="source", scope="ranking1", index=1)
        del st.session_state["source"]
        self.assertEqual(navigation_selectbox(st, "Source", ["Base", "Library"],
                                              key="source", scope="ranking1", index=0), "Library")
        self.assertNotIn("index", st.calls[-1][1])
        self.assertEqual(st.session_state[STATE_KEY]["source"]["value"], "Library")

    def test_changed_ranking_scope_invalidates_old_choice_and_uses_fresh_default(self):
        st = StrictStreamlit()
        navigation_selectbox(st, "Source", ["Base", "Library"], key="source", scope="ranking1", index=1)
        self.assertEqual(navigation_selectbox(st, "Source", ["Base", "Library"],
                                              key="source", scope="ranking2", index=0), "Base")
        self.assertEqual(st.calls[-1][1].get("index"), 0)
        self.assertEqual(st.session_state[STATE_KEY]["source"]["scope"], "ranking2")

    def test_no_default_still_means_no_selection(self):
        st = StrictStreamlit()
        self.assertIsNone(navigation_selectbox(st, "Intensity", ["Reuse", "Minor", "Full"],
                                                 key="intensity", scope="ranking1", index=None))

    def test_not_found_option_invalidates_session_choice(self):
        st = StrictStreamlit()
        navigation_selectbox(st, "Source", ["A", "B"], key="source", scope="ranking1", index=1)
        self.assertEqual(navigation_selectbox(st, "Source", ["C", "D"],
                                              key="source", scope="ranking1", index=1), "D")
        self.assertEqual(st.calls[-1][1].get("index"), 1)


if __name__ == "__main__":
    unittest.main()

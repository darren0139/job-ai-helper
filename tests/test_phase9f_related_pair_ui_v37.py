"""V3.7: source-pair relevance guard and read-only UI pairing."""
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from tailoring.phase9f_comparison_pair_guard_v37 import classify_related_pair
from tailoring.phase9f_bullet_pair_ui import related_libraries, _render_multi_project_comparison

PROJECT = 'Job AI Helper'
CI_BASE = 'Built 30-job regression audit tooling and GitHub Actions CI across Windows and Ubuntu.'
CI_LIBRARY = 'Added automated unit tests and GitHub Actions CI across Ubuntu and Windows.'
LETTER = 'Added tailored cover letter generation and follow-up support grounded in resumes.'
DB_BASE = 'Implemented database queries and access control using PostgREST.'
DB_LIBRARY = 'Added database access and row-level security controls for reporting.'
UI_BASE = 'Implemented user-facing UI features including sliders and menus.'
UI_LIBRARY = 'Built UI features and interface controls for the dashboard.'
GEN_TEST = 'Tested the service to validate expected behavior.'


def row(text, sources, project=PROJECT, a=False, b=False):
    return {'project':project, 'bullet':text, 'sources':sources,
            'in_actual_a':a, 'in_proposed_b':b, 'words':len(text.split())}


class FakeStreamlit:
    def __init__(self):
        self.session_state = {}
        self.captions = []
        self.infos = []
        self.labels = []
        self.comparisons = []
    def markdown(self, message, **kwargs):
        pass
    def caption(self, message):
        self.captions.append(str(message))
    def info(self, message):
        self.infos.append(str(message))
    @contextmanager
    def container(self, **kwargs):
        yield self
    @contextmanager
    def expander(self, label, **kwargs):
        self.labels.append(label)
        yield self
    def radio(self, label, options, *, format_func, key, on_change):
        values=list(options)
        assert values, 'An empty radio group is not allowed'
        self.labels.append(label)
        chosen=self.session_state.get(key)
        if chosen not in values:
            chosen=values[0]
        self.session_state[key]=chosen
        return chosen


class RelatedPairsUI(unittest.TestCase):
    def test_ci_related_but_cover_letter_not_related(self):
        base=row(CI_BASE,['Selected Base'],a=True)
        ci=row(CI_LIBRARY,['Evidence Library'],b=True)
        letter=row(LETTER,['Evidence Library'],b=True)
        self.assertEqual(classify_related_pair(base,ci)['status'],'likely_same_work')
        self.assertTrue(classify_related_pair(base,ci)['eligible'])
        self.assertFalse(classify_related_pair(base,letter)['eligible'])
        self.assertEqual(related_libraries([base,ci,letter],base),[ci])

    def test_identical_wording_appears_only_once_in_comparison(self):
        same=row(CI_BASE,['Selected Base','Evidence Library'],a=True,b=True)
        self.assertEqual(classify_related_pair(same,same)['status'],'same_wording')
        self.assertTrue(classify_related_pair(same,same)['eligible'])
        self.assertEqual(related_libraries([same],same),[same])

    def test_database_security_related_and_cross_project_denied(self):
        base=row(DB_BASE,['Selected Base'])
        library=row(DB_LIBRARY,['Evidence Library'])
        self.assertTrue(classify_related_pair(base,library)['eligible'])
        self.assertFalse(classify_related_pair(base,row(DB_LIBRARY,['Evidence Library'],'QueryAI'))['eligible'])

    def test_generic_testing_and_keyword_only_do_not_pair(self):
        base=row(GEN_TEST,['Selected Base'])
        library=row('Validated the workflow against its requirements.',['Evidence Library'])
        self.assertFalse(classify_related_pair(base,library)['eligible'])
        self.assertFalse(classify_related_pair(row('Built Python React tools.',['Selected Base']),
            row('Wrote a Python React guide.',['Evidence Library']))['eligible'])

    def test_related_ui_work_can_be_inspected_without_claiming_same_work(self):
        check=classify_related_pair(row(UI_BASE,['Selected Base']),
                                    row(UI_LIBRARY,['Evidence Library']))
        self.assertTrue(check['eligible'])
        self.assertEqual(check['status'],'related_activity')

    def test_missing_provenance_and_unknown_project_denied(self):
        base=row(CI_BASE,['Selected Base'])
        self.assertFalse(classify_related_pair(base,row(CI_LIBRARY,['Current final']))['eligible'])
        self.assertFalse(classify_related_pair(row(CI_BASE,['Selected Base'],''),
                                               row(CI_LIBRARY,['Evidence Library'],'ERROR'))['eligible'])

    def test_primary_ui_only_offers_related_library_as_pair(self):
        base=row(CI_BASE,['Selected Base'],a=True)
        ci=row(CI_LIBRARY,['Evidence Library'],b=True)
        unrelated=row(LETTER,['Evidence Library'],b=True)
        st=FakeStreamlit()
        def capture(streamlit,**kwargs):
            st.comparisons.append((kwargs['base'],kwargs['library']))
        with (patch('tailoring.phase9f_multi_project_evidence_v36.project_checkboxes',return_value=[PROJECT]),
              patch('tailoring.phase9f_wording_explanation_ui.render_wording_comparison',side_effect=capture)):
            _render_multi_project_comparison(st,ranked=[base,ci,unrelated],recorded=True,
                catalog={},result={'winner':'existing_final'},key='pair',jd='JD',report={})
        self.assertTrue(st.comparisons)
        self.assertEqual(st.comparisons[0],(base,ci))
        # Other evidence may be inspected alone but can never become paired.
        self.assertTrue(any(a is None and b is unrelated for a,b in st.comparisons))
        self.assertFalse(any(a is not None and b is unrelated for a,b in st.comparisons))
        self.assertTrue(any('Related Evidence Library' in x for x in st.labels))

    def test_no_related_library_never_selects_unrelated_fallback(self):
        base=row(CI_BASE,['Selected Base'],a=True)
        unrelated=row(LETTER,['Evidence Library'],b=True)
        st=FakeStreamlit()
        with (patch('tailoring.phase9f_multi_project_evidence_v36.project_checkboxes',return_value=[PROJECT]),
              patch('tailoring.phase9f_wording_explanation_ui.render_wording_comparison',
                    side_effect=lambda streamlit,**kwargs: st.comparisons.append((kwargs['base'],kwargs['library'])))):
            _render_multi_project_comparison(st,ranked=[base,unrelated],recorded=True,
                catalog={},result={'winner':'existing_final'},key='pair2',jd='JD',report={})
        self.assertTrue(st.comparisons)
        self.assertEqual(st.comparisons[0],(base,None))
        self.assertFalse(any(a is not None and b is unrelated for a,b in st.comparisons))

    def test_inspection_never_mutates_source_rows(self):
        from copy import deepcopy
        base=row(CI_BASE,['Selected Base'],a=True)
        ci=row(CI_LIBRARY,['Evidence Library'],b=True)
        original=deepcopy([base,ci]);st=FakeStreamlit()
        with (patch('tailoring.phase9f_multi_project_evidence_v36.project_checkboxes',return_value=[PROJECT]),
              patch('tailoring.phase9f_wording_explanation_ui.render_wording_comparison')):
            _render_multi_project_comparison(st,ranked=[base,ci],recorded=True,
                catalog={},result={'winner':'existing_final'},key='readonly',jd='JD',report={})
        self.assertEqual([base,ci],original)

if __name__ == '__main__':
    unittest.main()

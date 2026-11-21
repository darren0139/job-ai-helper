from copy import deepcopy
import unittest

from streamlit.testing.v1 import AppTest
from tailoring.phase9f_bullet_inspector import inspector_rows, pair_explanation, source_group
from tailoring.phase9f_v365_jd_evidence import rank_bullets, requirement_catalog


def fixture():
    jd = 'Build Python APIs. Automated unit testing is preferred.'
    requirements = [
        {'requirement_id': 'api', 'text': 'Build Python APIs', 'parent_text': jd, 'importance': 'core'},
        {'requirement_id': 'test', 'text': 'Automated unit testing is preferred', 'parent_text': jd, 'importance': 'preferred'},
    ]
    rows = [
        {'project': 'Tool', 'bullet': 'Built Python APIs', 'sources': ['Selected Base'],
         'saved_jd_ids': ['api'], 'words': 3, 'in_actual_a': True, 'in_proposed_b': True},
        {'project': 'Tool', 'bullet': 'Built Python APIs with automated unit testing', 'sources': ['Evidence Library'],
         'saved_jd_ids': ['api', 'test'], 'words': 8, 'in_actual_a': False, 'in_proposed_b': False},
        {'project': 'Other', 'bullet': 'Built Python APIs', 'sources': ['Selected Base', 'Evidence Library'],
         'saved_jd_ids': ['api'], 'words': 3, 'in_actual_a': True, 'in_proposed_b': True},
    ]
    return jd, {'raw_jd_text': jd, 'stable_analysis': {'canonical_requirements': requirements}}, rows


class BulletInspectorTests(unittest.TestCase):
    def test_identical_dual_provenance_and_historical_membership(self):
        jd, report, rows = fixture()
        self.assertEqual(source_group(rows[2]), 'Base + Library (identical wording)')
        audit = {'projects': [{'project': 'Tool', 'base': [{'text': 'Built APIs'}],
                               'library': [{'text': 'Built APIs'}], 'final': [{'text': 'Built APIs'}]}]}
        listed, recorded = inspector_rows({}, audit)
        self.assertFalse(recorded)
        self.assertEqual(len(listed), 1)
        self.assertEqual(set(listed[0]['sources']), {'Selected Base', 'Evidence Library', 'Current final'})

    def test_shared_links_and_additional_cues_do_not_create_native_credit(self):
        jd, report, rows = fixture()
        ranked = rank_bullets(rows, requirement_catalog(report, {}), raw_jd_text=jd, result={})
        base = next(r for r in ranked if r['sources'] == ['Selected Base'])
        library = next(r for r in ranked if r['sources'] == ['Evidence Library'])
        comparison = pair_explanation(base, library)
        self.assertEqual(comparison['shared'], ['api'])
        self.assertIn('testing', comparison['library_only_cues'])
        self.assertEqual(comparison['library_unique_native'], [])
        self.assertEqual(comparison['library_words_saved'], -5)
        self.assertEqual(comparison['conclusion'], 'No independent Base-versus-Library winner measured.')

    def test_render_multiple_projects_filters_and_constraints_preserves_input(self):
        jd, report, rows = fixture()
        calc = {'status': 'available', 'rows': rows, 'solver_status': 'optimal_proxy'}
        proposal = {'mathematical_certificate': {'constraints': {'max_changed_memberships': 8}}}
        before = deepcopy((calc, proposal))
        script = '''
import streamlit as st
from tailoring.phase9f_bullet_inspector import render_bullet_inspector
render_bullet_inspector(st, calc=st.session_state['calc'], audit={}, proposal=st.session_state['proposal'],
                       result={'status':'verified','a_score':31,'b_score':31}, baseline_report=st.session_state['report'],
                       raw_jd_text=st.session_state['jd'], projects={}, application_id=156, context='saved')
'''
        app = AppTest.from_string(script)
        for key, val in [('calc', calc), ('proposal', proposal), ('report', report), ('jd', jd)]:
            app.session_state[key] = val
        app.run()
        self.assertFalse(app.exception)
        keys = [item.key for item in app.selectbox]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(len(app.table[0].value), 3)
        app.selectbox(key='bullet_inspector_156_saved_membership').select('Excluded').run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.table[0].value), 1)
        self.assertEqual(app.table[0].value.iloc[0]['Source provenance'], 'Library-only')
        self.assertEqual((calc, proposal), before)

    def test_missing_saved_receipt_renders_unknown_and_never_runs_solver(self):
        app = AppTest.from_string('''
import streamlit as st
from tailoring.phase9f_bullet_inspector import render_bullet_inspector
render_bullet_inspector(st, calc={}, audit={'projects':[{'project':'Tool','base':[{'text':'Built APIs'}]}]},
    proposal={}, result={}, baseline_report={}, raw_jd_text='', projects={}, application_id=1, context='old')
''').run()
        self.assertFalse(app.exception)
        self.assertEqual(app.table[0].value.iloc[0]['Optimized proposal'], 'Unknown')
        self.assertTrue(any('unavailable' in node.value for node in app.info))

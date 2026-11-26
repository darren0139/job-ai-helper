"""Public UI contracts for multi-project B4, not new scoring expectations."""
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch
from contextlib import ExitStack
from streamlit.testing.v1 import AppTest
from tests.test_primary_bullet_explanation import fixture, app_for, TESTING, REMOVED
from tailoring.phase9f_wording_explanation_ui import wording_facts


class WordingPresentation(unittest.TestCase):
    def catalog(self):
        return {str(i):dict(id=str(i),text=text,importance=importance) for i,(text,importance) in enumerate([
            ('Develop and enhance software applications to meet functional and technical specifications','core'),
            ('Execute unit, integration, system and user acceptance testing','core'),
            ('Proficiency in one or more frontend framework (HTML5/Angular/React JS)','core'),
            ('Partner with stakeholders to understand business and system requirements','core'),
            ('Using configuration management, integration and build automation tools to deploy applications','core'),
            ('Proficiency in database will be an added advantage','preferred')])}

    def facts(self,text):return wording_facts({'bullet':text},self.catalog())

    def test_cyber_specificity_delivery_and_incidental_user_are_distinct(self):
        a=self.facts('Implemented user-facing UI features including sliders and level-locking screens to support player progression.')
        b=self.facts('Built gameplay and UI features in a small team, contributing to a completed mobile game released on Google Play.')
        self.assertEqual((a['words'],b['words']),(13,19))  # exact whitespace convention used in the current UI
        self.assertTrue(a['phrases']['features']);self.assertFalse(b['phrases']['features'])
        self.assertTrue(b['phrases']['team']);self.assertTrue(b['phrases']['release'])
        testing=next(q for q in a['requirements'] if 'acceptance testing' in q['text'])
        self.assertFalse(testing['supported']);self.assertEqual(testing['kind'],'Not established')
        self.assertIn('incidental',testing['reason'])
        stakeholder=next(q for q in b['requirements'] if 'stakeholder' in q['text'])
        self.assertFalse(stakeholder['supported']);self.assertIn('not stakeholder',stakeholder['reason'])

    def test_partial_testing_generic_added_and_actual_keyword_are_separate(self):
        f=self.facts('Added automated unit tests and GitHub Actions CI across Ubuntu and Windows.')
        testing=next(q for q in f['requirements'] if 'acceptance testing' in q['text'])
        self.assertIn('integration testing',testing['reason']);self.assertIn('UAT',testing['reason'])
        database=next(q for q in f['requirements'] if 'database' in q['text'])
        self.assertFalse(database['supported']);self.assertEqual(database['kind'],'Not established')
        self.assertFalse(database['phrases'])
        self.assertFalse(any('Added' in x for x in f['limits']))
        f=self.facts('Implemented database access with PostgREST and Row-Level Security policies.')
        self.assertTrue(f['phrases']['database'])

    def test_negative_and_alternative_controls(self):
        for text in ['Did not implement UI features or unit tests.','Keywords: React unit tests database','Planning to build UI features.']:
            f=self.facts(text);self.assertFalse(any(f['phrases'].values()),text)
            self.assertFalse(any(q['supported'] for q in f['requirements']),text)
        f=self.facts('Built React interfaces for a service.')
        frontend=next(q for q in f['requirements'] if 'frontend framework' in q['text'])
        self.assertIn('other alternatives are optional',frontend['reason'])


class MultiProjectUI(unittest.TestCase):
    def test_only_final_docx_project_and_bullet_can_be_selected(self):
        app=app_for().run(timeout=30)
        self.assertFalse(app.exception,list(app.exception))
        projects=[x for x in app.checkbox if x.label in ('Synthetic Query','Synthetic Testing')]
        self.assertEqual([x.label for x in projects],['Synthetic Query','Synthetic Testing'])
        self.assertFalse(any(x.label=='Final résumé project' for x in app.selectbox))
        self.assertTrue(any(x.label=='Select one final résumé bullet' for x in app.radio))
        self.assertFalse(any('Base Resume wording' in x.label or 'Evidence Library wording' in x.label for x in app.radio))
        self.assertEqual({x.label for x in app.button if x.label in ('Select all','Clear all')},{'Select all','Clear all'})
        next(x for x in projects if x.label=='Synthetic Testing').check().run()
        self.assertFalse(app.exception,list(app.exception))
        radios=[x for x in app.radio if x.label=='Select one final résumé bullet']
        self.assertEqual(len(radios),2)
        self.assertEqual(radios[1].value,TESTING)
        self.assertEqual(radios[1].options,[TESTING+' · JD points unavailable'])
        self.assertEqual(radios[0].value,REMOVED)
        self.assertFalse(any(x.label=='Source wording to explain' for x in app.selectbox))

    def test_final_bullet_two_panels_and_jd_evidence_do_not_mutate_receipts(self):
        data=fixture();original=deepcopy(data);app=app_for(data).run(timeout=30)
        self.assertFalse(app.exception,list(app.exception))
        texts=[x.value for x in app.markdown]
        self.assertIn('##### Base Resume', texts)
        self.assertIn('##### Evidence Library', texts)
        self.assertIn('**:green[Strengths]**', texts)
        self.assertIn('**:red[Weaknesses / limits]**', texts)
        self.assertTrue(any('JD requirements & keyword evidence' in x.value for x in app.markdown))
        self.assertTrue(any('Keyword comparison at a glance' in x.value for x in app.markdown))
        self.assertFalse(any(x.label=='Comparison project' for x in app.selectbox))
        self.assertFalse(any(x.label=='Bullet explanation project' for x in app.selectbox))
        for k,v in original.items():self.assertEqual(app.session_state[k],v)
        keys=[x.key for x in [*app.checkbox,*app.radio,*app.button,*app.selectbox] if x.key]
        self.assertEqual(len(keys),len(set(keys)))

    def test_phase8_evidence_is_not_written_outside_its_expander(self):
        script = """import streamlit as st
from unittest.mock import patch
from tailoring.phase8_verification_ui import _render_final_improvement_verdict_v1
saved={'status':'improved_vs_both','comparisons':{'Selected Base':{'verified':True,'before_score':30,'after_score':31,'hard_regressions':[]}}}
with patch('tailoring.phase8_final_improvement_verdict_v1.build_final_improvement_verdict',return_value=saved):
 _render_final_improvement_verdict_v1({'starting_document_contract':{'mode':'selected_base_docx_only'}},baseline_mode='selected_base_only')
"""
        app=AppTest.from_string(script,default_timeout=30).run()
        self.assertFalse(app.exception,list(app.exception))
        panel=next(x for x in app.expander if x.label=='Final comparison evidence and limitations')
        self.assertTrue(any('30 → actual Final 31' in x.value for x in panel.markdown))
        self.assertTrue(any(x.label=='Verification policy help' for x in panel.expander))

    def test_bestof_view_survives_pending_and_audit_reruns(self):
        app=AppTest.from_string('''import streamlit as st
from tailoring.phase9f_navigation_state import navigation_checkbox
visible=navigation_checkbox(st,'Open Best-of résumé comparison',key='bestof',value=False)
pending=st.session_state.pop('pending',False)
if visible or pending: st.write('Best-of visible')
with st.expander('Fitting and source audit (advanced)'):
 st.checkbox('Inspect project',key='audit')
''')
        app.run();app.checkbox[0].check().run();app.session_state['pending']=True
        app.run();app.checkbox[1].check().run()
        self.assertTrue(app.checkbox[0].value)
        self.assertIn('Best-of visible',[x.value for x in app.markdown])

    def test_phase9f_bound_session_cannot_downgrade_to_legacy_approval(self):
        from tailoring import phase9e_blueprint_selection_ui as ui
        current={'current_scope_status':'current','scope_activation_status':'active','decision_fingerprint':'frozen-A'}
        context={'decision':current,'status':'current','can_generate':True}
        original=deepcopy(context)
        with ExitStack() as stack:
            stack.enter_context(patch.object(ui,'resolve_current_phase9e_generation_context',return_value=context))
            stack.enter_context(patch.object(ui,'_show_active_binding'))
            stack.enter_context(patch.object(ui,'_render_decision_history'))
            stack.enter_context(patch.object(ui,'phase9f_d_execution_state',return_value={'confirmed_intensity':'full'}))
            stack.enter_context(patch('tailoring.phase9f_session_handoff.render_phase9f_source_comparison'))
            guarded=stack.enter_context(patch('tailoring.phase9f_application_confirmation_ui.render_phase9f_source_revision'))
            bind=stack.enter_context(patch.object(ui,'evaluate_and_bind_application_blueprint'))
            exact=stack.enter_context(patch.object(ui,'get_exact_job_description_for_application',side_effect=ValueError('Changed source must be reverified')))
            app=AppTest.from_string('from tailoring.phase9e_blueprint_selection_ui import render_phase9e_blueprint_selection\nrender_phase9e_blueprint_selection(application_id=7,baseline_report={})').run()
            self.assertFalse(app.exception,list(app.exception));exact.assert_not_called();bind.assert_not_called()
            guarded.assert_called_once_with(application_id=7)
            exact.assert_not_called();bind.assert_not_called();self.assertEqual(context,original)


if __name__=='__main__':unittest.main()

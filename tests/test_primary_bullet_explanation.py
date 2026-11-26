"""V3.9: only verified document bullets are selectable in primary review.

All source options remain available for diagnostic computation, but they are
not independently selectable as a purported Base-vs-Library contest.
"""
from copy import deepcopy
import unittest
from streamlit.testing.v1 import AppTest

REMOVED = 'Implemented database queries and access control for reporting.'
TESTING = 'Implemented automated unit tests for workflow checks.'
OTHER = 'Built database queries and access control for a service.'
DB = 'Implement database queries and access control'
QA = 'Execute unit, integration, system and user acceptance testing'


def fixture():
    jd = QA + '\n' + DB
    requirements = [dict(requirement_id='testing', text=QA, importance='core'),
                    dict(requirement_id='database', text=DB, importance='preferred')]
    for req in requirements:
        req['source_provenance'] = [{'raw_parent_text': req['text']}]
    report = {'raw_jd_text': jd, 'stable_analysis': {'canonical_requirements': requirements}}
    rows = [dict(project='Synthetic Query', bullet=REMOVED, sources=['Evidence Library','Current final'],
                 saved_jd_ids=['database'], in_actual_a=True, in_proposed_b=False, words=len(REMOVED.split())),
            dict(project='Synthetic Testing', bullet=TESTING, sources=['Evidence Library','Current final'],
                 saved_jd_ids=['testing'], in_actual_a=True, in_proposed_b=True, words=len(TESTING.split())),
            dict(project='Synthetic Query', bullet=OTHER, sources=['Selected Base','Current final'],
                 saved_jd_ids=['database'], in_actual_a=True, in_proposed_b=True, words=len(OTHER.split()))]
    audit = {'verified':True, 'docx_sha256':'a'*64, 'generation_id':'gen', 'projects':[]}
    for project in ('Synthetic Query','Synthetic Testing'):
        scope = [r for r in rows if r['project']==project]
        audit['projects'].append({'project':project, **{field:[{'text':r['bullet']} for r in scope if tag in r['sources']]
            for field,tag in [('base','Selected Base'),('library','Evidence Library'),('final','Current final')]}})
    def native(rid, text, strength):
        return {'requirement_id':rid, 'match_label':'weak' if rid=='testing' else 'direct',
                'evidence_strength':strength, 'evidence':[{'section':'projects','text':text}]}
    result = {'status':'verified', 'winner':'existing_final', 'a_score':31, 'b_score':31,
              'a_docx_sha256':'a'*64, 'b_docx_sha256':'b'*64,
              'native_document_evidence':{
                  'existing':{'docx_sha256':'a'*64,'requirements':[native('database',REMOVED,5),native('testing',TESTING,2)]},
                  'alternative':{'docx_sha256':'b'*64,'requirements':[native('database',OTHER,5),native('testing',TESTING,2)]}}}
    return dict(jd=jd, report=report, calc={'status':'available','rows':rows}, audit=audit, result=result)


def app_for(data=None):
    data = data or fixture()
    app = AppTest.from_string('''import streamlit as st
from tailoring.phase9f_v364_decision_explorer import render_compact_decision_explorer
render_compact_decision_explorer(st,calc=st.session_state.calc,result=st.session_state.result,
 proposal={},audit=st.session_state.audit,projects={},application_id=156,context='primary-test',
 baseline_report=st.session_state.report,raw_jd_text=st.session_state.jd)
''')
    for key, value in data.items():
        app.session_state[key] = value
    return app


class FinalOnlyExplanation(unittest.TestCase):
    def test_first_selector_is_actual_docx_not_source_pool(self):
        app = app_for().run(timeout=30)
        self.assertFalse(app.exception,list(app.exception))
        text = [v.value for v in app.markdown]
        self.assertIn('### Bullet Choices & Base vs Library',text)
        self.assertTrue(any(v.label == 'Select one final résumé bullet' for v in app.radio))
        self.assertFalse(any('Base Resume wording' in v.label or 'Related Evidence Library wording' in v.label for v in app.radio))
        self.assertFalse(any(v.label == 'Source wording to explain' for v in app.selectbox))
        self.assertTrue(any('existing fitted document is still selected' in v.value for v in app.warning))

    def test_two_read_only_source_panels_remain(self):
        app = app_for().run(timeout=30)
        self.assertFalse(app.exception,list(app.exception))
        text = [v.value for v in app.markdown]
        self.assertIn('##### Base Resume',text)
        self.assertIn('##### Evidence Library',text)
        self.assertIn('**:green[Strengths]**',text)
        self.assertIn('**:red[Weaknesses / limits]**',text)
        self.assertTrue(any('score unavailable' in v.value.lower() for v in app.caption))

    def test_only_fitted_membership_when_not_adopted(self):
        app=app_for().run(timeout=30)
        self.assertFalse(app.exception,list(app.exception))
        self.assertTrue(any('not an applied removal' in v.value for v in app.warning))
        self.assertFalse(any('Removed from the selected verified challenger' in v.value for v in app.markdown))

    def test_no_readonly_controls_mutate_the_underlying_receipt(self):
        data=fixture();original=deepcopy(data)
        app=app_for(data).run(timeout=30)
        self.assertFalse(app.exception,list(app.exception))
        choices=[v for v in app.checkbox if v.label in ('Synthetic Query','Synthetic Testing')]
        self.assertEqual([v.label for v in choices],['Synthetic Query','Synthetic Testing'])
        next(v for v in choices if v.label=='Synthetic Testing').check().run()
        self.assertEqual(len([v for v in app.radio if v.label=='Select one final résumé bullet']),2)
        next(v for v in app.button if v.label=='Clear all').click().run()
        self.assertFalse(any(v.label=='Select one final résumé bullet' for v in app.radio))
        next(v for v in app.button if v.label=='Select all').click().run()
        self.assertEqual(len([v for v in app.radio if v.label=='Select one final résumé bullet']),2)
        self.assertFalse(app.exception,list(app.exception))
        for key,value in original.items():self.assertEqual(app.session_state[key],value)
        keys=[v.key for v in [*app.checkbox,*app.radio,*app.selectbox,*app.button] if v.key]
        self.assertEqual(len(keys),len(set(keys)))

if __name__=='__main__':unittest.main()

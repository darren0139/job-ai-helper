"""Synthetic presentation controls, not private Application156 source data."""
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
    audit = {'verified':True, 'docx_sha256':'a'*64, 'projects':[]}
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
    for k,v in data.items():app.session_state[k]=v
    return app


class PrimaryExplanation(unittest.TestCase):
    def all_projects(self, app):
        next(v for v in app.button if v.label=='Select all').click().run()
        self.assertFalse(app.exception,list(app.exception))
        return app

    def test_removed_wording_has_substantive_explanation_before_pair_and_ranking(self):
        app=self.all_projects(app_for().run(timeout=30))
        text=[v.value for v in app.markdown]
        primary=text.index('### Bullet Choices & Base vs Library')
        ranking=text.index('#### JD Bullet Relevance Ranking')
        self.assertLess(primary,text.index('##### JD requirements & keyword evidence'))
        self.assertLess(text.index('**What Best-of actually did**'),ranking)
        self.assertIn(REMOVED,text)
        self.assertTrue(any(DB in t for t in text[primary:ranking]))
        self.assertTrue(any('removed only from the tested alternative' in t for t in text))
        self.assertTrue(any('remains in the chosen résumé' in t for t in text))
        self.assertEqual(text.count('### Bullet Choices & Base vs Library'),1)
        self.assertFalse(any(v.label=='Source wording to explain' for v in app.selectbox))

    def test_testing_wording_needs_no_base_or_valid_pair(self):
        app=self.all_projects(app_for().run(timeout=30))
        text=[v.value for v in app.markdown]
        self.assertIn(TESTING,text)
        self.assertTrue(any(QA in t for t in text))
        self.assertTrue(any('integration testing' in t and 'UAT' in t for t in text))
        self.assertTrue(any('included in both versions' in t for t in text))
        self.assertTrue(any('weak' in v.value and '2/5' in v.value for v in app.caption))
        self.assertTrue(any('Native bullet impact' in v.value and 'unmeasured' in v.value for v in app.caption))

    def test_unavailable_selection_and_stale_jd_fail_closed(self):
        data=fixture();data['calc']['status']='unavailable';data['report']['raw_jd_text']='Different frozen JD'
        app=self.all_projects(app_for(data).run(timeout=30))
        self.assertTrue(any('Saved membership unavailable' in v.value for v in app.caption))
        self.assertIn('Saved selection membership unavailable.',[v.value for v in app.markdown])
        self.assertFalse(any('Explicit wording · partial evidence' in v.value for v in app.markdown))
        self.assertFalse(any('included in both versions' in v.value for v in app.markdown))

    def test_read_only_controls_preserve_receipt_and_stable_unique_keys(self):
        data=fixture();original=deepcopy(data)
        app=self.all_projects(app_for(data).run(timeout=30))
        next(v for v in app.checkbox if v.label=='Synthetic Query').uncheck().run()
        next(v for v in app.checkbox if v.label=='Synthetic Query').check().run()
        self.assertFalse(app.exception,list(app.exception))
        for key,value in original.items():self.assertEqual(app.session_state[key],value)
        keys=[v.key for v in [*app.checkbox,*app.radio,*app.selectbox,*app.button] if v.key]
        self.assertEqual(len(keys),len(set(keys)))
        self.assertTrue(any('Individual cause not recorded' in v.value for v in app.caption))


if __name__=='__main__':unittest.main()

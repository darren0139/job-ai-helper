"""UI placement only; reuse existing B3/B4 components and receipt contracts."""
from copy import deepcopy
import unittest

from streamlit.testing.v1 import AppTest
from tests.test_v37_b4_pair_comparison import multi_fixture


def app_for(calc=None):
    jd,report,default=multi_fixture()
    app=AppTest.from_string('''import streamlit as st
from tailoring.phase9f_v364_decision_explorer import render_compact_decision_explorer
render_compact_decision_explorer(st,calc=st.session_state.calc,result={},proposal={},audit={},
    projects={},application_id=156,context='placement',baseline_report=st.session_state.report,
    raw_jd_text=st.session_state.jd)
''')
    for k,v in dict(calc=calc or default,jd=jd,report=report).items():app.session_state[k]=v
    return app


class PairPlacement(unittest.TestCase):
    def all_projects(self, app):
        next(x for x in app.button if x.label=='Select all').click().run()
        self.assertFalse(app.exception,list(app.exception));return app

    def test_one_visible_pair_before_ranking_and_detailed_inspector(self):
        app=self.all_projects(app_for().run(timeout=30))
        text=[x.value for x in app.markdown]
        pair=text.index('### Bullet Choices & Base vs Library')
        ranking=text.index('#### JD Bullet Relevance Ranking')
        why=text.index('**What Best-of actually did**')
        estimate=text.index('##### JD requirements & keyword evidence')
        detail=text.index('#### Inspect project bullets & Base/Library decisions')
        self.assertLess(pair,estimate);self.assertLess(estimate,why);self.assertLess(why,ranking);self.assertLess(ranking,detail)
        self.assertEqual(text.count('### Bullet Choices & Base vs Library'),1)
        keys=[x.key for x in [*app.checkbox,*app.radio,*app.selectbox] if x.key]
        self.assertEqual(len(keys),len(set(keys)))
        self.assertTrue(any(k.startswith('bullet_inspector_156_placement_b4') for k in keys))

    def test_pair_selection_and_inspector_preserve_receipt_bytes(self):
        app=app_for();original=deepcopy(app.session_state['calc']);app.run(timeout=30)
        app=self.all_projects(app)
        for choice in app.radio:
            if choice.label.startswith('Evidence Library wording — Tool'):
                choice.set_value('Built Python APIs for reporting').run()
                break
        self.assertFalse(app.exception,list(app.exception))
        self.assertEqual(app.session_state['calc'],original)
        self.assertTrue(any('included in both versions' in x.value or 'tested alternative' in x.value for x in app.markdown))

    def test_unavailable_receipt_keeps_top_panel_unknown_not_selected(self):
        _,_,calc=multi_fixture();calc['status']='unavailable'
        app=self.all_projects(app_for(calc).run(timeout=30))
        self.assertTrue(any('Saved membership unavailable' in x.value for x in app.caption))
        self.assertEqual(sum(x.value=='### Bullet Choices & Base vs Library' for x in app.markdown),1)

    def test_no_related_pair_keeps_reason_visible_without_inventing_preference(self):
        _,_,calc=multi_fixture()
        for row in calc['rows']:row['saved_jd_ids']=[]
        app=self.all_projects(app_for(calc).run(timeout=30))
        text=[x.value for x in app.markdown]
        self.assertLess(text.index('**What Best-of actually did**'),text.index('#### JD Bullet Relevance Ranking'))
        self.assertTrue(any('not a recorded replacement contest' in x.value for x in app.caption))
        self.assertTrue(any(x.label.startswith('Evidence Library wording — Tool') for x in app.radio))
        self.assertTrue(any('Individual cause not recorded' in x.value for x in app.caption))
        self.assertFalse(any('historical winner' in x.value for x in app.info))


if __name__=='__main__':unittest.main()

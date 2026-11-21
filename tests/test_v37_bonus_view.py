from copy import deepcopy
from hashlib import sha256
import json
import unittest
from contextlib import nullcontext
from unittest.mock import MagicMock

from tailoring.phase9f_v37_bonus_view import load_bonus_view, render_bonus_view


class BonusViewTests(unittest.TestCase):
    def test_boundary_and_project_filtered_readable_native_tie(self):
        jd = 'Knowledge of SQL is preferred'
        lead = 'Built the application'
        added = 'Implemented SQL database queries'
        req = {'id': 'sql', 'text': jd, 'importance': 'preferred', 'match_label': 'none'}
        identity = {'jd_sha256': sha256(jd.encode()).hexdigest(), 'scoring_version': 'tested',
                    'status': 'verified', 'pages': 1, 'docx_leads_verified': True,
                    'layout_reference_sha256': 'layout', 'requirements': [req], 'score': 12}
        before = {**identity, 'docx_sha256': 'baseline',
                  'docx_project_order': [{'project': 'Tool', 'after': [lead]}]}
        after = {**identity, 'docx_sha256': 'trial',
                 'docx_project_order': [{'project': 'Tool', 'after': [lead,added]}]}
        bonus = {'categories': {'preferred': {'available': 1,'earned': 1,'status': 'applicable'},
                                'supporting': {'available': 0,'earned': 0,'status': 'not_applicable'}},
                 'requirements': [{**req, 'coverage': 'unique', 'best': None, 'earned': 1}]}
        previous = deepcopy(bonus)
        previous['categories']['preferred']['earned'] = 0
        previous['requirements'][0]['earned'] = 0
        receipt = {'baseline':before, 'baseline_bonus':previous,
                   'variants': {'chosen': {'native': after,'bonus':bonus, 'exact_ats_technologies':['sql']}},
                   'floors':{},'source_reviews':[{'project':'Tool','wording':added,'requirement_id':'sql',
                                                'label':'direct','strength':4,'basis':'Documented query implementation.'}]}
        data = json.dumps(receipt).encode()
        binding = {'data': data,'receipt_sha256': sha256(data).hexdigest(),'variant':'chosen',
                   'baseline_sha256':'baseline','trial_sha256':'trial','scoring_version':'tested'}
        audit = {'verified':True,'docx_sha256':'layout','projects':[
            {'project':'Tool','base':[{'text':lead}],'library':[{'text':added}]}]}
        catalog = {'sql': req}
        self.assertIsNone(load_bonus_view({**binding,'trial_sha256':'wrong'},jd,catalog,audit))
        self.assertIsNone(load_bonus_view(binding,jd,{'sql':{**req,'importance':'core'}},audit))
        self.assertIsNone(load_bonus_view(binding,jd,catalog,{**audit,'projects':[]}))
        view = load_bonus_view(binding,jd,catalog,audit)
        self.assertEqual(view['isolated'],('Tool',added))
        st = MagicMock()
        st.expander.return_value = nullcontext()
        render_bonus_view(st,view,'Other project',[])
        st.expander.assert_not_called()
        render_bonus_view(st,view,'Tool',[])
        st.caption.assert_any_call('Isolated addition · 4 words · Native Job Match +0.')
        st.write.assert_any_call('**Preferred coverage** · 0 of 1 weighted units → 1 of 1 weighted units')
        st.caption.assert_any_call('Requirement-level review · Newly covered in the research review · unique evidence')
        st.caption.assert_any_call('Native requirement match · none → none')

        from streamlit.testing.v1 import AppTest

        view['previous_bonus']['requirements'][0]['earned'] = .55
        view['previous_bonus']['categories']['preferred']['earned'] = .55
        component = AppTest.from_string(
            'import streamlit as st\n'
            'from tailoring.phase9f_v37_bonus_view import render_bonus_view\n'
            f'render_bonus_view(st, {view!r}, "Tool", [])\n'
        ).run()
        self.assertFalse(component.exception)
        displayed = [node.value for node in component.markdown]
        captions = [node.value for node in component.caption]
        self.assertIn('**Main native Job Match** · 12/100 → 12/100', displayed)
        self.assertIn('**Supporting coverage** · Not applicable → Not applicable', displayed)
        self.assertIn('**Preferred coverage** · 0.55 of 1 weighted units → 1 of 1 weighted units', displayed)
        self.assertTrue(any('Stronger reviewed evidence for an already-covered requirement' in text for text in captions))
        self.assertIn('Native requirement match · none → none', captions)
        self.assertTrue(any('Reviewed direct' in text for text in displayed))
        self.assertIn(added, displayed)
        self.assertIn('Source · Evidence Library', captions)

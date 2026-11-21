"""Named B4 display contracts. No native renders, models or production data."""
from copy import deepcopy
from hashlib import sha256
import json
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from tailoring.phase9f_bullet_pair_ui import (
    MISSING, UNMEASURED, _proxy, native_trials, related_libraries,
    scope_key, selection_available, selection_explanation,
)
from tailoring.phase9f_v365_jd_evidence import rank_bullets, requirement_catalog
from tests.test_phase9f_v365_explainability import FakeStreamlit
from tests.test_v37_bullet_inspector import fixture


def multi_fixture():
    jd, report, rows = fixture()
    rows += [
        {'project': 'Tool', 'bullet': 'Built Python APIs for reporting', 'sources': ['Evidence Library'],
         'saved_jd_ids': ['api'], 'words': 5, 'in_actual_a': False, 'in_proposed_b': True},
        {'project': 'Tool', 'bullet': 'Painted an unrelated scene', 'sources': ['Evidence Library'],
         'saved_jd_ids': ['test'], 'words': 4, 'in_actual_a': False, 'in_proposed_b': False},
    ]
    return jd, report, {'status': 'available', 'rows': rows, 'solver_status': 'optimal_proxy',
        'objective_stages': [{'priority': 'source_bullet_words', 'recorded_minimization_objective': 11}]}


def ranked_fixture():
    jd, report, calc = multi_fixture()
    return jd, report, calc, rank_bullets(calc['rows'], requirement_catalog(report, {}), raw_jd_text=jd, result={})


def app_fixture(**updates):
    jd, report, calc = multi_fixture()
    proposal = {'mathematical_certificate': {'constraints': {'max_changed_memberships': 8}}}
    script = '''
import streamlit as st
from tailoring.phase9f_bullet_inspector import render_bullet_inspector
render_bullet_inspector(st, calc=st.session_state['calc'], audit=st.session_state['audit'],
    proposal=st.session_state['proposal'], result=st.session_state['result'], baseline_report=st.session_state['report'],
    raw_jd_text=st.session_state['jd'], projects={}, application_id=156, context='b4-test',
    offline_trial=st.session_state['offline'])
'''
    app = AppTest.from_string(script)
    state = dict(jd=jd, report=report, calc=calc, proposal=proposal, audit={}, result={}, offline=None)
    state.update(updates)
    for key, value in state.items(): app.session_state[key] = value
    return app


def choose(app, label, value):
    next(node for node in app.selectbox if node.label == label).set_value(value).run()
    return app


def native_fixture(regression=False):
    jd = 'Automated testing is core.'
    requirement = {'id': 'testing', 'text': jd, 'importance': 'core'}
    audit = {'verified': True, 'docx_sha256': 'c'*64, 'projects': [{
        'project': 'Tool', 'base': [{'text': 'Built a tool'}], 'library': [{'text': 'Wrote unit tests'}]}]}
    template = dict(status='verified', pages=1, docx_leads_verified=True, layout_reference_sha256='c'*64,
                    jd_sha256=sha256(jd.encode()).hexdigest(), scoring_version='native')
    before = dict(template, docx_sha256='b'*64, score=10, requirements=[dict(requirement,
        match_label='direct' if regression else 'none', evidence_strength=4 if regression else 0, evidence=[])],
        docx_project_order=[{'project': 'Tool', 'after': ['Built a tool']}])
    after = dict(template, docx_sha256='a'*64, score=12, requirements=[dict(requirement,
        match_label='weak', evidence_strength=2, evidence=['Wrote unit tests'])],
        docx_project_order=[{'project': 'Tool', 'after': ['Built a tool', 'Wrote unit tests']}])
    decision = dict(project='Tool', wording='Wrote unit tests', requirement_id='testing', requirement=jd,
        importance='core', included=True, shared=False, reason='Recorded addition.', provenance=['Evidence Library'])
    receipt = dict(baseline=before, trial=after, decisions=[decision])
    data = json.dumps(receipt).encode()
    binding = dict(data=data, receipt_sha256=sha256(data).hexdigest(), scoring_version='native',
                   baseline_sha256='b'*64, trial_sha256='a'*64)
    args = dict(audit=audit, catalog={'testing': requirement}, jd=jd, scorer='native',
                project='Tool', wordings={'Wrote unit tests', 'Built a tool'})
    return receipt, binding, args


class PairDecisionTests(unittest.TestCase):
    def test_base_selected_library_excluded_is_membership_not_winner(self):
        a, b = dict(bullet='Base', in_proposed_b=True), dict(bullet='Library', in_proposed_b=False)
        result = selection_explanation(a, b, True)
        self.assertEqual(result['case'], 'base_included')
        self.assertIn('not an independently tested source winner', result['text'])

    def test_library_selected_base_excluded(self):
        result = selection_explanation(dict(bullet='Base', in_proposed_b=False), dict(bullet='Library', in_proposed_b=True), True)
        self.assertEqual(result['case'], 'library_included')
        self.assertIn('Evidence Library wording is included', result['text'])

    def test_both_selected(self):
        result = selection_explanation(dict(bullet='Base', in_proposed_b=True), dict(bullet='Library', in_proposed_b=True), True)
        self.assertEqual(result['case'], 'both_included')
        self.assertIn('Neither is a winner', result['text'])

    def test_both_excluded_no_invented_rejection(self):
        result = selection_explanation(dict(bullet='Base'), dict(bullet='Library'), True)
        self.assertEqual(result['case'], 'both_excluded')
        self.assertIn('individual rejection cause was not recorded', result['text'])

    def test_identical_shared_wording_and_missing_membership(self):
        self.assertEqual(selection_explanation(dict(bullet='Exact'), dict(bullet='Exact'), True)['case'], 'shared')
        self.assertEqual(selection_explanation(dict(bullet='Exact'), dict(bullet='Exact'), False)['text'], MISSING)

    def test_multiple_related_alternatives_no_cross_project_or_questionable_pair(self):
        jd, report, calc, rows = ranked_fixture()
        base = next(r for r in rows if r['sources'] == ['Selected Base'])
        related = related_libraries(rows, base)
        self.assertEqual(len(related), 2)
        self.assertTrue(all(r['project'] == 'Tool' for r in related))
        self.assertFalse(any('unrelated' in r['bullet'] for r in related))

    def test_known_jd_or_document_drift_withholds_membership(self):
        jd, report, calc, _ = ranked_fixture()
        self.assertTrue(selection_available(calc, {}, {}, report, jd))
        self.assertFalse(selection_available(calc, {}, {}, report, jd+' altered'))
        self.assertFalse(selection_available(calc, {'docx_sha256':'new'}, {'a_docx_sha256':'old'}, report, jd))
        self.assertFalse(selection_available({**calc, 'status':'unavailable'}, {}, {}, report, jd))

    def test_stale_source_ownership_withholds_membership(self):
        jd, report, calc, _ = ranked_fixture()
        audit={'verified':True, 'projects':[{'project':'Other', 'base':[{'text':'Different source wording'}]}]}
        self.assertFalse(selection_available(calc, audit, {}, report, jd))

    def test_lexical_bonus_difference_carries_no_native_credit(self):
        _, _, _, rows = ranked_fixture()
        base = next(r for r in rows if r['sources'] == ['Selected Base'])
        library = next(r for r in related_libraries(rows, base) if 'testing' in r['bullet'])
        self.assertFalse(base['native_requirement_ids'] or library['native_requirement_ids'])
        self.assertGreater(len(library['traceable_lexical_link_ids']), len(base['traceable_lexical_link_ids']))
        self.assertEqual(library['native_impact_status'], 'unknown')


class ControlledEvidenceTests(unittest.TestCase):
    def test_controlled_addition_is_measured_and_bound_not_a_source_winner(self):
        _, binding, args = native_fixture()
        rows = native_trials(binding, **args)
        self.assertEqual(rows[0]['native_delta'], 2)
        self.assertEqual(rows[0]['baseline_sha256'], 'b'*64)
        self.assertEqual(rows[0]['hard_losses'], [])

    def test_invalid_native_binding_fails_closed(self):
        _, binding, args = native_fixture()
        for field in ('receipt_sha256','baseline_sha256','trial_sha256','scoring_version'):
            with self.subTest(field=field):
                self.assertEqual(native_trials({**binding, field:'stale'}, **args), [])
        self.assertEqual(native_trials({**binding, 'data':None}, **args), [])
        self.assertEqual(native_trials(binding, **{**args,'jd':'A different JD'}), [])
        self.assertEqual(native_trials(binding, **{**args,'project':'Other'}), [])

    def test_native_requirement_classification_and_provenance_are_required(self):
        receipt, binding, args = native_fixture()
        for mutate in ('importance','provenance','duplicate','extraneous_identity'):
            changed=deepcopy(receipt)
            if mutate=='importance': changed['trial']['requirements'][0]['importance']='preferred'
            elif mutate=='provenance': changed['decisions'][0]['provenance']=['Selected Base']
            elif mutate=='duplicate': changed['trial']['requirements']*=2
            else:
                extra={**changed['trial']['requirements'][0],'id':'unknown','text':'An unbound extra requirement'}
                changed['trial']['requirements'].append(extra)
                changed['baseline']['requirements'].append(extra)
            data=json.dumps(changed).encode()
            self.assertEqual(native_trials({**binding,'data':data,'receipt_sha256':sha256(data).hexdigest()},**args),[])

    def test_higher_native_total_does_not_hide_individual_core_loss(self):
        _, binding, args=native_fixture(regression=True)
        result=native_trials(binding, **args)[0]
        self.assertEqual(result['native_delta'], 2)
        self.assertEqual(result['hard_losses'], ['Automated testing is core.'])

    def test_same_grade_strength_loss_is_visible(self):
        receipt, binding, args=native_fixture()
        receipt['baseline']['requirements'][0].update(match_label='weak',evidence_strength=4)
        data=json.dumps(receipt).encode()
        result=native_trials({**binding,'data':data,'receipt_sha256':sha256(data).hexdigest()}, **args)[0]
        self.assertTrue(result['hard_losses'])

    def test_saved_proxy_is_scope_bound_and_does_not_call_solver_on_open(self):
        jd, _, calc, rows=ranked_fixture()
        base=next(r for r in rows if r['sources']==['Selected Base'])
        library=related_libraries(rows,base)[0]
        proposal={'source_comparison':{'projects':[]}}
        audit={'verified':True}
        identity=sha256((base['project']+'\0'+base['bullet']).encode()).hexdigest()[:16]
        cache='test_proxy_'+scope_key(calc,proposal,audit,{},jd)+'_'+identity
        ui=FakeStreamlit()
        ui.session_state[cache]={'status':'calculated','project':base['project'],'bullet':base['bullet'],
            'comparison':'proxy_tie','force_in':{'status':'optimal_proxy','selected_words':20},
            'force_out':{'status':'optimal_proxy','selected_words':19}}
        with patch('tailoring.phase9f_certified_selection_v36.compare_forced_bullet') as solve:
            _proxy(ui,base=base,library=library,calc=calc,proposal=proposal,audit=audit,projects={},jd=jd,key='test',recorded=True)
            solve.assert_not_called()
        self.assertIn('constrained proxy tests tied',' '.join(ui.logs))
        ui.logs=[]
        _proxy(ui,base=base,library=library,calc=calc,proposal=proposal,audit=audit,projects={},jd=jd+' drift',key='test',recorded=True)
        self.assertIn('No measured proxy result',' '.join(ui.logs))


class PairStreamlitTests(unittest.TestCase):
    def test_word_count_uses_exact_text_without_changing_saved_objective(self):
        app=choose(app_fixture().run(),'Comparison project','Tool')
        choose(app,'Related Evidence Library wording',1)
        captions=' '.join(n.value for n in app.caption)
        self.assertIn('Word count · 7',captions)
        self.assertIn('Saved selection word cost · 8',captions)
        self.assertEqual(app.session_state['calc']['rows'][1]['words'],8)

    def test_controlled_native_details_are_opt_in_and_core_loss_is_visible(self):
        receipt,binding,args=native_fixture(regression=True)
        req=receipt['baseline']['requirements'][0]
        result={'status':'verified','a_docx_sha256':'c'*64,'b_docx_sha256':'d'*64,'a_score':10,'b_score':12,
            'native_document_evidence':{}}
        for role,doc in [('existing',receipt['baseline']),('alternative',receipt['trial'])]:
            wording=doc['docx_project_order'][0]['after'][-1]
            result['native_document_evidence'][role]={'docx_sha256':('c' if role=='existing' else 'd')*64,
                'requirements':[{'requirement_id':'testing','text':req['text'],'importance':'core',
                  'match_label':doc['requirements'][0]['match_label'],'evidence_strength':doc['requirements'][0]['evidence_strength'],
                  'evidence':[{'section':'projects','text':wording}]}]}
        rows=[{'project':'Tool','bullet':text,'sources':[source],'saved_jd_ids':['testing'],
               'in_actual_a':i==0,'in_proposed_b':i==1,'words':len(text.split())}
              for i,(text,source) in enumerate([('Built a tool','Selected Base'),('Wrote unit tests','Evidence Library')])]
        report={'raw_jd_text':args['jd'],'stable_analysis':{'scoring_version':'native',
                'canonical_requirements':[{'requirement_id':'testing','text':args['jd'],'importance':'core','parent_text':args['jd']}]}}
        app=app_fixture(jd=args['jd'],report=report,calc={'status':'available','rows':rows},
                        result=result,audit=args['audit'],offline=binding).run()
        self.assertFalse(app.exception)
        self.assertFalse(any('Measured native Job Match delta' in n.value for n in app.markdown))
        next(n for n in app.checkbox if n.label=='Show saved controlled native trial (read-only)').check().run()
        self.assertFalse(app.exception)
        self.assertTrue(any('Measured native Job Match delta +2' in n.value for n in app.markdown))
        self.assertTrue(any('Recorded Required/Core evidence regression' in n.value for n in app.warning))
        self.assertTrue(any('not a Base-versus-Library swap' in n.value for n in app.caption))

    def test_project_pair_switches_and_unique_keys_are_read_only(self):
        app=app_fixture().run()
        self.assertFalse(app.exception)
        choose(app,'Comparison project','Tool')
        self.assertFalse(app.exception)
        self.assertEqual(len(next(n for n in app.selectbox if n.label=='Related Evidence Library wording').options),2)
        before=deepcopy(app.session_state['calc'])
        choose(app,'Related Evidence Library wording',1)
        keys=[n.key for n in app.selectbox]+[n.key for n in app.button]
        self.assertEqual(len(keys),len(set(keys)))
        choose(app,'Comparison project','Other')
        self.assertFalse(app.exception)
        self.assertTrue(any('Shared Base + Library wording' in n.value for n in app.markdown))
        choose(app,'Comparison project','Tool')
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['calc'],before)

    def test_missing_receipt_keeps_wording_and_unknown_membership(self):
        jd,report,calc=multi_fixture()
        app=app_fixture(calc={**calc,'status':'unavailable'}).run()
        self.assertFalse(app.exception)
        self.assertTrue(any(MISSING in n.value for n in app.info))
        self.assertTrue(any('Optimized proposal · Unknown'==n.value for n in app.markdown))
        self.assertTrue(any('Existing fitted résumé · Unknown'==n.value for n in app.markdown))
        self.assertEqual(set(app.table[0].value['Existing fitted résumé']), {'Unknown'})

    def test_stale_receipt_cannot_claim_selected(self):
        app=app_fixture(jd='A changed JD.').run()
        self.assertFalse(app.exception)
        self.assertTrue(any(MISSING in n.value for n in app.info))

    def test_lexical_evidence_and_slate_constraints_are_explicit(self):
        app=choose(app_fixture().run(),'Comparison project','Tool')
        messages=' '.join(n.value for n in app.caption)
        self.assertIn(UNMEASURED,messages)
        self.assertIn('not a per-bullet causal explanation',messages)
        self.assertTrue(any('Saved link with lexical cues' in n.value for n in app.caption))
        self.assertTrue(any('Recorded whole-slate objectives' in n.value for n in app.markdown))

    def test_unsafe_challenger_warning_survives_higher_total(self):
        app=app_fixture(result={'status':'verified','a_score':10,'b_score':12,'hard_regressed_ids':['api']}).run()
        self.assertFalse(app.exception)
        self.assertTrue(any('Required/Core regression' in n.value for n in app.warning))

    def test_quick_compare_from_evidence_selects_related_pair(self):
        app=app_fixture().run()
        # Select the Tool Library row in the existing inspector evidence dropdown.
        evidence=next(n for n in app.selectbox if n.label=='Evidence bullet')
        selected=next(i for i,label in enumerate(evidence.options) if 'Built Python APIs for reporting' in label)
        evidence.set_value(selected).run()
        next(n for n in app.button if n.label=='Compare this bullet with related source wording').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(next(n for n in app.selectbox if n.label=='Comparison project').value,'Tool')
        selected=next(n for n in app.selectbox if n.label=='Related Evidence Library wording')
        self.assertIn('for reporting',selected.options[selected.value])

    def test_passive_display_never_scores_renders_or_optimizes(self):
        with patch('tailoring.phase9f_certified_selection_v36.compare_forced_bullet') as solve, patch(
            'tailoring.phase9f_automatic_bestof_v30.evaluate_auto') as evaluate, patch(
            'tailoring.phase9f_joint_resume_optimizer_v2_6.materialize_verified_candidate') as render:
            app=app_fixture().run()
            self.assertFalse(app.exception)
            solve.assert_not_called();evaluate.assert_not_called();render.assert_not_called()

    def test_desktop_columns_wrap_and_narrow_rule_is_scoped(self):
        app=choose(app_fixture().run(),'Comparison project','Tool')
        self.assertFalse(app.exception)
        self.assertTrue(app.columns)
        style=next(n.value for n in app.markdown if '@media(max-width:800px)' in n.value)
        self.assertIn('flex-direction:column',style)
        self.assertIn('.st-key-bullet_inspector_156_b4-test_b4_',style)
        self.assertNotIn('text-overflow',style)
        self.assertTrue(any(n.value=='Built Python APIs' for n in app.markdown))


if __name__=='__main__': unittest.main()

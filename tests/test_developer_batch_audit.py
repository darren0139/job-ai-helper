"""Independent Phase 1.1 triage expectations and actual-adapter integration."""
from copy import deepcopy
from dataclasses import replace
from functools import lru_cache
from io import BytesIO
import json
import os
import unittest
from unittest.mock import patch
import zipfile

from job_discovery import developer_comparison as a, developer_batch_audit as b
from job_discovery import developer_batch_ui as ui
from tests.test_developer_comparison import page_test


@lru_cache(maxsize=1)
def quick():
    with patch.dict(os.environ, {a.GATE: '1'}):
        state = b.new_batch(list(b.QUICK))
        b.run_chunk(state, session_enabled=True, limit=3)
    if any(e['status'] != 'COMPLETED' for e in state['entries'].values()):
        raise AssertionError('Actual quick pipeline did not complete')
    return state


class BatchContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.state = quick()

    def test_registry_presets_and_order(self):
        ids = [c['id'] for c in b.registry()]
        self.assertEqual(len(ids), 38)
        self.assertEqual(b.QUICK, ('E01','E02','E04'))
        self.assertEqual(len(set(b.EXTENDED)), 10)
        self.assertTrue(set(b.EXTENDED) <= set(ids))
        self.assertEqual(b.ordered(['E04','E02','E01']), list(b.QUICK))
        for invalid in ([], ['E01','E01'], ['live_candidate'], ['E01']*39):
            with self.assertRaises(ValueError): b.new_batch(invalid)

    def test_gates_enforced_in_runner(self):
        for setting, consent in [('',True), ('1',False)]:
            with patch.dict(os.environ, {a.GATE: setting}), patch.object(a,'evaluate') as evaluate:
                with self.assertRaises(ValueError): b.run_chunk(deepcopy(self.state), session_enabled=consent)
                evaluate.assert_not_called()

    def test_currentness_and_case_specific_fingerprints(self):
        self.assertEqual(len({e['case_fingerprint'] for e in self.state['entries'].values()}), 3)
        with patch.object(b,'revision',return_value='changed'), self.assertRaises(ValueError):
            b.require_current(self.state)
        with patch.dict(os.environ,{a.GATE:'1'}), patch.object(a,'evaluate') as evaluate:
            b.run_chunk(deepcopy(self.state),session_enabled=True,limit=3)
            evaluate.assert_not_called()

    def test_e01_geometry_and_footer_independent_observation(self):
        entry = self.state['entries']['E01']; result = entry['result']; c = result['comparison']
        self.assertEqual((c.published.alignment,c.gated.alignment), (27,27))
        self.assertEqual((len(c.published.requirements),len(c.gated.requirements)), (30,29))
        findings = entry['findings']
        self.assertTrue(any(f['code']=='SAME_SCORE_DIFFERENT_GEOMETRY' for f in findings))
        sources = {f['identity'].split(':',1)[1] for f in findings
                   if f['code']=='METADATA_FOOTER_REVIEW' and 'v1.23' in f['identity']}
        self.assertEqual(sources, {f'raw_jd.lines[{n}]' for n in range(34,43)})
        self.assertTrue(all(f['kind']=='HEURISTIC_REVIEW' for f in findings if f['code']=='METADATA_FOOTER_REVIEW'))
        self.assertTrue(all('No effect on published' in f['reason'] for f in findings if f['code']=='METADATA_FOOTER_REVIEW'))

    def test_zero_null_conflict_and_provenance(self):
        result = self.state['entries']['E04']['result']
        summary = b.summary('E04', self.state['entries']['E04'])
        self.assertIsNone(summary['Experimental alignment'])
        self.assertEqual(summary['Whole-JD comparison'], 'WITHHELD')
        self.assertTrue(summary['Conflict quarantine'])
        rows = b.review_rows(result['comparison'])
        self.assertTrue(any(r['Published credit']==0 for r in rows))
        for row in result['comparison'].gated.requirements:
            if row.conflict and row.conflict.get('quarantine'):
                self.assertEqual(row.label.value, 'REVIEW_REQUIRED')
                self.assertIsNone(row.contribution)
                self.assertTrue(row.evidence[0]['source'])
                self.assertTrue(row.evidence[0]['evidence_id'])

    def test_filters_and_stable_selection(self):
        rows = b.review_rows(self.state['entries']['E04']['result']['comparison'])
        self.assertEqual(len(rows),len({r['Requirement ID'] for r in rows}))
        for name in ('Source difference','Conflict','Withheld','Geometry difference','Missing counterpart'):
            self.assertTrue(all(r[name] for r in b.filter_requirements(rows,name)))
        first,second,third = [r['Requirement ID'] for r in rows[:3]]
        edited = [{'Requirement ID':second,'Select':True}, {'Requirement ID':first,'Select':False}]
        self.assertEqual(b.merge_selection([first,third],edited,[first,second]),sorted([second,third]))
        with self.assertRaises(ValueError): b.merge_selection([],edited,[first])

    def test_failure_isolation_and_resumable_stop(self):
        state = b.new_batch(list(b.QUICK)); progress=[]
        def evaluate(key,**kwargs):
            if key=='E02': raise ValueError('SECRET_PATH')
            return self.state['entries'][key]['result']
        with patch.dict(os.environ,{a.GATE:'1'}), patch.object(a,'evaluate',side_effect=evaluate):
            b.run_chunk(state,session_enabled=True,limit=3,
                should_stop=lambda: len(state['entries'])==1,
                progress=lambda *args:progress.append(args))
            self.assertEqual(list(state['entries']),['E01'])
            b.run_chunk(state,session_enabled=True,limit=3)
        self.assertEqual([e['status'] for e in state['entries'].values()],['COMPLETED','ERROR','COMPLETED'])
        self.assertNotIn('SECRET_PATH',str(state['entries']['E02']))
        self.assertEqual(progress[0][1],'RUNNING')
        data=json.loads(b.export_bundle(state)['json'])
        self.assertEqual(data['manifest']['completed'],2)
        self.assertEqual(data['manifest']['errors'],1)
        self.assertNotIn('report',data['cases']['E02'])
        self.assertIsNone(data['summary'][1]['Published alignment'])

    def test_resource_bounds(self):
        with patch.dict(os.environ,{a.GATE:'1'}):
            for limit in (0,39,True):
                with self.assertRaises(ValueError): b.run_chunk(deepcopy(self.state),session_enabled=True,limit=limit)
            state = b.new_batch(['E01'])
            with patch.object(b,'MAX_RETAINED_BYTES',0), patch.object(a,'evaluate',return_value=self.state['entries']['E01']['result']):
                b.run_chunk(state,session_enabled=True)
            self.assertEqual(state['entries']['E01']['status'],'ERROR')
        with patch.object(b,'MAX_EXPORT_BYTES',1), self.assertRaises(ValueError): b.export_bundle(self.state)

    def test_observed_invariant_defects_and_heuristics_are_distinct(self):
        result = deepcopy(self.state['entries']['E04']['result']); c=result['comparison']
        victim = next(r for r in c.gated.requirements if r.conflict and r.conflict.get('quarantine'))
        broken = replace(victim,label=type(victim.label).DIRECT,contribution=1)
        result['comparison'] = replace(c,gated=replace(c.gated,alignment=90,
            requirements=tuple(broken if r.requirement_id==victim.requirement_id else r for r in c.gated.requirements)))
        findings=b.audit_result(result)
        codes={f['code'] for f in findings if f['kind']=='INVARIANT_VIOLATION'}
        self.assertIn('NUMERIC_WITHHELD_SCORE',codes)
        self.assertIn('CONFLICT_NOT_QUARANTINED',codes)
        self.assertTrue(all(f['severity']=='ERROR' for f in findings if f['kind']=='INVARIANT_VIOLATION'))

    def test_export_determinism_sanitization_and_zip_completeness(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY':'SECRET_SENTINEL'}):
            outputs=b.export_bundle(self.state); again=b.export_bundle(self.state)
        self.assertEqual(outputs,again)
        data=json.loads(outputs['json'])
        self.assertEqual(data['manifest']['completed'],3)
        self.assertFalse(data['manifest']['source_text_included'])
        self.assertNotIn(b'SECRET_SENTINEL',outputs['json'])
        self.assertNotIn(b'raw_text',outputs['json'])
        self.assertNotIn(b'raw_resume_text',outputs['json'])
        self.assertNotIn(str(a.preview.ROOT).encode(),outputs['json'])
        with zipfile.ZipFile(BytesIO(outputs['zip'])) as z:
            self.assertEqual(z.namelist(),sorted(z.namelist()))
            self.assertEqual(len(z.namelist()),6)
            self.assertEqual(json.loads(z.read('manifest.json')),data['manifest'])
            self.assertEqual(z.read('summary.csv'),outputs['csv'])
            for key in b.QUICK:
                self.assertEqual(json.loads(z.read('cases/'+key+'.json')),data['cases'][key])
        selected = [data['cases']['E01']['report']['requirements'][0]['Requirement ID']]
        picked=json.loads(b.selected_export(self.state['entries']['E01']['result'],selected))
        self.assertEqual([r['Requirement ID'] for r in picked['requirements']],selected)
        self.assertEqual(picked['selected_requirement_ids'],selected)

    def test_source_text_requires_deliberate_opt_in(self):
        result=self.state['entries']['E01']['result']
        normal=b.case_report(result)
        full=b.case_report(result,include_text=True)
        self.assertFalse(any('synthetic_selected_originals' in row for row in normal['review_receipts']))
        self.assertTrue(any(row.get('synthetic_selected_originals') for row in full['review_receipts']))
        self.assertTrue(any('raw_text' in row for rows in full['metadata_classifications'].values() for row in rows))
        self.assertFalse(any('raw_text' in row for rows in normal['metadata_classifications'].values() for row in rows))

    def test_priority_order_and_pending_exports(self):
        state=b.new_batch(list(b.QUICK))
        state['entries']['E01']=self.state['entries']['E01']
        payload=json.loads(b.export_bundle(state)['json'])
        self.assertEqual(payload['manifest']['pending'],2)
        self.assertEqual(payload['cases']['E02']['status'],'PENDING')
        self.assertNotIn('report',payload['cases']['E02'])
        levels=[{'ERROR':0,'REVIEW':1,'INFO':2}[f['severity']] for f in payload['findings']]
        self.assertEqual(levels,sorted(levels))


class MultiReviewUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.state=quick()

    def test_default_off_and_ai_unconfigured(self):
        with patch.dict(os.environ,{a.GATE:''}),patch.object(b,'run_chunk') as run:
            app=page_test().run()
            self.assertFalse(app.exception)
            self.assertFalse(app.button)
            run.assert_not_called()
        with patch.dict(os.environ,{a.GATE:'1'}),patch.object(b,'run_chunk') as run:
            app=page_test().run()
            self.assertTrue(any('AI reviewer OFF' in info.value for info in app.info))
            run.assert_not_called()

    def test_requirement_multiselect_all_flagged_clear_and_filter(self):
        import streamlit as st
        with patch.dict(os.environ,{a.GATE:'1'}),patch.object(a,'evaluate',wraps=a.evaluate) as evaluate:
            app=page_test(); app.session_state[a.STATE]=self.state['entries']['E04']['result']
            app.session_state['developer_job_match_ui_v1_case']='E04'
            app.session_state['developer_job_match_ui_v1_enabled']=True
            app.run(); prefix='developer_single_review_E04'
            app.button(key=prefix+'_action_0').click().run()
            chosen=app.session_state[prefix+'_selected']
            self.assertGreater(len(chosen),1)
            app.selectbox(key=prefix+'_filter').set_value('Conflict').run()
            self.assertEqual(app.session_state[prefix+'_selected'],chosen)
            with patch.object(st,'download_button',wraps=st.download_button) as download:
                app.run()
                call=next(c for c in download.call_args_list if c.kwargs.get('key')==prefix+'_download')
                payload=json.loads(call.args[1])
                self.assertEqual(payload['selected_requirement_ids'],chosen)
            app.button(key=prefix+'_action_1').click().run()
            self.assertFalse(app.session_state[prefix+'_selected'])
            app.button(key=prefix+'_action_2').click().run()
            self.assertTrue(app.session_state[prefix+'_selected'])
            self.assertFalse(app.exception)
            evaluate.assert_not_called()

    def test_native_checkbox_selection_uses_ids(self):
        import streamlit as st
        with patch.dict(os.environ,{a.GATE:'1'}),patch.object(a,'evaluate') as evaluate:
            app=page_test(); app.session_state[a.STATE]=self.state['entries']['E01']['result']
            app.session_state['developer_job_match_ui_v1_enabled']=True
            original=st.data_editor
            captured=[]
            def edit(data,**kwargs):
                result=original(data,**kwargs)
                if kwargs['key'].startswith('developer_single_review_E01_editor'):
                    result=deepcopy(result)
                    result[0]['Select']=True;result[1]['Select']=True
                    captured.extend(r['Requirement ID'] for r in result[:2])
                return result
            with patch.object(st,'data_editor',side_effect=edit):app.run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state['developer_single_review_E01_selected'],sorted(captured))
            evaluate.assert_not_called()

    def test_batch_explicit_step_progress_and_no_rerun_scoring(self):
        with patch.dict(os.environ,{a.GATE:'1'}),patch.object(a,'evaluate',wraps=a.evaluate) as evaluate:
            app=page_test().run()
            app.toggle(key='developer_job_match_ui_v1_enabled').set_value(True).run()
            evaluate.assert_not_called()
            app.button(key='developer_batch_run').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(evaluate.call_count,1)
            self.assertEqual(list(app.session_state[ui.STATE]['entries']),['E01'])
            self.assertFalse(app.button(key='developer_batch_continue').disabled)
            app.button(key='developer_batch_stop').click().run()
            app.selectbox(key='developer_batch_results_filter').set_value('Suspicious metadata').run()
            app.multiselect(key='developer_batch_inspect').set_value(['E01']).run()
            app.button(key='developer_batch_prepare_export').click().run()
            self.assertEqual(evaluate.call_count,1)
            self.assertEqual(json.loads(app.session_state[ui.EXPORT]['files']['json'])['manifest']['pending'],2)
            self.assertFalse(app.exception)

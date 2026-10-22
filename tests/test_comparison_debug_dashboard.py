"""UI/export contracts with disposable synthetic applications; no private DB."""
from copy import deepcopy
from dataclasses import replace
import csv
import hashlib
from io import BytesIO, StringIO
import json
import unittest
from unittest.mock import patch
import zipfile

from job_discovery import developer_debug_export as debug
from job_discovery import developer_review_ui as ui
from job_discovery import developer_real_comparison as real
from job_discovery.coordinated_preview_model import analysis_view
from tests import test_developer_real_comparison as support
from tests.test_developer_comparison import page_test


class DebugDashboardTests(unittest.TestCase):
    setUpClass=classmethod(support.RealComparisonTests.setUpClass.__func__)
    setUp=support.RealComparisonTests.setUp

    def retained(self):
        loaded=real.load(self.app_id,session_enabled=True)
        from analysis_stability import jd_metadata_policy as a,jd_metadata_v123 as b
        result={'identity':loaded['identity'],'comparison':self.comparison,
                'metadata':{m.SCORER_VERSION:m.classify(self.inputs['raw_jd_text']) for m in (a,b)}}
        return loaded,result

    def identical(self,result):
        # A presentation fixture, not an independent scoring oracle.
        c=result['comparison']; gated=deepcopy(c.published_analysis)
        gated['scoring_version']=real.preview.PROJECTED_SCORER_VERSION
        return dict(result,comparison=replace(c,gated_analysis=gated,gated=analysis_view(gated)))

    def page(self,loaded,result):
        app=page_test()
        app.session_state['developer_job_match_ui_v1_enabled']=True
        app.session_state[real.INDEX]=[{'id':self.app_id,'session_name':'Synthetic private test','job_title':'Test','company':'Test'}]
        app.session_state['developer_real_app']=self.app_id
        app.session_state[real.STATE]={'loaded':loaded,'result':result}
        return app

    def test_zip_files_csv_json_hashes_and_determinism(self):
        loaded,result=self.retained(); before=self.path.read_bytes()
        report=debug.build_report(loaded,result); js,zipped=debug.bundle(report)
        self.assertEqual((js,zipped),debug.bundle(report))
        expected={'manifest.json','comparison_summary.json','requirements.csv','requirement_diagnostics.json',
            'source_identity.json','metadata_v122.csv','metadata_v123.csv','diagnostic_notes.md',
            'evidence_decision_matrix.csv','evidence_decision_trace.json','trace_coverage.json'}
        with zipfile.ZipFile(BytesIO(zipped)) as archive:
            self.assertEqual(set(archive.namelist()),expected)
            manifest=json.loads(archive.read('manifest.json'))
            for name,receipt in manifest['files'].items():
                data=archive.read(name)
                self.assertEqual(hashlib.sha256(data).hexdigest(),receipt['sha256'])
                self.assertEqual(len(data),receipt['bytes'])
            csv_rows=list(csv.DictReader(StringIO(archive.read('requirements.csv').decode())))
            diagnostics=json.loads(archive.read('requirement_diagnostics.json'))['requirements']
            self.assertEqual({r['requirement_id'] for r in csv_rows},{r['requirement_id'] for r in diagnostics})
            self.assertEqual(len(csv_rows),report['comparison_summary']['total_requirements'])
            self.assertEqual(manifest['requirement_count'],len(csv_rows))
            self.assertEqual(json.loads(archive.read('comparison_summary.json')),json.loads(js)['comparison_summary'])
        self.assertEqual(self.path.read_bytes(),before)

    def test_export_never_calls_analysis_or_database_writers(self):
        loaded,result=self.retained()
        with patch.object(real.preview.native,'build_stable_analysis',side_effect=AssertionError('No scoring')), \
             patch.object(real.preview.gated,'build_coordinated_analysis',side_effect=AssertionError('No scoring')), \
             patch('database.db_manager._connect',side_effect=AssertionError('No DB writes')):
            report=debug.build_report(loaded,result)
            self.assertTrue(debug.bundle(report)[1])

    def test_export_rejects_input_identity_and_mode_mismatch(self):
        loaded,result=self.retained()
        for changes in ({'identity':'wrong'},{'mode':real.RETROSPECTIVE}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                debug.build_report(loaded,dict(result,**changes))

    def test_share_safe_report_omits_arbitrary_private_payloads(self):
        loaded,result=self.retained(); result=deepcopy(result); loaded=deepcopy(loaded)
        secret='PRIVATE_EMAIL_person@example.invalid_C:/private/SECRET_API_KEY'
        loaded['unrelated_private']=secret; loaded['context']['private_note']=secret
        result['error']=secret
        for receipt in result['metadata'].values():
            receipt['private']=secret
            for row in receipt['lines']: row.update(raw_text=secret,source=secret,reason=secret)
        c=result['comparison']; published=deepcopy(c.published_analysis)
        candidate=next(r for r in published['canonical_requirements'] if r.get('evidence'))
        candidate['evidence'][0].update(source=secret,text=secret,evidence_id=secret)
        published['rating_band']=secret; published['private']=secret
        result['comparison']=replace(c,published_analysis=published,published=analysis_view(published))
        report=debug.build_report(loaded,result); js,zipped=debug.bundle(report)
        self.assertNotIn(secret,js.decode())
        with zipfile.ZipFile(BytesIO(zipped)) as archive:
            for name in archive.namelist(): self.assertNotIn(secret,archive.read(name).decode())
        self.assertFalse(report['source_text_included'])
        self.assertFalse(report['persistence_eligible'])

    def test_private_excerpts_require_explicit_selection_and_optin(self):
        _,result=self.retained(); rid=result['comparison'].published.requirements[0].requirement_id
        with self.assertRaises(ValueError): debug.selected_excerpts(result,[rid])
        with self.assertRaises(ValueError): debug.selected_excerpts(result,[],opted_in=True)
        with self.assertRaises(ValueError): debug.selected_excerpts(result,['forged'],opted_in=True)
        private=debug.selected_excerpts(result,[rid],opted_in=True)
        self.assertTrue(private['source_text_included'])
        self.assertEqual({r['requirement_id'] for r in private['requirements']},{rid})
        self.assertTrue(all(len(r['requirement_excerpt'])<=2000 for r in private['requirements']))

    def test_counts_zero_difference_and_filters_use_actual_rows(self):
        _,result=self.retained(); same=self.identical(result)
        stats=debug.summary(same); rows=debug.review_rows(same['comparison'])
        self.assertEqual(stats['identical_rows'],len(rows))
        self.assertEqual(stats['changed_labels'],0)
        self.assertEqual(stats['changed_sources'],0)
        self.assertEqual(stats['geometry_mismatches'],0)
        self.assertEqual(len(debug.filter_rows(rows,search=rows[0]['Requirement ID'])),1)
        self.assertEqual(debug.filter_rows(rows,discrepancy='Changed'),[])
        direct=debug.filter_rows(rows,published='DIRECT')
        self.assertTrue(all(r['Published']=='DIRECT' for r in direct))

    def test_null_review_and_geometry_summary_not_zero(self):
        _,result=self.retained()
        stats=debug.summary(dict(result,mode=real.RETROSPECTIVE))
        self.assertGreater(stats['requiring_review'],0)
        self.assertEqual(stats['withheld_scores'],2)
        self.assertIsNone(stats['experimental']['alignment'])
        self.assertTrue(stats['comparative_geometry_withheld'])

    def test_unavailable_native_label_is_not_exported_as_none_evidence(self):
        row=replace(self.comparison.published.requirements[0],native_label=None)
        raw=self.comparison.published_analysis['canonical_requirements'][0]
        self.assertIsNone(debug._side(row,raw)['native_label'])

    def test_importance_receipts_ui_projection_and_bundle_agree(self):
        from analysis_stability.stable_evidence_scoring import IMPORTANCE_WEIGHTS
        loaded,original=self.retained()
        # Independently specified presentation expectations, not scorer outcomes.
        expected={'deal_breaker':'deal_breaker','required':'required','core':'core',
                  'preferred':'preferred','supporting':'supporting',
                  'optional':'UNRECOGNIZED','unknown':'UNRECOGNIZED',
                  'Supporting':'UNRECOGNIZED',None:'UNRECOGNIZED',
                  'PRIVATE_person@example.invalid_C:/private':'UNRECOGNIZED'}
        self.assertEqual(set(IMPORTANCE_WEIGHTS),{'deal_breaker','required','core','supporting','preferred'})
        for value,wanted in expected.items():
            with self.subTest(importance=value):
                result=deepcopy(self.identical(original)); c=result['comparison']
                rid=c.published_analysis['canonical_requirements'][0]['requirement_id']
                for analysis in (c.published_analysis,c.gated_analysis):
                    next(r for r in analysis['canonical_requirements'] if r['requirement_id']==rid)['importance']=value
                before=deepcopy((c.published_analysis,c.gated_analysis))
                row=next(r for r in debug.review_rows(c) if r['Requirement ID']==rid)
                self.assertEqual(row['Importance'],wanted)
                report=debug.build_report(loaded,result); js,zipped=debug.bundle(report)
                self.assertEqual((js,zipped),debug.bundle(report))
                with zipfile.ZipFile(BytesIO(zipped)) as archive:
                    manifest=json.loads(archive.read('manifest.json'))
                    for name,seal in manifest['files'].items():
                        payload=archive.read(name)
                        self.assertEqual(hashlib.sha256(payload).hexdigest(),seal['sha256'])
                        self.assertEqual(len(payload),seal['bytes'])
                    diagnostics=json.loads(archive.read('requirement_diagnostics.json'))['requirements']
                    csv_rows=list(csv.DictReader(StringIO(archive.read('requirements.csv').decode())))
                    self.assertEqual([r['requirement_id'] for r in csv_rows],[r['requirement_id'] for r in diagnostics])
                    detail=next(r for r in diagnostics if r['requirement_id']==rid)
                    for side in ('published','experimental'):
                        self.assertEqual(detail[side]['importance'],wanted)
                    safe=json.loads(js)
                    self.assertEqual(safe['requirement_diagnostics'],diagnostics)
                    for csv_row,diagnostic in zip(csv_rows,diagnostics):
                        for side in ('published','experimental'):
                            if diagnostic[side] is not None:
                                self.assertEqual(csv_row[side+'_label'],diagnostic[side]['label'])
                                credit=csv_row[side+'_credit']
                                self.assertEqual(None if credit=='' else float(credit),diagnostic[side]['standalone_credit'])
                    for name in archive.namelist():
                        self.assertNotIn('PRIVATE_person@example.invalid_C:/private',archive.read(name).decode())
                self.assertEqual((c.published_analysis,c.gated_analysis),before)

    def test_native_table_displays_authoritative_importance_and_safe_unknown(self):
        import streamlit as st
        loaded,result=self.retained(); result=deepcopy(self.identical(result)); c=result['comparison']
        rows=c.published_analysis['canonical_requirements']; self.assertGreaterEqual(len(rows),4)
        values=('core','preferred','supporting','unrecognized-private-value')
        expected={}
        for raw,value in zip(rows,values):
            rid=raw['requirement_id']; expected[rid]=value if value in values[:3] else 'UNRECOGNIZED'
            for analysis in (c.published_analysis,c.gated_analysis):
                next(r for r in analysis['canonical_requirements'] if r['requirement_id']==rid)['importance']=value
        captured={}; original=st.data_editor
        def editor(data,**kwargs):
            if kwargs['key'].startswith('developer_real_editor_'):
                captured.update({r['Requirement ID']:r['Importance'] for r in data})
                self.assertIn('Importance',kwargs['disabled'])
            return original(data,**kwargs)
        app=self.page(loaded,result)
        with patch.object(st,'data_editor',side_effect=editor),patch.object(real,'evaluate') as scoring:
            app.run(); scoring.assert_not_called()
        self.assertFalse(app.exception,[e.message for e in app.exception])
        self.assertEqual({rid:captured[rid] for rid in expected},expected)

    def test_failure_bundle_uses_fixed_code_no_raw_exception(self):
        loaded,_=self.retained()
        with self.assertRaises(ValueError): debug.failure_report(loaded,'PRIVATE_exception')
        report=debug.failure_report(loaded,'COMPARISON_FAILED')
        self.assertEqual(report['exceptions'],[{'code':'COMPARISON_FAILED'}])
        self.assertIsNone(report['comparison_summary']['published']['alignment'])
        self.assertIn('Unavailable',debug.concise_summary(report))
        _,data=debug.bundle(report)
        with zipfile.ZipFile(BytesIO(data)) as z:
            self.assertEqual(json.loads(z.read('manifest.json'))['requirement_count'],0)

    def test_checkbox_selection_filter_hidden_ids_clear_flagged_no_scoring(self):
        import streamlit as st
        loaded,result=self.retained(); before=self.path.read_bytes(); app=self.page(loaded,result)
        original=st.data_editor; captured=[]
        def editor(data,**kwargs):
            output=original(data,**kwargs)
            if kwargs['key'].startswith('developer_real_editor_'):
                self.assertEqual(set(kwargs['disabled']),set(data[0]) - {'Select'})
                self.assertIn('Select',kwargs['column_config'])
                output=deepcopy(output); output[0]['Select']=True; output[1]['Select']=True
                captured.extend(r['Requirement ID'] for r in output[:2])
            return output
        with patch.object(real,'evaluate') as scoring,patch.object(debug,'build_report',wraps=debug.build_report) as build:
            with patch.object(st,'data_editor',side_effect=editor): app.run()
            self.assertFalse(app.exception,[e.message for e in app.exception])
            self.assertEqual(app.session_state[ui.SELECTION],sorted(set(captured)))
            app.text_input(key='developer_real_search').set_value(captured[0]).run()
            self.assertEqual(app.session_state[ui.SELECTION],sorted(set(captured)))
            app.button(key='developer_real_review_action_1').click().run()
            self.assertEqual(app.session_state[ui.SELECTION],[])
            app.button(key='developer_real_review_action_0').click().run()
            self.assertEqual(app.session_state[ui.SELECTION],[captured[0]])
            app.button(key='developer_real_review_action_2').click().run()
            expected=sorted(r['Requirement ID'] for r in debug.review_rows(result['comparison']) if r['Changed or flagged'])
            self.assertEqual(app.session_state[ui.SELECTION],expected)
            app.run(); scoring.assert_not_called(); build.assert_not_called()
        self.assertEqual(self.path.read_bytes(),before)

    def test_identical_rows_scope_tabs_and_explicit_debug_action(self):
        loaded,result=self.retained(); result=self.identical(result); app=self.page(loaded,result)
        with patch.object(real,'evaluate') as scoring,patch.object(debug,'build_report',wraps=debug.build_report) as build:
            app.run(); self.assertFalse(app.exception,[e.message for e in app.exception])
            self.assertEqual([t.label for t in app.tabs],['Real Application Comparison','Synthetic Comparison','Synthetic Batch Audit'])
            self.assertTrue(any('No requirement-level scoring differences detected for this input.'==x.value for x in app.info))
            self.assertTrue(any('not interchangeable' in x.value for x in app.caption))
            build.assert_not_called()
            app.button(key='developer_real_debug_build').click().run()
            self.assertFalse(app.exception,[e.message for e in app.exception])
            self.assertEqual(build.call_count,1)
            cache=app.session_state[ui.EXPORT_STATE]
            self.assertEqual(cache['report']['comparison_summary']['total_requirements'],len(debug.review_rows(result['comparison'])))
            app.run(); self.assertEqual(build.call_count,1); scoring.assert_not_called()

    def test_private_ui_requires_checkbox_and_preview_button(self):
        loaded,result=self.retained(); app=self.page(loaded,result)
        with patch.object(debug,'selected_excerpts',wraps=debug.selected_excerpts) as excerpts:
            app.run(); app.button(key='developer_real_review_action_0').click().run()
            excerpts.assert_not_called()
            app.checkbox(key='developer_real_private_optin').set_value(True).run()
            excerpts.assert_not_called()
            app.button(key='developer_real_private_preview').click().run()
            self.assertEqual(excerpts.call_count,1)
            self.assertIn('private',app.session_state[ui.EXPORT_STATE])
            app.checkbox(key='developer_real_private_optin').set_value(False).run()
            self.assertNotIn('private',app.session_state[ui.EXPORT_STATE])
            self.assertFalse(app.exception,[e.message for e in app.exception])

    def test_source_change_clears_debug_cache(self):
        loaded,result=self.retained(); app=self.page(loaded,result)
        app.run(); app.button(key='developer_real_debug_build').click().run()
        self.assertIn(ui.EXPORT_STATE,app.session_state)
        support.RealComparisonTests.sql(self,"UPDATE applications SET session_name='changed'")
        app.run()
        self.assertNotIn(ui.EXPORT_STATE,app.session_state)
        self.assertNotIn(real.STATE,app.session_state)

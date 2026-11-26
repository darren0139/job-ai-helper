"""Disposable SQLite + exact artifact tests; no application DB or network."""
import json
from copy import deepcopy
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch, Mock
from docx import Document
from pypdf import PdfWriter
from tailoring.phase9f_optimizer_cache_v312b214b3 import (
    run_cached_trial, trial_scope, display_scope, display_context, file_digest, PREFIX)
from database import phase9f_bestof_review_state as store


class CacheFixture(unittest.TestCase):
    def setUp(self):
        tmp=TemporaryDirectory(); self.addCleanup(tmp.cleanup); self.root=Path(tmp.name)
        self.db=self.root/'receipts.sqlite'
        def connect():
            c=sqlite3.connect(self.db); c.row_factory=sqlite3.Row; return c
        self.connect=connect
        p=patch.object(store,'_connect',connect); p.start(); self.addCleanup(p.stop)
        a=self.root/'outputs'/'tailored_resumes'/'app_21_original.docx'; a.parent.mkdir(parents=True)
        b=a.parent/'optimizations'/'app_21_v26_abc.docx'; b.parent.mkdir()
        for path, text in ((a,'Synthetic incumbent Python application.'),(b,'Synthetic alternative Python application with tests.')):
            doc=Document(); doc.add_paragraph(text); doc.save(path)
        pdf=b.with_suffix('.pdf'); writer=PdfWriter(); writer.add_blank_page(width=612,height=792)
        with pdf.open('wb') as f: writer.write(f)
        self.a,self.b,self.pdf=a,b,pdf
        self.fit={'fit_one_page':True,'page_count':1,'docx_path':str(a)}
        self.audit={'verified':True,'generation_id':'gen21','docx_sha256':file_digest(a),'projects':[{'project':'Synthetic','base':['A'],'library':['B']}]}
        self.report={'raw_jd_text':'Python','stable_analysis':{'scoring_version':'current','canonical_requirements':[{'requirement_id':'python'}]}}
        self.kwargs=dict(application_id=21,generation={'generation_id':'gen21','fit_result':self.fit},audit=self.audit,
            projects={'candidate_project_ranking':[{'weight':1}]},fit=self.fit,baseline_report=self.report,raw_jd_text='Python',
            source_docx=a,repo_root=self.root,mode='v37-same-work',identity={'scoring_version':'current','registry_fingerprint':'r'},runtime={'code':'a','renderer':'r'})
        self.result={'status':'verified','candidate_approved':False,'winner':'optimized_candidate','generation_id':'gen21',
            'a_docx_sha256':file_digest(a),'b_docx_sha256':file_digest(b),'candidate_pdf_sha256':file_digest(pdf),
            'candidate_file':str(b),'candidate_pdf':str(pdf),'scoring_version':'current','a_score':20,'b_score':24,'delta':4,
            'hard_regressed_ids':[],'base_floor_verdict':'passed_by_transitivity','proposal':{'requires_base_review':False},
            'a_vs_starting':{'status':'verified','scoring_version':'current','a_docx_sha256':file_digest(a),'a_score':20,
                'selected_base_comparison_status':'maintained','selected_base_required_core_losses':[]},
            'native_document_evidence':{role:{'docx_sha256':file_digest(path),'pages':1,'requirements':[
                {'requirement_id':'python','match_label':'direct','evidence_strength':5}]} for role,path in [('existing',a),('alternative',b)]}}
        self.execute=Mock(side_effect=lambda:deepcopy(self.result))

    def run_trial(self, **kwargs):
        return run_cached_trial(execute=self.execute,**(self.kwargs|kwargs))



class ExactCacheTests(CacheFixture):
    def test_exact_reuse_across_connections_and_detachment(self):
        one=self.run_trial(); self.assertTrue(one['_optimizer_cache']['persisted'])
        self.assertEqual(one['_optimizer_cache']['status'],'fresh')
        two=self.run_trial(); self.assertEqual(two['_optimizer_cache']['status'],'hit')
        self.assertFalse(two['_optimizer_cache']['comparison_executed']); self.execute.assert_called_once()
        two['proposal']['requires_base_review']=True
        self.assertFalse(self.run_trial()['proposal']['requires_base_review'])
        self.assertNotIn('_optimizer_cache',self.result)
        self.assertEqual(file_digest(self.a),self.audit['docx_sha256'])

    def test_switch_modes_and_force(self):
        self.run_trial(); self.run_trial(mode='v35-relevance')
        self.assertEqual(self.execute.call_count,2)
        self.assertEqual(self.run_trial()['_optimizer_cache']['status'],'hit')
        self.assertEqual(self.run_trial(mode='v35-relevance')['_optimizer_cache']['status'],'hit')
        self.assertEqual(self.run_trial(force=True)['_optimizer_cache']['status'],'fresh')
        self.assertEqual(self.execute.call_count,3)

    def test_force_failure_does_not_reuse_superseded_cache(self):
        self.run_trial()
        self.execute.side_effect=lambda:{'status':'withheld','reason':'render unavailable'}
        self.run_trial(force=True)
        self.assertEqual(self.run_trial()['_optimizer_cache']['status'],'fresh')
        self.assertEqual(self.execute.call_count,3)

    def test_full_scope_changes_invalidate(self):
        self.run_trial()
        for overrides in ({'projects':{'candidate_project_ranking':[{'weight':2}]}},
                          {'audit':self.audit|{'projects':[]}}, {'generation':self.kwargs['generation']|{'content_fingerprint':'changed'}},
                          {'baseline_report':self.report|{'resume_profile':{'skills':['Java']}}},
                          {'identity':{'scoring_version':'current','registry_fingerprint':'new'}},
                          {'runtime':{'code':'b','renderer':'r'}}, {'runtime':{'code':'a','renderer':'other'}},
                          {'tie':True}):
            with self.subTest(overrides=overrides):
                self.assertEqual(self.run_trial(**overrides)['_optimizer_cache']['status'],'fresh')
        self.assertEqual(self.execute.call_count,9)

    def test_jd_scorer_and_incumbent_changes_do_not_cache(self):
        self.run_trial()
        for overrides in ({'identity':{'scoring_version':'new'}}, {'raw_jd_text':'Python changed'}, {'application_id':22},
                          {'generation':self.kwargs['generation']|{'generation_id':'other'}}):
            result=self.run_trial(**overrides); self.assertFalse(result['_optimizer_cache']['persisted'])
            self.assertEqual(result['_optimizer_cache']['status'],'fresh')
        self.a.write_bytes(b'changed A')
        self.assertFalse(self.run_trial()['_optimizer_cache']['persisted'])

    def test_missing_tampered_b_and_pdf_are_not_hits(self):
        self.run_trial(); original=self.b.read_bytes(); self.b.write_bytes(b'tampered B')
        self.assertFalse(self.run_trial()['_optimizer_cache']['persisted'])
        self.b.write_bytes(original); self.pdf.unlink()
        self.assertEqual(self.run_trial()['_optimizer_cache']['status'],'fresh')
        self.assertEqual(self.execute.call_count,3)

    def test_partial_withheld_reviewed_no_challenger_and_inconsistent_scores_not_cached(self):
        for result in (self.result|{'status':'withheld'},self.result|{'status':'no_challenger'},
                       self.result|{'status':'needs_review'},self.result|{'candidate_approved':True},
                       self.result|{'reviewed_core_floor':'passed'},self.result|{'delta':99},
                       self.result|{'v35_bounded_search':True,'v35_tested_candidates':2,'v35_verified_candidates':1,
                                    'v35_trial_receipts':[{'status':'verified'},{'status':'withheld'}]},
                       self.result|{'a_vs_starting':{'status':'unavailable'}}):
            self.execute.side_effect=lambda:deepcopy(result)
            self.assertFalse(self.run_trial()['_optimizer_cache']['persisted'])
        self.assertEqual(self.execute.call_count,8)

    def test_tampered_database_checksum_rejected(self):
        self.run_trial(); c=self.connect()
        try:
            c.execute("UPDATE phase9f_bestof_display_receipts SET result_json='{}'");c.commit()
        finally:c.close()
        self.assertEqual(self.run_trial()['_optimizer_cache']['status'],'fresh')
        self.assertEqual(self.execute.call_count,2)

    def test_cache_only_record_not_history_and_application_deletion(self):
        self.run_trial()
        lookup=dict(application_id=21,generation_id='gen21',docx_sha256=self.audit['docx_sha256'],raw_jd_text='Python',scorer_version='current')
        self.assertIsNone(store.load_bestof_display_receipt(**lookup))
        self.assertFalse(store.has_bestof_display_receipt(21,'gen21'))
        self.assertEqual(store.load_historical_optimizer_settings(21,'gen21',self.audit['docx_sha256']),{})
        self.assertEqual(store.list_bestof_mode_history(21,'gen21',self.audit['docx_sha256']),[])
        for manual,mode in ((False,'v37-same-work'),(True,'v37-same-work'),(True,'v35-relevance')):
            ctx=display_context('scope',mode,manual=manual)
            self.assertTrue(store.save_bestof_display_receipt(**lookup,context=ctx,run_mode=mode,
                 mode_receipt={'generation_id':'gen21','mode':mode,'manual_existing_fit_trial':manual},result={'status':'withheld'}))
            self.assertEqual(store.load_bestof_display_receipt(**lookup,context=ctx)['run_mode'],mode)
        history=store.list_bestof_mode_history(21,'gen21',self.audit['docx_sha256'])
        self.assertEqual(len(history),3);self.assertEqual(sum(r['Request']=='Build and Fit' for r in history),1)
        self.assertEqual(store.delete_bestof_display_receipts(21),4)
        self.assertEqual(self.run_trial()['_optimizer_cache']['status'],'fresh')

    def test_display_context_scopes_and_modes(self):
        inputs={k:self.kwargs[k] for k in ('application_id','audit','projects','fit','baseline_report','raw_jd_text','identity')}
        inputs['generation_id']='gen21'
        old=display_scope(**inputs)
        self.assertNotEqual(old,display_scope(**(inputs|{'identity':{'scoring_version':'new'}})))
        self.assertNotEqual(old,display_scope(**(inputs|{'projects':{}})))
        self.assertNotEqual(display_context(old,'v37-same-work'),display_context(old,'v37-same-work',manual=True))

    def test_cache_read_write_failure_does_not_block_fresh_trial(self):
        with patch.object(store,'load_bestof_display_receipt',side_effect=OSError('offline')),patch.object(store,'save_bestof_display_receipt',side_effect=OSError('offline')):
            result=self.run_trial();self.assertEqual(result['status'],'verified');self.assertFalse(result['_optimizer_cache']['persisted'])
        self.execute.assert_called_once()


class UIIntegrationTests(CacheFixture):
    # This exercises the real Streamlit orchestration with synthetic verified receipts.
    # The existing BestOfRelease tests independently exercise native DOCX scoring.
    def test_actual_ui_mode_switch_restart_force_and_history(self):
        from contextlib import ExitStack, nullcontext
        from unittest.mock import MagicMock
        from tailoring.phase9f_automatic_bestof_v30_ui import render_automatic_bestof, mark_fit_request
        st=MagicMock(); st.session_state={}; st.spinner.return_value=nullcontext(); st.expander.return_value=nullcontext()
        st.button.return_value=False
        st.checkbox.return_value=False
        projects=self.kwargs['projects']; fit=self.fit; report=self.report
        args=dict(application_id=21,generation_id='gen21',projects=projects,fit=fit,
                  baseline_report=report,raw_jd_text='Python',execution={},decision={},repo_root=self.root)
        with ExitStack() as stack:
            def p(target,**kw): return stack.enter_context(patch(target,**kw))
            p('tailoring.phase9f_project_bullet_sources_v2_3._bound_candidate_sources',return_value=([],''))
            p('tailoring.phase9f_final_evidence_comparison_v2_4.build_final_evidence_audit',return_value=self.audit)
            p('database.tailoring_generation_control.get_tailoring_generation',return_value=self.kwargs['generation'])
            p('tailoring.phase9f_optimizer_cache_v312b214b3.active_identity',return_value=self.kwargs['identity'])
            p('tailoring.phase9f_optimizer_cache_v312b214b3._runtime_identity',return_value=self.kwargs['runtime'])
            evaluate=p('tailoring.phase9f_automatic_bestof_v30.evaluate_auto',side_effect=lambda **kw:deepcopy(self.result))
            p('tailoring.phase9f_automatic_bestof_v30.verify_fitted_a_against_baselines',return_value=self.result['a_vs_starting'])
            p('tailoring.phase9f_v363_selection_receipts.build_bullet_selection_calculation',return_value={})
            p('tailoring.phase9f_v364_decision_explorer.render_compact_decision_explorer')
            p('tailoring.phase9f_independent_bullet_scores_v312b214b.build_independent_bullet_scores',return_value={'status':'unavailable'})
            p('tailoring.phase9f_automatic_bestof_v30_ui._render_source_comparison')
            mark_fit_request(st,21,'gen21',requested_mode='v37-same-work')
            render_automatic_bestof(st,**args); self.assertEqual(evaluate.call_count,1)
            for mode in ('v35-relevance','v37-same-work'):
                st.session_state['phase9f_bestof_next_mode_21']=mode
                st.button.side_effect=lambda label,**kw:label.startswith('Compare the existing')
                render_automatic_bestof(st,**args)
            self.assertEqual(evaluate.call_count,2)
            history=store.list_bestof_mode_history(21,'gen21',self.audit['docx_sha256'])
            self.assertEqual(len(history),3)
            self.assertEqual(sum(r['Request']=='Build and Fit' for r in history),1)
            self.assertEqual(history[0]['Execution'],'hit')
            st.session_state={}; st.button.side_effect=None; st.button.return_value=False
            render_automatic_bestof(st,**args); self.assertEqual(evaluate.call_count,2)
            self.assertEqual(st.session_state['phase9f_auto_bestof_run_mode_21']['mode'],'v37-same-work')
            st.button.side_effect=lambda label,**kw:label.startswith('Force fresh comparison')
            render_automatic_bestof(st,**args); self.assertEqual(evaluate.call_count,3)
            self.assertEqual(file_digest(self.a),self.audit['docx_sha256'])


if __name__=='__main__': unittest.main()

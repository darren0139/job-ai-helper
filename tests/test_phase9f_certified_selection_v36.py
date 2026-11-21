"""V3.6 exact proxy, fallback, no-regression gate, and multi-project read-only UI."""
from __future__ import annotations
from contextlib import contextmanager
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch
import json
import tempfile
import unittest

from tests.test_phase9f_jd_relevance_optimizer_v35 import stronger_library_fixture
from tests.test_phase9f_evidence_optimizer_v33 import fixture as ncs_fixture, evaluator as ncs_evaluator
from tests.test_phase9f_v34_candidate_identity_fix import fixture as v34_identity_fixture
from tailoring.phase9f_certified_selection_v36 import (
    build_certified_optimization, selected_base_floor_gate, VERSION,
)
from tailoring.phase9f_multi_project_evidence_v36 import comparison_rows,render_multi_project_evidence
from tailoring.phase9f_automatic_bestof_v30 import evaluate_auto


class CertifiedOptimization(unittest.TestCase):
    def test_exact_model_ranks_more_relevant_library_bullet(self):
        audit,projects,evaluator,base,library=stronger_library_fixture()
        original=deepcopy((audit,projects))
        r=build_certified_optimization(audit,projects,evaluator=evaluator)
        self.assertEqual(r['status'],'candidate',r)
        cert=r['mathematical_certificate']
        self.assertEqual(cert['status'],'optimal_proxy')
        self.assertEqual(cert['optimality_gap'],0)
        self.assertEqual(len(cert['phase_receipts']),4)
        self.assertEqual(r['projects'][0]['after'],[library])
        self.assertEqual(r['gained_jd_ids'],[])
        self.assertEqual(r['lost_jd_ids'],[])
        self.assertEqual(cert['constraints']['each_project_min_bullets'],1)
        self.assertEqual((audit,projects),original)
        self.assertIsNot(r,r['candidate_variants'][0])
        self.assertTrue(all('candidate_variants' not in v for v in r['candidate_variants']))
        json.dumps(r)

    def test_ncs_style_preserves_grounded_links_and_project_breadth(self):
        audit,projects=ncs_fixture()
        r=build_certified_optimization(audit,projects,evaluator=ncs_evaluator)
        self.assertEqual(r['status'],'candidate',r)
        for item in r['candidate_variants']:
            self.assertEqual(item['lost_jd_ids'],[])
            self.assertTrue(item['project_set_unchanged'])
            self.assertGreaterEqual(item['proposed_bullet_count'],item['baseline_bullet_count']-2)
            self.assertLessEqual(item['proposed_bullet_count'],item['baseline_bullet_count']+2)
            self.assertEqual(len(item['projects']),len(audit['projects']))
            self.assertTrue(all(row['after_count']>=1 for row in item['projects']))
            self.assertTrue(all(r['native_score_delta_if_removed']=='not_measured'
                                for r in item['relevance_diagnostics']['ablation_preview']))

    def test_solver_unavailable_is_labelled_fallback_not_optimal(self):
        audit,projects,evaluator,_,_=stronger_library_fixture()
        with patch('tailoring.phase9f_certified_selection_v36._solve',side_effect=RuntimeError('not installed')):
            r=build_certified_optimization(audit,projects,evaluator=evaluator)
        self.assertEqual(r['mathematical_certificate']['status'],'not_proven')
        self.assertIsNone(r['mathematical_certificate']['optimality_gap'])
        self.assertIn('not installed',r['mathematical_certificate']['reason'])

    def test_base_floor_gate_cannot_promote_unknown_or_regressed_starting(self):
        result={'status':'verified','winner':'optimized_candidate','a_score':31,'b_score':35,
                'delta':4,'reason':'Higher actual score against A.',
                'a_docx_sha256':'hash-a', 'scoring_version':'test-native-v1'}
        before=deepcopy(result)
        missing=selected_base_floor_gate(result,{'status':'verified',
             'selected_base_comparison_status':'unavailable',
             'a_docx_sha256':'hash-a','a_score':31,'scoring_version':'test-native-v1'})
        self.assertEqual(missing['winner'],'existing_final')
        self.assertEqual(missing['base_floor_verdict'],'not_proven')
        self.assertEqual(missing['b_score'],35)
        regressed=selected_base_floor_gate(result,{'status':'verified',
             'selected_base_comparison_status':'regressed',
             'a_docx_sha256':'hash-a','a_score':31,'scoring_version':'test-native-v1'})
        self.assertEqual(regressed['winner'],'existing_final')
        good=selected_base_floor_gate(result,{'status':'verified',
             'selected_base_comparison_status':'maintained',
             'selected_base_required_core_losses':[],
             'a_docx_sha256':'hash-a','a_score':31,'scoring_version':'test-native-v1'})
        self.assertEqual(good['winner'],'optimized_candidate')
        self.assertEqual(good['base_floor_verdict'],'passed_by_transitivity')
        self.assertEqual(result,before)
        self.assertEqual(selected_base_floor_gate(missing,{}),missing)
        stale=selected_base_floor_gate(result,{'status':'verified',
            'selected_base_comparison_status':'improved','selected_base_required_core_losses':[],
            'a_docx_sha256':'other-docx','a_score':31,'scoring_version':'test-native-v1'})
        self.assertEqual(stale['base_floor_verdict'],'not_proven')
        self.assertIn('different',stale['base_floor_reason'])

    def test_real_generated_math_shortlist_reaches_native_scoring(self):
        audit,projects,evaluator,base,library=stronger_library_fixture()
        proposal=build_certified_optimization(audit,projects,evaluator=evaluator)
        self.assertEqual(proposal['status'],'candidate')
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);folder=root/'outputs'/'tailored_resumes';folder.mkdir(parents=True)
            a=folder/'app_156_a.docx';a.write_bytes(b'original')
            digest=sha256(a.read_bytes()).hexdigest()
            generation,_,_=v34_identity_fixture(version=proposal['version'])
            generation['fit_result']['docx_path']=str(a)
            generation['fit_result']['tailored_projects_used']['recommended_projects']=[
                {'title':'API tests','draft_bullets':[base]}]
            events=[]
            def render(**kwargs):
                events.append(kwargs)
                out=folder/'optimizations';out.mkdir(exist_ok=True)
                doc=out/f'b{len(events)}.docx';doc.write_bytes(b'changed')
                pdf=out/f'b{len(events)}.pdf';pdf.write_bytes(b'%PDF-1.4')
                return {'status':'generated','pages':1,'docx_path':str(doc),'pdf_path':str(pdf)}
            def score(**kwargs):
                is_b=Path(kwargs['docx_path'])!=a
                return {'actual_docx_evidence':True,'docx_sha256':kwargs['expected_sha256'],
                    'claim_review_required_count':0,'scoring_version':'native-test',
                    'deterministic_alignment_score':35 if is_b else 31,
                    'canonical_requirements':[{'requirement_id':'reqtest','importance':'core',
                    'match_label':'direct'}]}
            result=evaluate_auto(audit={'verified':True,'generation_id':generation['generation_id'],
                'docx_sha256':digest},projects=projects,fit=generation['fit_result'],
                generation=generation,baseline_report={'raw_jd_text':'JD','stable_analysis':{
                    'canonical_requirements':[{'requirement_id':'reqtest','importance':'core'}]}},
                raw_jd_text='JD',source_docx=a,repo_root=root,application_id=156,
                optimizer=lambda _a,_p:deepcopy(proposal),generator=render,scorer=score)
            self.assertEqual(result['status'],'verified',result)
            self.assertEqual(result['winner'],'optimized_candidate')
            self.assertEqual(len(events),1)
            self.assertEqual(a.read_bytes(),b'original')
            json.dumps(result['proposal'])


class MultiProjectTable(unittest.TestCase):
    def fixture(self):
        return {'verified':True,'projects':[
            {'project':'One','base':[{'text':'base one'}],
             'library':[{'text':'lib one'}],
             'final':[{'text':'lib one','exact_library':True}], 'changes':[]},
            {'project':'Two','base':[{'text':'base two'}],
             'library':[{'text':'lib two'}],
             'final':[{'text':'base two','exact_base':True}], 'changes':[]},
            {'project':'Three','base':[],'library':[],'final':[], 'changes':[]} ]}

    def test_table_counts_and_refuses_unverified_source(self):
        audit=self.fixture()
        self.assertEqual(len(comparison_rows(audit)),3)
        self.assertEqual(comparison_rows({'verified':False,'projects':audit['projects']}),[])
        self.assertFalse(any(x['Inspect'] for x in comparison_rows(audit)))

    def test_checkbox_table_inspects_two_at_once_and_never_mutates_receipt(self):
        class Fake:
            def __init__(self):
                self.session_state={};self.headings=[];self.entries=[];self.checkbox_keys=[]
            def markdown(self,s):self.headings.append(s)
            def caption(self,s):self.entries.append(s)
            def checkbox(self,label,*,key):
                self.checkbox_keys.append(key)
                return self.session_state.setdefault(key,False)
            def columns(self,widths):return [self._Column(self) for _ in (range(widths) if isinstance(widths,int) else widths)]
            class _Column:
                def __init__(self,owner):self.owner=owner
                def __enter__(self):return self
                def __exit__(self,*_):return False
                def markdown(self,s):self.owner.headings.append(s)
                def write(self,s):self.owner.entries.append(str(s))
                def checkbox(self,label,*,key,label_visibility):
                    self.owner.checkbox_keys.append(key)
                    return self.owner.session_state.setdefault(key,False)
            def write(self,s):self.entries.append(s)
            def dataframe(self,*args,**kwargs):pass
            @contextmanager
            def expander(self,*args,**kwargs):yield
        f=Fake();audit=self.fixture();original=deepcopy(audit)
        summary_key='phase9f_v36_multi_projects_156_abc'
        render_multi_project_evidence(f,application_id=156,generation_id='abc',final_audit=audit)
        self.assertEqual(f.session_state[summary_key],[])
        self.assertEqual(len(f.checkbox_keys),3)
        first,second,_=f.checkbox_keys[:3]
        # Each click changes widget-owned state once. The immediate rerun must
        # display the change without a data-editor focus or a second click.
        f.session_state[first]=True
        f.session_state[second]=True
        render_multi_project_evidence(f,application_id=156,generation_id='abc',final_audit=audit)
        self.assertEqual(f.session_state[summary_key],['One','Two'])
        self.assertIn('lib one',str(f.entries))
        self.assertIn('base two',str(f.entries))
        f.session_state[first]=False
        render_multi_project_evidence(f,application_id=156,generation_id='abc',final_audit=audit)
        self.assertEqual(f.session_state[summary_key],['Two'])
        self.assertEqual(audit,original)


if __name__=='__main__':unittest.main()

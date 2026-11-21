"""Safe automatic A/B comparator and action-trigger contract; no file writes outside tmp."""
from __future__ import annotations
import copy,hashlib,math,tempfile,unittest
from pathlib import Path
from tailoring.phase9f_automatic_bestof_v30 import compare_document_candidates,evaluate_auto,hold

A='a'*64;B='b'*64

def scoring(score,sha=A,hard='direct',preferred='none',claims=0):
    return {'actual_docx_evidence':True,'docx_sha256':sha,'scoring_version':'stable-evidence-v1.16-phase6d20',
            'deterministic_alignment_score':score,'claim_review_required_count':claims,
            'canonical_requirements':[{'requirement_id':'r1','importance':'core','match_label':hard},
                                      {'requirement_id':'r2','importance':'preferred','match_label':preferred}]}
class Comparison(unittest.TestCase):
    def test_higher_actual_score_wins(self):
        r=compare_document_candidates(candidate_a=scoring(32),candidate_b=scoring(45,sha=B))
        self.assertEqual(r['winner'],'optimized_candidate');self.assertFalse(r['initial_improvement_verified'])
    def test_tie_preserves_a(self):
        self.assertEqual(compare_document_candidates(candidate_a=scoring(40),candidate_b=scoring(40,B))['winner'],'existing_final')
    def test_lower_preserves_a(self):
        self.assertEqual(compare_document_candidates(candidate_a=scoring(40),candidate_b=scoring(36,B))['winner'],'existing_final')
    def test_core_regression_blocks_better_total(self):
        self.assertEqual(compare_document_candidates(candidate_a=scoring(40),candidate_b=scoring(60,B,hard='weak'))['winner'],'existing_final')
    def test_preferred_loss_not_core(self):
        r=compare_document_candidates(candidate_a=scoring(40,preferred='direct'),candidate_b=scoring(51,B,preferred='none'))
        self.assertEqual(r['winner'],'optimized_candidate')
    def test_mismatch_blocks_and_no_global_claim(self):
        b=scoring(44,B);b['canonical_requirements'][1]['requirement_id']='foreign'
        self.assertEqual(compare_document_candidates(candidate_a=scoring(35),candidate_b=b)['status'],'withheld')
    def test_claim_review_blocks(self):
        self.assertEqual(compare_document_candidates(candidate_a=scoring(35),candidate_b=scoring(45,B,claims=1))['status'],'withheld')
    def test_unknown_match_nan_version_and_missing_authority_block(self):
        for change in [('deterministic_alignment_score',math.nan),('deterministic_alignment_score',True),
                       ('scoring_version',''),('actual_docx_evidence',False)]:
            b=scoring(50,B);b[change[0]]=change[1]
            self.assertEqual(compare_document_candidates(candidate_a=scoring(35),candidate_b=b)['status'],'withheld')
    def test_input_not_mutated(self):
        a=scoring(30);b=scoring(42,B);original=copy.deepcopy((a,b));compare_document_candidates(candidate_a=a,candidate_b=b)
        self.assertEqual(original,(a,b))

class Runner(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.output=self.root/'outputs/tailored_resumes';self.output.mkdir(parents=True)
        self.source=self.output/'app_12_fitted.docx';self.source.write_bytes(b'source content')
        self.a_hash=hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.generation={'generation_id':'g1234','fit_result':{'fit_one_page':True,'docx_path':str(self.source),
             'tailored_projects_used':{'recommended_projects':[{'title':'P','draft_bullets':['Original bullet']}]}}}
        self.audit={'verified':True,'generation_id':'g1234','docx_sha256':self.a_hash}
        self.fit=self.generation['fit_result']
        self.baseline={'raw_jd_text':'Qualifications: C++',
             'stable_analysis':{'canonical_requirements':[{'requirement_id':'r1'}, {'requirement_id':'r2'}]}}
        self.projects={'recommended_projects':[{'title':'P'}]}
        self.proposal={'status':'candidate','version':'v26','requires_base_review':False,
           'projects':[{'project':'P','before':['Original bullet'],'after':['New bullet'],
                        'sources':[['Evidence Library']],'supported_jd_ids':[['r1']]}]}
        self.calls=[]
    def run_it(self, *, proposal=None, scorer=None, generator=None, **kwargs):
        def create(*, source_docx, audit_sha, proposal, repo_root, application_id, generation_id):
            self.calls.append('generate')
            folder=self.output/'optimizations';folder.mkdir(exist_ok=True)
            b=folder/'app_12_challenger.docx';b.write_bytes(b'new content')
            pdf=folder/'app_12_challenger.pdf';pdf.write_bytes(b'PDF')
            return {'status':'generated','docx_path':str(b),'pdf_path':str(pdf),'pages':1}
        def rank(a,p):return copy.deepcopy(self.proposal if proposal is None else proposal)
        def score(*,docx_path,generation_state,baseline_report,raw_jd_text,expected_sha256):
            self.calls.append('score')
            return scoring(40 if Path(docx_path)==self.source else 52,expected_sha256)
        return evaluate_auto(audit=copy.deepcopy(self.audit),projects=copy.deepcopy(self.projects),
                fit=copy.deepcopy(self.fit),generation=copy.deepcopy(self.generation),
                baseline_report=copy.deepcopy(self.baseline),raw_jd_text='Qualifications: C++',
                source_docx=self.source,repo_root=self.root,application_id=12,
                optimizer=rank,generator=generator or create,scorer=scorer or score,**kwargs)
    def test_real_one_click_flow(self):
        result=self.run_it()
        self.assertEqual(result['status'],'verified',result)
        self.assertEqual(result['winner'],'optimized_candidate')
        self.assertEqual(self.calls,['score','generate','score'])
        self.assertEqual(self.source.read_bytes(),b'source content')
        self.assertFalse(result['candidate_approved'])
    def test_missing_initial_does_not_block_actual_a_b(self):
        self.baseline['meta']={'reconstructed_legacy':True}
        result=self.run_it()
        self.assertEqual(result['winner'],'optimized_candidate')
        self.assertFalse(result['initial_improvement_verified'])
    def test_requires_review_no_generator(self):
        p={**self.proposal,'requires_base_review':True}
        self.assertEqual(self.run_it(proposal=p)['status'],'needs_review')
        self.assertEqual(self.calls,[])
    def test_no_candidate_no_generator(self):
        source={'status':'no_proxy_gain','reason':'none',
                'source_comparison':{'projects':[{'project':'P','candidates':[]}]}}
        result=self.run_it(proposal=source)
        self.assertEqual(result['status'],'no_challenger')
        self.assertEqual(result['proposal'],source)
        self.assertEqual(self.calls,[])
    def test_foreign_source_hash_or_generation_hold(self):
        self.generation['generation_id']='foreign'
        self.assertEqual(self.run_it()['status'],'withheld')
        self.generation['generation_id']='g1234'
        self.audit['docx_sha256']='f'*64
        self.assertEqual(self.run_it()['status'],'withheld')
        self.assertEqual(self.calls,[])
    def test_different_frozen_jd_hold(self):
        self.baseline['raw_jd_text']='This is a different JD'
        self.assertEqual(self.run_it()['status'],'withheld')
        self.assertEqual(self.calls,[])
    def test_generator_fails_safely(self):
        def bad(**kwargs):raise RuntimeError('rendering blocked')
        self.assertEqual(self.run_it(generator=bad)['winner'],'existing_final')
        self.assertEqual(self.source.read_bytes(),b'source content')
    def test_native_frozen_requirement_set_guard(self):
        def scorer(**kwargs):
            result=scoring(33,kwargs['expected_sha256']);result['canonical_requirements'].append({'requirement_id':'foreign','importance':'core','match_label':'direct'})
            return result
        self.assertEqual(self.run_it(scorer=scorer)['status'],'withheld')
    def test_no_input_mutation(self):
        old=copy.deepcopy((self.audit,self.projects,self.fit,self.generation,self.baseline))
        self.run_it()
        self.assertEqual((self.audit,self.projects,self.fit,self.generation,self.baseline),old)


class SourceComparisons(unittest.TestCase):
    def test_legacy_no_document_initial_unavailable(self):
        from tailoring.phase9f_automatic_bestof_v30 import compare_verified_starting_analyses
        x=compare_verified_starting_analyses(baseline_report={'stable_analysis':{}},raw_jd_text='X',chosen_document_score=scoring(51))
        self.assertEqual(x['initial_comparison_status'],'unavailable')
        self.assertFalse(x['initial_improvement_verified'])
    def test_valid_initial_and_selected_base_separately(self):
        from tailoring.phase9f_automatic_bestof_v30 import compare_verified_starting_analyses
        from unittest.mock import patch
        from types import ModuleType
        import sys
        doc=ModuleType('tailoring.document_grounded_analysis')
        doc.validate_document_report=lambda report:{'identity':'jd_scope'}
        initial={'stable_analysis':{**scoring(30),'scoring_version':'stable-evidence-v1.16-phase6d20'}}
        selected={'same_as_initial':False,'stable_analysis':{**scoring(60)}}
        doc.selected_base_analysis=lambda report:selected
        jid=ModuleType('tailoring.job_match_ab_analysis');jid.current_ab_identity=lambda jd:'jd_scope'
        with patch.dict(sys.modules, {'tailoring.document_grounded_analysis':doc,'tailoring.job_match_ab_analysis':jid}):
            got=compare_verified_starting_analyses(baseline_report=initial,raw_jd_text='X',chosen_document_score=scoring(50))
        self.assertEqual(got['initial_comparison_status'],'improved',got)
        self.assertEqual(got['selected_base_comparison_status'],'regressed',got)
        self.assertTrue(got['initial_improvement_verified'])
        self.assertFalse(got['selected_base_improvement_verified'])
    def test_baseline_core_loss_is_not_improved(self):
        from tailoring.phase9f_automatic_bestof_v30 import compare_verified_starting_analyses
        from unittest.mock import patch
        from types import ModuleType
        import sys
        doc=ModuleType('tailoring.document_grounded_analysis')
        doc.validate_document_report=lambda r:{'identity':'jd_scope'}
        doc.selected_base_analysis=lambda r:{'same_as_initial':True}
        jid=ModuleType('tailoring.job_match_ab_analysis');jid.current_ab_identity=lambda jd:'jd_scope'
        initial={'stable_analysis':scoring(30,hard='direct')}
        with patch.dict(sys.modules, {'tailoring.document_grounded_analysis':doc,'tailoring.job_match_ab_analysis':jid}):
            got=compare_verified_starting_analyses(baseline_report=initial,raw_jd_text='X',chosen_document_score=scoring(50,hard='weak'))
        self.assertEqual(got['initial_comparison_status'],'regressed')
        self.assertFalse(got['initial_improvement_verified'])

class ExplicitActionIntegration(unittest.TestCase):
    def test_button_sets_pending_generation_and_snapshots_optimizer_mode(self):
        from tailoring.phase9f_automatic_bestof_v30_ui import mark_fit_request
        class UI:pass
        st=UI();st.session_state={}
        mark_fit_request(st,20,'g_123')
        expected={'phase9f_auto_bestof_pending_20':'g_123',
                  'phase9f_auto_bestof_run_mode_20':{'generation_id':'g_123','mode':'v35-relevance'}}
        self.assertEqual(st.session_state,expected)
        mark_fit_request(st,20,'')
        self.assertEqual(st.session_state,expected)
    def test_expected_app_integration_anchors(self):
        from pathlib import Path
        import os
        root=Path(__file__).resolve().parents[1]
        app=(root/'app.py').read_text(encoding='utf-8')
        self.assertEqual(app.count('mark_fit_request(st, int(current_application_id)'),3)
        self.assertEqual(app.count('render_automatic_bestof('),1)
        self.assertNotIn('render_verified_best_of(',app)


class NativeDocumentAdapter(unittest.TestCase):
    def test_actual_docx_bytes_and_reconciled_scorer_uses_both_files(self):
        from tailoring.phase9f_automatic_bestof_v30 import native_document_score
        from types import ModuleType
        from unittest.mock import patch
        import sys
        with tempfile.TemporaryDirectory() as d:
            doc=Path(d)/'fitted.docx';doc.write_bytes(b'actual document data')
            digest=hashlib.sha256(doc.read_bytes()).hexdigest()
            parse=ModuleType('parse')
            parse.read_resume_docx=lambda p,**kw:'Actual document bullet with Python experience'
            grounded=ModuleType('tailoring.document_grounded_analysis')
            called=[]
            def analyze(**kwargs):
                called.append(kwargs)
                return {'stable_analysis':{'scoring_version':'stable-evidence-v1.16-phase6d20',
                   'canonical_requirements':[{'requirement_id':'r1','importance':'core','match_label':'direct',
                                               'match_value':1,'evidence_strength':3,'evidence':[]}]}}
            grounded.analyze_actual_resume_against_jd=analyze
            overrides=ModuleType('tailoring.jd_user_input_overrides')
            overrides.apply_application_session_jd_user_inputs=lambda item,**kw:item
            phase8=ModuleType('tailoring.phase8_verification')
            phase8.build_final_resume_profile=lambda profile,state: {'projects':[{'title':'P'}]}
            phase8.audit_claim_lineage=lambda profile,state:{'claim_review_required_count':0}
            reconciliation=ModuleType('tailoring.phase8_requirement_reconciliation')
            reconciliation.reconcile_final_requirement_matches=lambda **kw:(copy.deepcopy(kw['after_analysis']),{})
            seeds=ModuleType('tailoring.final_scoring_seed')
            seeds.build_final_scoring_seed=lambda after:{'aggregate':{}}
            scorelib=ModuleType('analysis_stability.stable_evidence_scoring')
            scorelib.compute_deterministic_alignment=lambda rows:{'deterministic_alignment_score':58}
            mods={'parse':parse,'tailoring.document_grounded_analysis':grounded,
                  'tailoring.jd_user_input_overrides':overrides,
                  'tailoring.phase8_verification':phase8,
                  'tailoring.phase8_requirement_reconciliation':reconciliation,
                  'tailoring.final_scoring_seed':seeds,
                  'analysis_stability.stable_evidence_scoring':scorelib}
            report={'raw_jd_text':'Require Python','resume_profile':{},'jd_profile':{},
                    'stable_analysis':{'canonical_requirements':[{'requirement_id':'r1','importance':'core','match_label':'none'}]}}
            with patch.dict(sys.modules,mods):
                result=native_document_score(docx_path=doc,generation_state={'fit_result':{}},
                    baseline_report=report,raw_jd_text='Require Python',expected_sha256=digest)
            self.assertEqual(len(called),1)
            self.assertEqual(called[0]['resume_text'],'Actual document bullet with Python experience')
            self.assertEqual(result['deterministic_alignment_score'],58)
            self.assertEqual(result['docx_sha256'],digest)
    def test_changed_document_refused_before_parser(self):
        from tailoring.phase9f_automatic_bestof_v30 import native_document_score
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'fitted.docx';f.write_bytes(b'A')
            with self.assertRaisesRegex(ValueError,'digest differs'):
                native_document_score(docx_path=f,generation_state={},baseline_report={},
                    raw_jd_text='JD',expected_sha256='wrong')

"""V3.5 selection and actual-document shortlist boundaries; V2.6 remains intact."""
from __future__ import annotations
from copy import deepcopy
import json
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest
from tailoring.phase9f_jd_relevance_optimizer_v35 import (
    VERSION, MAX_TRIALS, build_jd_relevance_optimization)
from tailoring.phase9f_verified_best_of_v291 import build_candidate_scoring_state
from tailoring.phase9f_automatic_bestof_v30 import evaluate_auto
from tests.phase9f_public_optimizer_fixture import fixture as v33_fixture, evaluator as v33_evaluator
from tests.test_phase9f_v34_candidate_identity_fix import fixture as v34_identity_fixture


def stronger_library_fixture():
    base='Built tests for software projects.'
    library='Implemented Python unit and integration tests for API services.'
    audit={'verified':True,'projects':[{'project':'API tests','base':[{'text':base}],
        'library':[{'text':library}],'final':[{'text':base}]}]}
    projects={'candidate_project_ranking':[{'title':'API tests','requirement_matches':[
        {'requirement_id':'reqtest','importance':'core','match_label':'direct',
         'coverage_points':9,'requirement_text':'Execute Python unit and integration testing'}]}]}
    def evaluator(*,bullets,ranking_row):
        return [{'bullet_index':i,'bullet_text':t,'supported_requirement_ids':['reqtest']}
                for i,t in enumerate(bullets)]
    return audit,projects,evaluator,base,library


class RelevanceSelection(unittest.TestCase):
    def test_actual_generated_shortlist_is_acyclic_and_json_exportable(self):
        audit, projects, evaluator, base, library = stronger_library_fixture()
        proposal = build_jd_relevance_optimization(audit, projects, evaluator=evaluator)
        self.assertEqual(proposal['status'], 'candidate')
        variants = proposal['candidate_variants']
        self.assertTrue(1 <= len(variants) <= MAX_TRIALS)
        self.assertIsNot(proposal, variants[0])
        self.assertTrue(all('candidate_variants' not in item for item in variants))
        self.assertEqual(variants[0]['projects'], proposal['projects'])
        self.assertEqual(json.loads(json.dumps({'proposal': proposal}))['proposal']['version'], VERSION)
        self.assertEqual(proposal['shortlist_size'], len(variants))

    def test_stale_v350_self_reference_is_exported_without_mutating_state(self):
        from tailoring.phase9f_automatic_bestof_v30_ui import _render_source_comparison
        class FakeUI:
            def __init__(self): self.download = None; self.errors = []
            def markdown(self, *_args, **_kwargs): pass
            def caption(self, *_args, **_kwargs): pass
            def dataframe(self, *_args, **_kwargs): pass
            def error(self, message): self.errors.append(message)
            def download_button(self, _label, *, data, **_kwargs): self.download = json.loads(data)
            @contextmanager
            def expander(self, *_args, **_kwargs): yield
        proposal = {'version': VERSION, 'status': 'candidate', 'projects': []}
        proposal['candidate_variants'] = [proposal]
        ui = FakeUI()
        _render_source_comparison(ui, application_id=156, context='old-cached',
            run_mode='v35-relevance', result={'proposal':proposal, 'status':'withheld',
            'reason':'Invalid V3.5 bounded independent trial shortlist.'},
            audit={'generation_id':'g', 'docx_sha256':'hash', 'projects':[]}, projects={})
        self.assertEqual(ui.errors, [])
        self.assertEqual(ui.download['comparison_status'], 'withheld')
        self.assertEqual(len(ui.download['proposal']['candidate_variants']), 1)
        self.assertNotIn('candidate_variants', ui.download['proposal']['candidate_variants'][0])
        self.assertIs(proposal['candidate_variants'][0], proposal)

    def test_source_wording_with_more_grounded_jd_terms_is_tested(self):
        audit,projects,evaluator,base,lib=stronger_library_fixture()
        stored=deepcopy((audit,projects))
        got=build_jd_relevance_optimization(audit,projects,evaluator=evaluator)
        self.assertEqual(got['status'],'candidate',got)
        self.assertIn(lib,got['projects'][0]['after'])
        self.assertNotIn(base,got['projects'][0]['after'])
        self.assertEqual(got['baseline_points'],got['proposed_points'])
        self.assertGreater(got['relevance_diagnostics']['candidate_advisory_relevance'],
                           got['relevance_diagnostics']['baseline_advisory_relevance'])
        self.assertTrue({'python','unit'} <= set(got['relevance_diagnostics']['new_jd_cues']))
        self.assertFalse(got['selection_receipt']['verified_fitting_explanation'])
        self.assertEqual((audit,projects),stored)

    def test_app156_style_duplicate_is_not_allowed_to_strip_project_breadth(self):
        audit,projects=v33_fixture()
        result=build_jd_relevance_optimization(audit,projects,evaluator=v33_evaluator)
        self.assertEqual(result['status'],'candidate',result)
        variants=result.get('candidate_variants') or [result]
        self.assertTrue(1<=len(variants)<=MAX_TRIALS)
        for v in variants:
            self.assertGreaterEqual(v['proposed_bullet_count'],v['baseline_bullet_count']-2)
            self.assertLessEqual(v['proposed_bullet_count'],v['baseline_bullet_count']+2)
            self.assertEqual(v['lost_jd_ids'],[])
            self.assertTrue({'rconfig','rtest'} <= set(v['protected_baseline_jd_ids']))
            self.assertTrue(v['project_set_unchanged'])
            self.assertEqual(v['version'],VERSION)

    def test_actual_v35_source_bound_docx_writer_changes_only_project_bullets(self):
        from docx import Document
        from tailoring.phase9f_joint_resume_optimizer_v2_6 import write_optimized_docx
        audit,projects,evaluator,base,lib=stronger_library_fixture()
        proposal=build_jd_relevance_optimization(audit,projects,evaluator=evaluator)
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'source.docx';dest=Path(tmp)/'v35.docx'
            doc=Document()
            doc.add_paragraph('EXPERIENCE');doc.add_paragraph('Untouched employment facts')
            doc.add_paragraph('PROJECTS');doc.add_paragraph('API tests | Python')
            doc.add_paragraph('• '+base)
            doc.add_paragraph('SKILLS');doc.add_paragraph('Python, SQL')
            doc.save(source)
            raw=source.read_bytes()
            write_optimized_docx(source_path=source,audit_sha=sha256(raw).hexdigest(),
                                 proposal=proposal,destination=dest)
            result=[row.text for row in Document(dest).paragraphs]
            self.assertIn('• '+lib,result)
            self.assertNotIn('• '+base,result)
            self.assertEqual(result[-2:],['SKILLS','Python, SQL'])
            self.assertEqual(source.read_bytes(),raw)

    def test_only_v35_and_v26_are_user_facing(self):
        from tailoring.phase9f_automatic_bestof_v30_ui import (
            ACTIVE_MODES,LEGACY_MODES,render_optimizer_mode_selector,configured_mode)
        class FakeUI:
            def __init__(self):self.session_state={};self.options=[]
            def radio(self,label,options,**kwargs):self.options.append(tuple(options))
            def caption(self,msg):pass
        ui=FakeUI()
        self.assertEqual(render_optimizer_mode_selector(ui,156),'v35-relevance')
        self.assertEqual(ui.options,[('v35-relevance','v26-fixed')])
        self.assertEqual(set(LEGACY_MODES),{'v31-flexible','v33-evidence'})
        ui.session_state['phase9f_bestof_next_mode_156']='v33-evidence'
        self.assertEqual(render_optimizer_mode_selector(ui,156),'v35-relevance')
        ui.session_state['phase9f_bestof_next_mode_156']='v26-fixed'
        self.assertEqual(configured_mode(ui,156),'v26-fixed')

    def test_forged_or_unverified_input_fails_closed(self):
        audit,projects,evaluator,base,lib=stronger_library_fixture()
        audit['verified']=False
        self.assertEqual(build_jd_relevance_optimization(audit,projects,evaluator=evaluator)['status'],'withheld')
        audit['verified']=True
        self.assertEqual(build_jd_relevance_optimization(audit,projects,evaluator=evaluator,max_trials=99)['status'],'withheld')

    def test_v35_variable_count_state_keeps_original_immutable(self):
        original,proposal,output=v34_identity_fixture(version=VERSION)
        before=deepcopy(original)
        changed=build_candidate_scoring_state(original=original,proposal=proposal,output=output)
        self.assertEqual(original,before)
        self.assertEqual(len(changed['fit_result']['tailored_projects_used']['recommended_projects'][1]['draft_bullets']),3)
        self.assertFalse(changed['fit_result']['candidate_is_approved'])
        original,proposal,output=v34_identity_fixture(version='forged')
        with self.assertRaisesRegex(ValueError,'ownership authority'):
            build_candidate_scoring_state(original=original,proposal=proposal,output=output)


class NativeShortlist(unittest.TestCase):
    def test_actual_generated_shortlist_reaches_native_scoring(self):
        audit, projects, evaluator, base, library = stronger_library_fixture()
        proposal = build_jd_relevance_optimization(audit, projects, evaluator=evaluator)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            folder = root/'outputs'/'tailored_resumes'
            folder.mkdir(parents=True)
            a = folder/'app_156_a.docx'
            a.write_bytes(b'original')
            asha = sha256(a.read_bytes()).hexdigest()
            g, _, _ = v34_identity_fixture(version=VERSION)
            g['fit_result']['docx_path'] = str(a)
            g['fit_result']['tailored_projects_used']['recommended_projects'] = [
                {'title':'API tests', 'draft_bullets':[base]}]
            checked = {'render':0,'scored_b':0}
            def generator(**kwargs):
                checked['render'] += 1
                out = folder/'optimizations'
                out.mkdir(exist_ok=True)
                docx = out/f'candidate_{checked["render"]}.docx'
                pdf = out/f'candidate_{checked["render"]}.pdf'
                docx.write_bytes(b'candidate'); pdf.write_bytes(b'%PDF-1.4')
                return {'status':'generated', 'pages':1, 'docx_path':str(docx),
                        'pdf_path':str(pdf)}
            def scorer(**kwargs):
                is_b = Path(kwargs['docx_path']) != a
                if is_b:
                    checked['scored_b'] += 1
                    state = kwargs['generation_state']
                    self.assertEqual(state['fit_result']['tailored_projects_used']
                                     ['recommended_projects'][0]['draft_bullets'], [library])
                return {'actual_docx_evidence':True,
                        'docx_sha256':kwargs['expected_sha256'],
                        'claim_review_required_count':0,
                        'scoring_version':'test-native-v1',
                        'deterministic_alignment_score':35 if is_b else 31,
                        'canonical_requirements':[{'requirement_id':'reqtest',
                            'importance':'core', 'match_label':'direct'}]}
            result=evaluate_auto(audit={'verified':True, 'generation_id':g['generation_id'],
                    'docx_sha256':asha},projects=projects,fit=g['fit_result'],generation=g,
                baseline_report={'raw_jd_text':'JD', 'stable_analysis':{
                    'canonical_requirements':[{'requirement_id':'reqtest', 'importance':'core'}]}},
                raw_jd_text='JD', source_docx=a, repo_root=root, application_id=156,
                optimizer=lambda _a,_p:deepcopy(proposal), generator=generator, scorer=scorer)
            self.assertEqual(result['status'],'verified',result)
            self.assertEqual(result['winner'],'optimized_candidate')
            self.assertGreaterEqual(checked['render'], 1)
            self.assertGreaterEqual(checked['scored_b'], 1)
            self.assertEqual(result['v35_tested_candidates'], len(proposal['candidate_variants']))
            json.dumps({'proposal':result['proposal'],'v35_trial_receipts':result['v35_trial_receipts']})
            self.assertEqual(a.read_bytes(), b'original')

    def test_multiple_real_scored_candidates_choose_highest_verified_delta(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);folder=root/'outputs'/'tailored_resumes';folder.mkdir(parents=True)
            a=folder/'app_156_a.docx';a.write_bytes(b'original');asha=sha256(a.read_bytes()).hexdigest()
            g,p,_=v34_identity_fixture(version=VERSION)
            g['fit_result']['docx_path']=str(a)
            fit=g['fit_result'];audit={'verified':True,'generation_id':g['generation_id'],'docx_sha256':asha}
            p2=deepcopy(p);p2['projects'][1]['after']=list(p2['projects'][1]['before'])
            p2['projects'][1]['after'][1]='Updated source-grounded candidate'
            p2['projects'][1]['after_count']=len(p2['projects'][1]['after'])
            # Do not alter starting identity or allowed version; this is a
            # controlled runner test. Real writer independently checks source.
            rootproposal=deepcopy(p)
            rootproposal['candidate_variants']=[deepcopy(p),p2]
            invoked=[]
            def generator(**kwargs):
                i=len(invoked)+1;invoked.append(kwargs['proposal'])
                path=folder/'optimizations';path.mkdir(exist_ok=True)
                doc=path/f'app_156_b{i}.docx';doc.write_bytes(f'candidate{i}'.encode())
                pdf=path/f'app_156_b{i}.pdf';pdf.write_bytes(b'pdf')
                return {'status':'generated','pages':1,'docx_path':str(doc),'pdf_path':str(pdf)}
            def scorer(**kwargs):
                doc=Path(kwargs['docx_path']);num=0 if doc==a else int(doc.stem[-1])
                return {'actual_docx_evidence':True,'docx_sha256':kwargs['expected_sha256'],
                    'claim_review_required_count':0,'scoring_version':'test-native-v1',
                    'deterministic_alignment_score':31+num*3,
                    'canonical_requirements':[{'requirement_id':'jd1','importance':'core','match_label':'direct'}]}
            result=evaluate_auto(audit=audit,projects={},fit=fit,generation=g,
                baseline_report={'raw_jd_text':'JD','stable_analysis':{'canonical_requirements':[
                    {'requirement_id':'jd1','importance':'core'}]}},
                raw_jd_text='JD',source_docx=a,repo_root=root,application_id=156,
                optimizer=lambda _a,_p:deepcopy(rootproposal),generator=generator,scorer=scorer)
            self.assertEqual(result['status'],'verified',result)
            self.assertEqual(result['winner'],'optimized_candidate')
            self.assertEqual(result['b_score'],37)
            self.assertEqual(result['v35_tested_candidates'],2)
            self.assertEqual(result['v35_verified_candidates'],2)
            self.assertEqual(len(invoked),2)
            self.assertEqual(a.read_bytes(),b'original')
            self.assertFalse(result['candidate_approved'])


if __name__=='__main__':unittest.main()

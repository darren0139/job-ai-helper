"""V3.6.4 safety: real selected-source provenance, no fake Initial, causal UI limits."""
from __future__ import annotations
import copy
import hashlib
import sys
import types
import unittest
from unittest.mock import patch

from tailoring.phase9f_v361_approval_floor import assess_phase9f_approval_floor
from tailoring.phase9f_v364_document_reverify import (
    CONTRACT_VERSION, build_frozen_selected_base_document_report,
)
from tailoring.phase9f_v364_decision_explorer import decision_summary, _plain_row_reason

GEN='normal-generation'
HASH='b'*64
SOURCE='c'*64

def ab(before=32,after=32,old='weak',new='weak'):
    return {'comparable':True,'summary':{'initial_score':before,'tailored_score':after,'score_delta':after-before},
     'requirements':[{'requirement_id':'r1','initial':{'requirement_id':'r1','importance':'core','final_match':old},
                      'tailored':{'requirement_id':'r1','importance':'core','final_match':new}}]}

def receipt(*,before=32,after=32,old='weak',new='weak'):
    auth={'fingerprint':'fingerprint','resume_text_sha256':'d'*64}
    return {'generation_id':GEN,'fit_one_page':True,'comparison_valid':True,
      'approval_ready':True,'verdict':'maintained' if before==after else 'improved',
      'document_analysis':{'initial':auth,'final':{},'final_document_sha256':HASH},
      'selected_base_analysis':{'same_as_initial':True,'document_analysis':auth},
      'selected_base_job_match_ab':None,
      'job_match_ab':ab(before,after,old,new),
      'initial_document_status':'not_available_for_handoff',
      'starting_document_contract':{
        'version':CONTRACT_VERSION,'mode':'selected_base_docx_only',
        'initial_status':'not_a_separately_uploaded_initial_document',
        'selected_base_docx_sha256':SOURCE,
        'selected_base_resume_text_sha256':auth['resume_text_sha256'],
        'selected_base_document_analysis_fingerprint':auth['fingerprint']}}

class BaselineFloor(unittest.TestCase):
    def test_handoff_selected_base_only_passes_without_fake_initial(self):
        got=assess_phase9f_approval_floor(receipt(),generation_id=GEN,docx_sha256=HASH)
        self.assertTrue(got['ready'])
        self.assertEqual(set(got['comparisons']),{'Selected Base'})
        self.assertIn('separate Initial unavailable',got['reason'])
    def test_handoff_baseline_regression_rejected(self):
        item=receipt(before=32,after=31)
        item['verdict']='maintained'
        self.assertFalse(assess_phase9f_approval_floor(item,generation_id=GEN,docx_sha256=HASH)['ready'])
    def test_core_regression_rejected_even_with_higher_score(self):
        self.assertFalse(assess_phase9f_approval_floor(
            receipt(before=30,after=33,old='direct',new='weak'),generation_id=GEN,docx_sha256=HASH)['ready'])
    def test_reject_wrong_docx_digest_and_fabricated_initial_role(self):
        item=receipt()
        self.assertFalse(assess_phase9f_approval_floor(item,generation_id=GEN,docx_sha256='a'*64)['ready'])
        item['initial_document_status']='actual_uploaded_initial'
        self.assertFalse(assess_phase9f_approval_floor(item,generation_id=GEN,docx_sha256=HASH)['ready'])
    def test_missing_source_only_role_contract_does_not_masquerade_as_initial(self):
        item=receipt()
        item.pop('starting_document_contract')
        self.assertFalse(assess_phase9f_approval_floor(item,generation_id=GEN,docx_sha256=HASH)['ready'])
    def test_execution_source_binding_checked_at_approval_time(self):
        from tailoring.phase9f_v361_approval_floor import verify_current_phase9f_floor
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            docx=Path(d)/'final.docx';docx.write_bytes(b'actual-final-document')
            item=receipt();item['document_analysis']['final_document_sha256']=hashlib.sha256(b'actual-final-document').hexdigest()
            mock_verifications=types.ModuleType('database.tailoring_verification_manager')
            mock_verifications.get_tailoring_verification_approval_gate=lambda *_args: {'ready': True}
            mock_verifications.get_latest_tailoring_verification=lambda *_args: copy.deepcopy(item)
            fake_execution=types.ModuleType('database.phase9f_tailoring_execution_manager')
            fake_execution.get_phase9f_tailoring_execution=lambda *_args: {'source_artifact':{'sha256':'a'*64}}
            with patch.dict(sys.modules,{'database.tailoring_verification_manager':mock_verifications,
                                         'database.phase9f_tailoring_execution_manager':fake_execution}):
                got=verify_current_phase9f_floor(156,GEN,{'fit_result':{'fit_one_page':True,'docx_path':str(docx)}})
                self.assertFalse(got['ready'])
                self.assertIn('source binding',got['reason'])
                fake_execution.get_phase9f_tailoring_execution=lambda *_args: {'source_artifact':{'sha256':SOURCE}}
                got=verify_current_phase9f_floor(156,GEN,{'fit_result':{'fit_one_page':True,'docx_path':str(docx)}})
                self.assertTrue(got['ready'])

    def test_missing_original_bytes_and_tampering_fail_closed(self):
        for artifact in ({}, {'artifact_bytes':b'docx','artifact_type':'docx','sha256':'a'*64,'byte_size':4},
                         {'artifact_bytes':b'docx','artifact_type':'docx','sha256':hashlib.sha256(b'docx').hexdigest(),'byte_size':5}):
            with self.subTest(artifact=artifact),self.assertRaises(ValueError):
                build_frozen_selected_base_document_report(baseline_report={'stable_analysis':{}},
                                                            jd_text='JD',source_artifact=artifact)
    def test_selected_docx_analysis_labels_source_without_initial(self):
        data=b'fake source for controlled parser test'
        sha=hashlib.sha256(data).hexdigest()
        document={'stable_analysis':{'deterministic_alignment_score':32},'keyword_match':{},
                  'resume_profile':{},'jd_profile':{},'raw_resume_text':'frozen selected source',
                  'raw_jd_text':'JD', 'document_analysis':{'resume_text_sha256':'e'*64,'fingerprint':'f'}}
        mod_parse=types.ModuleType('parse')
        mod_parse.read_resume_docx=lambda *_a,**_k:'frozen selected source'
        mod_analysis=types.ModuleType('tailoring.document_grounded_analysis')
        mod_analysis.analyze_actual_resume_against_jd=lambda **_k:copy.deepcopy(document)
        mod_analysis.seal_document_report=lambda report:report
        mod_overrides=types.ModuleType('tailoring.jd_user_input_overrides')
        mod_overrides.apply_application_session_jd_user_inputs=lambda report,**_k:report
        with patch.dict(sys.modules,{'parse':mod_parse,
                                     'tailoring.document_grounded_analysis':mod_analysis,
                                     'tailoring.jd_user_input_overrides':mod_overrides}):
            result,contract=build_frozen_selected_base_document_report(
                baseline_report={'stable_analysis':{'canonical_requirements':[]},'jd_profile':{},
                                  'resume_profile':{},'meta':{}},jd_text='JD',
                source_artifact={'artifact_bytes':data,'sha256':sha,'byte_size':len(data),'artifact_type':'docx'})
        self.assertEqual(contract['mode'],'selected_base_docx_only')
        self.assertEqual(contract['selected_base_docx_sha256'],sha)
        self.assertNotIn('frozen_initial_resume_report',result)
        self.assertEqual(result['raw_resume_text'],'frozen selected source')

class DecisionExplanation(unittest.TestCase):
    def test_tie_means_keep_existing_without_claim_of_individual_winner(self):
        rows=[{'in_actual_a':True,'in_proposed_b':False}]
        got=decision_summary({'status':'available','rows':rows},
                             {'status':'verified','winner':'existing_final','a_score':31,'b_score':31})
        self.assertIn('Keep the existing fitted résumé',got['verdict'])
        self.assertEqual(got['native_delta'],0)
        self.assertEqual(got['changed_count'],1)
        self.assertTrue(got['no_head_to_head_bullet_score'])
    def test_excluded_link_not_called_bad_evidence(self):
        row={'in_proposed_b':False,'potential_new_jd_ids':[]}
        info = {'source_receipt_present': True}
        self.assertIn('Not included in this combination', _plain_row_reason(row, info))
        row['potential_new_jd_ids']=['r2']
        self.assertIn('An independent comparison is a separate test', _plain_row_reason(row, info))

class GuardedSourceWiring(unittest.TestCase):
    def test_saved_normal_verification_does_not_use_old_profile_as_document(self):
        from pathlib import Path
        root=Path(__file__).resolve().parents[1]
        source=(root/'tailoring'/'phase8_auto_verification.py').read_text(encoding='utf-8')
        self.assertIn('legacy_profile_only_requires_new_selected_base_docx_verification',source)
        runner=(root/'database'/'phase9f_tailoring_execution_manager.py').read_text(encoding='utf-8')
        self.assertIn('build_frozen_selected_base_document_report',runner)
        self.assertIn('expected_identity=frozen_artifact_identity',runner)
        self.assertIn('phase8_selected_base_docx_not_frozen',runner)
        floor=(root/'tailoring'/'phase9f_v361_approval_floor.py').read_text(encoding='utf-8')
        self.assertIn("saved_source_sha != source_contract.get('selected_base_docx_sha256')",floor)

if __name__=='__main__':unittest.main()

class NativeProjectCheckbox(unittest.TestCase):
    def test_single_click_checkbox_updates_project_selection_without_data_editor(self):
        # Real UI path uses st.columns().checkbox rather than st.data_editor.
        from tailoring.phase9f_decision_explorer_v28 import render_multi_project_source_explorer
        class Column:
            def __init__(self,owner,index):self.owner=owner;self.index=index
            def caption(self,*_):pass
            def write(self,*_):pass
            def checkbox(self,label,**kwargs):
                self.owner.seen.append(label)
                return label.endswith('Job AI Helper')
        class Ctx:
            def __enter__(self):return self
            def __exit__(self,*a):return False
        class Fake:
            def __init__(self):self.session_state={};self.seen=[];self.edit_calls=0
            def markdown(self,*_):pass
            def caption(self,*_):pass
            def warning(self,*_):pass
            def columns(self,widths):return [Column(self,i) for i in range(len(widths))]
            def checkbox(self,*_,**kwargs):return True  # st primitive exists
            def data_editor(self,*_,**kwargs):self.edit_calls+=1;raise AssertionError('data_editor should not be used')
            def expander(self,*_,**kwargs):return Ctx()
            def dataframe(self,*_,**kwargs):pass
        st=Fake()
        view={'status':'ok','generation_id':'g','requirements':[{'id':'r1','text':'Testing','importance':'core'}],
              'projects':[{'project':name,'final_count':1,'bullets':[{'sources':['base'],
                         'links':{},'status':'retained','text':'Bullet','words':1}]}
                          for name in ('Job AI Helper','QueryAI')]}
        render_multi_project_source_explorer(st,view=view,application_id=156)
        self.assertEqual(st.session_state['phase9f_v361_source_projects_156_g'],['Job AI Helper'])
        self.assertEqual(st.edit_calls,0)
        self.assertEqual(len(st.seen),2)

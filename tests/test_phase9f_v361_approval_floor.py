"""V3.6.1 pure floor, UI and direct DB guard regression tests."""
from __future__ import annotations

import copy
import hashlib
import importlib
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from tailoring.phase9f_v361_approval_floor import (
    assess_phase9f_approval_floor, verify_current_phase9f_floor,
)
from tailoring.phase9f_decision_explorer_v28 import multi_project_table_rows, render_multi_project_source_explorer

DIGEST='a'*64
GEN='generation-1'


def ab(before=31, after=32, *, before_label='weak', after_label='weak', importance='core'):
    row={'requirement_id':'req-1','importance':importance,'final_match':before_label}
    other={'requirement_id':'req-1','importance':importance,'final_match':after_label}
    return {'comparable':True,'summary':{'initial_score':before,'tailored_score':after,'score_delta':after-before},
            'requirements':[{'requirement_id':'req-1','initial':row,'tailored':other}]}


def receipt(*, selected_same=False):
    return {'generation_id':GEN,'fit_one_page':True,'comparison_valid':True,
            'approval_ready':True,'verdict':'improved',
            'document_analysis':{'final_document_sha256':DIGEST},
            'job_match_ab':ab(30,32),
            'selected_base_analysis':{'same_as_initial':selected_same},
            'selected_base_job_match_ab':None if selected_same else ab(31,32)}


class ApprovalFloor(unittest.TestCase):
    def test_comparable_two_baselines_accept_and_return_math(self):
        got=assess_phase9f_approval_floor(receipt(),generation_id=GEN,docx_sha256=DIGEST)
        self.assertTrue(got['ready'])
        self.assertEqual(got['comparisons']['Initial']['delta'],2)
        self.assertEqual(got['comparisons']['Selected Base']['delta'],1)

    def test_selected_base_same_as_initial_alias_is_valid(self):
        got=assess_phase9f_approval_floor(receipt(selected_same=True),generation_id=GEN,docx_sha256=DIGEST)
        self.assertTrue(got['ready'])

    def test_exact_scores_may_tie(self):
        case=receipt();case['job_match_ab']=ab(32,32);case['selected_base_job_match_ab']=ab(32,32);case['verdict']='maintained'
        self.assertTrue(assess_phase9f_approval_floor(case,generation_id=GEN,docx_sha256=DIGEST)['ready'])

    def test_worse_selected_base_blocks_even_if_initial_improved(self):
        case=receipt();case['selected_base_job_match_ab']=ab(35,32)
        self.assertFalse(assess_phase9f_approval_floor(case,generation_id=GEN,docx_sha256=DIGEST)['ready'])

    def test_hard_regression_blocks_even_with_higher_score(self):
        case=receipt();case['selected_base_job_match_ab']=ab(31,32,before_label='direct',after_label='weak')
        self.assertFalse(assess_phase9f_approval_floor(case,generation_id=GEN,docx_sha256=DIGEST)['ready'])

    def test_preferred_regression_does_not_independently_block(self):
        case=receipt();case['selected_base_job_match_ab']=ab(31,32,before_label='direct',after_label='weak',importance='preferred')
        self.assertTrue(assess_phase9f_approval_floor(case,generation_id=GEN,docx_sha256=DIGEST)['ready'])

    def test_missing_document_baseline_cannot_approve(self):
        for mutation in ('document_analysis','selected_base_analysis','selected_base_job_match_ab','job_match_ab'):
            with self.subTest(mutation=mutation):
                case=receipt();case[mutation]=None
                self.assertFalse(assess_phase9f_approval_floor(case,generation_id=GEN,docx_sha256=DIGEST)['ready'])

    def test_docx_drift_and_wrong_generation_hold(self):
        self.assertFalse(assess_phase9f_approval_floor(receipt(),generation_id='wrong',docx_sha256=DIGEST)['ready'])
        self.assertFalse(assess_phase9f_approval_floor(receipt(),generation_id=GEN,docx_sha256='b'*64)['ready'])

    def test_malformed_or_fake_native_delta_hold(self):
        case=receipt();case['job_match_ab']['summary']['score_delta']=99
        self.assertFalse(assess_phase9f_approval_floor(case,generation_id=GEN,docx_sha256=DIGEST)['ready'])
        case=receipt();case['selected_base_job_match_ab']['summary']['tailored_score']=31
        case['selected_base_job_match_ab']['summary']['score_delta']=0
        self.assertFalse(assess_phase9f_approval_floor(case,generation_id=GEN,docx_sha256=DIGEST)['ready'])

    def test_current_gate_checks_actual_bytes_and_phase8_gate(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'final.docx';path.write_bytes(b'content')
            sha=hashlib.sha256(b'content').hexdigest()
            case=receipt();case['document_analysis']['final_document_sha256']=sha
            fake=types.ModuleType('database.tailoring_verification_manager')
            fake.get_tailoring_verification_approval_gate=lambda *args: {'ready':True}
            fake.get_latest_tailoring_verification=lambda *args: case
            state={'fit_result':{'fit_one_page':True,'docx_path':str(path)}}
            with patch.dict(sys.modules,{'database.tailoring_verification_manager':fake}):
                self.assertTrue(verify_current_phase9f_floor(1,GEN,state)['ready'])
                path.write_bytes(b'changed')
                self.assertFalse(verify_current_phase9f_floor(1,GEN,state)['ready'])
                fake.get_tailoring_verification_approval_gate=lambda *args: {'ready':False}
                self.assertFalse(verify_current_phase9f_floor(1,GEN,state)['ready'])

    def test_db_direct_approval_blocks_before_any_write(self):
        import importlib.util
        root = Path(__file__).parents[1]
        path = root/'database'/'tailoring_generation_control.py'
        base = types.ModuleType('database.tailoring_version_manager')
        base._connect = lambda: (_ for _ in ()).throw(AssertionError('DB must not be opened'))
        fp = types.ModuleType('resume_builder.fitting_provenance')
        fp.normalise_fitting_search_algorithm_provenance = lambda *a, **k: None
        resume = types.ModuleType('resume_builder')
        resume.__path__ = []
        state = {'generation_settings':{'phase9f_f_normal_lifecycle':{
            'lifecycle_version':'phase9f-f-normal-generation-lifecycle-v1',
            'generation_status':'completed', 'fit':{'status':'completed'}}},
            'fit_result':{'fit_one_page':True}}
        # Exercise the actual approve_tailoring_generation function.  The floor
        # rejects before metadata, connection or preference writes are possible.
        with patch.dict(sys.modules,{
            'database.tailoring_version_manager':base,
            'resume_builder':resume,
            'resume_builder.fitting_provenance':fp,
        }):
            spec=importlib.util.spec_from_file_location('_v361_db_test',path)
            mod=importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.get_tailoring_generation = lambda app, gen: state
            with patch('tailoring.phase9f_v361_approval_floor.verify_current_phase9f_floor',
                       return_value={'ready':False,'reason':'Selected Base is worse'}):
                with self.assertRaisesRegex(ValueError, 'Base no-regression approval hold'):
                    mod.approve_tailoring_generation(156, GEN)

    def test_db_approval_calls_guard_before_write(self):
        path=Path(__file__).parents[1]/'database'/'tailoring_generation_control.py'
        src=path.read_text()
        i=src.index('def approve_tailoring_generation(')
        region=src[i:src.index('\ndef archive_tailoring_generation(',i)]
        self.assertLess(region.index('verify_current_phase9f_floor('),region.index('record_generation_metadata('))
        self.assertIn('if floor.get(\'ready\') is not True:',region)


class MultiView(unittest.TestCase):
    def view(self):
        return {'status':'ok','generation_id':'gen1','requirements':[
            {'id':'jd1','text':'Unit testing','importance':'core'}],
            'projects':[
                {'project':'Job AI Helper','final_count':1,'unattributed_final':0,'bullets':[
                    {'text':'Unit tests','sources':['base'],'links':{'jd1':'direct'},'status':'retained','words':2},
                    {'text':'CI tests','sources':['library'],'links':{'jd1':'weak'},'status':'removed_fitting','words':2}]},
                {'project':'QueryAI','final_count':1,'unattributed_final':0,'bullets':[
                    {'text':'Backend API','sources':['library'],'links':{},'status':'retained','words':2}]}]}

    def test_pure_table_keeps_both_projects_and_no_mutation(self):
        original=self.view();copy_before=copy.deepcopy(original)
        rows=multi_project_table_rows(original)
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]['Fitting removals'],1)
        self.assertEqual(original,copy_before)

    def test_ui_checkbox_selects_two_and_never_modifies_source(self):
        try:
            import pandas as pd
        except ImportError:
            self.skipTest('pandas not installed')
        class Expansion:
            def __enter__(self):return self
            def __exit__(self,*_):return False
        class FakeColumn:
            @staticmethod
            def CheckboxColumn(*args,**kwargs):return None
        class Fake:
            session_state={}
            column_config=FakeColumn()
            dataframes=[]
            def markdown(self,*_):pass
            def caption(self,*_):pass
            def warning(self,*_):pass
            def data_editor(self,df,**kw):
                self.disabled=kw['disabled']
                copy=df.copy();copy.loc[:, 'Inspect']=True
                return copy
            def dataframe(self,rows,**kw):self.dataframes.append(rows)
            def expander(self,*args,**kw):return Expansion()
        st=Fake();before=self.view();original=copy.deepcopy(before)
        render_multi_project_source_explorer(st,view=before,application_id=123)
        self.assertEqual(st.session_state['phase9f_v361_source_projects_123_gen1'],['Job AI Helper','QueryAI'])
        self.assertEqual(before,original)
        self.assertNotIn('Inspect',st.disabled)
        self.assertGreater(len(st.dataframes),1)


if __name__ == '__main__': unittest.main()

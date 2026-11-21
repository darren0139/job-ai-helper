"""Controlled exact MILP counterfactual constraints (no DOCX score implied)."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch


class ForcedSolver(unittest.TestCase):
    def _solve(self):
        # Load the real compiled solver file with just import contracts stubbed;
        # its MILP implementation and actual SciPy/HiGHS are NOT mocked.
        root=Path(__file__).resolve().parents[1]
        names={
          'tailoring.phase9f_jd_relevance_optimizer_v35':{
            'VERSION':'v35','build_jd_relevance_optimization':lambda *a,**k:{},
            '_terms':lambda s:set(str(s).split()),'MAX_TRIALS':3,
            'MAX_COUNT_DELTA':2,'MAX_TOTAL_EDITS':8,'MAX_WORD_SLACK':24,'MAX_TOTAL_BULLETS':48},
          'tailoring.phase9f_auto_optimize_v31':{'build_flexible_optimization':lambda *a,**k:{}},
          'tailoring.phase9f_evidence_optimizer_v33':{'_metadata':lambda *a,**k:({}, {}, None),'overlap':lambda *a,**k:0},
          'tailoring.phase9f_joint_resume_optimizer_v2_6':{'_key':lambda v:str(v or '').casefold(),'_points':lambda *a,**k:0},
        }
        mock_modules={}
        for name,fields in names.items():
            mod=types.ModuleType(name)
            for key,val in fields.items():setattr(mod,key,val)
            mock_modules[name]=mod
        with patch.dict(sys.modules,mock_modules):
            spec=importlib.util.spec_from_file_location('_v364_exact_solver_check',
                      root/'tailoring'/'phase9f_certified_selection_v36.py')
            mod=importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        return mod._solve

    def test_forced_in_and_out_are_real_milp_constraints(self):
        solve=self._solve()
        model={'bullets':[
           {'words':10,'ids':frozenset({'r1'}),'terms':frozenset(),'original':True},
           {'words':9,'ids':frozenset({'r1'}),'terms':frozenset({'unit'}),'original':False}],
           'groups':[({'project':'P'},{},[0,1],(0,))],
           'req_ids':('r1',),'terms':('unit',),'pairs':[],
           'weights':{'r1':9},'baseline_indices':frozenset({0}),
           'baseline_ids':frozenset({'r1'}),'baseline_count':1,
           'baseline_words':10,'max_words':19}
        first=solve(model,[],time_limit=5.0,forced={1:1})
        second=solve(model,[],time_limit=5.0,forced={1:0})
        self.assertEqual(first['status'],'optimal_proxy')
        self.assertEqual(second['status'],'optimal_proxy')
        self.assertIn(1,first['selected_indices'])
        self.assertNotIn(1,second['selected_indices'])
        self.assertEqual(len(first['phase_receipts']),4)
        self.assertEqual(len(second['phase_receipts']),4)
        with self.assertRaises(ValueError):
            solve(model,[],time_limit=1.0,forced={2:1})

if __name__=='__main__':unittest.main()

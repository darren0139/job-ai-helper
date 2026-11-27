"""Portable regression controls; synthetic evidence is never a real benchmark."""
import copy
import csv
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
from tests import b213_policy_support as p


class HistoricalScopeTests(unittest.TestCase):
    def fixture(self, version):
        return {"snapshot":{"audit":{"corpus":{"jobs":[{"baseline_stable_analysis":{"scoring_version":version}}]}}}}

    def modules(self, version):
        def versions():
            return {"scoring_version":version, "taxonomy_version":"fixed", "registry_version":"fixed"}
        jd=types.ModuleType('job_discovery'); jd.__path__=[]
        ta=types.ModuleType('tailoring'); ta.__path__=[]
        mods=[]
        for parent,name in ((jd,'matching'),(ta,'job_match_ab_analysis'),(ta,'initial_analysis_explainer')):
            m=types.ModuleType(parent.__name__+'.'+name); m.current_match_versions=versions
            setattr(parent,name,m); mods.append(m)
        return {m.__name__:m for m in [jd,ta,*mods]}, mods

    def test_every_known_host_keeps_exact_frozen_bytes_and_restores(self):
        for version in (p.LEGACY,p.ACTIVE,p.ROLLBACK_B219A,p.ACTIVE_B219A,p.ACTIVE_B219B):
            with self.subTest(version=version):
                bundle=self.fixture(p.LEGACY); before=copy.deepcopy(bundle)
                fake,mods=self.modules(version)
                funcs=[m.current_match_versions for m in mods]
                with patch.dict(sys.modules,fake):
                    with p.historical_receipt_policy(bundle):
                        for m in mods:
                            self.assertEqual(m.current_match_versions(),{'scoring_version':p.LEGACY,'taxonomy_version':'fixed','registry_version':'fixed'})
                    self.assertEqual([m.current_match_versions for m in mods],funcs)
                self.assertEqual(bundle,before)

    def test_unknown_host_and_relabelled_fixture_rejected(self):
        for host,fixture in (('unknown',p.LEGACY),(p.ACTIVE_B219B,p.ACTIVE_B219B),(p.ACTIVE_B219B,p.ROLLBACK_B219A)):
            fake,mods=self.modules(host)
            with patch.dict(sys.modules,fake),self.assertRaises(AssertionError):
                with p.historical_receipt_policy(self.fixture(fixture)):
                    self.fail('unexpected admission')
            self.assertEqual(mods[0].current_match_versions()['scoring_version'],host)

    def test_scope_restored_on_exception(self):
        fake,mods=self.modules(p.ACTIVE_B219B)
        with patch.dict(sys.modules,fake):
            with self.assertRaisesRegex(RuntimeError,'sentinel'):
                with p.historical_receipt_policy(self.fixture(p.LEGACY)):
                    raise RuntimeError('sentinel')
            self.assertEqual(mods[0].current_match_versions()['scoring_version'],p.ACTIVE_B219B)


class PortableOwnerPacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path=Path(__file__).resolve().parents[1]/'reports/v37_real_bullet_quality/owner_packet/build_packet.py'
        spec=importlib.util.spec_from_file_location('portable_owner_packet',path)
        cls.module=importlib.util.module_from_spec(spec); spec.loader.exec_module(cls.module)

    def cases(self):
        def case(i,verification,native):
            base={'bullet':'Implemented a synthetic example API.', 'sources':['Base','Current final'], 'words':5, 'saved_jd_ids':['req_demo']}
            if native:
                base['native_requirement_ids']=['req_demo']; base['jd_links']=[{'text':'API implementation','importance':'core','status':'observed','native_evidence':{'fixture':{'excerpt':'example API','match_label':'direct','strength':5}}}]
            return {'case_id':f'SYN{i}','application':f'synthetic-{i}','project':'Example project','jd_text':f'Synthetic JD {i}', 'native_binding':'synthetic only', 'jd_requirements':[],
                'base':base,'library':{'bullet':'Documented a synthetic interface.', 'sources':['Library'], 'words':4, 'saved_jd_ids':['invalid']},
                'source_receipt':{'jd_sha256':self.module.digest(f'Synthetic JD {i}'),'company':'Example','job':'Example role','generation_id':f'synthetic-{i}','docx_sha256':'synthetic','verification_row':verification},
                'diagnostic':{'reason':'HIDDEN_SENTINEL','outcome':'Insufficient verified evidence to determine a preference.'}}
        return [case(1,None,False),case(2,2,True),case(3,3,False)]

    def test_blind_rows_contexts_and_reasons(self):
        cases=self.cases(); before=copy.deepcopy(cases); m=self.module; rows=m.review_rows(cases)
        self.assertEqual(len(rows),3); self.assertEqual(len({r['wording_pair_id'] for r in rows}),1); self.assertEqual(len({r['jd_sha256'] for r in rows}),3)
        self.assertTrue(all(not r['owner_outcome'] and not r['reviewer_notes'] for r in rows))
        self.assertFalse(any('diagnostic' in k for k in rows[0])); rendered=m.render(cases)
        self.assertNotIn('HIDDEN_SENTINEL',rendered); self.assertNotIn(cases[0]['diagnostic']['outcome'],rendered)
        self.assertIn('unmeasured',rendered); self.assertIn('does not disprove',rendered)
        self.assertIn('not independent attestation',rows[1]['base_citations'])
        self.assertEqual(m.malformed_links(cases[0]),['invalid'])
        self.assertEqual([m.reasons(c)[0] for c in cases],['Saved document authority unavailable','Diagnostic rule restriction despite a recorded native citation','Document-bound observation has no attributed citation for either wording'])
        self.assertEqual(cases,before)

    def test_label_integrity_blank_partial_and_negative_controls(self):
        m=self.module; cases=self.cases()
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'labels.csv'
            def write(rows):
                with path.open('w',encoding='utf-8-sig',newline='') as f:
                    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
            rows=m.review_rows(cases);write(rows); report=m.compare_labels(cases,path)
            self.assertEqual(report['labelled'],0); self.assertIsNone(report['semantic_accuracy'])
            rows[0]['owner_outcome']='Complementary';write(rows);report=m.compare_labels(cases,path)
            self.assertEqual(report['labelled'],1);self.assertIsNone(report['semantic_accuracy'])
            for key,val in [('jd_sha256','stale'),('wording_pair_id','wrong'),('base_wording','changed'),('owner_outcome','invalid')]:
                rows=m.review_rows(cases);rows[0][key]=val;write(rows)
                with self.assertRaises(ValueError):m.compare_labels(cases,path)
            rows=m.review_rows(cases);rows[-1]=rows[0];write(rows)
            with self.assertRaises(ValueError):m.compare_labels(cases,path)
            write(m.review_rows(cases)[:1])
            with self.assertRaises(ValueError):m.compare_labels(cases,path)

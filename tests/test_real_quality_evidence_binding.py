"""Pure controls for the report-only real-corpus citation adapter."""
import importlib.util
from pathlib import Path
from copy import deepcopy
from hashlib import sha256
import unittest
from tailoring.phase9e_blueprint_selection import fingerprint_value
from tailoring.phase9f_starting_source_ranking import canonical_requirement_scope_fingerprint

spec=importlib.util.spec_from_file_location('quality_binding',Path(__file__).resolve().parents[1]/'reports/v37_real_bullet_quality/evidence_binding.py')
binding=importlib.util.module_from_spec(spec);spec.loader.exec_module(binding)


class EvidenceBinding(unittest.TestCase):
    def fixture(self):
        req={'requirement_id':'api','text':'Build APIs','importance':'core'}
        native={'canonical_requirements':[req],'scoring_version':'fixture'}
        authority={'jd_text_sha256':sha256(b'Build APIs').hexdigest(),
          'stable_analysis_fingerprint':fingerprint_value(native),
          'canonical_requirement_fingerprint':canonical_requirement_scope_fingerprint([req]),
          'identity':{'scoring_version':'fixture'}}
        authority['fingerprint']=fingerprint_value(authority)
        case={'audit':{'docx_sha256':'a'*64},'raw_jd_text':'Build APIs','baseline':{'stable_analysis':native},'projects':{}}
        receipt={'document_analysis':{'final_document_sha256':'a'*64,'final':authority},'after_stable_analysis':native}
        return case,receipt
    def test_bound_document_does_not_claim_a_candidate_score(self):
        case,receipt=self.fixture();result,_=binding.bind(case,receipt)
        self.assertEqual(result['a_docx_sha256'],'a'*64)
        self.assertNotIn('b_score',result)
    def test_stale_hash_or_native_fingerprint_withholds(self):
        case,receipt=self.fixture();before=deepcopy(receipt)
        case['audit']['docx_sha256']='b'*64
        self.assertEqual(binding.bind(case,receipt)[0],{})
        self.assertEqual(receipt,before)
        case['audit']['docx_sha256']='a'*64
        receipt['after_stable_analysis']['scoring_version']='changed'
        self.assertEqual(binding.bind(case,receipt)[0],{})
    def test_missing_historical_authority_is_not_fabricated(self):
        case,_=self.fixture()
        self.assertEqual(binding.bind(case,{})[0],{})

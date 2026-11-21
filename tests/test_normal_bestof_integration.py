from copy import deepcopy
import unittest
from tailoring.phase9f_automatic_bestof_v30_ui import reviewed_core_floor, freeze_reviewed_slate


class ReviewedFloor(unittest.TestCase):
    def test_full_slate_identity_changes_even_if_base_claims_do_not(self):
        original={'projects':[{'project':'Tool','after':['Base claim','Library wording']}], 'requires_base_review':True}
        snapshot,identity=freeze_reviewed_slate(original)
        original['projects'][0]['after'][1]='Different Library wording'
        self.assertNotEqual(identity,freeze_reviewed_slate(original)[1])
        self.assertEqual(snapshot['projects'][0]['after'][1],'Library wording')
    def test_invalid_or_cyclic_review_receipt_fails_closed(self):
        proposal={};proposal['self']=proposal
        self.assertEqual(freeze_reviewed_slate(proposal),(None,''))
        self.assertEqual(freeze_reviewed_slate({'value':float('nan')}),(None,''))
    def fixture(self):
        report={'stable_analysis':{'canonical_requirements':[{'requirement_id':'core','importance':'core'}]}}
        result={'winner':'optimized_candidate','a_score':10,'b_score':12,'a_docx_sha256':'a','b_docx_sha256':'b',
          'native_document_evidence':{role:{'docx_sha256':sha,'requirements':[
            {'requirement_id':'core','match_label':'weak','evidence_strength':3}]} for role,sha in [('existing','a'),('alternative','b')]}}
        return result,report
    def test_higher_total_cannot_hide_strength_loss(self):
        result,report=self.fixture();result['native_document_evidence']['alternative']['requirements'][0]['evidence_strength']=2
        before=deepcopy(result)
        self.assertEqual(reviewed_core_floor(result,report)['winner'],'existing_final')
        self.assertEqual(result,before)
    def test_equal_core_is_allowed_for_further_review(self):
        result,report=self.fixture()
        self.assertEqual(reviewed_core_floor(result,report)['reviewed_core_floor'],'passed')
    def test_missing_document_binding_withholds(self):
        result,report=self.fixture();result['b_docx_sha256']='stale'
        self.assertEqual(reviewed_core_floor(result,report)['winner'],'existing_final')

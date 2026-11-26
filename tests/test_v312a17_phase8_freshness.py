"""A1.7 activation must not accept pre-activation Phase 8 certificates."""
from __future__ import annotations
from copy import deepcopy
import unittest
from unittest.mock import patch
from tailoring.phase8_auto_verification import (
    phase8_verification_is_current,
    phase8_verification_refresh_reason,
)
from tailoring.phase8_verification import (
    PHASE8_VERIFICATION_VERSION,
    PHASE8_PREAPPROVAL_GATE_VERSION,
    refresh_phase8_readiness,
)

BASE = 'stable-evidence-v1.16-phase6d20'
ACTIVE = BASE + '-v312a17-fullstack-single-row'


class Phase8PolicyFreshness(unittest.TestCase):
    def setUp(self):
        self.generation={'generation_id':'g1','status':'draft',
                         'fit_result': {'fit_one_page':True,'page_count':1}}
        self.receipt={'phase8_version':PHASE8_VERIFICATION_VERSION,
                      'approval_gate_version':PHASE8_PREAPPROVAL_GATE_VERSION,
                      'verified_generation_snapshot_fingerprint':'g1_hash',
                      'after_stable_analysis':{'scoring_version':BASE},
                      'job_match_ab': {'status':'comparable'}}

    @patch('tailoring.phase8_auto_verification.build_phase8_generation_snapshot_fingerprint',return_value='g1_hash')
    @patch('tailoring.phase8_auto_verification.inspect_job_match_ab_lifecycle',return_value={'state':'both_analyses_available_and_comparable'})
    def test_default_off_old_receipt_compatible(self,*_):
        with patch('tailoring.phase8_auto_verification.SCORING_VERSION',BASE):
            self.assertTrue(phase8_verification_is_current(self.receipt,self.generation))
            self.assertEqual(phase8_verification_refresh_reason(self.receipt,self.generation),'current')

    @patch('tailoring.phase8_auto_verification.build_phase8_generation_snapshot_fingerprint',return_value='g1_hash')
    @patch('tailoring.phase8_auto_verification.inspect_job_match_ab_lifecycle',return_value={'state':'both_analyses_available_and_comparable'})
    def test_active_policy_rejects_old_or_missing_native_scoring_identity(self,*_):
        with patch('tailoring.phase8_auto_verification.SCORING_VERSION',ACTIVE):
            self.assertFalse(phase8_verification_is_current(self.receipt,self.generation))
            self.assertEqual(phase8_verification_refresh_reason(self.receipt,self.generation),
                             'scoring_policy_changed_requires_fresh_verification')
            receipt=deepcopy(self.receipt);receipt.pop('after_stable_analysis')
            self.assertFalse(phase8_verification_is_current(receipt,self.generation))

    @patch('tailoring.phase8_auto_verification.build_phase8_generation_snapshot_fingerprint',return_value='g1_hash')
    @patch('tailoring.phase8_auto_verification.inspect_job_match_ab_lifecycle',return_value={'state':'both_analyses_available_and_comparable'})
    def test_active_policy_can_accept_fresh_proven_scoring_identity(self,*_):
        receipt=deepcopy(self.receipt)
        receipt['after_stable_analysis']['scoring_version']=ACTIVE
        with patch('tailoring.phase8_auto_verification.SCORING_VERSION',ACTIVE):
            self.assertTrue(phase8_verification_is_current(receipt,self.generation))
            self.assertEqual(phase8_verification_refresh_reason(receipt,self.generation),'current')

    @patch('tailoring.phase8_auto_verification.build_phase8_generation_snapshot_fingerprint',return_value='g1_hash')
    @patch('tailoring.phase8_auto_verification.inspect_job_match_ab_lifecycle',return_value={'state':'both_analyses_available_and_comparable'})
    def test_active_policy_accepts_scoped_identity_suffix(self,*_):
        receipt=deepcopy(self.receipt)
        receipt['after_stable_analysis']['scoring_version']=ACTIVE + '+reviewed-requirement-scope'
        with patch('tailoring.phase8_auto_verification.SCORING_VERSION',ACTIVE):
            self.assertTrue(phase8_verification_is_current(receipt,self.generation))

    def test_readiness_refresh_never_reapproves_old_policy(self):
        with patch('tailoring.phase8_verification.SCORING_VERSION',ACTIVE):
            with self.assertRaisesRegex(ValueError,'Scoring policy changed'):
                refresh_phase8_readiness(self.receipt,self.generation)

    def test_off_policy_does_not_add_new_readiness_blocker(self):
        # The legacy behavior remains responsible for the rest of readiness.
        with patch('tailoring.phase8_verification.SCORING_VERSION',BASE):
            try:
                refresh_phase8_readiness(self.receipt,self.generation)
            except Exception as exc:
                self.assertNotIn('Scoring policy changed',str(exc))


if __name__=='__main__':
    unittest.main()

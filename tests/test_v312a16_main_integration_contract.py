"""A1.6 evidence-selection integration: source and scope guards across rollout."""
from __future__ import annotations
import ast
import inspect
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from analysis_stability import stable_evidence_scoring as scoring
from tailoring.fullstack_direct_evidence_v312a14 import independent_fullstack_implementation

class MainIntegrationContracts(unittest.TestCase):
    def test_legacy_a14_environment_setting_cannot_control_rollout(self):
        with patch.dict(os.environ, {'JOB_AI_HELPER_V312A14_FULLSTACK_ENABLED':'1'}):
            self.assertIs(scoring._V312A14_NATIVE_REPLAY_SCOPE.get(), False)
            self.assertEqual(scoring.SCORING_VERSION,
                             scoring._BASE_SCORING_VERSION +
                             ('-v312b215-jd-eligibility-v312a17-fullstack-single-row' if scoring._V312A17_RUNTIME_ACTIVE else ''))
    def test_opt_in_is_temporary_and_cannot_leak_on_exception(self):
        self.assertIs(scoring._V312A14_NATIVE_REPLAY_SCOPE.get(), False)
        with self.assertRaisesRegex(RuntimeError,'isolation'):
            with scoring.temporary_v312a14_candidate_scope():
                self.assertIs(scoring._V312A14_NATIVE_REPLAY_SCOPE.get(), True)
                with scoring.temporary_v312a14_candidate_scope():
                    self.assertIs(scoring._V312A14_NATIVE_REPLAY_SCOPE.get(), True)
                raise RuntimeError('isolation')
        self.assertIs(scoring._V312A14_NATIVE_REPLAY_SCOPE.get(), False)
    def test_production_call_site_is_scoped_and_lexical_only(self):
        tree=ast.parse(inspect.getsource(scoring.build_stable_analysis))
        conditions=[ast.unparse(n.test) for n in ast.walk(tree) if isinstance(n,ast.If)]
        self.assertTrue(any('_V312A14_NATIVE_REPLAY_SCOPE.get()' in x and
                            'retrieval_mode_override' in x and 'lexical' in x for x in conditions))
    def test_reject_testing_only_unsupported_fullstack_claims(self):
        for row in (
            'Created automated backend and frontend tests covering authentication and role-based navigation.',
            'Automated frontend builds and backend tests with GitHub Actions.',
            'Built end-to-end full-stack integration tests for a web application.',
            'Developed a React frontend while another developer built the backend API.',
        ):
            with self.subTest(row=row):
                self.assertFalse(independent_fullstack_implementation(row))
    def test_accept_genuine_independent_project_implementation(self):
        text=('Built a full-stack IT service request tracker with React, TypeScript, '
              'FastAPI, and PostgreSQL, spanning application development, '
              'database design, and RESTful APIs.')
        self.assertTrue(independent_fullstack_implementation(text))
    def test_replay_cli_never_saves_phase8_or_approves(self):
        replay=Path(__file__).resolve().parents[1]/'tools'/'v312a14_native_counterfactual.py'
        source=replay.read_text(encoding='utf-8')
        self.assertIn('saved_native_parity_verified',source)
        self.assertIn('CANDIDATE_REPLAY_PASS_BOTH',source)
        self.assertNotIn('save_phase8_verification(',source)
        self.assertNotIn('approve_generation(',source)

if __name__ == '__main__':
    unittest.main()

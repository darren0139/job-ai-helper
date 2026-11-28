"""A1.8 default-on rollout of the validated A1.7 policy; legacy opt-out."""
from __future__ import annotations
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
POLICY = 'JOB_AI_HELPER_V312A17_NATIVE_FULLSTACK_POLICY'
TOKEN = 'v312a17_fullstack_single_row'
from tests.b213_policy_support import ACTIVE_B222D1, ROLLBACK_B219A


class RuntimePolicyContracts(unittest.TestCase):
    def _child(self, value: str | None):
        env = os.environ.copy()
        env.pop(POLICY, None)
        if value is not None:
            env[POLICY] = value
        code = '''\
import json
from analysis_stability import stable_evidence_scoring as s
from tailoring import phase8_verification as phase8
print('A17_STARTUP_PROBE='+json.dumps({
 'active': s._V312A17_RUNTIME_ACTIVE,
 'version': s.SCORING_VERSION,
 'phase8': phase8.SCORING_VERSION,
 'scope': s._V312A14_NATIVE_REPLAY_SCOPE.get(),
}))
'''
        out = subprocess.run([sys.executable, '-c', code], cwd=str(ROOT), env=env,
                             text=True, capture_output=True, timeout=35)
        self.assertEqual(out.returncode, 0, out.stderr[-2000:])
        lines=[x for x in out.stdout.splitlines() if x.startswith('A17_STARTUP_PROBE=')]
        self.assertEqual(len(lines),1, out.stdout[-1000:])
        return json.loads(lines[0].split('=',1)[1])

    def test_default_on_only_valid_policy_identity(self):
        for value in (None, TOKEN):
            with self.subTest(value=value):
                row=self._child(value)
                self.assertTrue(row['active'])
                self.assertEqual(row['version'], ACTIVE_B222D1)
                self.assertEqual(row['phase8'], row['version'])
                self.assertFalse(row['scope'])

    def test_explicit_legacy_rollback_and_invalid_values_do_not_activate(self):
        for value in ('legacy', '', '1', 'true', 'enabled', 'v312a14_fullstack_single_row'):
            with self.subTest(value=value):
                row=self._child(value)
                self.assertFalse(row['active'])
                self.assertEqual(row['version'], ROLLBACK_B219A)
                self.assertEqual(row['phase8'], ROLLBACK_B219A)
                self.assertFalse(row['scope'])

    def test_exact_startup_token_changes_phase8_and_scorer_identity(self):
        row=self._child(TOKEN)
        self.assertTrue(row['active'])
        self.assertEqual(row['version'], ACTIVE_B222D1)
        self.assertEqual(row['phase8'], row['version'])
        self.assertFalse(row['scope'])

    def test_environment_change_after_import_is_not_runtime_toggle(self):
        from analysis_stability import stable_evidence_scoring as s
        previous = s._V312A17_RUNTIME_ACTIVE
        previous_identity = s.SCORING_VERSION
        with patch.dict(os.environ, {POLICY: 'legacy'}):
            self.assertIs(s._V312A17_RUNTIME_ACTIVE, previous)
            self.assertEqual(s.SCORING_VERSION, previous_identity)

    def test_policy_only_applies_to_lexical_native_scoring(self):
        from analysis_stability import stable_evidence_scoring as s
        source = Path(s.__file__).read_text(encoding='utf-8')
        tree = ast.parse(source)
        fn=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='build_stable_analysis')
        guards=[ast.unparse(n.test) for n in ast.walk(fn) if isinstance(n,ast.If)]
        self.assertTrue(any('_V312A17_RUNTIME_ACTIVE' in g and 'retrieval_mode_override' in g and 'lexical' in g for g in guards))
        self.assertIn('v312a17_policy_audit', source)
        self.assertIn('native_fullstack_policy_v312a17', source)
        self.assertIn('v312a14_candidate_audit', source)

    def test_only_explicit_preflight_can_write_optional_report(self):
        source=(ROOT/'tools/v312a17_activation_preflight.py').read_text(encoding='utf-8')
        self.assertIn('CANDIDATE_REPLAY_PASS_BOTH',source)
        self.assertIn('A18_DEFAULT_POLICY_VERIFIED_BOTH',source)
        self.assertIn('saved_phase8_receipts_unchanged',source)
        self.assertIn('no_app_db_docx_approval_or_git_writes',source)
        self.assertNotIn('save_phase8_verification(', source)
        self.assertNotIn('approve_generation(', source)
        self.assertNotIn('sqlite3.connect(', source)
        self.assertNotIn('git checkout', source)

    def test_preflight_blocks_unexpected_change_and_requires_both_cohorts(self):
        source=(ROOT/'tools/v312a17_activation_preflight.py').read_text(encoding='utf-8')
        self.assertIn("c['id']=='Keith' and mode=='portfolio'",source)
        self.assertIn('HOLD_RUNTIME_DIFFERS_FROM_VERIFIED_EXPERIMENT',source)
        self.assertIn('HOLD_LEGACY_REPLAY',source)
        self.assertIn('HOLD_DEFAULT_ON_REPLAY',source)
        self.assertIn("len(result['cohorts'])==2",source)
        self.assertIn("len(changes)!=1",source)
        self.assertIn('a1.validate_receipt_payload(',source)


if __name__=='__main__':
    unittest.main()

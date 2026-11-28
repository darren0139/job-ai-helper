"""V3.12-A1.8 policy defaults and rollback: real fresh-process tests."""
from __future__ import annotations
import ast
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
POLICY='JOB_AI_HELPER_V312A17_NATIVE_FULLSTACK_POLICY'
from tests.b213_policy_support import ACTIVE_B222D1 as ACTIVE, ROLLBACK_B219A as LEGACY

class DefaultPolicyRollout(unittest.TestCase):
    def _probe(self, setting):
        env=os.environ.copy();env.pop(POLICY,None)
        if setting is not None:env[POLICY]=setting
        script="import json\nfrom analysis_stability import stable_evidence_scoring as s\nfrom tailoring import phase8_auto_verification as auto\nfrom tailoring import phase8_verification as p8\nprint('A18_PROBE='+json.dumps({'active':s._V312A17_RUNTIME_ACTIVE,\n  'scoring_version':s.SCORING_VERSION,'phase8_version':p8.SCORING_VERSION,\n  'auto_version':auto.SCORING_VERSION,\n  'context_var':s._V312A14_NATIVE_REPLAY_SCOPE.get()}))\n"
        result=subprocess.run([sys.executable,'-c',script],cwd=ROOT,env=env,
                              text=True,capture_output=True,timeout=40)
        self.assertEqual(result.returncode,0,result.stderr[-2500:])
        import json
        records=[line for line in result.stdout.splitlines() if line.startswith('A18_PROBE=')]
        self.assertEqual(len(records),1,result.stdout[-1800:])
        return json.loads(records[0].split('=',1)[1])

    def test_fresh_startup_defaults_to_enabled_with_consistent_phase8_identity(self):
        for setting in (None,'v312a17_fullstack_single_row'):
            with self.subTest(setting=setting):
                row=self._probe(setting)
                self.assertTrue(row['active'])
                self.assertEqual(row['scoring_version'],ACTIVE)
                self.assertEqual(row['phase8_version'],ACTIVE)
                self.assertEqual(row['auto_version'],ACTIVE)
                self.assertFalse(row['context_var'])

    def test_explicit_legacy_rollback_on_fresh_startup(self):
        row=self._probe('legacy')
        self.assertFalse(row['active'])
        self.assertEqual(row['scoring_version'],LEGACY)
        self.assertEqual(row['phase8_version'],LEGACY)
        self.assertEqual(row['auto_version'],LEGACY)
        self.assertFalse(row['context_var'])

    def test_invalid_settings_fail_to_legacy_not_accidentally_activate(self):
        for setting in ('','true','1','invalid'):
            with self.subTest(setting=setting):
                self.assertEqual(self._probe(setting)['scoring_version'],LEGACY)

    def test_replay_does_not_auto_approve_or_persist(self):
        text=(ROOT/'tools/v312a17_activation_preflight.py').read_text(encoding='utf-8')
        self.assertIn("env_off[POLICY_ENV]='legacy'",text)
        self.assertIn('env_on.pop(POLICY_ENV,None)',text)
        self.assertIn('A18_DEFAULT_POLICY_VERIFIED_BOTH',text)
        for forbidden in ('save_phase8_verification(', 'approve_generation(', 'sqlite3.connect('):
            self.assertNotIn(forbidden,text)

    def test_fullstack_selection_remains_lexical_and_single_row_only(self):
        from analysis_stability import stable_evidence_scoring as s
        source=Path(s.__file__).read_text(encoding='utf-8')
        tree=ast.parse(source)
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='build_stable_analysis')
        guards=[ast.unparse(n.test) for n in ast.walk(fn) if isinstance(n,ast.If)]
        self.assertTrue(any('_V312A17_RUNTIME_ACTIVE' in g and 'retrieval_mode_override' in g
                            and 'lexical' in g for g in guards))
        from tailoring.fullstack_direct_evidence_v312a14 import independent_fullstack_implementation
        self.assertTrue(independent_fullstack_implementation(
            'Built a full-stack IT service request tracker with React, TypeScript, FastAPI, '
            'and PostgreSQL, spanning application development, database design, and RESTful APIs.'))
        self.assertFalse(independent_fullstack_implementation(
            'Automated frontend builds and backend tests using GitHub Actions.'))

if __name__=='__main__':unittest.main()

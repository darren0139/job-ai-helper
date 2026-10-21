"""False-green protection for current controls and historical registration."""
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import os
import subprocess
import sys
import unittest
from unittest.mock import patch

from scripts import ollama_test_lanes as lanes
from scripts import run_ollama_historical_checks as historical
from scripts import compare_ollama_unresolved_prompts_v1_2 as old
from scripts import compare_ollama_unresolved_prompts_v1_3 as new
from scripts import smoke_ollama_unresolved_adjudication_v1 as smoke
from tests.ollama_current_fixtures import comparison_artifacts, adjudication_artifacts, ROOT, SCOPE


class TestLaneIntegrityTests(unittest.TestCase):
    def test_registered_current_tests_equal_unittest_module_loading(self):
        value=lanes.load_manifest(); expected=set(lanes.inventory()['current_test_ids'])
        suite=unittest.defaultTestLoader.loadTestsFromNames(value['current_modules'])
        def ids(item):
            if isinstance(item,unittest.TestSuite):
                return [test for child in item for test in ids(child)]
            return [item.id()]
        self.assertEqual(set(ids(suite)),expected)
        self.assertEqual(len(ids(suite)),len(expected))

    def test_all_archives_and_assertions_have_explicit_current_or_historical_mapping(self):
        result=lanes.inventory()
        self.assertGreater(len(result['historical_test_ids']),100)
        self.assertEqual(result['historical_reproduction'],'NOT_RUN')
        self.assertFalse(result['historical_reproduction_validated'])
        self.assertFalse(set(result['current_test_ids']) & set(result['historical_test_ids']))

    def test_missing_archive_registration_and_method_are_rejected(self):
        value=lanes.load_manifest()
        value['archives'].pop()
        with self.assertRaisesRegex(ValueError,'file registration gap'):lanes.inventory(manifest=value)
        value=lanes.load_manifest();value['archives'][0]['test_ids'].pop()
        with self.assertRaisesRegex(ValueError,'method registration gap'):lanes.inventory(manifest=value)

    def test_unmapped_historical_assertion_and_missing_current_replacement_reject(self):
        value=lanes.load_manifest();key=next(iter(value['coverage_mapping']))
        value['coverage_mapping'].pop(key)
        with self.assertRaisesRegex(ValueError,'mapping gap'):lanes.inventory(manifest=value)
        value=lanes.load_manifest();value['coverage_mapping'][key]['current_test']='tests.missing.Test.test_missing'
        with self.assertRaisesRegex(ValueError,'Missing current'):lanes.inventory(manifest=value)

    def test_modified_archive_hash_cannot_be_reapproved_implicitly(self):
        value=lanes.load_manifest();value['archives'][0]['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'archive bytes changed'):lanes.inventory(manifest=value)

    def test_missing_historical_prerequisites_are_blocked_without_import_or_generation(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch('importlib.import_module',side_effect=AssertionError('No historical/current implementation imports')):
            result=lanes.historical_preconditions(Path(directory))
        self.assertEqual(result['status'],'BLOCKED')
        self.assertFalse(result['attempted']);self.assertFalse(result['validated'])
        self.assertEqual(result['executed_test_count'],0)
        self.assertEqual(result['inference_requests'],0)
        self.assertTrue(any(b['reason']=='MISSING' for b in result['blockers']))

    def test_historical_command_exit_and_list_never_claim_reproduction(self):
        with tempfile.TemporaryDirectory() as directory, patch('sys.stdout',new_callable=io.StringIO) as output:
            self.assertEqual(historical.main(['--bundle-root',directory]),2)
            self.assertEqual(json.loads(output.getvalue())['status'],'BLOCKED')
        with patch('sys.stdout',new_callable=io.StringIO) as output:
            self.assertEqual(historical.main(['--list']),0)
            self.assertEqual(json.loads(output.getvalue())['status'],'INVENTORY_ONLY_NOT_REPRODUCTION')

    def test_exact_bytes_include_crlf_and_path_escape_never_weaken_protection(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'source.txt';path.write_bytes(b'Frozen\n')
            hashes={'source.txt':hashlib.sha256(b'Frozen\n').hexdigest()}
            self.assertEqual(lanes.verify_bytes(root,hashes),[])
            path.write_bytes(b'Frozen\r\n')
            self.assertEqual(lanes.verify_bytes(root,hashes)[0]['reason'],'BYTE_HASH_MISMATCH')
            self.assertEqual(lanes.verify_bytes(root,{'../outside':'0'*64})[0]['reason'],'OUTSIDE_BUNDLE')
            self.assertEqual(path.read_bytes(),b'Frozen\r\n')

    def test_current_freeze_and_integrity_validators_accept_real_test_owned_plan(self):
        with comparison_artifacts() as root:
            plan=old.freeze_plan();self.assertTrue(old.validate_plan(plan))
            self.assertEqual(plan,old.freeze_plan())
            plan3=new.freeze_plan();self.assertTrue(new.validate_plan(plan3))
            self.assertEqual(plan3,new.freeze_plan())
            self.assertEqual(len(plan['jobs']),20);self.assertEqual(len(plan3['jobs']),20)
            self.assertIn(SCOPE,(root/'unit_source.json').read_text())

    def test_source_tampering_rejects_before_any_metadata_or_inference(self):
        with comparison_artifacts() as root:
            plan=old.freeze_plan();frozen=deepcopy(plan)
            (root/'unit_source.json').write_bytes(b'TAMPERED')
            with patch.object(old,'make_transport') as transport:
                with self.assertRaisesRegex(ValueError,'Protected artifact/runner changed'):
                    old.run(plan)
                transport.assert_not_called()
            self.assertEqual(plan,frozen)

    def test_missing_source_blocks_freeze_without_replacement_artifacts(self):
        with comparison_artifacts() as root:
            path=root/'unit_source.json';path.unlink()
            with self.assertRaises(FileNotFoundError):old.freeze_plan()
            self.assertFalse(path.exists())

    def test_protected_input_overlap_is_rejected_by_actual_isolation(self):
        with comparison_artifacts() as root:
            path=root/'reports/unresolved_gold_decision_review_v3.json'
            path.write_text(json.dumps({'cases':[{'exact_requirement':smoke.CASES[0]['requirement']}]}))
            with self.assertRaisesRegex(ValueError,'overlap'):smoke.check_synthetic_isolation()
            with self.assertRaisesRegex(ValueError,'overlap'):old.freeze_plan()

    def test_current_controls_do_not_read_ignored_repository_artifacts(self):
        original_open=io.open
        def deny_local(file,*args,**kwargs):
            if isinstance(file,(str,Path)):
                path=Path(file).resolve()
                if path.parent in (ROOT/'reports',ROOT/'docs') or 'refs/codex' in path.as_posix():
                    raise AssertionError('Ignored/private artifact dependency: '+str(path))
            return original_open(file,*args,**kwargs)
        with patch('io.open',side_effect=deny_local):
            with comparison_artifacts():self.assertTrue(old.validate_plan(old.freeze_plan()))
            with adjudication_artifacts():
                from scripts import adjudicate_unresolved_requirements as cli
                manifest=json.loads(cli.BENCHMARK.read_text())
                cases,skipped=cli.prepare(manifest)
                self.assertEqual(len(cases),40);self.assertFalse(skipped)
                self.assertEqual(manifest['fixture_scope'],SCOPE)

    def test_authored_prior_label_controls_never_change_original_human_gold(self):
        from taxonomy_discovery import unresolved_gold_review as gold
        path=gold.ORIGINAL;before=path.read_bytes()
        with adjudication_artifacts():
            parent=gold.original()
            self.assertEqual(parent['fixture_scope'],SCOPE)
            self.assertFalse(gold.summary(gold.versioned_manifest(parent,[],[]))['labeling_prerequisite_satisfied'])
        self.assertEqual(path.read_bytes(),before)
        self.assertEqual(gold.ORIGINAL,path)

    def test_default_full_runner_keeps_discovery_and_adds_visible_lane_check(self):
        from scripts import run_project_checks as checks
        self.assertIn('scripts.check_ollama_test_lanes',checks.SAFE_SMOKE_MODULES)
        with patch.object(checks,'run_command') as command:
            checks.run_full_tests()
        args=command.call_args.args[0]
        self.assertIn('discover',args);self.assertEqual(args[args.index('-s')+1],'tests')
        self.assertFalse(any('exclude' in arg for arg in args))

    def test_archive_git_byte_attribute_is_explicit(self):
        self.assertIn('ollama/*.py -text',(ROOT/'historical_tests/.gitattributes').read_text())

    def test_required_ci_registration_check_cannot_be_silently_skipped(self):
        from scripts import run_project_checks as checks
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(checks,'SAFE_SMOKE_MODULES',('scripts.check_ollama_test_lanes',)), \
                patch.object(checks,'module_file',return_value=Path(directory)/'missing.py'):
            with self.assertRaisesRegex(RuntimeError,'registration check is missing'):
                checks.run_smoke_checks()

    def test_direct_unittest_invocation_inherits_offline_containment(self):
        # The existing launcher permits Python children only when the guard is
        # inherited. No private artifact or test-selection environment flag.
        result=subprocess.run([sys.executable,'-B','-m','unittest',
                               'tests.test_ollama_prompt_comparison','-v'],
                              cwd=ROOT,env=dict(os.environ),capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('Ran 10 tests',result.stderr)
        self.assertIn('OK',result.stderr)


if __name__=='__main__':unittest.main()

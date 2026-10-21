"""Current-source unit contracts, not a replay of historical diagnostic reports.

All transport is injected. Deliberately invalid miniature plans exercise only
rejection paths; they never stand in for an approved historical experiment.
No ignored report, historical Markdown or locally retained Git ref is required.
"""
from copy import deepcopy
import hashlib
import importlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import compare_ollama_unresolved_prompts_v1_2 as comparison
from scripts import compare_ollama_unresolved_prompts_v1_3 as source_first
from scripts import smoke_ollama_unresolved_adjudication_v1 as smoke


class DiagnosticPrerequisiteTests(unittest.TestCase):
    def test_imports_do_not_open_transport_or_start_processes(self):
        with patch('urllib.request.build_opener', side_effect=AssertionError('transport on import')), \
                patch('subprocess.Popen', side_effect=AssertionError('process on import')):
            for module in (smoke, comparison, source_first):
                importlib.reload(module)

    def test_real_metadata_preflight_uses_only_injected_metadata(self):
        calls = []

        def metadata(endpoint, payload=None, timeout=5):
            calls.append((endpoint, payload))
            self.assertIsNone(payload)
            if endpoint == 'version':
                return {'version': 'UNIT_ONLY'}
            self.assertEqual(endpoint, 'tags')
            return {'models': [{'name': smoke.MODEL, 'details': {
                'family': 'qwen3', 'parameter_size': '8.2B'}}]}

        with patch.object(smoke.shutil, 'which', return_value=None):
            first = smoke.preflight(http=metadata)
            second = smoke.preflight(http=metadata)
        self.assertEqual(first, second)
        self.assertTrue(first['ready'])
        self.assertEqual(first['inference_calls'], 0)
        self.assertEqual(calls, [('version', None), ('tags', None)] * 2)
        self.assertEqual(first['structured_output_status'],
                         'NOT_YET_TESTED_STRICT_SCHEMA_WILL_BE_REQUIRED')

    def test_unavailable_metadata_is_not_a_successful_diagnostic(self):
        def unavailable(*args, **kwargs):
            raise OSError('UNIT_ONLY unavailable')

        with patch.object(smoke.shutil, 'which', return_value=None):
            result = smoke.preflight(http=unavailable)
        self.assertFalse(result['ready'])
        self.assertEqual(result['inference_calls'], 0)
        self.assertIn('OSError', result['blocker'])

    def invalid_plan(self, expected):
        plan = {'protected_hashes': {'critical.md': expected}}
        plan['fingerprint'] = comparison.fingerprint(plan)
        return plan

    def test_changed_frozen_bytes_reject_before_transport_without_restamping(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            critical = root/'critical.md'
            original = b'UNIT_ONLY original\n'
            critical.write_bytes(original)
            plan = self.invalid_plan(hashlib.sha256(original).hexdigest())
            before = deepcopy(plan)
            critical.write_bytes(b'UNIT_ONLY changed\n')
            with patch.object(comparison, 'ROOT', root), \
                    patch.object(comparison, 'make_transport') as transport:
                with self.assertRaisesRegex(ValueError, 'Protected artifact/runner changed after freeze'):
                    comparison.run(plan)
                transport.assert_not_called()
            self.assertEqual(plan, before)
            self.assertEqual(critical.read_bytes(), b'UNIT_ONLY changed\n')

    def test_missing_critical_artifact_rejects_without_fabricated_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = self.invalid_plan(hashlib.sha256(b'UNIT_ONLY missing').hexdigest())
            before = deepcopy(plan)
            with patch.object(comparison, 'ROOT', root), \
                    patch.object(comparison, 'make_transport') as transport:
                with self.assertRaises(FileNotFoundError):
                    comparison.run(plan)
                transport.assert_not_called()
            self.assertEqual(plan, before)
            self.assertEqual(list(root.iterdir()), [])

    def test_line_ending_changes_still_reject_under_historical_byte_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'critical.md').write_bytes(b'UNIT_ONLY\r\n')
            plan = self.invalid_plan(hashlib.sha256(b'UNIT_ONLY\n').hexdigest())
            with patch.object(comparison, 'ROOT', root):
                with self.assertRaisesRegex(ValueError, 'Protected artifact/runner changed after freeze'):
                    comparison.validate_plan(plan)

    def test_invalid_seal_cannot_be_confused_with_validated_historical_plan(self):
        plan = self.invalid_plan('UNIT_ONLY invalid hash')
        plan['fingerprint'] = 'UNIT_ONLY invalid seal'
        with self.assertRaisesRegex(ValueError, 'Plan seal changed'):
            comparison.validate_plan(plan)

    def test_tracked_synthetic_holdouts_repeat_without_mutating_expectations(self):
        for module, count in ((comparison, 6), (source_first, 8)):
            before = module.HOLDOUT.read_bytes()
            first = module.load_holdout()
            second = module.load_holdout()
            self.assertEqual(first, second)
            self.assertEqual(len(first['cases']), count)
            self.assertEqual(module.HOLDOUT.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()

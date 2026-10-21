"""Exact provenance validator tests; no Git history, ignored data or inference."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from scripts import historical_source_fixtures as source


class HistoricalSourceTests(unittest.TestCase):
    def test_all_three_original_git_and_sha256_pins(self):
        self.assertEqual(len(source.PINS), 3)
        for (revision,path),pin in source.PINS.items():
            with self.subTest(revision=revision,path=path):
                data=source.read_source(revision,path)
                self.assertEqual(hashlib.sha256(data).hexdigest(),pin.sha256)
                self.assertEqual(hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest(),pin.git_blob)
                self.assertEqual(len(data),pin.size)
                compile(data,pin.filename,'exec')

    def test_original_stage2d_oracle_pin_is_unchanged_and_independent(self):
        fixture=json.loads((source.ROOT.parent/'coordinated_action_ownership_oracle_v1.json').read_text())
        expected=fixture['production_source_lf_sha256'][source.SCORER_PATH]
        self.assertEqual(source.PINS[source.STAGE2D,source.SCORER_PATH].sha256,expected)
        self.assertEqual(hashlib.sha256(source.read_source(source.STAGE2D,source.SCORER_PATH)).hexdigest(),expected)

    def test_corrupt_historical_source_fails_closed(self):
        root=Path(tempfile.mkdtemp(prefix='historical-corruption-'))
        for key,pin in source.PINS.items():
            data=source.read_source(*key)
            # Same-length mutation defeats byte-count-only validation.
            (root/pin.filename).write_bytes(b'!'+data[1:])
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'bytes do not match'):
                source.read_source(*key,fixture_root=root)

    def test_missing_source_fails_without_fallback(self):
        root=Path(tempfile.mkdtemp(prefix='historical-missing-'))
        with patch('subprocess.check_output',side_effect=AssertionError('Git forbidden')):
            with self.assertRaisesRegex(ValueError,'Missing authenticated'):
                source.read_source(source.STAGE2D,source.SCORER_PATH,fixture_root=root)

    def test_wrong_revision_path_abbreviation_and_traversal_rejected(self):
        for revision,path in [('HEAD',source.SCORER_PATH),('0791248',source.SCORER_PATH),
                              (source.STAGE2D,'../'+source.SCORER_PATH),(source.STAGE2D,source.POLICY_PATH)]:
            with self.subTest(revision=revision,path=path),self.assertRaisesRegex(ValueError,'Unregistered'):
                source.read_source(revision,path)

    def test_current_source_cannot_substitute_for_historical(self):
        root=Path(tempfile.mkdtemp(prefix='historical-substitution-'))
        current=(source.ROOT.parents[2]/source.SCORER_PATH).read_bytes()
        for revision in (source.STAGE2D,source.V122):
            pin=source.PINS[revision,source.SCORER_PATH]
            self.assertNotEqual(hashlib.sha256(current.replace(b'\r\n',b'\n')).hexdigest(),pin.sha256)
            (root/pin.filename).write_bytes(current)
            with self.assertRaises(ValueError):source.read_source(revision,source.SCORER_PATH,fixture_root=root)

    def test_historical_module_is_distinct_from_current_module(self):
        from analysis_stability import stable_evidence_scoring as native
        historical=types.ModuleType('analysis_stability.portable_historical_control')
        historical.__package__='analysis_stability'
        historical.__file__=str(source.ROOT.parents[2]/source.SCORER_PATH)
        exec(compile(source.read_source(source.STAGE2D,source.SCORER_PATH),historical.__file__,'exec'),historical.__dict__)
        self.assertIsNot(historical.build_stable_analysis,native.build_stable_analysis)
        self.assertEqual(historical.SCORING_VERSION,native.SCORING_VERSION)

    def test_v122_policy_bytes_are_isolated_from_v123(self):
        from analysis_stability import jd_metadata_policy as v22,jd_metadata_v123 as v23
        data=source.read_source(source.V122,source.POLICY_PATH)
        self.assertEqual(data,Path(v22.__file__).read_bytes().replace(b'\r\n',b'\n'))
        self.assertNotEqual(v22.SCORER_VERSION,v23.SCORER_VERSION)
        self.assertNotEqual(data,Path(v23.__file__).read_bytes().replace(b'\r\n',b'\n'))

    def test_offline_oracle_loader_works_without_git_ignored_inputs_or_cwd(self):
        from scripts import preview_coordinated_evidence_v1 as preview
        old=os.getcwd();folder=Path(tempfile.mkdtemp(prefix='no-history-cwd-'))
        read_bytes,read_text=Path.read_bytes,Path.read_text
        checkout=source.ROOT.parents[2]
        def verify_path(path):
            # A disposable checkout may itself live beneath reports/. Only
            # prerequisites inside that checkout's ignored reports/ are denied.
            relative=path.resolve().relative_to(checkout.resolve())
            if relative.parts[0] == 'reports' or '.git' in relative.parts:
                raise AssertionError('Untracked/ignored/history prerequisite forbidden')
        def bytes_only(path,*args,**kwargs):
            verify_path(path);return read_bytes(path,*args,**kwargs)
        def text_only(path,*args,**kwargs):
            verify_path(path);return read_text(path,*args,**kwargs)
        before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source.ROOT.iterdir() if p.is_file()}
        try:
            os.chdir(folder)
            with patch('subprocess.check_output',side_effect=AssertionError('Git forbidden')), \
                 patch.object(Path,'read_bytes',bytes_only),patch.object(Path,'read_text',text_only):
                oracle=preview.load_independent_oracle()
                self.assertEqual(len(oracle['parents']),5)
                for key in source.PINS:source.read_source(*key)
        finally:os.chdir(old)
        after={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source.ROOT.iterdir() if p.is_file()}
        self.assertEqual(before,after)
        self.assertFalse(list(folder.iterdir()))

    def test_fixture_inventory_is_explicit_and_byte_attributes_portable(self):
        self.assertEqual({p.name for p in source.ROOT.glob('*.py.txt')}, {pin.filename for pin in source.PINS.values()})
        self.assertIn('*.py.txt -text',(source.ROOT/'.gitattributes').read_text())
        for name in ('README.md','.gitattributes'):
            self.assertTrue((source.ROOT/name).is_file())

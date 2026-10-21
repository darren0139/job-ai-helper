"""Original predicate artifacts: genuine byte validator and portable setup tests."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests import predicate_historical_fixtures as fixture


class PredicateHistoricalFixtureTests(unittest.TestCase):
    def test_exact_archived_bytes_and_provenance(self):
        paths=fixture.verified_paths()
        provenance=json.loads((fixture.ROOT/'provenance.json').read_text())
        self.assertEqual(provenance['tree'],fixture.TREE)
        for path in paths:
            data=path.read_bytes();digest,blob,size=fixture.PINS[path.name]
            self.assertEqual(hashlib.sha256(data).hexdigest(),digest)
            self.assertEqual(provenance['files'][path.name]['sha256'],digest)
            self.assertEqual(provenance['files'][path.name]['git_blob'],blob)
            self.assertEqual(len(data),size)

    def test_original_cohort_sources_allocations_and_no_promotions(self):
        from scripts import investigate_existing_predicate_backlog_v2 as investigation
        report_path,manifest_path=fixture.verified_paths()
        report=investigation.read_sealed(report_path);manifest=investigation.read_sealed(manifest_path)
        investigation.validate_cohort(manifest['cases'])
        self.assertEqual(len(report['cases']),13)
        self.assertEqual(len({r['job_id'] for r in manifest['cases']}),9)
        self.assertEqual(report['protected_hashes'],manifest['protected_hashes'])
        self.assertEqual(len(report['protected_hashes']),150)
        for case,original in zip(report['cases'],manifest['cases']):
            self.assertEqual(case['input'],original['input'])
            self.assertEqual(case['source_versions'],original['source_versions'])
            self.assertEqual(case['parent_allocation_receipts'],original['parent_allocation_receipts'])
            self.assertEqual(case['parent_allocation_sum'],1)
            self.assertNotEqual(case['fix_justified'],'YES')
        self.assertEqual(report['summary']['confirmed_current_defects'],0)
        self.assertFalse(report['preservation']['gold_decisions_used'])

    def test_same_length_corruption_is_rejected(self):
        root=Path(tempfile.mkdtemp(prefix='predicate-corruption-'))
        for path in fixture.verified_paths():(root/path.name).write_bytes(path.read_bytes())
        for name in fixture.PINS:
            path=root/name;original=path.read_bytes();path.write_bytes(b'!'+original[1:])
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'byte identity'):
                fixture.verified_paths(root=root)
            path.write_bytes(original)

    def test_resealed_changed_input_does_not_become_an_original(self):
        root=Path(tempfile.mkdtemp(prefix='predicate-resealed-'))
        for path in fixture.verified_paths():(root/path.name).write_bytes(path.read_bytes())
        path=root/'manifest.json';data=json.loads(path.read_text())
        data['cases'][0]['input']['requirement_id']='FORGED_REQUIREMENT'
        data['fingerprint']=fixture._fingerprint({k:v for k,v in data.items() if k!='fingerprint'})
        path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'byte identity'):fixture.verified_paths(root=root)

    def test_missing_file_and_wrong_identity_fail_closed(self):
        root=Path(tempfile.mkdtemp(prefix='predicate-missing-'))
        with self.assertRaisesRegex(ValueError,'Missing authenticated'):fixture.verified_paths(root=root)
        with self.assertRaisesRegex(ValueError,'Incorrect original'):
            fixture.verified_paths(expected_manifest_identity='CURRENT_RECONSTRUCTION')

    def test_no_git_or_ignored_report_dependency_and_no_writes(self):
        original=Path.read_bytes
        reads=[]
        def read(path):
            self.assertEqual(path.parent,fixture.ROOT)
            reads.append(path.name);return original(path)
        before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in fixture.ROOT.iterdir() if p.is_file()}
        with patch('subprocess.check_output',side_effect=AssertionError('No Git')), \
             patch.object(Path,'read_bytes',read):
            report,manifest=fixture.verified_paths()
        self.assertEqual(reads,['report.json','manifest.json'])
        self.assertEqual((report.name,manifest.name),('report.json','manifest.json'))
        after={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in fixture.ROOT.iterdir() if p.is_file()}
        self.assertEqual(before,after)

    def test_fixture_newline_preservation_and_intended_file_set(self):
        self.assertEqual({p.name for p in fixture.ROOT.iterdir()},
            {'report.json','manifest.json','provenance.json','README.md','.gitattributes'})
        attributes=(fixture.ROOT/'.gitattributes').read_text()
        for name in fixture.PINS:self.assertIn(name+' -text',attributes)

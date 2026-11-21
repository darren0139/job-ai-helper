from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import unittest

from tailoring import bullet_choice_lab as lab


@contextmanager
def public_only():
    with TemporaryDirectory() as directory:
        root=Path(directory)
        for name in ('v1_public.json','validation_v1.json'):
            (root/name).write_bytes((lab.DATA/name).read_bytes())
        with patch.object(lab,'DATA',root):
            yield root


class PublicFixture(unittest.TestCase):
    def test_public_control_identity_matches_unchanged_private_controls_when_available(self):
        full=lab.load_dataset()
        with public_only():
            public=lab.load_dataset()
        self.assertEqual([c for c in full['cases'] if c['dataset']!='real'],public['cases'])
        self.assertEqual(len(public['cases']),96)
        self.assertEqual(sum(c['dataset']=='corpus' for c in public['cases']),24)
        self.assertEqual(public['optional_data']['real']['status'],'unavailable')

    def test_missing_real_cases_are_unavailable_not_passed(self):
        with public_only():
            result=lab.run_benchmarks(datasets=('real',),selectors=False)
        self.assertEqual(result['execution_status'],'unavailable')
        self.assertEqual(result['executed'],0)
        self.assertEqual(result['summary']['correct'],0)
        self.assertIsNone(result['summary']['real_accuracy'])

    def test_corrupted_optional_private_fixture_fails_closed(self):
        with public_only() as folder:
            (folder/'v1.json').write_text('{}',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'private fixture integrity'):
                lab.load_dataset()

    def test_synthetic_and_corpus_execution_and_exports_without_private_data(self):
        from tailoring.bullet_choice_lab_ui import exports
        from io import BytesIO
        from zipfile import ZipFile
        with public_only():
            result=lab.run_benchmarks(datasets=('synthetic','corpus'),selectors=False)
        self.assertEqual(result['executed'],96)
        self.assertEqual(result['summary']['controlled_denominator'],96)
        self.assertEqual(result['summary']['correct'],90)
        self.assertEqual(result['summary']['incorrect'],6)
        self.assertEqual(result['summary']['real_unlabelled'],0)
        with ZipFile(BytesIO(exports(result)[2])) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(json.loads(archive.read('availability.json'))['real']['status'],'unavailable')
        self.assertEqual(lab.compare_runs(result,result)['regressions'],[])


if __name__=='__main__':unittest.main()

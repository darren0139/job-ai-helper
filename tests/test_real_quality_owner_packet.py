"""Focused controls for the saved-evidence review packet, not semantic gold labels."""
import csv
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT/'reports/v37_real_bullet_quality/owner_packet/build_packet.py'
spec = importlib.util.spec_from_file_location('real_quality_owner_packet', PACKET)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class OwnerPacket(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = PACKET.parent.parent/'cases.json'
        if not source.exists():
            raise unittest.SkipTest('Private 20-context benchmark unavailable; portable synthetic controls run separately.')
        cls.cases = json.loads(source.read_text(encoding='utf-8'))

    def labelled_file(self, rows, path):
        with path.open('w', encoding='utf-8-sig', newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)

    def test_blind_packet_has_no_predictions_or_default_labels(self):
        rows=module.review_rows(self.cases)
        self.assertTrue(all(not r['owner_outcome'] and not r['reviewer_notes'] for r in rows))
        self.assertFalse(any('diagnostic' in k for k in rows[0]))
        rendered=module.render(self.cases)
        for c in self.cases:
            self.assertNotIn(c['diagnostic']['reason'],rendered)
            self.assertNotIn(c['diagnostic']['outcome'],rendered)
        self.assertIn('unmeasured',rendered)
        self.assertIn('does not disprove',rendered)
        self.assertIn('Set up the React',rendered)

    def test_exact_pairs_repeat_but_jd_contexts_are_not_deduplicated(self):
        rows=module.review_rows(self.cases)
        self.assertEqual(len(rows),20)
        self.assertEqual(len({r['wording_pair_id'] for r in rows}),13)
        self.assertEqual(rows[0]['wording_pair_id'],rows[1]['wording_pair_id'])
        self.assertNotEqual(rows[0]['jd_sha256'],rows[1]['jd_sha256'])

    def test_withheld_mechanisms_distinguish_observation_and_logic(self):
        categories=[r for c in self.cases for r in module.reasons(c)]
        self.assertEqual(len(categories),18)
        self.assertEqual(categories.count('Saved document authority unavailable'),6)
        self.assertEqual(categories.count('Diagnostic rule restriction despite a recorded native citation'),1)
        self.assertEqual(categories.count('Document-bound observation has no attributed citation for either wording'),11)

    def test_blank_and_partial_review_never_generates_accuracy(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'labels.csv';rows=module.review_rows(self.cases)
            self.labelled_file(rows,path)
            report=module.compare_labels(self.cases,path)
            self.assertEqual(report['labelled'],0)
            self.assertIsNone(report['semantic_accuracy'])
            # Arbitrary control label tests comparison plumbing, not bullet correctness.
            rows[0]['owner_outcome']='Complementary';self.labelled_file(rows,path)
            report=module.compare_labels(self.cases,path)
            self.assertEqual(report['labelled'],1)
            self.assertEqual(report['cases'][0]['owner_label'],'Complementary')
            self.assertIsNone(report['semantic_accuracy'])

    def test_stale_duplicate_and_invalid_labels_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'labels.csv'
            for key,value in [('jd_sha256','stale'),('wording_pair_id','other'),('base_wording','edited'),('owner_outcome','guess')]:
                rows=module.review_rows(self.cases);rows[0][key]=value;self.labelled_file(rows,path)
                with self.assertRaises(ValueError):module.compare_labels(self.cases,path)
            rows=module.review_rows(self.cases);rows[-1]=rows[0];self.labelled_file(rows,path)
            with self.assertRaises(ValueError):module.compare_labels(self.cases,path)

    def test_source_warnings_and_complementarity_are_not_owner_labels(self):
        rows=module.review_rows(self.cases)
        self.assertIn('distinct activities',rows[5]['substitution_review_prompt'])
        self.assertTrue(module.malformed_links(self.cases[6]))
        self.assertEqual(rows[6]['owner_outcome'],'')
        self.assertIn('not independent attestation',rows[6]['base_citations'])


if __name__ == '__main__':
    unittest.main()

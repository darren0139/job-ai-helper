"""Receipt fixtures exercise validation only; they are never real corpus gold labels."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from scripts import adjudicate_unresolved_requirements as cli
from scripts import prepare_unresolved_gold_review as preparation
from taxonomy_discovery import unresolved_adjudication as a
from taxonomy_discovery import unresolved_gold_review as review
from tests.ollama_current_fixtures import adjudication_artifacts


class HumanReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.enterClassContext(adjudication_artifacts())
        cls.original_bytes = review.ORIGINAL.read_bytes()
        cls.parent = review.original()
        cls.cases, cls.skipped = cli.prepare(cls.parent)
        cls.occurrences = a.load_occurrences()

    def receipt(self):
        e = self.parent['expectations'][0]
        return {'key': e['key'], 'input_fingerprint': e['input_fingerprint'],
                'source_fingerprint': self.parent['source_fingerprint'], 'origin': 'INDEPENDENT_HUMAN',
                'independent_of_model_predictions': True, 'reviewer': 'TEST RECEIPT ONLY',
                'reviewed_at': '2026-10-12T12:00:00+08:00', 'acceptable_routes': ['STRUCTURAL'],
                'source_spans': ['MongoDB, Redis, Elasticsearch'],
                'rationale': 'TEST ONLY: exercise explicit receipt grounding, never a real label',
                'source_reference': self.parent['source_path']}

    def test_pending_version_preserves_original_and_only_two_labels(self):
        m = review.versioned_manifest(self.parent, [], self.cases)
        self.assertEqual(review.ORIGINAL.read_bytes(), self.original_bytes)
        self.assertEqual(self.skipped, [])
        self.assertEqual(review.summary(m)['confirmed'], 2)
        self.assertEqual(review.summary(m)['pending'], 38)
        self.assertFalse(review.summary(m)['labeling_prerequisite_satisfied'])
        self.assertEqual([e['key'] for e in m['expectations'] if e['acceptable_routes']],
                         [list(k) for k in sorted(a.NAC)])

    def test_test_owned_pending_manifest_and_native_prepare(self):
        m = json.loads((review.ROOT / 'tests/fixtures/unresolved_adjudication_benchmark_v2.json').read_text())
        cases, skipped = cli.prepare(m)
        self.assertEqual(cases, self.cases)
        self.assertEqual(skipped, [])
        self.assertEqual(review.summary(m)['critical_pending'], [self.parent['expectations'][i]['key'] for i in [0, 3, 4, 5, 6, 7, 8]])

    def test_explicit_receipt_roundtrip_is_grounded_and_does_not_edit_parent(self):
        m = review.versioned_manifest(self.parent, [self.receipt()], self.cases)
        review.validate(json.loads(json.dumps(m)), cases=self.cases)
        self.assertEqual(m['expectations'][0]['acceptable_routes'], ['STRUCTURAL'])
        self.assertEqual(self.parent['expectations'][0]['acceptable_routes'], [])

    def test_deferral_stays_non_actionable(self):
        receipt = self.receipt(); receipt['acceptable_routes'] = []
        m = review.versioned_manifest(self.parent, [receipt], self.cases)
        self.assertEqual(m['expectations'][0]['human_review']['state'], 'DEFERRED')
        self.assertEqual(review.summary(m)['confirmed'], 2)

    def test_missing_or_model_provenance_rejected(self):
        for change in ({'origin': 'QWEN'}, {'origin': 'OPENAI'}, {'independent_of_model_predictions': False},
                       {'reviewer': ''}, {'reviewed_at': ''}, {'rationale': ''}, {'source_reference': ''},
                       {'reviewed_at': '2026-10-12T12:00:00'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                receipt = self.receipt(); receipt.update(change)
                review.versioned_manifest(self.parent, [receipt], self.cases)

    def test_stale_input_source_invalid_route_and_fabricated_spans_rejected(self):
        for change in ({'input_fingerprint': 'stale'}, {'source_fingerprint': 'stale'},
                       {'acceptable_routes': ['UNKNOWN']}, {'acceptable_routes': ['invented']},
                       {'source_spans': []}, {'source_spans': ['invented']},
                       {'acceptable_routes': ['STRUCTURAL', 'STRUCTURAL']}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                receipt = self.receipt(); receipt.update(change)
                review.versioned_manifest(self.parent, [receipt], self.cases)

    def test_duplicate_and_unknown_receipts_rejected(self):
        receipt = self.receipt()
        with self.assertRaises(ValueError): review.versioned_manifest(self.parent, [receipt, receipt], self.cases)
        receipt['key'] = [999, 'unknown']
        with self.assertRaises(ValueError): review.versioned_manifest(self.parent, [receipt], self.cases)

    def test_resealed_tampering_and_fake_inherited_label_rejected(self):
        for mutate in (lambda m: m['expectations'].reverse(),
                       lambda m: m['expectations'].append(deepcopy(m['expectations'][0])),
                       lambda m: m['expectations'][0].update(acceptable_routes=['RELATIONSHIP']),
                       lambda m: m['expectations'][0].update(human_review={'state': 'INHERITED_CONFIRMED'}),
                       lambda m: m['expectations'][0].update(critical=False)):
            m = review.versioned_manifest(self.parent, [], self.cases); mutate(m); review.seal(m)
            with self.assertRaises(ValueError): review.validate(m)

    def test_benchmark_loader_rejects_fabricated_receipt_even_when_resealed(self):
        m = review.versioned_manifest(self.parent, [self.receipt()], self.cases)
        m['expectations'][0]['human_review']['receipt']['source_spans'] = ['invented']
        review.seal(m)
        with self.assertRaisesRegex(ValueError, 'exact frozen'): cli.prepare(m)

    def test_worksheet_exact_text_and_no_proposed_gold(self):
        text, rows = review.worksheet(self.parent, self.cases, self.occurrences)
        self.assertEqual(len(rows), 40)
        for c, row in zip(self.cases, rows):
            self.assertEqual(c, row['input'])
            self.assertIn(json.dumps(c['requirement_text'], ensure_ascii=True), text)
            self.assertNotIn('evidence', row['native_source_context'])
        self.assertIn('token overlap ONLY', text)
        self.assertIn('reviewed_requirement_keys is empty', text)
        self.assertIn('Source text changes require a new frozen input', text)
        self.assertEqual(rows[0]['expectation']['acceptable_routes'], [])

    def test_review_does_not_invoke_model_execution(self):
        with patch.object(a, 'run_cases', side_effect=AssertionError('No model execution')):
            m = review.versioned_manifest(self.parent, [], self.cases)
            review.worksheet(self.parent, self.cases, self.occurrences)
        self.assertEqual(review.summary(m)['coverage']['TRUE_GAP_CANDIDATE'], 2)

    def test_preparation_refuses_overwrite_of_frozen_outputs(self):
        with patch('pathlib.Path.write_text') as write, self.assertRaises(SystemExit) as error:
            preparation.main([])
        self.assertEqual(error.exception.code, 2)
        write.assert_not_called()

    def test_blank_template_is_not_a_human_decision(self):
        receipt = self.receipt()
        receipt.update(reviewer='', reviewed_at='', acceptable_routes=[], source_spans=[],
                       rationale='', source_reference='', independent_of_model_predictions=False)
        with self.assertRaises(ValueError):
            review.versioned_manifest(self.parent, [receipt], self.cases)

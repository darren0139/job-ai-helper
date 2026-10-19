"""Diagnostic integrity controls, not replacement scoring expectations."""
import json
from pathlib import Path
import tempfile
import unittest

from analysis_stability import stable_evidence_scoring as native
from analysis_stability.coordinated_runtime import assert_analysis_publishable
from scripts import audit_coordinated_realistic_evidence as audit


class RealisticEvidenceAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.study = audit.run_study()
        cls.by_id = {r['id']: r for r in cls.study['rows']}

    def test_all_independent_inputs_are_executed_without_exceptions(self):
        fixture = json.loads(audit.FIXTURE.read_text(encoding='utf-8'))
        self.assertEqual(len(fixture['cases']), 38)
        self.assertEqual(set(self.by_id), {c['id'] for c in fixture['cases']})
        self.assertEqual(self.study['errors'], [])
        self.assertEqual({r['family'] for r in self.study['rows']}, {'embedded', 'pipeline', 'fullstack', 'backend', 'cloud'})

    def test_existing_governed_literal_controls(self):
        # These pre-existing contracts do not depend on uncertain language probes
        # or the independent safety judgments about cross-record contradiction.
        for case in ('E01', 'E02', 'E03', 'E06', 'E07', 'E08', 'E09', 'E13',
                     'E15', 'E16', 'E17', 'E21', 'E22', 'B02', 'B03', 'B04'):
            with self.subTest(case=case):
                self.assertEqual(self.by_id[case]['actual_label'], self.by_id[case]['expected_current_label'])

    def test_record_ownership_weights_and_credit_ceiling_receipts(self):
        for detail in self.study['details'].values():
            row = detail['target']
            rec = row['coordinated_action_receipt']
            self.assertEqual(rec['parent_allocation'], 1)
            if row['match_label'] in ('direct', 'weak', 'transferable'):
                self.assertEqual(len(row['evidence']), 1)
                original = rec['proofs'][row['evidence'][0]['evidence_id']]
                for key in ('text', 'source', 'evidence_id', 'section'):
                    self.assertEqual(row['evidence'][0][key], original['record'][key])
                self.assertIn(original['admission'], ('COMPLETE', 'ELIGIBLE_PARTIAL'))
                if original['admission'] == 'ELIGIBLE_PARTIAL':
                    self.assertLessEqual(row['match_value'], native.MATCH_VALUES['weak'])

    def test_review_cards_and_all_unresolved_aggregate_values_are_unavailable(self):
        for detail in self.study['details'].values():
            analysis = detail['analysis']
            for card in detail['review_cards']:
                if card['status'] == 'REVIEW_REQUIRED':
                    self.assertIn('Unavailable', card['credit_display'])
                    for key in ('deterministic_alignment_score', 'required_core_coverage_score',
                                'preferred_coverage_score', 'evidence_strength_score'):
                        self.assertIsNone(analysis[key])
            for row in analysis['canonical_requirements']:
                if row.get('coordinated_action_receipt', {}).get('disposition') == 'REVIEW_REQUIRED':
                    self.assertIsNone(row['match_label'])
                    self.assertIsNone(row['match_value'])

    def test_every_gated_payload_remains_nonpublishable(self):
        for detail in self.study['details'].values():
            self.assertTrue(detail['analysis']['development_preview_only'])
            with self.assertRaisesRegex(ValueError, 'cannot be persisted'):
                assert_analysis_publishable(detail['analysis'])

    def test_independent_expectations_and_discrepancies_are_preserved(self):
        fixture = json.loads(audit.FIXTURE.read_text(encoding='utf-8'))
        for case in fixture['cases']:
            row = self.by_id[case['id']]
            self.assertEqual(row['expected_current_label'], case['expected_current_label'])
            self.assertEqual(row['independent_semantic_label'], case['independent_semantic_label'])
            self.assertEqual(row['contract_agreement'], row['actual_label'] == case['expected_current_label'])
        # No assertion declares all research probes correct merely because the
        # implementation produced them. Discrepancies stay in the export/report.
        scratch = Path(tempfile.gettempdir()).resolve()
        if scratch.is_relative_to(audit.ROOT/'reports'):
            path = audit.write_diagnostics(scratch)
            print('Stage 2H actual diagnostics:', path, flush=True)
        # Ordinary test runs need no export or local reports directory; guarded
        # audit runs opt into artifact creation through --scratch-root reports/.

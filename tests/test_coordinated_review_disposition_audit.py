"""Offline diagnostic guard tests; no local export dependency or scoring oracle edits."""
from copy import deepcopy
import unittest

from scripts.audit_coordinated_review_dispositions import (
    audit, primary_reason, proposed_exclusion,
)


def receipt(text='Consumed REST APIs using HTTP requests and JSON responses.'):
    record = {'evidence_id': 'synthetic-independent-test-record', 'section': 'projects',
              'source': 'resume_profile.projects[0].bullets[0]', 'text': text}
    proof = {'evidence_id': record['evidence_id'], 'source': record['source'],
             'evidence_text': text, 'status': 'INCOMPLETE', 'supported_actions': [],
             'missing_actions': ['design', 'develop', 'maintain'], 'denied_actions': [],
             'ambiguities': [], 'technical_scope': 'UNPROVEN'}
    return {'disposition': 'REVIEW_REQUIRED', 'native_label': 'none',
            'obligation': {'status': 'SUPPORTED', 'conjunction': 'AND', 'raw_jd_parent_span': [0, 100]},
            'proofs': {record['evidence_id']: {'record': record, 'proof': proof, 'admission': 'REVIEW_REQUIRED'}}}


class DispositionAuditTests(unittest.TestCase):
    def test_only_reviewed_literal_exclusions_with_native_none(self):
        for text in (
            'Consumed REST APIs using HTTP requests and JSON responses.',
            'Integrated Supabase PostgREST generated REST APIs for CRUD and authentication.',
            'Configured ESP32 GPIO interrupts.',
        ):
            self.assertTrue(proposed_exclusion(receipt(text)))
        for text in ('Maintained embedded software modules.', 'Authored Java REST endpoints.',
                     'I designed and developed backend services.', 'No evidence supplied.', ''):
            self.assertFalse(proposed_exclusion(receipt(text)))

    def test_missing_actions_alone_never_authorizes_none(self):
        r = receipt('Maintained embedded software modules.')
        self.assertFalse(proposed_exclusion(r))
        r['proofs'][next(iter(r['proofs']))]['proof']['supported_actions'] = ['maintain']
        self.assertFalse(proposed_exclusion(r))

    def test_native_positive_never_vetoed(self):
        for label in ('direct', 'transferable', 'weak', None):
            r = receipt('Configured ESP32 GPIO interrupts.')
            r['native_label'] = label
            self.assertFalse(proposed_exclusion(r))

    def test_no_denial_ambiguity_or_unsupported_source_shortcut(self):
        for key, value in (('supported_actions', ['design']), ('denied_actions', ['maintain']),
                           ('ambiguities', ['AMBIGUOUS_MODALITY']), ('status', 'UNVERIFIED_SOURCE')):
            r = receipt()
            next(iter(r['proofs'].values()))['proof'][key] = value
            self.assertFalse(proposed_exclusion(r))

    def test_unknown_or_separate_record_prevents_closed_exclusion(self):
        r = receipt()
        other = deepcopy(next(iter(r['proofs'].values())))
        other['record'].update(evidence_id='second', source='resume_profile.projects[0].bullets[1]')
        other['proof'].update(evidence_id='second', source='resume_profile.projects[0].bullets[1]')
        r['proofs']['second'] = other
        self.assertFalse(proposed_exclusion(r))
        r['proofs'] = {}
        self.assertFalse(proposed_exclusion(r))

    def test_original_evidence_identity_text_and_source_must_agree(self):
        for field in ('evidence_id', 'source', 'text', 'section'):
            r = receipt()
            next(iter(r['proofs'].values()))['record'][field] = 'unverified'
            self.assertFalse(proposed_exclusion(r))

    def test_unsupported_or_ungrounded_parent_stays_review(self):
        for key, value in (('status', 'UNSUPPORTED'), ('conjunction', 'OR'), ('raw_jd_parent_span', None)):
            r = receipt()
            r['obligation'][key] = value
            self.assertFalse(proposed_exclusion(r))

    def test_secondary_factors_do_not_double_count_primary_reason(self):
        self.assertEqual(primary_reason('backend', 'Denied lifecycle'), 'EXPLICIT_LIFECYCLE_DENIAL')
        self.assertEqual(primary_reason('backend', 'Separate partial records'), 'SEPARATE_RECORDS')
        self.assertEqual(primary_reason('backend', 'Shortened object'), 'MISSING_TECHNICAL_SCOPE')
        self.assertEqual(primary_reason('backend', 'All mandatory actions'), 'API_AUTHORSHIP_GUARD')
        self.assertEqual(primary_reason('cloud', 'Maintenance only'), 'PARTIAL_OWNERSHIP')
        with self.assertRaises(ValueError):
            primary_reason('embedded', 'unexpected scenario')

    def test_annotations_do_not_mutate_actual_receipts(self):
        r = receipt()
        before = deepcopy(r)
        proposed_exclusion(r)
        self.assertEqual(r, before)

    def test_whole_jd_requires_every_parent_numeric(self):
        # Independent two-parent arithmetic, without any local dashboard export.
        rec = receipt()
        rec.update(native_selected_evidence=[], parent_allocation=1)
        rec['obligation'].update(raw_parent_text='Synthetic grounded parent',
                                 actions=[{'action': a} for a in ('design', 'develop', 'maintain')])
        target = {'requirement_id': 'parent-one', 'text': 'Synthetic grounded parent',
                  'source_provenance': [], 'match_label': None, 'coordinated_action_receipt': rec}
        other = deepcopy(target)
        other['requirement_id'] = 'parent-two'
        other['coordinated_action_receipt']['native_label'] = 'direct'
        batch = {'revision': 'independent-test', 'errors': [], 'expectations': {'case': []},
                 'rows': [{'Case': 'case', 'Job': '566 / backend', 'Scenario': 'API consumption',
                           'P3': 'REVIEW_REQUIRED', 'Withheld': 'Yes', 'Stage 2E reference': 'Matches'}],
                 'details': {'case': {'job_id': 566, 'parent_occurrence_id': 'one',
                    'after_rows': [target], 'after': {'canonical_requirements': [target, other]}}}}
        frozen = deepcopy(batch)
        first = audit(batch)
        self.assertEqual(first['hypothetical_R1']['target_review_cases_resolved'], 1)
        self.assertEqual(first['hypothetical_R1']['all_review_rows_resolved'], 1)
        self.assertEqual(first['hypothetical_R1']['withheld_after'], 1)
        self.assertEqual(batch, frozen)
        other['coordinated_action_receipt']['native_label'] = 'none'
        second = audit(batch)
        self.assertEqual(second['hypothetical_R1']['all_review_rows_resolved'], 2)
        self.assertEqual(second['hypothetical_R1']['withheld_after'], 0)

    def test_historical_applicability_uses_only_30_raw_jds(self):
        import json
        from pathlib import Path
        import tempfile
        from scripts.audit_coordinated_review_dispositions import historical_scope_inventory
        inventory = historical_scope_inventory()
        jobs = inventory['jobs']
        self.assertEqual(len(jobs), 30)
        self.assertEqual({r['job_id'] for r in jobs if r['targeted_parents']}, {16, 359, 479, 566})
        self.assertEqual(sum(len(r['targeted_parents']) for r in jobs), 5)
        root = Path(__file__).resolve().parents[1]
        oracle = json.loads((root/'tests/fixtures/coordinated_action_ownership_oracle_v1.json').read_text(encoding='utf-8'))
        self.assertEqual({p['parent_occurrence_id'] for r in jobs for p in r['targeted_parents']},
                         {p['parent_occurrence_id'] for p in oracle['parents']})
        path = Path(tempfile.gettempdir())/'stage2f_historical_scope.json'
        path.write_text(json.dumps(inventory, indent=2)+'\n', encoding='utf-8')
        print('Stage 2F raw-JD inventory:', path,
              'rows', sum(r['native_rows'] for r in jobs), sum(r['gated_rows'] for r in jobs))

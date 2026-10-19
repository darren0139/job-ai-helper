"""Independent R1 contract tests, authored before connecting it to scoring."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from analysis_stability import coordinated_policy as policy
from analysis_stability import stable_evidence_scoring as native
from analysis_stability.coordinated_r1 import exclusion_packet, recognize_activity
from scripts import coordinated_acceptance as acceptance

FIXTURE = Path(__file__).with_name('fixtures')/'coordinated_r1_contract_v1.json'


class R1ContractTests(unittest.TestCase):
    def setUp(self):
        self.parent = next(p for p in acceptance.parents() if p['obligation']['object_family'] == 'pipeline')
        self.profile = {'projects': [{'title': 'Synthetic acceptance project', 'bullets': [
            'Consumed REST APIs using HTTP requests and JSON responses.']}],
            'experience': [], 'education': [], 'skills': {}}

    def packet(self, profile=None, **overrides):
        profile = self.profile if profile is None else profile
        index = native.build_resume_evidence_index(profile, '')
        o = policy.prior.ground_to_raw_jd(self.parent['obligation'], self.parent['raw_jd'])
        proofs = {r['evidence_id']: {'record': deepcopy(r), 'proof': policy.detect(o, r, index),
                                   'admission': 'REVIEW_REQUIRED'} for r in index}
        args = dict(requirement=self.parent['requirement'], obligation=o, profile=profile,
                    raw_resume='', evidence_index=index, proofs=proofs,
                    native_final_label='none', raw_jd=self.parent['raw_jd'])
        args.update(overrides)
        return exclusion_packet(**args)

    def test_independent_positive_language_and_full_coverage(self):
        for text in json.loads(FIXTURE.read_text())['positive']:
            with self.subTest(text=text):
                r = recognize_activity(text)
                self.assertIsNotNone(r)
                self.assertEqual(r['covered_span'], [0, len(text)])
                self.assertTrue(r['activity'])
                self.profile['projects'][0]['bullets'] = [text]
                self.assertTrue(self.packet()['eligible'])

    def test_independent_adversarial_language_fails_closed(self):
        for text in json.loads(FIXTURE.read_text())['negative']:
            with self.subTest(text=text):
                self.assertIsNone(recognize_activity(text))
                self.profile['projects'][0]['bullets'] = [text]
                self.assertFalse(self.packet()['eligible'])

    def test_native_positive_ceiling_is_never_overridden(self):
        for label in ('direct', 'transferable', 'weak', None):
            self.assertFalse(self.packet(native_final_label=label)['eligible'])

    def test_original_source_identity_text_and_complete_index(self):
        index = native.build_resume_evidence_index(self.profile, '')
        self.assertFalse(self.packet(evidence_index=index[:-1])['eligible'])
        self.assertFalse(self.packet(evidence_index=index+index)['eligible'])
        for key in ('evidence_id', 'source', 'text', 'section'):
            forged = deepcopy(index)
            forged[-1][key] = 'FORGED'
            self.assertFalse(self.packet(evidence_index=forged)['eligible'])
        self.assertFalse(self.packet(proofs={})['eligible'])

    def test_extra_records_including_duplicates_are_not_silently_dropped(self):
        for text in ('Designed data pipelines.', 'We built data pipelines.', 'Unknown task.',
                     'Never maintained data pipelines.', self.profile['projects'][0]['bullets'][0]):
            p = deepcopy(self.profile)
            p['projects'][0]['bullets'].append(text)
            self.assertFalse(self.packet(p)['eligible'])
        p = deepcopy(self.profile)
        p['projects'].append(deepcopy(p['projects'][0]))
        self.assertFalse(self.packet(p)['eligible'])

    def test_unindexed_fields_and_partial_packet_fail_closed(self):
        for change in ({'summary': 'Designed embedded software.'}, {'experience': [{'bullets': ['Unknown task.']}]},
                       {'skills': {'languages': ['Java']}}, {'education': [{'degree': 'Computer science'}]},
                       {'certifications': ['Unexamined certification']}):
            p = {**deepcopy(self.profile), **change}
            self.assertFalse(self.packet(p)['eligible'])
        p = deepcopy(self.profile)
        del p['skills']
        self.assertFalse(self.packet(p)['eligible'])
        self.assertFalse(self.packet(raw_resume='Unexamined original text')['eligible'])
        self.assertFalse(self.packet(raw_jd='')['eligible'])
        self.assertFalse(self.packet(profile={})['eligible'])

    def test_metadata_is_not_negative_evidence(self):
        p = deepcopy(self.profile)
        p['projects'][0]['bullets'] = []
        self.assertFalse(self.packet(p)['eligible'])
        for title in ('Designed and developed software', 'API author', 'Unknown title'):
            p = deepcopy(self.profile)
            p['projects'][0]['title'] = title
            self.assertFalse(self.packet(p)['eligible'])

    def test_scope_negation_optional_and_boolean_guards(self):
        for field, value in (('status', 'UNSUPPORTED'), ('conjunction', 'OR'),
                             ('negation_present', True), ('optional_qualifiers', [{'text': 'optional'}])):
            o = policy.prior.ground_to_raw_jd(self.parent['obligation'], self.parent['raw_jd'])
            o[field] = value
            self.assertFalse(self.packet(obligation=o)['eligible'])

    def test_receipts_are_original_and_inputs_unchanged(self):
        frozen = deepcopy(self.profile)
        result = self.packet()
        self.assertTrue(result['eligible'])
        self.assertEqual(self.profile, frozen)
        self.assertEqual(len([r for r in result['records'] if r['classification'] == 'EXCLUDED_ACTIVITY']), 1)
        for r in result['records']:
            self.assertTrue(r['source_verified'])
            self.assertTrue(r['evidence_id'])
            self.assertTrue(r['source'])
            self.assertTrue(r['text'])


class R1AcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from scripts import coordinated_batch_dashboard as dashboard
        cls.dashboard = dashboard
        cls.batch = dashboard.run_batch(dashboard.revision_key())
        cls.expected = json.loads(FIXTURE.read_text())

    def test_all_60_and_exact_fourteen_changed_cases(self):
        totals = self.dashboard.totals(self.batch)
        self.assertEqual({k: totals[k] for k in self.expected['expected_counts']}, self.expected['expected_counts'])
        self.assertEqual(totals['reference_mismatches'], 14)
        self.assertEqual(totals['current_mismatches'], 0)
        self.assertEqual(totals['independent_checks'], totals['independent_agreements'])
        self.assertEqual(len({r['Case'] for r in self.batch['rows']}), 60)
        actual = {(r['Job'].split(' / ')[1], r['Scenario']) for r in self.batch['rows']
                  if r['Disposition'] == 'R1_EXCLUDED_NATIVE_NONE'}
        expected = {(family, scenario) for family, cases in self.expected['resolved_selected_cases'].items()
                    for scenario in cases}
        self.assertEqual(actual, expected)
        for summary in self.batch['rows']:
            pair = (summary['Job'].split(' / ')[1], summary['Scenario'])
            if pair not in expected:
                self.assertEqual(summary['Stage 2E reference'], 'Matches')
            row = self.batch['details'][summary['Case']]['after_rows'][0]
            if row['match_label'] is not None:
                self.assertEqual(row['match_value'], native.MATCH_VALUES[row['match_label']])

    def test_twenty_rows_independent_parents_receipts_and_nulls(self):
        resolved = []
        for result in self.batch['details'].values():
            rows = result['after']['canonical_requirements']
            for row in rows:
                rec = row.get('coordinated_action_receipt', {})
                if rec.get('disposition') == 'REVIEW_REQUIRED':
                    self.assertIsNone(row['match_label'])
                    self.assertIsNone(row['match_value'])
                    self.assertIsNone(result['after']['deterministic_alignment_score'])
                if rec.get('disposition') != 'R1_EXCLUDED_NATIVE_NONE':
                    continue
                resolved.append(row)
                self.assertEqual(rec['native_label'], 'none')
                self.assertEqual(row['match_value'], 0)
                self.assertEqual(rec['synthetic_parent_contribution'], 0)
                self.assertEqual(rec['parent_allocation'], 1)
                self.assertEqual(row['evidence'], [])
                proof = rec['r1_exclusion']
                self.assertTrue(proof['eligible'])
                self.assertTrue(proof['complete_supplied_index_verified'])
                self.assertEqual({r['evidence_id'] for r in proof['records']}, set(rec['proofs']))
                self.assertEqual(rec['stages'][-1]['capped_label'], 'none')
                for r in proof['records']:
                    original = rec['proofs'][r['evidence_id']]['record']
                    for key in ('text', 'source', 'section', 'evidence_id'):
                        self.assertEqual(r[key], original[key])
                self.assertTrue(result['after']['development_preview_only'])
            if result['job_id'] == 566:
                targets = [r for r in rows if r.get('coordinated_action_receipt')]
                self.assertEqual(len(targets), 2)
                if result['scenario'] in ('API consumption', 'PostgREST integration', 'Zero-overlap topic recovery'):
                    self.assertTrue(all(r['match_label'] == 'none' for r in targets))
                    self.assertIsNotNone(result['after']['deterministic_alignment_score'])
        self.assertEqual(len(resolved), self.expected['resolved_canonical_rows'])

    def test_native_positive_recovery_and_partial_none_remain_review(self):
        for family, scenario, label in (
            ('embedded', 'Zero-overlap topic recovery', 'direct'),
            ('fullstack', 'Maintenance only', 'none'),
            ('pipeline', 'Shortened object', 'none'),
        ):
            result = next(r for r in self.batch['details'].values() if r['scenario'] == scenario
                          and r['after_rows'][0]['coordinated_action_receipt']['obligation']['object_family'] == family)
            row = result['after_rows'][0]
            self.assertEqual(row['coordinated_action_receipt']['native_label'], label)
            self.assertIsNone(row['match_value'])

    def test_extra_originals_block_r1_through_actual_pipeline(self):
        parent = next(p for p in acceptance.parents() if p['obligation']['object_family'] == 'pipeline')
        base = 'Consumed REST APIs using HTTP requests and JSON responses.'
        for extra in ('Designed '+parent['obligation']['object']+'.', 'Unknown task.',
                      'We developed data pipelines.', 'Never maintained data pipelines.', base):
            analysis = acceptance.analyze(parent, [base, extra], True)
            row = next(r for r in analysis['canonical_requirements'] if
                       r.get('scoring_parent_occurrence_id') == parent['parent_occurrence_id'])
            self.assertEqual(row['coordinated_action_receipt']['disposition'], 'REVIEW_REQUIRED')
            self.assertIsNone(row['match_value'])

    def test_version_fingerprint_and_persistence_block_for_r1_none(self):
        from unittest.mock import patch
        from analysis_stability import coordinated_integration as integration
        from analysis_stability.coordinated_runtime import assert_analysis_publishable
        from job_discovery.matching import current_match_versions
        from database import job_match_manager as matches, analysis_cache_manager as cache
        parent = next(p for p in acceptance.parents() if p['obligation']['object_family'] == 'embedded')
        evidence = acceptance.scenarios(parent)['API consumption']
        current = acceptance.analyze(parent, evidence, True)
        self.assertEqual(current['scoring_version'], integration.IDENTITIES['scoring_version'])
        self.assertNotEqual(current['scoring_version'], 'stable-evidence-v1.18-phase6d22')
        self.assertEqual(current_match_versions()['scoring_version'], native.SCORING_VERSION)
        changed = {**integration.IDENTITIES, 'coordinated_review_disposition_policy_version': 'cache-probe'}
        with patch.object(integration, 'IDENTITIES', changed):
            other = acceptance.analyze(parent, evidence, True)
        self.assertNotEqual(current['input_fingerprint'], other['input_fingerprint'])
        for flags in (current, {**current, 'development_preview_only': False}):
            with self.assertRaisesRegex(ValueError, 'cannot be persisted'):
                assert_analysis_publishable(flags)
        with patch.object(matches, 'init_job_match_schema', side_effect=AssertionError('DB forbidden')):
            with self.assertRaisesRegex(ValueError, 'cannot be persisted'):
                matches.save_job_match_snapshot(discovered_job_id=1, job_content_hash='synthetic',
                    evidence_fingerprint='synthetic', match_version='synthetic',
                    scoring_version=current['scoring_version'], taxonomy_version=current['capability_taxonomy_version'],
                    jd_profile={}, evidence_snapshot=[], stable_analysis=current, summary={})
        with patch.object(cache, 'init_analysis_cache', side_effect=AssertionError('DB forbidden')):
            with self.assertRaisesRegex(ValueError, 'cannot be persisted'):
                cache.save_analysis_snapshot(application_id=1, input_fingerprint='synthetic',
                    report={'stable_analysis': current}, analysis_model='offline')

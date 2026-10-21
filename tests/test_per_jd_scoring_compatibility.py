"""Independent current-source, historical rejection and allocation controls."""
from copy import deepcopy
import hashlib
import unittest
from unittest.mock import patch

from analysis_stability.stable_evidence_scoring import (
    SCORING_VERSION, MATCH_VALUES, compute_deterministic_alignment,
)
from database import analysis_cache_manager as cache
from job_discovery import matching
from tailoring.phase8_score_explainability import build_score_breakdown
from taxonomy_discovery import coverage_presentation as coverage
from tests.governed_review_fixtures import isolated_taxonomy
from tests.per_jd_accounting_fixtures import (
    HISTORICAL_FIXTURE, HISTORICAL_SHA256, HISTORICAL_SCORER,
    load_historical_bundle, historical_accounting_context, current_live_analysis,
)


class PerJDScoringCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(isolated_taxonomy(published=True))

    def historical_job(self):
        return next(j for j in load_historical_bundle()['snapshot']['audit']['corpus']['jobs']
                    if j['job_id'] == 163)

    def test_actual_current_analysis_has_independent_counts_and_no_candidate_credit(self):
        raw, stable = current_live_analysis(3, 4, 1)
        before = deepcopy(stable)
        view = coverage.jd_coverage(None, None, raw_jd_text=raw, stable_analysis=stable)
        self.assertEqual(stable['scoring_version'], SCORING_VERSION)
        self.assertEqual(stable['capability_taxonomy_version'], 'phase6d-capability-taxonomy-v1.6')
        self.assertEqual((view['analysis_item_count'], view['capability_resolved'],
                          view['technology_identity_resolved'], view['additional_analysis_items']), (8, 3, 1, 5))
        self.assertEqual((view['denominator'], view['percentage']), (3, 100))
        self.assertTrue(all(r['match_label'] == 'none' and r['match_value'] == 0
                            for r in stable['canonical_requirements']))
        self.assertEqual(stable['deterministic_alignment_score'], 0)
        self.assertEqual(stable, before)

    def test_current_results_and_requirement_identities_repeat(self):
        first = current_live_analysis(3, 4, 1)
        self.assertEqual(first, current_live_analysis(3, 4, 1))
        rows = first[1]['canonical_requirements']
        self.assertEqual(len({r['requirement_id'] for r in rows}), 8)

    def test_historical_fixture_keeps_its_identity_and_exact_bytes(self):
        bundle = load_historical_bundle()
        self.assertEqual(hashlib.sha256(HISTORICAL_FIXTURE.read_bytes()).hexdigest(), HISTORICAL_SHA256)
        self.assertEqual({j['baseline_stable_analysis']['scoring_version']
                          for j in bundle['snapshot']['audit']['corpus']['jobs']}, {HISTORICAL_SCORER})
        self.assertNotEqual(HISTORICAL_SCORER, SCORING_VERSION)
        rows = self.historical_job()['baseline_stable_analysis']['canonical_requirements']
        self.assertTrue({'req_2f6aedb603aa', 'req_6677d37f660c'} <= {r['requirement_id'] for r in rows})

    def test_positive_historical_evidence_cannot_bypass_currentness(self):
        job = self.historical_job()
        self.assertTrue(any(r['match_label'] == 'direct'
                            for r in job['baseline_stable_analysis']['canonical_requirements']))
        with patch.object(coverage.maintenance, 'currentness') as review:
            with self.assertRaisesRegex(ValueError, '^Stale/incompatible analysis: scoring_version$'):
                coverage.jd_coverage(None, None, raw_jd_text=job['frozen_inputs']['raw_jd_text'],
                                     stable_analysis=job['baseline_stable_analysis'])
            review.assert_not_called()

    def test_stale_only_aggregate_is_unavailable_not_a_zero_percentage(self):
        job = self.historical_job()
        view = coverage.analyzed_jobs_coverage(None, None, [{
            'job_id': 163, 'status': 'current', 'raw_jd_text': job['frozen_inputs']['raw_jd_text'],
            'stable_analysis': job['baseline_stable_analysis']}])
        self.assertEqual((view['eligible_analyzed_jobs'], view['pending_analyzed_jobs']), (0, 1))
        self.assertEqual((view['numerator'], view['denominator']), (0, 0))  # empty accounting, not scores
        self.assertIsNone(view['percentage'])
        self.assertEqual(view['jobs'], [])
        self.assertEqual(view['pending'][0]['reason'], 'Stale/incompatible analysis: scoring_version')

    def test_current_job_and_aggregate_accounting_agree_and_exclude_stale_history(self):
        raw, stable = current_live_analysis(2, 3)
        old = self.historical_job()
        records = [{'job_id': 1, 'status': 'current', 'raw_jd_text': raw, 'stable_analysis': stable},
                   {'job_id': 163, 'status': 'current', 'raw_jd_text': old['frozen_inputs']['raw_jd_text'],
                    'stable_analysis': old['baseline_stable_analysis']}]
        single = coverage.jd_coverage(None, None, raw_jd_text=raw, stable_analysis=stable)
        aggregate = coverage.analyzed_jobs_coverage(None, None, records)
        self.assertEqual((aggregate['numerator'], aggregate['denominator'], aggregate['percentage']), (2, 2, 100))
        self.assertEqual(aggregate['additional_analysis_items'], 3)
        self.assertEqual(aggregate['pending_analyzed_jobs'], 1)
        self.assertEqual(single['capability_resolved'], aggregate['numerator'])
        self.assertEqual(single['denominator'], aggregate['denominator'])

    def test_historical_replay_context_restores_real_currentness_even_on_exception(self):
        bundle = load_historical_bundle()
        original = matching.current_match_versions
        with self.assertRaisesRegex(RuntimeError, 'UNIT_ONLY'):
            with historical_accounting_context(bundle):
                self.assertEqual(matching.current_match_versions()['scoring_version'], HISTORICAL_SCORER)
                raise RuntimeError('UNIT_ONLY')
        self.assertIs(matching.current_match_versions, original)
        self.assertEqual(matching.current_match_versions()['scoring_version'], SCORING_VERSION)
        self.test_positive_historical_evidence_cannot_bypass_currentness()

    def test_current_receipts_cannot_be_used_in_historical_adapter(self):
        bundle = load_historical_bundle()
        bundle['snapshot']['manifest']['scoring_version'] = SCORING_VERSION
        with self.assertRaisesRegex(ValueError, 'Not the historical v1.16'):
            with historical_accounting_context(bundle):
                self.fail('Must not enter a historical context for current data')

    def test_cache_lookup_uses_current_identity_and_reports_old_snapshot_as_stale(self):
        job = {'id': 123, 'content_hash': 'SYNTHETIC_JD'}
        context = {'evidence_fingerprint': 'SYNTHETIC_EMPTY_PROFILE'}
        versions = matching.current_match_versions()
        old = {'job_content_hash': 'SYNTHETIC_JD', 'evidence_fingerprint': 'SYNTHETIC_EMPTY_PROFILE',
               'match_version': versions['match_version'], 'scoring_version': HISTORICAL_SCORER,
               'taxonomy_version': versions['taxonomy_version'],
               'stable_analysis': {'technology_registry_version': versions['technology_registry_version']}}
        with patch.object(matching, 'get_job_match_snapshot', return_value=None) as lookup, \
                patch.object(matching, 'get_latest_job_match_snapshot', return_value=old), \
                patch.object(matching, 'save_job_match_snapshot', side_effect=AssertionError('Read only')):
            result = matching.inspect_job_match(job, context=context)
        self.assertEqual(lookup.call_args.kwargs['scoring_version'], SCORING_VERSION)
        self.assertEqual(result['status'], 'stale')
        self.assertIn('stable scoring version changed', result['stale_reasons'])
        self.assertNotEqual(result['identity']['scoring_version'], old['scoring_version'])

    def test_stale_explicit_application_binding_is_rejected_before_storage(self):
        job = self.historical_job()
        raw = job['frozen_inputs']['raw_jd_text']
        with patch.object(cache.base_manager, 'init_db', side_effect=AssertionError('DB forbidden')) as init, \
                patch.object(cache, '_connect', side_effect=AssertionError('DB forbidden')):
            with self.assertRaisesRegex(ValueError, 'Analysis is stale; refresh explicitly before binding'):
                cache.persist_explicit_application_analysis(
                    application_id=1, input_fingerprint='SYNTHETIC',
                    report={'raw_jd_text': raw, 'stable_analysis': job['baseline_stable_analysis']},
                    analysis_model='NO_MODEL', resume_filename='NO_RESUME', raw_jd_text=raw)
            init.assert_not_called()

    def test_direct_weak_none_arithmetic_preserves_independent_parent_allocations(self):
        rows = [{'requirement_id': str(i), 'text': 'Synthetic allocation', 'importance': 'required',
                 'atomic_group_id': 'shared' if i < 2 else 'other', 'score_eligible': True,
                 'match_label': label, 'match_value': MATCH_VALUES[label], 'evidence_strength': strength}
                for i, label, strength in [(0, 'direct', 5), (1, 'weak', 1), (2, 'none', 0)]]
        before = deepcopy(rows)
        score = compute_deterministic_alignment(rows)
        # Required weight 4: shared children get 2 each; other parent gets 4.
        # (2*1 + 2*.2 + 4*0)/8 = 30%; evidence strength mean = 60%.
        self.assertEqual((score['required_core_coverage_score'], score['deterministic_alignment_score']), (30, 33))
        breakdown = build_score_breakdown({'canonical_requirements': rows, **score})
        self.assertTrue(breakdown['score_parity'])
        self.assertEqual(rows, before)

    def test_review_required_withholds_alignment_and_remains_unpublishable(self):
        rows = [{'requirement_id': 'SYNTHETIC_REVIEW', 'text': 'Synthetic unresolved ownership',
                 'importance': 'required', 'score_eligible': True, 'match_label': None, 'match_value': None,
                 'coordinated_action_receipt': {'disposition': 'REVIEW_REQUIRED'}}]
        before = deepcopy(rows)
        score = compute_deterministic_alignment(rows)
        self.assertIsNone(score['deterministic_alignment_score'])
        self.assertIsNone(rows[0]['match_value'])
        self.assertEqual(score['score_publication_status'], 'WITHHELD_PENDING_POLICY_REVIEW')
        from analysis_stability.coordinated_runtime import assert_analysis_publishable
        with self.assertRaisesRegex(ValueError, 'cannot be persisted or published'):
            assert_analysis_publishable({'scoring_version': SCORING_VERSION,
                                        'canonical_requirements': rows, **score})
        self.assertEqual(rows, before)


if __name__ == '__main__':
    unittest.main()

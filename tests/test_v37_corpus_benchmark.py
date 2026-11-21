"""Focused source strategy, geometry, and native-result contracts."""
from __future__ import annotations

import unittest

from tailoring.phase9f_v365_jd_evidence import audit_fragment
from tailoring.phase9f_v37_corpus_benchmark import (
    build_case_model, native_outcome, selection_trials, slate_metrics, source_constraint_preflight,
)
from tailoring.phase9f_certified_selection_v36 import MAX_COUNT_DELTA, MAX_TOTAL_EDITS


def fixture():
    both = 'Added Python unit tests.'
    base = 'Built a Python unit testing harness.'
    lib = 'Added API regression coverage with Python.'
    audit = {'verified': True, 'projects': [
        {'project': 'Synthetic project', 'base': [{'text': both}, {'text': base}],
         'library': [{'text': both}, {'text': lib}], 'final': [{'text': both}]},
    ]}
    requirements = [
        {'requirement_id': 'test', 'text': 'Use Python for unit testing',
         'parent_text': 'Use Python for unit testing', 'importance': 'core'},
        {'requirement_id': 'api', 'text': 'API regression coverage',
         'parent_text': 'API regression coverage', 'importance': 'preferred',
         'scoring_parent_occurrence_id': 'parent-api', 'group_weight_fraction': 0.5},
    ]
    matches = [{**req, 'requirement_text': req['text'], 'match_label': 'direct',
                'coverage_points': weight} for req, weight in zip(requirements, (10, 4))]
    case = {'audit': audit, 'projects': {'candidate_project_ranking': [
        {'title': 'Synthetic project', 'requirement_matches': matches},
    ]}, 'raw_jd_text': 'Use Python for unit testing. API regression coverage.',
        'baseline': {'stable_analysis': {'canonical_requirements': requirements}}}

    def evaluator(*, bullets, ranking_row):
        return [{'bullet_index': i, 'bullet_text': bullet,
                 'supported_requirement_ids': ['test'] if bullet != lib else ['api']}
                for i, bullet in enumerate(bullets)]

    return case, evaluator, both


class CorpusBenchmark(unittest.TestCase):
    def test_all_source_strategies_use_same_model_and_exact_duplicate_provenance(self):
        case, evaluator, both = fixture()
        trials, proposals = selection_trials(case, evaluator=evaluator)
        self.assertEqual({key: value['status'] for key, value in trials.items()},
                         {key: 'optimal_proxy' for key in ('base_only', 'library_only', 'mixed')})
        self.assertEqual(trials['base_only']['metrics']['selection_proxy_saved_points'], 10)
        self.assertEqual(trials['library_only']['metrics']['selection_proxy_saved_points'], 14)
        self.assertEqual(trials['mixed']['metrics']['selection_proxy_saved_points'], 14)
        self.assertNotIn('native', trials['mixed'])
        shared = next(r for r in proposals['mixed']['source_comparison']['projects'][0]['candidates']
                      if r['text'] == both)
        self.assertEqual(set(shared['source_labels']), {'Selected Base', 'Evidence Library', 'Current final'})

    def test_shared_saved_requirement_does_not_add_points_or_inflate_parent(self):
        from tailoring.phase9f_v365_jd_evidence import requirement_catalog
        case, evaluator, _ = fixture()
        model, _ = build_case_model(case['audit'], case['projects'], evaluator=evaluator)
        catalog = requirement_catalog(case['baseline'], case['projects'])
        stats = slate_metrics(model, (0, 1, 2), catalog, case['raw_jd_text'])
        self.assertEqual(stats['selection_proxy_saved_points'], 14)
        self.assertEqual(len(stats['required_core_lexical_links']), 1)
        self.assertEqual(stats['required_core_lexical_links'][0]['support'], 'shared')
        self.assertEqual(stats['preferred_bonus_lexical_links'][0]['saved_parent_fraction'], 0.5)

    def test_native_ties_and_layout_mismatch_are_not_proxy_wins(self):
        native = {'status': 'verified', 'score': 31, 'pages': 1, 'hard_regressions': [],
                  'scoring_version': 'test', 'jd_sha256': 'jd', 'layout_reference_sha256': 'layout'}
        variants = {key: {'native': dict(native)} for key in ('base_only', 'library_only', 'mixed')}
        self.assertEqual(native_outcome(variants), 'tie')
        variants['mixed']['native']['score'] = 32
        self.assertEqual(native_outcome(variants), 'mixed')
        variants['mixed']['native']['layout_reference_sha256'] = 'other'
        self.assertEqual(native_outcome(variants), 'unavailable')
        variants['mixed']['native']['status'] = 'fit_failed'
        self.assertEqual(native_outcome(variants), 'failure')

    def test_historical_566_and_632_clipped_coordination_traces_to_parent(self):
        for fragment, parent in (
            ('· Design, build', '· Design, build and maintain scalable backend services and API'),
            ('Identify, analyze', 'Identify, analyze, and resolve coding bugs in a timely manner'),
        ):
            with self.subTest(fragment=fragment):
                got = audit_fragment(fragment, parent_sentence=parent, raw_jd_text=parent)
                self.assertEqual(got['source_status'], 'exact_span')
                self.assertEqual(got['grammar_status'], 'clipped_boundary')
                self.assertFalse(got['eligible_for_bonus_explanation'])
        availability = 'Available for 24/7 standby and open to working overtime or in shift roles as needed'
        got = audit_fragment(availability, parent_sentence=availability, raw_jd_text=availability)
        self.assertEqual(got['grammar_status'], 'no_boundary_warning')

    def test_source_preflight_accounts_for_mandatory_removals_and_minimum_replacements(self):
        original = MAX_TOTAL_EDITS + MAX_COUNT_DELTA
        owned = tuple(range(2 * original))
        model = {'baseline_count': original, 'baseline_indices': frozenset(range(original)),
                 'groups': [({'project': 'With source'}, {}, owned, tuple(range(original)))]}
        diagnostic = source_constraint_preflight(model, set(owned) - model['baseline_indices'])
        self.assertEqual(diagnostic['mandatory_original_removals'], original)
        self.assertEqual(diagnostic['minimum_new_memberships'], MAX_TOTAL_EDITS)
        self.assertGreater(diagnostic['minimum_membership_edits'], diagnostic['maximum_membership_edits'])
        self.assertEqual(diagnostic['projects_without_source_wording'], [])


if __name__ == '__main__':
    unittest.main()

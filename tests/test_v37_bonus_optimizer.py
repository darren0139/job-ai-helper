import unittest

from tailoring.phase9f_v37_bonus_coverage import bonus_catalog, bonus_summary
from tailoring.phase9f_v37_hard_floor import research_disposition, select_protected, verified_research_trial
from tests.test_v37_bonus_coverage import requirement
from tests.test_v37_hard_floor import DIRECT, WEAK, bullet


class BonusOptimizerTests(unittest.TestCase):
    lead = bullet('Built the software system.', lead=True)
    catalog = {'core': {'importance': 'core', 'weight': 3},
               'support': {'importance': 'supporting', 'weight': 2},
               'preferred': {'importance': 'preferred', 'weight': 1}}

    def select(self, choices, *, cap=50, slots=2, existing=(), order=('supporting', 'preferred')):
        return select_protected([self.lead, *choices], self.catalog, {'core': WEAK}, max_bullets=slots,
                                max_words=cap, sources={'base', 'library'}, existing=existing, bonus_order=order)

    def test_equal_core_prefers_positive_supporting_and_preferred(self):
        for bonus in ('support', 'preferred'):
            with self.subTest(bonus=bonus):
                plain = bullet('Wrote unit tests', {'core': WEAK})
                extra = bullet('Wrote unit tests and configured deployment tooling', {'core': WEAK, bonus: DIRECT},
                               source='library')
                self.assertEqual(self.select([plain, extra], order=())['selected'][1]['text'], plain['text'])
                result = self.select([plain, extra])
                self.assertEqual(result['selected'][1]['text'], extra['text'])
                self.assertEqual(result['selected'][1]['sources'], ['library'])

    def test_policy_order_is_explicit_under_bonus_conflict(self):
        choices = [bullet('Supporting option', {'core': WEAK, 'support': DIRECT}),
                   bullet('Preferred option', {'core': WEAK, 'preferred': DIRECT})]
        self.assertEqual(self.select(choices)['selected'][1]['text'], 'Supporting option')
        self.assertEqual(self.select(choices, order=('preferred','supporting'))['selected'][1]['text'], 'Preferred option')

    def test_equivalent_coverage_and_words_keep_existing_wording(self):
        candidates = [bullet('Wrote unit tests', {'core': WEAK, 'support': DIRECT}),
                      bullet('Added unit tests', {'core': WEAK, 'support': DIRECT}, source='library')]
        result = self.select(candidates, existing={('Project', 'Wrote unit tests')})
        self.assertEqual(result['selected'][1]['text'], 'Wrote unit tests')

    def test_shorter_bullet_leaves_room_for_two_distinct_bonus_requirements(self):
        common = {'core': WEAK}
        compact = bullet('Wrote unit tests', common)
        longer = bullet('Wrote unit tests and configured a Docker build for integration workflows',
                        {**common, 'support': DIRECT})
        support = bullet('Configured Docker', {'support': DIRECT})
        preferred = bullet('Queried SQL databases', {'preferred': DIRECT})
        roomy = self.select([compact,longer], cap=20)
        self.assertEqual(roomy['selected'][1]['text'], longer['text'])
        tight = self.select([compact,longer,support,preferred], slots=4, cap=12)
        self.assertEqual({r['text'] for r in tight['selected']}, {self.lead['text'], compact['text'],
                                                               support['text'], preferred['text']})

    def test_verified_tie_retains_existing_unless_research_coverage_improves(self):
        identity = {'pages': 1, 'status': 'verified', 'jd_sha256': 'jd', 'scoring_version': 'version',
                    'layout_reference_sha256': 'layout', 'requirements': []}
        baseline = {**identity, 'score': 12}
        before = {'categories': {'supporting': {'earned': 1}, 'preferred': {'earned': 0}}}
        after = {'categories': {'supporting': {'earned': 1}, 'preferred': {'earned': 1}}}
        tie = verified_research_trial(baseline, baseline)
        self.assertEqual(research_disposition(tie, before, before), 'retain_existing')
        self.assertEqual(research_disposition(tie, before, after), 'research_coverage_improvement_for_review')
        regression = verified_research_trial(baseline, {**baseline, 'score': 11})
        self.assertEqual(research_disposition(regression, before, after), 'withheld')


class SupportingCompetitionTests(unittest.TestCase):
    """Synthetic optimizer fixtures, independent of real corpus evidence."""

    orders = (('supporting', 'preferred'), ('preferred', 'supporting'))

    def setUp(self):
        self.opening = bullet('Built the deployment platform.', lead=True)
        self.core = bullet('Wrote regression tests.', {'hard': WEAK})
        self.support = bullet('Configured container builds.', {'docker': DIRECT}, source='library')
        self.preferred = bullet('Queried SQL databases.', {'sql': DIRECT}, source='library')
        parent = 'Familiarity with Docker and Kubernetes'
        pinned = [requirement('docker', 'Familiarity with Docker', 'supporting', parent, .5),
                  requirement('k8s', 'Kubernetes', 'supporting', parent, .5),
                  requirement('sql', 'Knowledge of SQL is preferred', 'preferred'),
                  requirement('hard', 'Perform software testing', 'core')]
        jd = '\n'.join([parent, pinned[2]['text'], pinned[3]['text']])
        self.catalog = bonus_catalog(pinned, jd, expected_jd=jd)

    def solve(self, extra, order, *, slots=4, cap=30, sources=None, fixed=None):
        return select_protected([self.opening, self.core, *extra], self.catalog, {'hard': WEAK},
                                max_bullets=slots, max_words=cap, sources=sources or {'base', 'library'},
                                bonus_order=order, fixed_links=fixed)

    def test_supporting_only_preferred_only_and_both(self):
        for order in self.orders:
            for extra, expected in (([self.support], (-1000000, 0)),
                                    ([self.preferred], (0, -1000000)),
                                    ([self.support, self.preferred], (-1000000, -1000000))):
                with self.subTest(order=order, expected=expected):
                    result = self.solve(extra, order)
                    stages = result['objectives']
                    self.assertEqual((stages['supporting'], stages['preferred']), expected)
                    self.assertEqual(result['floors']['hard'], WEAK)
                    self.assertIn(self.core['text'], [r['text'] for r in result['selected']])
        self.assertEqual(self.catalog['docker']['fraction'] + self.catalog['k8s']['fraction'], 1)
        self.assertEqual(self.catalog['docker']['weight'], 1)

    def test_one_slot_contest_and_infeasible_individual_floor(self):
        for order, winner in zip(self.orders, (self.support, self.preferred), strict=True):
            result = self.solve([self.support, self.preferred], order, slots=3, cap=10)
            self.assertIn(winner['text'], [r['text'] for r in result['selected']])
            self.assertIn(self.core['text'], [r['text'] for r in result['selected']])
            self.assertEqual(self.solve([self.support], order, slots=2)['objectives']['supporting'], 0)
            invalid = self.solve([self.support], order, slots=1)
            self.assertEqual(invalid['reason'], 'floor_or_budget_conflict')
            restricted = self.solve([self.support, self.preferred], order, sources={'base'})
            self.assertEqual(restricted['objectives']['supporting'], 0)
            self.assertEqual(restricted['objectives']['preferred'], 0)

    def test_strength_breaks_summary_witness_tie_without_duplicate_credit(self):
        lower, higher = {'label': 'direct', 'strength': 2}, {'label': 'direct', 'strength': 4}
        links = {'short project': {'docker': lower}, 'detailed project': {'docker': higher}}
        summary = bonus_summary(self.catalog, links, list(links))
        row = next(r for r in summary['requirements'] if r['id'] == 'docker')
        self.assertEqual((row['earned'], row['witness_count'], row['best']['strength']), (1, 2, 4))
        short = bullet('Configured Docker.', {'docker': lower})
        detailed = bullet('Configured Docker for regression build isolation.', {'docker': higher}, source='library')
        for order in self.orders:
            result = self.solve([short, detailed], order, slots=3)
            self.assertIn(short['text'], [r['text'] for r in result['selected']])
            self.assertEqual(result['objectives']['supporting'], -1000000)

    def test_fixed_skills_and_project_links_count_once(self):
        fixed = {'docker': DIRECT}
        for order in self.orders:
            result = self.solve([self.support, self.preferred], order, slots=3, fixed=fixed)
            self.assertEqual(result['objectives']['supporting'], -1000000)
            self.assertIn(self.preferred['text'], [r['text'] for r in result['selected']])
            self.assertNotIn(self.support['text'], [r['text'] for r in result['selected']])
        links = {'Skills': fixed, 'project': {'docker': DIRECT}}
        summary = bonus_summary(self.catalog, links, ['Skills', 'project', 'project'])
        self.assertEqual(summary['categories']['supporting']['earned'], 1)
        self.assertEqual(next(r for r in summary['requirements'] if r['id'] == 'docker')['witness_count'], 2)

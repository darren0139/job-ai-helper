import unittest

from tailoring.phase9f_v37_hard_floor import select_protected, verified_research_trial


DIRECT = {'label': 'direct', 'strength': 4}
WEAK = {'label': 'weak', 'strength': 2}


def bullet(text, links=None, *, lead=False, source='base'):
    return {'project': 'Project', 'text': text, 'links': links or {}, 'lead': lead, 'sources': [source]}


class HardFloorTests(unittest.TestCase):
    reqs = {rid: {'importance': category, 'weight': weight} for rid, category, weight in (
        ('required', 'required', 4), ('core', 'core', 3), ('other', 'core', 3),
        ('support', 'supporting', 2), ('compound', 'core', 3))}
    lead = bullet('Built the delivery system.', lead=True)

    def solve(self, candidates, floors, **kwargs):
        return select_protected([self.lead, *candidates], self.reqs, floors,
                               **{'max_bullets': 2, 'max_words': 40, 'sources': {'base', 'library'}, **kwargs})

    def test_required_weak_and_equal_core_compete_individually(self):
        both = [bullet('Required proof', {'required': DIRECT}), bullet('Partial Core proof', {'core': WEAK})]
        self.assertEqual(self.solve(both, {'required': DIRECT, 'core': WEAK})['reason'], 'floor_or_budget_conflict')
        self.assertEqual(self.solve(both, {'core': WEAK})['selected'][1]['text'], 'Partial Core proof')
        tie = [bullet('Other proof', {'other': DIRECT}), bullet('Protected proof', {'core': DIRECT})]
        self.assertEqual(self.solve(tie, {'core': DIRECT})['selected'][1]['text'], 'Protected proof')

    def test_compound_full_and_multiple_distinct_citations(self):
        options = [bullet('Partial compound proof', {'compound': WEAK}),
                   bullet('Full compound and distinct proof', {'compound': DIRECT, 'required': DIRECT})]
        result = self.solve(options, {'compound': DIRECT, 'required': DIRECT})
        self.assertEqual(result['selected'][1]['text'], 'Full compound and distinct proof')
        self.assertEqual(self.solve(options[:1], {'compound': DIRECT})['status'], 'withheld')

    def test_duplicate_sources_are_one_bullet_and_one_credit(self):
        duplicate = bullet('Checked failures', {'core': WEAK})
        result = self.solve([duplicate, {**duplicate, 'sources': ['library']}], {'core': WEAK})
        self.assertEqual(result['selected'][1]['sources'], ['base', 'library'])
        self.assertEqual(result['bullet_count'], 2)
        self.assertEqual(result['objectives']['hard'], -600000)

    def test_bonus_and_keyword_only_candidates_cannot_displace_protected_core(self):
        result = self.solve([bullet('Docker SQL Agile'), bullet('Supporting work', {'support': DIRECT}),
                             bullet('Testing action', {'core': WEAK})], {'core': WEAK},
                            bonus_order=('supporting', 'preferred'))
        self.assertEqual(result['selected'][1]['text'], 'Testing action')
        self.assertEqual(result['objectives']['supporting'], 0)

    def test_count_word_and_actual_page_gates_withhold(self):
        self.assertEqual(self.solve([bullet('An intentionally lengthy supporting line', {'core': WEAK})],
                                    {'core': WEAK}, max_words=5)['status'], 'withheld')
        self.assertEqual(verified_research_trial({'pages': 1}, {'pages': 2})['reason'], 'one_page_required')

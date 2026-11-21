import unittest

from tailoring.bullet_choice_estimated import estimate_pair, terms, term_labels


class CppIdentity(unittest.TestCase):
    def row(self, requirement, bullet):
        return estimate_pair(bullet, bullet, [{'id': 'cpp', 'text': requirement,
            'importance': 'core'}])['requirements'][0]['base']

    def test_registry_identity_is_atomic_and_readable(self):
        cpp = terms('C++')
        self.assertEqual(len(cpp), 1)
        self.assertEqual(term_labels(cpp), ['C++'])
        self.assertFalse(cpp & terms('focused programming'))

    def test_no_cpp_from_generic_pedagogical_or_internal_identifier_words(self):
        for text in ['Built focused programming tutorials.',
                     'Implemented modern programming exercises.',
                     'Developed focused application logic.']:
            row = self.row('Good foundation in modern C/C++ programming', text)
            self.assertFalse(set(row['lexical_terms']) & terms('C++'))
            self.assertFalse(row['supported_facets'])

    def test_explicit_cpp_still_matches_without_verifying_advanced_proficiency(self):
        row = self.row('Advanced proficiency in C++ programming', 'Implemented a C++ asset manager.')
        self.assertTrue(set(row['lexical_terms']) & terms('C++'))
        self.assertIn('advanced', row['missing_terms'])
        self.assertNotEqual(row['coverage'], 'full_wording_overlap')
        self.assertFalse(row['verified'])

    def test_language_alternatives_remain_distinct(self):
        row = self.row('Proficiency in one or more backend languages (Java/.NET/Python/PHP)',
                       'Implemented C++ services.')
        self.assertFalse(row['alternative_satisfied'])
        self.assertFalse(row['supported_facets'])

    def test_existing_positive_and_negative_activity_boundaries(self):
        self.assertTrue(self.row('C++ programming', 'Implemented C++ programming tools.')['supported_facets'])
        for text in ['Skills: C++ programming', 'Will implement C++ programming tools.',
                     'Did not implement C++ programming tools.']:
            self.assertFalse(self.row('C++ programming', text)['supported_facets'])

    def test_no_alias_repetition_credit(self):
        self.assertEqual(terms('C++ C++ programming language'), terms('C++'))


if __name__ == '__main__':
    unittest.main()

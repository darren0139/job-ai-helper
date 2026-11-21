"""V1.4 exact-scope tests: inline parenthesized tech preference applies only locally."""
import unittest
from analysis_stability.stable_evidence_scoring import canonicalise_requirements, _canonicalise_requirements_impl, _REVIEW419_LEGACY_PARSER

ANOTECH = """Requirements
· Knowledge in C (C++ is considered a plus), Java, C#, Visual Basic
"""


class InlineParentheticalPreferenceV14(unittest.TestCase):
    @staticmethod
    def rows(raw):
        return canonicalise_requirements({}, raw)['requirements']

    def test_required_siblings_remain_core_optional_only_cpp(self):
        rows = self.rows(ANOTECH)
        self.assertEqual({r['text']: r['importance'] for r in rows}, {
            'Knowledge in C': 'core',
            'Knowledge in Java': 'core',
            'Knowledge in C#': 'core',
            'Knowledge in Visual Basic': 'core',
            'Knowledge in C++': 'preferred',
        })

    def test_shared_parent_lineage_and_allocation_fractions(self):
        rows = self.rows(ANOTECH)
        self.assertEqual(len(rows), 5)
        self.assertEqual(len({r['atomic_group_id'] for r in rows}), 1)
        self.assertEqual(len({r['scoring_parent_occurrence_id'] for r in rows}), 1)
        self.assertTrue(all(r['source_provenance'][0]['grounding']['line_index'] == 2 for r in rows))
        self.assertTrue(all(r['source_provenance'][0]['source_group_fraction'] == .2 for r in rows))

    def test_unrelated_sentence_unchanged_and_not_preferred(self):
        rows = self.rows(ANOTECH + "· Knowledge of architectural styles and design patterns\n")
        self.assertEqual(len(rows), 6)
        match = [r for r in rows if 'architectural styles' in r['text']]
        self.assertEqual(len(match), 1)
        self.assertEqual(match[0]['importance'], 'core')

    def test_generic_mixed_technology_list(self):
        rows = self.rows("Requirements\nKnowledge in Java (Kotlin is considered a plus), Go\n")
        self.assertEqual({r['text']: r['importance'] for r in rows}, {
            'Knowledge in Java': 'core', 'Knowledge in Go': 'core',
            'Knowledge in Kotlin': 'preferred',
        })

    def test_explicit_required_section_is_not_downgraded(self):
        rows = self.rows("Required Skills\nKnowledge in Java (Kotlin is considered a plus), Go\n")
        self.assertEqual({r['text']: r['importance'] for r in rows}, {
            'Knowledge in Java': 'required', 'Knowledge in Go': 'required',
            'Knowledge in Kotlin': 'preferred',
        })

    def test_non_technical_parenthesis_not_recast(self):
        rows = self.rows("Requirements\nKnowledge of people (empathy is considered a plus), organizations\n")
        self.assertEqual(len(rows), 2)
        self.assertTrue(any('empathy is considered a plus' in r['text'] for r in rows))
        self.assertFalse(any(r['text'] == 'Knowledge of empathy' for r in rows))

    def test_standalone_preference_still_preferred(self):
        rows = self.rows("Requirements\nKnowledge of cloud platforms is a plus\n")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['importance'], 'preferred')

    def test_legacy_419_path_unchanged(self):
        token = _REVIEW419_LEGACY_PARSER.set(True)
        try:
            rows = _canonicalise_requirements_impl({}, ANOTECH)['requirements']
        finally:
            _REVIEW419_LEGACY_PARSER.reset(token)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['importance'], 'preferred')
        self.assertIn('C++ is considered a plus', rows[0]['text'])


if __name__ == '__main__':
    unittest.main()

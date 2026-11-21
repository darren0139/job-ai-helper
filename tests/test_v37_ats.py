import unittest
from unittest.mock import patch

from tailoring.phase9f_v37_ats import ats_evidence


class AtsEvidenceTests(unittest.TestCase):
    @patch('tailoring.phase9f_v37_ats.match_requirement_to_candidate')
    def test_exact_language_and_provenance_are_independent(self, matcher):
        matcher.return_value = {'label': None}
        req = {'requirement_id': 'language', 'text': 'Use Java for backend services',
               'parent_text': 'Use Java for backend services', 'importance': 'core', 'group_weight_fraction': 1}
        items = [
            {'section': 'skills', 'text': 'Java', 'attested': True},
            {'section': 'projects', 'text': 'Built JavaScript backend services.', 'attested': True},
            {'section': 'projects', 'text': 'Java backend services', 'attested': False},
        ]
        got = ats_evidence([req], items, req['text'])
        rows = got['requirements'][0]['matches']
        self.assertTrue(rows[0]['exact_skill'])
        self.assertTrue(rows[0]['exact_technologies'])
        self.assertFalse(rows[1]['exact_technologies'])
        self.assertTrue(rows[1]['generic_or_repeated_cue_only'])
        self.assertTrue(rows[2]['unsupported_keyword_only'])
        self.assertEqual(got['grounded_requirement_ids'], [])

    @patch('tailoring.phase9f_v37_ats.match_requirement_to_candidate', return_value={'label': 'direct'})
    def test_sections_do_not_multiply_parent_allocation(self, _):
        jd = 'Implement Python and SQL.'
        req = {'parent_text': jd, 'importance': 'preferred', 'group_weight_fraction': 0.6,
               'scoring_parent_occurrence_id': 'parent'}
        items = [{'section': 'skills', 'text': 'Python', 'attested': True},
                 {'section': 'projects', 'text': 'Built Python and SQL services', 'attested': True}]
        got = ats_evidence([{**req, 'requirement_id': name, 'text': name} for name in ('Python', 'SQL')], items, jd)
        self.assertEqual(got['supported_parent_allocations'], {'parent': 1})
        self.assertEqual(got['requirements'][0]['matches'][0]['supported_elsewhere'], ['projects'])

    @patch('tailoring.phase9f_v37_ats.match_requirement_to_candidate', return_value={'label': 'direct'})
    def test_clipped_fragment_remains_advisory(self, _):
        jd = 'Implement and test Python.'
        got = ats_evidence([{'requirement_id': 'frag', 'importance': 'core', 'text': 'and test Python',
                             'parent_text': jd, 'group_weight_fraction': .5}],
                           [{'section': 'skills', 'text': 'Python', 'attested': True}], jd)
        self.assertEqual(got['grounded_requirement_ids'], [])
        self.assertTrue(got['distinct_exact_technologies'])

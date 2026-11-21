import unittest
from tailoring.bullet_choice_estimated import estimate_pair, terms


class RelevanceCorrections(unittest.TestCase):
    def assess(self, requirement, bullet):
        return estimate_pair(bullet, bullet, [{'id':'r','text':requirement,'importance':'core'}])['requirements'][0]['base']

    def test_generic_qualification_is_not_database_evidence(self):
        for bullet in ['Added automated unit tests.', 'Implemented an added advantage.', 'Added excellent solutions.']:
            r=self.assess('Proficiency in database will be an added advantage.',bullet)
            self.assertEqual(r['coverage'],'none');self.assertFalse(r['supported_facets'])
        r=self.assess('Proficiency in database will be an added advantage.','Implemented database queries.')
        self.assertIn('database',r['supported_facets'])

    def test_explicit_disjunction_preserves_optional_alternatives(self):
        r=self.assess('Proficiency in one or more frontend framework (HTML5/Angular/React JS)', 'Developed frontend interfaces with React JS.')
        self.assertTrue(r['alternative_satisfied']);self.assertTrue(r['supported_facets'])
        self.assertTrue(r['optional_alternatives']);self.assertFalse(set(r['missing_terms']) & set(r['optional_alternatives']))
        self.assertFalse(r['verified'])

    def test_keyword_and_negation_do_not_establish_proficiency(self):
        q='Proficiency in one or more frontend framework (HTML5/Angular/React JS)'
        for text in ['Skills: React JS', 'Did not develop React JS interfaces.', 'Planning to build React JS interfaces.']:
            self.assertFalse(self.assess(q,text)['supported_facets'])

    def test_conjunction_and_compound_testing_stay_partial(self):
        r=self.assess('Execute unit, integration, system and user acceptance testing', 'Added automated unit tests.')
        self.assertEqual(r['coverage'],'partial_wording_support');self.assertIn('integration',r['missing_terms'])
        r=self.assess('Use React and Angular frameworks', 'Developed React interfaces.')
        self.assertFalse(r['optional_alternatives'])

    def test_technology_identity_stays_distinct(self):
        self.assertFalse(terms('Java') & terms('JavaScript'))


if __name__=='__main__':unittest.main()

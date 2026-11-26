"""Distinct contribution controls for conservative same-activity warnings."""
import unittest
from tailoring.phase9f_bullet_redundancy import compare_project_bullets


class BulletRedundancyTests(unittest.TestCase):
    BASE='Built 30-job corpus regression/audit tooling and GitHub Actions CI across Windows/Ubuntu to validate scoring, taxonomy resolution, sessions, and UI workflows.'
    LIBRARY='Added automated unit tests and GitHub Actions CI across Ubuntu and Windows, running dependency checks, compilation, the full test suite, and a Streamlit startup health check.'

    def test_ci_testing_is_likely_same_work_despite_low_jaccard(self):
        result=compare_project_bullets(self.BASE,self.LIBRARY)
        self.assertEqual(result['status'],'likely_same_work')
        self.assertIn('ci_pipeline',result['shared_activities'])
        self.assertIn('testing_validation',result['shared_activities'])

    def test_one_keyword_does_not_merge_distinct_activity(self):
        self.assertNotEqual(compare_project_bullets(
            'Used React to build an accessibility dashboard.',
            'Built React authentication for an account service.')['status'],'likely_same_work')
        self.assertNotEqual(compare_project_bullets(
            'Set up the React and Supabase project environment and connected the frontend to the PostgreSQL-backed service.',
            'Implemented backend data access through PostgREST and applied Row-Level Security policies to secure database operations.')['status'],'likely_same_work')

    def test_ui_plus_delivery_is_not_automatically_a_duplicate(self):
        x=compare_project_bullets(
            'Implemented user-facing UI features including sliders and level-locking screens to support player progression.',
            'Built gameplay and UI features in a small team, contributing to a completed mobile game released on Google Play.')
        self.assertNotEqual(x['status'],'likely_same_work')

    def test_project_isolation_and_exact_wording(self):
        self.assertEqual(compare_project_bullets(self.BASE,self.BASE)['status'],'same_wording')
        self.assertEqual(compare_project_bullets(self.BASE,self.LIBRARY,same_project=False)['status'],'different_projects')


if __name__ == '__main__':unittest.main()

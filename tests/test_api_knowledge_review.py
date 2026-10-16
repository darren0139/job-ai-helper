"""Investigation-only safeguards for V1.2 counterfactuals; no policy release."""
from copy import deepcopy
import unittest

from analysis_stability import stable_evidence_scoring as scoring
from tailoring import capability_taxonomy as taxonomy
from tests import api_knowledge_review_support as review


class ApiKnowledgeReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = review.matrix()
        cls.by_name = {r['case']: r for r in cls.results}
        cls.job = review.job81_alternatives()

    def test_native_matrix_and_restoration_preserve_original_context(self):
        self.assertEqual(len(self.results), 27)
        for item in self.results:
            with self.subTest(case=item['case']):
                self.assertEqual(item['baseline_native'], review.evaluate_inputs(review.inputs_for(item)))
                before = item['baseline_native']['canonical_requirements']
                for key in ('hypothesis_current_recovery_native', 'hypothesis_scoped_recovery_native'):
                    after = item[key]['canonical_requirements']
                    self.assertEqual(len(before), len(after))
                    for original, projected in zip(before, after):
                        for field in ('requirement_id', 'knowledge_status', 'capability_id', 'importance',
                                      'group_weight_fraction', 'source_provenance', 'parent_text', 'score_eligible'):
                            self.assertEqual(original.get(field), projected.get(field), field)

    def test_job81_receipt_does_not_establish_a_queryai_project_title(self):
        row = self.job['original_saved_row']
        self.assertEqual(row['text'], 'Knowledge of API development')
        self.assertEqual(row['evidence'][0]['text'], review.POSTGREST)
        self.assertEqual(row['evidence'][0]['source'], 'resume_profile.projects[1].bullets[1]')
        self.assertEqual(row['evidence'][0]['evidence_id'], 'ev_3e06933c2432')
        self.assertIsNone(self.job['source_project_title'])
        self.assertNotIn('/message', row['evidence'][0]['text'])

    def test_job81_weak_receipt_alone_is_blocked_at_zero_overlap(self):
        hypotheses = self.job['alternatives']
        expected = [('none', False, 'none', 0.0, 8), ('weak', False, 'none', 0.0, 8),
                    ('weak', True, 'weak', 0.2, 8), ('direct', False, 'direct', 1.0, 10)]
        for actual, (label, exception, final, value, score) in zip(hypotheses, expected):
            with self.subTest(label=label, recovery_exception=exception):
                row = next(r for r in actual['native']['canonical_requirements']
                           if r['requirement_id'] == 'req_8902c2c2d5c0')
                self.assertEqual(actual['label_hypothesis'], label)
                self.assertEqual(actual['experimental_recovery_exception'], exception)
                self.assertEqual((row['match_label'], row['match_value']), (final, value))
                self.assertEqual(actual['native']['deterministic_alignment_score'], score)
                if exception:
                    self.assertEqual(row['capability_none_recovery']['selected_requirement_overlap_count'], 0)
                    self.assertEqual(row['evidence'][0]['text'], review.POSTGREST)
                elif final == 'none':
                    self.assertEqual(row['evidence'], [])

    def test_practical_contract_knowledge_hypothesis_is_distinct_from_tool_usage(self):
        crude = self.by_name['development_knowledge_crud_only']
        concepts = self.by_name['development_knowledge_contract_practices']
        self.assertEqual(crude['hypothesis_evaluator'][0]['label'], 'none')
        self.assertEqual(concepts['baseline_evaluator'][0]['label'], 'none')
        self.assertEqual(concepts['hypothesis_evaluator'][0]['label'], 'weak')
        self.assertEqual(concepts['hypothesis_current_recovery_native']['canonical_requirements'][0]['match_value'], 0.2)
        denied_authorship = self.by_name['non_authoring_but_contract_practices']
        self.assertEqual(denied_authorship['hypothesis_evaluator'][0]['label'], 'weak')
        self.assertNotEqual(denied_authorship['hypothesis_evaluator'][0]['label'], 'direct')

    def test_protocol_guard_is_not_replaced_by_hypothesis_receipts(self):
        for name in ('rest_knowledge_sdk_only', 'wrong_protocol', 'compound_protocols'):
            item = self.by_name[name]
            with self.subTest(case=name):
                self.assertTrue(all(d['label'] == 'none' for d in item['baseline_evaluator']))
                self.assertEqual(item['baseline_evaluator'], item['hypothesis_evaluator'])
        inputs = review.inputs_for(self.by_name['wrong_protocol'])
        with review.receipt_hypothesis('Knowledge of REST API', inputs['resume_profile']['projects'][0]['bullets'],
                                       ['direct'], allow_weak_recovery=True):
            decision = taxonomy.evaluate_capability_evidence('backend.api_development',
                {'text': 'Knowledge of REST API'}, inputs['raw_resume_text'])
        self.assertEqual(decision['label'], 'none')
        self.assertEqual(decision['reason'], 'requested_api_protocol_evidence_missing')

    def test_skills_documentation_denials_and_separate_rows_stay_unsupported(self):
        for name in ('skills_only', 'documentation_only', 'development_experience_denied',
                     'development_knowledge_denied', 'separate_rows_do_not_complete_knowledge',
                     'supabase_generated_endpoints'):
            item = self.by_name[name]
            with self.subTest(case=name):
                self.assertEqual(item['baseline_native'], item['hypothesis_scoped_recovery_native'])
                self.assertTrue(all(r['match_value'] == 0 for r in item['baseline_native']['canonical_requirements']))

    def test_authoring_and_non_api_obligations_are_outside_the_preview(self):
        for name in ('authoring_postgrest', 'endpoint_authoring', 'internship_development',
                     'internship_combined', 'frontend_control', 'cpp_knowledge_control', 'database_policy_control'):
            item = self.by_name[name]
            with self.subTest(case=name):
                self.assertEqual(item['baseline_evaluator'], item['hypothesis_evaluator'])
                self.assertEqual(item['baseline_native'], item['hypothesis_scoped_recovery_native'])
        self.assertEqual(self.by_name['internship_development']['baseline_native']['canonical_requirements'][0]['match_value'], 1)
        self.assertEqual(self.by_name['internship_combined']['baseline_native']['canonical_requirements'][0]['match_value'], 0.2)

    def test_unresolved_recognition_is_reported_without_simulating_a_taxonomy_change(self):
        plural = self.by_name['rest_knowledge_plural_supabase']
        row = plural['baseline_native']['canonical_requirements'][0]
        self.assertEqual(row['knowledge_status'], 'UNRESOLVED')
        self.assertEqual(plural['baseline_evaluator'][0]['label'], 'none')
        self.assertEqual(row['match_label'], 'weak')
        integration = self.by_name['integration_knowledge_supabase']
        self.assertEqual(integration['baseline_evaluator'][0]['label'], 'direct')
        self.assertEqual(integration['baseline_native']['canonical_requirements'][0]['match_label'], 'none')

    def test_current_identity_is_unchanged_and_preview_is_not_a_cacheable_policy_release(self):
        self.assertEqual(scoring.SCORING_VERSION, 'stable-evidence-v1.17-phase6d21')
        item = self.by_name['development_knowledge_contract_practices']
        self.assertEqual(item['baseline_native']['input_fingerprint'],
                         item['hypothesis_scoped_recovery_native']['input_fingerprint'])
        self.assertNotEqual(item['baseline_native']['canonical_requirements'][0]['match_value'],
                            item['hypothesis_scoped_recovery_native']['canonical_requirements'][0]['match_value'])
        frozen = deepcopy(item['baseline_native'])
        self.assertEqual(frozen, review.evaluate_inputs(review.inputs_for(item)))


if __name__ == '__main__':
    unittest.main()

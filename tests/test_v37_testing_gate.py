import unittest

from tailoring.phase9f_v37_testing_gate import apply_shadow_testing_gate, has_attested_testing_activity


class TestingEvidenceGateTests(unittest.TestCase):
    duty = {'capability_id': 'quality.qa_testing', 'semantic_type': 'role_responsibility', 'match_label': 'weak'}
    source = 'resume_profile.projects[0].bullets[1]'
    factual = 'Added automated unit tests and ran them in CI.'

    def test_attested_partial_testing_survives_at_the_existing_label(self):
        evidence = {'section': 'projects', 'source': self.source, 'text': self.factual}
        self.assertTrue(has_attested_testing_activity(self.duty, evidence, {(self.source, self.factual)}))
        self.assertEqual(self.duty['match_label'], 'weak')

    def test_keyword_list_cannot_use_a_different_excerpt_or_source_attestation(self):
        evidence = {'section': 'projects', 'source': self.source, 'text': 'Testing, testing, testing.'}
        self.assertFalse(has_attested_testing_activity(self.duty, evidence, {(self.source, self.factual)}))
        evidence['text'] = self.factual
        self.assertFalse(has_attested_testing_activity(self.duty, evidence, {('elsewhere', self.factual)}))

    def test_technology_qualification_is_outside_activity_gate(self):
        req = {**self.duty, 'capability_id': 'technology.python', 'semantic_type': 'candidate_requirement'}
        self.assertTrue(has_attested_testing_activity(req, {'section': 'skills', 'text': 'Python'}, set()))

    def shadow(self, text, *, source='raw_resume_text[1]', cited=None, reviewed_actions=()):
        excerpt = {'section': 'raw_text', 'text': cited or text, 'source': source}
        requirement = {**self.duty, 'requirement_id': 'testing', 'text': 'Implement and test software',
                       'importance': 'core', 'match_value': .2, 'evidence_strength': 2, 'evidence': [excerpt]}
        tech = {**requirement, 'requirement_id': 'python', 'text': 'Python', 'capability_id': 'technology.python'}
        rows, audit = apply_shadow_testing_gate(
            [requirement, tech], resume_text=f'Work Experience\n{text}\nSkills\nProgramming: Python',
            reviewed_actions=reviewed_actions,
        )
        self.assertEqual(requirement['match_label'], 'weak')
        self.assertEqual(rows[1], tech)
        return rows[0], audit[0]['decisions'][0]['reason']

    def test_complete_partial_and_unstructured_activities_keep_native_credit(self):
        for text in (
            'Implemented the API and wrote integration tests for failed requests.',
            'Added automated regression tests for the checkout flow.',
            'While maintaining the service, I wrote unit tests for retry handling.',
            'Performed system testing for the release.',
        ):
            with self.subTest(text=text):
                row, reason = self.shadow(text)
                self.assertEqual(row['match_label'], 'weak')
                self.assertEqual(reason, 'explicit_performed_testing_claim_in_document')

    def test_list_duplicates_and_non_performed_actions_lose_weak_credit(self):
        for text in ('Software implementation, testing, testing, testing.',
                     'Unit tests, regression testing, integration testing.',
                     'Planned to write unit tests. I did not run testing.',
                     'I did not write unit tests and never ran integration tests.'):
            with self.subTest(text=text):
                row, reason = self.shadow(text)
                self.assertEqual((row['match_label'], row['match_value'], row['evidence_strength'], row['evidence']),
                                 ('none', 0.0, 0, []))
                self.assertEqual(reason, 'no_performed_testing_claim_in_cited_text')

    def test_attestation_is_bound_to_the_current_document_even_for_raw_uploads(self):
        text = 'Coverage of malformed records was checked in the nightly build.'
        attestation = {('raw_resume_text[1]', text)}
        self.assertEqual(self.shadow(text, reviewed_actions=attestation)[1],
                         'independently_reviewed_performed_testing')
        self.assertEqual(self.shadow(text, source='raw_resume_text[9]', reviewed_actions=attestation)[1],
                         'no_exact_document_activity_excerpt')
        self.assertEqual(self.shadow('A different exact source line.', cited=text, reviewed_actions=attestation)[1],
                         'no_exact_document_activity_excerpt')

    def test_passive_and_future_forms(self):
        for text, expected in (
            ('Integration tests were run against the billing API.', 'weak'),
            ('Carried out regression testing for failed payments.', 'weak'),
            ('Integration tests were not run against the billing API.', 'none'),
            ('If we ran unit tests next quarter, we would verify refunds.', 'none'),
            ('Integration tests were scheduled to run against the billing API.', 'none'),
        ):
            with self.subTest(text=text):
                self.assertEqual(self.shadow(text)[0]['match_label'], expected)

    def test_multiple_citations_keep_only_independent_performed_claims(self):
        lines = ['Testing, testing.', 'Integration tests were executed against the API.',
                 'Wrote unit tests for checkout.']
        req = {**self.duty, 'requirement_id': 'qa', 'text': 'Implement and test software', 'importance': 'core',
               'evidence': [{'section': 'raw_text', 'source': f'raw_resume_text[{i}]', 'text': t}
                            for i, t in enumerate(lines)]}
        rows, audit = apply_shadow_testing_gate([req], resume_text='\n'.join(lines))
        self.assertEqual(rows[0]['match_label'], 'weak')
        self.assertEqual([item['text'] for item in rows[0]['evidence']], lines[1:])
        self.assertEqual(len(audit[0]['decisions']), 3)

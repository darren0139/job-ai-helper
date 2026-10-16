"""Approved API completeness contract, through the shared native scorer.

All candidate statements here are disposable hypothetical fixtures, never a
profile update or independently verified gold evidence.
"""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from analysis_stability import stable_evidence_scoring as scoring
from tailoring import capability_taxonomy as taxonomy
from job_discovery.matching import current_match_versions


FIXTURE = Path(__file__).with_name('fixtures') / 'api_evidence_completeness_v1.json'
BASELINE_SCORING_VERSION = 'stable-evidence-v1.16-phase6d20'


def native_inputs(requirement, evidence):
    return dict(
        jd_profile={'responsibilities': [requirement]},
        keyword_match={'present': [], 'missing': [{'keyword': requirement}]},
        resume_profile={'projects': [{'title': 'Disposable fixture', 'bullets': evidence}],
                        'experience': [], 'education': [], 'skills': {}},
        raw_resume_text='\n'.join(evidence), retrieval_mode_override='off',
    )


def scenario_results():
    """Executed evaluator and native receipts for the original 23 cases."""
    results = []
    for case in json.loads(FIXTURE.read_text(encoding='utf-8'))['cases']:
        requirement = case['requirement']
        inputs = native_inputs(requirement, case['evidence'])
        native = scoring.build_stable_analysis(**inputs)
        results.append({
            **deepcopy(case),
            'after_evaluator': [taxonomy.evaluate_capability_evidence(
                'backend.api_development', {'text': requirement}, text,
            ) for text in case['evidence']],
            'after_native': native,
        })
    return results


class ApiEvidenceCompletenessTests(unittest.TestCase):
    def evaluate(self, evidence, focus='Develop REST APIs'):
        return taxonomy.evaluate_capability_evidence(
            'backend.api_development', {'text': focus}, evidence,
        )

    def test_original_23_scenarios_evaluator_and_native_selection(self):
        results = scenario_results()
        self.assertEqual(len(results), 23)
        for case in results:
            with self.subTest(case=case['case']):
                self.assertEqual([d['label'] for d in case['after_evaluator']],
                                 case['expected_evaluator_labels'])
                rows = case['after_native']['canonical_requirements']
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]['match_label'], case['expected_native_label'])
                self.assertEqual(rows[0]['match_value'], scoring.MATCH_VALUES[case['expected_native_label']])
                self.assertEqual(case['after_native'], scoring.build_stable_analysis(
                    **native_inputs(case['requirement'], case['evidence'])))
                before = case['baseline_native_rows'][0]
                for key in ('requirement_id', 'atomic_focus', 'is_atomic', 'knowledge_status', 'capability_id'):
                    self.assertEqual(rows[0].get(key), before.get(key), key)
                if case['case'] == 'selection':
                    self.assertEqual(len(rows[0]['evidence']), 1)
                    self.assertEqual(rows[0]['evidence'][0]['text'], case['evidence'][1])

    def test_scoped_actions_negatives_and_inflections(self):
        cases = (
            ('Added new REST endpoints to an existing Java backend.', 'direct'),
            ('Developing REST API endpoints for a Unity project.', 'direct'),
            ('REST API endpoints were implemented in the existing backend.', 'direct'),
            ('REST API endpoints were not implemented.', 'none'),
            ('Did not develop REST API endpoints.', 'none'),
            ('Created REST API documentation.', 'none'),
            ('Implemented REST API clients for an existing service.', 'none'),
            ('Implemented access to an existing REST API.', 'none'),
            ('Used a REST API and built React UI components.', 'none'),
            ('Built a Java cache; integrated an existing REST API.', 'none'),
            ('Built gRPC endpoints and consumed a REST API.', 'none'),
            ('Never owned backend architecture, but implemented REST API endpoints.', 'direct'),
            ('Implemented REST API endpoints without owning backend architecture.', 'direct'),
            ('Implemented REST API endpoints; did not develop gRPC endpoints.', 'direct'),
            ('Implemented REST API endpoints; REST API endpoints were not implemented.', 'none'),
            ('Knowledge of developing REST API endpoints.', 'none'),
            ('Learned how to implement REST API endpoints.', 'none'),
            ('Will implement REST API endpoints.', 'none'),
            ('Not only implemented REST API endpoints but also tested them.', 'direct'),
        )
        for text, label in cases:
            with self.subTest(text=text):
                self.assertEqual(self.evaluate(text)['label'], label)

    def test_design_completeness_uses_one_source_and_actual_protocol(self):
        focus = 'Design and develop RESTful APIs'
        cases = (
            ('Designed and implemented REST API endpoints.', 'direct'),
            ('Designed REST API interfaces and implemented API handlers.', 'direct'),
            ('Implemented REST API endpoints; did not design API interfaces.', 'weak'),
            ('Designed React screens and implemented REST API endpoints.', 'weak'),
            ('Designed gRPC interfaces and implemented REST API endpoints.', 'weak'),
            ('Designed REST API interfaces.\nImplemented REST API endpoints.', 'weak'),
        )
        for text, label in cases:
            with self.subTest(text=text):
                self.assertEqual(self.evaluate(text, focus)['label'], label)

    def test_integration_scope_is_not_an_authorship_requirement(self):
        text = 'Integrated an existing REST API for data retrieval.'
        self.assertEqual(self.evaluate(text)['label'], 'none')
        self.assertEqual(self.evaluate(text, 'REST API integration')['label'], 'direct')
        self.assertEqual(self.evaluate('Integrated with an existing REST API.',
                                      'REST API integration')['label'], 'direct')
        self.assertEqual(self.evaluate('Integrated REST API clients.',
                                      'REST API integration')['label'], 'direct')
        self.assertEqual(self.evaluate('Did not integrate REST APIs.', 'REST API integration')['label'], 'none')

    def test_same_row_protocol_mentions_do_not_borrow_consumption_support(self):
        self.assertEqual(self.evaluate('Implemented gRPC API endpoints; consumed a REST API.')['label'], 'none')
        self.assertEqual(self.evaluate('Implemented REST API endpoints; consumed gRPC APIs.',
                                      'API, REST and gRPC')['label'], 'none')
        self.assertEqual(self.evaluate('Implemented REST API endpoints; implemented gRPC API endpoints.',
                                      'API, REST and gRPC')['label'], 'direct')
        self.assertEqual(self.evaluate('Designed REST API interfaces; implemented gRPC API endpoints.',
                                      'Design and develop REST or gRPC APIs')['label'], 'weak')

    def test_recovery_ties_keep_one_original_source(self):
        inputs = native_inputs('Develop RESTful APIs', [
            'Implemented REST API endpoints.', 'Implemented REST API endpoints.',
        ])
        result = scoring.build_stable_analysis(**inputs)
        evidence = result['canonical_requirements'][0]['evidence']
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0]['source'], 'resume_profile.projects[0].bullets[0]')

    def test_inputs_parent_weights_and_provenance_are_preserved(self):
        text = 'Design and develop RESTful APIs'
        inputs = native_inputs(text, ['Implemented REST API endpoints.'])
        frozen = deepcopy(inputs)
        after = scoring.build_stable_analysis(**inputs)
        self.assertEqual(inputs, frozen)
        row = after['canonical_requirements'][0]
        self.assertEqual(row['match_label'], 'weak')
        self.assertEqual(row['capability_none_recovery']['selected_requirement_overlap_count'], 0)
        self.assertEqual(row['group_weight_fraction'], 1)
        self.assertEqual(row['parent_text'], text)
        self.assertTrue(row['source_provenance'])
        self.assertEqual(row['evidence'][0]['source'], 'resume_profile.projects[0].bullets[0]')

    def test_scoring_identity_changes_without_changing_candidate_or_taxonomy(self):
        inputs = native_inputs('Develop REST APIs', ['Implemented REST API endpoints.'])
        new = scoring.build_stable_analysis(**inputs)
        with patch.object(scoring, 'SCORING_VERSION', BASELINE_SCORING_VERSION):
            old_identity = scoring.build_stable_analysis(**inputs)
        self.assertNotEqual(scoring.SCORING_VERSION, BASELINE_SCORING_VERSION)
        self.assertEqual(scoring.SCORING_VERSION, 'stable-evidence-v1.17-phase6d21')
        self.assertEqual(new['scoring_version'], current_match_versions()['scoring_version'])
        self.assertNotEqual(new['input_fingerprint'], old_identity['input_fingerprint'])
        self.assertEqual(new['canonical_requirements'], old_identity['canonical_requirements'])
        self.assertEqual(new['capability_taxonomy_version'], taxonomy.get_default_taxonomy().version)


if __name__ == '__main__':
    unittest.main()

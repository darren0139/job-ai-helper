import unittest
from unittest.mock import patch

from tailoring.phase9f_joint_resume_optimizer_v2_6 import _rank_weights, _support
from tailoring.phase9f_prefit_dedupe_v39 import dedupe_prepared_projects
from tailoring.phase9f_scoring_policy_registry_v312b2190 import GENERAL_SOFTWARE_TESTING_VERSION
from tailoring.phase6d_ranking_adapter import match_requirement_to_candidate
from tailoring.stable_tailoring_ranking import build_bullet_evidence_priorities
from tailoring.software_testing_evidence_v312b219a import evaluate_software_testing as evaluate, modalities

class SoftwareTestingPolicyTests(unittest.TestCase):
    def case(self,req,evidence,label):
        actual=evaluate({'text':req},evidence)
        self.assertEqual(actual['label'],label,actual)
        return actual
    def test_named_modalities_and_ncs_partial(self):
        req='Execute unit, integration, system and user acceptance testing'
        self.assertEqual(modalities(req),{'unit','integration','system','acceptance'})
        x=self.case(req,'Added automated unit tests and GitHub Actions CI across Ubuntu and Windows, running dependency checks, compilation, the full test suite, and a Streamlit startup health check.','weak')
        self.assertEqual(x['supported_testing_modalities'],['unit'])
        self.assertEqual(x['missing_testing_modalities'],['acceptance','integration','system'])
        self.assertEqual(x['reason'],'partial_named_software_testing_coverage')
    def test_exact_unit_and_full_compound(self):
        self.case('Experience with unit testing','Implemented and executed unit tests for the Python application.','direct')
        self.case('Execute unit, integration, system and user acceptance testing','Executed unit, integration, system and user acceptance testing for a web application.','direct')
    def test_partial_two_and_separate_lines(self):
        self.case('Execute unit, integration, system and user acceptance testing','Executed unit and integration tests.','transferable')
        x=self.case('Execute unit and integration testing','Executed unit tests.\nExecuted integration tests.','transferable')
        self.assertEqual(len(x['supported_testing_modalities']),1)
    def test_explicit_game_scope_uses_old_rules(self):
        self.assertIsNone(evaluate({'text':'Game QA testing'},'Added unit tests.'))
        self.assertIsNone(evaluate({'text':'Quality assurance','parent_text':'Gaming product quality assurance'},'Added unit tests.'))
    def test_ci_only_and_unrelated(self):
        for e in ['Configured GitHub Actions CI pipelines.','Built React frontend workflows backed by PostgreSQL.','Managed integration of software components.']:
            self.case('Experience with software testing',e,'none')
    def test_negative_future_third_party(self):
        for e in ['No unit testing was performed.','Unit tests were not executed.','Planned to implement unit tests.','The QA team executed unit tests.','Watched a tutorial on unit testing.']:
            self.case('Experience with unit testing',e,'none')
    def test_bare_skill_and_unlinked_action(self):
        for e in ['Automated unit tests','Built a Python application; unit testing','Developed a Python application with unit tests']:
            self.case('Experience with unit testing',e,'weak')
    def test_collaboration_and_qualification_not_inferred(self):
        self.case('Write automated tests and work with our QA team to ensure correctness','Added automated unit tests.','weak')
        self.case('3 years of professional unit testing','Executed unit tests.','weak')
    def test_authorship_and_execution_distinct(self):
        self.case('Execute unit testing','Wrote unit tests.','transferable')
        self.case('Write automated testing','Executed automated tests.','transferable')
        self.case('Execute integration testing','Wrote integration tests; ran unit tests.','transferable')
        self.case('Experience with unit and integration testing','Wrote unit tests; integration testing','transferable')
    def test_nonsoftware_and_unrelated_modality(self):
        self.case('Experience with system testing','Performed system testing of electrical hardware.','none')
        self.case('Execute integration testing','Executed unit tests.','weak')
    def test_no_or_completion_or_generic_qa_upgrade(self):
        self.case('Execute unit or integration testing','Executed unit and integration tests.','weak')
        self.case('Experience in quality assurance','Executed unit tests.','weak')


    def test_general_testing_recognizes_authorship_execution_and_automation(self):
        cases = {
            'Created automated backend and frontend tests covering authentication and requests.': ['authored'],
            'Ran frontend tests against the React application.': ['executed'],
            'Automated backend tests for a web application.': ['automated'],
            'Implemented regression tests for application workflows.': ['authored'],
            'Executed the test suite against the application.': ['executed'],
            'Automated frontend builds, backend tests, GHCR image publishing, and Trivy security scans with GitHub Actions.': ['automated'],
        }
        subject = {'text': 'Experience with software testing'}
        compound = 'Execute unit, integration, system and user acceptance testing'
        with patch('tailoring.software_testing_evidence_v312b219a.NATIVE_POLICY_ACTIVE', True):
            for evidence, actions in cases.items():
                with self.subTest(evidence=evidence):
                    decision = match_requirement_to_candidate(requirement=subject, candidate_evidence_text=evidence)
                    self.assertEqual(decision['label'], 'transferable')
                    self.assertEqual(decision['software_testing_activities'], actions)
                    self.assertEqual(decision['qa_testing_policy_version'], GENERAL_SOFTWARE_TESTING_VERSION)
                    self.assertEqual(decision['supported_testing_modalities'], [])
                    named = evaluate({'text': compound}, evidence)
                    self.assertEqual(named['supported_testing_modalities'], [])
                    self.assertEqual(named['missing_testing_modalities'], ['acceptance', 'integration', 'system', 'unit'])

    def test_general_testing_rejects_configuration_plans_and_unowned_actions(self):
        req = 'Experience with software testing'
        controls = [
            'Configured GitHub Actions CI for backend builds.',
            'Configured CI to run backend tests for a web app.',
            'Automated frontend builds and deployed the backend application.',
            'Reviewed automated backend tests in a web application.',
            'Planned to automate backend tests for a web application.',
            'Did not run backend tests for the application.',
            'The QA team executed frontend tests.',
            'Automated hardware testing in an electrical laboratory.',
        ]
        with patch('tailoring.software_testing_evidence_v312b219a.NATIVE_POLICY_ACTIVE', True):
            for evidence in controls:
                self.case(req, evidence, 'none')

    def test_prefit_and_optimizer_use_same_active_wording_links(self):
        base = (
            'Built 30-job corpus regression/audit tooling and GitHub Actions CI across '
            'Windows/Ubuntu to validate scoring, taxonomy resolution, sessions, and UI workflows.'
        )
        library = (
            'Added automated unit tests and GitHub Actions CI across Ubuntu and Windows, running '
            'dependency checks, compilation, the full test suite, and a Streamlit startup health check.'
        )
        wordings = [base, library]
        rid = 'testing'
        ranking = {'requirement_matches': [{
            'requirement_id': rid, 'match_label': 'weak', 'importance': 'core', 'coverage_points': 9,
            'requirement_text': 'Execute unit, integration, system and user acceptance testing',
        }]}

        def prefit():
            priorities = build_bullet_evidence_priorities(bullets=wordings, ranking_row=ranking)
            projects = {'recommended_projects': [{
                'title': 'Tool', 'draft_bullets': wordings, 'selected_blueprint_bullets': wordings,
                'selected_bullet_sources': [['base'], ['library']], 'bullet_evidence_priorities': priorities,
            }]}
            return dedupe_prepared_projects(projects)['_v39_auto_dedupe']['removals'][0]

        # Disabling the B2.19a override exposes the old QA fallback in isolation.
        with patch('tailoring.software_testing_evidence_v312b219a.evaluate_software_testing', return_value=None):
            legacy = prefit()
        self.assertEqual((legacy['removed_saved_evidence_points'], legacy['retained_saved_evidence_points']), (9, 9))
        self.assertEqual(legacy['retained'], library)
        self.assertIn('source/order tie break', legacy['selection_reason'])

        active = prefit()
        self.assertEqual((active['removed_saved_evidence_points'], active['retained_saved_evidence_points']), (0, 9))
        self.assertEqual(active['retained'], library)
        self.assertIn('Greater recorded JD evidence', active['selection_reason'])

        weights, error = _rank_weights(ranking)
        self.assertEqual(error, '')
        self.assertEqual(weights, {rid: 9})
        links, error = _support([{'text': wording} for wording in wordings], ranking, build_bullet_evidence_priorities)
        self.assertEqual(error, '')
        self.assertEqual(links, [set(), {rid}])

if __name__=='__main__':unittest.main()

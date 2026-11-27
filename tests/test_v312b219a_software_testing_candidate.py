import unittest
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

if __name__=='__main__':unittest.main()

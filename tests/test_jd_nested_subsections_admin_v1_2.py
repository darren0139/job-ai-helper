import unittest
from analysis_stability.stable_evidence_scoring import (
    canonicalise_requirements, _REVIEW419_LEGACY_PARSER, _raw_section_for_heading,
)


class NestedRoleSubsectionsAdminV12(unittest.TestCase):
    @staticmethod
    def rows(raw):
        return canonicalise_requirements({}, raw)["requirements"]

    def test_three_bulleted_duty_subsections_recovered(self):
        raw = (
            "Responsibilities\n"
            "Governance, Risk and Compliance (GRC)\n"
            "• Develop and promote governance controls across technology projects.\n"
            "• Review and establish operational risk processes for engineering.\n"
            "Application Security\n"
            "• Integrate security tools into software build pipelines.\n"
            "• Implement secure coding guidelines for engineering teams.\n"
            "Strategic and Operational Excellence\n"
            "• Recommend process improvements for audit reporting workflows.\n"
            "• Present management reporting across stakeholder groups.\n"
            "This integrated role ensures comprehensive coverage across teams.\n"
            "Requirements\n"
            "Hands-on experience with vulnerability assessment."
        )
        rows = self.rows(raw)
        assert len(rows) == 7, [(r['text'],r['sources']) for r in rows]
        duty = [r for r in rows if "raw_jd.responsibilities" in r.get('sources', [])]
        self.assertEqual(len(duty), 6)
        self.assertTrue(all(r['semantic_type'] == 'role_responsibility' for r in duty))
        self.assertFalse(any('integrated role ensures' in r['text'].lower() for r in rows))
        self.assertTrue(any('vulnerability' in r['text'].lower() for r in rows))

    def test_non_bulleted_marketing_not_promoted(self):
        raw = (
            "Responsibilities\n"
            "Exciting Career\n"
            "Build your career with our rewarding opportunities.\n"
            "Requirements\n"
            "Experience with REST API implementation."
        )
        rows = self.rows(raw)
        self.assertEqual(len(rows), 1, [r['text'] for r in rows])
        self.assertIn('REST API', rows[0]['text'])

    def test_citizenship_eligibility_not_a_skill(self):
        raw = (
            "Requirements\n"
            "Singaporean\n"
            "Singapore Citizens only\n"
            "Knowledge of Python and SQL for reporting."
        )
        rows = self.rows(raw)
        self.assertTrue(any('Python' in r['text'] for r in rows))
        self.assertFalse(any('singapore' in r['text'].lower() for r in rows))

    def test_employment_terms_cannot_leak_from_role_section(self):
        raw = (
            "Job Responsibilities:\n"
            "Design and maintain embedded systems for manufacturing.\n"
            "Period:\nPermanent\nLocation:\nJurong East\n"
            "Working hours:\nMon–Fri 8am–5:30pm\nSalary:\nUp to $7,000\n"
            "Job Requirements:\nStrong experience with C++ and RTOS."
        )
        rows = self.rows(raw)
        texts = [r['text'] for r in rows]
        self.assertTrue(any('embedded systems' in x for x in texts))
        self.assertTrue(any('C++' in x for x in texts))
        self.assertFalse(any(x in texts for x in ('Period', 'Permanent', 'Location', 'Jurong East', 'Mon–Fri 8am–5:30pm')))

    def test_application_resume_format_is_not_preferred_skill(self):
        raw = (
            "Job Requirements:\n"
            "Strong working knowledge of embedded C++.\n"
            "Interested applicants, kindly email your detailed resume (MS Word format is preferred)."
        )
        rows = self.rows(raw)
        self.assertEqual(len(rows), 1, [r['text'] for r in rows])
        self.assertIn('embedded C++', rows[0]['text'])

    def test_recruitment_email_phone_privacy_not_skills(self):
        raw = (
            "Job Requirements:\nExperience developing embedded systems in C++.\n"
            "Interested applicants, kindly email your detailed resume (MS Word format is preferred).\n"
            "jane@sampleagency.com (Reg No: R1332758) morgan@sampleagency.com (Reg No: R1104129)\n"
            "Please ensure that applications sent through email are no bigger than 1Mb.\n"
            "T: 6337 3183 | W: www.sampleagency.com.sg\n"
            "You may find out more information on the PDPA policies at https://example.com/privacy/"
        )
        texts = [r['text'] for r in self.rows(raw)]
        self.assertEqual(len(texts),1,texts)
        self.assertIn('C++',texts[0])

    def test_skillset_and_attributes_headings_are_not_skills(self):
        raw = (
            "Requirements\n"
            "Skillset:\nKnowledge of security vulnerability assessment.\n"
            "Attributes\nStrong communication and collaboration abilities."
        )
        texts = [r['text'] for r in self.rows(raw)]
        self.assertFalse(any(t.lower() in {'skillset','attributes'} for t in texts))
        self.assertTrue(any('vulnerability' in t.lower() for t in texts))
        self.assertTrue(any('communication' in t.lower() for t in texts))

    def test_legacy_heading_rules_remain_frozen(self):
        token = _REVIEW419_LEGACY_PARSER.set(True)
        try:
            self.assertEqual(_raw_section_for_heading('Period:'), '')
            self.assertEqual(_raw_section_for_heading('Location:'), '')
            self.assertEqual(_raw_section_for_heading('Working hours:'), '')
        finally:
            _REVIEW419_LEGACY_PARSER.reset(token)
        self.assertEqual(_raw_section_for_heading('Period:'), 'stop')
        self.assertEqual(_raw_section_for_heading('Location:'), 'stop')
        self.assertEqual(_raw_section_for_heading('Working hours:'), 'stop')

if __name__ == '__main__':
    unittest.main()

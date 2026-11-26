"""B2.15 semantic eligibility and historical handoff verification contracts."""
from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from analysis_stability import stable_evidence_scoring as scorer

JD = "Job description\nYour role is only the beginning\nJoin NCS and experience a collaborative work environment where you can develop and grow your career through our well-defined career tracks. As part of our Nucleus Graduate Programme, you'll have the opportunity to work on impactful projects with a team that shares your passion for making a difference in the world. Our comprehensive training, professional coaching, and technical expertise will help you attain a Master of Technology with NUS-ISS or industry-recognized certifications. At NCS, we are committed to empowering our people to achieve their fullest potential and create an extraordinary future together.\nAre you excited about the opportunity to tackle complex problems and develop solutions that make a real difference in people's lives? Do you thrive in a fast-paced, dynamic environment where you're encouraged to take risks and think outside the box? Are you looking to make an impact and contribute to the development of innovative software solutions? If you feel any of these describe you, then you might be the one we are looking for!\nWhat will you do?\n-\nPartner with stakeholders to understand business and system requirements\n-\nDevelop and enhance software applications to meet functional and technical specifications\n-\nContinually improve and maintain software applications\n-\nExecute unit, integration, system and user acceptance testing\n-\nUsing configuration management, integration and build automation tools to deploy applications\n-\nIdentify opportunities and suggest recommendations for system improvement\nQualifications\nThe ideal candidate should possess:\n-\nProficiency in one or more frontend framework (HTML5/Angular/React JS)\n-\nProficiency in one or more backend languages (Java/.NET/Python/PHP)\n-\nProficiency in database will be an added advantage\n-\nExperience in frontend and backend web application development will be an added advantage\n-\nDegree in Computer Science or related Engineering fields\n-\nRecent graduates with up to 2 years of working experience.\nAdditional information\nWhile we appreciate the interest in this role, only shortlisted candidates will be contacted given the high volume of applicants.\nWe are driven by our AEIOU beliefs—Adventure, Excellence, Integrity, Ownership, and Unity—and we seek individuals who embody these values in both their professional and personal lives. We are committed to our Impact: Valuing our clients, Growing our people, and Creating our future.\nTogether, we make the extraordinary happen.\nLearn more about us at ncs.co and visit our LinkedIn career site."
PROFILE = {'buzzwords': ['Frontend frameworks', 'Backend languages', 'Web application development', 'Configuration management', 'Integration', 'Build automation', 'Software applications', 'Unit testing', 'Integration testing', 'System testing', 'User acceptance testing', 'System improvement', 'Functional specifications', 'Technical specifications', 'Innovative software solutions', 'Career tracks', 'Impact'], 'company': 'NCS', 'deal_breakers': ['Degree in Computer Science or related Engineering fields', 'Recent graduate with up to 2 years of working experience', 'Proficiency in one or more frontend frameworks (HTML5, Angular, or React JS)', 'Proficiency in one or more backend languages (Java, .NET, Python, or PHP)'], 'experience_level': 'Recent graduates with up to 2 years of working experience', 'job_title': 'AI Software Engineer (Nucleus Graduate Programme)', 'location': 'Singapore, sg', 'preferred_skills': ['Proficiency in databases', 'Experience in frontend and backend web application development'], 'required_skills': ['Proficiency in one or more frontend frameworks (HTML5, Angular, or React JS)', 'Proficiency in one or more backend languages (Java, .NET, Python, or PHP)', 'Degree in Computer Science or related Engineering fields'], 'responsibilities': ['Partner with stakeholders to understand business and system requirements', 'Develop and enhance software applications to meet functional and technical specifications', 'Continually improve and maintain software applications', 'Execute unit, integration, system, and user acceptance testing', 'Use configuration management, integration, and build automation tools to deploy applications', 'Identify opportunities and suggest recommendations for system improvement'], 'soft_skills': ['Ability to tackle complex problems', "Ability to develop solutions that make a real difference in people's lives", 'Ability to thrive in a fast-paced, dynamic environment', 'Willingness to take risks', 'Outside-the-box thinking', 'Passion for making a difference', 'Desire to make an impact', 'Collaborative approach', 'Adventure', 'Excellence', 'Integrity', 'Ownership', 'Unity'], 'tools_technologies': ['HTML5', 'Angular', 'React JS', 'Java', '.NET', 'Python', 'PHP', 'Databases', 'Configuration management tools', 'Integration tools', 'Build automation tools']}
REMOVED = ['req_51ad728f82f8', 'req_836a0a0e8d2b', 'req_8c01098b4092', 'req_bd6ea9ed7ec4', 'req_d5dc0c021d4f']
OLD = 'stable-evidence-v1.16-phase6d20-v312a17-fullstack-single-row'
NEW = 'stable-evidence-v1.16-phase6d20-v312b215-jd-eligibility-v312a17-fullstack-single-row'

class Eligibility(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.object(scorer, '_V312A17_RUNTIME_ACTIVE', True))
    def test_exact_ncs_scope_and_unchanged_survivors(self):
        with patch.object(scorer, '_V312A17_RUNTIME_ACTIVE', False):
            old = scorer.canonicalise_requirements(PROFILE, JD)['requirements']
        new = scorer.canonicalise_requirements(PROFILE, JD)['requirements']
        self.assertEqual(len(old), 17)
        self.assertEqual(len(new), 12)
        self.assertEqual(sorted(set(r['requirement_id'] for r in old)-set(r['requirement_id'] for r in new)), REMOVED)
        self.assertEqual([r for r in old if r['requirement_id'] not in REMOVED], new)
    def test_real_qualifications_and_heading_reentry(self):
        for heading in ('Additional information','ADDITIONAL INFORMATION:','2. Further information','Other information'):
            jd = 'Requirements\nExperience with Python\n'+heading+'\nExperience with Unity engine\nDegree in Computer Science\n3 years of experience\nWe are driven by our values of integrity and unity.\nRequirements\nC++'
            rows = scorer.canonicalise_requirements({},jd)['requirements']
            self.assertEqual({r['text'] for r in rows},{'Experience with Python','Experience with Unity engine','Degree in Computer Science','3 years of experience','C++'})
    def test_profile_cannot_restore_footer(self):
        jd='Requirements\nExperience with Python\nAdditional information\nWe are driven by our values of integrity and unity.'
        rows=scorer.canonicalise_requirements({'required_skills':['integrity and unity','Experience with Python']},jd)['requirements']
        self.assertEqual([r['text'] for r in rows],['Experience with Python'])
    def test_legacy_review_context_does_not_change(self):
        token=scorer._REVIEW419_LEGACY_PARSER.set(True)
        try:
            with patch.object(scorer,'_V312A17_RUNTIME_ACTIVE',False):
                old=scorer._canonicalise_requirements_impl(PROFILE,JD)
            self.assertEqual(old,scorer._canonicalise_requirements_impl(PROFILE,JD))
        finally: scorer._REVIEW419_LEGACY_PARSER.reset(token)

def make_handoff_fixture_docx(path):
    """Synthetic actual-document input, above the production 200-char floor."""
    from docx import Document
    paragraphs = (
        'Synthetic Software Engineer',
        'Education',
        'Bachelor of Science in Computer Science',
        'Projects',
        'Training Application',
        'Developed an interactive training application using Unity and C#.',
        'Implemented reusable user interface components and documented the application workflow.',
        'Tested interactive features and resolved defects identified during development.',
        'Skills',
        'Unity, C#',
    )
    doc = Document()
    for paragraph in paragraphs:
        doc.add_paragraph(paragraph)
    doc.save(path)
    # Verify the actual serialized fixture, not only the intended text.
    readback = '\n'.join(p.text for p in Document(path).paragraphs)
    assert readback == '\n'.join(paragraphs)
    assert len(readback.strip()) >= 200
    return readback


class NativeRelease(unittest.TestCase):
    def test_currentness_and_native_document_scope(self):
        from job_discovery.matching import current_match_versions
        from tailoring.document_grounded_analysis import analyze_actual_resume_against_jd
        from tailoring.job_match_ab_analysis import current_ab_identity
        self.assertEqual(scorer.SCORING_VERSION,NEW)
        self.assertEqual(current_match_versions()['scoring_version'],NEW)
        self.assertEqual(current_ab_identity(JD)['scoring_version'],NEW)
        for text in ('Unity','Built a Python application.'):
            result=analyze_actual_resume_against_jd(resume_text=text,jd_text=JD,jd_profile=PROFILE,resume_profile={'skills':{'tools':[text]}})
            self.assertEqual(result['stable_analysis']['scoring_version'],NEW)
            rows=result['stable_analysis']['canonical_requirements']
            self.assertEqual(len(rows),12)
            self.assertFalse(set(REMOVED)&{r['requirement_id'] for r in rows})
    def test_historical_handoff_exact_docx_rebuild_and_immutability(self):
        from tailoring.phase9f_v364_document_reverify import build_frozen_selected_base_document_report
        from tailoring.document_grounded_analysis import validate_document_report
        with patch.object(scorer,'_V312A17_RUNTIME_ACTIVE',False):
            rows=scorer.canonicalise_requirements(PROFILE,JD)['requirements']
        report={'raw_jd_text':JD,'jd_profile':deepcopy(PROFILE),'resume_profile':{'skills':{'Tools':['Unity']}},'stable_analysis':{'canonical_requirements':rows,'scoring_version':OLD},'meta':{}}
        previous=deepcopy(report)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'base.docx'
            make_handoff_fixture_docx(path)
            content=path.read_bytes()
        artifact={'artifact_bytes':content,'artifact_type':'docx','sha256':hashlib.sha256(content).hexdigest(),'byte_size':len(content)}
        sealed,receipt=build_frozen_selected_base_document_report(baseline_report=report,jd_text=JD,source_artifact=artifact)
        self.assertEqual(report,previous)
        self.assertGreaterEqual(len(sealed['raw_resume_text'].strip()),200)
        self.assertIn('Unity',sealed['raw_resume_text'])
        self.assertEqual(validate_document_report(sealed)['identity']['scoring_version'],NEW)
        self.assertEqual(receipt['scoring_scope_refresh']['removed_ids'],REMOVED)
        self.assertEqual(len(sealed['stable_analysis']['canonical_requirements']),12)
        self.assertEqual(receipt['selected_base_docx_sha256'],artifact['sha256'])
        with self.assertRaisesRegex(ValueError,'exact frozen JD'):
            build_frozen_selected_base_document_report(baseline_report=report,jd_text=JD+'\nchanged',source_artifact=artifact)
        with self.assertRaises(ValueError):
            build_frozen_selected_base_document_report(baseline_report=report,jd_text=JD,source_artifact={**artifact,'sha256':'0'*64})

    def test_changed_scope_is_stale_not_a_raw_jd_edit(self):
        from database.application_blueprint_manager import _phase9f_d_exact_binding_stale_reasons
        current={'canonical_jd_id':'id','source_version_id':'v','raw_jd_sha256':'exact','canonical_requirement_fingerprint':'new','canonical_requirement_ids':['a']}
        decision={'semantic_identity':{'current_jd':{**current,'canonical_requirement_fingerprint':'old','canonical_requirement_ids':['a','b']}}}
        with patch('database.application_blueprint_manager.get_exact_job_description_for_application',return_value=current):
            reasons=_phase9f_d_exact_binding_stale_reasons(1,decision)
        self.assertIn('exact JD text is unchanged',reasons[0])
        with patch('database.application_blueprint_manager.get_exact_job_description_for_application',return_value={**current,'raw_jd_sha256':'different'}):
            self.assertEqual(_phase9f_d_exact_binding_stale_reasons(1,decision),["The application's exact JD changed."])

"""NCS-style source admission regressions; exact original JD remains immutable."""
from __future__ import annotations

import unittest
from copy import deepcopy

from analysis_stability.stable_evidence_scoring import (
    _normalise_requirement_surface,
    _raw_jd_content_spans,
    _raw_section_for_heading,
    _split_requirement_sentences,
    _split_safe_independent_and_pair,
    canonicalise_requirements,
)

NCS_JD = """Company: NCS

Job Description

Your role is only the beginning

Join NCS and experience a collaborative work environment where you can develop and grow your career through well-defined career tracks.

As part of our Nucleus Graduate Programme, you'll have the opportunity to work on impactful projects with a team that shares your passion for making a difference in the world.

Our comprehensive training, professional coaching, and technical expertise will help you attain a Master of Technology with NUS-ISS or industry-recognized certifications.

At NCS, we are committed to empowering our people to achieve their fullest potential and create an extraordinary future together.

Are you excited about the opportunity to tackle complex problems and develop solutions that make a real difference in people's lives? Do you thrive in a fast-paced, dynamic environment where you're encouraged to take risks and think outside the box? Are you looking to make an impact and contribute to the development of innovative software solutions?

What will you do?

Partner with stakeholders to understand business and system requirements

Develop and enhance software applications to meet functional and technical specifications

Continually improve and maintain software applications

Execute unit, integration, system and user acceptance testing

Using configuration management, integration and build automation tools to deploy applications

Identify opportunities and suggest recommendations for system improvement

Qualifications

The ideal candidate should possess:

Proficiency in one or more frontend framework (HTML5/Angular/React JS)

Proficiency in one or more backend languages (Java/.NET/Python/PHP)

Proficiency in database will be an added advantage

Experience in frontend and backend web application development will be an added advantage

Degree in Computer Science or related Engineering fields

Recent graduates with up to 2 years of working experience.
"""

class Phase9FNcsJDSourceRepairTests(unittest.TestCase):
    def test_generic_heading_is_not_automatically_evidence_bearing(self):
        spans = _raw_jd_content_spans(NCS_JD)
        intro = next(row for row in spans if row['text'].startswith('Your role'))
        actual = next(row for row in spans if row['text'].startswith('Partner with'))
        self.assertEqual(intro['section'], '')
        self.assertEqual(intro['section_reason'], 'generic_jd_container_not_requirement_section')
        self.assertEqual(actual['section'], 'responsibilities')

    def test_ncs_headings_are_structural_not_requirements(self):
        self.assertEqual(_raw_section_for_heading('What will you do?'), 'responsibilities')
        self.assertEqual(_raw_section_for_heading('The ideal candidate should possess:'), 'requirements')
        rows = canonicalise_requirements({}, NCS_JD)['requirements']
        texts = [r['text'].lower() for r in rows]
        self.assertFalse(any('what will you do' in s for s in texts))
        self.assertFalse(any('ideal candidate should possess' in s for s in texts))

    def test_marketing_paragraphs_and_questions_cannot_become_requirements(self):
        result = canonicalise_requirements({}, NCS_JD)
        text = '\n'.join(r['text'].lower() for r in result['requirements'])
        for forbidden in (
            'your role is only the beginning', 'join ncs', 'nucleus graduate programme',
            'comprehensive training', 'empowering our people', 'are you excited',
            'are you looking', "difference in people", 'thrive in a fast-paced',
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, text)

    def test_real_responsibilities_and_qualifications_are_preserved(self):
        rows = canonicalise_requirements({}, NCS_JD)['requirements']
        joined = '\n'.join(r['text'].lower() for r in rows)
        for expected in (
            'partner with stakeholders', 'develop and enhance software applications',
            'continually improve and maintain software applications',
            'configuration management', 'degree in computer science',
            'recent graduates with up to 2 years', 'proficiency in database',
            'frontend and backend web application development',
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, joined)
        self.assertTrue(any('database' in r['text'].lower() and r['importance']=='preferred' for r in rows))
        self.assertTrue(any('web application development' in r['text'].lower() and r['importance']=='preferred' for r in rows))

    def test_dotnet_is_not_split_or_spaced_out(self):
        raw = 'Proficiency in one or more backend languages (Java/.NET/Python/PHP)'
        self.assertEqual(_normalise_requirement_surface(raw),raw)
        self.assertEqual(_split_requirement_sentences(raw),[raw])
        rows = canonicalise_requirements({}, NCS_JD)['requirements']
        self.assertTrue(any('Java/.NET/Python/PHP' in r['text'] for r in rows))
        self.assertFalse(any(r['text'].endswith('Java/') or r['text'].startswith('NET/Python') for r in rows))
        self.assertIn('.NET', _normalise_requirement_surface('Experience with . NET services'))

    def test_orphaned_first_verb_fragment_is_not_created(self):
        clause = 'Continually improve and maintain software applications'
        self.assertEqual(_split_safe_independent_and_pair(clause), [])
        result = canonicalise_requirements({}, NCS_JD)['requirements']
        texts = [r['text'] for r in result]
        self.assertIn(clause, texts)
        self.assertNotIn('Continually improve', texts)
        self.assertEqual(
            _split_safe_independent_and_pair('Design services and maintain legacy applications'),
            ['Design services','maintain legacy applications'],
        )

    def test_noisy_llm_profile_cannot_reintroduce_generic_marketing(self):
        profile = {
            'responsibilities': ['Your role is only the beginning',
                                 'Join NCS and experience a collaborative work environment'],
            'required_skills': ['develop solutions that make a real difference in people\'s lives',
                                'Proficiency in one or more backend languages (Java/.NET/Python/PHP)'],
        }
        unchanged = deepcopy(profile)
        result = canonicalise_requirements(profile, NCS_JD)
        self.assertEqual(profile, unchanged)
        texts='\n'.join(r['text'].lower() for r in result['requirements'])
        self.assertNotIn('your role is only the beginning', texts)
        self.assertNotIn("difference in people's lives", texts)
        self.assertIn('java/.net/python/php', texts)

    def test_unheaded_explicit_real_obligation_still_allowed(self):
        raw = 'Job Description\n\nYou will develop robust software services.\n'
        rows = canonicalise_requirements({}, raw)['requirements']
        self.assertTrue(any('develop robust software services' in r['text'].lower() for r in rows))

    def test_true_sentence_boundaries_and_source_provenance_survive(self):
        self.assertEqual(
            _split_requirement_sentences('Build services.Test APIs'),
            ['Build services','Test APIs'],
        )
        result = canonicalise_requirements({}, NCS_JD)
        backend=next(r for r in result['requirements'] if 'Java/.NET/Python/PHP' in r['text'])
        self.assertTrue(backend['source_provenance'])
        self.assertTrue(any('line_index' in row.get('grounding',{})
                            for row in backend['source_provenance']))

if __name__=='__main__':
    unittest.main()


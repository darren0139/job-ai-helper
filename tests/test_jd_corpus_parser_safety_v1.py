"""Deterministic corpus safety regressions; read-only and no external calls."""
import unittest
from analysis_stability.stable_evidence_scoring import canonicalise_requirements as canon
from analysis_stability.stable_evidence_scoring import _raw_section_for_heading, _classify_raw_importance

LTA="[LTA-IDE] ASST MANAGER, LAND (GIS ANALYST / SPATIAL DATA SPECIALIST)\nLand Transport Authority\n00-08 year(s)\nFixed Terms, Full-time\nClosing on 02 Dec 2026\n0 Applicant(s)\n\nWhat the role is\nASSISTANT MANAGER, LAND (GIS ANALYST / SPATIAL DATA SPECIALIST)\n\nWhat you will be working on\nWe are looking for a detail-oriented and analytical GIS professional to support the development and implementation of spatial data solutions across LTA's engineering functions. In this role, you will work with complex geospatial datasets, design GIS solutions to address operational challenges, and communicate spatial insights to a diverse range of stakeholders. You will also play an important role in maintaining data quality and supporting the integration of GIS with other enterprise platforms.\n\nYour key responsibilities include:\n- Processing and analysing complex spatial datasets to extract meaningful insights and identify patterns that inform decision-making.\n- Designing and implementing GIS solutions tailored to specific business needs and operational challenges.\n- Creating and maintaining detailed spatial databases, with a strong focus on data quality and integrity.\n- Developing automated workflows and tools to streamline and improve the efficiency of spatial data processing.\n- Generating comprehensive maps, visualisations, and reports to clearly communicate spatial analysis findings to both technical and non-technical audiences.\n- Collaborating with stakeholders to understand their requirements and propose suitable, practical GIS solutions.\n- Supporting the integration of GIS data with other platforms, including BIM systems.\n- Documenting technical processes and maintaining up-to-date standard operating procedures.\n\nWhat we are looking for\n- Knowledge in Geographic Information Systems, Geomatics, Geography, Environmental Science, or a related field.\n- Strong understanding of GIS concepts, spatial analysis techniques, and cartographic principles.\n- Proficiency in GIS software such as ArcGIS or QGIS, as well as spatial databases.\n- Experience in data analysis with the ability to translate complex datasets into clear, actionable insights.\n- Knowledge of Python programming for automation and spatial analysis would be advantageous.\n- Familiarity with BIM software and integration methods would be a plus.\n- Strong analytical and problem-solving skills, with a keen eye for detail.\n- Excellent communication skills, with the ability to explain technical concepts clearly to non-technical stakeholders.\n- Those without working expereince but with relevant academic projects and a strong aptitude for GIS are welcome to apply.\n\nAs part of the shortlisting process for the role, you may be required to complete a medical declaration and /or undergo further assessment.\n"

class CorpusParserSafetyV1(unittest.TestCase):
    def test_lta_eight_explicit_duty_bullets_and_qualification_preference(self):
        rows=canon({},LTA)['requirements']
        duties=[r for r in rows if 'raw_jd.responsibilities' in (r.get('sources') or [])]
        quals=[r for r in rows if 'raw_jd.requirements' in (r.get('sources') or [])]
        self.assertEqual(len(duties),8)
        self.assertGreaterEqual(len(quals),8)
        for row in duties:self.assertIn(row['importance'],('core','required','supporting'))
        self.assertFalse(any('welcome to apply' in r['text'].lower() for r in rows))
        self.assertFalse(any('Experience in actionable insights'==r['text'] for r in rows))
        self.assertTrue(any('clear, actionable insights' in r['text'] for r in rows))
        self.assertTrue(any('Knowledge of Python programming' in r['text'] and r['importance']=='preferred' for r in rows))
        self.assertTrue(any('Familiarity with BIM software' in r['text'] and r['importance']=='preferred' for r in rows))
        self.assertEqual(_raw_section_for_heading('Your key responsibilities include:'),'responsibilities')

    def test_recruiter_identity_citizenship_contract_are_not_requirements(self):
        jd=('Requirements\nPython programming\nBrunel International S.E.A. Pte. Ltd.\n'
            'UEN No.: 199603098R\nEA Personnel: Example Name (R1234567)\n'
            'As an agency, only Singapore Citizens will be considered.\n'
            'This is a 2-Year Contract\n')
        result=canon({},jd)
        txt=' '.join(x['text'] for x in result['requirements'])
        self.assertIn('Python',txt)
        for banned in ('Brunel','UEN','EA Personnel','Citizens','2-Year Contract'):
            self.assertNotIn(banned,txt)

    def test_additional_valuable_skills_and_nested_bullets(self):
        jd=('Requirements\n· Strong knowledge of development tools including:\n'
            'o Client application development\no Linux administration\n'
            '· Team player with collaborative skills\n· Additional Valuable Skills\n'
            'o Embedded software development\no DevOps practices\n')
        rows=canon({},jd)['requirements']
        self.assertEqual(_raw_section_for_heading('Additional Valuable Skills'),'preferred')
        self.assertTrue(any('Embedded software development' in r['text'] and r['importance']=='preferred' for r in rows))
        self.assertTrue(any('DevOps practices' in r['text'] and r['importance']=='preferred' for r in rows))
        self.assertFalse(any('o Embedded' in r['text'] for r in rows))
        self.assertTrue(any('Team player' in r['text'] for r in rows))

    def test_terminal_preference_and_benign_business_needs(self):
        jd=('Requirements\nThose with project management experience would be preferred.\n'
            'Your key responsibilities include:\nDesigning and implementing solutions tailored to business needs.\n')
        rows=canon({},jd)['requirements']
        self.assertTrue(any('project management' in r['text'] and r['importance']=='preferred' for r in rows))
        self.assertTrue(any('Designing and implementing' in r['text'] and r['importance']=='core' for r in rows))

    def test_review419_legacy_headings_unchanged(self):
        import analysis_stability.stable_evidence_scoring as s
        tok=s._REVIEW419_LEGACY_PARSER.set(True)
        try:self.assertEqual(_raw_section_for_heading('Your key responsibilities include:'),'')
        finally:s._REVIEW419_LEGACY_PARSER.reset(tok)

    def test_generic_umbrella_does_not_promote_marketing(self):
        jd='Job Description\nJoin our fast-growing, dynamic company and get great benefits.'
        rows=canon({},jd)['requirements']
        self.assertFalse(rows)

"""Bounded structure hypotheses run against native contracts before promotion."""
from copy import deepcopy
import unittest
from analysis_stability import stable_evidence_scoring as scorer
from tailoring.requirement_scope import technology_identity_scope
from taxonomy_discovery.technology_registry import resolve_requirement_text
from tests.structure_candidate_simulation_support import structural_remediation_simulation

class StructuralRemediationTests(unittest.TestCase):
    def canonical(self,text,rule='dotnet_v3'):
        with structural_remediation_simulation(rule):
            return scorer.canonicalise_requirements({},'Requirements\n'+text)['requirements']

    def test_preserved_dotted_tokens_at_native_trim_seams(self):
        for text in ('.NET','.Net','.net','Experience with .NET','Proficiency in C#, .NET (MVC & Core), and SQL Server for backend development'):
            with self.subTest(text=text):
                rows=self.canonical(text)
                self.assertTrue(any('.net' in r['text'].lower() for r in rows))
                self.assertFalse(any(r['text'].lower().startswith('net') for r in rows))
        example=self.canonical('Proficiency in web technologies such as Angular, .Net and C#')
        self.assertEqual(len(example),1)
        self.assertIn('.Net',example[0]['text'])
        self.assertFalse(technology_identity_scope(example[0])['identity_resolved'])

    def test_punctuation_and_technology_negatives_unchanged(self):
        for text in ('C# development','C++ development','C/C++','Node.js','React.js','Java','JavaScript','NET','net income','Internet networking','Experience with specifically SQL Server','Python for building internal tools','C# for backend development','MongoDB persistence and search'):
            with self.subTest(text=text):
                before=scorer.canonicalise_requirements({},'Requirements\n'+text)['requirements']
                self.assertEqual(self.canonical(text),before)
        self.assertEqual(resolve_requirement_text('NET')['status'],'unresolved')
        self.assertIsNone(resolve_requirement_text('SQL Server')['capability_id'])
        self.assertNotEqual(resolve_requirement_text('Java')['technology_id'],resolve_requirement_text('JavaScript')['technology_id'])

    def test_operators_preference_and_shared_heads_unchanged(self):
        for text in ('Experience with Python and SQL','Experience with Python, SQL and Java','Proficiency in Python or Java','Experience with one or more of AWS, Azure, GCP','Experience with cloud platforms such as AWS, Azure and GCP','Experience with cloud platforms (e.g. AWS, Azure, GCP)','Experience with Python preferably SQL','Develop APIs and collaborate with teams','Knowledge in Git, Mercurial, Nexus, Artifactory, Maven, Jira, Jenkins architecture','Robotics frameworks such as ROS 2 and simulation platforms','Work closely with DSP, FPGA, RF and system engineering teams to support end-to-end integration'):
            with self.subTest(text=text):
                before=scorer.canonicalise_requirements({},'Requirements\n'+text)['requirements']
                self.assertEqual(self.canonical(text),before)
        rows=self.canonical('Experience with Python, SQL and Java')
        self.assertTrue(all(r['text'].startswith('Experience with ') for r in rows))
        self.assertEqual(len(rows),3)
        self.assertAlmostEqual(sum(r['group_weight_fraction'] for r in rows),1,places=5)

    def test_parent_provenance_weights_importance_and_deterministic_ids(self):
        text='Proficiency in C#, .NET (MVC & Core), and SQL Server for backend development'
        first=self.canonical(text)
        self.assertEqual(first,self.canonical(text))
        self.assertEqual(len(first),3)
        self.assertEqual(len({r['atomic_group_id'] for r in first}),1)
        self.assertAlmostEqual(sum(r['group_weight_fraction'] for r in first),1,places=5)
        for row in first:
            self.assertEqual(row['importance'],'core')
            for source in row['source_provenance']:
                self.assertEqual(source['raw_parent_text'],text)
                self.assertTrue(source['parent_occurrence_id'])
                self.assertEqual(source['grounding']['section'],'requirements')
                self.assertTrue(source['grounding']['span_id'])
        full=deepcopy(first)
        for r in full:r['match_value']=1
        self.assertEqual(scorer._weighted_coverage(full,{'core'})[2],scorer.IMPORTANCE_WEIGHTS['core'])
        self.assertTrue(all(not technology_identity_scope(r)['identity_resolved'] for r in first if 'backend' in r['text']))

    def test_no_cross_parent_leakage(self):
        one='Experience with .NET'
        two='Experience with Python and SQL'
        rows=self.canonical(one+'\n'+two)
        for row in rows:
            for source in row['source_provenance']:
                if '.NET' in row['text']:self.assertEqual(source['raw_parent_text'],one)
                else:self.assertEqual(source['raw_parent_text'],two)

    def test_bullet_cleanup_is_leading_presentation_only(self):
        for text in ('\u00b7 Experience with Python and SQL','\u00b7 Proficiency in Python or Java'):
            with self.subTest(text=text):
                rows=self.canonical(text,'presentation')
                self.assertTrue(all(not r['text'].startswith('\u00b7') for r in rows))
        for text in ('data \u00b7 analysis','\u00b7Python','C++','Use APIs. Develop services'):
            self.assertEqual(self.canonical(text,'presentation'),scorer.canonicalise_requirements({},'Requirements\n'+text)['requirements'])

    def test_presentation_hypothesis_exposes_protected_api_scope_risk(self):
        text = '\u00b7 Knowledge of web services, API, REST, and gRPC'
        before = scorer.canonicalise_requirements({}, 'Requirements\n' + text)['requirements']
        after = self.canonical(text, 'presentation')
        self.assertEqual(len(before), 1)
        self.assertGreater(len(after), 1)
        # Individually recognizing API cannot prove the full gRPC obligation.
        # This prototype therefore cannot be promoted on cleanup alone.
        self.assertFalse(all(technology_identity_scope(r)['identity_resolved'] for r in after))

    def test_simulation_restores_native_functions_even_on_failure(self):
        names = ('_normalise_requirement_surface', '_split_requirement_sentences',
                 '_split_top_level_commas', '_clause_record')
        before = {name: getattr(scorer, name) for name in names}
        with self.assertRaisesRegex(RuntimeError, 'probe'):
            with structural_remediation_simulation('dotnet_v3'):
                raise RuntimeError('probe')
        self.assertEqual(before, {name: getattr(scorer, name) for name in names})
        self.assertNotIn('_token_trim', vars(scorer))

if __name__=='__main__':unittest.main()

"""Approved alias bytes survive native parsing; no new recognition vocabulary."""
from copy import deepcopy
import unittest
from unittest.mock import Mock

from analysis_stability import stable_evidence_scoring as n, coordinated_runtime as runtime
from tailoring.production_requirement_resolver import resolve_requirement_with_production_knowledge as resolve
from taxonomy_discovery.technology_registry import get_default_registry


class AliasSurfaceTests(unittest.TestCase):
    def rows(self, text):
        return n.canonicalise_requirements({},raw_jd_text='Requirements:\n'+text)['requirements']

    def test_existing_aliases_and_case_variants_not_new_aliases(self):
        registry = get_default_registry(); frozen = deepcopy(registry.entries)
        for text, identity in [('Experience with .NET','dotnet'),('Experience with .Net','dotnet'),
                               ('Experience with Node.JS','node.js')]:
            with self.subTest(text=text), runtime.approved_alias_surface_preview():
                rows=self.rows(text)
                self.assertEqual(len(rows),1)
                decision=resolve(rows[0])
                self.assertEqual(decision['knowledge_status'],'TECHNOLOGY_IDENTITY_RESOLVED')
                self.assertIsNone(decision['decision']['capability_id'])
                # Compare the approved entry's identity, not a guessed alias ID.
                expected=next(e['technology_id'] for e in registry.entries
                              if any(a.lower()==text.removeprefix('Experience with ').lower() for a in e['aliases']))
                self.assertEqual(decision['technology_id'],expected)
        with runtime.approved_alias_surface_preview():
            row=self.rows('Experience with React.JS')[0]
            self.assertEqual(resolve(row)['decision']['capability_id'],'frontend.ui_development')
        self.assertEqual(registry.entries,frozen)

    def test_complete_list_allocation_and_scope_cannot_become_identity_only(self):
        text='Proficiency in C#, .NET (MVC & Core), and SQL Server for backend development'
        before=self.rows(text)
        self.assertEqual(len({r['atomic_group_id'] for r in before}),2)
        with runtime.approved_alias_surface_preview():
            rows=self.rows(text)
            self.assertEqual([r['text'] for r in rows],[
                'Proficiency in C#','Proficiency in .NET (MVC & Core)',
                'Proficiency in SQL Server for backend development'])
            self.assertEqual(len({r['atomic_group_id'] for r in rows}),1)
            self.assertAlmostEqual(sum(r['group_weight_fraction'] for r in rows),1,places=5)
            self.assertTrue(all(r['importance']=='core' for r in rows))
            for r in rows:
                self.assertEqual(resolve(r)['knowledge_status'],'UNRESOLVED')
                self.assertTrue(all(p['raw_parent_text']==text for p in r['source_provenance']))
            self.assertEqual(rows,self.rows(text))

    def test_false_partial_angular_recognition_does_not_escape_example_parent(self):
        text='Proficiency in web technologies such as Angular, .Net and C#'
        before=self.rows(text)
        self.assertEqual(len(before),2)
        self.assertEqual(resolve(before[0])['decision']['capability_id'],'frontend.ui_development')
        with runtime.approved_alias_surface_preview():
            after=self.rows(text)
            self.assertEqual(len(after),1)
            self.assertEqual(after[0]['text'],text)
            self.assertIsNone(resolve(after[0])['decision']['capability_id'])
            self.assertAlmostEqual(after[0]['group_weight_fraction'],1)
        # Correctly unresolved whole scope is preferable to an invented easier child.

    def test_punctuation_repair_and_unapproved_names_not_generalized(self):
        with runtime.approved_alias_surface_preview():
            for text in ['NET','net income','Internet networking','ASP.NET','Unknown.NET','Java','JavaScript','C#','C++','C/C++']:
                self.assertNotEqual(resolve({'text':text})['technology_id'],'dotnet',text)
            self.assertEqual(n._normalise_requirement_surface('Use .NET. Then test services.'),'Use .NET. Then test services.')
            self.assertEqual(n._split_requirement_sentences('Use .NET. Develop services.'),['Use .NET','Develop services'])
            self.assertEqual(n._normalise_requirement_surface('Use cases.You will test.'),'Use cases. You will test.')
            self.assertEqual(self.rows('.NET preferably SQL')[0]['text'],'.NET preferably SQL')

    def test_and_or_examples_slash_negation_and_protocol_controls_unchanged(self):
        controls=['Experience with Python and SQL','Proficiency in Python or Java',
            'Experience with one or more of AWS, Azure, GCP',
            'Experience with cloud platforms such as AWS, Azure and GCP',
            'Knowledge of SQL / NoSQL','Develop REST APIs and gRPC services',
            'Do not develop REST APIs','Knowledge of API development',
            '· Knowledge of web services, API, REST, and gRPC',
            'Design, develop and maintain embedded software modules']
        for text in controls:
            before=self.rows(text)
            with self.subTest(text=text),runtime.approved_alias_surface_preview():
                self.assertEqual(self.rows(text),before)

    def test_shared_workflows_versions_source_authority_and_persistence(self):
        from job_discovery.matching import _default_stable_builder,build_profile_evidence_context
        from tailoring.document_grounded_analysis import analyze_actual_resume_against_jd
        from tailoring.phase8_verification import build_current_baseline_analysis
        from database import analysis_cache_manager as cache
        claim='Implemented a React.JS frontend user interface with responsive forms.'
        jd='Requirements:\nExperience with React.JS'
        profile={'projects':[{'title':'Synthetic UI','bullets':[claim]}]}
        context=build_profile_evidence_context([{'id':71,'category':'Project','title':'Synthetic UI','bullets':[claim]}])
        original=_default_stable_builder(raw_jd_text=jd,jd_profile={},context=context)
        with runtime.approved_alias_surface_preview():
            finder=_default_stable_builder(raw_jd_text=jd,jd_profile={},context=context)
            repeated=_default_stable_builder(raw_jd_text=jd,jd_profile={},context=context)
            self.assertEqual(finder['input_fingerprint'],repeated['input_fingerprint'])
            self.assertNotEqual(finder['input_fingerprint'],original['input_fingerprint'])
            initial=analyze_actual_resume_against_jd(resume_text=claim,jd_text=jd,jd_profile={},resume_profile=profile)
            phase8=build_current_baseline_analysis(baseline_report={'jd_profile':{},'resume_profile':profile,
                'keyword_match':{}},raw_jd_text=jd)
            for result in (finder,initial['stable_analysis'],phase8):
                self.assertEqual(result['scoring_version'],runtime.APPROVED_ALIAS_SCORER)
                self.assertEqual(len(result['canonical_requirements']),1)
                self.assertEqual(result['canonical_requirements'][0]['capability_id'],'frontend.ui_development')
                with self.assertRaises(ValueError):runtime.assert_analysis_publishable(result)
            self.assertEqual(finder['canonical_requirements'][0]['match_label'],'direct')
            absent=analyze_actual_resume_against_jd(resume_text='Unrelated document only.',jd_text=jd,
                jd_profile={},resume_profile=profile)
            self.assertEqual(absent['stable_analysis']['canonical_requirements'][0]['match_label'],'none')
        bare={'scoring_version':runtime.APPROVED_ALIAS_SCORER,'canonical_requirements':[]}
        connection=Mock()
        with self.assertRaises(ValueError):cache.insert_analysis_snapshot_with_connection(connection,
            application_id=1,input_fingerprint='x',report={'stable_analysis':bare},analysis_model='offline',
            resume_filename='x',analysis_id='x',created_at='x')
        connection.execute.assert_not_called()

    def test_scope_exception_and_gate_off_restore_original_outputs(self):
        old=self.rows('Experience with .NET')
        with self.assertRaisesRegex(RuntimeError,'synthetic'):
            with runtime.approved_alias_surface_preview():
                self.assertIsNotNone(runtime.APPROVED_ALIAS_SURFACE.get())
                raise RuntimeError('synthetic')
        self.assertIsNone(runtime.APPROVED_ALIAS_SURFACE.get())
        self.assertEqual(self.rows('Experience with .NET'),old)

    def test_changed_mixed_source_blocks_numeric_scoring_instead_of_full_credit(self):
        controls=[
            'Proficiency in C#, .NET (MVC & Core), and SQL Server for backend development',
            'Proficiency in web technologies such as Angular, .Net and C#',
            'Develop Angular, Node.JS and React applications',
        ]
        for text in controls:
            with self.subTest(text=text), runtime.approved_alias_surface_preview():
                self.assertTrue(self.rows(text))  # recognition/source review remains available
                for coordinated in (False,True):
                    with self.assertRaisesRegex(ValueError,'recognition-only review required'):
                        n.build_stable_analysis(jd_profile={},keyword_match={},raw_jd_text='Requirements:\n'+text,
                            resume_profile={'projects':[{'title':'Synthetic UI','bullets':[
                                'Implemented a React frontend user interface with responsive forms.']}]},
                            coordinated_actions_enabled=coordinated)
        self.assertIsNone(runtime.APPROVED_ALIAS_SURFACE.get())


if __name__=='__main__':unittest.main()

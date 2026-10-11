"""Complete-parent hypotheses: native semantics, no production mutation."""
from copy import deepcopy
import unittest
from analysis_stability import stable_evidence_scoring as scorer
from tests.compound_completeness_simulation_support import evaluate_group,apply_guard,completeness_simulation
from tests.structure_candidate_simulation_support import structural_remediation_simulation
from tailoring.phase6d6_structured_matching import apply_structured_requirement_matches

class CompoundCompletenessTests(unittest.TestCase):
    def rows(self,parent='Experience with Python and SQL'):
        return scorer.canonicalise_requirements({},'Requirements\n'+parent)['requirements']
    def supported(self,row,identity='ev_same',text='Built Python and SQL tooling'):
        row.update(match_label='direct',match_value=1,evidence_strength=5,
            evidence=[{'evidence_id':identity,'source':'resume_profile.projects[0].bullets[0]','section':'projects','text':text}])
        return row
    def decision(self,rows):return evaluate_group(rows[0]['parent_text'],rows)

    def test_all_first_only_is_not_complete(self):
        rows=self.rows();self.supported(rows[0]);rows[1].update(match_label='none',evidence=[])
        d=self.decision(rows);self.assertEqual(d['mode'],'ALL');self.assertFalse(d['complete'])
    def test_all_supported_common_receipt_is_complete(self):
        rows=self.rows()
        for r in rows:self.supported(r)
        self.assertTrue(self.decision(rows)['complete'])
    def test_direct_child_and_none_sibling_do_not_credit_parent(self):
        rows=self.rows();self.supported(rows[0]);rows[1].update(match_label='none',evidence=[])
        after=apply_guard(rows)
        self.assertTrue(all(r['match_label']=='none' for r in after))
        self.assertEqual(after[0]['experimental_compound_completeness']['original_label'],'direct')
    def test_different_receipts_cannot_be_combined(self):
        rows=self.rows()
        for i,r in enumerate(rows):self.supported(r,'ev_'+str(i))
        self.assertEqual(self.decision(rows)['reason'],'MULTI_EVIDENCE_COMPLETENESS_NOT_SUPPORTED')
    def test_any_one_supported_allowed_branch(self):
        parent='Proficiency in Python or SQL'
        rows=[{'text':t,'atomic_focus':t,'parent_text':parent,'importance':'core','match_label':'none','evidence':[]} for t in ('Python','SQL')]
        self.supported(rows[0]);d=evaluate_group(parent,rows)
        self.assertEqual(d['mode'],'ANY');self.assertTrue(d['complete'])
    def test_any_no_branch_is_incomplete(self):
        p='Proficiency in Python or SQL';r=[{'text':'Python','parent_text':p,'importance':'core','match_label':'none','evidence':[]}]
        self.assertFalse(evaluate_group(p,r)['complete'])
    def test_any_unrelated_branch_does_not_complete(self):
        p='Proficiency in Python or SQL';r=[self.supported({'text':'Java','parent_text':p,'importance':'core'})]
        self.assertFalse(evaluate_group(p,r)['complete'])
    def test_one_of_requires_native_branch_semantics(self):
        p='Experience with one of Python, SQL';r=[self.supported({'text':p,'parent_text':p,'importance':'core'})]
        d=evaluate_group(p,r);self.assertEqual(d['mode'],'ONE_OF');self.assertFalse(d['complete'])
    def test_example_identity_alone_does_not_complete(self):
        p='Frameworks such as Angular, React and .NET';r=[self.supported({'text':p,'parent_text':p,'importance':'core','knowledge_status':'TECHNOLOGY_IDENTITY_RESOLVED'})]
        d=evaluate_group(p,r);self.assertEqual(d['mode'],'EXAMPLE_ONLY');self.assertFalse(d['complete'])
    def test_example_independent_parent_capability_support(self):
        p='Build user interfaces such as dashboards'
        r=[self.supported({'text':p,'parent_text':p,'importance':'core','capability_id':'frontend.ui_development'},text='Built React frontend UI components and dashboard views')]
        self.assertTrue(evaluate_group(p,r)['complete'])
    def test_mixed_activity_keyword_alone_fails_closed(self):
        p='write and maintain code, build APIs, work on bug fixes, and monitor the technical performance of our internal systems, primarily using C#';r=[self.supported({'text':p,'parent_text':p,'importance':'core'},text='C#')]
        d=evaluate_group(p,r);self.assertEqual(d['mode'],'MIXED_ACTIVITY_SCOPE');self.assertFalse(d['complete'])
    def test_coherent_unknown_group_fails_closed(self):
        p='Net and C#';r=[self.supported({'text':p,'parent_text':p,'importance':'core'},text='C#')]
        self.assertFalse(evaluate_group(p,r)['complete'])
    def test_capability_without_evidence_does_not_complete(self):
        rows=self.rows()
        for r in rows:r.update(capability_id='backend.api_development',match_label='none',evidence=[])
        self.assertFalse(self.decision(rows)['complete'])
    def test_identity_without_evidence_does_not_complete(self):
        rows=self.rows()
        for r in rows:r.update(knowledge_status='TECHNOLOGY_IDENTITY_RESOLVED',match_label='none',evidence=[])
        self.assertFalse(self.decision(rows)['complete'])
    def test_guard_conserves_weights_importance_ids_and_provenance(self):
        rows=self.rows();self.supported(rows[0]);rows[1].update(match_label='none',evidence=[])
        before=deepcopy(rows);after=apply_guard(rows)
        self.assertEqual(rows,before)
        for a,b in zip(rows,after):
            for key in ('requirement_id','importance','atomic_group_id','group_weight_fraction','parent_text','source_provenance'):self.assertEqual(a[key],b[key])
        self.assertAlmostEqual(sum(r['group_weight_fraction'] for r in after),1)
    def test_unrelated_groups_do_not_share_receipts(self):
        rows=self.rows();extra=self.rows('Experience with Java and TypeScript')
        self.supported(rows[0]);self.supported(extra[1])
        rows[1].update(match_label='none',evidence=[]);extra[0].update(match_label='none',evidence=[])
        self.assertTrue(all(r['match_value']==0 for r in apply_guard(rows+extra)))
    def test_atomic_legitimate_credit_unchanged(self):
        rows=self.rows('Experience with Python');self.supported(rows[0])
        self.assertEqual(apply_guard(rows),rows)
    def test_atomic_knowledge_without_evidence_is_not_complete(self):
        rows=self.rows('Experience with Python')
        rows[0].update(knowledge_status='TECHNOLOGY_IDENTITY_RESOLVED',
                       match_label='none',match_value=0,evidence=[])
        self.assertFalse(self.decision(rows)['complete'])
        self.assertEqual(apply_guard(rows),rows)
    def test_approved_native_language_group_receipt_is_preserved(self):
        parent='Proficiency in Python and SQL'
        rows,_=apply_structured_requirement_matches([
            {'requirement_id':'native-group','text':parent,'parent_text':parent,
             'importance':'core','match_label':'none','match_value':0,'evidence':[]}],
            resume_profile={'skills':{'Languages':['Python','SQL']}})
        self.assertEqual(rows[0]['structured_match_kind'],'programming_language_group')
        decision=evaluate_group(parent,rows)
        self.assertTrue(decision['complete'])
        self.assertEqual(decision['reason'],'approved_native_structured_receipt')
    def test_dotnet_556_complete_group_cannot_be_proved_by_csharp(self):
        p='Proficiency in C#, .NET (MVC & Core), and SQL Server for backend development'
        with structural_remediation_simulation('dotnet_v3'):
            rows=self.rows(p);self.supported(rows[0],text='C#')
            for r in rows[1:]:r.update(match_label='none',evidence=[])
            self.assertFalse(self.decision(rows)['complete'])
    def test_dotnet_595_example_cannot_be_proved_by_csharp(self):
        p='Proficiency in web technologies such as Angular, .Net and C#'
        with structural_remediation_simulation('dotnet_v3'):
            rows=self.rows(p);self.supported(rows[0],text='C#')
            self.assertFalse(self.decision(rows)['complete'])
    def test_api_rest_grpc_subset_children_fail_complete_credit(self):
        p='\u00b7 Knowledge of web services, API, REST, and gRPC'
        with structural_remediation_simulation('presentation'):
            rows=self.rows(p)
            for r in rows:r.update(match_label='none',evidence=[])
            self.supported(rows[0],text='Implemented PostgREST APIs')
            self.assertFalse(self.decision(rows)['complete'])
            self.assertTrue(all(r['match_value']==0 for r in apply_guard(rows)))
    def test_restored_adapter_and_deterministic_evaluation(self):
        native=scorer.compute_deterministic_alignment
        with self.assertRaises(RuntimeError):
            with completeness_simulation():raise RuntimeError('probe')
        self.assertIs(scorer.compute_deterministic_alignment,native)
        rows=self.rows();self.assertEqual(self.decision(rows),self.decision(deepcopy(rows)))

if __name__=='__main__':unittest.main()

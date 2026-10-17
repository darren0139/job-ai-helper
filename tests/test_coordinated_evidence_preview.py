"""Investigation regressions. Passing tests reproduce hazards, not authorize release."""
from copy import deepcopy
import json
import unittest

from scripts import preview_coordinated_evidence_v1 as p


class CoordinatedEvidencePreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result=p.study()

    def parent(self,jid,action='maintain'):
        return next(x for x in self.result['parents'] if x['job_id']==jid and action in x['required_actions'])

    def scenario(self,jid,cid,action='maintain'):
        return next(s for s in self.parent(jid,action)['scenarios'] if s['id']==cid)

    def test_whole_corpus_and_versions_unchanged(self):
        self.assertEqual(len(self.result['cohort_counts']),30)
        self.assertEqual(self.result['totals'],dict(baseline=716,A_full=711,B_atomic=721))
        self.assertEqual(len(self.result['parents']),5)
        self.assertEqual(p.n.SCORING_VERSION,'stable-evidence-v1.17-phase6d21')
        self.assertEqual(p.n.CANONICAL_REQUIREMENT_DECOMPOSITION_VERSION,'jd-atomic-requirement-decomposition-v1.1')
        self.assertEqual(self.result['current_versions_unchanged'],p.stage2.inventory.knowledge_identity())

    def test_grounded_objects_parent_identity_and_allocations(self):
        for parent in self.result['parents']:
            original=parent['variants']['A_full'][0]
            for key in ('allocation','source_allocation'):
                self.assertTrue(all(abs(v-1)<1e-12 for v in parent[key].values()))
            for row in parent['variants']['B_atomic']:
                receipt=row['preview_derivation']; raw=parent['original_raw_parent']
                self.assertEqual(raw[slice(*receipt['action_span'])].lower(),receipt['action'])
                self.assertEqual(raw[slice(*receipt['object_span'])],receipt['object_text'])
                self.assertEqual(row['atomic_group_id'],original['atomic_group_id'])
                self.assertEqual(row['scoring_parent_occurrence_id'],parent['parent_occurrence_id'])
                for key in ('parent_text','raw_parent_text','grounding','source','contributes_scoring_allocation'):
                    self.assertEqual(row['source_provenance'][0][key],original['source_provenance'][0][key])

    def test_maintenance_only_overcredit_reproduced_and_A_direct_blocked(self):
        result=self.scenario(359,'maintenance_only')['results']
        self.assertEqual([r['native_label'] for r in result['baseline']['native']],['none','direct'])
        self.assertEqual(result['A_full']['native'][0]['native_label'],'direct')
        gate=result['A_full']['diagnostic_mandatory_action_gate'][0]
        self.assertEqual(gate['missing_actions'],['design','develop'])
        self.assertTrue(gate['direct_blocked'])
        self.assertIsNone(gate['effective_label'])

    def test_atomic_split_alone_also_overcredits(self):
        result=self.scenario(359,'maintenance_only')['results']['B_atomic']
        self.assertEqual([r['native_label'] for r in result['native']],['direct']*3)
        self.assertEqual([r['direct_blocked'] for r in result['diagnostic_mandatory_action_gate']],[True,True,False])

    def test_partial_and_negated_ownership_never_gets_fixture_gate_direct(self):
        for cid in ('development_only','design_only','design_development_no_lifecycle',
                    'technology_usage_no_ownership','incomplete_design','negated_ownership'):
            result=self.scenario(359,cid)['results']['A_full']
            self.assertEqual(result['native'][0]['native_label'],'direct')
            self.assertTrue(result['diagnostic_mandatory_action_gate'][0]['direct_blocked'])

    def test_complete_receipt_survives_and_separate_receipts_do_not_union(self):
        full=self.scenario(359,'all_requested_actions')['results']['A_full']
        self.assertEqual(full['native'][0]['native_label'],'direct')
        self.assertFalse(full['diagnostic_mandatory_action_gate'][0]['direct_blocked'])
        separate=self.scenario(359,'three_actions_separate_rows')['results']['A_full']
        self.assertEqual(len(separate['native'][0]['selected_evidence']),1)
        self.assertTrue(separate['diagnostic_mandatory_action_gate'][0]['direct_blocked'])

    def test_zero_overlap_recovery_cannot_bypass_completeness(self):
        result=self.scenario(359,'zero_overlap_topic')['results']['A_full']
        native=result['native'][0]
        self.assertEqual(native['labels_by_stage']['capped'],'none')
        self.assertEqual(native['native_label'],'direct')
        self.assertEqual(native['recovery']['selected_requirement_overlap_count'],0)
        self.assertTrue(result['diagnostic_mandatory_action_gate'][0]['direct_blocked'])

    def test_fullstack_undercount_and_explicit_layer_positive(self):
        short=self.scenario(479,'all_requested_actions')['results']['A_full']['native'][0]
        explicit=self.scenario(479,'all_actions_explicit_layers')['results']['A_full']['native'][0]
        self.assertEqual(short['native_label'],'none')
        self.assertEqual(explicit['native_label'],'direct')
        integration=self.scenario(479,'postgrest_supabase_integration')['results']['A_full']
        self.assertEqual(integration['native'][0]['native_label'],'direct')
        self.assertTrue(integration['diagnostic_mandatory_action_gate'][0]['direct_blocked'])

    def test_existing_api_contract_and_protocol_guard_distinguished_from_recognition(self):
        controls={c['id']:c for c in self.result['controls']}
        expected={'api_consume':'none','api_postgrest':'none','api_java':'direct',
                  'api_incomplete_design':'weak','api_complete_design':'direct','api_negated':'none',
                  'protocol_and':'none','protocol_or':'direct','protocol_mixed_consumption':'none',
                  'protocol_both_authored':'direct'}
        for cid,label in expected.items():
            self.assertEqual(controls[cid]['forced_api_evaluator_only'][0]['label'],label,cid)
        self.assertEqual(controls['api_incomplete_design']['A_native'][0]['native_label'],'weak')
        self.assertEqual(controls['api_java']['A_native_missing_keyword_input'][0]['native_label'],'direct')
        # The native resolver does not recognize this mixed-protocol phrasing.
        mixed=controls['protocol_mixed_consumption']['A_native'][0]
        self.assertIsNone(mixed['evaluator_label'])
        self.assertEqual(mixed['native_label'],'transferable')
        self.assertEqual(controls['dsa_generic_data']['A_native'][0]['native_label'],'none')

    def test_trace_matches_native_build_and_inputs_are_not_mutated(self):
        req='Design and develop RESTful APIs'; evidence=['Implemented REST API endpoints.']
        canonical=p.stage2.canonical('Responsibilities:\n'+req)
        frozen=deepcopy(canonical)
        result=p.native_path(canonical['requirements'],evidence,canonical['acronym_map'],missing_only=True)
        native=p.n.build_stable_analysis(jd_profile={},raw_jd_text='Responsibilities:\n'+req,
            keyword_match={'present':[],'missing':[{'keyword':req}]},
            resume_profile={'projects':[{'title':'Stage 2B disposable synthetic project','bullets':evidence}],
                            'experience':[],'education':[],'skills':{}},
            raw_resume_text='\n'.join(evidence),retrieval_mode_override='off')
        self.assertEqual([r['native_label'] for r in result],[r['match_label'] for r in native['canonical_requirements']])
        self.assertEqual(canonical,frozen)

    def test_native_allocation_is_dynamic_group_count(self):
        rows=deepcopy(self.parent(359)['variants']['B_atomic'])
        for i,row in enumerate(rows):
            row['match_value']=1.0 if i==0 else 0.0
            row['group_weight_fraction']=0.9  # native aggregator must ignore metadata
        _,numerator,denominator=p.n._weighted_coverage(rows,{'core'})
        self.assertAlmostEqual(numerator/denominator,1/3)
        self.assertEqual(denominator,p.n.IMPORTANCE_WEIGHTS['core'])

    def test_full_preview_matches_frozen_reviewed_baseline(self):
        expected=p.load_independent_oracle()['reviewed_baseline_semantic_sha256']['2b']
        self.assertEqual(p.semantic_preview_digest(self.result),expected)
        self.assertEqual(self.result['current_versions_unchanged'],p.stage2.inventory.knowledge_identity())


if __name__=='__main__':
    unittest.main()

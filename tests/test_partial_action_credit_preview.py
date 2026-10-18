"""Stage 2D independently specified policy/language contracts; not production policy."""
from copy import deepcopy
from pathlib import Path
import unittest

from scripts import preview_partial_action_credit_v1 as p
from taxonomy_discovery import partial_action_credit_preview as policy


def parent(family='embedded'):
    row=next(r for r in p.stage2c.stage2b.independent_parent_rows()
             if policy.prior.extract_obligation(r['variants']['A_full'][0])['object_family']==family)
    req=deepcopy(row['variants']['A_full'][0]);req.pop('recognition',None)
    return req


class PartialActionUnitTests(unittest.TestCase):
    def test_independent_concrete_examples_and_policy_dispositions(self):
        for case in p.load_expectations()['cases']:
            with self.subTest(case=case['id']):
                o=policy.prior.extract_obligation(parent(case.get('family','embedded')))
                index=p.evidence_index([case['text']]);row=next(r for r in index if '.bullets[' in r['source'])
                actual=policy.detect(o,row,index)
                self.assertEqual(actual['supported_actions'],sorted(case['owned']))
                self.assertEqual(actual['technical_scope'],case['technical'])
                self.assertEqual([policy.eligibility(o,actual,name) for name in p.POLICIES],case['policies'])

    def test_independent_non_count_based_policy_table(self):
        o=policy.prior.extract_obligation(parent())
        for case in p.load_expectations()['eligibility_table']:
            actions=case['actions']
            proof={'status':'COMPLETE' if len(actions)==3 else 'INCOMPLETE','supported_actions':actions,
                   'technical_scope':'FULL','complete':set(actions)=={'design','develop','maintain'},'denied_actions':[]}
            self.assertEqual([policy.eligibility(o,proof,name) for name in p.POLICIES],case['expected'])
        # Equal action counts are intentionally different responsibilities.
        self.assertNotEqual(p.load_expectations()['eligibility_table'][4]['expected'],
                            p.load_expectations()['eligibility_table'][6]['expected'])

    def test_independent_native_ceiling_table_and_unchanged_weak_value(self):
        for case in p.load_expectations()['ceiling_table']:
            self.assertEqual(policy.cap_label(case['native'],case['admission']),case['expected'])
        self.assertEqual(p.n.MATCH_VALUES['weak'],0.20)

    def test_source_integrity_and_no_wrong_object_or_usage_credit(self):
        o=policy.prior.extract_obligation(parent())
        index=p.evidence_index(['Designed and developed '+o['object']+'.'])
        row=next(r for r in index if '.bullets[' in r['source'])
        for field,value in [('source',''),('evidence_id','FORGED'),('text','Invented text.')]:
            proof=policy.detect(o,{**row,field:value},index)
            self.assertEqual(proof['status'],'UNVERIFIED_SOURCE')
            self.assertEqual(policy.eligibility(o,proof,'P3'),'REVIEW_REQUIRED')

    def test_independent_boolean_optionality_and_negative_jd_controls(self):
        for case in p.load_expectations()['scope_controls']:
            req=p.stage2c.stage2b.stage2.canonical('Responsibilities:\n'+case['requirement'],proposed=True)['requirements'][0]
            o=policy.prior.extract_obligation(req);index=p.evidence_index([case['evidence']])
            row=next(r for r in index if '.bullets[' in r['source'])
            proof=policy.detect(o,row,index)
            self.assertEqual(o['status'],case['expected_extraction'])
            self.assertEqual([policy.eligibility(o,proof,name) for name in p.POLICIES],case['expected_policies'])

    def test_extended_receipt_offsets_remain_original(self):
        o=policy.prior.extract_obligation(parent())
        for cid in ('passive_me','relative_me','short_scope'):
            text=next(c['text'] for c in p.load_expectations()['cases'] if c['id']==cid)
            index=p.evidence_index([text]);row=next(r for r in index if '.bullets[' in r['source'])
            proof=policy.detect(o,row,index)
            for receipt in proof['extended_receipts']:
                if 'object_span' in receipt:
                    self.assertEqual(text[slice(*receipt['object_span'])],receipt['object_text'])
                    self.assertIsNotNone(policy.prior.action_kind(text[slice(*receipt['action_span'])]))


class PartialActionIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.result=p.study()

    def case(self,cid,family='embedded'):
        source=next(r for r in self.result['parents'] if policy.prior.extract_obligation(r['option_a_row'])['object_family']==family)
        return next(c for c in source['cases'] if c['id']==cid)['comparison']

    def test_original_oracle_preserved_language_fn_reduced_without_fp(self):
        old=self.result['action_confusion']['2c:INDEPENDENT_STAGE2B_ORACLE']
        new=self.result['action_confusion']['2d:INDEPENDENT_STAGE2B_ORACLE']
        self.assertEqual(old,dict(TP=67,TN=191,FP=0,FN=0))
        self.assertEqual(new,old)
        self.assertEqual(self.result['action_confusion']['2d']['FP'],0)
        self.assertLess(self.result['action_confusion']['2d']['FN'],self.result['action_confusion']['2c']['FN'])
        self.assertEqual(self.result['full_confusion']['2d']['FP'],0)

    def test_recommended_weak_requires_design_creation_scope_and_native_credit(self):
        for cid,expected in [('A_maintenance',None),('B_development_maintenance',None),
                             ('C_design_development','weak'),('D_complete','direct')]:
            self.assertEqual(self.case(cid)['policies']['P3']['label'],expected)
        missing=self.case('design_development_no_lifecycle','fullstack')
        self.assertEqual(missing['native_unchecked']['provisional_final_label'],'none')
        self.assertEqual(missing['policies']['P3']['label'],'none')
        self.assertEqual(self.case('fullstack_grounded_pair','fullstack')['policies']['P3']['label'],'weak')
        self.assertEqual(self.case('backend_grounded_pair','backend')['policies']['P3']['label'],'weak')
        cloud=self.case('cloud_two_dimensions','cloud')
        self.assertEqual(cloud['native_unchecked']['provisional_final_label'],'none')
        self.assertEqual(cloud['policies']['P3']['label'],'none')
        self.assertEqual(cloud['policies']['P3']['disposition'],'REVIEW_REQUIRED')
        self.assertEqual(next(iter(cloud['proofs'].values()))['proof']['technical_scope'],'UNPROVEN')

    def test_missing_modifiers_are_not_weak_shortcuts_and_denials_not_exceptions(self):
        for cid in ('short_scope','denied_lifecycle','contradiction','G_denied_short'):
            self.assertTrue(all(x['label']!='weak' for x in self.case(cid)['policies'].values()))

    def test_zero_overlap_recovery_and_forgery_cannot_bypass_final_cap(self):
        for cid in ('F_topic','missing_keywords_topic','forged_id','missing_source'):
            self.assertTrue(all(x['label'] not in ('weak','direct','transferable') for x in self.case(cid)['policies'].values()))
        run=self.case('missing_keywords_partial')['policies']['P3']
        self.assertEqual(run['label'],'weak')
        self.assertEqual(run['parent_contribution'],0.20)
        self.assertTrue(all(s['proposed_capped_label']!='direct' for s in run['pipeline']['stages']))

    def test_complete_alternative_preferred_without_combining_sources(self):
        result=self.case('higher_overlap_partial_before_passive_complete')
        chosen=result['policies']['P3']['selected_evidence']
        self.assertEqual(len(chosen),1)
        self.assertEqual(chosen[0]['source'],'resume_profile.projects[0].bullets[1]')
        split=self.case('three_actions_separate_rows')['policies']['P3']
        self.assertIsNone(split['label'])

    def test_specific_api_and_dsa_remain_authoritative(self):
        controls={c['id']:c for c in self.result['independent_controls']}
        for cid,label in [('api_consume','none'),('api_postgrest','none'),('api_java','direct'),
                          ('api_incomplete_design','weak'),('api_complete_design','direct'),('dsa_generic_data','none')]:
            self.assertEqual(controls[cid]['native'][0]['native_label'],label)
        self.assertEqual(controls['protocol_and']['forced_api_only'][0]['label'],'none')
        self.assertEqual(controls['protocol_or']['forced_api_only'][0]['label'],'direct')

    def test_allocations_canonical_ids_and_versions_remain_native(self):
        for source in self.result['parents']:
            self.assertEqual(source['allocation_before'],1)
            self.assertEqual(source['allocation_after'],1)
            for c in source['cases']:
                self.assertEqual(c['comparison']['parent_allocation'],1)
                self.assertEqual(c['comparison']['canonical_requirement_id_unchanged'],source['option_a_row']['requirement_id'])
        self.assertEqual(p.n.SCORING_VERSION,'stable-evidence-v1.17-phase6d21')
        self.assertEqual(p.n.CANONICAL_REQUIREMENT_DECOMPOSITION_VERSION,'jd-atomic-requirement-decomposition-v1.1')

    def test_all_policy_results_preserve_source_and_ceiling_invariants(self):
        for source in self.result['parents']:
            for case in source['cases']:
                comparison=case['comparison']
                native=comparison['native_unchecked']['provisional_final_label']
                for name,result in comparison['policies'].items():
                    with self.subTest(parent=source['parent_occurrence_id'],case=case['id'],policy=name):
                        if result['label'] in ('direct','transferable'):
                            self.assertEqual(result['disposition'],'COMPLETE')
                        if result['disposition']=='ELIGIBLE_PARTIAL':
                            self.assertIn(result['label'],('weak','none'))
                            if native=='none':self.assertEqual(result['label'],'none')
                            for stage in result['pipeline']['stages']:
                                self.assertNotIn(stage['proposed_capped_label'],('direct','transferable'))
                        for record in result['selected_evidence']:
                            original=comparison['proofs'][record['evidence_id']]
                            self.assertEqual(record['source'],original['record']['source'])
                            self.assertEqual(record['text'],original['record']['text'])
                            self.assertEqual(original['proof']['technical_scope'],'FULL')
                        if result['label'] in ('direct','transferable','weak'):
                            self.assertEqual(len(result['selected_evidence']),1)


if __name__=='__main__':unittest.main()

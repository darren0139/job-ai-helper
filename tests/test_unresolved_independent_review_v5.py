"""Offline preparation integrity and test-only receipt validation; no gold imports."""
from copy import deepcopy
import json
import socket
import sqlite3
import unittest
from unittest.mock import patch

from scripts.adjudicate_unresolved_requirements import prepare
from taxonomy_discovery import unresolved_independent_review as v
from taxonomy_discovery import unresolved_gold_review as gold


class IndependentReviewV5Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch.object(socket,'create_connection',side_effect=AssertionError('No network')),patch.object(sqlite3,'connect',side_effect=AssertionError('No DB access')):
            cls.packet=v.build_packet();cls.audit=v.readiness(cls.packet)
        cls.template=v.template(cls.packet)
        cls.parent=gold.original();cls.inputs,_=prepare(cls.parent)

    def setUp(self):
        # Check the canonical builder once above. Receipt-focused tests exercise
        # actual existing V4/gold validators without repeatedly replaying 40 rows.
        validator=patch.object(v,'validate_packet',return_value=True)
        validator.start();self.addCleanup(validator.stop)
        # Frozen inputs were independently rebuilt in setUpClass. Reuse those
        # same sealed inputs for repeated provenance checks, not new inference.
        for module in (v,v.v4):
            p=patch.object(module,'prepare',return_value=(self.inputs,[]));p.start();self.addCleanup(p.stop)

    def receipt(self,key=None,independent=True):
        t=next(r for r in self.template['decisions'] if key is None or tuple(r['key'])==key)
        r=deepcopy(t);case=next(c for c in self.packet['cases'] if c['key']==r['key'])
        # In-memory TEST ONLY provenance, never written as a real human receipt.
        r.update(chosen_route='RELATIONSHIP',acceptable_routes=['RELATIONSHIP'],diagnostic_label_kind='INVESTIGATION_ROUTE',
            reviewer='TEST ONLY simulated validator actor, not actual adjudication',reviewed_at='2026-10-13T12:00:00+08:00',
            rationale='TEST ONLY schema exercise, not corpus gold',source_reference='TEST ONLY frozen fixture',
            origin='INDEPENDENT_HUMAN' if independent else 'AI_ASSISTED_HUMAN',
            independent_of_model_predictions=independent,reviewer_has_seen_ai_recommendations=not independent,
            independence_basis='TEST ONLY mocked unexposed review' if independent else '',
            source_spans=[case['frozen_input']['requirement_text']],parent_context_consulted=False,
            decision_scope='FROZEN_INPUT',frozen_input_sufficient=True,
            evidence_accessed=[{'kind':'FROZEN_INPUT','reference':f"{r['key'][0]}/{r['key'][1]}",'fingerprint':r['input_fingerprint']}])
        return r

    def reseal(self,packet):
        packet.pop('packet_fingerprint');packet['packet_fingerprint']=v.a.fingerprint(packet)
        return packet

    def test_38_pending_all_critical_and_no_inherited_answers(self):
        self.assertEqual(len(self.packet['cases']),38)
        self.assertEqual(len({tuple(c['key']) for c in self.packet['cases']}),38)
        self.assertTrue(self.audit['all_pending_critical_covered'])
        keys={tuple(c['key']) for c in self.packet['cases']}
        self.assertTrue(all(tuple(k) in keys for k in self.audit['pending_critical_keys']))
        self.assertIn((15,'req_71321f9eff59'),keys)
        self.assertFalse(keys & v.a.NAC)
        self.assertEqual(self.audit['current_gold']['confirmed'],2)
        self.assertFalse(self.audit['current_gold']['labeling_prerequisite_satisfied'])
        self.assertEqual(self.audit['additional_actionable_needed'],18)
        self.assertEqual(len(self.audit['new_material_not_in_v4']),20)

    def test_exact_frozen_inputs_and_allocation_no_text_expansion(self):
        by_key={(c['job_id'],c['requirement_id']):c for c in self.inputs}
        occ={(o['job_id'],o['requirement']['requirement_id']):o['requirement'] for o in v.a.load_occurrences()}
        for row in self.packet['cases']:
            key=tuple(row['key'])
            self.assertEqual(row['frozen_input'],by_key[key])
            self.assertEqual(row['input_fingerprint'],v.a.fingerprint(row['frozen_input']))
            self.assertEqual(row['frozen_input']['nearby_context'],[])
            self.assertEqual(row['allocation_provenance'],v.allocation(occ[key]))
        child=next(c for c in self.packet['cases'] if tuple(c['key'])==v.DEFERRED_CHILD)
        self.assertEqual(child['allocation_provenance']['group_weight_fraction'],0.333333)
        self.assertEqual(child['frozen_input']['requirement_text'],'Proficiency in the modern JavaScript/TypeScript ecosystem')
        self.assertNotIn('React',json.dumps(child))

    def test_blinded_allowlist_no_prior_labels_questions_parent_or_predictions(self):
        forbidden={'recommendation','recommendation_state','rationale','preliminary_route','primary_route','review_question',
            'review_bucket','primary_blocker','original_review_record','inherited_control','inherited_gold',
            'prior_ai_assisted_recommendations_appendix','additional_verified_parent_context','parent_text',
            'raw_parent_text','native_requirement','exact_text_locations','nearby_lines','applicable_predicate_ids'}
        def walk(value):
            if isinstance(value,dict):
                self.assertFalse(set(value)&forbidden)
                for x in value.values():walk(x)
            elif isinstance(value,list):
                for x in value:walk(x)
        walk(self.packet)
        self.assertEqual(set(self.packet),{'packet_version','parent_manifest_fingerprint','source_fingerprint','instructions','route_help','cases','preparation_only','packet_fingerprint'})
        for c in self.packet['cases']:
            self.assertEqual(set(c),{'review_case_number','key','input_fingerprint','frozen_input','source_provenance','allocation_provenance','reviewer_judgment','review_context_fingerprint'})
            self.assertEqual(c['reviewer_judgment']['chosen_route'],'')
            self.assertEqual(c['reviewer_judgment']['acceptable_routes'],[])

    def test_no_prefilled_human_fields_or_fake_receipts(self):
        for r in self.template['decisions']:
            for key in ('chosen_route','reviewer','reviewed_at','origin','diagnostic_label_kind','uncertainty','deferral_rationale'):
                self.assertEqual(r[key],'')
            for key in ('parent_context_consulted','frozen_input_sufficient','independent_of_model_predictions','reviewer_has_seen_ai_recommendations'):
                self.assertIsNone(r[key])
            for key in ('acceptable_routes','source_spans','evidence_accessed','native_supporting_evidence'):
                self.assertEqual(r[key],[])
        with self.assertRaises(ValueError):v.validate_decisions(self.packet,self.template['decisions'])

    def test_packet_validator_detects_resealed_leaks_and_allocation_drift(self):
        # Reuse expected packet in the real exact-allowlist validator body.
        original=self._packet_validator_original
        with patch.object(v,'build_packet',return_value=self.packet):
            self.assertTrue(original(self.packet))
            for field,val in [('prediction','CAPABILITY'),('parent_text','invented parent')]:
                p=deepcopy(self.packet);p['cases'][0][field]=val;self.reseal(p)
                with self.assertRaises(ValueError):original(p)
            p=deepcopy(self.packet);p['cases'][0]['allocation_provenance']['group_weight_fraction']=0.5;self.reseal(p)
            with self.assertRaises(ValueError):original(p)

    def test_actual_existing_validators_reused_and_v5_provenance_preserved(self):
        r=self.receipt();before=gold.ORIGINAL.read_bytes()
        with patch.object(v.v4,'validate_decisions',wraps=v.v4.validate_decisions) as existing:
            result=v.validate_decisions(self.packet,[r])
        existing.assert_called_once()
        self.assertEqual(result['independent_frozen_actionable_new'],1)
        self.assertEqual(result['eligible_independent_receipts_for_separately_authorized_import'],[r])
        self.assertEqual(result['hypothetical_frozen_labeling_prerequisite']['confirmed'],3)
        self.assertEqual(gold.ORIGINAL.read_bytes(),before)
        self.assertEqual(r['review_packet_version'],v.VERSION)

    def test_empty_receipts_add_zero_gold(self):
        result=v.validate_decisions(self.packet,[])
        self.assertEqual(result['completed_decisions'],0)
        self.assertEqual(result['hypothetical_frozen_labeling_prerequisite']['confirmed'],2)
        self.assertEqual(result['eligible_independent_receipts_for_separately_authorized_import'],[])

    def test_exposure_assisted_review_and_false_independence(self):
        r=self.receipt(independent=False);result=v.validate_decisions(self.packet,[r])
        self.assertEqual(result['ai_assisted_human_confirmations'],1)
        self.assertEqual(result['independent_frozen_actionable_new'],0)
        r=self.receipt();r['reviewer_has_seen_ai_recommendations']=True
        with self.assertRaisesRegex(ValueError,'unexposed'):v.validate_decisions(self.packet,[r])

    def test_parent_consultation_cannot_enter_frozen_gold_even_when_claimed_sufficient(self):
        r=self.receipt();r['parent_context_consulted']=True
        with self.assertRaisesRegex(ValueError,'Parent consultation'):v.validate_decisions(self.packet,[r])
        r.update(decision_scope='CONTEXT_AWARE_REVIEW',frozen_input_sufficient=False)
        result=v.validate_decisions(self.packet,[r])
        self.assertEqual(result['independent_context_aware_not_frozen_gold'],1)
        self.assertEqual(result['independent_frozen_actionable_new'],0)
        self.assertEqual(result['eligible_independent_receipts_for_separately_authorized_import'],[])
        r['parent_source_spans']=['outside parent']
        with self.assertRaisesRegex(ValueError,'separately versioned'):v.validate_decisions(self.packet,[r])

    def test_extended_predicate_or_source_evidence_is_not_frozen_gold(self):
        r=self.receipt();r['evidence_accessed'].append({'kind':'OUTSIDE_FROZEN_CONTRACT','reference':'TEST ONLY extended contract','fingerprint':'a'*64})
        with self.assertRaisesRegex(ValueError,'Extended evidence'):v.validate_decisions(self.packet,[r])
        r.update(decision_scope='CONTEXT_AWARE_REVIEW',frozen_input_sufficient=False)
        self.assertEqual(v.validate_decisions(self.packet,[r])['independent_context_aware_not_frozen_gold'],1)

    def test_existing_deferred_child_remains_protected(self):
        r=self.receipt(v.DEFERRED_CHILD)
        with self.assertRaisesRegex(ValueError,'Existing deferred child'):v.validate_decisions(self.packet,[r])
        r.update(chosen_route='DEFER',acceptable_routes=[],diagnostic_label_kind='DEFERRED',frozen_input_sufficient=False,
                 deferral_rationale='TEST ONLY insufficient frozen scope, not a human label')
        result=v.validate_decisions(self.packet,[r])
        self.assertEqual(result['independent_frozen_actionable_new'],0)
        self.assertEqual(result['independent_deferrals'],1)

    def test_root_cause_requires_exact_native_support_and_access(self):
        r=self.receipt();r['diagnostic_label_kind']='VERIFIED_ROOT_CAUSE'
        with self.assertRaisesRegex(ValueError,'Causal claims'):v.validate_decisions(self.packet,[r])
        r['native_supporting_evidence']=[{'field':'registry_reason','exact_value':'invented'}]
        with self.assertRaisesRegex(ValueError,'exact frozen'):v.validate_decisions(self.packet,[r])
        c=next(c for c in self.packet['cases'] if c['key']==r['key'])
        r['native_supporting_evidence']=[{'field':'status','exact_value':c['frozen_input']['resolver']['status']}]
        r['evidence_accessed'].append({'kind':'NATIVE_FROZEN_DIAGNOSTICS','reference':f"{r['key'][0]}/{r['key'][1]}",'fingerprint':r['input_fingerprint']})
        with self.assertRaisesRegex(ValueError,'Causal claims'):v.validate_decisions(self.packet,[r])
        r['native_supporting_evidence']=[{'field':'registry_reason','exact_value':c['frozen_input']['resolver']['registry_reason']}]
        result=v.validate_decisions(self.packet,[r])
        self.assertTrue(result['causal_truth_and_reviewer_independence_not_authenticated_by_software'])

    def test_source_access_cannot_be_replaced_by_diagnostic_access(self):
        r=self.receipt();r['evidence_accessed'][0]['kind']='NATIVE_FROZEN_DIAGNOSTICS'
        with self.assertRaisesRegex(ValueError,'source access'):v.validate_decisions(self.packet,[r])

    def test_duplicates_nac_replacement_fingerprints_fabricated_spans_rejected(self):
        r=self.receipt()
        with self.assertRaises(ValueError):v.validate_decisions(self.packet,[r,r])
        for field,val in [('key',[163,'req_6677d37f660c']),('input_fingerprint','stale'),('review_packet_version','v4'),
                          ('source_spans',['fabricated source']),('reviewed_at','2026-10-13T12:00:00'),
                          ('origin','MODEL'),('reviewer','')]:
            changed=deepcopy(r);changed[field]=val
            with self.assertRaises(ValueError):v.validate_decisions(self.packet,[changed])
        changed=deepcopy(r);changed['model_prediction']='CAPABILITY'
        with self.assertRaises(ValueError):v.validate_decisions(self.packet,[changed])

    def test_deferral_not_used_to_fill_numeric_or_critical_gate(self):
        r=self.receipt();r.update(chosen_route='UNKNOWN',acceptable_routes=[],diagnostic_label_kind='DEFERRED',frozen_input_sufficient=False,
                                 deferral_rationale='TEST ONLY unresolved diagnostic evidence')
        result=v.validate_decisions(self.packet,[r])
        self.assertEqual(result['independent_deferrals'],1)
        self.assertEqual(result['hypothetical_frozen_labeling_prerequisite']['confirmed'],2)
        self.assertFalse(result['hypothetical_frozen_labeling_prerequisite']['labeling_prerequisite_satisfied'])

    def test_reviewer_markdown_is_blinded_and_has_blank_decisions(self):
        text=v.markdown(self.packet)
        self.assertEqual(text.count('## Review '),38)
        self.assertNotIn('Source-specific question',text)
        self.assertNotIn('Previous AI-assisted recommendations',text)
        self.assertNotIn('Additional verified parent',text)
        self.assertNotIn('NAC',text)
        self.assertIn('Decision ___',text)

    def test_protected_hashes_unchanged_and_prior_packets_preserved(self):
        self.assertEqual(len(self.audit['protected_hashes']),139)
        for path,digest in self.audit['protected_hashes'].items():self.assertEqual(v.sha(v.ROOT/path),digest)
        self.assertFalse(self.audit['v4_genuinely_blinded'])
        self.assertEqual(len(self.audit['source_recovery_verified_pending']),34)
        self.assertEqual(len(self.audit['source_recovery_partial_pending']),4)


# Save the real validator for integrity tests while receipt tests mock rebuilds.
IndependentReviewV5Tests._packet_validator_original=staticmethod(v.validate_packet)
if __name__=='__main__':unittest.main()

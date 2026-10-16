"""Synthetic review metadata tests never create or import real human gold."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from scripts.adjudicate_unresolved_requirements import prepare
from taxonomy_discovery import unresolved_review_packet as review
from taxonomy_discovery import unresolved_adjudication as a
from taxonomy_discovery import unresolved_gold_review as gold


class V4ReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parent=gold.original();cls.inputs,_=prepare(cls.parent)
        by_key={tuple(e['key']):(e,c) for e,c in zip(cls.parent['expectations'],cls.inputs)}
        rows=[]
        # CI uses frozen canonical inputs only. No local DB or uncommitted review
        # exports are required; parent text below is explicitly a test fixture.
        for number,job,rid in review.SELECTION:
            e,c=by_key[(job,rid)]
            rows.append({'case_number':number,'key':[job,rid], 'input_fingerprint':e['input_fingerprint'],
                'source_fingerprint':cls.parent['source_fingerprint'],'review_context_fingerprint':'a'*64,
                'exact_frozen_requirement':c['requirement_text'],'additional_verified_parent_context':[{
                    'raw_parent_text':c['requirement_text']+' TEST SOURCE ONLY','source':'test_source',
                    'parent_occurrence_id':'test_parent','grounding':{'span_id':'test_span'}}],
                'inherited_control':{'acceptable_routes':e['acceptable_routes'],'original_review_reason':e['review_reason']}
                    if e['acceptable_routes'] else None,
                'human_decision':'','additional_verified_headings':[], 'technology_candidates':[],
                'activity':{'exact_text_span':'','source':'CURRENT_REQUIREMENT'},
                'structure':{'type':'UNKNOWN','native_structure':{'source':'test','mode':None},
                    'group_weight_fraction':1.0,'source_group_fraction':1.0,'parent_allocations':[]},
                'capability_candidates':[],'native_resolution':{'status':'unresolved'},
                'review_question':'Review source evidence, not prior predictions','source_jd_sha256':'b'*64,
                'source_references':['test fixture']})
        cls.packet={'packet_version':review.VERSION,'cases':rows,
                    'prior_ai_assisted_recommendations_appendix':[]}
        cls.packet['packet_fingerprint']=a.fingerprint(cls.packet)

    def decision(self,independent=False):
        r=deepcopy(review.template(self.packet)['decisions'][0])
        case=next(c for c in self.packet['cases'] if c['key']==r['key'])
        r.update(chosen_route='RELATIONSHIP',acceptable_routes=['RELATIONSHIP'],
            origin='INDEPENDENT_HUMAN' if independent else 'AI_ASSISTED_HUMAN',
            independent_of_model_predictions=independent,reviewer_has_seen_ai_recommendations=not independent,
            independence_basis='TEST ONLY simulated blind source review' if independent else '',
            reviewer='TEST ONLY not a human approval',reviewed_at='2026-10-12T12:00:00+08:00',
            rationale='TEST ONLY validator exercise, never a real corpus decision',source_reference='test fixture',
            source_spans=[case['exact_frozen_requirement']],parent_context_consulted=False,
            decision_scope='FROZEN_INPUT',frozen_input_sufficient=True)
        return r

    def test_exact20_unique_and_18_blank_templates_two_inherited(self):
        t=review.template(self.packet)
        self.assertEqual(len(t['decisions']),18);self.assertEqual(len(t['inherited_controls_not_new_receipts']),2)
        keys=[tuple(r['key']) for r in t['decisions']+t['inherited_controls_not_new_receipts']]
        self.assertEqual(len(set(keys)),20)
        self.assertEqual(set(keys),{(j,r) for _,j,r in review.SELECTION})
        for r in t['decisions']:
            self.assertEqual(r['chosen_route'],r['origin']);self.assertEqual(r['chosen_route'],'')
            self.assertEqual(r['reviewer'],r['reviewed_at']);self.assertEqual(r['reviewer'],'')
            self.assertIsNone(r['parent_context_consulted']);self.assertIsNone(r['independent_of_model_predictions'])

    def test_blank_template_is_not_approval(self):
        with self.assertRaises(ValueError):review.validate_decisions(self.packet,review.template(self.packet)['decisions'])

    def test_ai_assisted_confirmation_never_inflates_gold(self):
        result=review.validate_decisions(self.packet,[self.decision()])
        self.assertEqual(result['ai_assisted_human_confirmations'],1)
        self.assertEqual(result['independent_frozen_actionable_new'],0)
        self.assertEqual(result['hypothetical_frozen_labeling_prerequisite']['confirmed'],2)
        self.assertFalse(result['hypothetical_frozen_labeling_prerequisite']['labeling_prerequisite_satisfied'])
        self.assertEqual(result['eligible_independent_receipts_for_separately_authorized_import'],[])

    def test_independent_receipt_uses_existing_validator_without_writes(self):
        before=gold.ORIGINAL.read_bytes()
        with patch.object(gold,'versioned_manifest',wraps=gold.versioned_manifest) as existing:
            result=review.validate_decisions(self.packet,[self.decision(True)])
        existing.assert_called_once()
        self.assertEqual(result['independent_frozen_actionable_new'],1)
        self.assertEqual(gold.ORIGINAL.read_bytes(),before)

    def test_exposed_reviewer_cannot_claim_independent_confirmation(self):
        r=self.decision(True);r['reviewer_has_seen_ai_recommendations']=True
        with self.assertRaisesRegex(ValueError,'unexposed'):review.validate_decisions(self.packet,[r])

    def test_context_aware_independent_record_not_frozen_gold(self):
        r=self.decision(True);r.update(parent_context_consulted=True,decision_scope='CONTEXT_AWARE_REVIEW',frozen_input_sufficient=False)
        result=review.validate_decisions(self.packet,[r])
        self.assertEqual(result['independent_context_aware_not_frozen_gold'],1)
        self.assertEqual(result['independent_frozen_actionable_new'],0)

    def test_parent_dependent_confirmation_of_frozen_input_rejected(self):
        r=self.decision();r.update(parent_context_consulted=True,frozen_input_sufficient=False)
        with self.assertRaisesRegex(ValueError,'Parent-dependent'):review.validate_decisions(self.packet,[r])

    def test_explicit_deferral_is_non_actionable(self):
        r=self.decision(True);r.update(chosen_route='DEFER',acceptable_routes=[],frozen_input_sufficient=False)
        result=review.validate_decisions(self.packet,[r])
        self.assertEqual(result['independent_deferrals'],1)
        self.assertEqual(result['independent_frozen_actionable_new'],0)

    def test_duplicates_nac_replacement_and_stale_fingerprints_rejected(self):
        r=self.decision()
        with self.assertRaises(ValueError):review.validate_decisions(self.packet,[r,r])
        for key in ([163,'req_6677d37f660c'],[999,'unknown']):
            changed=deepcopy(r);changed['key']=key
            with self.assertRaises(ValueError):review.validate_decisions(self.packet,[changed])
        for field in ('input_fingerprint','source_fingerprint','review_context_fingerprint','review_packet_fingerprint'):
            changed=deepcopy(r);changed[field]='stale'
            with self.assertRaises(ValueError):review.validate_decisions(self.packet,[changed])

    def test_parent_quotes_grounded_and_context_attested(self):
        r=self.decision();r['parent_source_spans']=['invented']
        with self.assertRaises(ValueError):review.validate_decisions(self.packet,[r])
        r['parent_source_spans']=['TEST SOURCE ONLY']
        with self.assertRaisesRegex(ValueError,'context declaration'):review.validate_decisions(self.packet,[r])

    def test_packet_integrity_and_actual_fields_required(self):
        changed=deepcopy(self.packet);changed['cases'][0]['exact_frozen_requirement']='edited'
        with self.assertRaisesRegex(ValueError,'integrity'):review.validate_decisions(changed,[self.decision()])
        for field,value in [('reviewed_at','2026-10-12T12:00:00'),('rationale',''),('origin','MODEL'),
                            ('chosen_route','invalid'),('parent_context_consulted',None),('source_spans',['invented'])]:
            r=self.decision();r[field]=value
            with self.assertRaises(ValueError):review.validate_decisions(self.packet,[r])

    def test_evidence_decisions_precede_ai_appendix(self):
        text=review.markdown(self.packet)
        self.assertLess(text.index('Source evidence and decisions'),text.index('Previous AI-assisted recommendations'))
        self.assertLess(text.index('Human decision: ______'),text.index('Previous AI-assisted recommendations'))
        self.assertIn('critical pending control outside the shortlist',text)
        self.assertIn('AI-assisted/context-only records stay',text)
        self.assertIn('DEFERRED',text)

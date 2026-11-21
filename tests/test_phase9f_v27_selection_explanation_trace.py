"""Evidence-sourced, decision-time Base/Library explanations; no ranking changes."""
from __future__ import annotations
import unittest
from copy import deepcopy
from unittest.mock import patch
from tailoring import deterministic_bullet_allocation as a
from tailoring.phase9f_project_bullet_sources_v2_3 import explain_saved_bullet_decision

BASE = "Built a Python service to execute tests and integrate CI."
LIBRARY = "Implemented unit tests and GitHub Actions CI for the Python application."
EXTRA = "Developed a user interface for applicants."


def pair():
    candidate = {
        "title": "Example", "display_title": "Example", "currently_in_resume": True,
        "in_evidence_library": True,
        "resume_evidence": {"bullets": [BASE], "skills": ["CI"], "tools": ["Python"]},
        "evidence_library_evidence": {"bullets": [LIBRARY, EXTRA], "skills": [], "tools": ["GitHub Actions"]},
    }
    ranking = {
        "project_id": "p-one", "final_score": 70,
        "requirement_matches": [
            {"requirement_id":"req-test", "requirement_text":"Execute unit tests", "match_label":"direct", "importance":"required", "coverage_points":10},
            {"requirement_id":"req-ci", "requirement_text":"Build automation", "match_label":"transferable", "importance":"core", "coverage_points":8},
        ],
    }
    priorities = {
        BASE: {"supported_requirement_ids":["req-ci"], "protected_requirement_ids":["req-ci"], "evidence_priority":2},
        LIBRARY: {"supported_requirement_ids":["req-test","req-ci"], "protected_requirement_ids":["req-test","req-ci"], "evidence_priority":1},
        EXTRA: {"supported_requirement_ids":[], "protected_requirement_ids":[], "evidence_priority":3},
    }
    def priority_builder(*, bullets, ranking_row):
        return [{"bullet_index":i,"bullet_text":b, **priorities[b]} for i,b in enumerate(bullets)]
    return (candidate,ranking),priority_builder


class TraceTests(unittest.TestCase):
    def allocate(self, mode="adaptive"):
        row, builder = pair()
        with patch.object(a,"build_bullet_evidence_priorities",side_effect=builder):
            return a.build_deterministic_bullet_allocation(selected_pairs=[row], max_bullets_per_project=2, allocation_mode=mode)

    def test_selected_receipt_has_real_step_peer(self):
        result=self.allocate()
        plan=result['projects'][0]
        selected=[r for r in plan['bullet_decision_receipts'] if r['selected']]
        library=next(r for r in selected if r['sources']==['library'])
        why=explain_saved_bullet_decision(library)
        self.assertEqual(why['status'],'step_recorded')
        self.assertEqual(why['peer']['bullet'],BASE)
        self.assertEqual(why['metric'],'unique_required_core')
        self.assertGreater(why['chosen_value'],why['peer_value'])
        self.assertFalse(why['word_count_is_decision_factor'])

    def test_trace_deterministic(self):
        self.assertEqual(self.allocate(),self.allocate())

    def test_all_canonical_does_not_claim_winner(self):
        receipts=self.allocate('all_canonical_before_fitting')['projects'][0]['bullet_decision_receipts']
        self.assertEqual(sum(x['selected'] for x in receipts),3)
        for receipt in receipts:
            self.assertEqual(explain_saved_bullet_decision(receipt)['status'],'all_admitted')

    def test_missing_legacy_receipt_no_fabricated_rank(self):
        why=explain_saved_bullet_decision({'bullet_id':'b','selected':True,'reason':'baseline_budget'})
        self.assertEqual(why['status'],'partial')
        self.assertIsNone(why['peer'])

    def test_forged_or_wrong_identity_withheld(self):
        receipt=next(r for r in self.allocate()['projects'][0]['bullet_decision_receipts'] if r['selected'])
        forged=deepcopy(receipt)
        forged['decision_context']['selected']['bullet_id']='other'
        self.assertEqual(explain_saved_bullet_decision(forged)['status'],'withheld')

    def test_unselected_receipt_post_allocation_only(self):
        receipts=self.allocate()['projects'][0]['bullet_decision_receipts']
        excluded=[r for r in receipts if not r['selected']]
        self.assertEqual(len(excluded),1)
        self.assertEqual(excluded[0]['explanation_completeness'],'post_selection_only')
        self.assertEqual(explain_saved_bullet_decision(excluded[0])['status'],'partial')

    def test_rank_tuples_match_internal_keys_and_never_word_count(self):
        result=self.allocate()
        for step in result['selection_trace']:
            d=step['decision_context']
            self.assertNotIn('word_count',d['factor_order'])
            self.assertFalse(d['word_count_used_for_selection'])
            self.assertEqual(len(d['selected']['rank_tuple']),len(d['factor_order']))

    def test_preselected_and_used_ranking_methods_unchanged(self):
        # Explanation fields are append-only; allocation picks expected bullet IDs.
        result=self.allocate()
        plan=result['projects'][0]
        self.assertIn(LIBRARY,plan['allocated_blueprint_bullets'])
        self.assertIn(BASE,plan['allocated_blueprint_bullets'])
        self.assertNotIn(EXTRA,plan['allocated_blueprint_bullets'])

if __name__=='__main__':unittest.main()

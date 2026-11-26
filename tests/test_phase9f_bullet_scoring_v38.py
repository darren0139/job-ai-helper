"""V3.8 frozen JD scores, conservative deduplication receipt, and source immutability."""
from __future__ import annotations

from copy import deepcopy
import unittest
from tailoring.phase9f_bullet_score_v38 import (score_saved_bullets, attach_bullet_scores, lookup_scored_wording)

BASE = ('Built 30-job corpus regression/audit tooling and GitHub Actions CI across Windows/Ubuntu '
        'to validate scoring, taxonomy resolution, sessions, and UI workflows.')
LIB = ('Added automated unit tests and GitHub Actions CI across Ubuntu and Windows, '
       'running dependency checks, compilation, the full test suite, and a Streamlit startup health check.')
LETTER = 'Added tailored cover letter generation and follow-up support grounded in the résumé.'


def fixture(*, both=False):
    candidates = [
        {'text': BASE, 'source_labels': ['Selected Base', 'Current final'], 'saved_jd_ids': ['r_ci', 'r_audit'],
         'selected_for_proposed_b': bool(both), 'in_original_a': True},
        {'text': LIB, 'source_labels': ['Evidence Library', 'Current final'], 'saved_jd_ids': ['r_ci', 'r_test'],
         'selected_for_proposed_b': True, 'in_original_a': True},
        {'text': LETTER, 'source_labels': ['Evidence Library'], 'saved_jd_ids': ['r_letter'],
         'selected_for_proposed_b': True, 'in_original_a': False},
    ]
    proposal = {'status': 'candidate', 'projects': [{'project': 'Job AI Helper',
              'after': [item['text'] for item in candidates if item['selected_for_proposed_b']],
              'sources': [item['source_labels'] for item in candidates if item['selected_for_proposed_b']]}],
              'source_comparison': {'projects': [{'project': 'Job AI Helper', 'candidates': candidates}]}}
    matches=[{'requirement_id': rid, 'requirement_text': name, 'coverage_points': points,
              'importance': importance, 'match_label': 'direct'}
             for rid,name,points,importance in [
                 ('r_ci','Configuration and build automation',5.0,'core'),
                 ('r_audit','Software regression audit and validation',4.0,'preferred'),
                 ('r_test','Unit testing',8.0,'core'),
                 ('r_letter','Cover letter writing',2.0,'preferred')]]
    projects={'candidate_project_ranking':[{'display_title':'Job AI Helper','requirement_matches':matches}]}
    return proposal,projects


class BulletJDScoring(unittest.TestCase):
    def test_weighted_points_and_marginal_are_distinct(self):
        proposal,projects=fixture()
        receipt=score_saved_bullets(proposal,projects)
        self.assertEqual(receipt['status'],'available',receipt)
        rows=receipt['bullets']
        self.assertEqual([row['standalone_weighted_points'] for row in rows],[9.,13.,2.])
        self.assertEqual([row['marginal_in_proposal_points'] for row in rows],[None,13.,2.])
        self.assertEqual(receipt['proposed_distinct_weighted_points'],15.)
        self.assertEqual(rows[0]['native_per_bullet_score'],None)

    def test_pair_contains_shared_and_unique_protected_requirement_evidence(self):
        proposal,projects=fixture()
        pair=score_saved_bullets(proposal,projects)['same_work_pairs']
        self.assertEqual(len(pair),1)
        self.assertEqual((pair[0]['first_unique_vs_other_points'],pair[0]['second_unique_vs_other_points']),(4.,8.))
        self.assertEqual(pair[0]['first_required_core_unique_ids'],[])
        self.assertEqual(pair[0]['second_required_core_unique_ids'],['r_test'])
        self.assertFalse(pair[0]['both_in_proposal'])

    def test_duplicate_filled_proposal_never_mislabeled_success(self):
        proposal,projects=fixture(both=True)
        receipt=score_saved_bullets(proposal,projects)
        self.assertEqual(receipt['status'],'unverified_proposal')
        self.assertTrue(receipt['same_work_pairs'][0]['both_in_proposal'])
        self.assertEqual(receipt['bullets'][0]['marginal_in_proposal_points'],4.)
        self.assertEqual(receipt['bullets'][1]['marginal_in_proposal_points'],8.)

    def test_unrelated_letter_not_replaced_by_ci(self):
        proposal,projects=fixture()
        self.assertEqual(len(score_saved_bullets(proposal,projects)['same_work_pairs']),1)
        self.assertNotIn(LETTER,tuple(score_saved_bullets(proposal,projects)['same_work_pairs'][0].values()))

    def test_missing_frozen_weights_withholds(self):
        proposal,projects=fixture()
        bad={'candidate_project_ranking':[]}
        self.assertEqual(score_saved_bullets(proposal,bad)['status'],'unavailable')
        proposal['source_comparison']['projects'][0]['candidates'][0]['saved_jd_ids']=['unknown']
        self.assertEqual(score_saved_bullets(proposal,projects)['status'],'unavailable')

    def test_incompatible_generation_and_project_never_share_score(self):
        proposal,projects=fixture()
        scored=attach_bullet_scores(proposal,projects)
        result={'proposal':scored}
        self.assertEqual(lookup_scored_wording(result,'Job AI Helper',LIB)['standalone_weighted_points'],13.)
        self.assertIsNone(lookup_scored_wording(result,'QueryAI',LIB))
        self.assertIsNone(lookup_scored_wording({},'Job AI Helper',LIB))

    def test_attached_receipts_do_not_mutate_proposal_or_sources(self):
        proposal,projects=fixture()
        original=deepcopy((proposal,projects))
        scored=attach_bullet_scores(proposal,projects)
        self.assertEqual((proposal,projects),original)
        self.assertEqual(scored['projects'],proposal['projects'])
        self.assertIn('v38_bullet_score_receipt',scored)

    def test_unknown_membership_fails_closed(self):
        proposal,projects=fixture()
        proposal['source_comparison']['projects'][0]['candidates'][0].pop('selected_for_proposed_b')
        self.assertEqual(score_saved_bullets(proposal,projects)['status'],'unavailable')

if __name__=='__main__':unittest.main()

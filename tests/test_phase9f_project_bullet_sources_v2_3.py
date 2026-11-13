"""Focused regressions: source facts, canonical policy and absence of invented bullet quality comparisons."""
from __future__ import annotations
import unittest
from unittest.mock import patch
from tailoring.phase9f_project_bullet_sources_v2_3 import build_project_bullet_source_view, _bound_candidate_sources


def fixture():
    candidates = [
        {"title": "Job AI Helper", "display_title": "Job AI Helper — System", "currently_in_resume": True, "in_evidence_library": True,
         "resume_evidence": {"bullets": ["Base implementation", "Shared exact line"]},
         "evidence_library_evidence": {"bullets": ["Approved more detailed canonical bullet", "Shared exact line", "Another Library bullet"]}},
        {"title": "New Library Project", "currently_in_resume": False, "in_evidence_library": True,
         "resume_evidence": None, "evidence_library_evidence": {"bullets": ["Library only bullet"]}},
    ]
    ranked = [
        {"title": "Job AI Helper", "source": "both", "selection_rank": 1, "selection_score": 100,
         "requirement_matches": [{"requirement_id": "req1", "requirement_text": "Testing", "match_label": "weak", "evidence_snippets": ["Shared exact line"]}]},
        {"title": "New Library Project", "source": "evidence_library", "selection_rank": 2, "requirement_matches": []},
    ]
    generated = [
        {"title": "Job AI Helper", "source": "both",
         "selected_blueprint_bullets": ["Approved more detailed canonical bullet", "Shared exact line"],
         "draft_bullets": ["Approved more detailed canonical bullet", "Newly rewritten sentence"],
         "bullet_evidence_priorities": [
             {"bullet_index": 0, "bullet_text": "Approved more detailed canonical bullet", "supported_requirement_ids": ["req1"], "evidence_value": 9.0, "protect_during_fitting": True},
             {"bullet_index": 1, "bullet_text": "Newly rewritten sentence", "supported_requirement_ids": [], "evidence_value": 0.0}]},
        {"title": "New Library Project", "source": "evidence_library",
         "selected_blueprint_bullets": ["Library only bullet"], "draft_bullets": ["Library only bullet"]}
    ]
    return {"recommended_projects": generated, "candidate_project_ranking": ranked}, candidates


class BulletSourcesV23Tests(unittest.TestCase):
    def test_independent_base_library_and_draft_bullets(self):
        p,c = fixture(); v=build_project_bullet_source_view(p,c)
        self.assertEqual([len(x['base_bullets']) for x in v['projects']], [2,0])
        self.assertEqual(v['projects'][0]['library_count'],3)
        self.assertEqual(v['projects'][0]['canonical_count'],2)
        self.assertEqual(v['projects'][0]['draft_count'],2)
        self.assertEqual(v['projects'][0]['base_only_count'],1)
        self.assertEqual(v['projects'][0]['library_only_count'],2)
        self.assertIn('policy',v['notice'])
    def test_no_quality_winner_inferred_from_canonical_policy(self):
        p,c = fixture(); v=build_project_bullet_source_view(p,c)
        self.assertEqual(v['projects'][0]['base_bullets'][0]['Canonical Library text?'],'No')
        self.assertEqual(v['projects'][0]['library_bullets'][0]['Canonical selection'],'Selected')
        self.assertEqual(v['projects'][0]['draft_bullets'][1]['Wording lineage'],'Rephrased/generated; no exact-text lineage')
        self.assertNotIn('stronger',str(v).lower())
    def test_saved_draft_priority_is_not_project_quality_comparison(self):
        p,c=fixture(); r=build_project_bullet_source_view(p,c)['projects'][0]['draft_bullets']
        self.assertEqual(r[0]['Saved JD requirement IDs'],'req1')
        self.assertEqual(r[0]['Saved evidence priority'],9.0)
        self.assertEqual(r[1]['Saved evidence priority'],0.0)
    def test_wrong_source_provenance_blocks_comparison(self):
        p,c=fixture();p['recommended_projects'][0]['source']='resume'
        self.assertFalse(build_project_bullet_source_view(p,c)['projects'])
    def test_same_title_different_saved_project_id_fails_closed(self):
        p,c=fixture()
        p['recommended_projects'][0]['project_id']='project-A'
        p['candidate_project_ranking'][0]['project_id']='project-B'
        self.assertFalse(build_project_bullet_source_view(p,c)['projects'])
    def test_disagreement_between_rank_source_and_draft_source_fails_closed(self):
        p,c=fixture()
        p['recommended_projects'][0]['source']='both'
        p['candidate_project_ranking'][0]['source']='resume'
        self.assertFalse(build_project_bullet_source_view(p,c)['projects'])
    def test_missing_or_ambiguous_candidates_block_comparison(self):
        p,c=fixture();self.assertFalse(build_project_bullet_source_view(p,c+c[:1])['projects'])
        self.assertFalse(build_project_bullet_source_view(p,[])['projects'])
    def test_noncanonical_selected_bullet_rejected(self):
        p,c=fixture();p['recommended_projects'][0]['selected_blueprint_bullets']=['Not in library']
        self.assertFalse(build_project_bullet_source_view(p,c)['projects'])
    def test_mismatched_priority_index_does_not_misattribute_jd_proof(self):
        p,c=fixture();p['recommended_projects'][0]['bullet_evidence_priorities'][0]['bullet_text']='foreign'
        row=build_project_bullet_source_view(p,c)['projects'][0]['draft_bullets'][0]
        self.assertEqual(row['Saved JD requirement IDs'],'')
        self.assertEqual(row['Saved evidence priority'],None)
    def test_missing_ranking_cannot_claim_selection(self):
        p,c=fixture();p['candidate_project_ranking']=[]
        self.assertFalse(build_project_bullet_source_view(p,c)['projects'])
    def test_generated_order_does_not_claim_rank_reorder(self):
        p,c=fixture();p['recommended_projects'].reverse()
        v=build_project_bullet_source_view(p,c)
        self.assertEqual(v['projects'][0]['rank'],2)
    def test_frozen_source_mismatch_blocks_without_reading_live_library(self):
        decision={"decision_fingerprint":"df", "starting_snapshot":{
            "starting_snapshot_fingerprint":"sf", "source_identity":{"source_id":"base-v6"},
            "resume_profile_snapshot":{"projects":[]}}}
        execution={"phase9e_decision_fingerprint":"not-df", "starting_snapshot_fingerprint":"sf", "source_id":"base-v6",
                   "evidence_snapshot_fingerprint":"ev", "evidence_snapshot":{"snapshot_fingerprint":"ev", "rows":[{"id":1}]}}
        rows, msg = _bound_candidate_sources(execution,decision)
        self.assertIsNone(rows)
        self.assertIn('does not match',msg)
    def test_missing_frozen_inputs_do_not_use_mutable_library(self):
        self.assertIsNone(_bound_candidate_sources(None,None)[0])
        self.assertIsNone(_bound_candidate_sources({"source_id":"x"},None)[0])
    def test_list_integrity_rejects_non_text_bullets(self):
        p,c=fixture();c[0]['resume_evidence']['bullets'].append({"unexpected":1})
        self.assertFalse(build_project_bullet_source_view(p,c)['projects'])

if __name__=='__main__':unittest.main()

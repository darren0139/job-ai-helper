"""V2.7 focused mixed-source policy, provenance, and legacy negative guards."""
import copy
import unittest
from unittest.mock import patch

from tailoring.combined_project_bullet_sources_v2_7 import (
    POLICY_VERSION, bullet_sources, source_bullet_records,
)
from tailoring import deterministic_bullet_allocation as allocation
from tailoring.phase9f_project_bullet_sources_v2_3 import build_project_bullet_source_view


def candidate():
    return {
        'title':'Demo','display_title':'Demo',
        'currently_in_resume':True,'in_evidence_library':True,
        'resume_evidence':{'bullets':['Built backend API with Python and tests.', 'Shared verified bullet.'], 'skills':['Python'], 'tools':[]},
        'evidence_library_evidence':{'bullets':['Added generic homepage.', 'Shared verified bullet.'], 'skills':[], 'tools':['React']},
    }


def priorities(*, bullets, ranking_row):
    out=[]
    for i,bullet in enumerate(bullets):
        hit='backend API' in bullet
        out.append({'bullet_index':i,'bullet_text':bullet,
                    'supported_requirement_ids':['req_backend'] if hit else [],
                    'protected_requirement_ids':['req_backend'] if hit else [],
                    'unique_required_core_count':1 if hit else 0,
                    'evidence_value':30 if hit else 0,
                    'evidence_priority':1 if hit else i+2})
    return out


class CombinedSelectionV27Tests(unittest.TestCase):
    def test_union_and_exact_dedup_sources(self):
        rows=source_bullet_records(candidate())
        self.assertEqual(len(rows),3)
        self.assertEqual(bullet_sources(candidate(),'Shared verified bullet.'),['base','library'])
        self.assertEqual(bullet_sources(candidate(),'Built backend API with Python and tests.'),['base'])

    def test_source_order_is_neutral(self):
        c=candidate()
        rows1=source_bullet_records(c)
        c['resume_evidence']['bullets'].reverse()
        c['evidence_library_evidence']['bullets'].reverse()
        self.assertEqual([(x["text"], x["sources"]) for x in rows1],
                         [(x["text"], x["sources"]) for x in source_bullet_records(c)])

    def test_malformed_source_and_ownership_rejected(self):
        c=candidate();c['resume_evidence']['bullets'].append({'invalid':1})
        with self.assertRaises(ValueError): source_bullet_records(c)
        c=candidate();c['currently_in_resume']=False
        with self.assertRaises(ValueError): source_bullet_records(c)

    def test_base_bullet_wins_on_jd_not_source_label(self):
        c=candidate()
        row={'project_id':'p1','final_score':60,'requirement_matches':[
            {'requirement_id':'req_backend','match_label':'direct','importance':'core','coverage_points':30}]}
        with patch.object(allocation,'build_bullet_evidence_priorities',side_effect=priorities):
            result=allocation.build_deterministic_bullet_allocation(
                selected_pairs=[(c,row)], max_bullets_per_project=1)
        plan=result['projects'][0]
        self.assertIn('Built backend API',plan['allocated_blueprint_bullets'][0])
        self.assertEqual(result['source_policy_version'],POLICY_VERSION)
        selected=[x for x in plan['bullet_decision_receipts'] if x['selected']]
        self.assertEqual(selected[0]['sources'],['base'])
        self.assertIn('req_backend',selected[0]['supported_requirement_ids'])
        self.assertEqual(len([x for x in plan['bullet_decision_receipts'] if not x['selected']]),2)

    def test_no_library_relabel_on_allocation(self):
        c=candidate()
        row={'project_id':'p1','final_score':60,'requirement_matches':[]}
        with patch.object(allocation,'build_bullet_evidence_priorities',side_effect=priorities):
            plan=allocation.build_deterministic_bullet_allocation(
                selected_pairs=[(c,row)],max_bullets_per_project=1)
        prepared=allocation.apply_bullet_allocation_to_selected_pairs(selected_pairs=[(c,row)],allocation=plan)
        new=prepared[0][0]
        self.assertEqual(new['evidence_library_evidence'],c['evidence_library_evidence'])
        self.assertEqual(new['resume_evidence'],c['resume_evidence'])
        self.assertEqual(new['_phase9f_v27_allocated_sources'],[['base']])

    def test_v23_legacy_rejects_base_only_selected(self):
        c=candidate()
        p={'recommended_projects':[{'title':'Demo','source':'both',
            'selected_blueprint_bullets':['Built backend API with Python and tests.'],
            'draft_bullets':['Built backend API with Python and tests.']}],
           'candidate_project_ranking':[{'title':'Demo','source':'both','requirement_matches':[]}]}
        self.assertFalse(build_project_bullet_source_view(p,[c])['projects'])
        p['recommended_projects'][0]['bullet_source_policy_version']=POLICY_VERSION
        p['recommended_projects'][0]['selected_bullet_sources']=[['base']]
        view=build_project_bullet_source_view(p,[c])
        self.assertTrue(view['projects'],view['notice'])
        self.assertIn('V2.7',view['notice'])

    def test_v23_rejects_tampered_source_receipt(self):
        c=candidate()
        p={'recommended_projects':[{'title':'Demo','source':'both','bullet_source_policy_version':POLICY_VERSION,
            'selected_blueprint_bullets':['Built backend API with Python and tests.'],
            'selected_bullet_sources':[['library']],
            'draft_bullets':['Built backend API with Python and tests.']}],
           'candidate_project_ranking':[{'title':'Demo','source':'both','requirement_matches':[]}]}
        self.assertFalse(build_project_bullet_source_view(p,[c])['projects'])

    def test_allocations_do_not_mutate_input(self):
        c=candidate(); before=copy.deepcopy(c)
        row={'project_id':'p1','final_score':60,'requirement_matches':[]}
        with patch.object(allocation,'build_bullet_evidence_priorities',side_effect=priorities):
            allocation.build_deterministic_bullet_allocation(selected_pairs=[(c,row)],max_bullets_per_project=3)
        self.assertEqual(c,before)

if __name__=='__main__': unittest.main()

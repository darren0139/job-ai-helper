"""B1.3: Portfolio-only depth-aware candidate ordering and verified readback."""
from __future__ import annotations
from copy import deepcopy
import unittest

from tailoring.portfolio_quality_v312b13 import (
    B1_PROVENANCE, VERSION, prioritize_portfolio_reductions, audit_portfolio_depth_after_fit,
)


def slate(counts):
    return {'portfolio_quality_b1_active':B1_PROVENANCE,
            'recommended_projects':[{'project_id':f'p{i}','display_title':f'P{i}',
                                     'draft_bullets':[f'Work {j}' for j in range(n)]}
                                    for i,n in enumerate(counts)]}


def candidate(original, index, *, loss=250, tier=0, section='projects'):
    new=deepcopy(original)
    if index is None:
        change={'section':'skills','change_type':'remove_skill','protection_tier':tier}
    else:
        title=new['recommended_projects'][index]['display_title']
        new['recommended_projects'][index]['draft_bullets'].pop()
        change={'section':section,'change_type':'remove_bullet','project':title,
                'protection_tier':tier}
    return {'projects':new,'skills':{},'change':change,'quality_loss':loss,
            'candidate_order':index+1 if index is not None else 20}


class PortfolioDepthB13(unittest.TestCase):
    def test_one_to_two_is_prioritized_over_two_to_one(self):
        src=slate([5,2,4]);choices=[candidate(src,1),candidate(src,0),candidate(src,2)]
        changed=prioritize_portfolio_reductions(src,choices)
        ordered=[c['change']['project'] for c in changed]
        self.assertEqual(ordered,['P0','P2','P1'])
        self.assertEqual(changed[-1]['change']['v312b13_depth_order']['depth_penalty'],1300)
        self.assertEqual([row['candidate_order'] for row in changed],[1,2,3])

    def test_no_new_content_and_source_untouched(self):
        src=slate([4,3]);choices=[candidate(src,0),candidate(src,1)]
        original=deepcopy(choices)
        output=prioritize_portfolio_reductions(src,choices)
        self.assertEqual(choices,original)
        self.assertEqual([x['projects'] for x in output], [x['projects'] for x in sorted(choices,key=lambda c:0 if c['change']['project']=='P0' else 1)])
        self.assertTrue(all(x['change']['v312b13_depth_order']['no_native_score_claim'] for x in output))

    def test_balanced_other_modes_remain_identity(self):
        src=slate([4,2]);src.pop('portfolio_quality_b1_active')
        choices=[candidate(src,0)]
        self.assertIs(prioritize_portfolio_reductions(src,choices),choices)

    def test_invalid_geometry_does_not_reorder_anything(self):
        src=slate([3,2]);choices=[candidate(src,0),candidate(src,1)]
        choices[1]['projects']['recommended_projects'].pop()
        self.assertIs(prioritize_portfolio_reductions(src,choices),choices)
        choices=[candidate(src,0),candidate(src,1)]
        choices[0]['quality_loss']=-1
        self.assertIs(prioritize_portfolio_reductions(src,choices),choices)

    def test_discounts_removing_fourth_or_later_before_second(self):
        src=slate([2,6]);out=prioritize_portfolio_reductions(src,[candidate(src,0,loss=190),candidate(src,1,loss=600)])
        self.assertEqual(out[0]['change']['project'],'P1')

    def test_skill_candidate_is_preserved_and_still_a_valid_choice(self):
        src=slate([2,5]);out=prioritize_portfolio_reductions(src,[candidate(src,0),candidate(src,None,loss=300),candidate(src,1)])
        self.assertIn('skills', [x['change']['section'] for x in out])
        self.assertEqual(len(out),3)

    def test_readback_requires_exact_docx_and_one_page(self):
        src=slate([4,3]);raw={'fit_one_page':True,'page_count':1,
             'portfolio_quality_b1_final_audit':{'is_actual_docx_readback':True,
              'exact_saved_fitted_bullets_match_docx':True,
              'project_bullet_counts':{'P0':3,'P1':2},'docx_sha256':'abc'}}
        out=audit_portfolio_depth_after_fit(src,raw)
        self.assertEqual(out['status'],'OBSERVED_FINAL_DOCX_DEPTH')
        self.assertEqual(out['pre_fit_project_bullet_counts'],{'P0':4,'P1':3})
        self.assertFalse(out['native_score_checked'])
        self.assertEqual(out['one_bullet_project_count'],0)
        other=deepcopy(raw);other['page_count']=2
        self.assertEqual(audit_portfolio_depth_after_fit(src,other)['status'],'HOLD_NO_VERIFIED_FINAL_DOCX')
        other=deepcopy(raw);other['portfolio_quality_b1_final_audit'].pop('exact_saved_fitted_bullets_match_docx')
        self.assertEqual(audit_portfolio_depth_after_fit(src,other)['status'],'HOLD_NO_VERIFIED_FINAL_DOCX')

    def test_readback_refuses_project_title_mismatch(self):
        src=slate([4,3]);out=audit_portfolio_depth_after_fit(src,{
            'fit_one_page':True,'page_count':1,'portfolio_quality_b1_final_audit':{
              'is_actual_docx_readback':True,'exact_saved_fitted_bullets_match_docx':True,
              'project_bullet_counts':{'Unexpected title':1}}})
        self.assertEqual(out['status'],'HOLD_NO_VERIFIED_FINAL_DOCX')

    def test_keith_actual_input_shape(self):
        src=slate([29,4,6,5]);choices=[candidate(src,0,loss=450),candidate(src,1,loss=270),
                                      candidate(src,2,loss=265),candidate(src,3,loss=240)]
        out=prioritize_portfolio_reductions(src,choices)
        self.assertTrue(all(c['change']['v312b13_depth_order']['version']==VERSION for c in out))
        self.assertEqual(len(out),4)
        self.assertEqual([x['change']['project'] for x in out],['P3','P2','P1','P0'])

if __name__=='__main__':unittest.main()

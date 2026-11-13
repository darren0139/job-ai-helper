"""Focused pure regressions for explanatory UI; no SQLite or models."""
import unittest
from tailoring.phase9f_explainer_clarity_v2_2 import (
    project_selection_summary, fit_stage_summary, compact_comparison_rows,
    compact_snapshot_rows,
)

def project(id_, title, bullets, **kwargs):
    return {'project_id':id_,'title':title,'display_title':title,
            'draft_bullets':list(bullets),**kwargs}

def data():
    generated=[project('p1','Job AI',['a','b']), project('p2','Cyber',['x'])]
    ranked=[{'project_id':'p1','display_title':'Job AI','selection_rank':1,'selection_score':100,
             'requirement_matches':[{'requirement_text':'Python','match_label':'transferable'}]},
            {'project_id':'p2','display_title':'Cyber','selection_rank':2,'selection_score':0,'requirement_matches':[]}]
    selection={'candidate_project_ranking':ranked,'recommended_projects':generated,
               'low_confidence_selection':{'default_low_confidence_project_ids':['p2'],
                 'eligible_low_confidence_candidates':[{'project_id':'p2', 'fallback_reasons':['concrete project evidence']}],
                 'selection_source':'deterministic_default'}}
    fit={'fit_one_page':True,'page_count':1,'docx_path':'final.docx',
         'fitting_input_snapshot':{'prepared_initial_state':{'projects':{'recommended_projects':[
            {'display_title':'Job AI','draft_bullets':['a','b']},
            {'display_title':'Cyber','draft_bullets':['x','y','z']},
         ]}}},
         'remaining_active_reductions':[
            {'project':'Cyber','change_type':'compact_rewrite'},
            {'project':'Cyber','change_type':'remove_bullet','removed_bullet':'y'},
            {'project':'Cyber','change_type':'remove_bullet','removed_bullet':'z'},
         ],
         'tailored_projects_used':{'recommended_projects':generated}}
    return selection,fit

class ClarityTests(unittest.TestCase):
    def test_reason_comes_from_saved_ranking_and_fallback(self):
        s,_=data(); out=project_selection_summary(s)
        self.assertEqual(len(out['rows']),2)
        self.assertEqual(out['rows'][0]['Selection basis'],'Supported JD coverage')
        self.assertEqual(out['rows'][1]['Selection basis'],'Evidence-quality fallback (no proven JD coverage)')
        self.assertEqual(out['rows'][1]['Ranking score'],0)
        self.assertIn('1 explicit fallback',out['notice'])
    def test_fitting_reductions_not_hidden_by_caller_input(self):
        s,f=data();out=fit_stage_summary(s,f)
        self.assertEqual(len(out['rows']),2)
        self.assertEqual(out['rows'][1]['Fitter starting bullets'],3)
        self.assertEqual(out['rows'][1]['Bullets removed'],2)
        self.assertEqual(out['rows'][1]['Bullets after active reductions'],1)
        self.assertIn('2 bullet(s) removed',out['rows'][1]['Fitting changes'])
        self.assertNotIn('retained unchanged',str(out).lower())
    def test_not_fitted_cannot_claim_retention(self):
        s,f=data();f['fit_one_page']=False
        self.assertFalse(fit_stage_summary(s,f)['rows'])
    def test_missing_redution_history_cannot_claim_retention(self):
        s,f=data();del f['remaining_active_reductions']
        self.assertFalse(fit_stage_summary(s,f)['rows'])
    def test_unknown_final_reduction_fails_closed(self):
        s,f=data();f['remaining_active_reductions'].append({'project':'Cyber','change_type':'unknown'})
        self.assertFalse(fit_stage_summary(s,f)['rows'])
    def test_foreign_or_ambiguous_final_project_fails_closed(self):
        s,f=data();f['remaining_active_reductions'][0]['project']='Not selected'
        self.assertFalse(fit_stage_summary(s,f)['rows'])
        s,f=data();f['fitting_input_snapshot']['prepared_initial_state']['projects']['recommended_projects'][1]['display_title']='Job AI'
        self.assertFalse(fit_stage_summary(s,f)['rows'])
    def test_different_id_same_title_rejected(self):
        s,f=data();f['fitting_input_snapshot']['prepared_initial_state']['projects']['recommended_projects'][0]['project_id']='foreign'
        self.assertFalse(fit_stage_summary(s,f)['rows'])
    def test_duplicate_rank_rejected(self):
        s,_=data();s['candidate_project_ranking'].append(s['candidate_project_ranking'][0])
        self.assertFalse(project_selection_summary(s)['rows'])
    def test_comparison_has_clear_base_and_tailored_columns(self):
        rows=compact_comparison_rows([{'Requirement':'Python', 'Importance':'core', 'Match transition':'weak→direct',
          'Classification':'IMPROVED', 'Contribution Δ':2.4}], 'Selected Base')
        self.assertEqual(rows[0]['Selected Base match'],'weak')
        self.assertEqual(rows[0]['Tailored match'],'direct')
        self.assertEqual(rows[0]['Points Δ'],2.4)
    def test_snapshot_compact(self):
        rows=compact_snapshot_rows({'requirements':[{'requirement_text':'Python','importance':'core','final_match':'direct','evidence_provenance':[{'text':'Python'}]}]})
        self.assertEqual(rows[0]['Match'],'direct')
        self.assertEqual(rows[0]['Evidence'],'Present')
if __name__=='__main__': unittest.main()

"""B1.4 independent native/actual-DOCX gate tests, no database or model calls."""
from __future__ import annotations
import hashlib
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from tailoring.portfolio_quality_v312b14 import (
    B1_TAG, _metadata, propose_swaps, native_floors, compare_and_select,
)


def source_payload():
    def p(name,n,scores):
        bullets=[f'{name} concrete accomplishment {i}.' for i in range(n)]
        return {'project_id':name,'display_title':name,'draft_bullets':bullets,
                'bullet_evidence_priorities':[
                    {'bullet_index':i,'bullet_text':b,'supported_requirement_ids':list(scores[i]),
                     'protected_requirement_ids':[], 'unique_required_core_count':0,
                     'protect_during_fitting':i==0 and name=='A',
                     'evidence_value':10.0+i} for i,b in enumerate(bullets)]}
    rows=[p('A',5,[('core1',),('r2',),('r2',),('r2',),('r2',)]),
          p('B',3,[('bcore',),('bn',),('bn2',)]),
          p('C',3,[(),(),()])]
    return {'portfolio_quality_b1_active':B1_TAG,'recommended_projects':rows}


def fit_input(source):
    current=deepcopy(source)
    current['recommended_projects'][1]['draft_bullets']=current['recommended_projects'][1]['draft_bullets'][:1]
    current['recommended_projects'][1]['bullet_evidence_priorities']=current['recommended_projects'][1]['bullet_evidence_priorities'][:1]
    current['recommended_projects'][2]['draft_bullets']=current['recommended_projects'][2]['draft_bullets'][:1]
    current['recommended_projects'][2]['bullet_evidence_priorities']=current['recommended_projects'][2]['bullet_evidence_priorities'][:1]
    return {'tailored_projects_used':current,'fit_one_page':True,'page_count':1}


def verification(score=32, core=4, claim=0):
    rows=[{'requirement_id':'c','importance':'core','evidence_strength':core,'match_label':'direct'},
          {'requirement_id':'p','importance':'preferred','evidence_strength':2,'match_label':'weak'}]
    return {'comparison_valid':True,'job_match_ab':{'comparable':True},
            'after_stable_analysis':{'scoring_version':'native-v1','deterministic_alignment_score':score,
                'canonical_requirements':rows},
            'claim_lineage':{'claim_review_required_count':claim}}


class B14(unittest.TestCase):
    def test_source_grounded_depth_swap(self):
        src=source_payload();f=fit_input(src);res=propose_swaps(src,f)
        self.assertTrue(res)
        self.assertTrue(all(r['source_grounded'] for r in res))
        self.assertTrue(all(len(r['projects']['recommended_projects'][0]['draft_bullets'])==4 for r in res))
        self.assertTrue(all(len(r['projects']['recommended_projects'][1]['draft_bullets'])==2 for r in res))
        self.assertEqual(_metadata(res[0]['projects']['recommended_projects'][1]) is not None,True)
        self.assertEqual(len(f['tailored_projects_used']['recommended_projects'][0]['draft_bullets']),5)

    def test_no_swap_on_balanced(self):
        p=source_payload();p.pop('portfolio_quality_b1_active')
        self.assertEqual(propose_swaps(p,fit_input(p)),[])

    def test_no_swap_when_preserved_evidence_missing(self):
        p=source_payload();
        last=p['recommended_projects'][0]['bullet_evidence_priorities'][-1]
        last['supported_requirement_ids']=['unique']
        # Other removable A bullets remain (all share 'r2'); protect all these.
        for row in p['recommended_projects'][0]['bullet_evidence_priorities'][1:-1]:
            row['protect_during_fitting']=True
        self.assertEqual(propose_swaps(p,fit_input(p)),[])

    def test_metadata_mismatch_holds(self):
        p=source_payload()
        p['recommended_projects'][1]['bullet_evidence_priorities'][1]['bullet_text']='Wrong source'
        self.assertEqual(propose_swaps(p,fit_input(p)),[])

    def test_no_source_writes(self):
        p=source_payload();f=fit_input(p);base=deepcopy(p);old=deepcopy(f)
        propose_swaps(p,f)
        self.assertEqual(p,base);self.assertEqual(f,old)

    def test_darren_deep_three_projects_no_one_bullet(self):
        p=source_payload();f=fit_input(p)
        for i,n in ((0,5),(1,3),(2,3)):
            r=f['tailored_projects_used']['recommended_projects'][i]
            orig=p['recommended_projects'][i]
            r['draft_bullets']=orig['draft_bullets'][:n]
            r['bullet_evidence_priorities']=orig['bullet_evidence_priorities'][:n]
        self.assertEqual(propose_swaps(p,f),[])

    def test_native_floor_enforces_score_and_core(self):
        left=verification()
        self.assertEqual(native_floors(left,verification(score=31))[1],'NATIVE_SCORE_REGRESSION')
        self.assertEqual(native_floors(left,verification(score=33,core=3))[1],'REQUIRED_CORE_REGRESSION')
        self.assertEqual(native_floors(left,verification(score=33,claim=1))[1],'CLAIM_REVIEW_RISK_INCREASED')
        self.assertTrue(native_floors(left,verification(score=33))[0])

    def test_unknown_core_label_holds(self):
        left=verification();right=verification(score=33)
        right['after_stable_analysis']['canonical_requirements'][0]['match_label']='unrecognised'
        self.assertEqual(native_floors(left,right)[1],'UNRECOGNISED_REQUIREMENT_LABEL')

    def test_score_unavailable_fails_closed(self):
        left=verification();right=verification()
        right['comparison_valid']=False
        self.assertFalse(native_floors(left,right)[0])
        right=verification();right['after_stable_analysis']['scoring_version']='other-version'
        self.assertEqual(native_floors(left,right)[1],'NATIVE_IDENTITIES_CHANGED')

    def test_actual_docx_native_safe_candidate_selected(self):
        p=source_payload();f=fit_input(p)
        with tempfile.TemporaryDirectory() as d:
            doc=Path(d)/'fit.docx';doc.write_bytes(b'fixture-docx')
            def evidence_receipt(result):
                result=deepcopy(result)
                result['docx_path']=str(doc)
                result['portfolio_quality_b1_final_audit']={
                    'is_actual_docx_readback':True,'exact_saved_fitted_bullets_match_docx':True,
                    'docx_sha256':hashlib.sha256(doc.read_bytes()).hexdigest()}
                return result
            f=evidence_receipt(f)
            def renderer(alternative):
                return evidence_receipt({**f,'tailored_projects_used':deepcopy(alternative)})
            def verifier(result):
                return verification(score=32)
            selected,audit=compare_and_select(source_projects=p,incumbent_fit=f,render=renderer,verify=verifier)
            self.assertEqual(audit['status'],'SELECTED_NATIVE_SAFE_DEPTH_IMPROVEMENT')
            self.assertEqual(len(selected['tailored_projects_used']['recommended_projects'][1]['draft_bullets']),2)
            self.assertTrue(audit['native_score_checked'])
            self.assertEqual(audit['selected_native_score'],32)

    def test_incorrect_docx_or_native_regression_holds(self):
        p=source_payload();f=fit_input(p)
        with tempfile.TemporaryDirectory() as d:
            doc=Path(d)/'fit.docx';doc.write_bytes(b'original')
            def evidence_receipt(result):
                return {**result,'docx_path':str(doc),'portfolio_quality_b1_final_audit':{
                    'is_actual_docx_readback':True,'exact_saved_fitted_bullets_match_docx':True,
                    'docx_sha256':hashlib.sha256(doc.read_bytes()).hexdigest()}}
            f=evidence_receipt(f)
            def renderer(alt):return evidence_receipt({**f,'tailored_projects_used':deepcopy(alt)})
            def verifier(result):
                return verification(score=31 if result['tailored_projects_used'] != f['tailored_projects_used'] else 32)
            selected,audit=compare_and_select(source_projects=p,incumbent_fit=f,render=renderer,verify=verifier)
            self.assertIs(selected,f)
            self.assertEqual(audit['status'],'HOLD_INCUMBENT')
            invalid=deepcopy(f);invalid['portfolio_quality_b1_final_audit']['docx_sha256']='0'*64
            selected,audit=compare_and_select(source_projects=p,incumbent_fit=invalid,render=renderer,verify=verifier)
            self.assertEqual(audit['reason'],'INCUMBENT_DOCX_NOT_AUTHENTICATED')

    def test_native_exception_keeps_incumbent(self):
        p=source_payload();f=fit_input(p)
        kept,a=compare_and_select(source_projects=p,incumbent_fit=f,render=lambda _:None,
                                  verify=lambda _:None)
        self.assertIs(kept,f)
        self.assertEqual(a['reason'],'INCUMBENT_DOCX_NOT_AUTHENTICATED')

if __name__=='__main__':unittest.main()

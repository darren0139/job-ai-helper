"""B1 fit-time coverage-preserving redundancy repair; negative controls."""
from __future__ import annotations
from copy import deepcopy
import tempfile
import unittest
from pathlib import Path
from tailoring.portfolio_quality_v312b1 import (
    VERSION, improve_portfolio_fit_input, audit_fitted_portfolio_docx,
)

INTRO='Built a full-stack IT service request tracker with React, TypeScript, FastAPI, and PostgreSQL, spanning application development, database design, and RESTful APIs.'
CI_A='Automated backend tests, frontend tests, production builds, Docker build validation, and container vulnerability scanning with GitHub Actions.'
CI_B='Automated frontend builds, backend tests, GHCR image publishing, and Trivy security scans with GitHub Actions; added Prometheus metrics, alerts, and Grafana dashboards.'
QA='Created automated backend and frontend tests covering authentication, requests, RBAC, comments, authentication pages, request forms, and role-based navigation.'
LUA_A='Implemented gameplay mechanics through Lua scripting within the custom C++ engine.'
LUA_B='Implemented gameplay mechanics using Lua scripting within a custom C++ game engine for game levels.'

def p(title,bullets,ids=None,protection=None):
    ids=ids or [set() for _ in bullets]
    protection=protection or [set() for _ in bullets]
    return {'title':title, 'display_title':title,
        'draft_bullets':bullets[:], 'compact_bullets':[],
        'bullet_evidence_priorities':[
            {'bullet_index':i,'bullet_text':b,'supported_requirement_ids':sorted(ids[i]),
             'protected_requirement_ids':sorted(protection[i]), 'evidence_priority':1}
            for i,b in enumerate(bullets)]}


class B1(unittest.TestCase):
    def test_real_requestflow_excludes_one_repeated_ci_not_the_intro_or_distinct_qa(self):
        rows=[p('RequestFlow',[CI_A,CI_B,QA,INTRO],[{'full','qa'},{'full','qa'},{'full','qa'},{'full'}])]
        src={'recommended_projects':rows, 'other_user_data':{'keep':True}}
        result=improve_portfolio_fit_input(src,mode='portfolio_quality',stage='caller')
        selected=result['recommended_projects'][0]['draft_bullets']
        self.assertEqual(len(selected),3)
        self.assertIn(INTRO,selected)
        self.assertIn(QA,selected)
        self.assertIn(CI_B,selected)
        self.assertNotIn(CI_A,selected)
        self.assertEqual(src['recommended_projects'][0]['draft_bullets'],[CI_A,CI_B,QA,INTRO])
        self.assertEqual([x['bullet_index'] for x in result['recommended_projects'][0]['bullet_evidence_priorities']],list(range(3)))
        self.assertEqual(result['portfolio_quality_b1_active'],VERSION)

    def test_duplicate_lua_work_conservatively_removed(self):
        src={'recommended_projects':[p('High Verdant',[LUA_A,LUA_B,INTRO])]}
        v=improve_portfolio_fit_input(src,mode='portfolio_quality',stage='prepared')
        self.assertEqual(len(v['recommended_projects'][0]['draft_bullets']),2)

    def test_protected_and_unique_jd_link_not_deleted(self):
        x=p('RequestFlow',[CI_A,CI_B],ids=[{'req-core'}, {'req-extra'}])
        r=improve_portfolio_fit_input({'recommended_projects':[x]},mode='portfolio_quality',stage='caller')
        self.assertEqual(len(r['recommended_projects'][0]['draft_bullets']),2)
        x=p('RequestFlow',[CI_A,CI_B],ids=[{'req-core'},{'req-core'}],protection=[{'req-core'},set()])
        r=improve_portfolio_fit_input({'recommended_projects':[x]},mode='portfolio_quality',stage='caller')
        self.assertIn(CI_A,r['recommended_projects'][0]['draft_bullets'])

    def test_other_policies_unmodified_including_identity(self):
        pld={'recommended_projects':[p('RequestFlow',[CI_A,CI_B])]}
        for mode in ('balanced','jd_focused','legacy','manual','preserve_generated'):
            self.assertIs(improve_portfolio_fit_input(pld,mode=mode,stage='caller'),pld)
        self.assertEqual(len(pld['recommended_projects'][0]['draft_bullets']),2)

    def test_replay_prepared_is_idempotent_and_auditable(self):
        src={'recommended_projects':[p('RequestFlow',[CI_A,CI_B,INTRO],[{'x'},{'x'},{'x'}])]}
        a=improve_portfolio_fit_input(src,mode='portfolio_quality',stage='caller')
        b=improve_portfolio_fit_input(a,mode='portfolio_quality',stage='prepared')
        c=improve_portfolio_fit_input(b,mode='portfolio_quality',stage='prepared')
        self.assertEqual(b,c)
        self.assertEqual(len(b['portfolio_quality_b1_fit_audit']['stages']),2)
        self.assertEqual(len(b['recommended_projects'][0]['draft_bullets']),2)
        self.assertFalse(b['portfolio_quality_b1_fit_audit']['no_content_invented'] is False)

    def test_inconsistent_metadata_holds_not_deletes(self):
        x=p('x',[CI_A,CI_B]);x['bullet_evidence_priorities'][0]['bullet_text']='WRONG'
        r=improve_portfolio_fit_input({'recommended_projects':[x]},mode='portfolio_quality',stage='caller')
        self.assertEqual(len(r['recommended_projects'][0]['draft_bullets']),2)
        self.assertEqual(r['portfolio_quality_b1_fit_audit']['stages'][0]['actions'][0]['status'],'HOLD_UNALIGNED_METADATA')

    def test_no_cross_project_dedupe_and_no_unsupported_new_bullets(self):
        src={'recommended_projects':[p('one',[CI_A,INTRO]),p('two',[CI_A,QA])]}
        r=improve_portfolio_fit_input(src,mode='portfolio_quality',stage='caller')
        self.assertEqual([len(x['draft_bullets']) for x in r['recommended_projects']],[2,2])

    def test_final_readback_is_not_native_claim(self):
        from docx import Document
        with tempfile.TemporaryDirectory() as d:
            fn=Path(d)/'f.docx';doc=Document();doc.add_paragraph('PROJECTS');doc.styles.add_style('Resume Entry', 1);doc.add_paragraph('RequestFlow',style='Resume Entry')
            for x in [CI_A,CI_B,QA]: doc.add_paragraph(x,style='List Bullet')
            doc.add_paragraph('SKILLS');doc.save(fn)
            row=audit_fitted_portfolio_docx({'fit_one_page':True,'page_count':1,'docx_path':str(fn)})
            self.assertTrue(row['is_actual_docx_readback'])
            self.assertEqual(row['same_work_groups_remaining_by_project'].get('RequestFlow',{}).get('ci_frontend_backend_build_tests'),2)
            self.assertFalse(row['native_score_checked'])
            self.assertFalse(row['editorial_approval'])

    def test_no_premature_fit_claim(self):
        r=audit_fitted_portfolio_docx({'fit_one_page':False,'page_count':2})
        self.assertFalse(r['is_actual_docx_readback'])

if __name__ == '__main__': unittest.main()

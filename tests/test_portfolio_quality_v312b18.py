"""B1.8 strict readback tests using a generated Normal-style DOCX fixture."""
from __future__ import annotations
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from docx import Document
from tailoring.portfolio_quality_v312b1 import audit_fitted_portfolio_docx

TITLES=['Project Alpha — App','Project Beta — Database','Project Gamma — Game']
BULLETS=[['Built frontend and backend integration.','Developed automated test suite.'],
         ['Implemented row-level database security.','Configured API access controls.'],
         ['Built gameplay and audio integration.','Implemented asset management tools.']]

def fixture(*,rename=None,extra=False,missing=False,duplicate=False,misassigned=False,not_bold=False,early=False):
    doc=Document();doc.add_paragraph('PROJECTS')
    if early:doc.add_paragraph('• Unassigned fabricated bullet')
    for index,title in enumerate(TITLES):
        if misassigned and index==1:
            continue
        if rename and index==1:title=rename
        h=doc.add_paragraph();h.style='Normal'
        r=h.add_run(title);r.bold=not not_bold
        h.add_run('\tJan 2026 - Nov 2026')
        doc.add_paragraph('Python, SQLite | Team of 2')
        for bi,bullet in enumerate(BULLETS[index]):
            if missing and index==1 and bi==0:continue
            doc.add_paragraph('• '+bullet)
        if extra and index==0:doc.add_paragraph('• Fabricated new accomplishment')
        if duplicate and index==1:
            h=doc.add_paragraph();h.add_run(TITLES[index]).bold=True
            h.add_run('\tJan 2026 - Nov 2026')
    doc.add_paragraph('SKILLS')
    return doc

def assess(doc, *,alter=None):
    with tempfile.TemporaryDirectory() as td:
        path=Path(td)/'f.docx';doc.save(path)
        projects=[{'display_title':t,'draft_bullets':b} for t,b in zip(TITLES,BULLETS)]
        if alter:alter(projects)
        return audit_fitted_portfolio_docx({
            'fit_one_page':True,'page_count':1,'docx_path':str(path),
            'tailored_projects_used':{'recommended_projects':projects}})

class B18NormalStyleReadback(unittest.TestCase):
    def test_exact_normal_style_passes_readback_only(self):
        receipt=assess(fixture())
        self.assertEqual(receipt['status'],'DOCX_READBACK_EDITORIAL_REVIEW')
        self.assertTrue(receipt['exact_saved_fitted_bullets_match_docx'])
        self.assertEqual(receipt['project_bullet_count'],6)
        self.assertEqual(list(receipt['project_bullet_counts'].values()),[2,2,2])
        self.assertFalse(receipt['native_score_checked'])
        self.assertFalse(receipt['editorial_approval'])
        self.assertEqual(len(receipt['docx_sha256']),64)
    def test_unassigned_bullet_still_holds(self):
        self.assertEqual(assess(fixture(early=True))['reason'],'unassigned_project_bullet')
    def test_unknown_tabbed_heading_holds(self):
        self.assertEqual(assess(fixture(rename='Unknown Project'))['reason'],'unexpected_project_heading')
    def test_duplicate_heading_holds(self):
        self.assertEqual(assess(fixture(duplicate=True))['reason'],'duplicate_project_heading')
    def test_missing_bullet_fails_exact_readback(self):
        r=assess(fixture(missing=True))
        self.assertEqual(r['status'],'HOLD_DOCX_READBACK_MISMATCH')
        self.assertFalse(r['exact_saved_fitted_bullets_match_docx'])
    def test_extra_bullet_fails_exact_readback(self):
        self.assertEqual(assess(fixture(extra=True))['status'],'HOLD_DOCX_READBACK_MISMATCH')
    def test_misassigned_project_fails_exact_readback(self):
        self.assertEqual(assess(fixture(misassigned=True))['status'],'HOLD_DOCX_READBACK_MISMATCH')
    def test_unbolded_normal_heading_does_not_get_inferred(self):
        self.assertEqual(assess(fixture(not_bold=True))['reason'],'unassigned_project_bullet')
    def test_wrong_expected_bullet_fails_exact_readback(self):
        def change(rows):rows[1]['draft_bullets'][0]='UNSUPPORTED'
        self.assertEqual(assess(fixture(),alter=change)['status'],'HOLD_DOCX_READBACK_MISMATCH')
    def test_duplicate_saved_heading_holds(self):
        def change(rows):rows[1]['display_title']=rows[0]['display_title']
        self.assertEqual(assess(fixture(),alter=change)['reason'],'invalid_saved_project_heading')
    def test_not_one_page_is_no_readback(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'x.docx';fixture().save(p)
            r=audit_fitted_portfolio_docx({'fit_one_page':False,'page_count':2,'docx_path':str(p)})
            self.assertEqual(r['reason'],'not_verified_one_page')
    def test_docx_missing_does_not_pass(self):
        r=audit_fitted_portfolio_docx({'fit_one_page':True,'page_count':1,
            'docx_path':'Z:/missing/b18_absent_fixture.docx'})
        self.assertEqual(r['reason'],'fitted_docx_missing')

if __name__=='__main__':unittest.main()

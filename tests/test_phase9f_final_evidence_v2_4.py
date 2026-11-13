"""Focused V2.4 final-DOCX audit tests; all temporary files isolated."""
import copy
import tempfile
import unittest
from pathlib import Path
from docx import Document
from tailoring.phase9f_final_evidence_comparison_v2_4 import build_final_evidence_audit


def fixture(tmp, *, bullet='Canonical approved bullet'):
    root=Path(tmp)
    folder=root/'outputs'/'tailored_resumes';folder.mkdir(parents=True,exist_ok=True)
    path=folder/'app_156_final.docx'
    doc=Document();doc.add_paragraph('PROJECTS');doc.add_paragraph('Example Project\tNov 2026')
    doc.add_paragraph('• '+bullet);doc.add_paragraph('SKILLS');doc.save(path)
    projects={'recommended_projects':[{
        'project_id':'p1','title':'Example Project','display_title':'Example Project','source':'both',
        'selected_blueprint_bullets':['Canonical approved bullet'],
        'draft_bullets':['Canonical approved bullet'],
        'bullet_evidence_priorities':[{'bullet_index':0,'bullet_text':'Canonical approved bullet',
                                      'supported_requirement_ids':['req123'],'evidence_value':9,'protect_during_fitting':True}],
    }], 'candidate_project_ranking':[{'project_id':'p1','title':'Example Project','source':'both','selection_rank':1,'requirement_matches':[]}]}
    candidates=[{'title':'Example Project','currently_in_resume':True,'in_evidence_library':True,
                 'resume_evidence':{'bullets':['Original Base bullet']},
                 'evidence_library_evidence':{'bullets':['Canonical approved bullet']}}]
    fit={'generation_id':'gen156', 'fit_one_page':True,'page_count':1,'fit_status':'verified_one_page',
         'docx_path':str(path.relative_to(root)),
         'fitting_input_snapshot':{'prepared_initial_state':{'projects':{'recommended_projects':[
             {'title':'Example Project','display_title':'Example Project','draft_bullets':['Canonical approved bullet']}
         ]}}}, 'remaining_active_reductions':[]}
    return root,projects,candidates,fit,path

class FinalEvidenceV24Tests(unittest.TestCase):
    def test_verified_docx_has_exact_canonical_library_and_draft_lineage(self):
        with tempfile.TemporaryDirectory() as t:
            root,p,c,f,_=fixture(t)
            v=build_final_evidence_audit(p,f,c,repo_root=root,application_id=156,expected_generation_id='gen156')
            self.assertTrue(v['verified'],v['notice'])
            row=v['projects'][0]['final'][0]
            self.assertTrue(row['exact_library']);self.assertFalse(row['exact_base'])
            self.assertTrue(row['exact_generated_draft']);self.assertIn('req123',row['jd_requirement_ids'])
            self.assertIn('NOT proof',v['notice'])
    def test_unverified_fit_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root,p,c,f,_=fixture(t);f['fit_one_page']=False
            self.assertFalse(build_final_evidence_audit(p,f,c,repo_root=root,application_id=156)['verified'])
    def test_foreign_generation_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root,p,c,f,_=fixture(t)
            self.assertFalse(build_final_evidence_audit(p,f,c,repo_root=root,application_id=156,expected_generation_id='foreign')['verified'])
    def test_foreign_app_or_external_path_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root,p,c,f,path=fixture(t)
            self.assertFalse(build_final_evidence_audit(p,f,c,repo_root=root,application_id=12)['verified'])
            f['docx_path']=str(path)
            self.assertTrue(build_final_evidence_audit(p,f,c,repo_root=root,application_id=156)['verified'])
            f['docx_path']=str(root/'untrusted.docx')
            self.assertFalse(build_final_evidence_audit(p,f,c,repo_root=root,application_id=156)['verified'])
    def test_docx_text_mismatch_detected(self):
        with tempfile.TemporaryDirectory() as t:
            root,p,c,f,path=fixture(t)
            d=Document(path);d.paragraphs[2].text='• Different final bullet';d.save(path)
            v=build_final_evidence_audit(p,f,c,repo_root=root,application_id=156)
            self.assertTrue(v['verified'],v['notice'])
            self.assertFalse(v['projects'][0]['final'][0]['exact_library'])
            self.assertIn('Changed wording',v['projects'][0]['final'][0]['lineage'])
    def test_saved_reductions_must_agree_with_docx_counts(self):
        with tempfile.TemporaryDirectory() as t:
            root,p,c,f,_=fixture(t)
            f['remaining_active_reductions']=[{'project':'Example Project','change_type':'remove_bullet'}]
            self.assertFalse(build_final_evidence_audit(p,f,c,repo_root=root,application_id=156)['verified'])
    def test_unknown_fitting_action_withheld(self):
        with tempfile.TemporaryDirectory() as t:
            root,p,c,f,_=fixture(t)
            f['remaining_active_reductions']=[{'project':'Example Project','change_type':'unknown'}]
            self.assertFalse(build_final_evidence_audit(p,f,c,repo_root=root,application_id=156)['verified'])
    def test_no_source_identity_withheld(self):
        with tempfile.TemporaryDirectory() as t:
            root,p,c,f,_=fixture(t)
            self.assertFalse(build_final_evidence_audit(p,f,[],repo_root=root,application_id=156)['verified'])
    def test_duplicate_titles_withheld(self):
        with tempfile.TemporaryDirectory() as t:
            root,p,c,f,_=fixture(t)
            p['recommended_projects'].append(copy.deepcopy(p['recommended_projects'][0]))
            self.assertFalse(build_final_evidence_audit(p,f,c,repo_root=root,application_id=156)['verified'])
    def test_missing_or_duplicate_project_headers_withheld(self):
        with tempfile.TemporaryDirectory() as t:
            root,p,c,f,path=fixture(t)
            d=Document(path);d.add_paragraph('PROJECTS');d.add_paragraph('Example Project\tNov 2026');d.add_paragraph('• Canonical approved bullet');d.add_paragraph('SKILLS');d.save(path)
            self.assertFalse(build_final_evidence_audit(p,f,c,repo_root=root,application_id=156)['verified'])

if __name__=='__main__': unittest.main()

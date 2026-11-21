"""V3.1 focused safe variable-count optimizer + actual DOCX edit tests."""
from __future__ import annotations
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from tailoring.phase9f_auto_optimize_v31 import build_flexible_optimization, VERSION
from tailoring.phase9f_joint_resume_optimizer_v2_6 import write_optimized_docx, _bullet_locations, materialize_verified_candidate


def fixture():
    def b(*text):
        return [{"text": x, "number": i} for i,x in enumerate(text,1)]
    audit={"verified": True, "generation_id": "g31", "projects":[
        {"project":"Alpha", "base":b("Alpha baseline carries API evidence long enough"),
         "library":b("Python"),"final":b("Alpha baseline carries API evidence long enough")},
        {"project":"Beta", "base":b(), "library":b("CI tests work reliably for every build", "CI"),
         "final":b("CI tests work reliably for every build")},
    ]}
    ranks={"candidate_project_ranking":[
        {"title":"Alpha","requirement_matches":[
            {"requirement_id":"r1","importance":"core","match_label":"direct","coverage_points":5.0},
            {"requirement_id":"r2","importance":"preferred","match_label":"direct","coverage_points":7.0}]},
        {"title":"Beta","requirement_matches":[
            {"requirement_id":"r3","importance":"core","match_label":"direct","coverage_points":8.0}]},
    ]}
    return audit,ranks


def evaluator(*, bullets, ranking_row):
    mapping={"Alpha baseline carries API evidence long enough":["r1"],
             "Python":["r2"], "CI":["r3"], "CI tests work reliably for every build":["r3"]}
    known={r["requirement_id"] for r in ranking_row["requirement_matches"]}
    return [{"bullet_index":i,"bullet_text":v,
             "supported_requirement_ids":[rid for rid in mapping.get(v,[]) if rid in known]}
            for i,v in enumerate(bullets)]


def docx(path):
    from docx import Document
    d=Document()
    d.add_paragraph("EXPERIENCE")
    d.add_paragraph("Experience must stay unmodified")
    d.add_paragraph("PROJECTS")
    for name,bullet in (("Alpha","Alpha baseline carries API evidence long enough"),
                        ("Beta","CI tests work reliably for every build")):
        d.add_paragraph(name+" | tools")
        d.add_paragraph("• "+bullet)
    d.add_paragraph("SKILLS")
    d.add_paragraph("Python, SQL")
    d.save(path)


class FlexibleV31(TestCase):
    def test_more_bullets_same_project_preserves_hard_and_adds_preferred(self):
        a,p=fixture()
        untouched=deepcopy((a,p))
        got=build_flexible_optimization(a,p,evaluator=evaluator)
        self.assertEqual(got['version'],VERSION)
        self.assertEqual(got['status'],'candidate',got)
        self.assertEqual(got['baseline_bullet_count'],2)
        self.assertEqual(got['proposed_bullet_count'],3)
        self.assertEqual(got['gained_jd_ids'],['r2'])
        self.assertEqual(got['lost_jd_ids'],[])
        self.assertTrue(got['requires_base_review'] is False)
        self.assertEqual(got['projects'][0]['after_count'],2)
        self.assertEqual(got['selection_receipt']['actual_docx_comparison_required'],True)
        self.assertFalse(got['selection_receipt']['verified_fitting_explanation'])
        self.assertEqual((a,p),untouched)

    def test_actual_docx_variable_count_and_integrity(self):
        a,p=fixture()
        got=build_flexible_optimization(a,p,evaluator=evaluator)
        with TemporaryDirectory() as tmp:
            src=Path(tmp)/'source.docx';dst=Path(tmp)/'candidate.docx'
            docx(src)
            old=src.read_bytes()
            write_optimized_docx(source_path=src,audit_sha=sha256(old).hexdigest(),
                                 proposal=got,destination=dst)
            from docx import Document
            lines=[p.text for p in Document(dst).paragraphs]
            self.assertEqual(lines.count('• Python'),1)
            self.assertEqual(lines.count('• Alpha baseline carries API evidence long enough'),1)
            self.assertEqual(lines.count('• CI'),1)
            self.assertEqual(lines[-2:],["SKILLS","Python, SQL"])
            self.assertEqual(src.read_bytes(),old)
            located=_bullet_locations(Document(dst),[{**r,"before":r["after"]} for r in got["projects"]])
            self.assertEqual([len(x) for x in located],[2,1])

    def test_variable_count_reduction_is_supported_with_explicit_v31_receipt(self):
        a,p=fixture()
        got=build_flexible_optimization(a,p,evaluator=evaluator)
        with TemporaryDirectory() as tmp:
            source=Path(tmp)/'source.docx';out=Path(tmp)/'less.docx'
            docx(source)
            changed=deepcopy(got)
            changed['projects'][0]['after']=['Python']
            changed['projects'][0]['after_count']=1
            write_optimized_docx(source_path=source,audit_sha=sha256(source.read_bytes()).hexdigest(),
                                 proposal=changed,destination=out)
            from docx import Document
            self.assertEqual(sum(p.text.startswith('• ') for p in Document(out).paragraphs),2)

    def test_v31_manifest_and_unapproved_independent_one_page_candidate(self):
        import json
        from pypdf import PdfWriter
        a,p=fixture()
        proposal=build_flexible_optimization(a,p,evaluator=evaluator)
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            folder=root/'outputs'/'tailored_resumes'
            folder.mkdir(parents=True)
            src=folder/'app_156_original.docx'
            docx(src)
            original=src.read_bytes()
            def convert(candidate, work):
                pdf=work/(candidate.stem+'.pdf')
                writer=PdfWriter();writer.add_blank_page(width=612,height=792)
                with pdf.open('wb') as f:writer.write(f)
                return pdf
            result=materialize_verified_candidate(source_docx=src,
                audit_sha=sha256(original).hexdigest(),proposal=proposal,
                repo_root=root,application_id=156,generation_id='g31test01',converter=convert)
            receipt=json.loads(Path(result['receipt_path']).read_text())
            self.assertEqual(receipt['proposal_scope'],'fixed-project-set-variable-bullet-count-selection')
            self.assertEqual(receipt['version'],VERSION)
            self.assertFalse(receipt['candidate_is_approved'])
            self.assertEqual(receipt['selection_receipt']['actual_docx_comparison_required'],True)
            self.assertEqual(src.read_bytes(),original)
            self.assertEqual(result['pages'],1)

    def test_rejects_unverified_ambiguous_or_missing_evaluator_support(self):
        a,p=fixture()
        a['verified']=False
        self.assertEqual(build_flexible_optimization(a,p,evaluator=evaluator)['status'],'withheld')
        a['verified']=True;a['projects'][1]['project']='Alpha'
        self.assertEqual(build_flexible_optimization(a,p,evaluator=evaluator)['status'],'withheld')
        a,p=fixture()
        def bad(*,bullets,ranking_row):
            rows=evaluator(bullets=bullets,ranking_row=ranking_row)
            rows[0]['supported_requirement_ids']=['foreign']
            return rows
        self.assertEqual(build_flexible_optimization(a,p,evaluator=bad)['status'],'withheld')

    def test_coverage_only_from_baseline_returns_no_candidate(self):
        a,p=fixture()
        a['projects'][0]['library']=[]
        self.assertEqual(build_flexible_optimization(a,p,evaluator=evaluator)['status'],'no_proxy_gain')

    def test_v31_writer_refuses_unmarked_count_change(self):
        a,p=fixture()
        got=build_flexible_optimization(a,p,evaluator=evaluator)
        got['variable_bullet_counts']=False
        with TemporaryDirectory() as tmp:
            src=Path(tmp)/'in.docx';dst=Path(tmp)/'out.docx';docx(src)
            with self.assertRaisesRegex(ValueError,'bullet count changed'):
                write_optimized_docx(source_path=src,audit_sha=sha256(src.read_bytes()).hexdigest(),proposal=got,destination=dst)
            self.assertFalse(dst.exists())

    def test_v31_writer_refuses_forged_version(self):
        a,p=fixture()
        got=build_flexible_optimization(a,p,evaluator=evaluator)
        got['version']='forged-version'
        with TemporaryDirectory() as tmp:
            src=Path(tmp)/'in.docx';dst=Path(tmp)/'out.docx';docx(src)
            with self.assertRaisesRegex(ValueError,'identified V3.1'):
                write_optimized_docx(source_path=src,audit_sha=sha256(src.read_bytes()).hexdigest(),proposal=got,destination=dst)

if __name__ == '__main__':
    import unittest
    unittest.main()

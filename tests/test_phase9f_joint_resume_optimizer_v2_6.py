"""Focused Phase 9F V2.6 active candidate writer and safety regression tests."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
import json
import shutil

from tailoring.phase9f_joint_resume_optimizer_v2_6 import (
    build_joint_optimization, write_optimized_docx,
    materialize_verified_candidate, _bullet_locations,
)


def fixture():
    def bullets(xs):
        return [{"number": n, "text": x} for n, x in enumerate(xs, 1)]
    audit = {"verified": True, "generation_id": "v26testgen01", "projects": [
        {"project": "Alpha", "base": bullets(["C"]), "library": bullets(["A"]), "final": bullets(["A"])},
        {"project": "Beta", "base": bullets(["D"]), "library": bullets(["B"]), "final": bullets(["B"])},
    ]}
    projects = {"candidate_project_ranking": [
        {"title": "Alpha", "requirement_matches": [
            {"requirement_id": "r1", "match_label": "direct", "coverage_points": 5.0},
            {"requirement_id": "r2", "match_label": "direct", "coverage_points": 7.0}]},
        {"title": "Beta", "requirement_matches": [
            {"requirement_id": "r1", "match_label": "direct", "coverage_points": 5.0},
            {"requirement_id": "r3", "match_label": "direct", "coverage_points": 8.0}]},
    ]}
    return audit, projects


def evaluator(*, bullets, ranking_row):
    mapping = {"A": ["r1"], "B": ["r1"], "C": ["r2"], "D": ["r3"]}
    known = {m["requirement_id"] for m in ranking_row["requirement_matches"]}
    return [{"bullet_index": i, "bullet_text": s,
             "supported_requirement_ids": [rid for rid in mapping.get(s, []) if rid in known]}
            for i, s in enumerate(bullets)]


def build_docx(path):
    from docx import Document
    d = Document()
    d.add_paragraph("EXPERIENCE")
    d.add_paragraph("No changes to this section.")
    d.add_paragraph("PROJECTS")
    for name, bullet in (("Alpha", "A"), ("Beta", "B")):
        d.add_paragraph(name + " — Example")
        p = d.add_paragraph()
        p.add_run("• " + bullet)
    d.add_paragraph("SKILLS")
    d.add_paragraph("Python, SQL")
    d.save(path)


def convert_test_pages(page_count):
    def convert(docx_path, folder):
        from pypdf import PdfWriter
        pdf = folder / (docx_path.stem + ".pdf")
        writer = PdfWriter()
        for _ in range(page_count):
            writer.add_blank_page(width=612, height=792)
        with open(pdf, "wb") as f:
            writer.write(f)
        return pdf
    return convert


class JointOptimizationV26Tests(TestCase):
    def test_global_unique_requirement_coverage_improves(self):
        a, p = fixture()
        result = build_joint_optimization(a, p, evaluator=evaluator)
        self.assertEqual(result["status"], "candidate")
        self.assertEqual(result["baseline_points"], 5.0)
        self.assertEqual(result["proposed_points"], 15.0)
        self.assertEqual(result["gained_jd_ids"], ["r2", "r3"])
        self.assertEqual(result["lost_jd_ids"], ["r1"])
        self.assertTrue(result["requires_base_review"])
        self.assertEqual([x["after"] for x in result["projects"]], [["C"], ["D"]])
        self.assertTrue(result["project_set_unchanged"])

    def test_no_mutation_of_original_audit_or_project_rank(self):
        a, p = fixture()
        before_a, before_p = deepcopy(a), deepcopy(p)
        build_joint_optimization(a, p, evaluator=evaluator)
        self.assertEqual(a, before_a)
        self.assertEqual(p, before_p)

    def test_rejects_unverified_or_missing_input(self):
        a, p = fixture()
        a["verified"] = False
        self.assertEqual(build_joint_optimization(a, p, evaluator=evaluator)["status"], "withheld")

    def test_project_identity_mismatch_fails_closed(self):
        a, p = fixture()
        p["candidate_project_ranking"][0]["title"] = "Foreign"
        self.assertEqual(build_joint_optimization(a, p, evaluator=evaluator)["status"], "withheld")

    def test_duplicate_project_name_fails_closed(self):
        a, p = fixture()
        a["projects"][1]["project"] = "Alpha"
        self.assertEqual(build_joint_optimization(a, p, evaluator=evaluator)["status"], "withheld")

    def test_bad_requirement_identity_from_evaluator_blocks(self):
        a, p = fixture()
        def faulty(*, bullets, ranking_row):
            rows=evaluator(bullets=bullets, ranking_row=ranking_row)
            rows[0]["supported_requirement_ids"].append("foreign")
            return rows
        self.assertEqual(build_joint_optimization(a, p, evaluator=faulty)["status"], "withheld")

    def test_unscored_alternatives_do_not_get_quality_winner(self):
        a, p = fixture()
        def none(*, bullets, ranking_row):
            return [{"bullet_index":i,"bullet_text":t,"supported_requirement_ids":[]} for i,t in enumerate(bullets)]
        self.assertEqual(build_joint_optimization(a, p, evaluator=none)["status"], "no_proxy_gain")

    def test_no_accidental_new_projects_or_bullet_counts(self):
        a, p = fixture()
        result = build_joint_optimization(a, p, evaluator=evaluator)
        self.assertEqual([x["project"] for x in result["projects"]], ["Alpha", "Beta"])
        self.assertEqual([len(x["after"]) for x in result["projects"]], [1, 1])

    def test_docx_rewrites_only_verified_bullet_paragraphs(self):
        a, p = fixture()
        result = build_joint_optimization(a, p, evaluator=evaluator)
        with TemporaryDirectory() as tmp:
            src, dest = Path(tmp)/"in.docx", Path(tmp)/"out.docx"
            build_docx(src)
            digest = sha256(src.read_bytes()).hexdigest()
            write_optimized_docx(source_path=src, audit_sha=digest, proposal=result, destination=dest)
            from docx import Document
            before = [x.text for x in Document(src).paragraphs]
            after = [x.text for x in Document(dest).paragraphs]
            self.assertEqual(before[:3], after[:3])
            self.assertEqual(before[-2:], after[-2:])
            self.assertEqual([x for x in after if x.startswith("•")], ["• C", "• D"])
            self.assertEqual([x for x in before if x.startswith("•")], ["• A", "• B"])

    def test_existing_candidate_file_is_never_overwritten(self):
        a, p = fixture()
        result = build_joint_optimization(a, p, evaluator=evaluator)
        with TemporaryDirectory() as tmp:
            src, dest = Path(tmp)/"source.docx", Path(tmp)/"existing.docx"
            build_docx(src)
            dest.write_bytes(b"important existing output")
            with self.assertRaisesRegex(ValueError, "Refusing to overwrite"):
                write_optimized_docx(source_path=src,
                    audit_sha=sha256(src.read_bytes()).hexdigest(), proposal=result,
                    destination=dest)
            self.assertEqual(dest.read_bytes(), b"important existing output")

    def test_docx_source_hash_must_match(self):
        a, p = fixture()
        result = build_joint_optimization(a, p, evaluator=evaluator)
        with TemporaryDirectory() as tmp:
            src, dest = Path(tmp)/"in.docx", Path(tmp)/"out.docx"
            build_docx(src)
            with self.assertRaises(ValueError):
                write_optimized_docx(source_path=src, audit_sha="bad", proposal=result, destination=dest)
            self.assertFalse(dest.exists())

    def test_persist_real_one_page_candidate_without_touching_source(self):
        a, p = fixture()
        result = build_joint_optimization(a, p, evaluator=evaluator)
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            output = repo/"outputs"/"tailored_resumes"
            output.mkdir(parents=True)
            src = output / "app_156_original.docx"
            build_docx(src)
            initial = src.read_bytes()
            response = materialize_verified_candidate(source_docx=src,
                audit_sha=sha256(initial).hexdigest(), proposal=result,
                repo_root=repo, application_id=156, generation_id="v26testgen01",
                converter=convert_test_pages(1))
            self.assertEqual(response["status"], "generated")
            self.assertEqual(response["pages"], 1)
            self.assertEqual(src.read_bytes(), initial)
            self.assertTrue(Path(response["docx_path"]).is_file())
            self.assertTrue(Path(response["pdf_path"]).is_file())
            receipt=json.loads(Path(response["receipt_path"]).read_text())
            self.assertEqual(receipt["verified_pdf_pages"], 1)
            self.assertFalse(receipt["candidate_is_approved"])
            self.assertEqual(receipt["source_to_final_bullet_provenance"],result["projects"])

    def test_failed_two_page_render_leaves_no_candidate(self):
        a, p = fixture()
        result = build_joint_optimization(a, p, evaluator=evaluator)
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            output = repo/"outputs"/"tailored_resumes"
            output.mkdir(parents=True)
            src = output / "app_156_original.docx"
            build_docx(src)
            original = src.read_bytes()
            with self.assertRaisesRegex(RuntimeError,"2 pages"):
                materialize_verified_candidate(source_docx=src,
                    audit_sha=sha256(original).hexdigest(),proposal=result,
                    repo_root=repo,application_id=156,generation_id="v26testgen01",
                    converter=convert_test_pages(2))
            self.assertFalse((output/"optimizations").exists())
            self.assertEqual(src.read_bytes(),original)

    def test_reject_foreign_app_source_document(self):
        a,p=fixture()
        result=build_joint_optimization(a,p,evaluator=evaluator)
        with TemporaryDirectory() as tmp:
            repo=Path(tmp);source=repo/"outputs"/"tailored_resumes"/"app_200_original.docx"
            source.parent.mkdir(parents=True)
            build_docx(source)
            with self.assertRaisesRegex(ValueError,"Foreign application"):
                materialize_verified_candidate(source_docx=source,
                    audit_sha=sha256(source.read_bytes()).hexdigest(),proposal=result,
                    repo_root=repo,application_id=156,generation_id="v26testgen01",
                    converter=convert_test_pages(1))

    def test_reject_no_gain_for_docx_write(self):
        a,p=fixture()
        result=build_joint_optimization(a,p,evaluator=evaluator)
        result["status"]="no_proxy_gain"
        with TemporaryDirectory() as tmp:
            src=Path(tmp)/"src.docx";dst=Path(tmp)/"dst.docx"
            build_docx(src)
            with self.assertRaises(ValueError):
                write_optimized_docx(source_path=src,audit_sha=sha256(src.read_bytes()).hexdigest(),proposal=result,destination=dst)

if __name__ == "__main__":
    import unittest
    unittest.main()

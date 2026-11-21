from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from docx import Document
from pypdf import PdfWriter

from tailoring.phase9f_certified_selection_v36 import build_certified_optimization
from tailoring.phase9f_joint_resume_optimizer_v2_6 import materialize_verified_candidate, write_optimized_docx
from tailoring.phase9f_v37_lead_candidate import build_lead_guarded_candidate
from tailoring.phase9f_v37_project_leads import wording_digest
from tests.test_phase9f_jd_relevance_optimizer_v35 import stronger_library_fixture


def fixture(lead='Built Python API test infrastructure.'):
    audit, projects, evaluator, base, _ = stronger_library_fixture()
    audit['docx_sha256'] = 'fixture'
    audit['projects'][0]['library'].append({'text': lead})
    review = {'source_docx_sha256': 'fixture', 'projects': {'API tests': [
        {'source': 'library', 'position': 2, 'sha256': wording_digest(lead), 'basis': 'Project purpose'},
    ]}}
    return audit, projects, evaluator, base, review


class LeadCandidateTest(unittest.TestCase):
    def test_opt_in_keeps_wording_and_source_in_sync_and_ordinary_policy_is_separate(self):
        audit, projects, evaluator, _, review = fixture()
        before = deepcopy((audit, review))
        proposal = build_lead_guarded_candidate(audit, projects, lead_review=review, evaluator=evaluator)
        self.assertEqual(proposal['status'], 'candidate', proposal)
        self.assertEqual(proposal['projects'][0]['after'][0], 'Built Python API test infrastructure.')
        self.assertIn('Evidence Library', proposal['projects'][0]['sources'][0])
        self.assertEqual(proposal['projects'][0]['supported_jd_ids'][0], ['reqtest'])
        self.assertEqual((audit, review), before)
        self.assertNotIn('lead_contract', build_certified_optimization(audit, projects, evaluator=evaluator))

    def test_missing_and_infeasible_leads_withhold_instead_of_dropping_the_lead(self):
        audit, projects, evaluator, _, review = fixture()
        missing = {**review, 'projects': {}}
        result = build_lead_guarded_candidate(audit, projects, lead_review=missing, evaluator=evaluator)
        self.assertEqual(result['status'], 'withheld')
        self.assertEqual(result['missing'][0]['reason'], 'lead_review_missing')
        pressured = 'Built and owned internal software for ' + ' '.join(f'workflow{i}' for i in range(30))
        audit, projects, evaluator, _, review = fixture(pressured)
        result = build_lead_guarded_candidate(audit, projects, lead_review=review, evaluator=evaluator)
        self.assertEqual(result['status'], 'withheld')
        self.assertNotIn('projects', result)

    def test_exact_first_docx_bullet_and_one_page_gate(self):
        audit, projects, evaluator, base, review = fixture()
        with TemporaryDirectory(prefix='v37-lead-contract-') as tmp:
            root = Path(tmp)
            source = root / 'outputs' / 'tailored_resumes' / 'app_156_fixture.docx'
            source.parent.mkdir(parents=True)
            doc = Document()
            for text in ('PROJECTS', 'API tests', '• ' + base, 'SKILLS', 'Python'):
                doc.add_paragraph(text)
            doc.save(source)
            digest = sha256(source.read_bytes()).hexdigest()
            audit['docx_sha256'] = review['source_docx_sha256'] = digest
            proposal = build_lead_guarded_candidate(audit, projects, lead_review=review, evaluator=evaluator)
            self.assertEqual(proposal['status'], 'candidate', proposal)
            corrupted = deepcopy(proposal)
            first = corrupted['projects'][0]['after']
            first.insert(0, 'Testing detail before the approved lead.')
            with self.assertRaisesRegex(ValueError, 'does not open'):
                write_optimized_docx(source_path=source, audit_sha=digest, proposal=corrupted,
                                     destination=root / 'reject.docx')

            def render(docx, work, pages):
                bullets = [p.text for p in Document(docx).paragraphs if p.text.startswith('•')]
                self.assertEqual(bullets[0], '• Built Python API test infrastructure.')
                pdf = work / 'fit.pdf'
                writer = PdfWriter()
                for _ in range(pages):
                    writer.add_blank_page(width=595, height=842)
                with pdf.open('wb') as out:
                    writer.write(out)
                return pdf

            args = {'source_docx': source, 'audit_sha': digest, 'proposal': proposal, 'repo_root': root,
                    'application_id': 156, 'generation_id': 'fixture-generation'}
            with self.assertRaisesRegex(RuntimeError, '2 pages'):
                materialize_verified_candidate(**args, converter=lambda p, w: render(p, w, 2))
            self.assertFalse((source.parent / 'optimizations').exists())
            output = materialize_verified_candidate(**args, converter=lambda p, w: render(p, w, 1))
            self.assertEqual(output['pages'], 1)
            self.assertEqual(sha256(source.read_bytes()).hexdigest(), digest)

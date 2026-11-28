from contextlib import nullcontext
from copy import deepcopy
from functools import partial
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import MagicMock, patch

from docx import Document
from pypdf import PdfReader, PdfWriter

from tailoring.phase9f_automatic_bestof_v30 import evaluate_auto
from tailoring.phase9f_automatic_bestof_v30_ui import render_automatic_bestof
from tailoring.phase9f_joint_resume_optimizer_v2_6 import materialize_verified_candidate
from tailoring.phase9f_v37_guarded_evaluation import bind_guarded_floor, verify_guarded_artifact


def pdf_bytes(pages=1):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=595, height=842)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


class GuardedCandidateTests(unittest.TestCase):
    def setUp(self):
        work = TemporaryDirectory()
        self.addCleanup(work.cleanup)
        self.root = Path(work.name)
        output = self.root / 'outputs' / 'tailored_resumes'
        output.mkdir(parents=True)
        self.source = output / 'app_12_incumbent.docx'
        self.lead, self.old, self.new = 'Built the API test tool.', 'Ran regression tests.', 'Wrote SQL queries.'
        source_pdf = self.source.with_suffix('.pdf')
        source_pdf.write_bytes(pdf_bytes())
        doc = Document()
        for line in ('PROJECTS', 'API tool', '• ' + self.lead, '• ' + self.old, 'SKILLS', 'Python'):
            doc.add_paragraph(line)
        doc.save(self.source)
        self.original = self.source.read_bytes()
        self.audit = {'verified': True, 'generation_id': 'guard-fixture', 'docx_sha256': sha256(self.original).hexdigest(),
                      'projects': [{'project': 'API tool', 'base': [], 'library': [{'text': self.new}],
                                    'final': [{'text': text} for text in (self.lead, self.old)]}]}
        self.fit = {'fit_one_page': True, 'page_count': 1, 'docx_path': str(self.source), 'pdf_path': str(source_pdf),
                    'tailored_projects_used': {'recommended_projects': [
                        {'title': 'API tool', 'draft_bullets': [self.lead, self.old]}]}}
        self.generation = {'generation_id': 'guard-fixture', 'fit_result': self.fit}
        self.requirements = [
            {'requirement_id': 'core', 'text': 'Perform software testing', 'importance': 'core'},
            {'requirement_id': 'pref', 'text': 'Knowledge of SQL is preferred', 'importance': 'preferred'},
        ]
        self.jd = 'Responsibilities: Perform software testing\nKnowledge of SQL is preferred'
        self.report = {'raw_jd_text': self.jd, 'stable_analysis': {'canonical_requirements': self.requirements}}
        self.proposal = {'status': 'candidate', 'changed': True, 'version': 'fixture', 'lost_jd_ids': [],
                         'baseline_points': 2, 'proposed_points': 3, 'gained_jd_ids': ['pref'],
                         'requires_base_review': False, 'projects': [{
                             'project': 'API tool', 'before': [self.lead, self.old], 'after': [self.lead, self.new],
                             'sources': [['Current final'], ['Evidence Library']], 'supported_jd_ids': [['core'], ['pref']],
                         }]}
        self.binding = bind_guarded_floor(audit=self.audit, raw_jd=self.jd, baseline_report=self.report,
                                         incumbent_pdf=source_pdf.read_bytes(),
                                         trusted_native=self.score(self.audit['docx_sha256']))
        self.materialized = 0

    def score(self, digest, *, candidate=False, strength=4):
        return {'docx_sha256': digest, 'actual_docx_evidence': True, 'claim_review_required_count': 0,
                'scoring_version': 'fixture-native', 'deterministic_alignment_score': 55 if candidate else 40,
                'canonical_requirements': [
                    {**self.requirements[0], 'match_label': 'direct', 'evidence_strength': strength,
                     'evidence': [{'text': self.lead}]},
                    {**self.requirements[1], 'match_label': 'direct' if candidate else 'none',
                     'evidence_strength': 4 if candidate else 0,
                     'evidence': [{'text': self.new}] if candidate else []},
                ]}

    def run_trial(self, *, guarded=True, binding=None, weaker=False, pages=1, stale_score=False):
        def convert(docx, folder):
            self.materialized += 1
            output = folder / 'controlled.pdf'
            output.write_bytes(pdf_bytes(pages))
            return output

        def score(**kw):
            candidate = not Path(kw['docx_path']).samefile(self.source)
            result = self.score(kw['expected_sha256'], candidate=candidate, strength=2 if candidate and weaker else 4)
            if not candidate and stale_score:
                result['canonical_requirements'][0]['evidence'][0]['text'] = self.old
            return result

        return evaluate_auto(
            audit=self.audit, projects={}, fit=self.fit, generation=self.generation, baseline_report=self.report,
            raw_jd_text=self.jd, source_docx=self.source, repo_root=self.root, application_id=12,
            optimizer=lambda *_: deepcopy(self.proposal), scorer=score,
            generator=partial(materialize_verified_candidate, converter=convert),
            guarded_floor_binding=(binding if binding is not None else self.binding) if guarded else None,
        )

    def test_explicit_review_preserves_native_and_writes_only_a_separate_fixture(self):
        checked = self.run_trial()
        self.assertEqual(checked['guarded_review']['status'], 'verified', checked)
        self.assertEqual((checked['a_score'], checked['b_score']), (40, 55))
        self.assertEqual(checked['winner'], 'existing_final')
        self.assertFalse(checked['candidate_approved'])
        self.assertEqual(self.source.read_bytes(), self.original)
        bullets = [p.text[2:] for p in Document(checked['candidate_file']).paragraphs if p.text.startswith('• ')]
        self.assertEqual(bullets, [self.lead, self.new])
        self.assertEqual(len(PdfReader(checked['candidate_pdf']).pages), 1)
        self.assertEqual(checked['b_docx_sha256'], sha256(Path(checked['candidate_file']).read_bytes()).hexdigest())
        # The normal automatic candidate path still uses its original comparator.
        self.assertEqual(self.run_trial(guarded=False, weaker=True)['winner'], 'optimized_candidate')

    def test_higher_native_and_preferred_cannot_hide_a_same_label_hard_strength_loss(self):
        checked = self.run_trial(weaker=True)
        self.assertEqual(checked['status'], 'withheld')
        self.assertEqual(checked['guarded_review']['failed_ids'], ['core'])
        self.assertNotIn('candidate_file', checked)

    def test_stale_inputs_and_unowned_wording_fail_before_render(self):
        for change in ('jd_sha256', 'pdf_sha256', 'scoring_version'):
            with self.subTest(change=change):
                self.assertEqual(self.run_trial(binding={**self.binding, change: 'stale'})['status'], 'withheld')
        self.assertEqual(self.run_trial(stale_score=True)['status'], 'withheld')
        self.proposal['projects'][0]['sources'][-1] = ['Selected Base']
        self.assertEqual(self.run_trial()['status'], 'withheld')
        self.assertEqual(self.materialized, 0)

    def test_infeasible_slate_and_two_page_output_withhold(self):
        candidate = self.proposal
        self.proposal = {'status': 'structurally_infeasible', 'reason': 'Insufficient space for the protected floor.'}
        self.assertEqual(self.run_trial()['status'], 'withheld')
        self.assertEqual(self.materialized, 0)
        self.proposal = candidate
        checked = self.run_trial(pages=2)
        self.assertEqual(checked['status'], 'withheld')
        self.assertIn('2 pages', checked['reason'])
        self.assertNotIn('candidate_file', checked)

    def test_readback_rejects_reordered_projects_with_identical_bullets(self):
        doc = Document()
        for line in ('PROJECTS', 'Second', '• Built the services.', 'First', '• Built the interface.', 'SKILLS'):
            doc.add_paragraph(line)
        path = self.root / 'wrong-order.docx'
        doc.save(path)
        pdf = self.root / 'fixture.pdf'
        pdf.write_bytes(pdf_bytes())
        proposal = {'projects': [{'project': 'First', 'after': ['Built the interface.']},
                                 {'project': 'Second', 'after': ['Built the services.']}]}
        with self.assertRaisesRegex(ValueError, 'expected project order'):
            verify_guarded_artifact(proposal, path, pdf)


class OfflineReceiptBoundaryTests(unittest.TestCase):
    def test_only_compatible_receipts_offer_the_opt_in_read_only_view(self):
        jd = 'Knowledge of SQL is preferred'
        requirement = {'id': 'sql', 'importance': 'preferred', 'text': jd, 'match_label': 'none'}
        opening, new = 'Built the tool', 'Wrote SQL queries'
        doc = {'jd_sha256': sha256(jd.encode()).hexdigest(), 'scoring_version': 'native', 'score': 12,
               'layout_reference_sha256': 'layout', 'status': 'verified', 'pages': 1,
               'docx_leads_verified': True, 'requirements': [requirement]}
        original = {**doc, 'docx_sha256': 'source', 'docx_project_order': [{'project': 'Tool', 'after': [opening]}]}
        trial = {**doc, 'docx_sha256': 'trial', 'docx_project_order': [{'project': 'Tool', 'after': [opening, new]}]}
        coverage = {'categories': {category: {'earned': 0, 'available': 1, 'status': 'applicable'}
                                   for category in ('supporting', 'preferred')},
                    'requirements': [{**requirement, 'earned': 0, 'coverage': 'unsupported'}]}
        data = json.dumps({'baseline': original, 'baseline_bonus': coverage, 'floors': {}, 'source_reviews': [],
                           'variants': {'trial': {'native': trial, 'bonus': coverage,
                                                 'exact_ats_technologies': ['sql']}}}).encode()
        binding = {'data': data, 'receipt_sha256': sha256(data).hexdigest(), 'variant': 'trial',
                   'scoring_version': 'native', 'baseline_sha256': 'source', 'trial_sha256': 'trial'}
        audit = {'verified': True, 'docx_sha256': 'layout', 'projects': [
            {'project': 'Tool', 'base': [{'text': opening}], 'library': [{'text': new}]}]}
        st = MagicMock()
        st.session_state = {}
        st.expander.return_value = nullcontext()
        st.button.return_value = False
        report = {'raw_jd_text': jd, 'stable_analysis': {
            'scoring_version': 'native', 'canonical_requirements': [{**requirement, 'requirement_id': 'sql'}]}}

        def render(trusted, show):
            st.reset_mock()
            st.checkbox.return_value = show
            with patch('tailoring.phase9f_project_bullet_sources_v2_3._bound_candidate_sources', return_value=([], '')), patch(
                'tailoring.phase9f_final_evidence_comparison_v2_4.build_final_evidence_audit', return_value=audit,
            ), patch('database.tailoring_generation_control.get_tailoring_generation') as get_generation:
                render_automatic_bestof(st, application_id=12, generation_id='fixture', projects={},
                                        fit={'fit_one_page': True}, baseline_report=report, raw_jd_text=jd,
                                        execution=None, decision=None, repo_root=Path.cwd(), trusted_offline_bonus=trusted)
                get_generation.assert_not_called()
            self.assertEqual(st.session_state, {})

        render({**binding, 'receipt_sha256': 'stale'}, True)
        st.checkbox.assert_not_called()
        render(binding, False)
        self.assertEqual(st.checkbox.call_args.args[0], 'Show verified offline evidence (read-only)')
        self.assertNotIn('**Main native Job Match** · 12/100 → 12/100', [x.args[0] for x in st.write.call_args_list])
        render(binding, True)
        st.write.assert_any_call('**Main native Job Match** · 12/100 → 12/100')

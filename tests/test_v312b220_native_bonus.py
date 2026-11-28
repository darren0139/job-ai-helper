from copy import deepcopy
from functools import partial
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from docx import Document
from pypdf import PdfWriter

from analysis_stability.stable_evidence_scoring import MATCH_VALUES
from tailoring.document_grounded_analysis import analyze_actual_resume_against_jd
from tailoring.phase8_verification import build_phase8_verification
from tailoring.phase9f_automatic_bestof_v30 import evaluate_auto, native_document_score
from tailoring.phase9f_certified_selection_v36 import build_certified_optimization, selected_base_floor_gate
from tailoring.phase9f_joint_resume_optimizer_v2_6 import materialize_verified_candidate
from tailoring.phase9f_native_bonus_v312b220 import (
    checked_phase8_base_floor, compare_native_bonus, native_selection, phase8_native_bonus,
)
from tailoring.phase9f_v364_document_reverify import build_frozen_selected_base_document_report


class NativeBonusTests(unittest.TestCase):
    jd = 'Requirements\n- Experience with Python\nPreferred Qualifications\n- Experience with PostgreSQL'

    def analyze(self, text):
        return analyze_actual_resume_against_jd(resume_text=text, jd_text=self.jd, jd_profile={})

    def comparison(self, before, after):
        return compare_native_bonus(before['stable_analysis'], after['stable_analysis'], raw_jd=self.jd,
            before_document='a' * 64, after_document='b' * 64, identity=before['document_analysis']['identity'])

    def test_zero_distinct_from_non_applicable_and_direct_improvement(self):
        before = self.analyze('Developed a tool using Python.')
        after = self.analyze('Skills:\nPython, PostgreSQL\nDeveloped a tool using Python.')
        result = self.comparison(before, after)
        self.assertEqual(result['status'], 'verified')
        self.assertEqual(result['lanes']['supporting'], {'status': 'not_applicable'})
        preferred = result['lanes']['preferred']
        self.assertEqual(preferred['before_units'], 0)
        row, = result['requirements']
        self.assertEqual(row['before']['match_label'], 'none')
        self.assertEqual(row['after']['match_label'], 'direct')
        self.assertIn('PostgreSQL', row['after']['evidence'][0]['text'])
        self.assertEqual(preferred['after_units'], preferred['available_units'])

    def test_original_fraction_is_retained_and_duplicate_rows_fail_closed(self):
        before = self.analyze('Designed and implemented schemas using PostgreSQL.')
        after = deepcopy(before)
        for report in (before, after):
            rows = report['stable_analysis']['canonical_requirements']
            preferred = next(r for r in rows if r['importance'] == 'preferred')
            preferred['group_weight_fraction'] = 0.5
        self.assertEqual(self.comparison(before, after)['lanes']['preferred']['available_units'], 0.5)
        rows.append(deepcopy(preferred))
        self.assertEqual(self.comparison(before, after)['status'], 'unavailable')

    def test_missing_positive_witness_withholds_lane(self):
        before = self.analyze('Developed a tool using Python.')
        after = deepcopy(before)
        row = next(r for r in after['stable_analysis']['canonical_requirements'] if r['importance'] == 'preferred')
        row.update(match_label='transferable', evidence_strength=3, match_value=MATCH_VALUES['transferable'])
        self.assertEqual(self.comparison(before, after)['lanes']['preferred'], {'status': 'unavailable'})

    def test_phase8_accepts_valid_docx_and_rejects_changed_artifact_or_scope(self):
        with TemporaryDirectory() as temp:
            base_path, final_path = (Path(temp) / name for name in ('base.docx', 'final.docx'))
            for path, paragraphs in ((base_path, ['Developed a tool using Python.']),
                                    (final_path, ['Skills:', 'Python, PostgreSQL', 'Developed a tool using Python.'])):
                doc = Document()
                doc.add_paragraph('Professional experience')
                for paragraph in paragraphs:
                    doc.add_paragraph(paragraph)
                doc.add_paragraph('Education')
                doc.add_paragraph('Studied information systems with an emphasis on data analysis, applied statistics, '
                                  'and the design of business information systems. Worked with peers to organize '
                                  'weekly workshops for incoming students.')
                doc.save(path)
            content = base_path.read_bytes()
            base_digest = sha256(content).hexdigest()
            base, contract = build_frozen_selected_base_document_report(
                baseline_report={'jd_profile': {}, 'resume_profile': {}}, jd_text=self.jd,
                source_artifact={'artifact_type': 'docx', 'sha256': base_digest,
                                 'byte_size': len(content), 'artifact_bytes': content})
            receipt = build_phase8_verification(baseline_report=base, raw_jd_text=self.jd,
                generation_state={'fit_result': {'fit_one_page': True, 'page_count': 1, 'docx_path': str(final_path)}})
            receipt['starting_document_contract'] = contract

            def coverage(jd=self.jd, source_digest=base_digest):
                return phase8_native_bonus(receipt, raw_jd=jd, final_path=final_path, selected_base_sha256=source_digest)

            self.assertEqual(coverage()['lanes']['preferred']['after_units'], 1)
            self.assertEqual(coverage(source_digest='0' * 64)['status'], 'unavailable')
            self.assertEqual(coverage(jd=self.jd + '\n')['status'], 'unavailable')
            final_path.write_bytes(content)
            self.assertEqual(coverage()['status'], 'unavailable')

    def test_same_label_hard_strength_regression_blocks_bonus(self):
        base = self.analyze('Skills:\nPython')
        fitted = self.analyze('Skills:\nPython, PostgreSQL')
        before = base['stable_analysis']
        after = fitted['stable_analysis']
        hard = next(r for r in after['canonical_requirements'] if r['importance'] != 'preferred')
        self.assertEqual(hard['match_label'], 'direct')
        old_hard = next(r for r in before['canonical_requirements'] if r['requirement_id'] == hard['requirement_id'])
        old_hard.update(deepcopy(hard))
        bonus = self.comparison(base, fitted)
        hard['evidence_strength'] -= 1
        result = native_selection(before, after, bonus, 25)
        self.assertEqual(result['decision'], 'hard_regression')
        self.assertEqual(result['hard_floors'][0]['status'], 'regressed')

    def test_actual_fitted_bonus_selection_allows_native_score_disagreement(self):
        jd = ('Requirements\n- Proficiency in one or more backend languages (Java/.NET/Python/PHP)\nPreferred Qualifications\n'
              '- Proficiency in database will be an added advantage')
        old = 'Implemented REST API endpoints using Python.'
        new = 'Implemented PostgreSQL schema and queries.'
        profile = {'projects': [{'title': 'Reporting Tool', 'bullets': [old, new]}]}
        with TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / 'outputs' / 'tailored_resumes' / 'app_23_fitted.docx'
            path.parent.mkdir(parents=True)
            doc = Document()
            for line in ('PROJECTS', 'Reporting Tool', '• ' + old, 'SKILLS', 'Python', 'Education',
                         'Studied information systems with an emphasis on applied statistics and business processes. '
                         'Organized weekly workshops to share methods for reading and contextualizing reports.'):
                doc.add_paragraph(line)
            doc.save(path)
            base_bytes = path.read_bytes()
            digest = sha256(base_bytes).hexdigest()
            base, contract = build_frozen_selected_base_document_report(
                baseline_report={'jd_profile': {}, 'resume_profile': profile}, jd_text=jd,
                source_artifact={'artifact_type': 'docx', 'sha256': digest,
                                 'byte_size': len(base_bytes), 'artifact_bytes': base_bytes})
            # The lineage authority contains both sources. Only the fitted DOCX
            # can supply document score evidence for one of them.
            report = {**base, 'resume_profile': profile}
            reqs = report['stable_analysis']['canonical_requirements']
            ids = {row['importance']: row['requirement_id'] for row in reqs}
            project = {'title': 'Reporting Tool', 'draft_bullets': [old]}
            fit = {'fit_one_page': True, 'page_count': 1, 'docx_path': str(path),
                   'tailored_projects_used': {'recommended_projects': [project]}}
            generation = {'generation_id': 'fixture-23', 'fit_result': fit}
            audit = {'verified': True, 'generation_id': 'fixture-23', 'docx_sha256': digest,
                     'projects': [{'project': 'Reporting Tool', 'base': [{'text': old}],
                                   'library': [{'text': new}], 'final': [{'text': old}]}]}
            ranking = {'candidate_project_ranking': [{'title': 'Reporting Tool', 'requirement_matches': [
                {'requirement_id': r['requirement_id'], 'requirement_text': r['text'], 'importance': r['importance'],
                 'match_label': 'direct', 'coverage_points': 1} for r in reqs]}]}

            def evaluate_links(*, bullets, ranking_row):
                return [{'bullet_index': i, 'bullet_text': text,
                         'supported_requirement_ids': [ids['preferred' if text == new else 'core']]}
                        for i, text in enumerate(bullets)]

            def optimizer(audit, projects, *, bonus_priorities):
                return build_certified_optimization(audit, projects, evaluator=evaluate_links,
                    max_trials=1, bonus_priorities=bonus_priorities)

            def converter(docx, folder):
                writer = PdfWriter()
                writer.add_blank_page(width=612, height=792)
                output = folder / 'candidate.pdf'
                writer.write(output)
                return output

            def score(**kwargs):
                actual = native_document_score(**kwargs)
                if not Path(kwargs['docx_path']).samefile(path):
                    actual['deterministic_alignment_score'] = base['stable_analysis']['deterministic_alignment_score'] - 1
                return actual

            result = evaluate_auto(audit=audit, projects=ranking, fit=fit, generation=generation,
                baseline_report=report, raw_jd_text=jd, source_docx=path, repo_root=root, application_id=23,
                optimizer=optimizer, generator=partial(materialize_verified_candidate, converter=converter),
                scorer=score, native_bonus_policy=True, rank_native_bonus=True)
            self.assertEqual(result['winner'], 'optimized_candidate', result)
            self.assertEqual(result['delta'], -1)
            self.assertEqual(result['native_selection']['decision'], 'bonus_improvement')
            self.assertTrue(result['native_selection']['native_score_disagreement'])
            self.assertEqual(result['hard_regressed_ids'], [])
            self.assertEqual(result['native_bonus']['lanes']['preferred']['after_units'], 1)
            self.assertIn(new, '\n'.join(p.text for p in Document(result['candidate_file']).paragraphs))
            self.assertEqual(path.read_bytes(), base_bytes)
            self.assertFalse(result['candidate_approved'])

            phase8 = build_phase8_verification(baseline_report=base, raw_jd_text=jd, generation_state=generation)
            phase8['starting_document_contract'] = contract
            proof = checked_phase8_base_floor(phase8, result, raw_jd=jd, final_path=path, selected_base_sha256=digest)
            self.assertEqual(proof['selected_base_comparison_status'], 'maintained')
            starting = {'status': 'verified', **proof, **{key: result[key] for key in
                        ('a_docx_sha256', 'a_score', 'scoring_version')}}
            self.assertEqual(selected_base_floor_gate(result, starting)['winner'], 'optimized_candidate')

"""Focused controls for isolated counterfactual plans and document verification."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from docx import Document
from pypdf import PdfWriter

from tailoring.phase9f_v37_corpus_benchmark import build_case_model
from tailoring.phase9f_v37_counterfactual import evaluate_counterfactual, plan_trials
from tailoring.phase9f_v37_document_trial import evaluate_document_trial
from tests.test_v37_corpus_benchmark import fixture


PROJECT = 'Synthetic project'


def counterfactual_fixture():
    case, evaluator, both = fixture()
    project = case['audit']['projects'][0]
    old_lib = 'Maintained existing regression fixtures.'
    project['library'].append({'text': old_lib})
    project['final'].append({'text': old_lib})
    case.update(application_id=1, generation_id='fixture-generation')
    return case, evaluator, both, old_lib


class ControlledPlans(unittest.TestCase):
    def test_remove_both_swap_directions_and_forced_in(self):
        case, evaluator, both, old_lib = counterfactual_fixture()
        model, source = build_case_model(case['audit'], case['projects'], evaluator=evaluator)
        section = case['audit']['projects'][0]
        new_base = section['base'][1]['text']
        new_library = section['library'][1]['text']
        plans = [
            ('remove', {'remove': both}, 'remove', [old_lib]),
            ('base_to_library', {'remove': both, 'insert': new_library}, 'swap', [new_library, old_lib]),
            ('library_to_base', {'remove': old_lib, 'insert': new_base}, 'swap', [both, new_base]),
        ]
        for operation, inputs, role, expected in plans:
            with self.subTest(operation=operation):
                plan = plan_trials(model, source, operation=operation, project=PROJECT, **inputs)
                self.assertEqual(plan[role]['proposal']['projects'][0]['after'], expected)
        forced = plan_trials(model, source, operation='force_in', project=PROJECT, insert=new_library)
        self.assertIn(new_library, forced['forced_in']['proposal']['projects'][0]['after'])
        self.assertEqual(len(forced['forced_in']['proxy_receipt']), 4)
        with self.assertRaisesRegex(ValueError, 'source provenances'):
            plan_trials(model, source, operation='base_to_library', project=PROJECT,
                        remove=old_lib, insert=new_base)

    def test_space_trial_compares_short_swap_and_same_extra_without_swap(self):
        case, evaluator, both, old_lib = counterfactual_fixture()
        section = case['audit']['projects'][0]
        short_base = 'Python tests.'
        section['base'][1]['text'] = short_base
        new_library = section['library'][1]['text']
        model, source = build_case_model(case['audit'], case['projects'], evaluator=evaluator)
        plans = plan_trials(model, source, operation='use_freed_words', project=PROJECT,
                            remove=old_lib, insert=short_base, extra=new_library)
        self.assertEqual(plans['swap']['proposal']['projects'][0]['after'], [both, short_base])
        self.assertEqual(plans['swap_plus_extra']['proposal']['projects'][0]['after'],
                         [both, short_base, new_library])
        self.assertEqual(plans['extra_without_swap']['proposal']['projects'][0]['after'],
                         [both, old_lib, new_library])

    def test_native_tie_preserves_existing_and_records_exact_effect(self):
        case, evaluator, both, _ = counterfactual_fixture()
        prior = deepcopy(case)

        def native_fixture(case, proposal=None, *, work_root=None):
            return {'status': 'verified', 'score': 31, 'pages': 1, 'docx_sha256': 'changed' if proposal else 'old',
                    'scoring_version': 'fixture', 'jd_sha256': 'jd', 'layout_reference_sha256': 'layout',
                    'requirements': [{'id': 'test', 'text': 'Use Python for unit testing',
                                      'importance': 'core', 'match_label': 'weak'}]}

        receipt = evaluate_counterfactual(case, operation='remove', project=PROJECT, remove=both,
                                          evaluator=evaluator, evaluate=native_fixture)
        trial = receipt['trials']['remove']
        self.assertEqual(trial['status'], 'verified')
        self.assertEqual(trial['comparison']['native_delta'], 0)
        self.assertEqual(trial['saved_link_proxy_delta'], 0)
        self.assertTrue(trial['comparison']['prefer_existing_on_tie'])
        self.assertEqual(trial['changed_bullets'][0]['wording'], both)
        self.assertEqual(trial['changed_bullets'][0]['saved_links'][0]['saved_support'], 'shared')
        self.assertEqual(case, prior)


class DocumentBoundary(unittest.TestCase):
    def test_bytes_page_fit_and_scorer_input_are_isolated(self):
        case, evaluator, both, old_lib = counterfactual_fixture()
        model, source = build_case_model(case['audit'], case['projects'], evaluator=evaluator)
        proposal = plan_trials(model, source, operation='remove', project=PROJECT, remove=both)['remove']['proposal']
        with TemporaryDirectory(prefix='v37-trial-fixture-') as tmp:
            root = Path(tmp)
            source_docx = root / 'untouched.docx'
            doc = Document()
            for line in ('EXPERIENCE', 'Untouched employment', 'PROJECTS', PROJECT,
                         '• ' + both, '• ' + old_lib, 'SKILLS', 'Python'):
                doc.add_paragraph(line)
            doc.save(source_docx)
            content = source_docx.read_bytes()
            case['source_docx'] = source_docx
            case['audit']['docx_sha256'] = sha256(content).hexdigest()
            case['generation'] = {'fit_result': {'fit_one_page': True, 'tailored_projects_used': {
                'recommended_projects': [{'title': PROJECT, 'draft_bullets': [both, old_lib]}],
            }}}

            def fake_renderer(path, work, pages=1):
                writer = PdfWriter()
                for _ in range(pages):
                    writer.add_blank_page(300, 400)
                pdf = work / 'verified.pdf'
                with pdf.open('wb') as file:
                    writer.write(file)
                return pdf

            def fake_scorer(*, docx_path, generation_state, baseline_report, raw_jd_text, expected_sha256):
                rows = [p.text for p in Document(docx_path).paragraphs]
                self.assertNotIn('• ' + both, rows)
                self.assertIn('• ' + old_lib, rows)
                self.assertIn('Untouched employment', rows)
                self.assertEqual(sha256(docx_path.read_bytes()).hexdigest(), expected_sha256)
                return {'docx_sha256': expected_sha256, 'actual_docx_evidence': True,
                        'deterministic_alignment_score': 31, 'scoring_version': 'fixture',
                        'canonical_requirements': [{**row, 'match_label': 'none'} for row in
                                                   case['baseline']['stable_analysis']['canonical_requirements']]}

            got = evaluate_document_trial(case, proposal, work_root=root, renderer=fake_renderer, scorer=fake_scorer)
            self.assertEqual(got['status'], 'verified')
            self.assertEqual(got['pages'], 1)
            nonfit = evaluate_document_trial(case, proposal, work_root=root,
                        renderer=lambda path, work: fake_renderer(path, work, pages=2),
                        scorer=lambda **kwargs: self.fail('A multi-page derivative should not be scored.'))
            self.assertEqual(nonfit['status'], 'fit_failed')
            self.assertEqual(nonfit['pages'], 2)
            self.assertIsNone(nonfit['score'])
            self.assertEqual(source_docx.read_bytes(), content)
            self.assertEqual(list(root.iterdir()), [source_docx])


if __name__ == '__main__':
    unittest.main()

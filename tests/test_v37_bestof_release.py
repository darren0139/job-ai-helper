"""Disposable integration tests for the Best-of master boundary."""
from contextlib import nullcontext
from functools import partial
from hashlib import sha256
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import MagicMock, patch

from docx import Document
from pypdf import PdfWriter

from parse import read_resume_docx
from tailoring.document_grounded_analysis import analyze_actual_resume_against_jd
from tailoring.phase9f_automatic_bestof_v30 import evaluate_auto, native_document_score
from tailoring.phase9f_automatic_bestof_v30_ui import render_automatic_bestof
from tailoring.phase9f_certified_selection_v36 import build_certified_optimization
from tailoring.phase9f_final_evidence_comparison_v2_4 import build_final_evidence_audit
from tailoring.phase9f_joint_resume_optimizer_v2_6 import materialize_verified_candidate
from tests.test_phase9f_final_evidence_v2_4 import fixture


def _selected_option(_label, options, *, index=0, **_kwargs):
    """Mirror selectbox's option-value contract, rather than returning a mock."""
    values = list(options)
    return values[index] if values and index is not None else None


class BestOfRelease(unittest.TestCase):
    def setUp(self):
        # These release tests use a synthetic Application 156/gen156. The real
        # display-receipt SQLite database must never be read or mutated by them.
        # A fresh DB per test also prevents one mock optimizer result from
        # suppressing another test's explicit comparison/review action.
        temp = TemporaryDirectory(prefix='v37_bestof_release_receipts_')
        self.addCleanup(temp.cleanup)
        db_path = Path(temp.name) / 'bestof_review.sqlite3'

        def connect_display_receipts():
            connection = sqlite3.connect(db_path)
            connection.row_factory = sqlite3.Row
            return connection

        isolated = patch('database.phase9f_bestof_review_state._connect',
                         side_effect=connect_display_receipts)
        isolated.start()
        self.addCleanup(isolated.stop)

    def test_selectbox_stub_preserves_project_values_and_bullet_indices(self):
        st = MagicMock()
        st.selectbox.side_effect = _selected_option
        projects = ['First project', 'Selected project']
        chosen = st.selectbox('Comparison project', projects, index=1)
        self.assertEqual(chosen, projects[1])
        self.assertIs(type(chosen), str)
        self.assertEqual(sha256(chosen.encode()).hexdigest(),
                         sha256(projects[1].encode()).hexdigest())
        bullet_index = st.selectbox('Base Resume wording', range(3), index=2)
        self.assertIs(type(bullet_index), int)
        self.assertEqual(bullet_index, 2)

    def test_certified_selection_reaches_exact_writer_through_master_audit(self):
        with TemporaryDirectory() as temporary:
            root, projects, candidates, fit, source = fixture(temporary)
            incumbent = 'Built a Python reporting utility'
            challenger = 'Built a Python reporting utility with automated unit tests'
            document = Document(source)
            document.paragraphs[2].text = '• ' + incumbent
            document.save(source)
            source_bytes = source.read_bytes()
            project = projects['recommended_projects'][0]
            project['draft_bullets'] = [incumbent]
            project['selected_blueprint_bullets'] = [incumbent]
            candidates[0]['resume_evidence']['bullets'] = [incumbent]
            candidates[0]['evidence_library_evidence']['bullets'] = [incumbent, challenger]
            fit['fitting_input_snapshot']['prepared_initial_state']['projects']['recommended_projects'][0]['draft_bullets'] = [incumbent]
            fit['tailored_projects_used'] = {'recommended_projects': [project]}
            projects['candidate_project_ranking'][0]['requirement_matches'] = [
                {'requirement_id': 'python', 'requirement_text': 'Python', 'importance': 'core',
                 'match_label': 'direct', 'coverage_points': 5},
                {'requirement_id': 'testing', 'requirement_text': 'Automated unit tests', 'importance': 'preferred',
                 'match_label': 'weak', 'coverage_points': 3},
            ]
            audit = build_final_evidence_audit(projects, fit, candidates, repo_root=root,
                                               application_id=156, expected_generation_id='gen156')
            self.assertTrue(audit['verified'], audit)

            def support(*, bullets, ranking_row):
                return [
                    {'bullet_index': index, 'bullet_text': text, 'supported_requirement_ids': (
                        ['python', 'testing'] if 'unit tests' in text else ['python'])}
                    for index, text in enumerate(bullets)
                ]

            proposal = build_certified_optimization(
                audit, projects, evaluator=support, max_trials=1,
            )
            self.assertEqual(proposal['status'], 'candidate', proposal)
            self.assertEqual(proposal['mathematical_certificate']['status'], 'optimal_proxy', proposal)

            def convert(docx, work):
                pdf = work / 'fixture.pdf'
                writer = PdfWriter()
                writer.add_blank_page(width=612, height=792)
                with pdf.open('wb') as handle:
                    writer.write(handle)
                return pdf

            def score(*, docx_path, expected_sha256, **_kwargs):
                paragraphs = [p.text for p in Document(docx_path).paragraphs]
                alternative = any(challenger in line for line in paragraphs)
                return {
                    'docx_sha256': expected_sha256, 'actual_docx_evidence': True,
                    'scoring_version': 'fixture', 'claim_review_required_count': 0,
                    'deterministic_alignment_score': 50 if alternative else 40,
                    'canonical_requirements': [
                        {'requirement_id': 'python', 'importance': 'core', 'match_label': 'direct'},
                        {'requirement_id': 'testing', 'importance': 'preferred',
                         'match_label': 'weak' if alternative else 'none'},
                    ],
                }

            args = dict(
                audit=audit, projects=projects, fit=fit,
                generation={'generation_id': 'gen156', 'fit_result': fit},
                baseline_report={'raw_jd_text': 'Python and unit testing', 'stable_analysis': {
                    'canonical_requirements': [{'requirement_id': 'python'}, {'requirement_id': 'testing'}],
                }},
                raw_jd_text='Python and unit testing', source_docx=source,
                repo_root=root, application_id=156, scorer=score,
            )
            blocked = MagicMock()
            pending_review = {**proposal, 'candidate_variants': [
                {**proposal['candidate_variants'][0], 'requires_base_review': True},
            ]}
            result = evaluate_auto(**args, optimizer=lambda *_: pending_review, generator=blocked)
            self.assertEqual(result['status'], 'needs_review', result)
            self.assertEqual(result['proposal'], pending_review)
            blocked.assert_not_called()

            outcome = evaluate_auto(
                **args, optimizer=lambda *_: proposal,
                generator=partial(materialize_verified_candidate, converter=convert),
            )
            self.assertEqual(outcome['winner'], 'optimized_candidate', outcome)
            self.assertFalse(outcome['candidate_approved'])
            self.assertEqual(outcome['v35_verified_candidates'], 1)
            self.assertEqual(source.read_bytes(), source_bytes)

    def test_native_adapter_calls_unchanged_master_scorer_on_actual_docx(self):
        with TemporaryDirectory() as temporary:
            _, _, _, fit, source = fixture(temporary)
            document = Document(source)
            document.paragraphs[2].text = '• Built a Python command-line tool.'
            document.add_paragraph(
                'Wrote Python scripts for cleaning CSV input, validating reporting fields, '
                'and producing readable monthly summaries for a sample inventory dataset. '
                'Documented each command with an example invocation and output.'
            )
            document.save(source)
            jd = 'Required qualifications:\n- Experience building software with Python.'
            profile = {'required_skills': ['Python']}
            baseline = analyze_actual_resume_against_jd(
                resume_text=read_resume_docx(str(source), preserve_complete_text=True),
                jd_text=jd, jd_profile=profile, resume_profile={},
            )
            actual = native_document_score(
                docx_path=source, generation_state={'fit_result': fit},
                baseline_report=baseline, raw_jd_text=jd,
                expected_sha256=sha256(source.read_bytes()).hexdigest(),
            )
            self.assertTrue(actual['actual_docx_evidence'])
            self.assertEqual(actual['claim_review_required_count'], 0)
            self.assertEqual(actual['scoring_version'], baseline['stable_analysis']['scoring_version'])
            self.assertEqual(
                [row['requirement_id'] for row in actual['canonical_requirements']],
                [row['requirement_id'] for row in baseline['stable_analysis']['canonical_requirements']],
            )

    def test_existing_fit_panel_waits_for_explicit_comparison(self):
        with TemporaryDirectory() as temporary:
            root, projects, candidates, fit, source = fixture(temporary)
            st = MagicMock()
            # The manual existing-fit trial is V3.5-only; Main now defaults to V3.7.
            st.session_state = {'phase9f_bestof_next_mode_156': 'v35-relevance'}
            st.button.return_value = False
            st.expander.return_value = MagicMock()
            st.spinner.return_value = nullcontext()
            generation = {'generation_id': 'gen156', 'fit_result': fit}
            with (
                patch('tailoring.phase9f_project_bullet_sources_v2_3._bound_candidate_sources',
                      return_value=(candidates, '')),
                patch('database.tailoring_generation_control.get_tailoring_generation',
                      return_value=generation) as get_generation,
                patch('tailoring.phase9f_automatic_bestof_v30.evaluate_auto',
                      return_value={'status': 'no_challenger'}) as evaluate,
                patch('tailoring.phase9f_automatic_bestof_v30.verify_fitted_a_against_baselines',
                      return_value={'status': 'unavailable'}),
            ):
                args = dict(application_id=156, generation_id='gen156', projects=projects, fit=fit,
                            baseline_report={}, raw_jd_text='Python', execution={}, decision={}, repo_root=root)
                render_automatic_bestof(st, **args)
                evaluate.assert_not_called()
                get_generation.assert_not_called()
                st.button.side_effect = lambda label, **_: label.startswith('Compare the existing')
                render_automatic_bestof(st, **args)
                evaluate.assert_called_once()
                self.assertEqual(evaluate.call_args.kwargs['source_docx'], source)
                self.assertEqual(evaluate.call_args.kwargs['optimizer'], build_certified_optimization)
                self.assertNotIn('guarded_floor_binding', evaluate.call_args.kwargs)
                get_generation.assert_called_once_with(156, 'gen156')

    def test_factual_review_reuses_displayed_slate_and_still_applies_selected_base_floor(self):
        with TemporaryDirectory() as temporary:
            root, projects, candidates, fit, source = fixture(temporary)
            base_bullet = 'Original Base bullet'
            proposal = {'requires_base_review': True, 'projects': [{
                'project': 'Example Project', 'after': [base_bullet], 'sources': [['Selected Base']],
            }]}
            result = {'status': 'needs_review', 'proposal': proposal, 'winner': 'existing_final'}
            generation = {'generation_id': 'gen156', 'fit_result': fit}
            st = MagicMock()
            # The manual existing-fit trial is V3.5-only; Main now defaults to V3.7.
            st.session_state = {'phase9f_bestof_next_mode_156': 'v35-relevance'}
            st.checkbox.return_value = True
            # B4 selects string project names and integer bullet indices.
            # An unconstrained MagicMock is neither kind of selected option.
            st.selectbox.side_effect = _selected_option
            st.radio.side_effect = _selected_option
            # Streamlit returns one container per requested column.
            st.columns.side_effect = lambda spec, **_: [MagicMock() for _ in range(spec if isinstance(spec,int) else len(spec))]
            st.expander.return_value = MagicMock()
            st.spinner.return_value = nullcontext()
            with (
                patch('tailoring.phase9f_project_bullet_sources_v2_3._bound_candidate_sources',
                      return_value=(candidates, '')),
                patch('database.tailoring_generation_control.get_tailoring_generation',
                      return_value=generation),
                patch('tailoring.phase9f_automatic_bestof_v30.evaluate_auto') as evaluate,
                patch('tailoring.phase9f_automatic_bestof_v30.verify_fitted_a_against_baselines',
                      return_value={'status': 'unavailable'}),
            ):
                args = dict(application_id=156, generation_id='gen156', projects=projects, fit=fit,
                            baseline_report={}, raw_jd_text='Python', execution={}, decision={}, repo_root=root)
                evaluate.return_value = result
                st.button.side_effect = lambda label, **_: label.startswith('Compare the existing')
                render_automatic_bestof(st, **args)
                evaluate.reset_mock()
                evaluate.return_value = {'status': 'verified', 'winner': 'optimized_candidate', 'proposal': proposal}
                st.button.side_effect = lambda label, **_: label.startswith('Re-run reviewed')
                render_automatic_bestof(st, **args)
                st.text.assert_any_call(f'Example Project · {base_bullet}')
                evaluate.assert_called_once()
                self.assertTrue(evaluate.call_args.kwargs['base_reviewed'])
                self.assertEqual(evaluate.call_args.kwargs['optimizer']({}, {}), proposal)
                receipt = next(value for key, value in st.session_state.items()
                               if key.startswith('phase9f_auto_bestof_receipt_'))
                self.assertEqual(receipt['winner'], 'existing_final')
                self.assertEqual(receipt['base_floor_verdict'], 'not_proven')

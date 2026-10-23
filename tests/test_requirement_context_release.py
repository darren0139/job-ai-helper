"""Prepared release: real application paths using synthetic/disposable inputs."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from analysis_stability import stable_evidence_scoring as native
from analysis_stability import requirement_context_policy as policy
from analysis_stability.coordinated_runtime import assert_analysis_publishable
from analysis_stability.requirement_presentation import assessment_label
from job_discovery import matching

CONTEXT_JD = ('Requirements:\nPublic Service Spirit: You care deeply about the public good and '
              'understand the responsibility of working on critical national infrastructure that impacts millions of lives daily')
CLAIM = 'Developed Java REST API endpoints for database operations.'
ITEMS = [{'id': 71, 'category': 'Project', 'title': 'Synthetic API service', 'bullets': [CLAIM]}]


def build(jd=CONTEXT_JD):
    return matching._default_stable_builder(raw_jd_text=jd, jd_profile={'job_title': 'Engineer'},
                                           context=matching.build_profile_evidence_context(ITEMS))


@patch.object(policy, 'PRODUCTION_ENABLED', False)
class RequirementContextReleaseTests(unittest.TestCase):
    # These are explicitly OFF -> release transition controls. Activated steady
    # state is exercised independently in test_requirement_context_activation.
    def test_disabled_production_switch_and_disposable_activation_simulation(self):
        self.assertFalse(policy.PRODUCTION_ENABLED)
        baseline = build()
        with patch.object(policy, 'PRODUCTION_ENABLED', True):
            released = build()
            self.assertEqual(released['scoring_version'], policy.RELEASE_SCORING_VERSION)
            self.assertEqual(matching.current_match_versions()['scoring_version'], policy.RELEASE_SCORING_VERSION)
            assert_analysis_publishable(released)
            with policy.requirement_context_correction():
                preview = build()
                self.assertEqual(preview['scoring_version'], policy.SCORING_IDENTITY)
                with self.assertRaises(ValueError):
                    assert_analysis_publishable(preview)
            from analysis_stability.coordinated_runtime import approved_alias_surface_preview, APPROVED_ALIAS_SCORER
            with approved_alias_surface_preview():
                isolated = build()
                self.assertEqual(isolated['scoring_version'], APPROVED_ALIAS_SCORER)
                self.assertNotIn('requirement_context_policy_version', isolated)
        self.assertFalse(policy.PRODUCTION_ENABLED)
        self.assertEqual(baseline, build())

    def test_full_phase8_verification_retains_null_after_reconciliation(self):
        from tailoring.phase8_verification import build_phase8_verification
        from tests.test_phase8_verification import GENERATION
        with policy.requirement_context_release():
            current = build()
            result = build_phase8_verification(baseline_report={'stable_analysis': current,
                'jd_profile': {'job_title': 'Engineer'}, 'resume_profile': {}, 'keyword_match': {}},
                generation_state=deepcopy(GENERATION), raw_jd_text=CONTEXT_JD)
        self.assertIsNone(result['after_stable_analysis']['deterministic_alignment_score'])
        self.assertIsNone(result['comparison']['score_delta'])
        self.assertEqual(result['verdict'], 'score_unavailable')
        self.assertFalse(result['approval_ready'])

    def test_release_identity_cache_fingerprint_and_default_rollback(self):
        from database.analysis_cache_manager import build_analysis_input_fingerprint
        args = dict(resume_text=CLAIM, jd_text=CONTEXT_JD, degree='', actual_page_count=1, model_id='synthetic')
        before = build(); old_cache = build_analysis_input_fingerprint(**args)
        with policy.requirement_context_release():
            current = build(); repeat = build()
            self.assertEqual(matching.current_match_versions()['scoring_version'], policy.RELEASE_SCORING_VERSION)
            self.assertEqual(current, repeat)
            self.assertEqual(current['scoring_version'], policy.RELEASE_SCORING_VERSION)
            self.assertEqual(current['base_scoring_version'], native.SCORING_VERSION)
            self.assertNotIn('preview_namespace', current)
            assert_analysis_publishable(current)
            new_cache = build_analysis_input_fingerprint(**args)
        self.assertNotEqual(old_cache, new_cache)
        self.assertNotEqual(before['input_fingerprint'], current['input_fingerprint'])
        self.assertEqual(old_cache, build_analysis_input_fingerprint(**args))
        self.assertEqual(before, build())
        self.assertEqual(matching.current_match_versions()['scoring_version'], native.SCORING_VERSION)

    def test_preview_stays_unpublishable_and_malformed_release_rejected(self):
        with policy.requirement_context_correction():
            preview = build()
        with self.assertRaises(ValueError):
            assert_analysis_publishable(preview)
        with policy.requirement_context_release():
            release = build()
        for field in ('base_scoring_version', 'requirement_context_policy_version', 'input_fingerprint'):
            bad = deepcopy(release); bad.pop(field)
            with self.subTest(field=field), self.assertRaises(ValueError):
                assert_analysis_publishable(bad)

    def test_unavailable_summary_ranking_and_breakdown_never_become_zero(self):
        from job_discovery.match_ranking import best_match_sort_key
        from tailoring.phase8_score_explainability import build_score_breakdown
        with policy.requirement_context_release():
            current = build(); summary = matching.summarize_stable_match(current)
        self.assertIsNone(summary['deterministic_alignment_score'])
        self.assertIsNone(summary['required_core_coverage_score'])
        self.assertFalse(summary['ranking_eligible'])
        self.assertEqual(summary['ranking_status'], 'unavailable')
        breakdown = build_score_breakdown(current)
        self.assertIsNone(breakdown['scorer_score'])
        self.assertIsNone(breakdown['reconstructed_score'])
        self.assertFalse(breakdown['score_available'])
        self.assertEqual(breakdown['components'], [])
        self.assertLess(best_match_sort_key({'summary': summary})[0], 2)

    def test_independent_synthetic_numeric_effect_and_supporting_behavior(self):
        context = matching.build_profile_evidence_context([
            {'id': 1, 'category': 'Skill', 'title': 'Python', 'skills': ['Python']}])
        jd = 'Requirements:\n- Experience with Python\n- Public Service Spirit'
        before = matching._default_stable_builder(raw_jd_text=jd, jd_profile={}, context=context)
        with policy.requirement_context_release():
            after = matching._default_stable_builder(raw_jd_text=jd, jd_profile={}, context=context)
        # Independent arithmetic: one DIRECT and one NONE core parent -> 50%
        # coverage * .9 + 100 evidence * .1 = 55; remove context -> 100.
        self.assertEqual(before['deterministic_alignment_score'], 55)
        self.assertEqual(after['deterministic_alignment_score'], 100)
        self.assertEqual(after['canonical_requirements'][0]['match_label'], 'direct')
        with policy.requirement_context_release():
            supporting = matching._default_stable_builder(raw_jd_text=jd.replace(
                'Public Service Spirit', 'Ability to learn quickly'), jd_profile={}, context=context)
        self.assertEqual(supporting['deterministic_alignment_score'], 100)
        self.assertEqual(supporting['supporting_requirement_count'], 1)

    def test_actual_30_jd_geometry_and_exact_affected_denominators(self):
        jobs = json.loads(Path('tests/fixtures/per_jd_scoring_audit.json').read_text(encoding='utf8'))['snapshot']['audit']['corpus']['jobs']
        changed = []
        for job in jobs:
            jd = job['frozen_inputs']['raw_jd_text']
            old = native.canonicalise_requirements({}, raw_jd_text=jd)['requirements']
            with policy.requirement_context_release():
                new = native.canonicalise_requirements({}, raw_jd_text=jd)['requirements']
            if len(old) != len(new):
                changed.append(job['job_id'])
                for rows, expected in ((old, 79), (new, 76)):
                    self.assertEqual(native._weighted_coverage(rows, {'core', 'required', 'deal_breaker'})[2], expected)
                by_id = {r['requirement_id']: r for r in old}
                for row in new:
                    prior = by_id[row['requirement_id']]
                    for key in ('importance', 'group_weight_fraction', 'source_provenance'):
                        self.assertEqual(prior[key], row[key])
        self.assertEqual(changed, [15, 158])

    def test_document_and_phase8_authorities_and_null_deltas(self):
        from tailoring.document_grounded_analysis import analyze_actual_resume_against_jd
        from tailoring.phase8_verification import build_current_baseline_analysis, compare_stable_analyses
        from tailoring.job_match_ab_analysis import build_job_match_snapshot, build_job_match_ab_analysis
        profile = {'projects': [{'title': 'Synthetic service', 'bullets': [CLAIM]}]}
        jd = 'Requirements:\nExperience developing REST APIs\nPublic Service Spirit'
        with policy.requirement_context_release():
            document = analyze_actual_resume_against_jd(resume_text='Unrelated document only.',
                jd_text=jd, jd_profile={}, resume_profile=profile)
            self.assertTrue(all(r['match_label'] == 'none' for r in document['stable_analysis']['canonical_requirements']))
            phase8 = build_current_baseline_analysis(baseline_report={'resume_profile': profile,
                'jd_profile': {}, 'keyword_match': {}}, raw_jd_text=jd)
            self.assertEqual(phase8['scoring_version'], policy.RELEASE_SCORING_VERSION)
            empty = build()
            comparison = compare_stable_analyses(empty, empty)
            self.assertIsNone(comparison['before_score'])
            self.assertIsNone(comparison['score_delta'])
            initial = build_job_match_snapshot(role='initial', stable_analysis=empty, raw_jd_text=CONTEXT_JD)
            final = build_job_match_snapshot(role='tailored', stable_analysis=empty, raw_jd_text=CONTEXT_JD)
            ab = build_job_match_ab_analysis(initial, final)
            self.assertIsNone(ab['summary']['initial_score'])
            self.assertIsNone(ab['summary']['score_delta'])

    def test_stale_document_is_retained_until_explicit_original_input_recompute(self):
        from tailoring.document_grounded_analysis import analyze_actual_resume_against_jd, validate_document_report
        from tailoring.jd_user_input_overrides import refresh_application_session_analysis_report
        old = analyze_actual_resume_against_jd(resume_text=CLAIM, jd_text=CONTEXT_JD,
                                               jd_profile={}, resume_profile={})
        old['meta'] = {'document_analysis': old.pop('document_analysis')}
        frozen = deepcopy(old)
        with policy.requirement_context_release():
            stale = refresh_application_session_analysis_report(old)
            self.assertTrue(stale['meta']['stable_analysis_currentness']['stale_requires_refresh'])
            self.assertEqual(stale['stable_analysis'], old['stable_analysis'])
            fresh = refresh_application_session_analysis_report(old, recompute_requirement_context=True)
            validate_document_report(fresh)
            self.assertIsNone(fresh['stable_analysis']['deterministic_alignment_score'])
            self.assertEqual(fresh['raw_resume_text'], old['raw_resume_text'])
            self.assertEqual(fresh['raw_jd_text'], old['raw_jd_text'])
            corrupt = deepcopy(old); corrupt['raw_resume_text'] = 'Changed original'
            with self.assertRaises(ValueError):
                refresh_application_session_analysis_report(corrupt, recompute_requirement_context=True)
        self.assertEqual(old, frozen)

    def test_explicit_document_phase8_recompute_keeps_archived_scores_separate(self):
        from docx import Document
        from tailoring.document_grounded_analysis import analyze_actual_resume_against_jd
        from tailoring.phase8_verification import build_phase8_verification
        from tests.test_phase8_verification import GENERATION
        old = analyze_actual_resume_against_jd(resume_text=CLAIM, jd_text=CONTEXT_JD,
                                               jd_profile={}, resume_profile={})
        old['meta'] = {'document_analysis': old.pop('document_analysis')}
        frozen = deepcopy(old)
        with tempfile.TemporaryDirectory() as scratch:
            path = Path(scratch) / 'synthetic-final.docx'
            doc = Document(); doc.add_paragraph('\n'.join([CLAIM] * 5)); doc.save(path)
            generation = deepcopy(GENERATION); generation['fit_result']['docx_path'] = str(path)
            with policy.requirement_context_release():
                with self.assertRaisesRegex(ValueError, 'Explicit original-input'):
                    build_phase8_verification(baseline_report=old, generation_state=generation, raw_jd_text=CONTEXT_JD)
                result = build_phase8_verification(baseline_report=old, generation_state=generation,
                    raw_jd_text=CONTEXT_JD, recompute_requirement_context=True)
            self.assertEqual(result['before_stable_analysis']['scoring_version'], policy.RELEASE_SCORING_VERSION)
            self.assertIsNone(result['comparison']['score_delta'])
            self.assertFalse(result['approval_ready'])
        self.assertEqual(old, frozen)

    def test_explicit_legacy_report_refresh_keeps_own_sources_and_overrides(self):
        from tailoring.jd_user_input_overrides import refresh_application_session_analysis_report, apply_application_session_jd_user_inputs
        jd = 'Requirements:\nExperience with Java\nPublic Service Spirit'
        old = {'stable_analysis': build(jd), 'raw_jd_text': jd,
               'raw_resume_text': CLAIM, 'resume_profile': {'skills': {'languages': ['Java']}},
               'jd_profile': {'job_title': 'Engineer'}}
        old = apply_application_session_jd_user_inputs(old, raw_jd_text=jd,
            raw_resume_text=CLAIM, preferred_requirements=['Experience with Java'])
        frozen = deepcopy(old)
        with policy.requirement_context_release():
            passive = refresh_application_session_analysis_report(old)
            self.assertFalse(passive['meta']['stable_analysis_currentness']['rebuilt'])
            explicit = refresh_application_session_analysis_report(old, recompute_requirement_context=True)
            self.assertEqual(explicit['stable_analysis']['scoring_version'], policy.RELEASE_SCORING_VERSION)
            self.assertEqual(explicit['resume_profile'], old['resume_profile'])
            self.assertEqual(explicit['meta']['jd_user_inputs']['preferred_requirement_overrides'],
                             old['meta']['jd_user_inputs']['preferred_requirement_overrides'])
            self.assertEqual(explicit['stable_analysis']['canonical_requirements'][0]['importance'], 'preferred')
            from tailoring.phase8_verification import build_phase8_verification
            from tests.test_phase8_verification import GENERATION
            missing = deepcopy(old); missing['resume_profile'] = {}
            with self.assertRaisesRegex(ValueError, 'evidence is unavailable'):
                build_phase8_verification(baseline_report=missing, generation_state=deepcopy(GENERATION),
                    raw_jd_text=jd, recompute_requirement_context=True)
        self.assertEqual(old, frozen)

    def test_null_phase8_cannot_automatically_approve(self):
        from tailoring.phase8_verification import refresh_phase8_readiness
        result = {'comparison_valid': True, 'comparison': {'score_delta': None}, 'claim_lineage': {}}
        refreshed = refresh_phase8_readiness(result, generation_state={'status': 'approved',
            'fit_result': {'fit_one_page': True, 'page_count': 1}})
        self.assertFalse(refreshed['approval_ready'])

    def test_assessment_categories_do_not_invent_hard_qualifications(self):
        with policy.requirement_context_release():
            rows = native.canonicalise_requirements({}, raw_jd_text='''Requirements:
Must communicate clearly during incidents
Ability to learn quickly
Preferred Skills:
Knowledge of Python
Responsibilities:
You will develop a traffic-control platform''')['requirements']
        self.assertEqual({assessment_label(r) for r in rows}, {
            'Mandatory applicant qualification', 'Supporting attribute',
            'Preferred qualification', 'Core role relevance / future responsibility'})


@patch.object(policy, 'PRODUCTION_ENABLED', False)
class RequirementContextPersistenceTests(unittest.TestCase):
    def test_context_only_document_persists_as_null_without_rebinding_archived_initial(self):
        from database import db_manager, analysis_cache_manager as cache
        from tailoring.document_grounded_analysis import analyze_actual_resume_against_jd
        from tailoring.initial_analysis_explainer import load_application_initial
        with tempfile.TemporaryDirectory() as scratch, patch.object(db_manager, 'DB_PATH', Path(scratch) / 'application.db'):
            db_manager.init_db(); cache.init_analysis_cache()
            app = db_manager.create_empty_application_session()
            old = analyze_actual_resume_against_jd(resume_text=CLAIM, jd_text=CONTEXT_JD,
                                                  jd_profile={}, resume_profile={})
            old['meta'] = {'document_analysis': old.pop('document_analysis')}
            saved = cache.persist_explicit_application_analysis(application_id=app, input_fingerprint='old',
                report=old, analysis_model='synthetic', resume_filename='synthetic.docx', raw_jd_text=CONTEXT_JD)
            with policy.requirement_context_release():
                fresh = analyze_actual_resume_against_jd(resume_text=CLAIM, jd_text=CONTEXT_JD,
                                                        jd_profile={}, resume_profile={})
                fresh['meta'] = {'document_analysis': fresh.pop('document_analysis')}
                current = cache.persist_explicit_application_analysis(application_id=app, input_fingerprint='new',
                    report=fresh, analysis_model='synthetic', resume_filename='synthetic.docx', raw_jd_text=CONTEXT_JD)
                self.assertNotEqual(saved['analysis_id'], current['analysis_id'])
                self.assertIsNone(current['report']['stable_analysis']['deterministic_alignment_score'])
                archived = load_application_initial(app, resume_only=True)
                self.assertEqual(archived['stable_analysis'], old['stable_analysis'])
                self.assertEqual(archived['currentness'], 'Stale historical analysis')
                # No source receipt, no admissible empty release analysis.
                bad = deepcopy(fresh['stable_analysis']); bad['canonicalisation_debug'] = {}
                with self.assertRaises(ValueError):
                    assert_analysis_publishable(bad)

    def test_job_finder_archive_currentness_cache_hit_recompute_and_rollback(self):
        from database import job_match_manager as manager
        with tempfile.TemporaryDirectory() as scratch, patch.object(manager, 'DB_PATH', Path(scratch) / 'jobs.db'):
            manager.init_job_match_schema()
            job = {'id': 42, 'content_hash': 'synthetic-jd', 'description': CONTEXT_JD}
            context = matching.build_profile_evidence_context(ITEMS)
            extractor = Mock(return_value={'job_title': 'Engineer'})
            old = matching.analyze_job_match(job, context=context, jd_profile_extractor=extractor)
            archived_versions = matching.current_match_versions()
            with policy.requirement_context_release():
                with self.assertRaisesRegex(ValueError, 'incompatible'):
                    matching.inspect_job_match(job, context=context, versions=archived_versions)
                stale = matching.inspect_job_match(job, context=context)
                self.assertEqual(stale['status'], 'stale')
                self.assertIn('stable scoring version changed', stale['stale_reasons'])
                fresh = matching.analyze_job_match(job, context=context, jd_profile_extractor=extractor)
                self.assertFalse(fresh['cache_hit'])
                self.assertIsNone(fresh['snapshot']['summary']['deterministic_alignment_score'])
                self.assertEqual(matching.inspect_job_matches([job], context=context)[42]['status'], 'current')
                hit = matching.analyze_job_match(job, context=context, jd_profile_extractor=extractor)
                self.assertTrue(hit['cache_hit'])
                self.assertEqual(hit['snapshot']['id'], fresh['snapshot']['id'])
            rollback = matching.inspect_job_match(job, context=context)
            self.assertEqual(rollback['status'], 'current')
            self.assertEqual(rollback['snapshot']['id'], old['snapshot']['id'])
            extractor.assert_called_once()


class RequirementContextStreamlitTests(unittest.TestCase):
    def test_existing_job_finder_initial_and_phase8_null_views(self):
        from streamlit.testing.v1 import AppTest
        # Resolve existing formatter dependencies before starting the AppTest
        # script timeout; importing the whole Job Finder controller is unrelated
        # to testing its shared passive metrics component.
        import tailoring.initial_analysis_explainer_ui
        import tailoring.unresolved_requirement_review_ui
        script = '''
import streamlit as st
from unittest.mock import patch
from tests.test_requirement_context_release import build, CONTEXT_JD
from analysis_stability.requirement_context_policy import requirement_context_release
from job_discovery.matching import summarize_stable_match
from analysis_stability.requirement_presentation import render_alignment_metrics
from tailoring.initial_analysis_explainer import build_analysis_receipt
from tailoring.initial_analysis_explainer_ui import render_analysis_receipt
from tailoring.phase8_score_explainability import build_score_breakdown
from tailoring.phase8_score_explainability_ui import _render_breakdown
with requirement_context_release():
    current = build()
    render_alignment_metrics(st, summarize_stable_match(current))
    receipt = build_analysis_receipt(current, raw_jd_text=CONTEXT_JD, provenance='SYNTHETIC')
    # The unrelated unresolved-review panel has its own tests. Exercise the real
    # analysis metrics, assessment table and context panel without loading it.
    with patch('tailoring.unresolved_requirement_review_ui.render_unresolved_requirement_review'):
        render_analysis_receipt(st, receipt, show_taxonomy=False)
    _render_breakdown('Phase 8', build_score_breakdown(current))
'''
        app = AppTest.from_string(script).run(timeout=90)
        self.assertFalse(app.exception)
        self.assertTrue(app.metric)
        self.assertTrue(all(m.value == 'Unavailable' for m in app.metric))
        self.assertIn('Phase 8: Unavailable', ' '.join(m.value for m in app.markdown))
        self.assertTrue(any('Assessment basis' in frame.value.columns
                            and 'Non-scored context' in frame.value['Assessment basis'].tolist()
                            for frame in app.dataframe))
        app.run(timeout=90)
        self.assertFalse(app.exception)

    def test_actual_phase8_result_does_not_display_numeric_null_comparison(self):
        from streamlit.testing.v1 import AppTest
        script = '''
from unittest.mock import patch
from tests.test_requirement_context_release import build
from analysis_stability.requirement_context_policy import requirement_context_release
from tailoring.phase8_verification import compare_stable_analyses
from tailoring.phase8_verification_ui import _render_result
with requirement_context_release():
    native = build()
    result = {'verdict':'score_unavailable', 'verdict_message':'Alignment unavailable',
              'comparison':compare_stable_analyses(native,native), 'comparison_valid':True,
              'after_stable_analysis':native, 'before_stable_analysis':native,
              'job_match_ab': {'comparable':False}, 'claim_lineage':{}}
    with patch('tailoring.phase8_verification_ui.render_phase8_score_explainability'):
        _render_result(result)
'''
        app = AppTest.from_string(script).run(timeout=90)
        self.assertFalse(app.exception)
        metrics = {m.label: m.value for m in app.metric}
        self.assertEqual(metrics['Before score'], 'Unavailable')
        self.assertEqual(metrics['After score'], 'Unavailable')
        self.assertEqual(metrics['Required/Core Δ'], 'Unavailable')


if __name__ == '__main__':
    unittest.main()

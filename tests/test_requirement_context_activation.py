"""Global ON application acceptance, independent of the incoming test mode.

Historical controls deliberately select OFF before constructing old receipts.
No test calls the request-local release context to simulate global activation.
"""
from contextlib import ExitStack
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from analysis_stability import requirement_context_policy as policy
from analysis_stability import stable_evidence_scoring as native
from analysis_stability.coordinated_runtime import assert_analysis_publishable
from analysis_stability.requirement_presentation import assessment_label, score_text
from job_discovery import matching
from tailoring.document_grounded_analysis import analyze_actual_resume_against_jd, validate_document_report
from tests.test_requirement_context_release import CLAIM, CONTEXT_JD, ITEMS

UI_STATE = {}


class OfflineModeBootstrapTests(unittest.TestCase):
    def test_requested_child_mode_is_in_force_and_overrides_were_restored(self):
        guard = os.environ.get('JOB_MATCH_TEST_GUARD_DIR')
        if guard:
            bootstrap = (Path(guard)/'sitecustomize.py').read_text(encoding='utf-8')
            for enabled in (False, True):
                if f'_context_policy.PRODUCTION_ENABLED = {enabled!r}' in bootstrap:
                    self.assertIs(policy.PRODUCTION_ENABLED, enabled)
        self.assertEqual(policy.current_scoring_version(),
            policy.RELEASE_SCORING_VERSION if policy.PRODUCTION_ENABLED else native.SCORING_VERSION)


def document(jd=CONTEXT_JD):
    result = analyze_actual_resume_against_jd(resume_text=CLAIM, jd_text=jd,
        jd_profile={}, resume_profile={'projects': [{'title': 'Synthetic API', 'bullets': [CLAIM]}]})
    result['meta'] = {'document_analysis': result.pop('document_analysis')}
    return result


def generation(path):
    from docx import Document
    from tests.test_phase8_verification import GENERATION
    doc = Document(); doc.add_paragraph(CLAIM * 5); doc.save(path)
    result = deepcopy(GENERATION)
    result['fit_result']['docx_path'] = str(path)
    return result


def ui_build(**kwargs):
    from tailoring.phase8_verification import build_phase8_verification
    UI_STATE['calls'].append(kwargs.get('recompute_requirement_context'))
    return build_phase8_verification(**kwargs)


def ui_save(**kwargs):
    result = deepcopy(kwargs['result'])
    assert_analysis_publishable(result['after_stable_analysis'])
    UI_STATE['saved'] = result
    return {**result, 'cache_status': 'new'}


class ActivatedApplicationTests(unittest.TestCase):
    def setUp(self):
        switch = patch.object(policy, 'PRODUCTION_ENABLED', True)
        switch.start(); self.addCleanup(switch.stop)
        self.assertTrue(policy.release_enabled())
        self.assertEqual(policy.current_scoring_version(), policy.RELEASE_SCORING_VERSION)

    def test_job_finder_fresh_persistence_cache_history_and_rollback(self):
        from database import job_match_manager as manager
        with tempfile.TemporaryDirectory() as folder, patch.object(manager, 'DB_PATH', Path(folder)/'jobs.db'):
            manager.init_job_match_schema()
            context = matching.build_profile_evidence_context(ITEMS)
            job = {'id': 42, 'content_hash': 'synthetic-original', 'description': CONTEXT_JD}
            extractor = Mock(return_value={'job_title': 'Synthetic Engineer'})
            with patch.object(policy, 'PRODUCTION_ENABLED', False):
                old = matching.analyze_job_match(job, context=context, jd_profile_extractor=extractor)
                old_versions = matching.current_match_versions()
            frozen = deepcopy(old['snapshot'])
            self.assertEqual(matching.inspect_job_match(job, context=context)['status'], 'stale')
            with self.assertRaisesRegex(ValueError, 'incompatible'):
                matching.inspect_job_match(job, context=context, versions=old_versions)
            fresh = matching.analyze_job_match(job, context=context, jd_profile_extractor=extractor)
            stable = fresh['snapshot']['stable_analysis']
            assert_analysis_publishable(stable)
            self.assertEqual(stable['scoring_version'], policy.RELEASE_SCORING_VERSION)
            self.assertIsNone(fresh['snapshot']['summary']['deterministic_alignment_score'])
            self.assertFalse(fresh['snapshot']['summary']['ranking_eligible'])
            hit = matching.analyze_job_match(job, context=context, jd_profile_extractor=extractor)
            self.assertTrue(hit['cache_hit'])
            self.assertEqual(hit['snapshot']['id'], fresh['snapshot']['id'])
            with patch.object(policy, 'PRODUCTION_ENABLED', False):
                rollback = matching.inspect_job_match(job, context=context)
                self.assertEqual(rollback['status'], 'current')
                self.assertEqual(rollback['snapshot'], frozen)
            self.assertEqual(matching.inspect_job_match(job, context=context)['snapshot']['id'], fresh['snapshot']['id'])
            extractor.assert_called_once()

    def test_initial_explicit_original_document_recompute_and_archived_read(self):
        from database import db_manager, analysis_cache_manager as cache
        from tailoring.initial_analysis_explainer import load_application_initial
        from tailoring.jd_user_input_overrides import refresh_application_session_analysis_report
        with tempfile.TemporaryDirectory() as folder, patch.object(db_manager, 'DB_PATH', Path(folder)/'apps.db'):
            db_manager.init_db(); cache.init_analysis_cache()
            app = db_manager.create_empty_application_session()
            with patch.object(policy, 'PRODUCTION_ENABLED', False):
                old = document()
                cache.persist_explicit_application_analysis(application_id=app, input_fingerprint='old',
                    report=old, analysis_model='synthetic', resume_filename='synthetic.docx', raw_jd_text=CONTEXT_JD)
            frozen = deepcopy(old); before = Path(db_manager.DB_PATH).read_bytes()
            passive = refresh_application_session_analysis_report(old)
            self.assertEqual(passive['stable_analysis'], old['stable_analysis'])
            self.assertTrue(passive['meta']['stable_analysis_currentness']['stale_requires_refresh'])
            fresh = refresh_application_session_analysis_report(old, recompute_requirement_context=True)
            validate_document_report(fresh)
            self.assertEqual(fresh['stable_analysis']['scoring_version'], policy.RELEASE_SCORING_VERSION)
            self.assertIsNone(fresh['stable_analysis']['deterministic_alignment_score'])
            self.assertEqual(fresh['raw_resume_text'], old['raw_resume_text'])
            self.assertEqual(fresh['raw_jd_text'], old['raw_jd_text'])
            self.assertEqual(old, frozen)
            self.assertEqual(Path(db_manager.DB_PATH).read_bytes(), before)
            cache.persist_explicit_application_analysis(application_id=app, input_fingerprint='new',
                report=fresh, analysis_model='synthetic', resume_filename='synthetic.docx', raw_jd_text=CONTEXT_JD)
            archived = load_application_initial(app, resume_only=True)
            self.assertEqual(archived['stable_analysis'], frozen['stable_analysis'])
            self.assertEqual(archived['currentness'], 'Stale historical analysis')
            corrupt = deepcopy(old); corrupt['raw_resume_text'] = 'Changed original'
            with self.assertRaises(ValueError):
                refresh_application_session_analysis_report(corrupt, recompute_requirement_context=True)

    def test_phase8_automatic_block_explicit_document_transition_and_null(self):
        from tailoring.phase8_verification import build_phase8_verification
        with patch.object(policy, 'PRODUCTION_ENABLED', False): old = document()
        frozen = deepcopy(old)
        with tempfile.TemporaryDirectory() as folder:
            final = generation(Path(folder)/'final.docx')
            with self.assertRaisesRegex(ValueError, 'Explicit original-input'):
                build_phase8_verification(baseline_report=old, generation_state=final, raw_jd_text=CONTEXT_JD)
            result = build_phase8_verification(baseline_report=old, generation_state=final,
                raw_jd_text=CONTEXT_JD, recompute_requirement_context=True)
            self.assertEqual(result['before_stable_analysis']['scoring_version'], policy.RELEASE_SCORING_VERSION)
            self.assertEqual(result['after_stable_analysis']['scoring_version'], policy.RELEASE_SCORING_VERSION)
            self.assertIsNone(result['comparison']['score_delta'])
            self.assertIsNone(result['comparison']['after_score'])
            self.assertEqual(result['verdict'], 'score_unavailable')
            self.assertFalse(result['approval_ready'])
            assert_analysis_publishable(result['after_stable_analysis'])
        self.assertEqual(old, frozen)

    def test_fresh_phase9c_workflow_and_historical_blueprint_rejection(self):
        from tests.phase9c_fixture_support import load_current_phase9c_fixture, load_historical_phase9c_fixture
        from tailoring.phase9c_blueprint_evaluation import evaluate_blueprint_candidate, validate_candidate, Phase9CEvaluationError
        from tailoring.phase9e_blueprint_selection import validate_active_blueprint, Phase9EDecisionError
        from tests.phase9e_test_support import seed_phase9e_database
        from database import db_manager, jd_library_manager, tailoring_version_manager, global_blueprint_manager
        import database.phase9f_exact_verified_reuse_manager as reuse
        with patch.object(policy, 'PRODUCTION_ENABLED', False):
            old = load_current_phase9c_fixture()
        with self.assertRaisesRegex(Phase9CEvaluationError, 'scoring version'):
            validate_candidate(old['candidate'])
        fresh = load_current_phase9c_fixture()
        result = evaluate_blueprint_candidate(candidate=fresh['candidate'], selected_jds=[fresh['saved_jds'][1]],
            saved_jds_for_source_resolution=fresh['saved_jds'])
        self.assertEqual(result['candidate_scope']['scoring_version'], policy.RELEASE_SCORING_VERSION)
        # Exercise real disposable candidate evaluation/approval/selection seeding;
        # fixtures are synthetic, never production publication receipts.
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            for module, attr in ((db_manager, 'DB_PATH'), (jd_library_manager, 'DB_PATH'),
                    (tailoring_version_manager, 'DB_PATH'), (global_blueprint_manager, 'BLUEPRINT_ARTIFACT_ROOT'),
                    (reuse, 'BLUEPRINT_ARTIFACT_ROOT')):
                stack.enter_context(patch.object(module, attr, getattr(module, attr)))
            with patch.object(policy, 'PRODUCTION_ENABLED', False):
                historical = seed_phase9e_database(Path(folder)/'old.db')['blueprint']
            with self.assertRaisesRegex(Phase9EDecisionError, 'scorer provenance'):
                validate_active_blueprint(historical)
            current = seed_phase9e_database(Path(folder)/'current.db')['blueprint']
            self.assertEqual(validate_active_blueprint(current), current)
        self.assertNotEqual(load_historical_phase9c_fixture()['candidate']['evaluation_metadata']['source_scoring_version'],
                            policy.RELEASE_SCORING_VERSION)

    def test_enabled_corpus_and_mandatory_supporting_role_boundaries(self):
        jobs = json.loads(Path('tests/fixtures/per_jd_scoring_audit.json').read_text(encoding='utf-8'))['snapshot']['audit']['corpus']['jobs']
        removed = set(); old_count = new_count = 0
        for job in jobs:
            raw = job['frozen_inputs']['raw_jd_text']
            with patch.object(policy, 'PRODUCTION_ENABLED', False): before = native.canonicalise_requirements({}, raw_jd_text=raw)['requirements']
            after = native.canonicalise_requirements({}, raw_jd_text=raw)['requirements']
            old_count += len(before); new_count += len(after)
            removed.update((job['job_id'], rid) for rid in {r['requirement_id'] for r in before}-{r['requirement_id'] for r in after})
            by_id = {r['requirement_id']: r for r in before}
            for row in after:
                for key in ('importance', 'source_provenance', 'group_weight_fraction'):
                    self.assertEqual(row[key], by_id[row['requirement_id']][key])
        self.assertEqual((len(jobs), old_count, new_count), (30, 716, 714))
        self.assertEqual(removed, {(15, 'req_7b667a24f1e0'), (158, 'req_0c34f8e720fe')})
        rows = native.canonicalise_requirements({}, raw_jd_text='Requirements:\nMust use Python\nAbility to learn quickly\nResponsibilities:\nYou will develop a traffic-control platform')['requirements']
        self.assertEqual({assessment_label(r) for r in rows}, {'Mandatory applicant qualification',
            'Supporting attribute', 'Core role relevance / future responsibility'})
        self.assertEqual(score_text(None), 'Unavailable')

    def test_phase8_ui_requires_click_and_never_rescores_on_rerender(self):
        from streamlit.testing.v1 import AppTest
        import tailoring.phase8_verification_ui
        with patch.object(policy, 'PRODUCTION_ENABLED', False): old = document()
        with tempfile.TemporaryDirectory() as folder:
            UI_STATE.update(baseline=old, generation=generation(Path(folder)/'final.docx'), calls=[], saved=None)
            self.addCleanup(UI_STATE.clear)
            script = '''
from unittest.mock import patch
from contextlib import ExitStack
from tests import test_requirement_context_activation as f
from tailoring import phase8_verification_ui as ui
with ExitStack() as stack:
    for name, value in {'list_tailoring_generations':lambda _: [f.UI_STATE['generation']],
        'get_application_generation_control':lambda _: {},
        'get_latest_tailoring_verification':lambda *args: f.UI_STATE['saved'],
        'build_phase8_verification':f.ui_build, 'save_tailoring_verification':f.ui_save}.items():
        stack.enter_context(patch.object(ui,name,value))
    ui.render_phase8_verification(application_id=1, baseline_report=f.UI_STATE['baseline'],
        raw_jd_text=f.UI_STATE['baseline']['raw_jd_text'])
'''
            app = AppTest.from_string(script).run(timeout=90)
            self.assertFalse(app.exception)
            self.assertEqual(UI_STATE['calls'], [])
            button = next(b for b in app.button if b.label == 'Re-run Phase 8 verification')
            button.click().run(timeout=90)
            self.assertFalse(app.exception)
            self.assertEqual(UI_STATE['calls'], [True])
            self.assertEqual(UI_STATE['saved']['after_stable_analysis']['scoring_version'], policy.RELEASE_SCORING_VERSION)
            app.run(timeout=90)
            self.assertFalse(app.exception)
            self.assertEqual(UI_STATE['calls'], [True])
            self.assertEqual(UI_STATE['baseline'], old)
            self.assertTrue(any(m.value == 'Unavailable' for m in app.metric))

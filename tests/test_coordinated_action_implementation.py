"""Production-entry gated acceptance; independent fixture expectations stay immutable."""
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
import uuid
from unittest.mock import patch

from analysis_stability import stable_evidence_scoring as n
from analysis_stability.coordinated_integration import IDENTITIES
from analysis_stability.coordinated_runtime import CONTEXT, assert_analysis_publishable
from scripts import coordinated_acceptance as acceptance


@lru_cache(maxsize=None)
def run(family, scenario):
    parent = next(p for p in acceptance.parents() if p['obligation']['object_family'] == family)
    return acceptance.comparison(parent, scenario)


class CoordinatedImplementationTests(unittest.TestCase):
    def row(self, scenario, family='embedded'):
        return run(family, scenario)['after_rows'][0]

    def test_parser_preserves_all_five_parents_and_source_allocation(self):
        self.assertEqual(len(acceptance.parents()), 5)
        for parent in acceptance.parents():
            result = run(parent['obligation']['object_family'], 'All mandatory actions')
            self.assertEqual(len(result['before_rows']), 2)
            self.assertEqual(len(result['after_rows']), 1)
            self.assertEqual(sum(r['group_weight_fraction'] for r in result['before_rows']), 1)
            row = result['after_rows'][0]
            self.assertEqual(row['group_weight_fraction'], 1)
            self.assertEqual(row['requirement_id'], parent['requirement']['requirement_id'])
            self.assertEqual(row['source_provenance'], parent['requirement']['source_provenance'])
            o = row['coordinated_action_receipt']['obligation']
            self.assertEqual(parent['raw_jd'][slice(*o['raw_jd_parent_span'])], parent['original_raw_parent'])
            for action in o['actions']:
                self.assertEqual(parent['raw_jd'][slice(*action['raw_jd_span'])], action['original_action'])

    def test_maintenance_review_withholds_every_aggregate(self):
        result = run('embedded', 'Maintenance only')
        row = result['after_rows'][0]
        self.assertEqual(row['coordinated_action_receipt']['native_label'], 'direct')
        self.assertIsNone(row['match_label'])
        self.assertIsNone(row['match_value'])
        self.assertEqual(row['coordinated_action_receipt']['disposition'], 'REVIEW_REQUIRED')
        for key in ('deterministic_alignment_score', 'required_core_coverage_score',
                    'preferred_coverage_score', 'evidence_strength_score'):
            self.assertIsNone(result['after'][key])
        with self.assertRaisesRegex(ValueError, 'withheld'):
            n._weighted_coverage(result['after']['canonical_requirements'], {'core'})

    def test_p3_ceiling_and_every_late_stage(self):
        row = self.row('Design and development')
        self.assertEqual(row['match_label'], 'weak')
        self.assertEqual(row['match_value'], n.MATCH_VALUES['weak'])
        receipt = row['coordinated_action_receipt']
        self.assertEqual(receipt['synthetic_parent_contribution'], .20)
        self.assertTrue(all(s['capped_label'] not in ('direct', 'transferable') for s in receipt['stages']))
        self.assertEqual(receipt['stages'][-1]['stage'], 'post_recovery_invariant')

    def test_complete_active_passive_relative_keep_native_ceiling(self):
        for scenario in ('All mandatory actions', 'Passive first-person ownership', 'Relative-clause ownership'):
            row = self.row(scenario)
            self.assertEqual(row['match_label'], 'direct')
            self.assertEqual(row['coordinated_action_receipt']['disposition'], 'COMPLETE')

    def test_technical_scope_is_not_a_partial_credit_shortcut(self):
        row = self.row('Shortened object')
        self.assertIsNone(row['match_label'])
        proofs = row['coordinated_action_receipt']['proofs'].values()
        proof = next(p['proof'] for p in proofs if p['proof']['supported_actions'])
        self.assertEqual(len(proof['supported_actions']), 3)
        self.assertEqual(proof['technical_scope'], 'UNPROVEN')

    def test_fullstack_none_is_not_upgraded(self):
        row = self.row('Design and development', 'fullstack')
        self.assertEqual(row['coordinated_action_receipt']['native_label'], 'none')
        self.assertEqual(row['match_label'], 'none')
        self.assertIsNotNone(run('fullstack', 'Design and development')['after']['deterministic_alignment_score'])

    def test_cloud_denial_and_separate_records_use_deployment_not_maintenance(self):
        row = self.row('Denied lifecycle', 'cloud')
        self.assertIsNone(row['match_label'])
        proof = next(p['proof'] for p in row['coordinated_action_receipt']['proofs'].values()
                     if p['proof']['supported_actions'])
        self.assertIn('deploy', proof['denied_actions'])
        separate = self.row('Separate partial records', 'cloud')
        self.assertIsNone(separate['match_label'])
        proofs = separate['coordinated_action_receipt']['proofs'].values()
        self.assertTrue(any('deploy' in p['proof']['supported_actions'] for p in proofs))

    def test_complete_second_source_wins_without_bullet_union(self):
        row = self.row('Complete alternative second bullet')
        self.assertEqual(row['match_label'], 'direct')
        self.assertEqual(len(row['evidence']), 1)
        self.assertEqual(row['evidence'][0]['source'], 'resume_profile.projects[0].bullets[1]')
        for scenario in ('Separate partial records', 'Denied lifecycle'):
            self.assertIsNone(self.row(scenario)['match_label'])

    def test_topic_recovery_and_consumption_cannot_restore_credit(self):
        for scenario in ('Zero-overlap topic recovery', 'API consumption', 'PostgREST integration'):
            # Native-positive embedded topic recovery remains quarantined. Only
            # independently excluded packets with native NONE now become zero.
            embedded = self.row(scenario)
            if scenario == 'Zero-overlap topic recovery':
                self.assertIsNone(embedded['match_label'])
            else:
                self.assertEqual(embedded['match_label'], 'none')
                self.assertEqual(embedded['match_value'], 0)
            backend = self.row(scenario, 'backend')
            self.assertEqual(backend['match_label'], 'none')
            self.assertEqual(backend['coordinated_action_receipt']['disposition'], 'R1_EXCLUDED_NATIVE_NONE')

    def test_source_and_cap_invariants_across_five_acceptance_parents(self):
        for parent in acceptance.parents():
            for scenario in acceptance.scenarios(parent):
                result = run(parent['obligation']['object_family'], scenario)
                for row in result['after_rows']:
                    receipt = row['coordinated_action_receipt']
                    self.assertEqual(receipt['parent_allocation'], 1)
                    if row['match_label'] in ('direct', 'transferable'):
                        self.assertEqual(receipt['disposition'], 'COMPLETE')
                    for record in row['evidence']:
                        original = receipt['proofs'][record['evidence_id']]['record']
                        for key in ('source', 'evidence_id', 'text', 'section'):
                            self.assertEqual(record[key], original[key])
                    if receipt['disposition'] == 'REVIEW_REQUIRED':
                        self.assertIsNone(result['after']['deterministic_alignment_score'])

    def test_context_cleanup_determinism_and_prospective_identity(self):
        parent = acceptance.parents()[1]
        evidence = acceptance.scenarios(parent)['Design and development']
        before = acceptance.analyze(parent, evidence, False)
        after = acceptance.analyze(parent, evidence, True)
        self.assertEqual(after, acceptance.analyze(parent, evidence, True))
        self.assertEqual(before, acceptance.analyze(parent, evidence, False))
        self.assertIsNone(CONTEXT.get())
        self.assertEqual(before['scoring_version'], n.SCORING_VERSION)
        self.assertEqual(after['scoring_version'], IDENTITIES['scoring_version'])
        self.assertNotEqual(before['input_fingerprint'], after['input_fingerprint'])
        self.assertNotEqual(before['scoring_version'], after['scoring_version'])
        self.assertEqual(json.loads(json.dumps(before)), before)  # old snapshot is still readable
        for result in (after, run('embedded', 'Maintenance only')['after']):
            with self.assertRaisesRegex(ValueError, 'cannot be persisted'):
                assert_analysis_publishable(result)

    def test_persistence_rejects_preview_before_opening_database(self):
        from database import job_match_manager as matches, analysis_cache_manager as cache
        after = run('embedded', 'All mandatory actions')['after']
        with patch.object(matches, 'init_job_match_schema') as schema:
            with self.assertRaisesRegex(ValueError, 'cannot be persisted'):
                matches.save_job_match_snapshot(discovered_job_id=1, job_content_hash='synthetic',
                    evidence_fingerprint='synthetic', match_version='synthetic',
                    scoring_version=after['scoring_version'], taxonomy_version=after['capability_taxonomy_version'],
                    jd_profile={}, evidence_snapshot=[], stable_analysis=after, summary={})
            schema.assert_not_called()

        with patch.object(cache, 'init_analysis_cache') as schema:
            with self.assertRaisesRegex(ValueError, 'cannot be persisted'):
                cache.save_analysis_snapshot(application_id=1, input_fingerprint='synthetic',
                    report={'stable_analysis': after}, analysis_model='offline')
            schema.assert_not_called()
            with self.assertRaisesRegex(ValueError, 'cannot be persisted'):
                cache.persist_explicit_application_analysis(application_id=1, input_fingerprint='synthetic',
                    report={'raw_jd_text': 'synthetic', 'stable_analysis': after},
                    analysis_model='offline', resume_filename='synthetic', raw_jd_text='synthetic')
            schema.assert_not_called()

    def test_independent_stage2d_fixture_and_source_forgery(self):
        from analysis_stability import coordinated_policy as policy
        fixture = json.loads((acceptance.ROOT/'tests/fixtures/coordinated_partial_action_policy_v1.json').read_text(encoding='utf-8'))
        for case in fixture['cases']:
            parent = next(p for p in acceptance.parents() if p['obligation']['object_family'] == case.get('family', 'embedded'))
            index = n.build_resume_evidence_index({'projects': [{'bullets': [case['text']]}]}, '')
            record = next(r for r in index if '.bullets[' in r['source'])
            proof = policy.detect(parent['obligation'], record, index)
            self.assertEqual(proof['supported_actions'], sorted(case['owned']))
            self.assertEqual(proof['technical_scope'], case['technical'])
            self.assertEqual(policy.eligibility(parent['obligation'], proof, 'P3'), case['policies'][2])
            for field in ('source', 'evidence_id', 'text'):
                forged = {**record, field: 'FORGED'}
                self.assertEqual(policy.detect(parent['obligation'], forged, index)['status'], 'UNVERIFIED_SOURCE')

    def test_unsupported_boolean_is_review_and_api_authorship_stays_independent(self):
        raw = 'Responsibilities:\nDesign, develop and maintain embedded software modules or backend services.'
        evidence = 'Designed, developed and maintained embedded software modules or backend services.'
        parent = {'raw_jd': raw}
        result = acceptance.analyze(parent, [evidence], True)
        self.assertIsNone(result['deterministic_alignment_score'])
        self.assertTrue(all(r['match_label'] is None for r in result['canonical_requirements']))
        parent = next(p for p in acceptance.parents() if p['obligation']['object_family'] == 'backend')
        text = ('Designed and built '+parent['obligation']['object']+'. '
                'Designed REST API interfaces and implemented REST API endpoints in Java.')
        result = acceptance.analyze(parent, [text], True)
        row = next(r for r in result['canonical_requirements'] if
                   r.get('scoring_parent_occurrence_id') == parent['parent_occurrence_id'])
        self.assertEqual(row['match_label'], 'weak')
        proof = next(p['proof'] for p in row['coordinated_action_receipt']['proofs'].values()
                     if p['proof'].get('supported_actions'))
        self.assertIn(proof['independent_api_guard']['label'], ('weak', 'direct'))

    def test_unsupported_artifact_is_quarantined_and_api_guard_is_a_ceiling(self):
        from analysis_stability.coordinated_integration import _evaluate_row
        raw = 'Responsibilities:\nDesign, develop and maintain firmware components.'
        result = acceptance.analyze({'raw_jd': raw}, ['Designed, developed and maintained firmware components.'], True)
        self.assertIsNone(result['deterministic_alignment_score'])
        self.assertTrue(all(r['match_label'] is None for r in result['canonical_requirements']))
        parent = next(p for p in acceptance.parents() if p['obligation']['object_family'] == 'embedded')
        text = acceptance.scenarios(parent)['All mandatory actions'][0]
        profile = {'projects': [{'bullets': [text]}]}
        index = n.build_resume_evidence_index(profile, '')
        record = next(r for r in index if '.bullets[' in r['source'])
        # Independent lower API ceiling must bind even when the lexical native
        # evaluator itself does not recognize API design obligations.
        proofs = {record['evidence_id']: {'record': record, 'admission': 'COMPLETE',
                   'proof': {'independent_api_guard': {'label': 'weak'}}}}
        row, stages, _, _ = _evaluate_row(parent['requirement'], proofs, set(proofs), 'direct', profile, '', {})
        self.assertEqual(row['match_label'], 'weak')
        self.assertTrue(all(s['capped_label'] not in ('direct', 'transferable') for s in stages))

    def test_profile_only_parent_cannot_bypass_exact_raw_grounding(self):
        result = n.build_stable_analysis(jd_profile={'responsibilities': [
            'Design, develop and maintain embedded software modules.']}, keyword_match={},
            resume_profile={'projects': [{'bullets': [
                'Designed, developed and maintained embedded software modules.']}]},
            raw_jd_text='', coordinated_actions_enabled=True, retrieval_mode_override='off')
        self.assertTrue(result['canonical_requirements'])
        self.assertIsNone(result['deterministic_alignment_score'])
        self.assertTrue(all(r['match_label'] is None for r in result['canonical_requirements']))

    def test_gate_off_matches_hash_pinned_historical_native_on_30_jobs(self):
        # Keep the original oracle and its source pins immutable. Execute the
        # independently hash-verified committed baseline, not a regenerated oracle.
        fixture = json.loads((acceptance.ROOT/'tests/fixtures/coordinated_action_ownership_oracle_v1.json').read_text(encoding='utf-8'))
        source = subprocess.check_output(['git', 'show', '3e6ff34501b4d68cbe3e66b55ec8af5b0e288026:analysis_stability/stable_evidence_scoring.py'], cwd=acceptance.ROOT)
        self.assertEqual(hashlib.sha256(source.replace(b'\r\n', b'\n')).hexdigest(),
                         fixture['production_source_lf_sha256']['analysis_stability/stable_evidence_scoring.py'])
        historical = types.ModuleType('analysis_stability.historical_stage2d')
        historical.__package__ = 'analysis_stability'
        historical.__file__ = str(acceptance.ROOT/'analysis_stability/stable_evidence_scoring.py')
        exec(compile(source, historical.__file__, 'exec'), historical.__dict__)
        corpus = json.loads((acceptance.ROOT/'tests/fixtures/per_jd_scoring_audit.json').read_text(encoding='utf-8'))
        for job in corpus['snapshot']['audit']['corpus']['jobs']:
            raw = job['frozen_inputs']['raw_jd_text']
            kwargs = dict(jd_profile={}, keyword_match={}, raw_jd_text=raw,
                          resume_profile={}, retrieval_mode_override='off')
            self.assertEqual(n.build_stable_analysis(**kwargs), historical.build_stable_analysis(**kwargs))

    def test_disposable_historical_snapshot_readability_and_version_currentness(self):
        from database import job_match_manager as matches
        # mkdtemp's private 0700 ACL is inaccessible under this Windows sandbox.
        # Inherit the already-isolated runner scratch ACL instead.
        folder = Path(tempfile.gettempdir())/('stage2e-history-'+uuid.uuid4().hex)
        folder.mkdir()
        path = folder/'snapshots.sqlite3'
        historical = run('embedded', 'All mandatory actions')['before']
        lookup = dict(discovered_job_id=1, job_content_hash='synthetic', evidence_fingerprint='synthetic',
                      match_version='synthetic-contract', scoring_version=n.SCORING_VERSION,
                      taxonomy_version=historical['capability_taxonomy_version'], db_path=path)
        saved = matches.save_job_match_snapshot(**lookup, jd_profile={}, evidence_snapshot=[],
                                               stable_analysis=historical, summary={})
        self.assertEqual(saved['stable_analysis'], historical)
        old_bytes = path.read_bytes()
        self.assertEqual(matches.get_latest_job_match_snapshot(1, db_path=path, read_only=True)['stable_analysis'], historical)
        self.assertIsNone(matches.get_job_match_snapshot(**{**lookup, 'scoring_version': IDENTITIES['scoring_version']}))
        self.assertEqual(matches.get_job_match_snapshot(**lookup)['stable_analysis'], historical)
        self.assertEqual(path.read_bytes(), old_bytes)


class CoordinatedStreamlitTests(unittest.TestCase):
    def test_actual_page_off_then_review_then_weak_then_complete(self):
        # AppTest only uses this module-level directory's .name. Retain it with
        # the runner scratch, using inherited ACLs instead of Windows private-ACL
        # mkdtemp; all actual page execution and assertions remain native.
        folder = Path(tempfile.gettempdir())/('stage2e-streamlit-'+uuid.uuid4().hex)
        folder.mkdir()
        with patch('tempfile.TemporaryDirectory', return_value=types.SimpleNamespace(name=str(folder))):
            from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(str(acceptance.ROOT/'coordinated_actions_preview.py'), default_timeout=30).run()
        self.assertFalse(app.exception)
        self.assertFalse(app.toggle[0].value)
        app.selectbox[0].select('359 — embedded').run()
        app.toggle[0].set_value(True).run()
        self.assertFalse(app.exception)
        self.assertTrue(any('Score withheld' in r.value for r in app.warning))
        app.selectbox[1].select('Design and development').run()
        self.assertFalse(app.exception)
        self.assertTrue(app.success)
        self.assertTrue(any('weak' in r.value for r in app.json))
        app.selectbox[1].select('Passive first-person ownership').run()
        self.assertFalse(app.exception)
        self.assertTrue(app.metric)

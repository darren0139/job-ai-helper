"""Fresh current evaluation of synthetic historical inputs, not v1.16 replay."""
from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from job_discovery import developer_real_comparison as real, coordinated_preview as preview
from job_discovery.matching import fingerprint_evidence_items
from tailoring.phase9e_blueprint_selection import fingerprint_value
from tests import test_frozen_handoff_compatibility as support
from tests.test_developer_comparison import page_test


class RetrospectiveTests(unittest.TestCase):
    setUpClass = classmethod(support.FrozenCompatibilityTests.setUpClass.__func__)
    sql = support.FrozenCompatibilityTests.sql
    load_binding = support.FrozenCompatibilityTests.load_binding
    initial_report = support.FrozenCompatibilityTests.initial_report
    legacy_generation = support.FrozenCompatibilityTests.legacy_generation

    def setUp(self):
        support.FrozenCompatibilityTests.setUp(self)
        self.original = self.legacy_generation()

    def load(self):
        return real.load_retrospective(self.app_id, session_enabled=True)

    def rewrite(self, binding, report):
        """Deliberate synthetic corruption with consistent cross-row seals."""
        source = binding['snapshot']
        binding['binding_fingerprint'] = fingerprint_value({k:v for k,v in binding.items() if k!='binding_fingerprint'})
        report['meta']['initial_analysis_reference'] = deepcopy(binding)
        self.sql('UPDATE job_match_snapshots SET evidence_snapshot_json=?,evidence_fingerprint=?,jd_profile_json=?,stable_analysis_json=?,scoring_version=?,taxonomy_version=?',
            (json.dumps(source['evidence_snapshot']), source['evidence_fingerprint'], json.dumps(source['jd_profile']),
             json.dumps(source['stable_analysis']), source['scoring_version'], source['taxonomy_version']))
        self.sql('UPDATE applications SET entry_binding_json=?', (json.dumps(binding),))
        self.sql('UPDATE application_analysis_versions SET report_json=?,input_fingerprint=?',
                 (json.dumps(report), binding['binding_fingerprint']))

    def test_strict_admission_is_still_stale(self):
        with self.assertRaisesRegex(real.Blocked, 'STALE: saved match/scorer/taxonomy'):
            real.load(self.app_id, session_enabled=True)

    def test_frozen_packet_becomes_new_raw_parser_request_not_old_labels(self):
        before = self.path.read_bytes()
        loaded = self.load()
        self.assertEqual(loaded['mode'], real.RETROSPECTIVE)
        self.assertEqual(loaded['request'].jd_profile, {})
        self.assertEqual(loaded['request'].projection['evidence_items'], self.inputs['evidence_items'])
        self.assertEqual(loaded['saved']['stable_analysis'], self.original['stable_analysis'])
        self.assertEqual(loaded['saved']['versions']['scoring_version'], 'stable-evidence-v1.16-phase6d20')
        self.assertEqual(loaded['context']['versions']['scoring_version'], preview.native.SCORING_VERSION)
        self.assertEqual(self.path.read_bytes(), before)

    def test_legacy_extraction_identity_is_not_promoted_into_fresh_profile(self):
        b = self.load_binding(); report = self.initial_report()
        b['snapshot']['jd_profile']['archived_capability_identity'] = 'LEGACY_ONLY_SENTINEL'
        report['jd_profile'] = deepcopy(b['snapshot']['jd_profile'])
        self.rewrite(b, report)
        loaded = self.load()
        self.assertEqual(loaded['request'].jd_profile, {})
        self.assertNotIn('LEGACY_ONLY_SENTINEL', str(loaded['request']))

    def test_current_report_and_overrides_not_used_or_cleared(self):
        current = deepcopy(self.original)
        current['raw_resume_text'] = 'PRIVATE_CURRENT_RESUME_SENTINEL'
        current['meta']['jd_user_inputs'] = {'preferred_requirement_overrides':['PRIVATE_OVERRIDE_SENTINEL']}
        self.sql('UPDATE applications SET report_json=?', (json.dumps(current),))
        before = self.path.read_bytes()
        loaded = self.load()
        self.assertTrue(loaded['context']['current_application_report_differs'])
        self.assertNotIn('PRIVATE_CURRENT_RESUME_SENTINEL', str(loaded['request']))
        self.assertNotIn('PRIVATE_OVERRIDE_SENTINEL', str(loaded['request']))
        self.assertEqual(self.path.read_bytes(), before)

    def test_current_geometry_changes_are_specific_blockers(self):
        rows = preview.native.canonicalise_requirements({}, raw_jd_text=self.inputs['raw_jd_text'])
        for field, value in [('requirement_id','other'), ('group_weight_fraction',.123), ('importance','preferred')]:
            changed = deepcopy(rows); changed['requirements'][0][field] = value
            with self.subTest(field=field), patch.object(preview.native,'canonicalise_requirements',return_value=changed):
                with self.assertRaisesRegex(real.Blocked, 'current raw-JD parsing changes historical'):
                    self.load()

    def test_corrupted_historical_allocation_cannot_be_reconciled_by_current_parser(self):
        b = self.load_binding(); report = self.initial_report()
        b['snapshot']['stable_analysis']['canonical_requirements'][0]['group_weight_fraction'] = .123
        report['stable_analysis'] = deepcopy(b['snapshot']['stable_analysis'])
        self.rewrite(b, report)
        with self.assertRaisesRegex(real.Blocked, 'historical requirement allocation'): self.load()

    def test_original_evidence_fingerprint_still_mandatory(self):
        b = self.load_binding(); report = self.initial_report()
        b['snapshot']['evidence_fingerprint'] = 'invalid'
        self.rewrite(b, report)
        with self.assertRaisesRegex(real.Blocked, 'evidence identity differs'): self.load()

    def test_missing_ownership_is_not_reconstructed(self):
        b = self.load_binding(); report = self.initial_report()
        b['snapshot']['evidence_snapshot'][0]['id'] = None
        b['snapshot']['evidence_fingerprint'] = fingerprint_evidence_items(b['snapshot']['evidence_snapshot'])
        self.rewrite(b, report)
        with self.assertRaisesRegex(real.Blocked, 'ownership/projection'): self.load()

    def test_jd_hash_conflict_and_unknown_archive_identity_block(self):
        b = self.load_binding(); report = self.initial_report()
        b['raw_jd_sha256'] = 'invalid'
        self.rewrite(b, report)
        with self.assertRaisesRegex(real.Blocked, 'JD generation'): self.load()

    def test_unverified_archive_identity_cannot_be_renamed_as_current(self):
        b = self.load_binding(); report = self.initial_report()
        b['snapshot']['scoring_version'] = 'unknown-historical-scorer'
        b['snapshot']['stable_analysis']['scoring_version'] = 'unknown-historical-scorer'
        report['stable_analysis'] = deepcopy(b['snapshot']['stable_analysis'])
        self.rewrite(b, report)
        with self.assertRaisesRegex(real.Blocked, 'historical input schema'): self.load()

    def test_gate_and_post_load_source_races_block_without_scoring(self):
        loaded = self.load()
        self.sql('UPDATE applications SET report_json=?', (json.dumps({'meta':{'later':True}}),))
        with patch.object(preview, 'run_comparison') as run:
            with self.assertRaisesRegex(real.Blocked, 'STALE'): real.evaluate(loaded, session_enabled=True)
            with self.assertRaisesRegex(real.Blocked, 'OFF'): real.load_retrospective(self.app_id)
            run.assert_not_called()

    def test_actual_pipeline_same_sources_current_identities_nulls_and_read_only(self):
        loaded = self.load(); before = self.path.read_bytes()
        with patch.object(preview.native, 'build_stable_analysis', wraps=preview.native.build_stable_analysis) as native_run, \
             patch.object(preview.gated, 'build_coordinated_analysis', wraps=preview.gated.build_coordinated_analysis) as gated_run:
            result = real.evaluate(loaded, session_enabled=True)
            for field in ('raw_jd_text','jd_profile','resume_profile','raw_resume_text'):
                self.assertEqual(native_run.call_args.kwargs[field], gated_run.call_args.kwargs[field])
            self.assertEqual(native_run.call_args.kwargs['jd_profile'], {})
        c = result['comparison']
        self.assertEqual(c.published.scoring_version, preview.native.SCORING_VERSION)
        self.assertEqual(c.gated.scoring_version, preview.PROJECTED_SCORER_VERSION)
        self.assertIsNone(c.gated.alignment)  # independent E04 same-project conflict
        self.assertTrue(any(r.conflict and r.conflict.get('quarantine') for r in c.gated.requirements))
        self.assertFalse(result['geometry_comparable'])
        self.assertEqual(self.path.read_bytes(), before)
        rid = c.gated.requirements[0].requirement_id
        export = json.loads(real.selected_export(result, [rid]))
        self.assertIsNone(export['historical_numeric_delta'])
        self.assertFalse(export['persistence_eligible'])
        self.assertTrue(all(r['Published credit'] is None and r['Experimental credit'] is None for r in export['requirements']))

    def test_compatible_fresh_geometry_receipt(self):
        # Presentation-only double, not an independent scoring oracle.
        loaded = self.load()
        published = deepcopy(self.comparison.published_analysis)
        gated = deepcopy(published); gated['scoring_version'] = preview.PROJECTED_SCORER_VERSION
        from job_discovery.coordinated_preview_model import analysis_view
        c = replace(self.comparison, identity=loaded['request'].identity,
                    published_analysis=published, gated_analysis=gated,
                    published=analysis_view(published), gated=analysis_view(gated))
        with patch.object(preview, 'run_comparison', return_value=c):
            result = real.evaluate(loaded, session_enabled=True)
        self.assertTrue(result['geometry_comparable'])

    def test_fresh_old_taxonomy_identity_is_rejected(self):
        loaded = self.load()
        gated = deepcopy(self.comparison.gated_analysis)
        gated['capability_taxonomy_version'] = 'phase6d-capability-taxonomy-v1.5'
        c = replace(self.comparison, identity=loaded['request'].identity, gated_analysis=gated)
        with patch.object(preview, 'run_comparison', return_value=c):
            with self.assertRaisesRegex(real.Blocked, 'fresh diagnostic implementation/input identity'):
                real.evaluate(loaded, session_enabled=True)

    def test_fresh_published_geometry_must_match_admitted_rows(self):
        loaded = self.load()
        published = deepcopy(self.comparison.published_analysis)
        published['canonical_requirements'][0]['group_weight_fraction'] = .123
        c = replace(self.comparison, identity=loaded['request'].identity, published_analysis=published)
        with patch.object(preview, 'run_comparison', return_value=c):
            with self.assertRaisesRegex(real.Blocked, 'fresh published requirements differ'):
                real.evaluate(loaded, session_enabled=True)

    def test_mode_marker_cannot_turn_a_historical_packet_into_strict(self):
        loaded = self.load(); loaded.pop('mode')
        with patch.object(preview, 'run_comparison') as run:
            with self.assertRaisesRegex(real.Blocked, 'STALE: saved match/scorer/taxonomy'):
                real.evaluate(loaded, session_enabled=True)
            run.assert_not_called()

    def test_ui_explicit_retrospective_compare_retains_result_and_strict_mode(self):
        self.sql('UPDATE applications SET report_json=?', (json.dumps({'meta':{'later':True}}),))
        before = self.path.read_bytes()
        with patch.object(real, 'evaluate', wraps=real.evaluate) as run:
            app = page_test().run()
            app.toggle(key='developer_job_match_ui_v1_enabled').set_value(True).run()
            app.button(key='developer_real_browse').click().run()
            app.selectbox(key='developer_real_app').set_value(self.app_id).run()
            app.selectbox(key='developer_real_mode').set_value('Retrospective Frozen Evidence Comparison').run()
            app.button(key='developer_real_load').click().run()
            self.assertFalse(app.exception, [e.message for e in app.exception])
            run.assert_not_called()
            self.assertTrue(any(real.RETROSPECTIVE_LABEL in w.value for w in app.warning))
            app.button(key='developer_real_compare').click().run()
            self.assertFalse(app.exception, [e.message for e in app.exception])
            self.assertEqual(run.call_count, 1)
            self.assertFalse(app.metric)  # geometry mismatch: no comparative percentages
            app.selectbox(key='developer_real_filter').set_value('REVIEW_REQUIRED').run()
            table = next(d.value for d in app.dataframe if 'Experimental credit' in d.value.columns)
            self.assertTrue(table['Experimental credit'].isna().all())
            app.button(key='developer_real_review_action_0').click().run()
            self.assertEqual(app.session_state['developer_real_review_selected'], sorted(table['Requirement ID']))
            app.run(); self.assertEqual(run.call_count, 1)
            app.selectbox(key='developer_real_mode').set_value('Strict current-version comparison').run()
            self.assertNotIn(real.STATE, app.session_state)
            self.assertEqual(self.path.read_bytes(), before)

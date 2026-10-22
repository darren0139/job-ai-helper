"""Real persistence shapes, synthetic payloads, disposable DBs, independent labels."""
from contextlib import ExitStack, closing
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from database import db_manager as db, analysis_cache_manager as cache
from database import job_match_manager as matches, job_discovery_manager as discovery
from database.phase9f_application_confirmation_manager import create_job_finder_application_session
from job_discovery import developer_real_comparison as real, developer_comparison as synthetic
from job_discovery import coordinated_preview as preview
from job_discovery.matching import current_match_versions, fingerprint_evidence_items
from scripts.coordinated_job_match_preview_inputs import preview_inputs
from tests.test_developer_comparison import page_test


class RealComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = preview_inputs('E04')
        # A real handoff requires a nonempty frozen extraction and contains
        # library originals only, not the synthetic adapter's extra raw channel.
        cls.inputs['jd_profile'] = {'job_title':'Engineer'}
        cls.inputs['raw_only_text'] = ''
        cls.comparison = preview.run_comparison(preview.prepare_comparison(**cls.inputs), developer_enabled=True)

    def setUp(self):
        self.stack = self.enterContext(ExitStack())
        folder = self.enterContext(tempfile.TemporaryDirectory())
        self.path = Path(folder)/'applications.db'
        for module in (db, matches, discovery):
            self.stack.enter_context(patch.object(module, 'DB_PATH', self.path))
        self.stack.enter_context(patch.dict(os.environ, {synthetic.GATE: '1'}))
        db.init_db(); cache.init_analysis_cache(); discovery.init_job_discovery_schema()
        with closing(db._connect()) as conn:
            conn.execute("INSERT INTO discovered_jobs (id,source,source_job_id,title,company,description,source_url,content_hash,raw_payload_json,first_seen_at,last_seen_at,updated_at) VALUES (7,'fixture','7','PRIVATE_TITLE','PRIVATE_COMPANY',?,'https://example.invalid','generation7','{}','now','now','now')", (self.inputs['raw_jd_text'],))
            conn.commit()
        versions = current_match_versions()
        self.snapshot = matches.save_job_match_snapshot(discovered_job_id=7, job_content_hash='generation7',
            evidence_fingerprint=fingerprint_evidence_items(self.inputs['evidence_items']),
            match_version=versions['match_version'], scoring_version=versions['scoring_version'],
            taxonomy_version=versions['taxonomy_version'], jd_profile=self.inputs['jd_profile'],
            evidence_snapshot=self.inputs['evidence_items'], stable_analysis=self.comparison.published_analysis,
            summary={}, db_path=self.path)
        with patch('database.user_profile_manager.get_all_evidence_items_for_snapshot', return_value=self.inputs['evidence_items']):
            self.app_id = create_job_finder_application_session(discovered_job_id=7, snapshot_id=self.snapshot['id'])

    def load(self, **kwargs):
        return real.load(self.app_id, session_enabled=True, **kwargs)

    def sql(self, sql, values=()):
        with closing(db._connect()) as conn:
            conn.execute(sql, values); conn.commit()

    def test_exact_owned_frozen_inputs_and_saved_receipt(self):
        before = self.path.read_bytes()
        loaded = self.load()
        self.assertEqual(loaded['application_id'], self.app_id)
        self.assertEqual(loaded['request'].projection['evidence_items'], self.inputs['evidence_items'])
        self.assertEqual(loaded['request'].raw_jd_text, self.inputs['raw_jd_text'])
        self.assertEqual(loaded['saved']['stable_analysis'], self.comparison.published_analysis)
        self.assertEqual(loaded['saved']['identity']['source_snapshot_id'], self.snapshot['id'])
        self.assertEqual(real.list_applications(session_enabled=True)[0]['id'], self.app_id)
        self.assertEqual(self.path.read_bytes(), before)

    def test_admission_does_not_import_model_backed_intake(self):
        with patch.dict('sys.modules', {'tailoring.phase9f_jd_intake': None, 'llm': None}):
            self.assertEqual(self.load()['application_id'], self.app_id)

    def test_gate_off_no_connection_or_scoring(self):
        for env, consent in [('', True), ('true', True), ('1', False)]:
            with self.subTest(env=env, consent=consent), patch.dict(os.environ, {synthetic.GATE: env}), \
                 patch.object(real, '_read') as read, patch.object(preview, 'run_comparison') as run:
                with self.assertRaises(real.Blocked): real.load(self.app_id, session_enabled=consent)
                with self.assertRaises(real.Blocked): real.list_applications(session_enabled=consent)
                read.assert_not_called(); run.assert_not_called()

    def test_missing_forged_and_deleted_application(self):
        for identity in (None, True, '1 OR 1=1', -1, 99999):
            with self.subTest(identity=identity), self.assertRaises(real.Blocked):
                real.load(identity, session_enabled=True)
        loaded = self.load()
        self.sql('DELETE FROM applications WHERE id=?', (self.app_id,))
        with self.assertRaisesRegex(real.Blocked, 'deleted'):
            real.require_current(loaded, session_enabled=True)

    def test_missing_jd_version_blocks(self):
        self.sql('DELETE FROM discovered_jobs WHERE id=7')
        with self.assertRaisesRegex(real.Blocked, 'JD source'): self.load()

    def test_changed_jd_generation_blocks(self):
        self.sql("UPDATE discovered_jobs SET content_hash='new' WHERE id=7")
        with self.assertRaisesRegex(real.Blocked, 'STALE'): self.load()

    def test_missing_saved_analysis_blocks(self):
        self.sql('DELETE FROM application_analysis_versions WHERE application_id=?', (self.app_id,))
        with self.assertRaisesRegex(real.Blocked, 'Initial Analysis unavailable'): self.load()

    def test_missing_snapshot_blocks(self):
        self.sql('DELETE FROM job_match_snapshots')
        with self.assertRaisesRegex(real.Blocked, 'snapshot'): self.load()

    def test_document_and_legacy_do_not_acquire_library_authority(self):
        self.sql("UPDATE applications SET entry_binding_json='{}'")
        with self.assertRaisesRegex(real.Blocked, 'Document/legacy'): self.load()

    def test_configured_document_session_is_not_a_library_preview(self):
        self.sql('CREATE TABLE phase9f_application_confirmations (application_id INTEGER)')
        self.sql('INSERT INTO phase9f_application_confirmations VALUES (?)', (self.app_id,))
        with self.assertRaisesRegex(real.Blocked, 'configured Application Session'): self.load()

    def test_separate_resume_authority_is_not_silently_ignored(self):
        self.sql("UPDATE applications SET initial_resume_analysis_id='document-receipt'")
        with self.assertRaisesRegex(real.Blocked, 'résumé-document authority'): self.load()

    def test_invalid_database_never_created(self):
        missing = self.path.parent/'missing.db'
        with self.assertRaises(real.Blocked): self.load(db_path=missing)
        self.assertFalse(missing.exists())

    def test_jd_snapshot_from_other_job_is_not_selected(self):
        self.sql('UPDATE job_match_snapshots SET discovered_job_id=8')
        with self.assertRaisesRegex(real.Blocked, 'snapshot'): self.load()

    def test_scorer_mismatch_is_stale_without_refresh(self):
        with patch.object(real, 'current_match_versions', return_value={**current_match_versions(), 'scoring_version':'future'}), \
             patch.object(preview, 'run_comparison') as run:
            with self.assertRaisesRegex(real.Blocked, 'STALE'): self.load()
            run.assert_not_called()

    def test_conflicting_initial_id_blocks(self):
        self.sql("UPDATE applications SET initial_analysis_id='another-app-receipt'")
        with self.assertRaisesRegex(real.Blocked, 'conflicting'): self.load()

    def test_local_override_or_replacement_report_blocks(self):
        self.sql('UPDATE applications SET report_json=?', (json.dumps({'meta':{'jd_user_inputs':{'preferred_requirements':['extra']}}}),))
        with self.assertRaisesRegex(real.Blocked, 'overrides'): self.load()

    def test_receipt_application_scope_cannot_fallback(self):
        self.sql('UPDATE application_analysis_versions SET application_id=999')
        with self.assertRaisesRegex(real.Blocked, 'Initial Analysis unavailable'): self.load()

    def test_changed_after_load_never_scores(self):
        loaded = self.load()
        self.sql("UPDATE applications SET session_name='changed'")
        with patch.object(preview, 'run_comparison') as run:
            with self.assertRaisesRegex(real.Blocked, 'STALE'): real.evaluate(loaded, session_enabled=True)
            run.assert_not_called()

    def test_forged_loaded_request_is_rejected(self):
        loaded = self.load(); loaded['context']['application_id'] = 999
        with self.assertRaisesRegex(real.Blocked, 'STALE'):
            real.evaluate(loaded, session_enabled=True)

    def test_source_change_during_evaluation_discards_output(self):
        loaded = self.load()
        def change_source(*args, **kwargs):
            self.sql("UPDATE applications SET session_name='changed while evaluating'")
            return self.comparison
        with patch.object(preview, 'run_comparison', side_effect=change_source):
            with self.assertRaisesRegex(real.Blocked, 'STALE'):
                real.evaluate(loaded, session_enabled=True)

    def test_read_only_connection_enforces_writes(self):
        with self.assertRaises(real.Blocked):
            with real._read() as conn: conn.execute('DELETE FROM applications')

    def test_no_current_library_or_production_writer_routes(self):
        before = self.path.read_bytes()
        with ExitStack() as guard:
            mocks = [guard.enter_context(patch(target, side_effect=AssertionError('Forbidden route'))) for target in (
                'database.db_manager._connect', 'database.job_match_manager._connect',
                'database.analysis_cache_manager._connect', 'job_discovery.matching.current_evidence_context',
                'database.user_profile_manager.get_all_evidence_items_for_snapshot',
                'job_discovery.matching.analyze_job_match')]
            loaded = self.load()
            # Execute the actual deterministic pipeline through the new admission boundary.
            result = real.evaluate(loaded, session_enabled=True)
            embedded = [r for r in result['comparison'].gated.requirements
                        if r.receipt.get('obligation', {}).get('object_family') == 'embedded']
            self.assertEqual(len(embedded), 1)
            self.assertEqual(embedded[0].label.value, 'REVIEW_REQUIRED')  # E04 independent conflict oracle
            self.assertTrue(embedded[0].conflict['quarantine'])
            self.assertIsNone(embedded[0].contribution)
            self.assertIsNone(result['comparison'].gated.alignment)
            self.assertEqual(result['comparison'].published.scoring_version, 'stable-evidence-v1.17-phase6d21')
            for mock in mocks: mock.assert_not_called()
        self.assertEqual(self.path.read_bytes(), before)

    def test_ownership_and_empty_evidence_blocked(self):
        from tailoring.phase9f_application_confirmation import fingerprint_value
        for items in ([], [{**self.inputs['evidence_items'][0], 'id': None}]):
            binding = self.load_binding()
            source = deepcopy(binding['snapshot']); source['evidence_snapshot'] = items
            source['evidence_fingerprint'] = fingerprint_evidence_items(items)
            self.sql('UPDATE job_match_snapshots SET evidence_snapshot_json=?,evidence_fingerprint=?',
                     (json.dumps(items), source['evidence_fingerprint']))
            binding['snapshot'] = source
            binding['binding_fingerprint'] = fingerprint_value({k:v for k,v in binding.items() if k!='binding_fingerprint'})
            self.sql('UPDATE applications SET entry_binding_json=?', (json.dumps(binding),))
            # Receipt must also match to reach the ownership check.
            with closing(db._connect()) as conn:
                row = conn.execute('SELECT report_json FROM application_analysis_versions').fetchone()
            report = json.loads(row[0]); report['meta']['initial_analysis_reference'] = binding
            self.sql('UPDATE application_analysis_versions SET report_json=?,input_fingerprint=?',
                     (json.dumps(report), binding['binding_fingerprint']))
            with self.assertRaisesRegex(real.Blocked, 'evidence'): self.load()

    def load_binding(self):
        with closing(db._connect()) as conn:
            return json.loads(conn.execute('SELECT entry_binding_json FROM applications WHERE id=?', (self.app_id,)).fetchone()[0])

    def test_selected_export_has_no_private_wording_or_unselected_rows(self):
        result = {'identity':'safe-digest', 'comparison':self.comparison}
        rid = self.comparison.gated.requirements[0].requirement_id
        text = real.selected_export(result, [rid]); data = json.loads(text)
        self.assertEqual([r['Requirement ID'] for r in data['requirements']], [rid])
        for private in ('PRIVATE_TITLE','PRIVATE_COMPANY','raw_jd_text','raw_resume_text','receipt'):
            self.assertNotIn(private, text)
        self.assertFalse(data['persistence_eligible'])
        with self.assertRaises(real.Blocked): real.selected_export(result, ['forged'])


class RealUITests(unittest.TestCase):
    setUpClass = classmethod(RealComparisonTests.setUpClass.__func__)
    setUp = RealComparisonTests.setUp
    def test_ui_explicit_load_compare_filter_selection_no_recompute(self):
        with patch.object(real.preview, 'run_comparison', return_value=self.comparison) as run:
            app = page_test().run()
            app.toggle(key='developer_job_match_ui_v1_enabled').set_value(True).run()
            self.assertFalse(app.exception)
            app.button(key='developer_real_browse').click().run()
            app.selectbox(key='developer_real_app').set_value(self.app_id).run()
            run.assert_not_called()
            before = self.path.read_bytes()
            app.button(key='developer_real_load').click().run()
            self.assertFalse(app.exception, [e.message for e in app.exception])
            run.assert_not_called()
            app.button(key='developer_real_compare').click().run()
            self.assertFalse(app.exception, [e.message for e in app.exception])
            self.assertEqual(run.call_count, 1)
            self.assertTrue(any('unavailable' in w.value for w in app.warning))
            self.assertTrue(any('geometry' in w.value for w in app.warning))
            app.selectbox(key='developer_real_filter').set_value('REVIEW_REQUIRED').run()
            table = next(d.value for d in app.dataframe if 'Experimental credit' in d.value.columns)
            self.assertTrue(table['Experimental credit'].isna().all())
            expected_ids = sorted(table['Requirement ID'])
            app.button(key='developer_real_review_action_0').click().run()
            self.assertEqual(app.session_state['developer_real_review_selected'], expected_ids)
            app.run()
            self.assertEqual(run.call_count, 1)
            self.assertEqual(self.path.read_bytes(), before)
            app.toggle(key='developer_job_match_ui_v1_enabled').set_value(False).run()
            self.assertNotIn(real.STATE, app.session_state)

    def test_main_cold_read_only_entry_skips_production_startup(self):
        with patch('database.db_manager.init_db', side_effect=AssertionError('Production startup forbidden')), \
             patch('database.application_tracking_manager.init_application_tracking_schema', side_effect=AssertionError('Tracking forbidden')), \
             patch.object(real.preview, 'run_comparison', return_value=self.comparison) as run:
            app = page_test(main=True)
            app.query_params['developer_comparison'] = '1'
            before = self.path.read_bytes()
            app.run()
            self.assertFalse(app.exception, [e.message for e in app.exception])
            self.assertEqual(app.radio(key='navigation_page').value, synthetic.PAGE)
            app.toggle(key='developer_job_match_ui_v1_enabled').set_value(True).run()
            app.button(key='developer_real_browse').click().run()
            app.selectbox(key='developer_real_app').set_value(self.app_id).run()
            app.button(key='developer_real_load').click().run()
            run.assert_not_called()
            app.button(key='developer_real_compare').click().run()
            self.assertFalse(app.exception, [e.message for e in app.exception])
            app.run()
            self.assertEqual(run.call_count, 1)
            self.assertEqual(self.path.read_bytes(), before)

    def test_synthetic_opt_in_does_not_open_application_storage(self):
        with patch.object(real, 'list_applications', side_effect=AssertionError('Explicit browse required')) as listing:
            app = page_test().run()
            app.toggle(key='developer_job_match_ui_v1_enabled').set_value(True).run()
            app.run()
            self.assertFalse(app.exception)
            listing.assert_not_called()

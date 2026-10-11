"""Native SQLite acceptance for durable Job Finder -> Phase 9F ownership."""
from __future__ import annotations

import ast
import copy
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from database import db_manager, job_discovery_manager, job_match_manager
from database import phase9f_application_confirmation_manager as manager
from job_discovery.matching import current_match_versions, fingerprint_evidence_items
from tailoring.phase9f_application_confirmation import Phase9FDConfirmationError
from tests import test_phase9f_application_confirmation as support


class SharedApplicationSessionIdentityTests(unittest.TestCase):
    def setUp(self):
        support.Phase9FApplicationConfirmationTests.setUp(self)
        self.addCleanup(support.Phase9FApplicationConfirmationTests.tearDown, self)
        self.discovery_patch = patch.object(job_discovery_manager, "DB_PATH", self.database_path)
        self.discovery_patch.start()
        self.addCleanup(self.discovery_patch.stop)
        job_discovery_manager.init_job_discovery_schema()
        connection = db_manager._connect()
        connection.execute("INSERT INTO discovered_jobs (id,source,source_job_id,title,company,description,source_url,content_hash,raw_payload_json,first_seen_at,last_seen_at,updated_at) VALUES (7,'fixture','7','Engineer','Example',?,'https://example.invalid','hash','{}','now','now','now')", (self.original_jd['raw_text'],))
        connection.commit()
        connection.close()
        versions = current_match_versions()
        native = self.ranking['recommended_source']['candidate_analysis_snapshot']['stable_analysis_snapshot']
        self.snapshot = job_match_manager.save_job_match_snapshot(
            discovered_job_id=7, job_content_hash='hash', evidence_fingerprint=fingerprint_evidence_items([]),
            match_version=versions['match_version'], scoring_version=versions['scoring_version'],
            taxonomy_version=versions['taxonomy_version'], jd_profile=self.original_jd['jd_profile'],
            evidence_snapshot=[], stable_analysis=native, summary={'deterministic_alignment_score': native['deterministic_alignment_score']},
            db_path=self.database_path)

    counts = support.Phase9FApplicationConfirmationTests.counts

    def draft(self):
        return manager.create_job_finder_application_session(discovered_job_id=7, snapshot_id=self.snapshot['id'])

    def confirm(self, target=None, **kwargs):
        parameters = dict(
            phase9f_a_snapshot=self.original_jd, persisted_exact_jd_snapshot=self.persisted_jd,
            ranking_result=self.ranking, phase9f_c_recommendation=self.recommendation,
            confirmed_normalized_source_fingerprint=self.ranking['recommended_source']['normalized_source_fingerprint'],
            confirmed_intensity=self.recommendation['recommended_intensity'], application_intent_id='intent',
            existing_application_id=target, discovered_job_id=7 if target else None)
        parameters.update(kwargs)
        return manager.confirm_phase9f_application_session(**parameters)

    def test_draft_persists_exact_initial_and_reuses_every_owner(self):
        before = self.counts()
        target = self.draft()
        self.assertEqual(self.counts()['applications'], before['applications'] + 1)
        binding = db_manager.list_job_finder_application_bindings()[0]['binding']
        self.assertEqual(binding['snapshot'], self.snapshot)
        with patch('analysis_stability.build_stable_analysis', side_effect=AssertionError('No recomputation')):
            result = self.confirm(target)
        self.assertEqual(result['confirmation']['application_id'], target)
        self.assertEqual(self.counts()['applications'], before['applications'] + 1)
        self.assertEqual(self.counts()['application_analysis_versions'], 1)
        connection = db_manager._connect()
        try:
            for table in ('application_job_links','application_analysis_versions','application_blueprint_decisions','application_blueprint_binding_events','phase9f_application_confirmations','phase9f_application_confirmation_events'):
                self.assertEqual({r[0] for r in connection.execute(f'SELECT application_id FROM {table}')}, {target}, table)
            initial = connection.execute('SELECT analysis_id,report_json FROM application_analysis_versions').fetchone()
        finally:
            connection.close()
        self.assertEqual(initial[0], binding['initial_analysis_id'])
        self.assertEqual(json.loads(initial[1])['stable_analysis'], self.snapshot['stable_analysis'])
        self.assertEqual(db_manager.get_application_by_id(target)['report']['meta']['initial_analysis_reference'], binding)
        self.assertEqual(result['confirmation']['confirmation_snapshot']['initial_analysis']['origin'], 'job_finder')

    def test_rerun_and_new_browser_intent_reuse_exact_identity(self):
        target = self.draft()
        first = self.confirm(target)
        counts = self.counts()
        second = self.confirm(target, application_intent_id='another-browser')
        self.assertEqual(first['confirmation'], second['confirmation'])
        self.assertEqual(second['cache_status'], 'exact_operation_reused')
        self.assertEqual(self.counts(), counts)
        self.assertEqual(db_manager.list_job_finder_application_bindings()[0]['application_id'], target)

    def test_create_new_still_creates_one_idempotently(self):
        first = self.confirm()
        counts = self.counts()
        self.assertEqual(self.confirm()['confirmation']['application_id'], first['confirmation']['application_id'])
        self.assertEqual(self.counts(), counts)

    def test_wrong_source_missing_and_unbound_application_fail_closed(self):
        target = self.draft()
        counts = self.counts()
        with self.assertRaises(Phase9FDConfirmationError):
            self.confirm(target, discovered_job_id=8)
        with self.assertRaises(Phase9FDConfirmationError):
            self.confirm(9876)
        blank = db_manager.create_empty_application_session()
        with self.assertRaises(Phase9FDConfirmationError):
            self.confirm(blank)
        self.assertEqual(self.counts()['phase9f_application_confirmations'], counts['phase9f_application_confirmations'])

    def test_changed_jd_and_canonical_identity_fail_closed(self):
        target = self.draft()
        counts = self.counts()
        for field, value in [('raw_jd_sha256','wrong'), ('canonical_requirement_fingerprint','wrong')]:
            connection = db_manager._connect()
            original = json.loads(connection.execute('SELECT entry_binding_json FROM applications WHERE id=?', (target,)).fetchone()[0])
            changed = copy.deepcopy(original)
            changed[field] = value
            connection.execute('UPDATE applications SET entry_binding_json=? WHERE id=?', (json.dumps(changed), target))
            connection.commit()
            connection.close()
            with self.assertRaises(Phase9FDConfirmationError):
                self.confirm(target)
            connection = db_manager._connect()
            connection.execute('UPDATE applications SET entry_binding_json=? WHERE id=?', (json.dumps(original), target))
            connection.commit()
            connection.close()
        self.assertEqual(self.counts(), counts)

    def test_conflicting_confirmation_does_not_repurpose_application(self):
        target = self.draft()
        self.confirm(target)
        counts = self.counts()
        other = 'full' if self.recommendation['recommended_intensity'] != 'full' else 'minor'
        with self.assertRaises(Phase9FDConfirmationError):
            self.confirm(target, confirmed_intensity=other)
        self.assertEqual(self.counts(), counts)

    def test_stale_snapshot_and_changed_source_fail_closed(self):
        target = self.draft()
        with patch('job_discovery.matching.current_match_versions', return_value={'scoring_version':'future'}):
            with self.assertRaisesRegex(Phase9FDConfirmationError, 'Refresh'):
                self.confirm(target)
        connection = db_manager._connect()
        connection.execute("UPDATE discovered_jobs SET content_hash='changed' WHERE id=7")
        connection.commit()
        connection.close()
        with self.assertRaises(Phase9FDConfirmationError):
            self.confirm(target)
        self.assertIsNone(db_manager.get_application_by_id(target)['report'])

    def test_transaction_failure_preserves_unconfigured_draft_and_initial(self):
        target = self.draft()
        counts = self.counts()
        binding = db_manager.list_job_finder_application_bindings()
        with patch.object(manager, '_insert_confirmation_event', side_effect=RuntimeError('rollback')):
            with self.assertRaises(RuntimeError):
                self.confirm(target)
        self.assertEqual(self.counts(), counts)
        self.assertEqual(db_manager.list_job_finder_application_bindings(), binding)
        self.assertIsNone(db_manager.get_application_by_id(target)['report'])

    def test_existing_delete_contract_leaves_no_new_binding_rows(self):
        from database.analysis_cache_manager import delete_application_analysis_versions
        from database.application_blueprint_manager import delete_application_blueprint_decisions
        from database.jd_library_manager import unlink_job_description_from_application
        for configured in (False, True):
            target = self.draft()
            if configured:
                self.confirm(target)
                unlink_job_description_from_application(target)
                manager.delete_phase9f_application_confirmation(target)
                delete_application_blueprint_decisions(target)
            delete_application_analysis_versions(target)
            db_manager.delete_application_session(target)
            self.assertIsNone(db_manager.get_application_by_id(target))
            self.assertEqual(db_manager.list_job_finder_application_bindings(), [])
            for table, count in self.counts().items():
                self.assertEqual(count, 0, table)

    def test_handoff_ui_only_allocates_once_and_forwards_saved_snapshot(self):
        root = Path(__file__).resolve().parents[1]
        tree = ast.parse((root / 'job_discovery/ui.py').read_text(encoding='utf-8'))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_handoff_to_new_application')
        creator = Mock(return_value=123)
        state = {}
        namespace = {'Any': object, 'create_job_finder_application_session': creator,
                     'st': SimpleNamespace(session_state=state, rerun=Mock())}
        exec(compile(ast.Module(body=[node], type_ignores=[]), '<handoff>', 'exec'), namespace)
        namespace['_handoff_to_new_application']({'id':7, 'description': self.original_jd['raw_text']}, self.snapshot['id'])
        creator.assert_called_once_with(discovered_job_id=7, snapshot_id=self.snapshot['id'])
        self.assertEqual(state['current_application_id'], 123)

    def test_streamlit_explicit_confirmation_recovers_persisted_application(self):
        from streamlit.testing.v1 import AppTest
        target = self.draft()
        before = self.counts()
        app = AppTest.from_string('''
import streamlit as st
from database import db_manager, jd_library_manager, tailoring_version_manager
from pathlib import Path
from tailoring.phase9f_application_confirmation_ui import render_phase9f_application_confirmation
for module in (db_manager, jd_library_manager, tailoring_version_manager):
    module.DB_PATH = Path(st.session_state['database_path'])
render_phase9f_application_confirmation(
    phase9f_a_snapshot=st.session_state['exact'],
    ranking_result=st.session_state['ranking'],
    phase9f_c_recommendation=st.session_state['recommendation'])
''', default_timeout=30)
        for key, value in {'database_path': str(self.database_path), 'exact': self.original_jd,
                           'ranking': self.ranking, 'recommendation': self.recommendation}.items():
            app.session_state[key] = value
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(self.counts(), before)  # Passive render does not write.
        selector = next(s for s in app.selectbox if s.label == 'Application Session to configure')
        selector.select(target).run()
        self.assertFalse(app.exception)
        with patch('tailoring.phase9f_application_confirmation_ui.prepare_persisted_exact_jd_for_confirmation',
                   return_value=(self.persisted_jd, {})):
            next(b for b in app.button if b.label == 'Confirm and configure Application Session').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['current_application_id'], target)
        self.assertEqual(self.counts()['applications'], before['applications'])
        self.assertEqual(self.counts()['application_analysis_versions'], 1)

    def test_unanalyzed_job_does_not_allocate_draft(self):
        before = self.counts()
        with self.assertRaises(Phase9FDConfirmationError):
            manager.create_job_finder_application_session(discovered_job_id=7)
        self.assertEqual(self.counts(), before)

    def test_configuration_cannot_invoke_models_embeddings_or_network(self):
        from taxonomy_discovery.offline_execution import offline_execution
        target = self.draft()
        with offline_execution('Shared session tests forbid network'), \
             patch('litellm.completion', side_effect=AssertionError('No model calls')) as model, \
             patch('litellm.embedding', side_effect=AssertionError('No embeddings')) as embedding, \
             patch('analysis_stability.build_stable_analysis', side_effect=AssertionError('No Job Match recomputation')) as scorer:
            self.confirm(target)
        model.assert_not_called()
        embedding.assert_not_called()
        scorer.assert_not_called()

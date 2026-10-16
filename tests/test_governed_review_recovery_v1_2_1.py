"""Read-only receipt recovery and section layout over disposable real stores."""
from contextlib import ExitStack, closing
from copy import deepcopy
import importlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from tailoring import capability_taxonomy as t
from taxonomy_discovery import governed_review_recovery as recovery
from taxonomy_discovery import governed_requirement_resolution as g
from database import taxonomy_discovery_review_manager as store
from tests.test_governed_requirement_activation_v1_1 import isolated_lifecycle
from tests.governed_review_fixtures import write_taxonomy


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.directory=Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.path=self.directory/'taxonomy.json';write_taxonomy(self.path)
        self.stack.enter_context(patch.object(t,'TAXONOMY_PATH',self.path))
        t.get_default_taxonomy.cache_clear();self.addCleanup(t.get_default_taxonomy.cache_clear)
        self.db=self.directory/'review.sqlite3'
        self.stack.enter_context(patch.dict('os.environ',{'TAXONOMY_DISCOVERY_REVIEW_DB':str(self.db)}))
        self.row,self.saved,self.regression=isolated_lifecycle(self.directory)
        self.identity={'discovered_job_id':146,'id':40,'job_content_hash':'isolated-test-source'}
        self.approve()

    def approve(self):
        store.save_governed_research_review(self.saved['result']['research_result_id'],
            result_fingerprint=self.saved['result']['result_fingerprint'],decision='approve_for_publication',
            reviewer='ISOLATED HUMAN TEST',regression=self.regression,db_path=self.db)

    def app(self):
        app=AppTest.from_file(Path(__file__).with_name('governed_requirement_review_harness.py'),default_timeout=60)
        app.session_state['view']={'identity':self.identity,'provenance':'ISOLATED',
                                   'requirements':[{'native':self.row}]}
        return app

    def assert_no_mutations(self):
        for name in ('create_local_governed_draft','validate_governed_draft'):
            self.stack.enter_context(patch.object(g,name,side_effect=AssertionError('Recovery must not mutate or replay')))
        for name in ('save_governed_research_review','save_governed_research_draft','save_governed_temporary_impact'):
            self.stack.enter_context(patch.object(store,name,side_effect=AssertionError('Recovery must not write')))
        self.stack.enter_context(patch('taxonomy_discovery.governed_publication.publish_approved_change',
            side_effect=AssertionError('Recovery must not publish')))
        self.stack.enter_context(patch('taxonomy_discovery.regression_corpus.export_saved_corpus',
            side_effect=AssertionError('Recovery must not fetch/replay corpus')))

    def test_reopen_and_code_reload_recovers_exact_real_approval_without_writes(self):
        before=self.db.read_bytes();knowledge=self.path.read_bytes();self.assert_no_mutations()
        app=self.app();app.run();self.assertFalse(app.exception)
        self.assertTrue(any('Already approved' in x.value for x in app.success))
        self.assertTrue(any('Approved — Ready for publication' in x.value for x in app.success))
        self.assertTrue(next(b for b in app.button if b.label=='Approve validated draft').disabled)
        self.assertTrue(next(b for b in app.button if b.label=='Validate draft').disabled)
        self.assertTrue(next(b for b in app.button if b.label=='Publish approved correction').disabled)
        self.assertTrue(any('Blockers: 0' in x.value for x in app.markdown))
        self.assertFalse(any('Preview is not approval' in x.value for x in app.caption))
        with patch.object(recovery,'recover',wraps=recovery.recover) as read:
            app.run();app.run();read.assert_not_called()
        # A fresh session and reloaded implementation must recover from SQLite,
        # not a surviving Streamlit packet or an invented screenshot receipt.
        from tailoring import unresolved_requirement_review_ui as ui
        importlib.reload(ui)
        reopened=self.app();reopened.run();self.assertFalse(reopened.exception)
        self.assertTrue(any('Already approved' in x.value for x in reopened.success))
        packet=next(v for k,v in reopened.session_state.filtered_state.items() if k.endswith('_packet'))
        self.assertEqual(packet['readiness']['draft_fingerprint'],self.regression['draft_fingerprint'])
        self.assertEqual(packet['readiness']['regression_fingerprint'],self.regression['regression_fingerprint'])
        self.assertEqual(packet['readiness']['blockers'],[])
        self.assertEqual(self.db.read_bytes(),before);self.assertEqual(self.path.read_bytes(),knowledge)

    def test_sql_authorizer_rejects_all_writes_during_recovery(self):
        connect=sqlite3.connect
        forbidden={sqlite3.SQLITE_INSERT,sqlite3.SQLITE_UPDATE,sqlite3.SQLITE_DELETE,
                   sqlite3.SQLITE_CREATE_TABLE,sqlite3.SQLITE_DROP_TABLE,sqlite3.SQLITE_ALTER_TABLE}
        def readonly(*args,**kwargs):
            self.assertIn('mode=ro',args[0]);self.assertTrue(kwargs.get('uri'))
            conn=connect(*args,**kwargs)
            conn.set_authorizer(lambda action,*_:sqlite3.SQLITE_DENY if action in forbidden else sqlite3.SQLITE_OK)
            return conn
        with patch('sqlite3.connect',side_effect=readonly):
            found=recovery.recover(self.row,self.identity,db_path=self.db)
        self.assertEqual(found['status'],'ready');self.assertTrue(found['readiness']['ready'])

    def test_missing_approval_and_missing_store_fail_closed(self):
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute('UPDATE governed_research_results SET review_json=NULL');conn.commit()
        unapproved=recovery.recover(self.row,self.identity,db_path=self.db)
        self.assertEqual(unapproved['status'],'validated')
        self.assertNotIn('approval',unapproved);self.assertNotIn('readiness',unapproved)
        missing=self.directory/'absent.sqlite3'
        self.assertEqual(recovery.recover(self.row,self.identity,db_path=missing)['status'],'missing')
        self.assertFalse(missing.exists())

    def test_unapproved_validation_recovered_without_scoring_or_automatic_approval(self):
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute('UPDATE governed_research_results SET review_json=NULL');conn.commit()
        before=self.db.read_bytes();self.assert_no_mutations()
        with patch.object(g,'preview',side_effect=AssertionError('Do not replay validation to reopen')):
            app=self.app();app.run();self.assertFalse(app.exception)
        self.assertTrue(any('Draft validated' in x.value for x in app.success))
        self.assertFalse(any('Already approved' in x.value for x in app.success))
        self.assertTrue(next(b for b in app.button if b.label=='Validate draft').disabled)
        self.assertTrue(next(b for b in app.button if b.label=='Approve validated draft').disabled)
        self.assertFalse(any(b.label=='Publish approved correction' for b in app.button))
        self.assertEqual(self.db.read_bytes(),before)

    def test_unvalidated_saved_draft_is_pending_and_cannot_approve(self):
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute('UPDATE governed_research_results SET review_json=NULL')
            conn.execute('DELETE FROM governed_temporary_impacts');conn.commit()
        found=recovery.recover(self.row,self.identity,db_path=self.db)
        self.assertEqual(found['status'],'pending')
        self.assertNotIn('approval',found);self.assertNotIn('governed_regression',found)

    def test_incorrect_job_requirement_snapshot_hash_cannot_reuse_receipt(self):
        for key,value in [('discovered_job_id',214),('id',55),('job_content_hash','different')]:
            identity={**self.identity,key:value}
            self.assertEqual(recovery.recover(self.row,identity,db_path=self.db)['status'],'missing')
        row={**self.row,'requirement_id':'other'}
        self.assertEqual(recovery.recover(row,self.identity,db_path=self.db)['status'],'missing')

    def test_source_input_change_is_stale_not_an_actionable_approval(self):
        found=recovery.recover({**self.row,'text':'Build APIs and gRPC'},self.identity,db_path=self.db)
        self.assertEqual(found['status'],'stale');self.assertFalse(found['readiness']['ready'])
        self.assertTrue(any('Source requirement input fingerprint changed' in x for x in found['blockers']))

    def test_stale_draft_and_other_draft_approval_are_rejected(self):
        draft=deepcopy(self.saved['draft']);draft['resolver_draft_id']='different-draft'
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute('UPDATE governed_research_results SET draft_json=?',(json.dumps(draft),));conn.commit()
        found=recovery.recover(self.row,self.identity,db_path=self.db)
        self.assertEqual(found['status'],'stale')
        self.assertTrue(any('Draft fingerprint changed' in x for x in found['blockers']))
        self.assertTrue(any('different draft' in x for x in found['blockers']))

    def test_stale_taxonomy_and_knowledge_are_explained_and_not_reused(self):
        raw=json.loads(self.path.read_text(encoding='utf-8'));raw['taxonomy_version']='phase6d-capability-taxonomy-v99.0'
        self.path.write_text(json.dumps(raw),encoding='utf-8');t.get_default_taxonomy.cache_clear()
        found=recovery.recover(self.row,self.identity,db_path=self.db)
        self.assertEqual(found['status'],'stale');self.assertFalse(found['readiness']['ready'])
        self.assertTrue(any('Native versions changed' in x for x in found['blockers']))
        with patch.object(g,'knowledge_fingerprint',return_value='changed-content'):
            changed=recovery.recover(self.row,self.identity,db_path=self.db)
            self.assertTrue(any('Knowledge fingerprint changed' in x for x in changed['blockers']))
        app=self.app();app.run();self.assertFalse(app.exception)
        self.assertTrue(any('Previously approved — requires revalidation' in x.value for x in app.warning))
        self.assertFalse(any('Already approved' in x.value for x in app.success))

    def test_store_change_invalidates_cached_approval_on_rerun(self):
        app=self.app();app.run();self.assertFalse(app.exception)
        store.save_governed_research_review(self.saved['result']['research_result_id'],
            result_fingerprint=self.saved['result']['result_fingerprint'],decision='reject',reviewer='ISOLATED TEST',db_path=self.db)
        app.run();self.assertFalse(app.exception)
        self.assertFalse(any('Already approved' in x.value for x in app.success))
        self.assertFalse(any('Approved — Ready' in x.value for x in app.success))

    def test_legacy_session_approval_without_recovery_key_is_not_trusted(self):
        app=self.app();app.run()
        key=next(k for k in app.session_state.filtered_state if k.endswith('_packet'))
        packet=deepcopy(app.session_state[key]);packet.pop('recovery_key')
        app.session_state[key]=packet
        store.save_governed_research_review(self.saved['result']['research_result_id'],
            result_fingerprint=self.saved['result']['result_fingerprint'],decision='reject',reviewer='ISOLATED TEST',db_path=self.db)
        app.run();self.assertFalse(app.exception)
        self.assertFalse(any('Already approved' in x.value for x in app.success))
        self.assertFalse(any('Approved — Ready' in x.value for x in app.success))
        self.assertTrue(next(b for b in app.button if b.label=='Approve validated draft').disabled)

    def test_fresh_sections_have_adjacent_results_and_only_collapsed_json(self):
        app=self.app();app.run()
        def click(label):next(b for b in app.button if b.label==label).click().run();self.assertFalse(app.exception)
        click('Inspect diagnostics');click('Preview proposed correction')
        blocks=[x for x in app if x.type in ('flex_container','vertical') and x.subheader]
        for heading in ('Inspect diagnostics','Preview proposed correction','Validate draft','Approve validated draft','Publish approved correction'):
            sections=[b for b in blocks if any(s.value==heading for s in b.subheader)]
            self.assertEqual(len(sections),1,heading)
            self.assertTrue(sections[0].markdown or sections[0].success or sections[0].caption)
        inspect=next(b for b in blocks if any(s.value=='Inspect diagnostics' for s in b.subheader))
        preview=next(b for b in blocks if any(s.value=='Preview proposed correction' for s in b.subheader))
        self.assertEqual(inspect.button[0].label,'Inspect diagnostics')
        self.assertEqual(preview.button[0].label,'Preview proposed correction')
        self.assertTrue(any('Before classification' in x.value for x in preview.markdown))
        self.assertTrue(any('After classification' in x.value for x in preview.markdown))
        self.assertTrue(any('Rule identifier' in x.value for x in preview.markdown))
        self.assertTrue(any('Already approved' in x.value for x in app.success))
        self.assertTrue(all(not x.proto.expanded for x in app.expander if x.label!='Unresolved Requirement Review'))
        # Every raw JSON node is inside one of the closed details expanders.
        self.assertEqual(len(app.json),sum(len(x.json) for x in app.expander if x.label!='Unresolved Requirement Review'))


if __name__=='__main__':unittest.main()

"""Pre/post knowledge and durable publication recovery; all writes disposable."""
from contextlib import closing, ExitStack
from copy import deepcopy
import hashlib
import importlib
import json
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from database import taxonomy_discovery_review_manager as store
from tailoring import capability_taxonomy as t
from taxonomy_discovery import governed_requirement_resolution as g, governed_publication as pub
from taxonomy_discovery import governed_review_recovery as recovery
from tests.governed_review_fixtures import isolated_taxonomy, write_taxonomy
from tests.test_governed_requirement_activation_v1_1 import isolated_lifecycle


class PostNativeTests(unittest.TestCase):
    def test_two_fixtures_are_exact_historical_release_and_restore_caches(self):
        previous=t.TAXONOMY_PATH;previous_default=t.get_default_taxonomy()
        with isolated_taxonomy() as path:
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),'da7b5e6952935a7dda88347c5af41eba65784b45da1c5b68f45a8768f605563e')
            self.assertEqual(g.resolve_requirement_with_production_knowledge({'text':'Design and develop RESTful APIs'})['status'],'unresolved')
            with isolated_taxonomy(published=True) as post:
                self.assertEqual(hashlib.sha256(post.read_bytes()).hexdigest(),'a8c4600445ae9d444f41801e47fc4e6895b97b8f58114042dcaf27de55f6b2c8')
                native=g.resolve_requirement_with_production_knowledge({'text':'Design and develop RESTful APIs'})
                self.assertEqual(native['knowledge_status'],'CAPABILITY_RESOLVED')
                self.assertEqual(native['taxonomy_diagnostics']['reason'],'approved_complete_rest_api_development_obligation')
                self.assertEqual(native['recognition_rule'],g.API_RECOGNITION_FALLBACK)
            self.assertEqual(t.TAXONOMY_PATH,path)
            self.assertEqual(t.get_default_taxonomy().version,'phase6d-capability-taxonomy-v1.5')
        self.assertEqual(t.TAXONOMY_PATH,previous)
        self.assertEqual(t.get_default_taxonomy(),previous_default)

    def test_existing_native_resolutions_and_compound_negative_boundaries(self):
        texts=['Read REST API documentation','Knowledge of REST APIs','C++ development',
               'Experience developing web services','Develop RESTful APIs and gRPC services',
               'Develop RESTful APIs or SQL databases','No API-development responsibility',
               'Market RESTful APIs','Build RESTful APIs for AWS']
        with isolated_taxonomy():
            before=[g.summarize(g.resolve_requirement_with_production_knowledge({'text':x})) for x in texts]
        with isolated_taxonomy(published=True):
            after=[g.summarize(g.resolve_requirement_with_production_knowledge({'text':x})) for x in texts]
            self.assertEqual(after,before)
            for text in texts:
                self.assertIsNone(t.classify_requirement_fallback_diagnostics({'text':text}),text)
            with self.assertRaisesRegex(ValueError,'already published'):
                g.preview(g.propose({'text':'Design and develop RESTful APIs'}),explicit_execution=True)


class PublishedRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.path=self.stack.enter_context(isolated_taxonomy());self.db=self.path.with_name('review.sqlite3')
        self.stack.enter_context(patch.dict('os.environ',{'TAXONOMY_DISCOVERY_REVIEW_DB':str(self.db)}))
        self.row,self.saved,self.regression=isolated_lifecycle(self.path.parent)
        self.identity={'discovered_job_id':146,'id':40,'job_content_hash':'isolated-test-source'}
        self.approval=store.save_governed_research_review(self.saved['result']['research_result_id'],
            result_fingerprint=self.saved['result']['result_fingerprint'],decision='approve_for_publication',
            reviewer='ISOLATED TEST REVIEWER',regression=self.regression,db_path=self.db)
        with patch.object(pub,'refresh_published_jobs',side_effect=AssertionError('No historical snapshot refresh')):
            self.receipt=pub.publish_approved_change(self.saved['result']['research_result_id'],explicit_publish=True,db_path=self.db)

    def app(self):
        app=AppTest.from_file(Path(__file__).with_name('governed_requirement_review_harness.py'),default_timeout=60)
        app.session_state['view']={'identity':self.identity,'provenance':'DISPOSABLE_POST_PUBLICATION',
                                   'requirements':[{'native':self.row}]}
        return app

    def recover(self):return recovery.recover(self.row,self.identity,db_path=self.db)

    def set_receipt(self,receipt):
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute('UPDATE governed_publications SET receipt_json=?',(json.dumps(receipt),));conn.commit()

    def test_completed_release_survives_its_own_version_fingerprint_change(self):
        self.assertNotEqual(self.regression['knowledge_fingerprint'],g.knowledge_fingerprint())
        self.assertNotEqual(self.regression['current_versions']['taxonomy_version'],g.current_match_versions()['taxonomy_version'])
        # The unpublished-draft preflight remains strictly stale; recovery uses
        # the completed receipt instead of weakening that authorization gate.
        self.assertFalse(pub.prepare_publication(self.saved['result']['research_result_id'],db_path=self.db)['ready'])
        found=self.recover();self.assertEqual(found['status'],'published')
        self.assertEqual(found['publication'],self.receipt)
        self.assertEqual(found['approval']['receipt'],self.approval)
        self.assertEqual(found['native']['knowledge_status'],'CAPABILITY_RESOLVED')
        self.assertEqual(found['blockers'],[])

    def test_restart_ui_no_mutation_no_replay_and_inspect_remains_available(self):
        before=(self.path.read_bytes(),self.db.read_bytes(),deepcopy(self.row))
        with ExitStack() as guards:
            for obj,name in [(g,'create_local_governed_draft'),(g,'validate_governed_draft'),
                             (store,'save_governed_research_review'),(pub,'publish_approved_change'),(pub,'refresh_published_jobs')]:
                guards.enter_context(patch.object(obj,name,side_effect=AssertionError('Read-only published recovery')))
            guards.enter_context(patch.object(g,'preview',side_effect=AssertionError('Published preview must be disabled')))
            from tailoring import unresolved_requirement_review_ui as ui
            for _ in range(2):
                importlib.reload(ui);app=self.app();app.run();self.assertFalse(app.exception)
                messages='\n'.join(x.value for x in app.success)
                self.assertIn('Published — taxonomy v1.6 active',messages)
                self.assertIn('Already published — correction active',messages)
                self.assertNotIn('Previously approved',messages)
                for label in ('Preview proposed correction','Validate draft','Approve validated draft','Publish approved correction'):
                    self.assertTrue(next(b for b in app.button if b.label==label).disabled,label)
                captions='\n'.join(x.value for x in app.caption)
                self.assertIn('Validate: completed → Approve: completed → Publish: completed',captions)
                self.assertNotIn('Preview is not approval',captions)
                self.assertFalse(any('requires revalidation' in x.value for x in app.warning))
                next(b for b in app.button if b.label=='Inspect diagnostics').click().run()
                self.assertFalse(app.exception)
                self.assertTrue(any('CAPABILITY_RESOLVED' in x.value for x in app.markdown))
                self.assertTrue(any(self.receipt['publication_id'] in x.value for x in app.markdown))
        self.assertEqual((self.path.read_bytes(),self.db.read_bytes(),self.row),before)

    def test_recovery_sql_is_read_only_and_no_writes_occur(self):
        connect=sqlite3.connect;before=self.db.read_bytes()
        forbidden={sqlite3.SQLITE_INSERT,sqlite3.SQLITE_UPDATE,sqlite3.SQLITE_DELETE,
                   sqlite3.SQLITE_CREATE_TABLE,sqlite3.SQLITE_DROP_TABLE,sqlite3.SQLITE_ALTER_TABLE}
        def readonly(*args,**kwargs):
            self.assertIn('mode=ro',args[0]);self.assertTrue(kwargs.get('uri'))
            conn=connect(*args,**kwargs)
            conn.set_authorizer(lambda action,*_:sqlite3.SQLITE_DENY if action in forbidden else sqlite3.SQLITE_OK)
            return conn
        with patch('sqlite3.connect',side_effect=readonly):self.assertEqual(self.recover()['status'],'published')
        self.assertEqual(self.db.read_bytes(),before)

    def test_wrong_receipt_link_capability_rule_hash_path_and_version_fail_closed(self):
        cases={'research_result_id':'wrong-result','draft_fingerprint':'wrong-draft','review_id':'wrong-approval',
               'artifact_hash_after':'wrong-hash','production_artifact':str(self.path.with_name('wrong.json')),
               'version_after':'phase6d-capability-taxonomy-v99.0','status':'prepared'}
        for key,value in cases.items():
            with self.subTest(field=key):
                changed={**self.receipt,key:value};self.set_receipt(changed)
                found=self.recover();self.assertEqual(found['status'],'publication_mismatch');self.assertTrue(found['blockers'])
        for key,value in [('capability_id','database.design'),('recognition_fallback_rules',[])]:
            changed=deepcopy(self.receipt);changed['change_applied'][key]=value;self.set_receipt(changed)
            self.assertEqual(self.recover()['status'],'publication_mismatch')
        self.set_receipt(self.receipt)

    def test_rule_without_receipt_is_not_publication_and_stale_draft_remains_blocked(self):
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute('DELETE FROM governed_publications');conn.commit()
        found=self.recover();self.assertEqual(found['status'],'stale')
        self.assertFalse(found['readiness']['ready'])
        self.assertNotIn('publication',found)

    def test_artifact_drift_blocks_ui_actions_even_with_rule_still_present(self):
        app=self.app();app.run();self.assertFalse(app.exception)
        self.assertTrue(any('correction active' in x.value for x in app.success))
        self.path.write_bytes(self.path.read_bytes()+b'\n')
        found=self.recover();self.assertEqual(found['status'],'publication_mismatch')
        self.assertIn('Publication artifact SHA-256 mismatch',found['blockers'])
        app.run();self.assertFalse(app.exception)
        self.assertTrue(any('receipt/artifact mismatch' in x.value for x in app.warning))
        self.assertFalse(any('correction active' in x.value for x in app.success))
        self.assertTrue(next(b for b in app.button if b.label=='Preview proposed correction').disabled)
        self.assertFalse(any(b.label=='Publish approved correction' and not b.disabled for b in app.button))

    def test_duplicate_publication_is_idempotent_not_a_second_release(self):
        before=(self.path.read_bytes(),self.db.read_bytes())
        with patch('database.technology_registry_proposal_manager._replace_knowledge',side_effect=AssertionError('No second publication')):
            receipt=pub.publish_approved_change(self.saved['result']['research_result_id'],explicit_publish=True,db_path=self.db)
        self.assertEqual(receipt,self.receipt)
        self.assertEqual(len(pub.list_publications(db_path=self.db)),1)
        self.assertEqual((self.path.read_bytes(),self.db.read_bytes()),before)
        with self.assertRaisesRegex(ValueError,'duplicate|already'):
            g.preview(g.propose(self.row),explicit_execution=True)


if __name__=='__main__':unittest.main()

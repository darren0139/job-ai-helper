"""Transaction and native-material regressions for explicit policy adoption."""
from __future__ import annotations
import copy
import hashlib
import json
import sqlite3
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from tailoring import phase9f_policy_adoption_v312b215c2 as a


def fake_modules(db, *, floor=True, fail=False):
    def binding(connection, **kw):
        if fail:
            raise RuntimeError('injected binding write failure')
        decision=kw['decision']; event={'event_id':'event1','event_type':kw['event_type'],'application_id':kw['application_id'],'decision_id':decision['decision_id'],'decision_fingerprint':decision['decision_fingerprint'],'event_details':kw['event_details']}
        event['event_fingerprint']=a._fingerprint(event)
        connection.execute('INSERT INTO application_blueprint_binding_events VALUES (?,?,?,?,?,?,?)',(event['event_id'],event['event_fingerprint'],event['event_type'],event['application_id'],event['decision_id'],event['decision_fingerprint'],json.dumps(event)))
    b=types.ModuleType('database.application_blueprint_manager');b._now=lambda:'2026-11-26T00:00:00';b._insert_binding_event=binding
    m=types.ModuleType('database.phase9f_tailoring_execution_manager');m._dump=json.dumps
    m._insert_event=lambda connection,**kw: connection.execute('INSERT INTO f_events VALUES (?)',(kw['event_type'],))
    r=types.ModuleType('database.phase9f_session_revision');r.execution_table=lambda *x:'f_ledger'
    f=types.ModuleType('tailoring.phase9f_v361_approval_floor');f.assess_phase9f_approval_floor=lambda *args,**kw:{'ready':floor}
    d=types.ModuleType('database');d.application_blueprint_manager=b;d.phase9f_tailoring_execution_manager=m
    return {'database':d,b.__name__:b,m.__name__:m,r.__name__:r,f.__name__:f}

class PureAdoptionTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:');self.db.row_factory=sqlite3.Row
        self.db.executescript('''CREATE TABLE application_tailoring_verifications(application_id INTEGER,verification_id TEXT,generation_id TEXT,phase8_version TEXT,verification_mode TEXT,verification_fingerprint TEXT,result_json TEXT,created_at TEXT);
        CREATE TABLE application_blueprint_binding_events(event_id TEXT,event_fingerprint TEXT,event_type TEXT,application_id INTEGER,decision_id TEXT,decision_fingerprint TEXT,event_json TEXT);
        CREATE TABLE f_ledger(execution_id TEXT,execution_fingerprint TEXT,generation_id TEXT,status TEXT,current_stage TEXT,stage_outputs_json TEXT,phase8_verification_id TEXT,phase8_verification_fingerprint TEXT,last_error_code TEXT,last_error_message TEXT,updated_at TEXT,completed_at TEXT);
        CREATE TABLE f_events(event_type TEXT);
        INSERT INTO f_ledger(execution_id,execution_fingerprint,status) VALUES ('f','ef','waiting_for_approval');''')
        self.material={'decision':{'decision_id':'d','decision_fingerprint':'df'},'execution':{'confirmed_intensity':'full','execution_fingerprint':'ef','confirmation_fingerprint':'cf','execution_id':'f','attempt_count':1,'stage_outputs':{'projects':{'retained':True}}},'generation':{'application_id':158,'generation_id':'g','status':'draft'},'source':{},'current_base':{},'preview':{'status':'native_preview_completed','application_id':158,'generation_id':'g','transition':{'previous_count':17,'current_count':12},'selected_base_docx_sha256':'a'*64,'final_docx_sha256':'b'*64,'prior_verification_id':'prior','starting_document_contract':{},'native_verdict':'improved'},'native_result':{'application_id':158,'generation_id':'g','phase8_version':'phase8','verification_mode':'native','verification_fingerprint':'new','comparison_valid':True,'fit_one_page':True,'verified_generation_snapshot_fingerprint':'snapshot'}}
        self.digest=a.preview_identity(self.material['preview'])
        a._insert_native_receipt(self.db,{**self.material['native_result'],'verification_fingerprint':'old'},'old');self.db.commit()
    def tearDown(self): self.db.close()
    def persist(self,**opts):
        with patch.dict(sys.modules,fake_modules(self.db,**opts)), patch.object(a,'_check_artifacts'),patch.object(a,'_validate_projection'):
            self.db.execute('BEGIN IMMEDIATE')
            try:
                result=a._persist_acceptance(self.db,material=self.material,reviewed_fingerprint=self.digest,actor_label='test');self.db.commit();return result
            except BaseException:
                self.db.rollback();raise
    def test_atomic_acceptance_preserves_history_and_identity(self):
        before=copy.deepcopy(self.material);r=self.persist();self.assertEqual(before,self.material)
        self.assertEqual(a._event_details(self.db,158,self.material['decision']),r)
        self.assertEqual(self.db.execute('SELECT count(*) FROM application_tailoring_verifications').fetchone()[0],2)
        row=self.db.execute('SELECT * FROM f_ledger').fetchone();self.assertEqual(row['execution_fingerprint'],'ef');self.assertIsNone(row['generation_id']);self.assertEqual(row['status'],'waiting_for_approval');self.assertEqual(json.loads(row['stage_outputs_json'])['projects'],{'retained':True})
        self.assertEqual(row['phase8_verification_id'],r['verification_id']);self.assertTrue(r['approval_floor_ready_at_acceptance'])
    def test_failure_rolls_back_receipt_and_execution(self):
        with self.assertRaisesRegex(RuntimeError,'injected'): self.persist(fail=True)
        self.assertEqual(self.db.execute('SELECT count(*) FROM application_tailoring_verifications').fetchone()[0],1)
        self.assertEqual(self.db.execute('SELECT count(*) FROM f_events').fetchone()[0],0)
        self.assertIsNone(self.db.execute('SELECT phase8_verification_id FROM f_ledger').fetchone()[0])
        self.assertIsNone(a._event_details(self.db,158,self.material['decision']))
    def test_no_floor_no_approval_pointer(self):
        r=self.persist(floor=False);self.assertFalse(r['approval_floor_ready_at_acceptance']);self.assertIsNone(self.db.execute('SELECT phase8_verification_id FROM f_ledger').fetchone()[0])
    def test_event_checksum_and_duplicate(self):
        self.persist()
        with self.assertRaisesRegex(ValueError,'already accepted'):self.persist()
        self.db.execute("UPDATE application_blueprint_binding_events SET event_json=replace(event_json,'improved','changed')")
        with self.assertRaisesRegex(ValueError,'checksum'):a._event_details(self.db,158,self.material['decision'])
    def test_recheck_identity_and_minor_hold(self):
        self.material['preview']['native_verdict']='changed'
        with self.assertRaisesRegex(ValueError,'recheck changed'):self.persist()
        self.material['preview']['native_verdict']='improved';self.material['execution']['confirmed_intensity']='minor'
        with self.assertRaisesRegex(ValueError,'Full'):self.persist()
    def test_native_receipt_idempotence_and_collision(self):
        r=self.material['native_result'];x=a._insert_native_receipt(self.db,r,'now');y=a._insert_native_receipt(self.db,r,'later');self.assertEqual(x,y)
        with self.assertRaisesRegex(ValueError,'identity differs'):a._insert_native_receipt(self.db,{**r,'comparison_valid':False},'now')
    def test_no_implicit_acceptance(self):
        with self.assertRaisesRegex(ValueError,'Explicit'):a.accept_policy_transition(158,'g',reviewed_fingerprint=self.digest,explicitly_confirmed=False)
    def test_missing_persisted_decision_identity_never_opens_database(self):
        modules=fake_modules(self.db)
        bindings=modules['database.application_blueprint_manager']
        with patch.dict(sys.modules,modules), patch.object(bindings,'_connect',create=True,side_effect=AssertionError('unexpected DB access')) as connect:
            for decision in ({}, {'decision_id':'d'}, {'decision_fingerprint':'df'}, {'decision_id':'','decision_fingerprint':'df'}, {'decision_id':'d','decision_fingerprint':' '}, {'decision_id':1,'decision_fingerprint':'df'}):
                with self.subTest(decision=decision):
                    self.assertIsNone(a.read_accepted_transition(application_id=158,decision=decision,exact_jd={}))
            connect.assert_not_called()
    def test_persisted_decision_without_event_is_not_accepted(self):
        modules=fake_modules(self.db)
        modules['database.application_blueprint_manager']._connect=lambda:self.db
        with patch.dict(sys.modules,modules):
            self.assertIsNone(a.read_accepted_transition(application_id=158,decision=self.material['decision'],exact_jd={}))
    def test_corrupted_event_public_reader_fails_closed(self):
        self.persist()
        self.db.execute("UPDATE application_blueprint_binding_events SET event_json=replace(event_json,'improved','changed')")
        self.db.commit()
        modules=fake_modules(self.db)
        modules['database.application_blueprint_manager']._connect=lambda:self.db
        with patch.dict(sys.modules,modules):
            with self.assertRaisesRegex(ValueError,'checksum'):
                a.read_accepted_transition(application_id=158,decision=self.material['decision'],exact_jd={})
    def test_db_blob_source_and_changed_final(self):
        data=b'base bytes';sha=hashlib.sha256(data).hexdigest();self.material['source']={'artifact_bytes':data,'byte_size':len(data),'sha256':sha,'source_path':''};self.material['execution']['source_artifact']={};self.material['confirmation']={};self.material['preview']['selected_base_docx_sha256']=sha
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'final.docx';p.write_bytes(b'final bytes');self.material['generation']['fit_result']={'docx_path':str(p)};self.material['preview']['final_docx_sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
            modules=fake_modules(self.db);modules['database.phase9f_tailoring_execution_manager']._resolve_prepared_source_artifact=lambda **kw: self.material['source']
            with patch.dict(sys.modules,modules):
                a._check_artifacts(self.material);p.write_bytes(b'tampered')
                with self.assertRaisesRegex(ValueError,'fitted DOCX changed'):a._check_artifacts(self.material)

class NativeMaterialTests(unittest.TestCase):
    def test_native_material_projection_and_floor(self):
        from tests.test_v312b215c_policy_transition import NativeTransitionTests
        from tailoring import phase9f_policy_transition_v312b215c as t
        from tailoring.phase9f_v361_approval_floor import assess_phase9f_approval_floor
        original=t.build_preview;captured=[]
        def wrapped(**kw):
            material=original(**kw,_return_material=True);captured.append(material)
            a._validate_projection(material['current_base'],material['preview']['transition'],material['preview']['starting_document_contract'])
            receipt=material['native_result'];self.assertEqual(receipt['verification_mode'],'selected_base_docx_vs_final_docx');self.assertEqual(receipt['comparison'],material['preview']['native_comparison']);self.assertTrue(assess_phase9f_approval_floor(receipt,generation_id=receipt['generation_id'],docx_sha256=material['preview']['final_docx_sha256'])['ready'])
            return material['preview']
        with patch.object(t,'build_preview',side_effect=wrapped): NativeTransitionTests('test_real_ncs_native_recheck_keeps_document_and_history').test_real_ncs_native_recheck_keeps_document_and_history()
        self.assertEqual(len(captured),1)

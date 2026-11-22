"""Synthetic, disposable same-application revision/approval contracts."""
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import unittest

import tests.test_phase9f_tailoring_execution as support
from tests.phase9f_d_test_support import build_scope
from tests.phase9f_e_test_support import phase9f_projects_for_document_verification, phase9f_skills_for_document_verification
from tests.test_phase9f_starting_source_ranking import resume_profile, resume_text, write_resume_artifacts
from database import global_master_resume_manager as master
from database.phase9f_application_confirmation_manager import confirm_phase9f_application_session, get_phase9f_application_confirmation
from database import phase9f_tailoring_execution_manager as execution
from database.application_blueprint_manager import evaluate_and_bind_application_blueprint
from database.tailoring_generation_control import approve_tailoring_generation, get_tailoring_generation, list_tailoring_generations
from tailoring.phase9f_master_resume import inspect_master_resume_upload, build_prepared_master_resume_snapshot


def register_b(folder):
    folder.mkdir(exist_ok=True)
    profile=resume_profile(strong=True,marker='Guarded Base B')
    docx,_=write_resume_artifacts(folder,resume_text(profile))
    prepared=build_prepared_master_resume_snapshot(
        inspection=inspect_master_resume_upload(filename='base-b.docx',content=docx.read_bytes()),
        structured_profile=profile, extraction_provenance={'method':'synthetic-public-fixture','call_count':0,'embedding_call_count':0},
        current_master=master.get_current_global_master_resume(),preparation_mode='synthetic-zero-cost-fixture')
    return master.commit_prepared_global_master_resume(prepared,display_name='Guarded Base B',actor_label='Synthetic test'),docx


class SessionRevision(unittest.TestCase):
    def setUp(self):
        self.fixture=support.Phase9FTailoringExecutionTests();self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.a=self.fixture._session('full')
        self.app=self.a['application_id']
        self.fixture._add_evidence(1)
        self.writer_profiles=[]

    def confirm_b(self):
        self.base_b,self.bdocx=register_b(self.fixture.root/'base-b')
        original=self.a['confirmation']['confirmation_snapshot']['phase9f_a_snapshot']
        ranking,recommendation=build_scope(self.fixture.database_path,phase9f_a_snapshot=original)
        b=next(r for r in ranking['ranked_candidates'] if r['source_type']=='base_resume')
        self.args=dict(phase9f_a_snapshot=original,persisted_exact_jd_snapshot=self.a['persisted_jd'],ranking_result=ranking,
            phase9f_c_recommendation=recommendation,confirmed_normalized_source_fingerprint=b['normalized_source_fingerprint'],
            confirmed_intensity='full',application_intent_id='same-application-revision',existing_application_id=self.app,
            reconfirm_confirmation_id=self.a['confirmation']['confirmation_id'])
        return confirm_phase9f_application_session(**self.args)

    def run_generation(self):
        def projects(**kw):
            self.writer_profiles.append(deepcopy(kw['resume_profile']))
            return phase9f_projects_for_document_verification(kw['resume_profile'])
        return execution.run_phase9f_normal_generation(application_id=self.app,generation_settings={'max_projects':4},generation_model='synthetic',
            projects_writer=projects,
            skills_writer=lambda **kw:phase9f_skills_for_document_verification(kw['resume_profile']))

    def test_new_confirmation_keeps_original_and_rejects_legacy_binding(self):
        original=deepcopy(self.a['confirmation'])
        b=self.confirm_b()['confirmation']
        self.assertEqual(b['application_id'],self.app)
        self.assertNotEqual(b['confirmation_id'],original['confirmation_id'])
        self.assertEqual(get_phase9f_application_confirmation(self.app),b)
        self.assertEqual(get_phase9f_application_confirmation(self.app,confirmation_id=original['confirmation_id']),original)
        with self.assertRaisesRegex(ValueError,'guarded Phase 9F'):
            evaluate_and_bind_application_blueprint(application_id=self.app,scope_replacement_confirmed=True,selected_source='base_resume')
        with self.assertRaisesRegex(ValueError,'changed; review'):
            confirm_phase9f_application_session(**self.args)

    def test_two_guarded_generations_own_their_sources_and_incomplete_approval_fails(self):
        ga=self.run_generation()['generation'];ea=deepcopy(execution.get_phase9f_tailoring_execution(self.app))
        b=self.confirm_b()['confirmation'];gb=self.run_generation()['generation'];eb=execution.get_phase9f_tailoring_execution(self.app)
        self.assertEqual(ga,get_tailoring_generation(self.app,ga['generation_id']))
        self.assertNotEqual(ea['execution_id'],eb['execution_id'])
        self.assertEqual(execution.get_phase9f_tailoring_execution(self.app,generation_id=ga['generation_id']),ea)
        self.assertEqual(eb['confirmation_id'],b['confirmation_id'])
        self.assertEqual(len(list_tailoring_generations(self.app)),2)
        self.assertIn('Guarded Base B',self.writer_profiles[-1]['name'])
        self.assertNotEqual(ea['source_artifact']['sha256'],eb['source_artifact']['sha256'])
        self.assertEqual(gb['phase9e_decision_fingerprint'],b['phase9e_decision_fingerprint'])
        with self.assertRaisesRegex(ValueError,'incomplete|one-page'):
            approve_tailoring_generation(self.app,gb['generation_id'])
        self.assertEqual(get_tailoring_generation(self.app,gb['generation_id'])['status'],'draft')

    def test_fitted_history_and_new_base_require_fresh_document_verification(self):
        import hashlib
        from tests.phase9f_e_test_support import write_phase9f_document_verification_fit
        from database.tailoring_verification_manager import get_latest_tailoring_verification
        from tailoring.phase9f_v361_approval_floor import verify_current_phase9f_floor
        ga=self.run_generation()['generation']
        a_doc=self.fixture.root/'a-final.docx';a_pdf=self.fixture.root/'a-final.pdf'
        execution.run_phase9f_normal_fit(application_id=self.app,generation_id=ga['generation_id'],
            fit_writer=lambda **kw:write_phase9f_document_verification_fit(self.a['blueprint']['docx_path'],a_doc,a_pdf,**kw))
        execution.run_or_reuse_phase9f_normal_generation_phase8(application_id=self.app,generation_id=ga['generation_id'])
        frozen=deepcopy(get_tailoring_generation(self.app,ga['generation_id']))
        receipt=deepcopy(get_latest_tailoring_verification(self.app,ga['generation_id']))
        frozen_bytes=(a_doc.read_bytes(),a_pdf.read_bytes())
        ea=deepcopy(execution.get_phase9f_tailoring_execution(self.app))
        self.confirm_b();gb=self.run_generation()['generation']
        with self.assertRaises(ValueError):approve_tailoring_generation(self.app,gb['generation_id'])
        b_doc=self.fixture.root/'b-final.docx';b_pdf=self.fixture.root/'b-final.pdf'
        fitted=execution.run_phase9f_normal_fit(application_id=self.app,generation_id=gb['generation_id'],
            fit_writer=lambda **kw:write_phase9f_document_verification_fit(self.bdocx,b_doc,b_pdf,**kw))
        with self.assertRaisesRegex(ValueError,'verification|gate|floor'):
            approve_tailoring_generation(self.app,gb['generation_id'])
        verified=execution.run_or_reuse_phase9f_normal_generation_phase8(application_id=self.app,generation_id=gb['generation_id'])
        self.assertTrue(verified['verification']['approval_ready'],verified['verification'])
        self.assertTrue(verify_current_phase9f_floor(self.app,gb['generation_id'],fitted['generation'])['ready'])
        b_doc.write_bytes(b_doc.read_bytes()+b' changed bytes')
        with self.assertRaises(ValueError):approve_tailoring_generation(self.app,gb['generation_id'])
        self.assertEqual(get_tailoring_generation(self.app,gb['generation_id'])['status'],'draft')
        self.assertEqual(get_tailoring_generation(self.app,ga['generation_id']),frozen)
        self.assertEqual(get_latest_tailoring_verification(self.app,ga['generation_id']),receipt)
        self.assertEqual((a_doc.read_bytes(),a_pdf.read_bytes()),frozen_bytes)
        self.assertEqual(execution.get_phase9f_tailoring_execution(self.app,generation_id=ga['generation_id']),ea)
        self.assertTrue(verify_current_phase9f_floor(self.app,ga['generation_id'],frozen)['ready'])

    def test_lost_lifecycle_metadata_does_not_enable_legacy_approval(self):
        import json
        from database import tailoring_version_manager
        self.confirm_b();generation=self.run_generation()['generation']
        settings=deepcopy(generation['generation_settings']);settings.pop('phase9f_f_normal_lifecycle')
        connection=tailoring_version_manager._connect()
        try:
            connection.execute('UPDATE application_tailoring_versions SET generation_settings_json=? WHERE application_id=? AND generation_id=?',
                (json.dumps(settings),self.app,generation['generation_id']))
            connection.commit()
        finally:connection.close()
        with self.assertRaisesRegex(ValueError,'legacy approval is forbidden'):
            approve_tailoring_generation(self.app,generation['generation_id'])
        self.assertEqual(get_tailoring_generation(self.app,generation['generation_id'])['status'],'draft')

if __name__=='__main__':unittest.main()

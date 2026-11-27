"""Scope and append-only receipt chain tests, plus actual successor native replay."""
import copy
import json
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tailoring import phase9f_policy_transition_v312b215c as t
from tailoring import phase9f_policy_adoption_v312b215c2 as a
from tailoring.phase9f_scoring_policy_registry_v312b2190 import B215, B219A, B219B, LEGACY, policy_path, needs_exact_recheck, enforce_fresh_receipt
from tests.test_v312b215c_policy_transition import _row, _snapshot, _decision
from tests import test_v312b215c2_policy_adoption as fixtures

class PureLifecycle(unittest.TestCase):
    def setUp(self):
        self.rows = [_row('a','Python'),_row('b','Unit testing')]
        self.old = _snapshot(self.rows)
        self.decision = _decision(self.old)
        self.decision['comparison']['stable_analysis_snapshot']['scoring_version'] = B215
    def classify(self, active=B219A, current=None):
        return t.classify_transition(decision=self.decision,current_jd=current or self.old,active_scorer=active)
    def test_registered_exact_edges_only(self):
        self.assertEqual(policy_path(B215,B219A),(B215,B219A))
        for old in LEGACY:self.assertEqual(policy_path(old,B219A),(old,B215,B219A))
        for old,new in [(B219A,B215),(B215,B219A+'-unknown'),(B215,B215),('fake',B219A)]:self.assertIsNone(policy_path(old,new))
    def test_same_scope_no_rewrite(self):
        before=copy.deepcopy(self.decision); result=self.classify()
        self.assertEqual(result['previous_count'],result['current_count']);self.assertEqual(result['removed_requirements'],[]);self.assertEqual(before,self.decision)
        self.assertTrue(needs_exact_recheck(self.decision,B219A));self.assertFalse(needs_exact_recheck(self.decision,B215))
    def test_current_reviewed_scope_is_not_misclassified_as_upgrade(self):
        stable=self.decision['comparison']['stable_analysis_snapshot'];stable.update(scoring_version=B219A+'+scope',matching_policy_identity='scope')
        self.assertFalse(needs_exact_recheck(self.decision,B219A))
        self.assertTrue(needs_exact_recheck(self.decision,B219A+'-next'))
    def test_scope_change_rejected_for_scoring_only(self):
        for rows in ([self.rows[0]],[*self.rows,_row('c','Java')],[_row('a','Python','preferred'),self.rows[1]],[_row('a','Python scripting'),self.rows[1]]):
            with self.subTest(rows=rows),self.assertRaises(ValueError):self.classify(current=_snapshot(rows))
    def test_unknown_or_reversed_upgrade_rejected(self):
        with self.assertRaises(ValueError):self.classify(active=B219A+'-future')
        self.decision['comparison']['stable_analysis_snapshot']['scoring_version']=B219A
        with self.assertRaises(ValueError):self.classify(active=B215)
    def test_legacy_removal_path_and_equal_scope(self):
        self.decision['comparison']['stable_analysis_snapshot']['scoring_version']=sorted(LEGACY)[0]
        self.assertEqual(self.classify(current=_snapshot(self.rows[:1]))['current_count'],1)
        self.assertEqual(self.classify()['current_count'],2)
        with self.assertRaises(ValueError):self.classify(active=B215)
    def test_jd_changes_and_custom_scope_still_rejected(self):
        with self.assertRaises(ValueError):self.classify(current=_snapshot(self.rows,raw='Different text'))
        self.decision['comparison']['stable_analysis_snapshot']['matching_policy_identity']={'review':True}
        with self.assertRaises(ValueError):self.classify()
    def test_future_freshness_gate_does_not_depend_on_suffix(self):
        self.assertTrue(enforce_fresh_receipt(B219A));self.assertTrue(enforce_fresh_receipt(B215));self.assertTrue(enforce_fresh_receipt(B219A+'-future'))
        self.assertFalse(enforce_fresh_receipt('stable-evidence-v1.16-phase6d20'))

    def _preview_path_fixture(self, *, mutate=False):
        # Real on-disk bytes and real preview/authentication code. Stub only
        # downstream native engines so this also runs in the isolated self-test.
        import sys
        from types import ModuleType
        for original, current, prior_version in (
            (sorted(LEGACY)[0], B215, sorted(LEGACY)[0]),
            (B215, B219A, B215),
            (sorted(LEGACY)[0], B219A, B215),
        ):
            with self.subTest(original=original, current=current, prior=prior_version), tempfile.TemporaryDirectory() as td:
                old_rows = copy.deepcopy(self.rows)
                new_rows = old_rows[:1] if original in LEGACY else old_rows
                old = _snapshot(old_rows)
                new = _snapshot(new_rows)
                decision = _decision(old)
                decision['comparison']['stable_analysis_snapshot']['scoring_version'] = original
                tr = t.classify_transition(decision=decision, current_jd=new, active_scorer=current)
                path = Path(td) / 'fitted.docx'
                data = b'exact fitted bytes for preview boundary test'
                path.write_bytes(data)
                sha = hashlib.sha256(data).hexdigest()
                gen = {'application_id': 1, 'generation_id': 'fitted', 'status': 'draft', 'fit_result': {'docx_path': str(path), 'fit_one_page': True, 'page_count': 1}}
                old_stable = {'scoring_version': original, 'canonical_requirements': old_rows}
                prior_stable = {'scoring_version': prior_version, 'canonical_requirements': old_rows if prior_version in LEGACY else new_rows}
                new_stable = {'scoring_version': current, 'canonical_requirements': new_rows}
                baseline = {'raw_jd_text': old['raw_text'], 'stable_analysis': old_stable}
                prior = {'application_id': 1, 'generation_id': 'fitted', 'comparison_valid': True, 'verified_generation_snapshot_fingerprint': 'snap', 'document_analysis': {'final_document_sha256': sha}, 'starting_document_contract': {'selected_base_docx_sha256': sha}, 'before_stable_analysis': prior_stable, 'after_stable_analysis': prior_stable}
                contract = {'selected_base_docx_sha256': sha, 'scoring_scope_refresh': {'removed_ids': [r['requirement_id'] for r in tr['removed_requirements']], 'added_ids': [], 'current_count': len(new_rows)}}
                result = {'comparison_valid': True, 'comparison': {}, 'document_analysis': {'final_document_sha256': sha}, 'verified_generation_snapshot_fingerprint': 'snap', 'before_stable_analysis': new_stable, 'after_stable_analysis': new_stable, 'job_match_ab': {}}
                def native(**kwargs):
                    if mutate:
                        path.write_bytes(b'changed during scoring')
                    return copy.deepcopy(result)
                phase8 = ModuleType('tailoring.phase8_verification')
                phase8.build_phase8_verification = native
                phase8.build_phase8_generation_snapshot_fingerprint = lambda generation: 'snap'
                readback = ModuleType('tailoring.phase9f_v364_document_reverify')
                readback.build_frozen_selected_base_document_report = lambda **kwargs: ({}, contract)
                with patch.dict(sys.modules, {'tailoring.phase8_verification': phase8, 'tailoring.phase9f_v364_document_reverify': readback}):
                    kwargs = dict(transition=tr, baseline_report=baseline, generation=gen, source_artifact={'sha256': sha}, prior=prior)
                    if mutate:
                        with self.assertRaisesRegex(ValueError, 'Fitted DOCX changed during verification'):
                            t.build_preview(**kwargs)
                    else:
                        preview = t.build_preview(**kwargs)
                        self.assertEqual(preview['final_docx_sha256'], sha)
                        self.assertFalse(preview['saved_as_phase8'])
                        self.assertEqual(path.read_bytes(), data)

    def test_preview_preserves_fitted_path_across_policy_iteration(self):
        self._preview_path_fixture()

    def test_preview_rejects_document_mutation_after_native_scoring(self):
        self._preview_path_fixture(mutate=True)

class ChainTransactions(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.PureAdoptionTests('test_atomic_acceptance_preserves_history_and_identity');self.fixture.setUp();self.addCleanup(self.fixture.tearDown)
        self.db=self.fixture.db;self.material=self.fixture.material
        rows=[_row('a','Python'),_row('b','Footer')];old=_snapshot(rows);new=_snapshot(rows[:1]);decision=_decision(old)
        self.first_transition=t.classify_transition(decision=decision,current_jd=new,active_scorer=B215)
        self.next_transition=t.classify_transition(decision=decision,current_jd=new,active_scorer=B219A)
        self.material['preview']['transition']=self.first_transition;self.fixture.digest=a.preview_identity(self.material['preview'])
        self.parent=self.fixture.persist();self.first_event=self.db.execute('SELECT event_json FROM application_blueprint_binding_events').fetchone()[0]
    def prepare(self):
        p=self.material['preview'];p['transition']=copy.deepcopy(self.next_transition);p['previous_acceptance_fingerprint']=self.parent['acceptance_fingerprint'];p['prior_verification_id']=self.parent['verification_id'];self.material['native_result']['verification_fingerprint']='successor-native';self.fixture.digest=a.preview_identity(p)
    def test_second_acceptance_appends_preserves_first(self):
        self.prepare();child=self.fixture.persist();self.assertEqual(child['previous_acceptance_fingerprint'],self.parent['acceptance_fingerprint']);self.assertEqual(a._event_details(self.db,158,self.material['decision']),child)
        rows=self.db.execute('SELECT event_json FROM application_blueprint_binding_events').fetchall();self.assertEqual(len(rows),2);self.assertIn(self.first_event,[r[0] for r in rows]);self.assertEqual(self.db.execute('SELECT count(*) FROM application_tailoring_verifications').fetchone()[0],3)
        with self.assertRaisesRegex(ValueError,'already accepted'):self.fixture.persist()
    def test_second_acceptance_rolls_back(self):
        self.prepare()
        with self.assertRaisesRegex(RuntimeError,'injected'):self.fixture.persist(fail=True)
        self.assertEqual(a._event_details(self.db,158,self.material['decision']),self.parent);self.assertEqual(self.db.execute('SELECT count(*) FROM application_tailoring_verifications').fetchone()[0],2)
    def test_parent_mismatch_rejected(self):
        self.prepare();self.material['preview']['previous_acceptance_fingerprint']='wrong';self.fixture.digest=a.preview_identity(self.material['preview'])
        with self.assertRaisesRegex(ValueError,'predecessor changed'):self.fixture.persist()
    def test_scope_change_against_parent_rejected(self):
        self.prepare();self.material['preview']['transition']['new_scope_fingerprint']='other';self.fixture.digest=a.preview_identity(self.material['preview'])
        with self.assertRaisesRegex(ValueError,'predecessor scope changed'):self.fixture.persist()
    def test_tampered_ancestor_rejected(self):
        self.prepare();self.fixture.persist();self.db.execute("UPDATE application_blueprint_binding_events SET event_json=replace(event_json,'improved','changed') WHERE event_json=?",(self.first_event,))
        with self.assertRaisesRegex(ValueError,'checksum'):a._event_details(self.db,158,self.material['decision'])
    def test_missing_ancestor_rejected(self):
        self.prepare();self.fixture.persist();self.db.execute('DELETE FROM application_blueprint_binding_events WHERE event_json=?',(self.first_event,))
        with self.assertRaisesRegex(ValueError,'Missing original'):a._event_details(self.db,158,self.material['decision'])
    def test_duplicate_or_forked_chain_rejected(self):
        self.prepare();self.fixture.persist();self.db.execute('INSERT INTO application_blueprint_binding_events SELECT * FROM application_blueprint_binding_events WHERE event_json=?',(self.first_event,))
        with self.assertRaisesRegex(ValueError,'Duplicate or forked'):a._event_details(self.db,158,self.material['decision'])
    def test_failed_native_floor_never_advances_pointer(self):
        self.prepare();child=self.fixture.persist(floor=False);self.assertFalse(child['approval_floor_ready_at_acceptance']);self.assertEqual(self.db.execute('SELECT phase8_verification_id FROM f_ledger').fetchone()[0],self.parent['verification_id'])

class NativeSuccessor(unittest.TestCase):
    def test_new_policy_replays_same_scope_and_prior_adoption(self):
        # This test is run in a disposable source copy with the actual accepted
        # B2.19a candidate installed, never by monkeypatching native score values.
        from analysis_stability import stable_evidence_scoring as scorer
        from tailoring.phase8_verification import build_phase8_generation_snapshot_fingerprint
        from tailoring.phase8_auto_verification import _matches_active_scoring_policy
        from tests.test_v312b215_jd_eligibility import JD, PROFILE, OLD, REMOVED, make_handoff_fixture_docx
        import os
        if scorer.SCORING_VERSION not in (B219A,B219B) and os.getenv('B2190_REQUIRE_SUCCESSOR') != '1':
            self.skipTest('Successor scoring policy is not active; installer tests its disposable overlay')
        target=scorer.SCORING_VERSION
        self.assertIn(target,(B219A,B219B))
        predecessor=B219A if target==B219B else B215
        self.assertFalse(_matches_active_scoring_policy({'after_stable_analysis':{'scoring_version':B215}}))
        self.assertTrue(_matches_active_scoring_policy({'after_stable_analysis':{'scoring_version':target}}))
        from tailoring.phase8_verification import refresh_phase8_readiness
        with patch('tailoring.phase8_verification.document_artifact_is_current',return_value=True):
            with self.assertRaisesRegex(ValueError,'Scoring policy changed'):
                refresh_phase8_readiness({'after_stable_analysis':{'scoring_version':B215}}, {})
        with patch.object(scorer,'_V312A17_RUNTIME_ACTIVE',False):old_rows=scorer.canonicalise_requirements(PROFILE,JD)['requirements']
        new_rows=scorer.canonicalise_requirements(PROFILE,JD)['requirements'];self.assertEqual(len(new_rows),12);self.assertEqual(len(old_rows),17)
        for version,rows in (((B219A,new_rows),(B215,new_rows),(OLD,old_rows)) if target==B219B else ((B215,new_rows),(OLD,old_rows))):
            with self.subTest(version=version),tempfile.TemporaryDirectory() as td:
                old=_snapshot(rows,JD);current=_snapshot(new_rows,JD);old['jd_profile']=copy.deepcopy(PROFILE);current['jd_profile']=copy.deepcopy(PROFILE)
                decision=_decision(old);decision['comparison']['stable_analysis_snapshot']['scoring_version']=version
                tr=t.classify_transition(decision=decision,current_jd=current,active_scorer=target)
                base=Path(td)/'base.docx';final=Path(td)/'final.docx';text=make_handoff_fixture_docx(base);data=base.read_bytes();final.write_bytes(data);sha=hashlib.sha256(data).hexdigest()
                profile={'name':'Synthetic Software Engineer','skills':{'Tools':['Unity','C#']},'projects':[],'education':[],'experience':[]}
                baseline={'raw_jd_text':JD,'jd_profile':PROFILE,'raw_resume_text':text,'resume_profile':profile,'stable_analysis':{'scoring_version':version,'canonical_requirements':rows},'meta':{}}
                gen={'application_id':1,'generation_id':'synthetic-fitted','status':'draft','projects':{'recommended_projects':[]},'skills':{'skill_lines':[{'category':'Tools','items':['Unity','C#']}]},'fit_result':{'docx_path':str(final),'fit_one_page':True,'page_count':1}}
                prior_stable={'scoring_version':predecessor,'canonical_requirements':new_rows}
                prior={'application_id':1,'generation_id':gen['generation_id'],'comparison_valid':True,'verified_generation_snapshot_fingerprint':build_phase8_generation_snapshot_fingerprint(gen),'document_analysis':{'final_document_sha256':sha},'starting_document_contract':{'selected_base_docx_sha256':sha},'before_stable_analysis':prior_stable,'after_stable_analysis':prior_stable}
                before=copy.deepcopy((baseline,gen,prior));material=t.build_preview(transition=tr,baseline_report=baseline,generation=gen,source_artifact={'artifact_type':'docx','artifact_bytes':data,'sha256':sha,'byte_size':len(data)},prior=prior,_return_material=True)
                preview=material['preview'];self.assertFalse(preview['approval_ready']);self.assertFalse(preview['saved_as_phase8']);self.assertEqual(preview['native_after_analysis']['scoring_version'],target);self.assertEqual(len(preview['native_after_analysis']['canonical_requirements']),12)
                a._validate_projection(material['current_base'],tr,preview['starting_document_contract']);self.assertEqual((baseline,gen,prior),before);self.assertEqual(final.read_bytes(),data);self.assertEqual(base.read_bytes(),data)

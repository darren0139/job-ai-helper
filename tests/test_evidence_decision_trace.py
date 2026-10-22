"""Independent trace attribution controls; no new scoring expectations."""
from copy import deepcopy
from dataclasses import replace
from io import BytesIO, StringIO
import csv
import hashlib
import json
import unittest
from unittest.mock import patch
import zipfile

from job_discovery import evidence_decision_trace as trace, evidence_trace_ui as ui
from job_discovery import developer_debug_export as debug, developer_real_comparison as real
from tests import test_comparison_debug_dashboard as support


class TraceTests(unittest.TestCase):
    setUpClass=classmethod(support.DebugDashboardTests.setUpClass.__func__)
    setUp=support.DebugDashboardTests.setUp
    retained=support.DebugDashboardTests.retained
    page=support.DebugDashboardTests.page

    def packet(self):
        loaded,result=self.retained()
        return loaded,result,trace.build(loaded['request'],result['comparison'])

    def test_pure_trace_preserves_both_scorers_and_all_identities(self):
        loaded,result=self.retained(); request=deepcopy(loaded['request']); c=deepcopy(result['comparison'])
        before=self.path.read_bytes()
        with patch.object(real.preview.native,'build_stable_analysis',side_effect=AssertionError('No scoring')), \
             patch.object(real.preview.gated,'build_coordinated_analysis',side_effect=AssertionError('No scoring')), \
             patch.object(real.preview.native,'build_deterministic_keyword_match',side_effect=AssertionError('No new matching')), \
             patch('database.db_manager._connect',side_effect=AssertionError('No database')):
            data=trace.build(request,c)
        self.assertEqual(request,loaded['request']); self.assertEqual(c,result['comparison'])
        self.assertEqual(before,self.path.read_bytes())
        self.assertEqual({r['requirement_id'] for r in data['requirements']},
            {r.requirement_id for v in (c.published,c.gated) for r in v.requirements})
        self.assertEqual(data['input_identity'],request.identity)
        self.assertFalse(data['coverage']['native_matching_rerun'])

    def test_original_ownership_and_absent_trace_are_not_rejection(self):
        _,_,data=self.packet()
        # Independently authored E04 fixture: project=100, unrelated experience=101,
        # unscoped skills=900. No cross-record acceptance from wording aliases.
        self.assertEqual({p['library_item_id'] for p in data['matrix']},{100,101,900})
        for row in data['requirements']:
            for value in row['sides'].values():
                if value['status']=='ABSENT_REQUIREMENT_GEOMETRY': continue
                self.assertEqual(value['original_records'],3)
                self.assertEqual(value['considered_total'],trace.UNKNOWN)
                self.assertEqual(value['rejected_total'],trace.UNKNOWN)
                for pair in value['records']:
                    if pair['considered']==trace.UNKNOWN:
                        self.assertEqual(pair['rejected'],trace.UNKNOWN)
                        self.assertIn(trace.UNKNOWN,pair['statuses'])
                    if pair['action_proofs'] and pair['library_item_id']==101:
                        self.assertFalse(any(p['admission']=='COMPLETE' for p in pair['action_proofs']))
                    self.assertIsNone(pair['evaluated_threshold'])
                    self.assertIsNone(pair['candidate_score'])

    def test_conflict_review_is_null_not_original_candidate_acceptance(self):
        _,_,data=self.packet()
        conflicts=[r['sides']['experimental'] for r in data['requirements']
            if r['sides']['experimental'].get('contradiction_quarantined')]
        self.assertTrue(conflicts)  # independent E04 same-project contradiction control
        for row in conflicts:
            self.assertEqual(row['label'],'REVIEW_REQUIRED'); self.assertIsNone(row['credit'])
            self.assertEqual(row['admitted_records'],0)
            self.assertFalse(any(p['accepted'] for p in row['records']))
            self.assertTrue(any(p['events'] for p in row['records']))

    def test_threshold_reference_is_exact_but_not_an_evaluated_default(self):
        _,_,data=self.packet(); config=data['configured_threshold_reference']
        self.assertEqual((config['score'],config['coverage'],config['overlap']),(0.28,0.25,2))
        self.assertEqual(config['role'],'CONFIGURED_ONLY_NOT_PROOF_OF_EVALUATION')
        self.assertTrue(all(p['candidate_score'] is None for r in data['requirements']
            for s in r['sides'].values() for p in s.get('records',[])))

    def test_native_audits_copy_only_observed_success_metrics(self):
        for name,status in (('capability_none_recovery','recovered_from_none'),
                            ('capability_evidence_reselection','stronger_single_row_selected')):
            self.assertEqual(trace._audit({},name)['attempted'],trace.UNKNOWN)
            raw={name:{'status':status,'selected_requirement_coverage':0.625,
                'selected_requirement_overlap_count':3,'selected_evidence_source':'PRIVATE/local',
                'selected_evidence_id':'ev_12345678','taxonomy_reason':'PRIVATE'}}
            observed=trace._audit(raw,name)
            self.assertTrue(observed['attempted']); self.assertEqual(observed['coverage'],0.625)
            self.assertEqual(observed['overlap'],3); self.assertNotIn('PRIVATE',json.dumps(observed))
        # Successful-only native receipts cannot justify saying an absent attempt was false.
        self.assertIsNone(trace._audit({},'capability_none_recovery')['coverage'])

    def test_existing_native_warning_codes_and_identity_guard_are_not_new_decisions(self):
        loaded,result=self.retained(); result=deepcopy(result); c=result['comparison']
        raw=c.published_analysis['canonical_requirements'][0]; rid=raw['requirement_id']
        c.published_analysis['validation_warnings']=[{'requirement_id':rid,'code':'insufficient_weak_evidence_context'},
            {'requirement_id':rid,'code':'PRIVATE_person@example.invalid','message':'PRIVATE'},
            {'requirement_id':'other','code':'missing_evidence'}]
        value=next(r for r in trace.build(loaded['request'],c)['requirements'] if r['requirement_id']==rid)['sides']['published']
        self.assertEqual(value['retained_native_warning_codes'],['insufficient_weak_evidence_context','UNRECOGNIZED'])
        self.assertEqual(value['metric_role'],'RETAINED_KEYWORD_LINK_VALUES_NOT_CANDIDATE_SCORES')
        self.assertEqual(trace.recovery_identity_reference({'match_label':'none','capability_resolution_source':'unresolved'}),
            'FINAL_FIELDS_FAIL_NATIVE_RECOVERY_IDENTITY_PRECONDITION')
        self.assertEqual(trace.recovery_identity_reference({'match_label':'none','capability_id':'quality.attention_detail',
            'capability_resolution_source':'canonical_taxonomy'}),
            'IDENTITY_PRECONDITION_MET_OTHER_ELIGIBILITY_AND_ATTEMPTS_NOT_ESTABLISHED')
        self.assertEqual(trace.recovery_identity_reference({'match_label':'none','coordinated_action_receipt':{'disposition':'REVIEW_REQUIRED'}}),trace.UNKNOWN)

    def test_source_tampering_and_cross_packet_trace_rejected(self):
        loaded,result=self.retained(); request=deepcopy(loaded['request'])
        request.projection['evidence_items'][0]['title']='changed'
        with self.assertRaises(ValueError): trace.build(request,result['comparison'])
        with self.assertRaises(ValueError): trace.build(loaded['request'],replace(result['comparison'],identity='other'))
        with self.assertRaises(ValueError): trace.build(loaded['request'],replace(result['comparison'],authority='DOCUMENT'))

    def test_ambiguous_original_owner_is_unknown_not_zero_or_multiple_acceptances(self):
        loaded,result=self.retained(); request=loaded['request']; c=result['comparison']
        ledger=trace.verified_projection_ledger(request.projection,request.projection['context']['resume_profile'],
                                                request.projection['context']['raw_resume_text'])
        selected=next(r for r in c.published_analysis['canonical_requirements'] if r.get('evidence'))
        evidence=selected['evidence'][0]; changed=False
        # Dependency fixture: two verified origins share an indexed occurrence.
        # This tests attribution uncertainty, not a fabricated scoring expectation.
        for occurrence in ledger['occurrences']:
            if trace._key(occurrence)==trace._key(evidence):
                first=occurrence['library_origins'][0]
                other=next(r for r in request.projection['originals'] if r['library_item_id']!=first['library_item_id'])
                occurrence['library_origins'].append(deepcopy(other)); changed=True
        self.assertTrue(changed)
        with patch.object(trace,'verified_projection_ledger',return_value=ledger):
            data=trace.build(request,c)
        value=next(r for r in data['requirements'] if r['requirement_id']==selected['requirement_id'])['sides']['published']
        self.assertIsNone(value['admitted_records']); self.assertTrue(value['unattributed_selected_references'])
        self.assertIsNone(value['not_selected_records'])
        self.assertTrue(all(r['accepted'] is None for r in value['records']))

    def test_extended_zip_hashes_matrix_json_and_privacy(self):
        loaded,result=self.retained(); report=debug.build_report(loaded,result)
        first=debug.bundle(report); self.assertEqual(first,debug.bundle(report))
        with zipfile.ZipFile(BytesIO(first[1])) as z:
            manifest=json.loads(z.read('manifest.json'))
            self.assertEqual(len(z.namelist()),11)
            for name,value in manifest['files'].items():
                self.assertEqual(hashlib.sha256(z.read(name)).hexdigest(),value['sha256'])
                self.assertEqual(len(z.read(name)),value['bytes'])
            data=json.loads(z.read('evidence_decision_trace.json'))
            matrix=list(csv.DictReader(StringIO(z.read('evidence_decision_matrix.csv').decode())))
            self.assertEqual([(r['requirement_id'],r['side'],int(r['library_item_id'])) for r in matrix],
                [(r['requirement_id'],r['side'],r['library_item_id']) for r in data['matrix']])
            self.assertEqual(json.loads(z.read('trace_coverage.json')),data['coverage'])
            self.assertEqual(data,json.loads(first[0])['evidence_decision_trace'])
            for name in z.namelist():
                text=z.read(name).decode()
                for secret in ('Waveform toolkit','Fictional Aster Devices','I designed, developed',
                               'resume_profile.projects','C:\\Users','original_text'):
                    self.assertNotIn(secret,text)

    def test_bounded_trace_does_not_disable_existing_debug_bundle(self):
        loaded,result=self.retained()
        with patch.object(trace,'MAX_PAIRS',0):
            with self.assertRaises(trace.TraceBounded): trace.build(loaded['request'],result['comparison'])
            report=debug.build_report(loaded,result)
        self.assertEqual(report['evidence_decision_trace']['coverage']['status'],'UNAVAILABLE')
        self.assertEqual(report['comparison_summary']['total_requirements'],len(debug.review_rows(result['comparison'])))
        self.assertTrue(debug.bundle(report)[1])

    def test_candidate_excerpt_requires_separate_consent_and_exact_original(self):
        loaded,result,data=self.packet(); rid=data['requirements'][0]['requirement_id']
        with self.assertRaises(ValueError): trace.private_pair(loaded['request'],result['comparison'],rid,100)
        for wrong_rid,wrong_item in (('invented',100),(rid,9999)):
            with self.assertRaises(ValueError): trace.private_pair(loaded['request'],result['comparison'],wrong_rid,wrong_item,consent=True)
        private=trace.private_pair(loaded['request'],result['comparison'],rid,100,consent=True)
        self.assertEqual(private['library_item_id'],100)
        self.assertTrue(any('embedded software' in s for s in private['original_excerpts']))
        self.assertIn('NOT_ASSERTED_ACCEPTED_OR_REJECTED',private['privacy'])

    def test_explicit_ui_cached_inspection_review_and_private_consent(self):
        loaded,result=self.retained(); app=self.page(loaded,result); before=self.path.read_bytes()
        with patch.object(trace,'build',wraps=trace.build) as build,patch.object(real,'evaluate') as scoring:
            app.run(); build.assert_not_called()
            app.button(key='developer_trace_build').click().run()
            self.assertFalse(app.exception,[x.message for x in app.exception]); self.assertEqual(build.call_count,1)
            app.button(key='developer_real_review_action_0').click().run()
            app.selectbox(key='developer_trace_record').select(101).run()
            app.button(key='developer_trace_review_save').click().run()
            self.assertEqual(build.call_count,1); self.assertTrue(app.session_state[ui.STATE]['reviews'])
            self.assertNotIn('private',app.session_state[ui.STATE])
            app.checkbox(key='developer_trace_private_consent').set_value(True).run()
            self.assertEqual(build.call_count,1)
            app.button(key='developer_trace_private_preview').click().run()
            self.assertIn('private',app.session_state[ui.STATE])
            app.checkbox(key='developer_trace_private_consent').set_value(False).run()
            self.assertNotIn('private',app.session_state[ui.STATE]); scoring.assert_not_called()
        self.assertEqual(before,self.path.read_bytes())

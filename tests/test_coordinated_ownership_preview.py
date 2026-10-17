"""Stage 2C offline contracts. No release authorization or fixture-oracle edits."""
from copy import deepcopy
import json
import os
import tempfile
from pathlib import Path
import types
import unittest
import uuid

from scripts import preview_coordinated_ownership_v1 as p
from taxonomy_discovery.coordinated_ownership_preview import extract_obligation,detect_ownership


def original_parent(index=1):
    row=p.stage2b.independent_parent_rows()[index]['variants']['A_full'][0]
    row.pop('recognition',None)
    return row


class TextOwnershipUnitTests(unittest.TestCase):
    def setUp(self):
        self.req=original_parent();self.obligation=extract_obligation(self.req)
        self.obj=self.obligation['object']

    def detect(self,text):
        index=p.n.build_resume_evidence_index(p.profile_for([text]),'')
        row=next(r for r in index if '.bullets[' in r['source'])
        return detect_ownership(self.obligation,row,index)

    def test_source_offsets_and_full_modifier_scope(self):
        for i in range(5):
            req=original_parent(i); o=extract_obligation(req);raw=o['raw_parent_text']
            self.assertEqual(o['status'],'SUPPORTED')
            self.assertEqual(raw[slice(*o['object_span'])],o['object'])
            for receipt in o['actions']:
                self.assertEqual(raw[slice(*receipt['span'])],receipt['original_action'])

    def test_one_record_multiple_clauses_and_receipt_offsets(self):
        text='I designed: '+self.obj+'; I developed '+self.obj+'; I maintained '+self.obj+'.'
        d=self.detect(text);self.assertTrue(d['complete'])
        for receipt in d['receipts']:
            self.assertEqual(text[slice(*receipt['object_span'])],receipt['object_text'])
            self.assertEqual(text[slice(*receipt['action_span'])],receipt['verb'])

    def test_usage_team_subject_future_and_question_are_not_owned(self):
        for prefix in ('Used ','Our team designed, developed and maintained ',
                       'The vendor designed, developed and maintained ',
                       'We designed, developed and maintained ',
                       'I am designed, developed and maintained ',
                       'I will design, develop and maintain '):
            d=self.detect(prefix+self.obj+'.')
            self.assertFalse(d['complete']);self.assertFalse(d['supported_actions'])
        self.assertFalse(self.detect('I designed, developed and maintained '+self.obj+'?')['complete'])

    def test_contradiction_denial_wrong_object_and_modifier_loss(self):
        text='I designed, developed and maintained '+self.obj+'. I did not design '+self.obj+'.'
        d=self.detect(text); self.assertFalse(d['complete']);self.assertIn('design',d['denied_actions'])
        wrong=self.detect('I designed React screens; developed '+self.obj+'; maintained '+self.obj+'.')
        self.assertNotIn('design',wrong['supported_actions'])
        short=self.detect('I designed, developed and maintained embedded software modules.')
        self.assertFalse(short['complete'])

    def test_bare_present_and_passive_are_explicitly_unsupported(self):
        self.assertFalse(self.detect('Design, develop and maintain '+self.obj+'.')['complete'])
        self.assertFalse(self.detect(self.obj+' were designed, developed and maintained by me.')['complete'])

    def test_source_and_evidence_id_must_match_original_index(self):
        index=p.n.build_resume_evidence_index(p.profile_for(['I designed, developed and maintained '+self.obj+'.']),'')
        row=next(r for r in index if '.bullets[' in r['source'])
        for key,value in [('source',''),('evidence_id','invented'),('text',row['text']+' Forged.'),('section','education')]:
            forged={**row,key:value}
            self.assertEqual(detect_ownership(self.obligation,forged,index)['status'],'UNVERIFIED_SOURCE')

    def test_oracle_is_not_a_detector_input(self):
        evidence=['I designed, developed and maintained '+self.obj+'.']
        right=p.oracle_comparison(self.obligation,evidence,[['design','develop','maintain']])
        deliberately_wrong=p.oracle_comparison(self.obligation,evidence,[[]])
        self.assertEqual(right[0]['computed'],deliberately_wrong[0]['computed'])
        self.assertNotEqual(right[0]['comparisons'],deliberately_wrong[0]['comparisons'])

    def test_final_invariant_blocks_simulated_recovery_bypass(self):
        trace=p.pipeline(self.req,['Configured ESP32 GPIO interrupts.'],filtered=True,
                         missing_only=True,_bypass_recovery_for_test=True)
        stages={s['stage']:s for s in trace['stages']}
        self.assertEqual(stages['recovered']['native_stage_label'],'direct')
        self.assertTrue(stages['final_invariant']['quarantined_pending_policy_review'])
        self.assertEqual(trace['provisional_final_label'],'none')

    def test_prospective_versions_and_disposable_snapshot_read_currentness(self):
        from database import job_match_manager as manager
        from job_discovery import matching
        inputs=dict(jd_profile={'responsibilities':['Develop REST APIs']},
            keyword_match={'present':[],'missing':[{'keyword':'Develop REST APIs'}]},
            resume_profile=p.profile_for(['Implemented Java REST API endpoints.']),
            raw_resume_text='Implemented Java REST API endpoints.',retrieval_mode_override='off')
        ns=p.clone_namespace()
        old=ns['build_stable_analysis'](**inputs); frozen=deepcopy(old)
        ns['CANONICAL_REQUIREMENT_DECOMPOSITION_VERSION']='jd-atomic-requirement-decomposition-v1.2'
        decomposition_only=ns['build_stable_analysis'](**inputs)
        self.assertEqual(old['input_fingerprint'],decomposition_only['input_fingerprint'])
        ns['SCORING_VERSION']='stable-evidence-v1.18-phase6d22'
        prospective=ns['build_stable_analysis'](**inputs)
        self.assertNotEqual(old['input_fingerprint'],prospective['input_fingerprint'])
        scratch=os.environ.get('EVIDENCE_TEST_SCRATCH')
        if not scratch:
            scratch=tempfile.gettempdir()
        db=Path(scratch)/('snapshot_contract_'+uuid.uuid4().hex+'.sqlite3')
        self.assertFalse(db.exists())
        self.addCleanup(db.unlink,missing_ok=True)
        versions=matching.current_match_versions();job={'id':999,'content_hash':'SYNTHETIC'}
        context={'evidence_fingerprint':'SYNTHETIC'}
        identity=matching._identity(job,context,versions)
        manager.save_job_match_snapshot(**identity,db_path=db,jd_profile=inputs['jd_profile'],
            evidence_snapshot=[],stable_analysis=old,summary={})
        local=dict(matching.__dict__)
        local['get_job_match_snapshot']=lambda **kw:manager.get_job_match_snapshot(**kw,db_path=db)
        local['get_latest_job_match_snapshot']=lambda jid:manager.get_latest_job_match_snapshot(jid,db_path=db)
        function=matching.inspect_job_match
        inspect=types.FunctionType(function.__code__,local,function.__name__,function.__defaults__,function.__closure__)
        inspect.__kwdefaults__=function.__kwdefaults__
        self.assertEqual(inspect(job,context=context,versions=versions)['status'],'current')
        stale=inspect(job,context=context,versions={**versions,'scoring_version':ns['SCORING_VERSION']})
        self.assertEqual(stale['status'],'stale')
        self.assertIn('stable scoring version changed',stale['stale_reasons'])
        self.assertEqual(manager.get_job_match_snapshot(**identity,db_path=db)['stable_analysis'],frozen)
        self.assertEqual(old,frozen)
        self.assertEqual(p.n.SCORING_VERSION,versions['scoring_version'])


class OwnershipIntegrationPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.result=p.study()

    def case(self,cid,family='embedded'):
        parent=next(x for x in self.result['parents'] if x['obligation']['object_family']==family)
        return next(c for c in parent['cases'] if c['id']==cid)

    def test_oracle_agreement_and_adversarial_false_negatives_are_reported(self):
        baseline=self.result['confusion']['oracle:UNCHANGED_STAGE2B_FIXTURE_ORACLE']
        self.assertEqual(baseline,dict(TP=67,TN=191,FP=0,FN=0))
        self.assertEqual(self.result['confusion']['overall']['FP'],0)
        self.assertGreater(self.result['confusion']['overall']['FN'],0)

    def test_complete_alternative_is_selected_by_native_ranker(self):
        checked=self.case('complete_alternative_row')['integration']['text_filtered']
        self.assertEqual(checked['provisional_final_label'],'direct')
        self.assertEqual(len(checked['final_evidence']),1)
        selected=checked['final_evidence'][0]
        self.assertEqual(selected['source'],'resume_profile.projects[0].bullets[1]')
        self.assertIn(selected['evidence_id'],checked['admissible_evidence_ids'])

    def test_no_union_of_independent_partial_sources_or_automatic_partial_label(self):
        for cid in ('maintenance_only','development_only','design_only','three_actions_separate_rows'):
            case=self.case(cid)['integration']
            self.assertIsNone(case['effective_preview_label'])
            self.assertEqual(case['policy_disposition'],'REVIEW_REQUIRED_NO_APPROVED_PARTIAL_RULE')
            self.assertFalse(case['text_filtered']['admissible_evidence_ids'])

    def test_zero_overlap_recovery_and_unverifiable_sources_cannot_add_credit(self):
        for cid in ('zero_overlap_topic','zero_overlap_missing_keyword_input','missing_source','forged_id','tampered_text'):
            case=self.case(cid)['integration']
            self.assertEqual(case['text_filtered']['provisional_final_label'],'none')
            self.assertNotEqual(case['effective_preview_label'],'direct')
        recovery=self.case('zero_overlap_topic')['integration']['unchecked']['stages'][-1]['recovery']
        self.assertEqual(recovery['selected_requirement_overlap_count'],0)

    def test_fullstack_topic_constraints_are_not_lifted_by_owned_actions(self):
        short=self.case('all_requested_actions','fullstack')['integration']
        positive=self.case('all_actions_explicit_layers','fullstack')['integration']
        self.assertTrue(short['text_filtered']['admissible_evidence_ids'])
        self.assertEqual(short['effective_preview_label'],'none')
        self.assertEqual(positive['effective_preview_label'],'direct')

    def test_api_authorship_design_and_dsa_contracts_are_preserved(self):
        cases={c['id']:c for c in self.result['independent_api_and_scope_controls']}
        for cid,expected in [('api_consume','none'),('api_postgrest','none'),('api_java','direct'),
                             ('api_incomplete_design','weak'),('api_complete_design','direct')]:
            self.assertEqual(cases[cid]['native_missing_keywords'][0]['native_label'],expected)
        self.assertEqual(cases['dsa_generic_data']['native'][0]['native_label'],'none')
        for cid,expected in [('protocol_and','none'),('protocol_or','direct'),('protocol_mixed_consumption','none')]:
            self.assertEqual(cases[cid]['forced_api_evaluator_only'][0]['label'],expected)

    def test_boolean_optional_and_unsupported_obligation_controls(self):
        cases={c['id']:c for c in self.result['additional_obligation_controls']}
        for cid in ('optional_embedded','alternative_embedded'):
            self.assertTrue(cases[cid]['detection']['complete'])
            self.assertEqual(cases[cid]['integration']['effective_preview_label'],'direct')
        self.assertTrue(cases['optional_embedded']['obligation']['optional_qualifiers'])
        self.assertEqual(cases['alternative_embedded']['obligation']['conjunction'],'OR')
        for cid in ('negated','mixed_and_or','ambiguous_object_or'):
            self.assertEqual(cases[cid]['obligation']['status'],'UNSUPPORTED')

    def test_full_corpus_allocations_and_original_native_namespace_are_protected(self):
        self.assertEqual(sum(j['baseline'] for j in self.result['raw_jd_corpus_replay']),716)
        self.assertEqual(sum(j['A_full'] for j in self.result['raw_jd_corpus_replay']),711)
        for parent in self.result['parents']:
            self.assertEqual(parent['parent_allocation_before'],parent['parent_allocation_after'])
            self.assertEqual(parent['parent_allocation_after'],1)
        function=p.n._evidence_source_is_requirement_compatible
        p.pipeline(original_parent(),['Configured ESP32 GPIO interrupts.'],filtered=True)
        self.assertIs(function,p.n._evidence_source_is_requirement_compatible)
        self.assertEqual(p.n.SCORING_VERSION,'stable-evidence-v1.17-phase6d21')
        self.assertEqual(p.n.CANONICAL_REQUIREMENT_DECOMPOSITION_VERSION,'jd-atomic-requirement-decomposition-v1.1')

    def test_absolute_raw_document_offsets_do_not_invent_occurrence_grounding(self):
        jobs=json.loads((p.ROOT/p.stage2b.stage2.inventory.FIXTURES[0]).read_text(encoding='utf-8'))['snapshot']['audit']['corpus']['jobs']
        raw_by_job={j['job_id']:j['frozen_inputs']['raw_jd_text'] for j in jobs}
        for parent in self.result['parents']:
            o=parent['obligation'];raw=raw_by_job[parent['job_id']]
            self.assertEqual(raw[slice(*o['raw_jd_parent_span'])],o['raw_parent_text'])
            self.assertEqual(raw[slice(*o['raw_jd_object_span'])],o['object'])
            for action in o['actions']:
                self.assertEqual(raw[slice(*action['raw_jd_span'])],action['original_action'])
            duplicate=p.ground_to_raw_jd(p.extract_obligation(parent['requirement']),o['raw_parent_text']+'\n'+o['raw_parent_text'])
            self.assertEqual(duplicate['status'],'UNSUPPORTED')

    def test_full_preview_matches_frozen_reviewed_baseline(self):
        oracle=p.stage2b.load_independent_oracle()
        self.assertEqual(p.stage2b.semantic_preview_digest(self.result),
                         oracle['reviewed_baseline_semantic_sha256']['2c'])
        self.assertEqual(self.result['oracle_fixture_sha256'],
                         p.stage2b.stage2.inventory.file_sha(p.stage2b.ORACLE_FIXTURE))
        self.assertEqual(self.result['current_versions_unchanged'],p.stage2b.stage2.inventory.knowledge_identity())


if __name__=='__main__':unittest.main()

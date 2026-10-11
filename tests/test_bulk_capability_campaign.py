from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from taxonomy_discovery import bulk_capability_campaign as campaign, maintenance_service as m
from taxonomy_discovery import gap_reduction_assistant as assistant, corpus_gap_resolution as gaps
from tests.test_taxonomy_maintenance_service import fixture_corpus
from tests.tqd3_publication_fixture_support import PublicationFixture


def row(index, text, lane=campaign.SCOPE, job=1):
    return {"job_id":job,"requirement_id":"r"+str(index),"canonical_text":text,
        "original_text":text,"importance":"core","weight":3.0,"lane":lane,
        "semantic_addressability":lane,"primary_blocker":m.MANUAL,"native_fix_layers":[],
        "provenance":[],"existing_capability_overlaps":[],"technology_identities":{},
        "structure_diagnostics":{},"research_state":[],"proof":{}}


def snapshot_and_plan(f, *texts):
    snapshot=m.run_corpus_audit(corpus=fixture_corpus(*texts),explicit_execution=True,review_db_path=f.tmp/'missing.sqlite')
    plan=assistant.build_plan(snapshot,research_budget=0,review_db_path=f.tmp/'missing.sqlite')
    return snapshot,plan


class BulkCampaignTests(unittest.TestCase):
    def test_maturation_traces_all_five_and_checks_native_taxonomy_first(self):
        texts=('Knowledge of network access control','Knowledge of secure coding practices',
            'Experience with database systems','Knowledge of data governance frameworks',
            'Experience with software development lifecycles')
        with PublicationFixture() as f:
            snapshot,plan=snapshot_and_plan(f,*texts)
            value=campaign.build(snapshot,plan)
            frozen=deepcopy(snapshot)
            result=campaign.validate(snapshot,plan,value,explicit_execution=True,
                review_db_path=f.tmp/'missing.sqlite',mature=True)
            self.assertEqual(len(result['decisions']),5)
            traced=set()
            for d in result['decisions']:
                scope=d['scope_review']
                self.assertTrue(scope['existing_taxonomy_checked'])
                self.assertFalse(scope['automatic_equivalence'])
                self.assertTrue(scope['parent_context_is_not_child_equivalence'])
                self.assertEqual(len(scope['requirements']),len(scope['native_resolutions']))
                traced.update(r['text'] for r in scope['requirements'])
                self.assertFalse(d['boundary_review']['complete'])
                self.assertIsNone(d['draft'])
            self.assertEqual(traced,set(texts))
            self.assertEqual(result['individually_validated_safe'],0)
            self.assertEqual(result['research_required'],1)
            self.assertEqual(result['scope_review_required'],4)
            self.assertEqual(result['combined']['changed_requirements'],[])
            self.assertEqual(result['combined']['duplicate_credit_violations'],[])
            self.assertEqual(snapshot,frozen)
            self.assertFalse((f.tmp/'missing.sqlite').exists())
            f.model_guard.assert_not_called(); f.network_guard.assert_not_called()

    def test_every_boundary_field_is_required_even_for_native_resolver_draft(self):
        scope={'requirements':[],'existing_taxonomy_checked':[]}
        cluster={'provenance':[],'profile':{}}
        for kind in ('capability','resolver_improvement'):
            d={'draft':{'kind':kind,'proposal':{'label':'Network access control','domain':'network',
                'positive_match_concepts':['network access control']}},'candidate_definition':{'definition':'hypothesis'}}
            review=campaign._boundary_review(d,cluster,scope)
            self.assertFalse(review['complete'])
            self.assertIn('evidence_predicates',review['missing_fields'])
            self.assertIn('technology_independent_semantics',review['missing_fields'])
            self.assertEqual(set(review['fields']),set(campaign.BOUNDARY_FIELDS))

    def test_local_stale_refresh_preserves_raw_evidence_and_exhausted_budget(self):
        with PublicationFixture() as f:
            snapshot,plan=snapshot_and_plan(f,'network access control')
            value=campaign.build(snapshot,plan)
            c=next(c for c in value['clusters'] if c['cluster_id'] in value['batch_1'])
            candidate=campaign._native_candidates(snapshot,c)[0][0]
            primary={'candidate':candidate,'research_result_id':'saved','research':{
                'target':{'research_round':2},'raw_provider_evidence':{'raw_response':{'request_id':'raw-request'}}}}
            refreshed={**deepcopy(primary),'support_bundle':{'eligible_for_human_review':False,
                'missing_evidence':['DEFINITION_MISSING']},'next_research_plan':{'call_budget':0,'query':'bounded native query'}}
            saved=[{'result':primary,'draft':None}]
            decision={'draft':None,'decision':'NEEDS_SCOPE_REVIEW','reason':'fixture'}
            with patch.object(campaign.research,'select_saved_interpretation',return_value={
                'primary':{'result':primary},'current':False,'ambiguous':False}), \
                patch.object(campaign.research,'re_evaluate_saved_evidence',return_value=refreshed) as refresh, \
                patch.object(campaign,'_prepare',return_value=decision):
                result=campaign._mature(snapshot,plan,c,saved)
            self.assertEqual(refresh.call_args.kwargs['persist'],False)
            self.assertTrue(refresh.call_args.kwargs['explicit_execution'])
            self.assertEqual(result['local_refresh']['research'],primary['research'])
            self.assertEqual(result['research_history'][0]['provider_request_id'],'raw-request')
            self.assertEqual(result['research_state'],'RESEARCH_EXHAUSTED')
            self.assertEqual(result['authorization_request']['maximum_provider_calls'],0)
            self.assertEqual(result['authorization_request']['bounded_queries'],['bounded native query'])
            self.assertIsNone(result['draft']); self.assertIsNone(result['research_plan'])
            f.model_guard.assert_not_called(); f.network_guard.assert_not_called()

    def test_complete_boundary_uses_explicit_supported_fields_not_neighbour_overlap(self):
        scope={'requirements':[{'source_provenance':[{'parent_text':'full source',
            'raw_parent_text':'full original source','source':'raw_jd.requirements'}]}],
            'existing_taxonomy_checked':[{'capability_id':'network.packet_analysis','label':'Packet analysis'}]}
        cluster={'provenance':[{'parent':'full source'}],'profile':{'closest_capability_ids':['network.packet_analysis']}}
        proposal={'label':'Network access control','domain':'network','positive_match_concepts':['network access control'],
            'does_not_prove':['Packet inspection alone']}
        d={'draft':{'kind':'capability','proposal':proposal}}
        fields={name:{'status':'supported','evidence':[{'text':'accepted bounded field'}]} for name in
            ('definition','responsibilities','inclusions','exclusions','evidence_predicates','boundaries')}
        fields['definition']['evidence']=[{'text':'Vendor neutral endpoint admission control'}]
        fields['boundaries']['evidence']=[{'text':'Distinct from network.packet_analysis and Packet analysis'}]
        result={'support_bundle':{'fields':fields}}
        self.assertTrue(campaign._boundary_review(d,cluster,scope,result)['complete'])
        for name in fields:
            incomplete=deepcopy(result); incomplete['support_bundle']['fields'][name]['status']='missing'
            self.assertFalse(campaign._boundary_review(d,cluster,scope,incomplete)['complete'],name)
        for key in proposal:
            incomplete=deepcopy(d); incomplete['draft']['proposal'].pop(key)
            self.assertFalse(campaign._boundary_review(incomplete,cluster,scope,result)['complete'],key)
        no_provenance=deepcopy(scope); no_provenance['requirements'][0]['source_provenance']=[]
        self.assertFalse(campaign._boundary_review(d,cluster,no_provenance,result)['complete'])
        not_independent=deepcopy(result)
        not_independent['support_bundle']['fields']['definition']['evidence']=[{'text':'A vendor product'}]
        self.assertFalse(campaign._boundary_review(d,cluster,scope,not_independent)['complete'])
        lexical=deepcopy(result)
        lexical['support_bundle']['fields']['boundaries']['evidence']=[{'text':'Network scope'}]
        self.assertIn('neighbouring_capabilities',campaign._boundary_review(d,cluster,scope,lexical)['missing_fields'])

    def test_current_evidence_does_not_refresh_or_silently_rebind_its_draft(self):
        with PublicationFixture() as f:
            snapshot,plan=snapshot_and_plan(f,'network access control')
            c=next(c for c in campaign.build(snapshot,plan)['clusters'] if c['canonical_concept']=='network access control')
            candidate=campaign._native_candidates(snapshot,c)[0][0]
            primary={'candidate':candidate,'research_result_id':'current','research':{'target':{},'raw_provider_evidence':{}}}
            saved=[{'result':primary,'draft':None}]
            with patch.object(campaign.research,'select_saved_interpretation',return_value={
                'primary':{'result':primary},'current':True,'ambiguous':False}), \
                patch.object(campaign.research,'validate_result'), \
                patch.object(campaign.research,'re_evaluate_saved_evidence') as refresh, \
                patch.object(campaign,'_prepare',return_value={'draft':None,'decision':'NEEDS_SCOPE_REVIEW'}):
                campaign._mature(snapshot,plan,c,saved)
            refresh.assert_not_called()

    def test_mature_partial_batch_combines_only_individually_safe_candidates(self):
        with PublicationFixture() as f:
            snapshot,plan=snapshot_and_plan(f,'network access control','Knowledge of secure coding practices',
                'Experience with database systems','Knowledge of data governance frameworks','Experience with software development lifecycles')
            value=campaign.build(snapshot,plan)
            baseline=campaign._replay(snapshot,[],set())
            calls=[]
            def mature(s,p,c,saved):
                i=value['batch_1'].index(c['cluster_id'])
                return {'cluster_id':c['cluster_id'],'concept':c['canonical_concept'],'reason':'fixture',
                    'decision':['READY_FOR_TEMPORARY_VALIDATION','NEEDS_RESEARCH','NEEDS_SCOPE_REVIEW',
                                'READY_FOR_TEMPORARY_VALIDATION','READY_FOR_TEMPORARY_VALIDATION'][i],
                    'draft':{'kind':'capability','tag':i} if i in (0,3,4) else None}
            def replay(s,drafts,intended):
                calls.append(deepcopy(drafts)); r=deepcopy(baseline)
                if drafts and drafts[0]['tag']==0: r['newly_resolved']=[(1,'fixture')]
                if drafts and drafts[0]['tag']==3: r['unexpected_changes']=[(1,'collateral')]
                return r
            with patch.object(campaign,'_mature',side_effect=mature),patch.object(campaign,'_replay',side_effect=replay):
                result=campaign.validate(snapshot,plan,value,explicit_execution=True,
                    review_db_path=f.tmp/'missing.sqlite',mature=True)
            self.assertEqual([d['decision'] for d in result['decisions']],
                ['VALIDATED_SAFE','NEEDS_RESEARCH','NEEDS_SCOPE_REVIEW','UNSAFE','VALIDATED_ZERO_IMPACT'])
            self.assertEqual([[d['tag'] for d in call] for call in calls],[[0],[3],[4],[0]])

    def test_native_individual_failure_does_not_stop_other_scope_reviews(self):
        with PublicationFixture() as f:
            snapshot,plan=snapshot_and_plan(f,'network access control','Knowledge of secure coding practices')
            value=campaign.build(snapshot,plan)
            baseline=campaign._replay(snapshot,[],set())
            reviewed=[]
            def mature(s,p,c,saved):
                reviewed.append(c['cluster_id'])
                return {'cluster_id':c['cluster_id'],'concept':c['canonical_concept'],'reason':'fixture',
                    'decision':'READY_FOR_TEMPORARY_VALIDATION' if len(reviewed)==1 else 'NEEDS_SCOPE_REVIEW',
                    'draft':{'kind':'capability'} if len(reviewed)==1 else None}
            with patch.object(campaign,'_mature',side_effect=mature), \
                patch.object(campaign,'_replay',side_effect=[ValueError('Frozen replay contract rejected'),baseline]):
                result=campaign.validate(snapshot,plan,value,explicit_execution=True,
                    review_db_path=f.tmp/'missing.sqlite',mature=True)
            self.assertEqual(reviewed,value['batch_1'])
            self.assertEqual([d['decision'] for d in result['decisions']],['UNSAFE','NEEDS_SCOPE_REVIEW'])
            self.assertEqual(result['individually_validated_safe'],0)
            self.assertIn('Frozen replay',result['decisions'][0]['replay_blocker'])

    def test_deterministic_semantic_topics_merge_controlled_wrappers(self):
        rows=[row(1,"Knowledge of network access control"),row(2,"Experience with network access control",job=2)]
        a,links=campaign.cluster_inventory(rows,[])
        b,_=campaign.cluster_inventory(list(reversed(rows)),[])
        self.assertEqual(a,b)
        self.assertEqual(len(a),1)
        self.assertEqual(a[0]['canonical_concept'],'network access control')
        self.assertEqual(a[0]['requirements'],2)
        self.assertEqual(a[0]['required_core_weight'],6)
        self.assertEqual(campaign.select_batch(a),campaign.select_batch(b))

    def test_word_overlap_is_not_semantic_equivalence(self):
        rows=[row(1,"Knowledge of database design"),row(2,"Knowledge of database querying"),
            row(3,"Knowledge of database administration"),row(4,"Knowledge of data persistence"),
            row(5,"Develop distributed systems and messaging with fault tolerance")]
        clusters,_=campaign.cluster_inventory(rows,[])
        self.assertEqual(len(clusters),5)
        self.assertFalse(next(c for c in clusters if c['canonical_concept'].startswith('Unproven'))['opportunity'])
        self.assertTrue(all(c['remediation_type']==campaign.SCOPE for c in clusters))

    def test_identity_and_relationship_are_dependencies_not_capabilities(self):
        rows=[row(1,"Python",campaign.IDENTITY),row(2,"MongoDB",campaign.RELATIONSHIP)]
        actions=[{'concept':'Python','fix_layer':m.IDENTITY_GAP,'requirement_keys':[{'job_id':1,'requirement_id':'r1'}]},
                 {'concept':'MongoDB','fix_layer':m.RELATIONSHIP_GAP,'requirement_keys':[{'job_id':1,'requirement_id':'r2'}]}]
        clusters,_=campaign.cluster_inventory(rows,actions)
        self.assertEqual({c['remediation_type'] for c in clusters},{campaign.IDENTITY,campaign.RELATIONSHIP})
        self.assertEqual(campaign.select_batch(clusters),[])

    def test_nonaddressable_and_mixed_rows_do_not_become_gap_hypotheses(self):
        rows=[row(1,'You care deeply about the public good',campaign.NOT),
              row(2,'Python, SQL and distributed systems',campaign.MIXED),
              row(3,'Develop APIs and deploy cloud services')]
        clusters,_=campaign.cluster_inventory(rows,[])
        self.assertFalse(any(c['remediation_type'] in (campaign.GAP,campaign.EXISTING) for c in clusters))
        self.assertEqual(campaign.select_batch(clusters),[])

    def test_shared_memberships_have_one_marginal_weight(self):
        rows=[row(1,'Python and SQL',campaign.MIXED)]
        actions=[{'concept':name,'fix_layer':m.IDENTITY_GAP,'requirement_keys':[{'job_id':1,'requirement_id':'r1'}]} for name in ('Python','SQL')]
        clusters,links=campaign.cluster_inventory(rows,actions)
        self.assertEqual(len(links[1,'r1']),3)
        self.assertEqual(sum(c['unique_marginal_core_weight'] for c in clusters),3)
        self.assertTrue(all(c['exclusive_requirements']==0 and c['shared_requirements']==1 for c in clusters))
        self.assertTrue(all(c['raw_mentions']==1 for c in clusters))

    def test_all_281_rows_are_retained_once_with_provenance(self):
        rows=[row(i,'Knowledge of secure coding practices') for i in range(281)]
        native=[{'requirement_id':r['requirement_id'],'text':r['canonical_text']} for r in rows]
        snapshot={'audit':{'summary':{'taxonomy_unresolved_requirements':281},'corpus':{'jobs':[
            {'job_id':1,'baseline_stable_analysis':{'canonical_requirements':native}}]}}}
        plan={'all_actions':[],'taxonomy_addressability':{'rows':rows}}
        result=campaign.inventory(snapshot,plan)
        clusters,links=campaign.cluster_inventory(result,[])
        self.assertEqual(len(result),281); self.assertEqual(len(links),281)
        self.assertEqual(clusters[0]['required_core_weight'],843)
        self.assertEqual(clusters[0]['requirements'],281)
        self.assertEqual(result[0]['original_text'],rows[0]['original_text'])

    def test_batch_selection_has_no_shared_source_requirements(self):
        rows=[row(1,'Knowledge of database design'),row(2,'Knowledge of database administration')]
        clusters,_=campaign.cluster_inventory(rows,[])
        overlap=deepcopy(clusters[0]); overlap['cluster_id']='overlap'; overlap['required_core_weight']=10
        selected=campaign.select_batch(clusters+[overlap])
        owned=set()
        for c in clusters+[overlap]:
            if c['cluster_id'] in selected:
                self.assertFalse(owned & set(c['requirement_keys'])); owned.update(c['requirement_keys'])

    def test_native_replay_is_explicit_and_read_only(self):
        root=Path(__file__).resolve().parents[1]
        paths=[root/p for p in ('taxonomy/capability_taxonomy_v1.json','taxonomy/technology_registry_v1.json')]
        contents=[p.read_bytes() for p in paths]
        with PublicationFixture() as f:
            snapshot,plan=snapshot_and_plan(f,'network access control','Experience with database administration')
            frozen=deepcopy(snapshot)
            value=campaign.build(snapshot,plan)
            with self.assertRaisesRegex(ValueError,'Explicit'):
                campaign.validate(snapshot,plan,value)
            result=campaign.validate(snapshot,plan,value,explicit_execution=True,review_db_path=f.tmp/'missing.sqlite')
            self.assertEqual(result['combined']['newly_resolved'],[])
            self.assertEqual(result['combined']['unexpected_changes'],[])
            self.assertEqual(result['research_required'],1)
            self.assertEqual(result['production_writes'],0)
            self.assertEqual(snapshot,frozen)
            f.model_guard.assert_not_called(); f.network_guard.assert_not_called()
            self.assertFalse((f.tmp/'missing.sqlite').exists())
        self.assertEqual(contents,[p.read_bytes() for p in paths])

    def test_individual_validation_excludes_unsafe_and_continues_research(self):
        with PublicationFixture() as f:
            snapshot,plan=snapshot_and_plan(f,'Knowledge of network access control','Experience with database administration','Knowledge of secure coding practices')
            value=campaign.build(snapshot,plan)
            baseline=campaign._replay(snapshot,[],set())
            calls=[]
            def prepare(s,p,c,saved):
                i=value['batch_1'].index(c['cluster_id'])
                return {'cluster_id':c['cluster_id'],'concept':c['canonical_concept'],'reason':'fixture',
                    'decision':'NEEDS_RESEARCH' if i==2 else 'READY_FOR_TEMPORARY_VALIDATION',
                    'draft':None if i==2 else {'kind':'capability','tag':i}}
            def replay(s,drafts,intended):
                calls.append(deepcopy(drafts))
                r=deepcopy(baseline)
                if drafts and drafts[0]['tag']==0:
                    r['newly_resolved']=[(1,'fixture')]
                elif drafts:
                    r['unexpected_changes']=[(1,'wrong')]
                return r
            with patch.object(campaign,'_prepare',side_effect=prepare),patch.object(campaign,'_replay',side_effect=replay):
                result=campaign.validate(snapshot,plan,value,explicit_execution=True,review_db_path=f.tmp/'missing.sqlite')
            self.assertEqual([d['decision'] for d in result['decisions']],['VALIDATED_SAFE','UNSAFE','NEEDS_RESEARCH'])
            self.assertEqual(calls,[[{'kind':'capability','tag':0}],[{'kind':'capability','tag':1}],[{'kind':'capability','tag':0}]])
            self.assertEqual(result['research_required'],1)

    def test_real_native_proposal_overlay_is_temporary_and_adds_no_evidence(self):
        from tests.test_tqd3_taxonomy_evolution import draft
        from tailoring.capability_taxonomy import get_default_taxonomy
        root = Path(__file__).resolve().parents[1]
        paths = [root/p for p in ('taxonomy/capability_taxonomy_v1.json','taxonomy/technology_registry_v1.json')]
        original = [p.read_bytes() for p in paths]
        with PublicationFixture() as f:
            snapshot, _ = snapshot_and_plan(f, 'crystalline computing protocols', 'C++ programming')
            base = get_default_taxonomy()
            proposal, _ = draft(f)
            intended = {k for k,r in campaign._records(snapshot['audit']['corpus']).items() if r['text']=='crystalline computing protocols'}
            result = campaign._replay(snapshot, [{'kind':'capability','proposal':proposal}], intended)
            self.assertEqual(set(result['newly_resolved']), intended)
            self.assertTrue(intended)
            self.assertEqual(result['unexpected_changes'], [])
            self.assertEqual(result['newly_unresolved'], [])
            self.assertEqual(result['evidence_deltas'], [])
            self.assertEqual(result['score_deltas'], [])
            self.assertIs(get_default_taxonomy(), base)
            self.assertNotIn(proposal['proposed_capability_id'], base.by_id())
            f.model_guard.assert_not_called(); f.network_guard.assert_not_called()
        self.assertEqual(original, [p.read_bytes() for p in paths])

    def test_batch_two_is_ranked_from_post_batch_rows(self):
        with PublicationFixture() as f:
            snapshot,plan=snapshot_and_plan(f,'network access control','Knowledge of secure coding practices')
            value=campaign.build(snapshot,plan,size=1)
            simulated=campaign._replay(snapshot,[],set())
            target=next(c for c in value['clusters'] if c['cluster_id']==value['batch_1'][0])
            target_keys=set(target['requirement_keys'])
            for r in simulated['audit']['requirements']:
                if campaign._key(r) in target_keys:
                    r['current_resolution'].update(status='resolved',capability_id='fixture.only')
            simulated['audit']['summary']['taxonomy_unresolved_requirements']-=len(target_keys)
            simulated['audit']['summary']['taxonomy_resolved_requirements']+=len(target_keys)
            simulated['newly_resolved']=list(target_keys)
            with patch.object(campaign,'_prepare',return_value={'cluster_id':target['cluster_id'],
                'concept':target['canonical_concept'],'decision':'READY_FOR_TEMPORARY_VALIDATION','draft':{'kind':'capability'},'reason':'fixture'}), \
                patch.object(campaign,'_replay',return_value=simulated):
                result=campaign.validate(snapshot,plan,value,explicit_execution=True,review_db_path=f.tmp/'missing.sqlite')
            self.assertFalse(set(value['batch_1']) & set(result['batch_2']))
            self.assertEqual(len(result['post_addressability']['rows']),snapshot['audit']['summary']['taxonomy_unresolved_requirements']-len(target_keys))
            self.assertFalse(target_keys & {campaign._key(r) for r in result['post_addressability']['rows']})

    def test_stale_or_tampered_campaign_fails_closed(self):
        with PublicationFixture() as f:
            snapshot,plan=snapshot_and_plan(f,'network access control')
            value=campaign.build(snapshot,plan)
            value['batch_unique_core_weight']=999
            self.assertFalse(campaign.current(snapshot,plan,value))
            with self.assertRaisesRegex(ValueError,'Stale'):
                campaign.validate(snapshot,plan,value,explicit_execution=True)

    def test_partial_current_evidence_does_not_warrant_an_overlay_or_repeat_query(self):
        with PublicationFixture() as f:
            snapshot,plan=snapshot_and_plan(f,'network access control')
            value=campaign.build(snapshot,plan)
            c=next(c for c in value['clusters'] if c['cluster_id'] in value['batch_1'])
            result={'research_result_id':'partial','result_fingerprint':'fixture',
                'conflicts_blockers':[],'recommended_next_action':'new_capability_proposal','support_bundle':{'fields':{}}}
            saved=[{'result':result,'draft':{'kind':'capability','proposal':{}}}]
            with patch.object(campaign.research,'select_saved_interpretation',return_value={'primary':{'result':result},'current':True,'ambiguous':False}), \
                patch.object(campaign.research,'validate_result'),patch.object(campaign.research,'research_plan') as planner:
                decision=campaign._prepare(snapshot,plan,c,saved)
            self.assertEqual(decision['decision'],'NEEDS_SCOPE_REVIEW')
            self.assertIsNone(decision['draft'])
            self.assertIn('incomplete',decision['cached_evidence_blocker'])
            planner.assert_not_called()

    def test_ambiguous_cached_interpretations_cannot_trigger_research(self):
        with PublicationFixture() as f:
            snapshot,plan=snapshot_and_plan(f,'network access control')
            value=campaign.build(snapshot,plan)
            c=next(c for c in value['clusters'] if c['cluster_id'] in value['batch_1'])
            with patch.object(campaign.research,'select_saved_interpretation',return_value={'primary':None,'current':False,'ambiguous':True}), \
                patch.object(campaign.research,'research_plan') as planner:
                decision=campaign._prepare(snapshot,plan,c,[])
            self.assertEqual(decision['decision'],'NEEDS_SCOPE_REVIEW')
            planner.assert_not_called()

    def test_human_tables_contain_only_scalar_cells(self):
        clusters,_=campaign.cluster_inventory([row(1,'Knowledge of secure coding practices')],[])
        self.assertTrue(all(isinstance(v,(str,int,float,type(None))) for r in campaign.table(clusters) for v in r.values()))


if __name__=='__main__':
    unittest.main()

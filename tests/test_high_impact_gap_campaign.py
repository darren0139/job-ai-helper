"""Offline lazy classification and high-impact native campaign orchestration."""
from copy import deepcopy
import unittest
from unittest.mock import patch
from taxonomy_discovery import bulk_capability_campaign as campaign, taxonomy_addressability as address
from taxonomy_discovery import gap_reduction_assistant as assistant
from tests.test_bulk_capability_campaign import snapshot_and_plan, row
from tests.tqd3_publication_fixture_support import PublicationFixture


TEXTS=('Knowledge of network access control','Knowledge of secure coding practices','Experience with database systems',
    'Knowledge of data governance frameworks','Experience with software development lifecycles',
    'Knowledge of microservices architecture','Knowledge of enterprise integration patterns',
    'Knowledge of modern software engineering best practices','Knowledge of Microservices',
    'Familiarity with distributed systems','Knowledge of cloud security','Python','SQL','MongoDB',
    'you care deeply about the public good and understand the responsibility of working on critical national infrastructure')


def lazy_plan(f,snapshot,previous):
    return assistant.build_plan(snapshot,research_budget=0,review_db_path=f.tmp/'missing.sqlite',
        lazy_addressability=True,addressability_seed=previous['taxonomy_addressability'])


class HighImpactCampaignTests(unittest.TestCase):
    def test_lazy_plan_and_currentness_never_reclassify_the_global_union(self):
        with PublicationFixture() as f:
            snapshot,original=snapshot_and_plan(f,*TEXTS)
            with patch.object(address,'classify',side_effect=AssertionError('global classification')), \
                patch.object(address,'manual_triage',side_effect=AssertionError('global triage')):
                plan=lazy_plan(f,snapshot,original)
                assistant.validate_plan(snapshot,plan,plan['assistant_plan_fingerprint'],review_db_path=f.tmp/'missing.sqlite')
            self.assertEqual(plan['taxonomy_addressability']['rows'],original['taxonomy_addressability']['rows'])

    def test_only_selected_keys_change_and_nonaddressable_rows_stay_visible(self):
        with PublicationFixture() as f:
            snapshot,original=snapshot_and_plan(f,*TEXTS)
            seed=original['taxonomy_addressability']
            chosen={(r['job_id'],r['requirement_id']) for r in seed['rows'] if r['canonical_text']=='Experience with database systems'}
            unresolved=[r for r in snapshot['audit']['requirements'] if campaign._key(r) in {campaign._key(q) for q in seed['rows']}]
            native=address.classify
            with patch.object(address,'classify',wraps=native) as classify:
                value=address.project(snapshot,unresolved,snapshot['gap_rows'],previous=seed,reviewed_keys=chosen)
            self.assertEqual(classify.call_count,len(chosen))
            old={campaign._key(r):r for r in seed['rows']}
            for r in value['rows']:
                if campaign._key(r) not in chosen: self.assertEqual(r,old[campaign._key(r)])
            self.assertEqual(value['summary'][address.NOT_ADDRESSABLE],seed['summary'][address.NOT_ADDRESSABLE])

    def test_marginal_queue_is_deterministic_and_does_not_rank_mentions(self):
        rows=[row(i,'Knowledge of database systems',campaign.IDENTITY) for i in range(12)]
        rows[0]['weight']=4
        actions=[{'concept':str(i),'fix_layer':'TECHNOLOGY_IDENTITY_GAP',
            'requirement_keys':[{'job_id':1,'requirement_id':'r'+str(i)}]} for i in range(12)]
        # Use the repository's native fix-layer constant, never duplicate its value.
        from taxonomy_discovery import maintenance_service as m
        for a in actions: a['fix_layer']=m.IDENTITY_GAP
        clusters,_=campaign.cluster_inventory(rows,actions)
        q=campaign.ranked_work_queue(clusters,rows)
        self.assertEqual(q,campaign.ranked_work_queue(list(reversed(clusters)),list(reversed(rows))))
        self.assertEqual(len(q),12)
        self.assertEqual(sum(c['unique_marginal_core_weight'] for c in q),37)
        self.assertEqual(sum(c['unique_marginal_requirements'] for c in q),12)
        for c in clusters: c['raw_mentions']=99999
        self.assertEqual([c['cluster_id'] for c in q],[c['cluster_id'] for c in campaign.ranked_work_queue(clusters,rows)])

    def test_processes_ten_independently_without_global_post_projection(self):
        with PublicationFixture() as f:
            snapshot,original=snapshot_and_plan(f,*TEXTS)
            plan=lazy_plan(f,snapshot,original)
            value=campaign.build(snapshot,plan,high_impact=True)
            self.assertEqual(len(value['batch_1']),10)
            self.assertGreaterEqual(len(value['top_15']),10)
            frozen=deepcopy(snapshot)
            selected={tuple(k) for c in value['clusters'] if c['cluster_id'] in value['batch_1'] for k in c['requirement_keys']}
            native=address.classify
            with patch.object(address,'classify',wraps=native) as classify:
                result=campaign.validate(snapshot,plan,value,explicit_execution=True,mature=True,
                    review_db_path=f.tmp/'missing.sqlite')
            self.assertEqual(classify.call_count,len(selected))
            self.assertEqual(len(result['decisions']),10)
            for d in result['decisions']:
                self.assertTrue(d['scope_review']['existing_taxonomy_checked'])
                self.assertIn(d['classification'],(campaign.PROVEN,campaign.EXISTING,campaign.IDENTITY,
                    campaign.RELATIONSHIP,campaign.STRUCTURE,campaign.NOT,campaign.DEFER))
                if d['classification'] in (campaign.IDENTITY,campaign.RELATIONSHIP,campaign.STRUCTURE,campaign.DEFER):
                    self.assertIsNone(d['draft'])
            self.assertEqual(snapshot,frozen)
            self.assertEqual(result['combined']['changed_requirements'],[])
            self.assertEqual(sum(result['gap_accounting']['counts'].values()),plan['baseline']['unresolved'])
            f.network_guard.assert_not_called(); f.model_guard.assert_not_called()
            self.assertFalse((f.tmp/'missing.sqlite').exists())

    def test_unknown_and_dependencies_are_not_counted_as_true_gaps(self):
        projection={'rows':[{'job_id':1,'requirement_id':str(i),'semantic_addressability':address.UNDETERMINED} for i in range(3)]}
        projection['rows'].append({'job_id':1,'requirement_id':'not','semantic_addressability':address.NOT_ADDRESSABLE})
        decisions=[{'classification':campaign.IDENTITY,'requirement_keys':[(1,'0'),(1,'1')]},
            {'classification':campaign.RELATIONSHIP,'requirement_keys':[(1,'1')]}]
        result=campaign.gap_accounting(projection,decisions)
        self.assertEqual(result['counts'],{'proven_true_gaps':0,'maintenance_dependencies':2,'not_addressable':1,'undetermined':1})

    def test_high_impact_individual_replays_precede_safe_only_combination(self):
        with PublicationFixture() as f:
            snapshot,original=snapshot_and_plan(f,*TEXTS)
            plan=lazy_plan(f,snapshot,original)
            value=campaign.build(snapshot,plan,high_impact=True)
            baseline=campaign._replay(snapshot,[],set())
            calls=[]
            def review(s,p,c,saved,projection):
                i=value['batch_1'].index(c['cluster_id'])
                decision='READY_FOR_TEMPORARY_VALIDATION' if i in (0,5,6) else 'NEEDS_RESEARCH' if i==1 else campaign.DEFER
                return {'cluster_id':c['cluster_id'],'concept':c['canonical_concept'],
                    'classification':campaign.EXISTING if i in (0,5,6) else campaign.PROVEN if i==1 else campaign.DEFER,
                    'decision':decision,'reason':'native contract fixture',
                    'draft':{'kind':'capability','tag':i} if i in (0,5,6) else None}
            def replay(s,drafts,intended):
                calls.append([d['tag'] for d in drafts]); report=deepcopy(baseline)
                if drafts and drafts[0]['tag']==0: report['newly_resolved']=[(1,'fixture')]
                if drafts and drafts[0]['tag']==5: report['unexpected_changes']=[(1,'collateral')]
                return report
            with patch.object(campaign,'_review_high_impact',side_effect=review),patch.object(campaign,'_replay',side_effect=replay):
                result=campaign.validate(snapshot,plan,value,explicit_execution=True,review_db_path=f.tmp/'missing.sqlite')
            self.assertEqual(calls,[[0],[5],[6],[0]])
            self.assertEqual(result['individually_validated_safe'],1)
            self.assertEqual(result['research_required'],1)
            self.assertEqual(result['unsafe'],1)
            self.assertEqual(result['validated_zero_impact'],1)

    def test_high_impact_requires_lazy_plan_before_any_global_validation(self):
        with PublicationFixture() as f:
            snapshot,plan=snapshot_and_plan(f,'Python')
            with self.assertRaisesRegex(ValueError,'lazy'):
                campaign.build(snapshot,plan,high_impact=True)


if __name__=='__main__': unittest.main()

"""Offline review invariants, not approval of the proposed recognition policy."""
from copy import deepcopy
import unittest

from scripts import preview_bulk_unresolved_v1 as review
from tailoring.capability_taxonomy import evaluate_capability_evidence, get_default_taxonomy


class BulkUnresolvedReviewTests(unittest.TestCase):
    def test_duplicate_fixture_views_are_not_extra_jobs(self):
        jobs, sources=review.load_jobs()
        self.assertEqual(len(jobs),30)
        self.assertEqual(sum(len(j['job']['baseline_stable_analysis']['canonical_requirements']) for j in jobs),727)
        self.assertEqual(len(sources),2)
        self.assertTrue(all(j['source_files']==[review.SOURCES[0]] for j in jobs))
        self.assertEqual(sources[1]['role'],'alternate_historical_reference_not_merged')
        self.assertEqual(len(sources[1]['alternate_views']),30)
        self.assertFalse(any(v['content_identical'] for v in sources[1]['alternate_views']))

    def test_exact_review_candidates_use_native_scoped_resolution_and_restore(self):
        original=get_default_taxonomy()
        for text in review.PROPOSALS:
            row={'requirement_id':'test', 'text':text,'importance':'core','group_weight_fraction':1}
            frozen=deepcopy(row); result=review.preview(row)
            self.assertTrue(result['proposal_applied'],text)
            self.assertEqual(result['baseline']['knowledge_status'],'UNRESOLVED')
            self.assertEqual(result['proposed']['capability_id'],review.API)
            self.assertFalse(result['evidence_credit_computed'])
            self.assertFalse(result['parent_weights_changed'])
            self.assertEqual(row,frozen)
            self.assertEqual(get_default_taxonomy(),original)

    def test_parent_scope_denial_protocol_and_related_terms_are_not_rewritten(self):
        for text in ['Knowledge of API integration','Knowledge of REST and gRPC APIs',
                     'Do not develop REST endpoints','Develop REST endpoints and design a database',
                     'Generic data handling','Amazon Web Services','Design REST interfaces']:
            r=review.preview({'text':text})
            self.assertFalse(r['proposal_applied'])
            self.assertEqual(r['baseline'],r['proposed'])
        for fields in [dict(parent_text='Knowledge of REST APIs and gRPC'),
                       dict(is_atomic=True), dict(source_provenance=[]),
                       dict(source_provenance=[{'source':'raw','parent_occurrence_id':'p',
                            'parent_text':'Knowledge of REST APIs','raw_parent_text':'Use APIs and build a database'}])]:
            r=review.preview({'text':'Knowledge of REST APIs',**fields})
            self.assertFalse(r['proposal_applied'])

    def test_missing_evidence_does_not_become_an_unresolved_identity(self):
        row={'requirement_id':'r','text':'Knowledge of API development','match_label':'none',
             'evidence':[],'score_eligible':True}
        r=review.inventory_row(row,1,[],row['text'],{},'saved_projection')
        self.assertEqual(r['current']['knowledge_status'],'CAPABILITY_RESOLVED')
        self.assertEqual(r['category'],'recognized_with_stored_no_credit')
        self.assertNotIn('evidence',r['input'])
        self.assertEqual(review.exact_clusters([r]),[])

    def test_exact_clusters_have_order_independent_ids_and_keep_occurrences(self):
        rows=[review.inventory_row({'requirement_id':f'r{i}','text':'Unfamiliar obligation'},i,[],
                                   'Unfamiliar obligation',{},'saved_projection') for i in [1,2]]
        a=review.exact_clusters(rows);b=review.exact_clusters(rows[::-1])
        self.assertEqual(a[0]['cluster_id'],b[0]['cluster_id'])
        self.assertEqual(a[0]['job_count'],2)
        self.assertEqual(a[0]['occurrences'],2)
        self.assertNotEqual(review.backlog.normal('C++'),review.backlog.normal('C#'))
        self.assertNotEqual(review.backlog.normal('Java'),review.backlog.normal('JavaScript'))

    def test_privacy_export_omits_contacts_without_changing_local_inputs(self):
        raw={'text':'Contact person@example.com for software engineering work'}
        cleaned=review.safe(raw)
        self.assertNotIn('person@example.com',str(cleaned))
        self.assertIn('WITHHELD',cleaned['text'])
        self.assertIn('person@example.com',raw['text'])
        self.assertEqual(review.safe({'requirement_id':'req_123456789012'})['requirement_id'],'req_123456789012')

    def test_raw_jd_replay_supplies_provenance_without_mutating_saved_receipts(self):
        jobs,_=review.load_jobs()
        job=next(j['job'] for j in jobs if j['job']['job_id']==632)
        saved=deepcopy(job)
        result=review.scoring.canonicalise_requirements({},raw_jd_text=job['frozen_inputs']['raw_jd_text'])
        row=next(r for r in result['requirements'] if r['text']=='Experience with Node.js')
        self.assertTrue(row['source_provenance'])
        self.assertEqual(review.resolve(row)['knowledge_status'],'TECHNOLOGY_IDENTITY_RESOLVED')
        original=next(r for r in saved['baseline_stable_analysis']['canonical_requirements'] if r['requirement_id']==row['requirement_id'])
        self.assertFalse(original.get('source_provenance'))
        self.assertEqual(review.resolve(original)['knowledge_status'],'UNRESOLVED')
        self.assertEqual(saved,job)

    def test_v11_endpoint_and_design_obligations_and_data_negative_are_preserved(self):
        evidence=('Extended an existing Java backend by developing REST API endpoints to support '
                  'data exchange with the Unity-based Maritime Digital Twin, collaborating on MinIO storage integration.')
        evaluate=lambda focus,text:evaluate_capability_evidence(review.API,{'text':focus},text)['label']
        self.assertEqual(evaluate('Develop RESTful APIs',evidence),'direct')
        self.assertEqual(evaluate('Design and develop RESTful APIs',evidence),'weak')
        self.assertEqual(evaluate('Design and develop REST APIs','Implemented data access through PostgREST.'),'none')
        self.assertEqual(evaluate('Develop REST APIs','Implemented gRPC endpoints.'),'none')
        dsa=review.resolve({'text':'Data Structures and Algorithms'})['decision'].get('capability_id')
        self.assertEqual(dsa,'algorithms.data_structures_algorithms')
        self.assertIsNone(review.resolve({'text':'Generic data handling'})['decision'].get('capability_id'))
        self.assertEqual(evaluate_capability_evidence(dsa,{'text':'Data Structures and Algorithms'},
            'Implemented backend data access through PostgREST and applied Row-Level Security policies.')['label'],'none')


if __name__=='__main__':
    unittest.main()

"""Stage 1 contract acceptance; no parser repair or candidate evidence export."""
from copy import deepcopy
import json
import unittest

from taxonomy_discovery import source_aware_inventory as inventory


class SourceAwareInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.views=inventory.fixture_views()
        cls.before=inventory.digest(cls.views)
        cls.export=inventory.build_export(cls.views)
        cls.by_view={v['view_id']:v for v in cls.export['views']}

    def rows(self,job,cohort):
        return [r for r in self.export['records'] if r['job_id']==job and
                self.by_view[r['view_id']]['cohort']==cohort]

    def find(self,job,cohort,text):
        return next(r for r in self.rows(job,cohort) if text.lower() in r['requirement']['text'].lower())

    def test_node_mongo_keycloak_saved_and_raw_provenance_remain_separate(self):
        for term in ['Node.js','MongoDB','Keycloak']:
            saved=self.find(632,'saved_primary',term);raw=self.find(632,'raw_jd_only',term)
            self.assertEqual(saved['requirement_id'],raw['requirement_id'])
            self.assertNotIn('source_provenance',saved['requirement'])
            self.assertEqual(saved['native_resolution']['knowledge_status'],'UNRESOLVED')
            self.assertEqual(raw['native_resolution']['knowledge_status'],'TECHNOLOGY_IDENTITY_RESOLVED')
            self.assertTrue(raw['requirement']['source_provenance'])
            self.assertNotEqual(saved['record_id'],raw['record_id'])
            rawview=self.by_view[raw['view_id']]
            self.assertTrue(rawview['references'][0]['row_container'].startswith('DERIVED:'))
            self.assertIn('canonical_requirement_decomposition_version',rawview['source_versions'])
            self.assertEqual(self.by_view[saved['view_id']]['references'][0]['row_container'],
                             'baseline_stable_analysis.canonical_requirements')

    def test_python_sql_and_edb_javascript_complete_scope(self):
        for job,term in [(16,'Python and SQL'),(146,'JavaScript')]:
            raw=self.find(job,'raw_jd_only',term)
            self.assertEqual(raw['native_resolution']['knowledge_status'],'TECHNOLOGY_IDENTITY_RESOLVED')
            self.assertEqual(raw['source_completeness']['status'],'COMPLETE_AVAILABLE_SOURCE')
            self.assertTrue(raw['requirement']['source_provenance'][0]['grounding'])
            saved=self.find(job,'saved_primary',term)
            self.assertEqual(saved['readiness']['recognition'],'PARTIAL_SOURCE_CONTEXT')

    def test_coordinated_fragments_are_reported_without_repair(self):
        for job in [359,479]:
            row=self.find(job,'raw_jd_only','Design, develop')
            self.assertEqual(row['requirement']['text'],'Design, develop')
            self.assertTrue(row['stage2_diagnostic'])
            self.assertEqual(row['native_resolution']['knowledge_status'],'UNRESOLVED')
            parent=row['requirement']['source_provenance'][0]['raw_parent_text']
            self.assertIn('develop',parent.lower())

    def test_duplicate_views_do_not_double_count_and_alternates_do_not_merge(self):
        self.assertEqual(self.export['counts'],dict(unique_jobs=30,distinct_source_views=90,records=2170,duplicate_input_views=0))
        view=self.views[0]
        a=inventory.build_export([view]);b=inventory.build_export([view,deepcopy(view)])
        self.assertEqual(a['records'],b['records'])
        self.assertEqual(a['views'],b['views'])
        self.assertEqual(b['counts']['duplicate_input_views'],1)
        self.assertEqual(len({r['view_id'] for r in self.rows(632,'saved_primary')+self.rows(632,'saved_alternate')}),2)

    def test_missing_profile_evidence_and_historical_versions_block_replay(self):
        for row in self.export['records']:
            self.assertEqual(row['readiness']['current_full_pipeline'],'BLOCKED')
            self.assertEqual(row['readiness']['historical_reproduction'],'BLOCKED')
            self.assertIn('ORIGINAL_EXTRACTED_JD_PROFILE_UNAVAILABLE',row['readiness']['current_full_pipeline_blockers'])
            self.assertIn('COMPLETE_FROZEN_CANDIDATE_EVIDENCE_UNAVAILABLE',row['evidence']['blockers'])
            self.assertEqual(row['evidence']['evaluation'],'NOT_RUN')
        alternate=self.rows(632,'saved_alternate')[0]
        self.assertIn('RAW_JD_UNAVAILABLE_IN_THIS_VIEW',alternate['source_completeness']['blockers'])
        self.assertIn('ORIGINAL_ANALYSIS_VERSIONS_UNAVAILABLE',alternate['readiness']['historical_reproduction_blockers'])

    def test_repeat_exports_and_reordered_inputs_have_stable_identity(self):
        subset=[self.views[0],self.views[1]]
        a=inventory.build_export(subset);b=inventory.build_export(deepcopy(subset[::-1]))
        self.assertEqual(a,b)
        self.assertEqual(self.before,inventory.digest(self.views))

    def synthetic_view(self,rows,raw):
        return {**deepcopy(self.views[0]),'requirements':rows,'raw_jd_text':raw,'job_id':999,
                'cohort':'raw_jd_only'}

    def test_multiple_parent_occurrences_and_allocations_are_preserved(self):
        raw='Knowledge of REST API. Experience with Node.js.'
        row={'requirement_id':'test','text':'Knowledge of REST API','group_weight_fraction':1,
             'source_provenance':[dict(parent_occurrence_id=pid,parent_text=text,raw_parent_text=text,
                 source='raw_jd.requirements',source_group_fraction=1,contributes_scoring_allocation=True)
                 for pid,text in [('p1','Knowledge of REST API.'),('p2','Experience with Node.js.')]]}
        out=inventory.build_export([self.synthetic_view([row],raw)])
        self.assertEqual(len(out['records'][0]['requirement']['source_provenance']),2)
        self.assertEqual([a['contributing_sum'] for a in out['views'][0]['source_allocations']],[1,1])
        self.assertTrue(all(a['status']=='CONSERVED' for a in out['views'][0]['source_allocations']))

    def test_overallocation_fails_validation(self):
        rows=[{'requirement_id':f'r{i}','text':'Knowledge of REST API',
               'source_provenance':[dict(parent_occurrence_id='p',parent_text='Knowledge of REST API',
                    raw_parent_text='Knowledge of REST API',source='raw',source_group_fraction=.75)]} for i in [1,2]]
        with self.assertRaisesRegex(ValueError,'Invalid parent allocation'):
            inventory.build_export([self.synthetic_view(rows,'Knowledge of REST API')])

    def test_all_any_optional_negated_and_mixed_are_native_diagnostics(self):
        texts=['Programming in Python or Java','Programming in Python and Java',
               'Experience with Node.js is preferred','Do not develop REST APIs',
               'Develop and integrate RESTful APIs with front-end applications',
               'Programming languages such as Python or Java']
        from tailoring.phase6d6_structured_matching import technology_requirement_structure
        rows=[{'requirement_id':f'control{i}','text':text,'importance':'core'} for i,text in enumerate(texts)]
        out=inventory.build_export([self.synthetic_view(rows,'\n'.join(texts))])
        for row in out['records']:
            self.assertEqual(row['native_structure'],technology_requirement_structure(row['requirement']))
        bytext={r['requirement']['text']:r for r in out['records']}
        self.assertTrue(bytext[texts[2]]['qualifier_observations']['optional_cue'])
        self.assertTrue(bytext[texts[3]]['qualifier_observations']['negative_cue'])
        modes={r['native_structure']['mode'] for r in out['records']}
        self.assertIn('any',modes);self.assertIn('all',modes)
        self.assertIsNone(bytext[texts[5]]['native_structure']['mode'])

    def test_privacy_and_evidence_payloads_never_escape(self):
        row={'requirement_id':'req_123456789012','text':'Contact sample@example.com for details',
             'evidence':[{'text':'PRIVATE RESUME CONTENT'}],'resume_profile':{'secret':'NO'}}
        out=inventory.build_export([self.synthetic_view([row],row['text'])])
        body=json.dumps(out)
        self.assertNotIn('sample@example.com',body)
        self.assertNotIn('PRIVATE RESUME',body)
        self.assertNotIn('resume_profile',body)
        r=out['records'][0]
        self.assertEqual(r['requirement_id'],row['requirement_id'])
        self.assertEqual(r['readiness']['recognition'],'BLOCKED_REDACTED_EXPORT')

    def test_schema_and_tampering_validation(self):
        a=inventory.build_export([self.views[0]])
        a['records'][0]['requirement']['text']='tampered'
        with self.assertRaisesRegex(ValueError,'fingerprint'):
            inventory.validate_export(a)
        a['export_fingerprint']=inventory.digest({k:v for k,v in a.items() if k!='export_fingerprint'})
        with self.assertRaisesRegex(ValueError,'fingerprint'):
            inventory.validate_export(a)

    def test_false_input_completeness_and_unapproved_sources_fail_closed(self):
        view=deepcopy(self.views[0]);view['full_evidence_available']=True
        with self.assertRaisesRegex(ValueError,'cannot certify'):
            inventory.build_export([view])
        with self.assertRaisesRegex(ValueError,'only the two tracked fixtures'):
            inventory.fixture_views(['data/production.sqlite3'])

    def test_cli_refuses_existing_artifacts_and_overlapping_output_paths(self):
        from unittest.mock import patch
        from scripts.export_source_aware_inventory_v1 import main
        with patch('sys.argv',['export','--output','bulk_unresolved_v1_architecture.md']):
            with self.assertRaisesRegex(ValueError,'never overwritten'):
                main()
        with patch('sys.argv',['export','--output','stage1_unused.json','--records-output','stage1_unused.json']):
            with self.assertRaisesRegex(ValueError,'different new paths'):
                main()

    def test_duplicate_canonical_ids_fail_even_if_content_differs(self):
        rows=[{'requirement_id':'same','text':text} for text in ['Knowledge of REST API','Experience with Node.js']]
        with self.assertRaisesRegex(ValueError,'Duplicate canonical requirement ID'):
            inventory.build_export([self.synthetic_view(rows,'\n'.join(r['text'] for r in rows))])


if __name__=='__main__':
    unittest.main()

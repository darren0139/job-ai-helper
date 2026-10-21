"""Offline research-contract tests; no new production matching expectations."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from scripts import investigate_existing_predicate_backlog_v2 as v
from tests.predicate_historical_fixtures import verified_paths


class InvestigationTests(unittest.TestCase):
    def setUp(self):
        report,manifest=verified_paths()
        self.enterContext(patch.object(v,'REPORT',report))
        self.enterContext(patch.object(v,'MANIFEST',manifest))

    def test_seal_tampering_fails_closed(self):
        body=v.seal({'cases':[]})
        with patch.object(v.Path,'read_text',return_value=json.dumps(body)):
            self.assertEqual(v.read_sealed('TEST_ONLY')['cases'],[])
        body['cases']=[{'invented':'TEST_ONLY'}]
        with patch.object(v.Path,'read_text',return_value=json.dumps(body)):
            with self.assertRaises(ValueError):v.read_sealed('TEST_ONLY')

    def test_no_candidate_evidence_exported(self):
        value={'reason':'saved native reason','evidence':[{'text':'PRIVATE'}],
            'nested':{'selected_resume':'PRIVATE','candidates':[{'capability_id':'TEST_ONLY'}]}}
        result=v.safe_history(value)
        self.assertNotIn('PRIVATE',json.dumps(result))
        self.assertEqual(result['reason'],'saved native reason')
        self.assertEqual(result['nested']['candidates'],[{'capability_id':'TEST_ONLY'}])
        self.assertIn('evidence',value)

    def test_original_count_jobs_text_and_provenance_required(self):
        rows=[{'job_id':1,'requirement_id':'TEST_ONLY_1','normalized_text_fingerprint':'1',
               'parent_source_available':True,'parent_provenance_verified':True}]
        v.validate_cohort(rows,1,1)
        with self.assertRaises(ValueError):v.validate_cohort(rows)
        rows[0]['parent_provenance_verified']=False
        with self.assertRaises(ValueError):v.validate_cohort(rows,1,1)

    def test_latest_active_same_hash_original_input_preserved(self):
        jobs=[{'id':1,'lifecycle_status':'active','content_hash':'same','description':'TEST ONLY'},
              {'id':2,'lifecycle_status':'expired','content_hash':'same','description':'TEST ONLY'}]
        def snapshot(i,j,h='same'):
            return {'id':i,'discovered_job_id':j,'job_content_hash':h,
                'requirements_json':json.dumps([{'requirement_id':'TEST_ONLY','text':'TEST ONLY'}])}
        rows=v.active_records(jobs,[snapshot(1,1),snapshot(2,1),snapshot(3,2),snapshot(4,99)])
        self.assertEqual([r['snapshot_id'] for r in rows],[2])
        self.assertEqual(rows[0]['requirement']['text'],'TEST ONLY')
        self.assertEqual(v.active_records(jobs,[snapshot(2,1,'changed')]),[])

    def test_reconstruction_reuses_original_analyzer_and_restores_patch(self):
        original=v.c.clusters
        def analyze(records,protected,resolve):
            rows=[{'dimensions':['existing_predicate_observations'],'requirement_id':'TEST_ONLY'}]
            v.c.clusters(rows)
            return {'TEST_ONLY':True}
        with patch.object(v.c,'analyze',side_effect=analyze),patch.object(v.c,'clusters',return_value=[]) as cluster:
            rows,stats=v.reconstruct([],{},resolve=lambda r:None)
            self.assertIs(v.c.clusters,cluster)
        self.assertIs(v.c.clusters,original)
        self.assertEqual(len(rows),1)
        self.assertTrue(stats['TEST_ONLY'])

    def test_database_and_protected_hashes_fail_closed(self):
        manifest={'database_sha256':'saved','protected_hashes':{'TEST_ONLY':'protected'}}
        with patch.object(v.c,'sha',side_effect=['changed']):
            with self.assertRaises(ValueError):v.assert_preserved(manifest,'TEST_ONLY')
        with patch.object(v.c,'sha',side_effect=['saved','changed']):
            with self.assertRaises(ValueError):v.assert_preserved(manifest,'TEST_ONLY')

    def test_frozen_manifest_has_exact_13_and_requirement_only_inputs(self):
        manifest=v.read_sealed(v.MANIFEST)
        v.validate_cohort(manifest['cases'])
        for case in manifest['cases']:
            self.assertEqual(case['input_fingerprint'],v.fingerprint(case['input']))
            self.assertFalse(set(case['input'])-set(v.c.FIELDS))
            self.assertTrue(case['parent_allocation_receipts'])
        self.assertEqual(len(manifest['protected_hashes']),150)

    def test_comparison_does_not_invent_historical_traces(self):
        current={'status':'unresolved','registry_resolution':{'reason':'same'},
                 'identity_scope':{'category':'activity'}}
        self.assertEqual(v.comparison({},current),'INSUFFICIENT_HISTORICAL_EVIDENCE')
        self.assertEqual(v.comparison({'status':'unresolved'},current),'UNCHANGED_UNRESOLVED')
        self.assertEqual(v.comparison({'status':'unresolved','registry_reason':'old'},current),
                         'BEHAVIOR_CHANGED_BUT_UNRESOLVED')
        self.assertEqual(v.comparison({'status':'resolved'},current),'NEWLY_UNRESOLVED')
        self.assertEqual(v.comparison({'status':'unresolved'},{'status':'resolved'}),'NOW_RESOLVED')
        self.assertEqual(v.comparison({'status':'unresolved'},{}),'NOT_COMPARABLE')

    def test_wrapped_source_occurrence_is_corroboration_not_claim_verification(self):
        inp={'source_provenance':[{'parent_occurrence_id':'TEST_ONLY','raw_parent_text':'Bounded source wording',
                                  'grounding':{'line_index':2}}]}
        anchors=v.source_anchors(inp,'Header\n* Bounded source\n wording')
        self.assertEqual(anchors[0]['corroborated_occurrence_count'],1)
        self.assertTrue(anchors[0]['recorded_line_matches_occurrence'])
        self.assertIn('not Phase8',anchors[0]['verification_limit'])
        self.assertEqual(v.source_anchors(inp,'Different source')[0]['corroborated_occurrence_count'],0)

    def test_probe_passes_exact_saved_input_no_applicant_evidence(self):
        inp={'text':'TEST ONLY','parent_text':'TEST ONLY PARENT','group_weight_fraction':0.5}
        row={'job_id':100,'requirement_id':'TEST_ONLY','input':deepcopy(inp),
             'predicate_observations':[],'historical_recorded_unresolved':True}
        manifest={'cases':[row],'fingerprint':'TEST_ONLY','protected_hashes':{},'database_sha256':'TEST_ONLY'}
        def resolve(value):
            self.assertEqual(value,inp)
            self.assertNotIn('evidence',value)
            return {'status':'unresolved','knowledge_status':'UNRESOLVED'}
        with patch.object(v,'read_sealed',return_value=manifest),patch.object(v,'assert_preserved'),\
             patch.object(v.Path,'exists',return_value=False),patch.object(v.Path,'write_text'),\
             patch.object(v.c,'sha',return_value='TEST_ONLY'),\
             patch.object(v.c,'resolve_requirement_with_production_knowledge',side_effect=resolve) as resolver:
            v.probe('TEST_ONLY')
        resolver.assert_called_once()
        self.assertEqual(row['input'],inp)

    def test_final_report_preserves_source_versions_and_no_promotions(self):
        report=v.read_sealed(v.REPORT);manifest=v.read_sealed(v.MANIFEST)
        self.assertEqual(report['manifest_fingerprint'],manifest['fingerprint'])
        self.assertEqual(len(report['cases']),13)
        for case, frozen in zip(report['cases'],manifest['cases']):
            self.assertEqual(case['key'],[frozen['job_id'],frozen['requirement_id']])
            self.assertEqual(case['input'],frozen['input'])
            self.assertEqual(case['source_versions'],frozen['source_versions'])
            self.assertEqual(case['parent_allocation_sum'],1)
            self.assertTrue(all(a['recorded_line_matches_occurrence'] for a in case['source_anchors']))
            self.assertNotIn(case['fix_justified'],['YES'])
        self.assertEqual(report['summary']['confirmed_current_defects'],0)
        self.assertFalse(report['preservation']['gold_decisions_used'])


if __name__=='__main__':unittest.main()

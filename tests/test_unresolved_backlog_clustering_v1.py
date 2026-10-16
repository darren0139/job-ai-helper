"""Mocked offline backlog selection/quarantine; no database or model calls."""
from copy import deepcopy
import json
import unittest
from unittest.mock import MagicMock,patch

from scripts import cluster_unresolved_backlog_v1 as c


class BacklogClusteringTests(unittest.TestCase):
    def setUp(self):
        self.protected={'keys':{(1,'protected')},'texts':['Proficiency in the example technology ecosystem'],
          'parent_texts':['Build a secure widget using the example technology ecosystem'],
          'families':{(1,'family')},'source_fingerprint':'TEST_ONLY'}

    def resolve(self,r):
        self.assertNotIn('evidence',r)
        return {'status':'unresolved','knowledge_status':'UNRESOLVED',
                'identity_scope':{'category':'TEST_ONLY_UNCERTAIN'},'registry_resolution':{'reason':'TEST_ONLY'},'taxonomy_diagnostics':{}}

    def record(self,text,rid='r1',job=2,**fields):
        req={'requirement_id':rid,'text':text,'atomic_focus':text,'score_eligible':True,'importance':'core',
             'parent_text':text,'match_label':'none','evidence':['PRIVATE RESUME MUST NOT EXPORT'],**fields}
        return {'job_key':f'job:{job}','job_id':job,'snapshot_id':10,'source_table':'TEST_ONLY',
                'source_versions':{'scoring_version':'TEST_ONLY'},'raw_jd_text':text,'requirement':req}

    def test_quarantine_keys_families_exact_near_and_parent_context(self):
        for row,reason in [
          (self.record('different text','protected',1),'protected_key'),
          (self.record('different child',scoring_parent_occurrence_id='family',job=1),'shared_protected_parent'),
          (self.record('PROFICIENCY IN THE EXAMPLE TECHNOLOGY ECOSYSTEM'),'protected_exact_text'),
          (self.record('Proficiency in an example technology ecosystem'),'protected_near_text_or_parent'),
          (self.record('harmless child',parent_text='Build a secure widget using the example technology ecosystem'),'protected_parent_clause_containment')]:
            self.assertEqual(c.quarantine_reason(row['requirement'],row['job_id'],self.protected),reason)
        self.assertIsNone(c.quarantine_reason(self.record('Plan a new warehouse layout')['requirement'],2,self.protected))

    def test_quarantine_happens_before_observations_and_examples(self):
        row=self.record('Proficiency in the example technology ecosystem','protected',1)
        with patch.object(c,'observations',side_effect=AssertionError('Protected example cannot be analyzed')):
            result=c.analyze([row],self.protected,resolve=self.resolve)
        self.assertEqual(result['development_occurrences'],0)
        self.assertEqual(result['clusters'],[])
        self.assertNotIn(row['requirement']['text'],json.dumps(result))

    def test_analysis_only_normalization_preserves_languages_and_qualification(self):
        self.assertEqual(c.normal('A\u200b  B'),'a b')
        self.assertNotEqual(c.normal('C++'),c.normal('C#'))
        self.assertNotEqual(c.normal('Java'),c.normal('JavaScript'))
        self.assertFalse(c.similar('Do not deploy Python services','Deploy Python services'))

    def test_multi_dimensions_not_primary_routes_or_evidence_credit(self):
        row=self.record('Experience with Python to build automated reports is preferred')
        result=c.analyze([row],self.protected,resolve=self.resolve)
        names={x['dimension'] for x in result['clusters']}
        self.assertIn('technology_alias_candidates',names)
        self.assertIn('activity_cues',names)
        self.assertIn('optional_or_alternative_cues',names)
        self.assertIn('technology_activity_cooccurrence',names)
        body=json.dumps(result)
        self.assertNotIn('PRIVATE RESUME',body);self.assertNotIn('primary_route',body)
        self.assertEqual(row['requirement']['match_label'],'none')

    def test_duplicate_views_keep_all_provenance_but_not_job_inflation(self):
        a=self.record('Respectfully coordinate daily logistics');b=deepcopy(a);b['snapshot_id']=11
        result=c.analyze([a,b],self.protected,resolve=self.resolve)
        self.assertEqual(result['distinct_unresolved_occurrences'],1)
        self.assertEqual(result['development_occurrences'],1)
        self.assertEqual(result['counts']['duplicate_current_record_views'],1)
        self.assertEqual(result['clusters'][0]['raw_record_views'],2)
        self.assertEqual(result['clusters'][0]['distinct_job_or_jd_keys'],1)

    def test_knowledge_and_applicant_none_are_separate(self):
        a=self.record('Known scoped requirement');b=self.record('Unrecognized scoped requirement','r2',match_label='transferable')
        def resolve(r):return {'status':'resolved','knowledge_status':'CAPABILITY_RESOLVED'} if r['requirement_id']=='r1' else self.resolve(r)
        result=c.analyze([a,b],self.protected,resolve=resolve)
        self.assertEqual(result['knowledge_resolved_but_stored_applicant_none'],1)
        self.assertEqual(result['counts']['unresolved_with_stored_positive_match'],1)
        self.assertEqual(result['counts']['current_knowledge_unresolved_records'],1)

    def test_privacy_sensitive_requirement_is_not_an_example(self):
        result=c.analyze([self.record('Contact jane@example.com for engineering work')],self.protected,resolve=self.resolve)
        self.assertEqual(result['quarantine_excluded_record_counts']['privacy_sensitive_text'],1)
        self.assertNotIn('jane@example.com',json.dumps(result))

    def test_latest_active_same_hash_selection_excludes_expired_orphan_stale(self):
        jobs=[{'id':i,'lifecycle_status':life,'content_hash':'same','description':'TEST ONLY'} for i,life in [(2,'active'),(3,'expired'),(4,'active')]]
        def snap(id,job,h='same'):return {'id':id,'discovered_job_id':job,'job_content_hash':h,
          'match_version':'TEST_ONLY','scoring_version':'TEST_ONLY','taxonomy_version':'TEST_ONLY','created_at':'TEST_ONLY',
          'requirements_json':json.dumps([{'requirement_id':'r','text':'TEST ONLY'}])}
        snapshots=[snap(1,2),snap(2,2),snap(3,3),snap(4,4,'changed'),snap(5,99)]
        with patch.object(c,'analyze',side_effect=lambda records,p:{'selected_ids':[r['snapshot_id'] for r in records]}):
            r=c.build_report(jobs,snapshots,[],{},self.protected)
        self.assertEqual(r['scopes']['active_same_hash']['selected_ids'],[2])
        self.assertEqual(r['scopes']['inactive_job']['selected_ids'],[3])
        self.assertEqual(r['selection']['stale_job_content'],1)
        self.assertEqual(r['selection']['orphaned_discovered_job'],1)
        self.assertEqual(r['snapshot_history_counts']['superseded_snapshot_rows'],1)
        self.assertEqual(r['snapshot_history_counts']['repeated_snapshot_record_views'],1)

    def test_read_only_uri_query_only_and_projection_no_resume_columns(self):
        conn=MagicMock()
        def execute(sql):
            result=MagicMock()
            if 'sqlite_master' in sql:result.__iter__.return_value=iter([('discovered_jobs',),('job_match_snapshots',)])
            elif sql.startswith('SELECT id,content_hash'):result.__iter__.return_value=iter([])
            elif sql.startswith('SELECT id,discovered_job_id'):result.__iter__.return_value=iter([])
            else:result.fetchone.return_value=(1,)
            return result
        conn.execute.side_effect=execute
        with patch.object(c.sqlite3,'connect',return_value=conn) as connect:
            c.read_database(c.ROOT/'data/applications.db')
        self.assertTrue(connect.call_args.args[0].endswith('?mode=ro'));self.assertTrue(connect.call_args.kwargs['uri'])
        statements=[x.args[0] for x in conn.execute.call_args_list]
        self.assertIn('PRAGMA query_only=ON',statements)
        self.assertIn('BEGIN',statements)
        self.assertFalse(any(x.startswith(('INSERT','UPDATE','DELETE','CREATE')) for x in statements))
        self.assertFalse(any('evidence_snapshot_json' in x or 'resume_profile' in x for x in statements))
        conn.commit.assert_not_called();conn.close.assert_called_once()

    def test_protected_forty_loaded_without_receipts_or_expected_answers(self):
        p=c.protected_sources();self.assertEqual(len(p['keys']),40)
        self.assertEqual(len(p['texts']),40)
        self.assertNotIn('acceptable_routes',p);self.assertNotIn('decisions',p)

    def test_near_group_does_not_merge_different_technologies(self):
        result=c.analyze([self.record('Familiarity with Python is strongly preferred'),self.record('Familiarity with Java is strongly preferred','r2')],self.protected,resolve=self.resolve)
        self.assertEqual(result['near_duplicate_groups'],[])

    def test_protected_parent_in_one_view_quarantines_all_same_occurrence_views(self):
        a=self.record('A neutral short child');b=deepcopy(a)
        b['requirement']['parent_text']=self.protected['parent_texts'][0]
        with patch.object(c,'observations',side_effect=AssertionError('No protected sibling view analysis')):
            result=c.analyze([a,b],self.protected,resolve=self.resolve)
        self.assertEqual(result['development_occurrences'],0)

    def test_different_parent_provenance_is_not_silently_treated_as_same_native_problem(self):
        a=self.record('Coordinate daily logistics');b=deepcopy(a)
        b['snapshot_id']=11;b['requirement']['parent_text']='Coordinate daily logistics and repair equipment'
        result=c.analyze([a,b],self.protected,resolve=self.resolve)
        self.assertTrue(any(x['multiple_scope_provenance_view_count']==1 for x in result['clusters']))

    def test_short_parent_subclause_cannot_leak_protected_context(self):
        p=deepcopy(self.protected)
        p['parent_texts'].append('A substantial separate protected activity is stated here. Another short technical clause is here.')
        r=self.record('Another short technical clause is here')['requirement']
        self.assertEqual(c.quarantine_reason(r,2,p),'protected_parent_clause_containment')


if __name__=='__main__':unittest.main()

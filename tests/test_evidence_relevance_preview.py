"""Independent synthetic relevance controls; never private or historical gold."""
from copy import deepcopy
import os
import sys
import unittest
from unittest.mock import Mock,patch

from job_discovery import coordinated_preview as base, developer_comparison as gate
from job_discovery import evidence_relevance_preview as experiment, native_evidence_observation as observer
from analysis_stability.coordinated_runtime import assert_analysis_publishable

TRAIT='Attention to detail and quality is a desired attribute'


class RelevancePreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.cache={}

    def setUp(self): self.enterContext(patch.dict(os.environ,{gate.GATE:'1'}))

    def prepared(self,bullets,requirement=TRAIT,extra=None,raw=''):
        items=[{'id':11,'category':'Project','title':'Synthetic import tool','bullets':list(bullets)}]
        if extra: items.extend(deepcopy(extra))
        key=repr((items,requirement,raw))
        if key not in self.cache:
            request=base.prepare_comparison(raw_jd_text='Requirements:\n- '+requirement,
                jd_profile={'job_title':'Engineer'},evidence_items=items,raw_only_text=raw)
            self.cache[key]=(request,base.run_comparison(request,developer_enabled=True))
        return self.cache[key]

    def run_preview(self,bullets,**kwargs):
        request,baseline=self.prepared(bullets,**kwargs)
        return experiment.evaluate(request,session_enabled=True,baseline=baseline)

    def test_independent_quality_activity_recovers_only_weak(self):
        for claim in ('Implemented import checks ensuring data integrity.',
                      'Improved the pipeline consistency by validating imports.',
                      'Improved pipeline consistency by validating asset imports.',
                      'Applied row-level security policies to protect stored records.'):
            with self.subTest(claim=claim):
                result=self.run_preview([claim]); rows=result['experimental_analysis']['canonical_requirements']
                self.assertEqual(result['baseline'].published.requirements[0].label.value,'NONE')
                self.assertEqual(result['baseline'].gated.requirements[0].label.value,'NONE')
                self.assertEqual(rows[0]['match_label'],'weak')
                self.assertEqual(rows[0]['match_value'],base.native.MATCH_VALUES['weak'])
                self.assertEqual(len(rows[0]['evidence']),1)
                self.assertEqual(rows[0]['evidence'][0]['text'],claim)
                self.assertEqual(result['changes'][0]['library_item_id'],11)
                self.assertEqual(result['changes'][0]['ceiling'],'weak')

    def test_no_global_threshold_relaxation_or_unrelated_relevance(self):
        cases=('Programmed a Python chatbot.','Used SQLite.','Reviewed a film.',
               'Implemented a report generator.','Implemented a React page. Access control is listed.',
               'Access control','Discussed data integrity.','Planned to implement data integrity checks.',
               'Never implemented row-level security.','My colleague applied row-level security policies.',
               'The team implemented access control.','Read an access control tutorial.')
        cases+=('Implemented a chatbot about data integrity.',
                'Implemented React while another developer applied row-level security.',
                'Implemented React and someone ensured data integrity.',
                'Implemented a webpage about access control.')
        for claim in cases:
            with self.subTest(claim=claim):
                result=self.run_preview([claim])
                self.assertEqual(result['changes'],[])
                self.assertEqual(result['experimental_view'].requirements[0].label.value,'NONE')

    def test_source_scope_negative_veto_and_no_cross_bullet_support(self):
        result=self.run_preview(['Implemented import checks.','Data integrity'])
        self.assertEqual(result['changes'],[])
        result=self.run_preview(['Implemented import checks ensuring data integrity.',
                                'Never implemented data integrity checks.'])
        self.assertEqual(result['changes'],[])
        result=self.run_preview(['Implemented import checks ensuring data integrity.'],raw='Never implemented data integrity checks.')
        self.assertEqual(result['changes'],[])
        result=self.run_preview(['Implemented import checks ensuring data integrity.'],extra=[
            {'id':12,'category':'Project','title':'Unrelated project','bullets':['Never implemented data integrity checks.']}])
        self.assertEqual(result['changes'][0]['library_item_id'],11)
        self.assertEqual(len(result['experimental_view'].requirements[0].evidence),1)

    def test_no_compound_obligation_or_other_capability_promotion(self):
        for requirement in ('Attention to detail and maintain REST API endpoints',
                            'Knowledge of SQL and NoSQL databases','Write engineering documentation',
                            'Collaborate to specify, design, build and maintain software applications',
                            'Implement custom REST API endpoints','Knowledge of data structures and algorithms'):
            with self.subTest(requirement=requirement):
                result=self.run_preview(['Applied row-level security policies to protect stored records.'],requirement=requirement)
                self.assertEqual(result['changes'],[])
        result=self.run_preview(['Handled data for a help-desk application.'],requirement='Knowledge of data structures and algorithms')
        self.assertTrue(all(r.label.value=='NONE' for r in result['experimental_view'].requirements))

    def test_geometry_published_parity_and_determinism(self):
        request,baseline=self.prepared(['Implemented import checks ensuring data integrity.'])
        before=deepcopy(baseline)
        with patch.object(base,'run_comparison',side_effect=AssertionError('Retained baseline must not rescore')):
            a=experiment.evaluate(request,session_enabled=True,baseline=baseline)
            b=experiment.evaluate(request,session_enabled=True,baseline=baseline)
        self.assertEqual(a,b); self.assertEqual(before,baseline)
        fields=('requirement_id','text','importance','atomic_group_id','group_weight_fraction')
        self.assertEqual([[r.get(k) for k in fields] for r in baseline.gated_analysis['canonical_requirements']],
                         [[r.get(k) for k in fields] for r in a['experimental_analysis']['canonical_requirements']])
        self.assertEqual(a['experimental_analysis']['scoring_version'],experiment.SCORING_VERSION)
        self.assertEqual(a['experimental_analysis']['capability_taxonomy_version'],baseline.gated_analysis['capability_taxonomy_version'])

    def test_explicit_gate_and_stale_source_identity(self):
        request,baseline=self.prepared(['Implemented import checks ensuring data integrity.'])
        with self.assertRaises(ValueError): experiment.evaluate(request,baseline=baseline)
        with patch.dict(os.environ,{gate.GATE:''}),self.assertRaises(ValueError):
            experiment.evaluate(request,session_enabled=True,baseline=baseline)
        bad=deepcopy(request);bad.projection['evidence_items'][0]['title']='changed'
        with self.assertRaises(ValueError):experiment.evaluate(bad,session_enabled=True,baseline=baseline)

    def test_other_review_required_parent_keeps_whole_jd_unavailable(self):
        from scripts.coordinated_job_match_preview_inputs import preview_inputs
        inputs=preview_inputs('E04');inputs['raw_jd_text']+='\n- '+TRAIT
        inputs['evidence_items'].append({'id':901,'category':'Project','title':'Synthetic import tool',
            'bullets':['Implemented import checks ensuring data integrity.']})
        request=base.prepare_comparison(**inputs)
        baseline=base.run_comparison(request,developer_enabled=True)
        self.assertGreater(baseline.gated.review_count,0)
        result=experiment.evaluate(request,session_enabled=True,baseline=baseline)
        self.assertEqual(result['experimental_view'].review_count,baseline.gated.review_count)
        self.assertFalse(result['experimental_view'].score_available)
        self.assertIsNone(result['experimental_view'].alignment)
        self.assertTrue(result['changes'])
        for row in result['experimental_view'].requirements:
            if row.label.value=='REVIEW_REQUIRED': self.assertIsNone(row.contribution)

    def test_new_identity_rejects_all_persistence_before_database_access(self):
        from database import job_match_manager as matches,analysis_cache_manager as cache
        bare={'scoring_version':experiment.SCORING_VERSION,'canonical_requirements':[]}
        with self.assertRaises(ValueError):assert_analysis_publishable(bare)
        with patch.object(matches,'init_job_match_schema',side_effect=AssertionError('No DB')):
            with self.assertRaises(ValueError):matches.save_job_match_snapshot(discovered_job_id=1,job_content_hash='x',
                evidence_fingerprint='x',match_version='x',scoring_version=experiment.SCORING_VERSION,taxonomy_version='x',
                jd_profile={},evidence_snapshot=[],stable_analysis=bare,summary={})
        connection=Mock()
        with self.assertRaises(ValueError):cache.insert_analysis_snapshot_with_connection(connection,
            application_id=1,input_fingerprint='x',report={'stable_analysis':bare},analysis_model='offline',
            resume_filename='x',analysis_id='x',created_at='x')
        connection.execute.assert_not_called()

    def test_actual_native_observer_parity_threshold_reason_and_owner(self):
        request,baseline=self.prepared(['Implemented import checks ensuring data integrity.'])
        observed,data=observer.observe(request,session_enabled=True)
        self.assertEqual(observed,baseline);self.assertEqual(data['observer_errors'],0)
        self.assertEqual(data['dropped_events'],0);self.assertIsNone(sys.gettrace())
        rejection=[e for e in data['events'] if e['event']=='RECOVERY_WEAK_ZERO_OVERLAP_REJECTED' and e['side']=='published']
        self.assertTrue(rejection)
        self.assertEqual(rejection[0]['library_owner_ids'],[11])
        self.assertEqual(rejection[0]['taxonomy_label'],'weak')
        self.assertEqual(rejection[0]['taxonomy_reason_code'],experiment.REASON)
        self.assertEqual(rejection[0]['metrics']['overlap'],0)
        self.assertNotIn('Implemented import checks',str(data))

    def test_observer_gate_bounds_failure_cleanup_and_no_existing_trace_override(self):
        request,_=self.prepared(['Implemented import checks ensuring data integrity.'])
        with self.assertRaises(ValueError):observer.observe(request)
        with patch.object(observer,'MAX_EVENTS',1):
            _,data=observer.observe(request,session_enabled=True)
        self.assertLessEqual(len(data['events']),1);self.assertGreater(data['dropped_events'],0)
        with patch.object(base,'run_comparison',side_effect=RuntimeError('synthetic failure')):
            with self.assertRaises(RuntimeError):observer.observe(request,session_enabled=True)
        self.assertIsNone(sys.gettrace())
        with patch.object(sys,'gettrace',return_value=object()),self.assertRaises(ValueError):
            observer.observe(request,session_enabled=True)

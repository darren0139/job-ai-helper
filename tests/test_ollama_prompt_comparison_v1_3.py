"""Offline source preservation and sealed experiment tests; no inference."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch
from scripts import compare_ollama_unresolved_prompts_v1_3 as study
from tests.ollama_current_fixtures import comparison_artifacts


def proposal(case,route=None):
    o=case['source_observations']
    return dict(proposed_route=route or case['expected_routes'][0],requirement_interpretation='Bounded diagnostic; native blocker unverified.',
        technology_mentions=o['technology_names'],explicit_activities=[a['span'] for a in o['affirmative_activities']],
        structural_observations=o['negative_scope_spans']+o['alternative_spans']+o['technology_activity_links'],
        supporting_source_spans=case['expected_supporting_spans'],unsupported_inferences_avoided=['No approval or applicant proficiency inferred.'],
        reasoning_summary='Source-first investigation only.',needs_human_review=True)


class SourceFirstTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(comparison_artifacts())
        self.plan=study.freeze_plan();self.calls=[]
        for name,val in [('runtime_state',{'generation_activity':'IDLE_OBSERVED'}),('readiness',{'gate':'MOCK_ONLY'})]:
            p=patch.object(study.legacy,name,return_value=val);p.start();self.addCleanup(p.stop)

    def case(self,name):return next(j['case'] for j in self.plan['jobs'] if j['case']['id']==name)

    def evaluate(self,case,obj):
        native=study.legacy.validate(json.dumps(obj),case)
        return native,study.research_validate(native,case)

    def http(self,endpoint,payload=None,timeout=5):
        if endpoint=='version':return {'version':'TEST'}
        if endpoint=='tags':return {'models':[{'name':study.legacy.MODEL,'digest':study.DIGEST,'details':{'family':'qwen3','parameter_size':'8.2B'}}]}
        self.assertEqual(endpoint,'generate');self.calls.append(payload)
        job=next(j for j in self.plan['jobs'] if study.prompt(j['case'],j['version'])==payload['prompt'])
        return {'model':study.legacy.MODEL,'done':True,'done_reason':'stop','response':json.dumps(proposal(job['case']))}

    def test_same_schema_versions_and_no_hidden_expectations(self):
        self.assertEqual(self.plan['schema'],study.legacy.SCHEMA)
        for j in self.plan['jobs']:
            text=study.prompt(j['case'],j['version'])
            self.assertNotIn('source_observations',text);self.assertNotIn('expected_routes',text)
            self.assertNotIn('expected_supporting_spans',text);self.assertNotIn('fingerprint',text)
            if j['version']==study.OLD_VERSION:self.assertEqual(text,study.old.prompt(j['case']))
        self.assertTrue(study.isolation([j['case'] for j in self.plan['jobs']]))

    def test_freeze_exact_twenty_and_semantic_contrast(self):
        self.assertEqual(len(self.plan['jobs']),20)
        self.assertEqual([j['version'] for j in self.plan['jobs'][:4]],[study.VERSION]*4)
        self.assertEqual(len(study.load_holdout()['cases']),8)
        self.assertEqual(self.case('fresh_01')['source_observations']['technology_names'],self.case('fresh_02')['source_observations']['technology_names'])
        self.assertNotEqual(self.case('fresh_01')['expected_routes'],self.case('fresh_02')['expected_routes'])

    def test_metadata_only_and_twenty_serial_requests(self):
        self.assertEqual(study.run(self.plan,http=self.http)['executed_classification_requests'],0)
        checkpoints=[]
        r=study.run(self.plan,execute=True,http=self.http,checkpoint=lambda x:checkpoints.append(deepcopy(x)))
        self.assertEqual(len(self.calls),20);self.assertTrue(study.validate_report(r,self.plan))
        self.assertEqual(checkpoints[0]['rows'][0]['status'],'REQUEST_RESERVED')
        self.assertTrue(all(row['research_validation']['contract_valid'] for row in r['rows']))
        self.assertTrue(all(p['options']==study.OPTIONS and p['format']==study.legacy.SCHEMA for p in self.calls))

    def test_missing_activity_and_source_denial_reject_only_new_contract(self):
        c=self.case('holdout_03');obj=proposal(c,'TECH_ID')
        obj.update(explicit_activities=[],requirement_interpretation='Named technology without any bounded implementation obligation.')
        native,new=self.evaluate(c,obj)
        self.assertTrue(native['contract_valid']);self.assertIsNotNone(native['proposal'])
        self.assertFalse(new['contract_valid']);self.assertIsNone(new['proposal'])
        self.assertIn('OMITTED_FROZEN_AFFIRMATIVE_ACTIVITY',new['objective_source_failures'])
        self.assertIn('DENIES_EXPLICIT_TECHNICAL_OBLIGATION',new['objective_source_failures'])

    def test_identity_route_plus_preserved_activity_is_flag_not_rejection(self):
        c=self.case('fresh_02');_,new=self.evaluate(c,proposal(c,'TECH_ID'))
        self.assertTrue(new['contract_valid'])
        self.assertIn('IDENTITY_PRIMARY_DESPITE_ACTIVITY_NATIVE_BLOCKER_UNVERIFIED',new['semantic_review_flags'])
        self.assertFalse(new['human_approval'])

    def test_technology_absence_and_omission(self):
        c=self.case('fresh_01');obj=proposal(c);obj['technology_mentions']=[]
        obj['requirement_interpretation']='No named technology is present.'
        _,new=self.evaluate(c,obj)
        self.assertIn('OMITTED_FROZEN_EXPLICIT_TECHNOLOGY',new['objective_source_failures'])
        self.assertIn('DENIES_EXTRACTED_TECHNOLOGY',new['objective_source_failures'])

    def test_exposure_professional_route_review(self):
        c=self.case('fresh_01');_,new=self.evaluate(c,proposal(c,'NOT_TAXONOMY_ADDRESSABLE'))
        self.assertIn('TECHNOLOGY_ONLY_MISROUTED_AS_PROFESSIONAL',new['semantic_review_flags'])
        c=self.case('fresh_05');_,new=self.evaluate(c,proposal(c))
        self.assertEqual(new['semantic_review_flags'],[])

    def test_negative_unqualified_activity_not_positive_obligation(self):
        c=self.case('fresh_07');obj=proposal(c);obj['explicit_activities']=['database tuning and administration']
        _,new=self.evaluate(c,obj)
        self.assertIn('NEGATIVE_SCOPE_IN_UNQUALIFIED_ACTIVITY_FIELD',new['semantic_review_flags'])
        obj['explicit_activities']=['database tuning and administration are not required']
        _,new=self.evaluate(c,obj)
        self.assertNotIn('NEGATIVE_SCOPE_IN_UNQUALIFIED_ACTIVITY_FIELD',new['semantic_review_flags'])
        self.assertTrue(new['source_measures']['negative_scope_requires_human_semantic_review'])

    def test_alternative_presence_does_not_prove_structure_error(self):
        c=self.case('fresh_07');_,new=self.evaluate(c,proposal(c,'STRUCTURAL'))
        self.assertIn('STRUCTURE_FAILURE_NOT_SUPPLIED',new['semantic_review_flags'])
        self.assertEqual(new['source_measures']['affirmative_activity_total'],0)

    def test_injection_influence_is_reviewed_not_claimed_causal(self):
        c=self.case('fresh_08');_,new=self.evaluate(c,proposal(c,'UNKNOWN'))
        self.assertIn('POSSIBLE_INJECTION_ROUTE_INFLUENCE_NOT_CAUSALLY_PROVEN',new['semantic_review_flags'])
        _,new=self.evaluate(c,proposal(c))
        self.assertEqual(new['semantic_review_flags'],[])

    def test_unsupported_capability_gap_and_ids_fail_closed(self):
        c=self.case('fresh_02');_,new=self.evaluate(c,proposal(c,'CAPABILITY'))
        self.assertIn('CAPABILITY_WITHOUT_SUPPLIED_PREDICATE',new['semantic_review_flags'])
        _,new=self.evaluate(c,proposal(c,'TRUE_GAP_CANDIDATE'))
        self.assertFalse(new['contract_valid']);self.assertIsNone(new['proposal'])
        obj=proposal(c);obj['reasoning_summary']='backend.invented'
        native,new=self.evaluate(c,obj)
        self.assertFalse(native['contract_valid']);self.assertIsNone(new['proposal'])

    def test_grounding_rejection_cannot_be_rehabilitated(self):
        c=self.case('fresh_02');obj=proposal(c);obj['explicit_activities']=['Design a worldwide system']
        native,new=self.evaluate(c,obj)
        self.assertFalse(native['contract_valid']);self.assertFalse(new['contract_valid']);self.assertIsNone(new['proposal'])

    def test_tampered_plan_and_result_provenance(self):
        p=deepcopy(self.plan);p['jobs'][0]['case']['expected_routes']=['CAPABILITY'];p.pop('fingerprint');p['fingerprint']=study.fingerprint(p)
        with self.assertRaises(ValueError):study.validate_plan(p)
        r=study.run(self.plan,http=self.http);r['plan_fingerprint']='OTHER';r.pop('fingerprint');r['fingerprint']=study.fingerprint(r)
        with self.assertRaises(ValueError):study.validate_report(r,self.plan)

    def test_timeout_no_retry_and_outstanding_work_no_generation(self):
        def failed(endpoint,payload=None,timeout=5):
            if endpoint=='generate':self.calls.append(payload);raise TimeoutError('TEST')
            return self.http(endpoint,payload,timeout)
        r=study.run(self.plan,execute=True,http=failed)
        self.assertEqual(len(self.calls),1);self.assertEqual(len(r['rows']),1)
        with patch.object(study.legacy,'runtime_state',return_value={'generation_activity':'UNKNOWN'}):
            r=study.run(self.plan,execute=True,http=self.http)
        self.assertEqual(r['executed_classification_requests'],0)

    def test_digest_change_and_finite_loopback_request(self):
        def changed(endpoint,payload=None,timeout=5):
            value=self.http(endpoint,payload,timeout)
            if endpoint=='tags':value['models'][0]['digest']='WRONG'
            return value
        with self.assertRaises(ValueError):study.run(self.plan,execute=True,http=changed)
        self.assertEqual(self.calls,[])
        http=study.make_transport(self.plan);j=self.plan['jobs'][0]
        p={'model':study.legacy.MODEL,'prompt':study.prompt(j['case'],j['version']),'format':study.legacy.SCHEMA,'options':study.OPTIONS,'stream':False,'think':False}
        with patch.object(study.urllib.request,'build_opener') as opener:
            opener.return_value.open.return_value.__enter__.return_value.read.return_value=b'{"response":"{}"}'
            http('generate',p,180)
            self.assertEqual(opener.return_value.open.call_args.args[0].full_url,'http://127.0.0.1:11434/api/generate')
            self.assertEqual(opener.call_args.args[0].proxies,{})
            self.assertIsInstance(opener.call_args.args[1],study._NoRedirect)
        for timeout in (float('inf'),0,181):
            with self.assertRaises(ValueError):http('generate',p,timeout)
        with self.assertRaises(ValueError):http('generate',p|{'prompt':'OTHER'},180)


if __name__=='__main__':unittest.main()

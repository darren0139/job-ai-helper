"""Mocked local transport only; no inference on discovery or offline validation."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from scripts import smoke_ollama_unresolved_adjudication_v1 as smoke


def proposal(case, route='UNKNOWN'):
    return {'proposed_route':route,'requirement_interpretation':'Synthetic scoped requirement.',
        'technology_mentions':[],'explicit_activities':[], 'structural_observations':[],
        'supporting_source_spans':[case['requirement']], 'reasoning_summary':'Context remains bounded.',
        'unsupported_inferences_avoided':['No identities or applicant skills invented.'], 'needs_human_review':True}


class LocalSmokeTests(unittest.TestCase):
    def http(self, endpoint, payload=None, timeout=5):
        self.calls.append((endpoint,payload))
        if endpoint=='version':return {'version':'TEST_ONLY'}
        if endpoint=='tags':return {'models':[{'name':smoke.MODEL,'digest':'TEST_ONLY',
            'details':{'family':'qwen3','parameter_size':'8.2B'}}]}
        return {'model':smoke.MODEL,'done':True,'response':json.dumps(proposal(smoke.CASES[0]))}

    def setUp(self):
        self.calls=[]
        # Transport/schema tests do not repeatedly rebuild the 40-case review.
        patcher=patch.object(smoke,'readiness',return_value={'formal_benchmark_executed':False})
        self.mock_readiness=patcher.start();self.addCleanup(patcher.stop)

    def test_actual_readiness_validator_no_new_labels(self):
        self.mock_readiness.side_effect=None
        with patch.object(smoke,'readiness',wraps=REAL_READINESS):
            r=smoke.readiness()
        self.assertEqual(r['existing_validator_summary']['confirmed'],2)
        self.assertFalse(r['existing_validator_summary']['labeling_prerequisite_satisfied'])
        self.assertEqual(r['v4_blank_decisions'],18)
        self.assertEqual(r['additional_independent_actionable_needed'],18)
        self.assertFalse(r['formal_benchmark_executed'])

    def test_preflight_no_inference_and_import_is_passive(self):
        r=smoke.run(http=self.http)
        self.assertEqual([c[0] for c in self.calls],['version','tags'])
        self.assertEqual(r['inference_requests'],0);self.assertFalse(r['formal_benchmark_executed'])

    def test_explicit_only_selected_synthetic_case_and_strict_payload(self):
        r=smoke.run(execute=True,http=self.http,limit=1)
        self.assertEqual(r['inference_requests'],1)
        payload=self.calls[-1][1]
        self.assertEqual(payload['format'],smoke.SCHEMA)
        self.assertEqual(payload['model'],smoke.MODEL)
        self.assertFalse(payload['stream']);self.assertFalse(payload['think'])
        self.assertEqual(payload['options']['temperature'],0)
        self.assertNotIn('expected_routes',payload['prompt'])

    def test_missing_or_remote_model_no_inference(self):
        for remote in (False,True):
            def http(endpoint,payload=None,timeout=5):
                if endpoint=='version':return {'version':'TEST'}
                if endpoint=='tags':return {'models':[{'name':smoke.MODEL,'remote_host':'cloud','details':{'family':'qwen3','parameter_size':'8.2B'}}] if remote else []}
                self.fail('No inference when model unavailable/remote')
            self.assertEqual(smoke.run(execute=True,http=http)['inference_requests'],0)

    def test_bounds_and_no_retry_after_failure(self):
        for limit,repeats in [(9,0),(0,0),(1,3)]:
            with self.assertRaises(ValueError):smoke.run(http=self.http,limit=limit,repeats=repeats)
        with self.assertRaises(ValueError):smoke.run(http=self.http,total_seconds=float('inf'))
        def failing(endpoint,payload=None,timeout=5):
            if endpoint=='generate':raise TimeoutError('TEST timeout')
            return self.http(endpoint,payload,timeout)
        r=smoke.run(execute=True,http=failing)
        self.assertEqual(r['inference_requests'],1)
        self.assertEqual(r['rows'][0]['classification'],'TRANSPORT_RUNTIME_FAILURE')

    def test_strict_types_extra_fields_duplicates_and_thinking_rejected(self):
        c=smoke.CASES[0];obj=proposal(c)
        for raw in [json.dumps(obj|{'execute':'delete files'}), json.dumps(obj|{'needs_human_review':1}),
                    json.dumps(obj|{'technology_mentions':[12]}),
                    '{"proposed_route":"UNKNOWN","proposed_route":"TECH_ID"}', '<think>hidden</think>{}']:
            self.assertFalse(smoke.validate(raw,c)['contract_valid'])
            self.assertIsNone(smoke.validate(raw,c)['proposal'])

    def test_ungrounded_identity_and_span_rejected(self):
        c=smoke.CASES[0]
        for obj in [proposal(c)|{'technology_mentions':['Invented technology']},
                    proposal(c)|{'supporting_source_spans':['fabricated']},
                    proposal(c)|{'reasoning_summary':'technology.invented'},
                    proposal(c)|{'reasoning_summary':'I approve the mapping.'}]:
            self.assertFalse(smoke.validate(json.dumps(obj),c)['contract_valid'])

    def test_unknown_abstention_valid_and_no_source_mutation(self):
        c=deepcopy(smoke.CASES[5]);before=deepcopy(c)
        result=smoke.validate(json.dumps(proposal(c)),c)
        self.assertTrue(result['contract_valid']);self.assertEqual(c,before)
        self.assertTrue(result['proposal']['needs_human_review'])

    def test_prompt_no_expected_labels_or_protected_inputs(self):
        self.assertTrue(smoke.check_synthetic_isolation())
        for c in smoke.CASES:
            self.assertNotIn('expected_routes',smoke.prompt(c))
            self.assertIn('UNTRUSTED DATA',smoke.prompt(c))
        with self.assertRaises(ValueError):smoke.local_http('https://example.com')
        with self.assertRaises(ValueError):smoke.local_http('generate',{'model':'cloud','format':smoke.SCHEMA})

    def test_http_proxy_disabled_and_no_redirects(self):
        with patch.object(smoke.urllib.request,'build_opener') as opener:
            opener.return_value.open.return_value.__enter__.return_value.read.return_value=b'{"version":"TEST"}'
            self.assertEqual(smoke.local_http('version')['version'],'TEST')
            url=opener.return_value.open.call_args.args[0].full_url
            self.assertEqual(url,'http://127.0.0.1:11434/api/version')
            self.assertEqual(opener.call_args.args[0].proxies,{})
            self.assertIsInstance(opener.call_args.args[1],smoke._NoRedirect)


REAL_READINESS=smoke.readiness


class RuntimeRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.calls=[]
        for name,value in [('readiness',{'gate':'TEST_ONLY','formal_benchmark_executed':False}),
                           ('runtime_state',{'generation_activity':'IDLE_OBSERVED'}),
                           ('runtime_diagnostics',{'generation_activity':'IDLE_OBSERVED'})]:
            patcher=patch.object(smoke,name,return_value=value)
            patcher.start();self.addCleanup(patcher.stop)

    def http(self,endpoint,payload=None,timeout=5):
        if endpoint=='version':return {'version':'TEST_ONLY'}
        if endpoint=='tags':return {'models':[{'name':smoke.MODEL,'details':{'family':'qwen3','parameter_size':'8.2B'}}]}
        self.assertEqual(endpoint,'generate');self.calls.append((payload,timeout))
        if payload['prompt']==smoke.BASIC_PROMPT:text='OK'
        else:
            case=next(c for c in smoke.CASES if c['requirement'] in payload['prompt'])
            text=json.dumps(proposal(case,case['expected_routes'][0]))
        return {'model':smoke.MODEL,'done':True,'done_reason':'stop','response':text,'eval_count':20,
                'load_duration':1,'eval_duration':2,'total_duration':3,'prompt_eval_count':10,'prompt_eval_duration':1}

    def test_one_basic_eight_classifications_two_repeats_no_duplicate_stage3(self):
        report=smoke.recover_runtime(http=self.http)
        self.assertEqual(len(self.calls),11)
        self.assertEqual(len(report['rows']),8);self.assertEqual(len(report['repeatability_rows']),2)
        self.assertEqual(report['summary']['contract_valid'],8)
        self.assertTrue(all(row['same_validated_proposal'] for row in report['repeatability_rows']))
        self.assertNotIn('format',self.calls[0][0])
        for payload,timeout in self.calls[1:]:
            self.assertEqual(payload['format'],smoke.SCHEMA);self.assertEqual(payload['options']['num_predict'],512)
            self.assertLessEqual(timeout,180)

    def test_basic_failure_stops_without_retry(self):
        def fail(endpoint,payload=None,timeout=5):
            if endpoint=='generate':self.calls.append((payload,timeout));raise TimeoutError('TEST')
            return self.http(endpoint,payload,timeout)
        report=smoke.recover_runtime(http=fail)
        self.assertEqual(len(self.calls),1);self.assertEqual(report['rows'],[])

    def test_schema_or_truncation_failure_in_stage3_stops(self):
        for text,reason in [('{}','stop'),(json.dumps(proposal(smoke.CASES[0])),'length')]:
            self.calls=[]
            def bad(endpoint,payload=None,timeout=5):
                result=self.http(endpoint,payload,timeout)
                if payload and 'format' in payload:result.update(response=text,done_reason=reason)
                return result
            report=smoke.recover_runtime(http=bad)
            self.assertEqual(len(self.calls),2)
            self.assertIn('Stage3',report['stop_reason'])

    def test_outstanding_generation_blocks_all_requests(self):
        with patch.object(smoke,'runtime_state',return_value={'generation_activity':'POSSIBLE_OUTSTANDING_GENERATION'}):
            report=smoke.recover_runtime(http=self.http)
        self.assertEqual(self.calls,[]);self.assertEqual(report['generation_requests'],0)

    def test_finite_time_and_output_bounds(self):
        for kwargs in [{'request_timeout':181},{'total_seconds':float('inf')},{'output_tokens':4096},{'repeats':3}]:
            with self.assertRaises(ValueError):smoke.recover_runtime(http=self.http,**kwargs)

    def test_original_cases_schema_and_prompt_unchanged(self):
        previous=json.loads((smoke.ROOT/'reports/ollama_unresolved_adjudication_smoke_v1.json').read_text())
        self.assertEqual(smoke.CASES,previous['synthetic_dataset'])
        self.assertEqual(smoke.SCHEMA,previous['schema'])
        self.assertEqual(smoke.fingerprint(smoke.prompt(smoke.CASES[0])),previous['rows'][0]['prompt_fingerprint'])

    def test_basic_http_allowlist_does_not_relax_classification_schema(self):
        payload={'model':smoke.MODEL,'prompt':smoke.BASIC_PROMPT,'stream':False,'think':False,'options':smoke.BASIC_OPTIONS}
        with patch.object(smoke.urllib.request,'build_opener') as opener:
            opener.return_value.open.return_value.__enter__.return_value.read.return_value=b'{"response":"OK"}'
            self.assertEqual(smoke.local_http('generate',payload,180)['response'],'OK')
        with self.assertRaises(ValueError):smoke.local_http('generate',payload|{'prompt':'arbitrary benchmark text'},180)
        with self.assertRaises(ValueError):smoke.local_http('generate',payload|{'prompt':'arbitrary benchmark text','format':smoke.SCHEMA},180)

    def test_basic_mode_only_one_request(self):
        report=smoke.recover_runtime(http=self.http,basic_only=True)
        self.assertEqual(len(self.calls),1);self.assertTrue(report['basic_generation']['basic_valid'])
        self.assertEqual(report['rows'],[])

if __name__=='__main__':unittest.main()

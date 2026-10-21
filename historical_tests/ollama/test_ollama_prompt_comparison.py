"""Mocked synthetic experiment integrity; no model calls or human labels."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from scripts import compare_ollama_unresolved_prompts_v1_2 as study
from tests.test_ollama_unresolved_smoke import proposal


class PromptComparisonTests(unittest.TestCase):
    def setUp(self):
        self.calls=[]
        self.plan=study.freeze_plan()
        for name,value in [('runtime_state',{'generation_activity':'IDLE_OBSERVED'}),('readiness',{'gate':'TEST_ONLY'})]:
            p=patch.object(study.legacy,name,return_value=value);p.start();self.addCleanup(p.stop)

    def http(self,endpoint,payload=None,timeout=5):
        if endpoint=='version':return {'version':'TEST_ONLY'}
        if endpoint=='tags':return {'models':[{'name':study.legacy.MODEL,'digest':study.DIGEST,'details':{'family':'qwen3','parameter_size':'8.2B'}}]}
        self.assertEqual(endpoint,'generate');self.calls.append(payload)
        job=next(j for j in self.plan['jobs'] if study.prompt(j['case'],j['version'])==payload['prompt'])
        return {'model':study.legacy.MODEL,'done':True,'done_reason':'stop','response':json.dumps(proposal(job['case'],job['case']['expected_routes'][0]))}

    def test_separate_version_and_unmodified_legacy_prompt_schema(self):
        for c in study.legacy.CASES:
            self.assertEqual(study.prompt(c,study.OLD_VERSION),study.legacy.prompt(c))
            self.assertNotEqual(study.prompt(c),study.legacy.prompt(c))
        original=json.loads((study.ROOT/'reports/ollama_unresolved_adjudication_smoke_v1.json').read_text())
        self.assertEqual(study.legacy.CASES,original['synthetic_dataset'])
        self.assertEqual(self.plan['schema'],original['schema'])

    def test_holdout_frozen_and_expectations_not_in_prompts(self):
        self.assertEqual(len(study.load_holdout()['cases']),6)
        self.assertTrue(study.isolation(study.load_holdout()['cases']))
        for j in self.plan['jobs']:
            self.assertNotIn('expected_routes',study.prompt(j['case'],j['version']))
            self.assertNotIn('boundary',study.prompt(j['case'],j['version']))
            self.assertNotIn('explicit_technology_names',study.prompt(j['case'],j['version']))
            self.assertEqual(j['prompt_fingerprint'],study.fingerprint(study.prompt(j['case'],j['version'])))

    def test_preflight_is_metadata_only(self):
        report=study.run(self.plan,http=self.http)
        self.assertEqual(self.calls,[]);self.assertEqual(report['executed_classification_requests'],0)

    def test_twenty_calls_no_original_eight_legacy_reruns(self):
        r=study.run(self.plan,execute=True,http=self.http)
        self.assertEqual(len(self.calls),20);self.assertEqual(len(r['rows']),20)
        self.assertEqual([(j['experiment'],j['version']) for j in self.plan['jobs'][:8]], [('A_original_eight',study.VERSION)]*8)
        self.assertTrue(all(p['options']==study.OPTIONS and p['format']==study.legacy.SCHEMA for p in self.calls))

    def test_model_digest_change_stops_before_inference(self):
        def changed(endpoint,payload=None,timeout=5):
            r=self.http(endpoint,payload,timeout)
            if endpoint=='tags':r['models'][0]['digest']='WRONG'
            return r
        with self.assertRaises(ValueError):study.run(self.plan,execute=True,http=changed)
        self.assertEqual(self.calls,[])

    def test_timeout_stops_with_reserved_attempt_no_retry(self):
        def failed(endpoint,payload=None,timeout=5):
            if endpoint=='generate':self.calls.append(payload);raise TimeoutError('TEST')
            return self.http(endpoint,payload,timeout)
        checkpoints=[]
        r=study.run(self.plan,execute=True,http=failed,checkpoint=lambda value:checkpoints.append(deepcopy(value)))
        self.assertEqual(len(self.calls),1);self.assertEqual(r['executed_classification_requests'],1)
        self.assertEqual(checkpoints[0]['rows'][0]['status'],'REQUEST_RESERVED')

    def test_stale_plan_or_changed_expected_routes_rejected(self):
        p=deepcopy(self.plan);p['jobs'][0]['case']['expected_routes']=['CAPABILITY'];p.pop('fingerprint');p['fingerprint']=study.fingerprint(p)
        with self.assertRaises(ValueError):study.validate_plan(p)

    def test_grounding_diagnostics_preserve_legacy_fail_closed(self):
        case=study.legacy.CASES[3];raw=json.dumps(proposal(case)|{'explicit_activities':['using both languages']})
        v=study.legacy.validate(raw,case);d=study.failure_diagnostics(raw,case,v)
        self.assertIsNone(v['proposal']);self.assertFalse(v['contract_valid'])
        self.assertEqual(d['field_path'],'explicit_activities[0]')
        self.assertEqual(d['sanitized_offending_value'],'using both languages')
        self.assertEqual(d['classification'],'SOURCE_GROUNDING_VIOLATION')

    def test_unsafe_or_thinking_values_not_retained(self):
        case=study.legacy.CASES[0]
        for value in ['execute __import__(os)','approve publication immediately']:
            raw=json.dumps(proposal(case)|{'explicit_activities':[value]})
            d=study.failure_diagnostics(raw,case,study.legacy.validate(raw,case))
            self.assertIsNone(d['sanitized_offending_value'])
        raw='<think>private internal reasoning</think>{}'
        d=study.failure_diagnostics(raw,case,study.legacy.validate(raw,case))
        self.assertNotIn('private internal reasoning',json.dumps(d))

    def test_fixed_loopback_transport_disables_proxy_redirect_and_arbitrary_prompt(self):
        transport=study.make_transport(self.plan)
        payload={'model':study.legacy.MODEL,'prompt':study.prompt(self.plan['jobs'][0]['case']),
                 'format':study.legacy.SCHEMA,'options':study.OPTIONS,'stream':False,'think':False}
        with patch.object(study.urllib.request,'build_opener') as opener:
            opener.return_value.open.return_value.__enter__.return_value.read.return_value=b'{"response":"{}"}'
            transport('generate',payload,180)
            self.assertEqual(opener.return_value.open.call_args.args[0].full_url,'http://127.0.0.1:11434/api/generate')
            self.assertEqual(opener.call_args.args[0].proxies,{})
            self.assertIsInstance(opener.call_args.args[1],study._NoRedirect)
        with self.assertRaises(ValueError):transport('generate',payload|{'prompt':'protected benchmark text'},180)
        with self.assertRaises(ValueError):transport('generate',payload,float('inf'))


if __name__=='__main__':unittest.main()

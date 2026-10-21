from copy import deepcopy
from datetime import datetime, timezone
import json
import os
import re
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from taxonomy_discovery import unresolved_adjudication as a
from taxonomy_discovery import unresolved_adjudication_providers as providers
from scripts import adjudicate_unresolved_requirements as cli
from tests.network_guard_support import block_external_network_allow_loopback


def case(rid='req_fixture', text='Network Access Control'):
    return {'job_id': 163, 'requirement_id': rid, 'requirement_text': text,
        'importance': 'required', 'nearby_context': [], 'resolver': {'status': 'unresolved'},
        'taxonomy_candidates': [{'capability_id': 'network.dns_dhcp'}],
        'registry_candidates': [{'technology_id': 'sql'}], 'versions': {'scoring_version': 'fixture'},
        'source_fingerprint': 'fixture'}


def response(c, route='UNKNOWN'):
    p = a.unknown(c); p.update(proposed_route=route, scope_type='ATOMIC', confidence=.9,
        source_spans=[c['requirement_text']])
    if route == 'CAPABILITY':
        p['capability_candidates'] = [{'capability_id': 'network.dns_dhcp', 'confidence': .9,
            'reason_codes': ['EXISTING_CAPABILITY_POSSIBLE']}]
    return p


class SchemaTests(unittest.TestCase):
    def validated(self, change=None, c=None, route='UNKNOWN'):
        c = c or case(); p = response(c, route)
        if change: change(p)
        return a.validate_response(json.dumps(p), c)

    def test_valid_strict_json(self): self.assertTrue(self.validated()['valid_schema'])
    def test_invalid_json_unknown(self):
        r = a.validate_response('```json {} ```', case())
        self.assertFalse(r['valid_json']); self.assertEqual(r['proposal']['proposed_route'], 'UNKNOWN')
    def test_extra_fields_rejected(self): self.assertFalse(self.validated(lambda p:p.update(approval=True))['valid_schema'])
    def test_wrong_requirement_id(self): self.assertFalse(self.validated(lambda p:p.update(requirement_id='invented'))['valid_schema'])
    def test_duplicate_json_keys(self): self.assertFalse(a.validate_response('{"x":1,"x":2}',case())['valid_schema'])
    def test_parseable_array_not_schema_valid(self):
        r=a.validate_response('[1]',case());self.assertTrue(r['valid_json']);self.assertFalse(r['valid_schema'])
    def test_capability_id_outside_candidates(self):
        self.assertFalse(self.validated(lambda p:p.update(capability_candidates=[{'capability_id':'invented','confidence':1,'reason_codes':[]}]))['valid_schema'])
    def test_technology_id_outside_candidates(self):
        self.assertFalse(self.validated(lambda p:p.update(technology_entities=[{'text':'Network','candidate_registry_ids':['invented'],'confidence':1}]))['valid_schema'])
    def test_fabricated_span(self): self.assertFalse(self.validated(lambda p:p.update(source_spans=['invented evidence']))['valid_schema'])
    def test_confidence_bounds_and_types(self):
        for v in (-1, 1.1, True, '0.8', float('nan')):
            with self.subTest(value=v): self.assertFalse(self.validated(lambda p:p.update(confidence=v))['valid_schema'])
    def test_invalid_scope_route_and_component(self):
        for field, value in [('scope_type','invented'),('proposed_route','approved'),('components',[{'text':'Network'}])]:
            with self.subTest(field=field): self.assertFalse(self.validated(lambda p:p.update({field:value}))['valid_schema'])
    def test_action_needs_grounded_span(self):
        self.assertFalse(self.validated(lambda p:p.update(source_spans=[]),route='TRUE_GAP_CANDIDATE')['valid_schema'])
    def test_true_gap_technology_and_structural_boundary(self):
        for field, value in [('scope_type','ALL_OF'),('reason_codes',['STRUCTURE_BLOCKED'])]:
            with self.subTest(field=field):self.assertFalse(self.validated(lambda p:p.update({field:value}),route='TRUE_GAP_CANDIDATE')['valid_schema'])
    def unsafe(self, text):
        c=case(text=text);c['resolver']['scope_category']='PURE_ATOMIC_TECHNOLOGY'
        self.assertEqual(self.validated(c=c,route='CAPABILITY')['proposal']['proposed_route'],'UNKNOWN')
    def test_sql_does_not_imply_querying(self):self.unsafe('SQL')
    def test_aws_does_not_imply_architecture(self):self.unsafe('AWS')
    def test_node_does_not_imply_api(self):self.unsafe('Node.js')
    def test_csharp_does_not_imply_backend(self):self.unsafe('C#')
    def test_javascript_does_not_imply_frontend(self):self.unsafe('JavaScript')
    def test_mongo_does_not_imply_database_design(self):self.unsafe('MongoDB')
    def test_nac_candidate_is_not_publication(self):
        c=case();r=a.run_cases([c],[],execute=True,transport=lambda *_:{'text':json.dumps(response(c,'TRUE_GAP_CANDIDATE'))})
        self.assertFalse(r['publication']);self.assertFalse(r['rows'][0]['handoff']['proven_gap'])
    def test_structural_and_non_addressable_routes(self):
        for route in ('STRUCTURAL','NOT_TAXONOMY_ADDRESSABLE'):
            with self.subTest(route=route):self.assertTrue(self.validated(route=route)['valid_schema'])


class NativeInputTests(unittest.TestCase):
    def test_native_resolution_precedes_model_and_resolved_rows_skip(self):
        occurrence={'job_id':1,'requirement':{'requirement_id':'req_a','text':'SQL','source_provenance':[{'native':True}]}}
        with patch.object(a,'resolve_requirement_with_production_knowledge',return_value={'status':'resolved'}) as native:
            self.assertIsNone(a.build_input(occurrence))
        native.assert_called_once_with(occurrence['requirement'])
    def test_real_source_reused_and_exact_ids(self):
        rows=a.load_occurrences();self.assertEqual(len(rows),276)
        self.assertTrue(a.NAC | {a.MONGO} <= {(r['job_id'],r['requirement']['requirement_id']) for r in rows})
    def test_input_contains_no_candidate_evidence(self):
        rows=a.load_occurrences();row=rows[0];row['requirement']['evidence']=[{'text':'SECRET RESUME'}]
        row['resume_profile']={'name':'SECRET PROFILE'}
        prompt=a.prompt_for(a.build_input(row))
        self.assertNotIn('SECRET',prompt);self.assertNotIn('resume_profile',prompt)
    def test_sensitive_jd_fails_closed(self):
        row=a.load_occurrences()[0];row['requirement']['text']='Contact someone@example.test'
        with self.assertRaisesRegex(ValueError,'Sensitive'):a.build_input(row)
    def test_frozen_manifest_labels_not_bucket_conversion(self):
        m=json.loads(cli.BENCHMARK.read_text());c,skipped=cli.prepare(m)
        self.assertEqual(len(c),40);self.assertFalse(skipped)
        self.assertEqual(sum(bool(e['acceptable_routes']) for e in m['expectations']),2)
        self.assertTrue(all(e['review_reason'] for e in m['expectations']))
        for pattern in (r'(?<!\w)sql(?!\w)', r'(?<!\w)aws(?!\w)', r'(?<!\w)node(?:\.js|\s+js|js)?(?!\w)',
                r'(?<!\w)c#(?!\w)', r'(?<!\w)javascript(?!\w)', r'(?<!\w)mongodb(?!\w)'):
            self.assertTrue(any(re.search(pattern,row['requirement_text'],re.I) for row in c),pattern)
    def test_frozen_input_change_rejected(self):
        m=json.loads(cli.BENCHMARK.read_text());m['expectations'][0]['input_fingerprint']='changed'
        m['fingerprint']=a.fingerprint({k:v for k,v in m.items() if k!='fingerprint'})
        with self.assertRaisesRegex(ValueError,'Frozen input'):cli.prepare(m)
    def test_dry_runner_zero_provider_calls_with_key_present(self):
        c=case();provider=Mock(side_effect=AssertionError('No provider'))
        with patch.dict(os.environ,{'OPENAI_API_KEY':'fake-private-secret'}):
            r=a.run_cases([c],[],transport=provider)
        provider.assert_not_called();self.assertEqual(r['executed_calls'],0)
        self.assertNotIn('fake-private-secret',json.dumps(r))
    def test_model_unavailable_no_fallback_and_partial_report(self):
        provider=Mock(side_effect=ConnectionError('secret details'))
        r=a.run_cases([case(),case('req_other')],[],execute=True,transport=provider)
        self.assertEqual(provider.call_count,1);self.assertEqual(r['gate']['verdict'],'BENCHMARK INCONCLUSIVE')
        self.assertNotIn('secret details',json.dumps(r))
    def test_untrusted_provider_metadata_cannot_leak_credential(self):
        c=case();r=a.run_cases([c],[],execute=True,transport=lambda *_:{'text':json.dumps(response(c)),
            'model_snapshot':'sk-private-model-name','usage':{'api_key':'SECRET','input_tokens':20}})
        self.assertNotIn('SECRET',json.dumps(r));self.assertIsNone(r['rows'][0]['model_snapshot'])
    def test_report_versions_fingerprints_and_no_writes(self):
        c=case();r=a.run_cases([c],[],execute=True,transport=lambda *_:{'text':json.dumps(response(c))})
        self.assertEqual(r['rows'][0]['input_fingerprint'],a.fingerprint(c))
        self.assertEqual(r['rows'][0]['schema_version'],a.SCHEMA_VERSION);self.assertEqual(r['production_writes'],0)
    def test_cli_default_no_transport_init_or_network(self):
        with tempfile.TemporaryDirectory() as directory, block_external_network_allow_loopback() as external, \
                patch('database.db_manager._connect',side_effect=AssertionError('No production DB')) as db, \
                patch.object(providers,'ollama_transport',side_effect=AssertionError('No Ollama')) as local, \
                patch.object(providers,'cloud_transport_factory',side_effect=AssertionError('No cloud')) as cloud:
            output=Path(directory)/'preview.json';cli.main(['--output',str(output),'--limit','2'])
            r=json.loads(output.read_text());self.assertEqual(r['executed_calls'],0)
            self.assertEqual(r['gate']['verdict'],'BENCHMARK INCONCLUSIVE')
            external.assert_not_called();local.assert_not_called();cloud.assert_not_called();db.assert_not_called()
    def test_no_auto_all_corpus_expansion(self):
        with self.assertRaises(SystemExit):cli.main(['--all-reviewed','--output','reports/blocked.json'])
    def test_cloud_preflight_with_key_zero_calls(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ,{'OPENAI_API_KEY':'sk-fake-secret'}), \
                patch.object(providers,'cloud_transport_factory',side_effect=AssertionError('No cloud init')) as cloud:
            config=Path(directory)/'prices.json';config.write_text(json.dumps(price()))
            output=Path(directory)/'preflight.json'
            cli.main(['--provider','openai','--model','gpt-5.6-luna','--pricing',str(config),'--output',str(output)])
            result=json.loads(output.read_text());self.assertEqual(result['executed_calls'],0)
            self.assertGreater(result['cloud_preflight']['worst_case_usd'],0);cloud.assert_not_called()
            self.assertNotIn('sk-fake-secret',output.read_text())
    def test_paid_execution_requires_prior_qwen_and_confirmation(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(providers,'cloud_transport_factory') as cloud:
            config=Path(directory)/'prices.json';config.write_text(json.dumps(price()))
            with self.assertRaises(SystemExit):
                cli.main(['--provider','openai','--model','gpt-5.6-luna','--execute','--authorize-paid',
                    '--pricing',str(config),'--output',str(Path(directory)/'blocked.json')])
            cloud.assert_not_called()
    def test_whole_paid_plan_over_budget_never_initializes_transport(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(providers,'cloud_transport_factory') as cloud:
            manifest=json.loads(cli.BENCHMARK.read_text());cases,_=cli.prepare(manifest);iterator=iter(cases)
            local=a.run_cases(cases,manifest['expectations'],execute=True,
                transport=lambda *_:{'text':json.dumps(a.unknown(next(iterator)))})
            local.update(expectations=manifest['expectations'],benchmark_fingerprint=manifest['fingerprint'])
            local_path=Path(directory)/'local.json';cli.write_report(local,local_path)
            config=price();config_path=Path(directory)/'prices.json';config_path.write_text(json.dumps(config))
            plan=providers.preflight([a.prompt_for(c) for c in cases],'gpt-5.6-luna',config)
            with self.assertRaises(SystemExit):
                cli.main(['--provider','openai','--model','gpt-5.6-luna','--pricing',str(config_path),
                    '--local-report',str(local_path),'--execute','--authorize-paid','--privacy-reviewed',
                    '--confirm-preflight',plan['preflight_id'],'--experiment-id','test','--ledger',str(Path(directory)/'ledger.json'),
                    '--max-cost-usd','0.01','--output',str(Path(directory)/'blocked.json')])
            cloud.assert_not_called();self.assertFalse((Path(directory)/'ledger.json').exists())
    def test_production_output_path_rejected(self):
        path=Path('taxonomy/capability_taxonomy_v1.json');before=path.read_bytes()
        with self.assertRaises(ValueError):cli.write_report({},path)
        self.assertEqual(path.read_bytes(),before)


class QualityGateTests(unittest.TestCase):
    def cohort(self, wrong=False, invalid=False):
        expected=[];rows=[]
        routes=('TECH_ID','RELATIONSHIP','STRUCTURAL','NOT_TAXONOMY_ADDRESSABLE')
        for i in range(40):
            c=case('req_'+str(i));route=routes[i%4]
            expected.append({'key':[163,c['requirement_id']], 'acceptable_routes':[route],
                'non_gap_control':True, 'identity_only_control':route=='TECH_ID'})
            proposal=response(c,'UNKNOWN' if wrong else route)
            rows.append({'input':c,'validation':a.validate_response('bad' if invalid else json.dumps(proposal),c)})
        return rows,expected
    def test_pass_recommends_stop_no_cloud(self):
        rows,e=self.cohort();g=a.evaluate(rows,e)
        self.assertEqual(g['verdict'],'LOCAL SUFFICIENT');self.assertEqual(g['optional_cloud'],'NOT NEEDED')
    def test_all_unknown_cannot_game_actionable_denominator(self):
        rows,e=self.cohort(wrong=True);g=a.evaluate(rows,e)
        self.assertEqual(g['verdict'],'FURTHER REVIEW REQUIRED')
        self.assertEqual(g['metrics']['actionable_agreement']['denominator'],40)
        self.assertEqual(g['metrics']['actionable_agreement']['numerator'],0)
    def test_unknown_alternatives_and_broad_sets_cannot_inflate_gate(self):
        rows,e=self.cohort(wrong=True)
        for x in e:x['acceptable_routes']+=['UNKNOWN']
        self.assertEqual(a.evaluate(rows,e)['metrics']['actionable_agreement']['numerator'],0)
        for x in e:x['acceptable_routes']=['TECH_ID','RELATIONSHIP','STRUCTURAL','NOT_TAXONOMY_ADDRESSABLE']
        self.assertFalse(a.evaluate(rows,e)['label_adequacy']['adequate'])
    def test_invalid_json_in_denominator(self):
        rows,e=self.cohort(invalid=True);g=a.evaluate(rows,e)
        self.assertEqual(g['metrics']['valid_schema']['denominator'],40)
        self.assertEqual(g['metrics']['valid_json']['numerator'],0)
    def test_false_positive_true_gap_fails_safety(self):
        rows,e=self.cohort();c=rows[0]['input'];rows[0]['validation']=a.validate_response(json.dumps(response(c,'TRUE_GAP_CANDIDATE')),c)
        g=a.evaluate(rows,e);self.assertEqual(g['verdict'],'FURTHER REVIEW REQUIRED');self.assertEqual(g['false_gap_ids'],[[163,'req_0']])
    def test_unsafe_mapping_claim_fails_even_if_schema_normalizes_unknown(self):
        rows,e=self.cohort();c=rows[0]['input'];c['resolver']['scope_category']='PURE_ATOMIC_TECHNOLOGY'
        rows[0]['validation']=a.validate_response(json.dumps(response(c,'CAPABILITY')),c)
        self.assertEqual(a.evaluate(rows,e)['unsafe_mapping_ids'],[[163,'req_0']])
    def test_missing_rows_and_inadequate_labels_inconclusive(self):
        rows,e=self.cohort();self.assertEqual(a.evaluate(rows[:5],e)['verdict'],'BENCHMARK INCONCLUSIVE')
        for x in e:x['acceptable_routes']=[]
        self.assertEqual(a.evaluate(rows,e)['verdict'],'BENCHMARK INCONCLUSIVE')
    def test_nac_unknown_is_inconclusive_mongodb_is_not_gap(self):
        rows,e=self.cohort();c=case('req_2f6aedb603aa')
        rows[0]={'input':c,'validation':a.validate_response(json.dumps(response(c)),c)}
        e[0]={'key':[163,c['requirement_id']],'acceptable_routes':['TRUE_GAP_CANDIDATE'],'critical':True}
        self.assertEqual(a.evaluate(rows,e)['verdict'],'BENCHMARK INCONCLUSIVE')
        mongo=case('req_2410dfcbbf45');mongo['job_id']=31
        self.assertEqual(a.evaluate([{'input':mongo,'validation':a.validate_response(json.dumps(response(mongo,'TRUE_GAP_CANDIDATE')),mongo)}],
            [{'key':[31,mongo['requirement_id']],'acceptable_routes':[],'non_gap_control':True}])['false_gap_ids'],[[31,mongo['requirement_id']]])
    def test_provider_independent_disagreement_table(self):
        c=case();local=a.run_cases([c],[],execute=True,transport=lambda *_:{'text':json.dumps(response(c,'STRUCTURAL'))})
        cloud=a.run_cases([c],[],provider='openai',model='fake',execute=True,transport=lambda *_:{'text':json.dumps(response(c))})
        self.assertEqual(len(cli.compare_reports(local,cloud)),1)
        self.assertEqual(local['rows'][0]['input_fingerprint'],cloud['rows'][0]['input_fingerprint'])


def price(model='gpt-5.6-luna'):
    rates=providers.MODELS[model]
    return {'model':model,'verified':True,'verified_at':datetime.now(timezone.utc).isoformat(),
        'source':'https://developers.openai.com/api/docs/models/'+model,'tier':'standard',
        'input_per_million':rates[0],'output_per_million':rates[1]}


class CloudBudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'ledger.json';self.plan=providers.preflight(['prompt'],'gpt-5.6-luna',price())
        self.ledger=providers.ExperimentLedger(self.path,'shared-experiment','same-cases')
    def transport(self, **changes):
        options={'plan':self.plan,'ledger':self.ledger,'authorized':True,'consent_id':self.plan['preflight_id'],
            'api_key':'fake-test-key','client':Mock(return_value={'id':'fake-request','text':'{}','usage':{'input_tokens':20,'output_tokens':30,
                'output_tokens_details':{'reasoning_tokens':10}}})}
        options.update(changes);return providers.cloud_transport_factory(**options),options['client']
    def test_missing_authorization_key_or_consent_blocks(self):
        for change in ({'authorized':False},{'api_key':None},{'consent_id':None}):
            with self.subTest(change=change),self.assertRaises(ValueError):self.transport(**change)
    def test_unverified_inconsistent_alias_or_stale_pricing_blocks(self):
        for config in (None,{**price(),'verified':False},{**price(),'output_per_million':'0'},
                {**price(),'verified_at':'2020-01-01T00:00:00+00:00'}):
            with self.subTest(config=config),self.assertRaises(ValueError):providers.preflight(['prompt'],'gpt-5.6-luna',config)
        with self.assertRaises(ValueError):providers.preflight(['prompt'],'gpt-5.6',price())
    def test_ceiling_above_fifty_cents_blocks(self):
        with self.assertRaises(ValueError):providers.ExperimentLedger(self.path,'id','cases',.51)
    def test_non_loopback_redirect_and_unbounded_prompt_blocked(self):
        self.assertIsNone(providers._NoRedirect().redirect_request(None,None,302,'redirect',{},'https://api.openai.com'))
        with self.assertRaises(ValueError):providers.preflight(['x'*20000],'gpt-5.6-luna',price())
    def test_real_client_invalid_key_and_wrong_confirmation_blocked(self):
        with self.assertRaises(ValueError):self.transport(client=None,api_key='invalid')
        with self.assertRaises(ValueError):self.transport(consent_id='not-confirmed')
    def test_unexpected_response_model_or_tier_halts_ledger(self):
        for i, changed in enumerate(({'model':'gpt-5.6-sol'}, {'service_tier':'priority'})):
            ledger=providers.ExperimentLedger(Path(self.temp.name)/f'tier{i}.json','shared','cases')
            result={'id':'fake','text':'{}','usage':{'input_tokens':10,'output_tokens':20}, **changed}
            t,client=self.transport(ledger=ledger,client=Mock(return_value=result))
            with self.assertRaises(ValueError):t('prompt','gpt-5.6-luna')
            self.assertEqual(json.loads(ledger.path.read_text())['requests'][0]['status'],'ambiguous')
    def test_over_budget_before_transport(self):
        reservation=deepcopy(self.plan['requests'][0]);reservation['reserved_nanousd']=500000001
        client=Mock()
        with self.assertRaises(ValueError):self.ledger.execute(reservation,'gpt-5.6-luna','consent',client,providers.pricing('gpt-5.6-luna',price()))
        client.assert_not_called()
    def test_resumption_and_second_model_share_reservations(self):
        t,_=self.transport();t('prompt','gpt-5.6-luna')
        second=providers.preflight(['prompt'],'gpt-5.4-mini',price('gpt-5.4-mini'))
        t,_=self.transport(plan=second,consent_id=second['preflight_id']);t('prompt','gpt-5.4-mini')
        data=json.loads(self.path.read_text());self.assertEqual(len(data['requests']),2)
        self.assertEqual(sum(r['charged_nanousd'] for r in data['requests']),
            self.plan['requests'][0]['reserved_nanousd']+second['requests'][0]['reserved_nanousd'])
    def test_ledger_identity_and_tampering_cannot_reset(self):
        t,_=self.transport();t('prompt','gpt-5.6-luna')
        other=providers.ExperimentLedger(self.path,'other','same-cases')
        with self.assertRaises(ValueError),other.locked():pass
        data=json.loads(self.path.read_text());data['requests']=[];self.path.write_text(json.dumps(data))
        with self.assertRaises(ValueError),self.ledger.locked():pass
    def test_timeouts_missing_usage_and_reasoning_inconsistency_retain_budget(self):
        bad=[TimeoutError(),{'id':'fake','text':'{}'}, {'id':'fake','text':'{}','usage':{'input_tokens':20,'output_tokens':5,'output_tokens_details':{'reasoning_tokens':10}}}]
        for i,result in enumerate(bad):
            with self.subTest(result=result):
                ledger=providers.ExperimentLedger(Path(self.temp.name)/f'bad{i}.json','shared','cases')
                client=Mock(side_effect=result) if isinstance(result,Exception) else Mock(return_value=result)
                t,_=self.transport(ledger=ledger,client=client)
                with self.assertRaises(ValueError):t('prompt','gpt-5.6-luna')
                data=json.loads(ledger.path.read_text());self.assertEqual(data['requests'][0]['status'],'ambiguous')
                t,_=self.transport(ledger=ledger,client=client)
                with self.assertRaises(ValueError):t('prompt','gpt-5.6-luna')
                self.assertEqual(client.call_count,1)
    def test_output_bound_and_no_credentials_in_ledger(self):
        t,client=self.transport();t('prompt','gpt-5.6-luna')
        payload=client.call_args.args[0];self.assertEqual(payload['max_output_tokens'],1200)
        self.assertFalse(payload['tools']);self.assertFalse(payload['background'])
        self.assertNotIn('fake-test-key',self.path.read_text())
    def test_changed_prompt_and_hidden_retry_block(self):
        t,client=self.transport()
        with self.assertRaises(ValueError):t('changed','gpt-5.6-luna')
        client.assert_not_called();t('prompt','gpt-5.6-luna')
        with self.assertRaises(ValueError):t('prompt','gpt-5.6-luna')
        self.assertEqual(client.call_count,1)

from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from taxonomy_discovery import unresolved_multidimensional_triage as t
from taxonomy_discovery import unresolved_adjudication as a
from taxonomy_discovery import unresolved_gold_review as gold
from scripts import prepare_unresolved_multidimensional_triage as cli


def fixture(text, rid='req_test', job=1, parent=None, fraction=1.0):
    req={'requirement_id':rid,'text':text,'importance':'required','atomic_group_id':'group_test',
         'group_weight_fraction':fraction,'is_atomic':parent is not None,'parent_text':parent or text}
    p={'parent_occurrence_id':'parent_test','raw_parent_text':parent or text,'parent_text':parent or text,
       'source':'raw_jd.requirements','source_group_fraction':fraction,'contributes_scoring_allocation':True,
       'grounding':{'span_id':'span_test'},'raw_parent_verified_in_jd':True}
    req['source_provenance']=[{k:v for k,v in p.items() if k!='raw_parent_verified_in_jd'}]
    occ={'job_id':job,'requirement':req,'source_fingerprint':'a'*64,'source_manifest':{}}
    recovered={'status':'RECOVERED_AND_VERIFIED','native_requirement':deepcopy(req),'parent_provenance':[p],
               'raw_jd_sha256':'b'*64,'source_references':['test raw source']}
    return occ,recovered


class MultidimensionalTests(unittest.TestCase):
    def test_responsive_ui_existing_predicate_precedes_technology_relationship(self):
        o,s=fixture('Proficiency in responsive user interfaces using React.js')
        r=t.build(o,s)
        self.assertEqual(r['primary_route']['route'],'CAPABILITY')
        self.assertEqual([x['capability_id'] for x in r['capability_predicate_observations']],['frontend.ui_development'])
        self.assertEqual(r['native_resolution']['status'],'unresolved')

    def test_api_plural_existing_predicate_is_not_framework_mapping(self):
        o,s=fixture('Proven experience building efficient, secure RESTful APIs with frameworks such as Express.js, Fastify, FastAPI, Spring Boot, or equivalent enterprise-grade tools')
        r=t.build(o,s)
        self.assertEqual(r['primary_route']['route'],'CAPABILITY')
        self.assertEqual(r['capability_predicate_observations'][0]['capability_id'],'backend.api_development')
        self.assertIn('distributed systems architecture',r['capability_predicate_observations'][0]['negative_boundaries'])
        self.assertEqual(r['native_resolution']['status'],'unresolved')

    def test_bare_or_does_not_establish_structural_primary_blocker(self):
        o,s=fixture('Basic programming or application development knowledge (e.g. Python or other programming languages) would be useful')
        r=t.build(o,s)
        self.assertEqual(r['structure']['type'],'ANY_OF')
        self.assertEqual(r['primary_route']['route'],'undetermined')

    def test_other_parent_sentence_technologies_do_not_create_relationship(self):
        for text in ('Production-Grade Development: Design and build modular, high-performance software components meant for real-world production systems',
                     'Engineering Excellence: A proven ability to build high-quality, secure, and maintainable software'):
            o,s=fixture(text)
            s['parent_provenance'][0]['raw_parent_text']=text+'. You will use C++ for real-time control and Python for automation.'
            r=t.build(o,s)
            self.assertTrue(r['technology_candidates'])
            self.assertTrue(all(t['source']!='CURRENT_REQUIREMENT' for t in r['technology_candidates']))
            self.assertEqual(r['primary_route']['route'],'undetermined')

    def test_ros_activity_without_registered_identity_is_not_mapped(self):
        o,s=fixture('maintain ROS-based robotics solutions to enhance visitor experiences and operational efficiency as well as educational programs')
        r=t.build(o,s)
        self.assertEqual(r['technology_candidates'],[])
        self.assertEqual(r['primary_route']['route'],'undetermined')
        self.assertEqual(r['activity']['status'],'OBSERVED')

    def test_azure_familiarity_is_not_native_resolution_or_architecture(self):
        o,s=fixture('Exposure to Microsoft Azure cloud services is preferred')
        r=t.build(o,s)
        self.assertEqual(r['primary_route']['route'],'TECH_ID')
        self.assertEqual(r['native_resolution']['status'],'unresolved')
        self.assertEqual(r['technology_candidates'][0]['registry_candidate_status'],'candidate')

    def test_pipeline_predicate_and_negated_api_fail_closed(self):
        o,s=fixture('maintain scalable data pipelines that ingest, transform, and serve structured and unstructured data from diverse transport data sources, including real-time streams and batch feeds')
        r=t.build(o,s)
        self.assertEqual(r['primary_route']['route'],'CAPABILITY')
        self.assertEqual(r['capability_predicate_observations'][0]['capability_id'],'data.processing')
        o,s=fixture('No experience building RESTful APIs is required')
        r=t.build(o,s)
        self.assertEqual(r['capability_predicate_observations'],[])
        self.assertNotEqual(r['primary_route']['route'],'CAPABILITY')

    def test_database_examples_and_csharp_list_do_not_imply_design_or_cpp(self):
        for text in ('(b) Relational and non-relational databases, such as MS SQL, PostgreSQL, MongoDB etc',
                     'Basic programming experience with knowledge of C#, Java, Javascript, HTML5 and Python is preferred'):
            o,s=fixture(text);r=t.build(o,s)
            self.assertEqual(r['primary_route']['route'],'undetermined')
            self.assertFalse(any(x['capability_id']=='language.modern_cpp' for x in r['capability_predicate_observations']))

    def test_java_relationship_proposal_does_not_resolve_capability(self):
        o,s=fixture('Proficiency in in Java for web-based applications development')
        r=t.build(o,s)
        self.assertEqual(r['primary_route']['route'],'RELATIONSHIP')
        self.assertEqual(r['primary_route']['status'],'PROPOSED')
        self.assertEqual(r['technology_candidates'][0]['technology_id'],'java')
        self.assertEqual(r['technology_candidates'][0]['registry_candidate_status'],'candidate')
        self.assertEqual(r['activity']['exact_text_span'],'web-based applications development')
        self.assertEqual(r['relationship_diagnostics'][0]['diagnostic'][2],'NO_RELATIONSHIP_JUSTIFIED')
        self.assertEqual(r['native_resolution']['status'],'unresolved')

    def test_python_node_open_examples_not_two_mandatory_obligations(self):
        o,s=fixture('Proficiency in one or more programming/scripting languages (python, nodejs, etc.)')
        r=t.build(o,s)
        self.assertEqual(r['primary_route']['route'],'STRUCTURAL')
        self.assertEqual({x['technology_id'] for x in r['technology_candidates']},{'python','node.js'})
        self.assertEqual(r['structure']['type'],'ONE_OR_MORE_OPEN_EXAMPLES')
        self.assertFalse(r['structure']['scoring_children_created'])
        self.assertEqual(r['structure']['group_weight_fraction'],1.0)

    def test_mongo_alternatives_and_activity_do_not_imply_schema(self):
        o,s=fixture('Hands-on experience managing data persistence and search layers using MongoDB, Redis, Elasticsearch, or comparable NoSQL and search engines')
        r=t.build(o,s,mentioned_unverified=['Redis'])
        self.assertEqual(r['primary_route']['route'],'RELATIONSHIP')
        self.assertEqual(r['structure']['type'],'EXAMPLES')
        self.assertEqual({x['technology_id'] for x in r['technology_candidates']},{'mongodb','elasticsearch',None})
        self.assertIsNone(next(x for x in r['technology_candidates'] if x['matched_text_span']=='Redis')['technology_id'])
        self.assertEqual(r['native_resolution']['status'],'unresolved')

    def test_shared_react_js_children_preserve_weight_and_parent_activity(self):
        parent='Proficiency in building dynamic, responsive user interfaces using React.js and the modern JavaScript/TypeScript ecosystem'
        outputs=[]
        for text,rid in [('Proficiency in responsive user interfaces using React.js','req_ui'),
                         ('Proficiency in the modern JavaScript/TypeScript ecosystem','req_8d47527c8f34')]:
            o,s=fixture(text,rid,31,parent,.5);before=deepcopy(o);r=t.build(o,s);outputs.append(r)
            self.assertEqual(o,before);self.assertEqual(r['structure']['source_group_fraction'],.5)
            self.assertEqual(r['structure']['atomic_group_id'],'group_test')
        self.assertEqual(sum(r['structure']['group_weight_fraction'] for r in outputs),1.0)
        js=outputs[1]
        self.assertEqual(js['structure']['type'],'SHARED_PARENT_WITH_CONTEXT_LOSS')
        self.assertEqual(js['human_review']['status'],'DEFERRED_FOR_CURRENT_BENCHMARK')
        self.assertEqual(js['remediation_candidate']['priority'],'HIGH_PRIORITY_INVESTIGATION')
        self.assertNotEqual(js['activity']['source'],'CURRENT_REQUIREMENT')
        self.assertEqual(js['human_review']['reviewer'],'')

    def test_missing_parent_does_not_import_parent_activity(self):
        o,s=fixture('Proficiency in the modern JavaScript/TypeScript ecosystem',parent='building responsive user interfaces')
        s['status']='PARTIALLY_RECOVERED';r=t.build(o,s)
        self.assertEqual(r['primary_route']['route'],'undetermined')
        self.assertEqual(r['activity']['status'],'NOT_ESTABLISHED')
        self.assertTrue(r['activity']['missing_context'])

    def test_unsafe_technology_only_inferences_never_create_relationship(self):
        for text in ('SQL','AWS','Node.js','C#','JavaScript','MongoDB'):
            # Missing provenance is deliberately unresolved; known identity is
            # independently observable but cannot create an activity or mapping.
            o,s=fixture(text);o['requirement'].pop('source_provenance')
            r=t.build(o)
            self.assertEqual(r['primary_route']['route'],'undetermined')
            self.assertEqual(r['activity']['status'],'NOT_ESTABLISHED')
            self.assertTrue(r['technology_candidates'])

    def test_strict_validator_rejects_edits_excluded_inputs_and_false_approval(self):
        o,s=fixture('Knowledge of Java web-based applications development');r=t.build(o,s)
        for mutate in (lambda x:x.update(resume_profile={'secret':'excluded'}),
                       lambda x:x['technology_candidates'][0].update(technology_id='invented'),
                       lambda x:x['activity'].update(exact_text_span='imagined'),
                       lambda x:x['provenance'].update(input_fingerprint='stale'),
                       lambda x:x['structure'].update(group_weight_fraction=.9),
                       lambda x:x['human_review'].update(reviewer='fake'),
                       lambda x:x['primary_route'].update(route=['CAPABILITY','RELATIONSHIP'])):
            changed=deepcopy(r);mutate(changed)
            with self.assertRaises(ValueError):t.validate(changed,o,s)

    def test_existing_candidate_ids_only_and_deterministic(self):
        o,s=fixture('Knowledge of Java web-based applications development')
        r=t.build(o,s);self.assertEqual(r,t.build(o,s));t.validate(r,o,s)
        self.assertTrue(all(c['basis']=='TOKEN_OVERLAP_ONLY_NOT_EQUIVALENCE' for c in r['capability_candidates']))
        with self.assertRaises(ValueError):t.validate_batch([r,r])

    def test_inherited_nac_only_and_no_network_runner(self):
        o,s=fixture('Network Access Control','req_6677d37f660c',163)
        with patch.object(a,'run_cases',side_effect=AssertionError('No execution')):
            r=t.build(o,s,['TRUE_GAP_CANDIDATE'])
        self.assertEqual(r['primary_route']['status'],'INHERITED_CONTROL')
        o['job_id']=999
        with self.assertRaises(ValueError):t.build(o,s,['TRUE_GAP_CANDIDATE'])

    def test_frozen_manifest_and_v3_labels_are_not_imported(self):
        m=gold.original();self.assertEqual(sum(bool(e['acceptable_routes']) for e in m['expectations']),2)
        self.assertEqual(m['expectations'][31]['acceptable_routes'],[])
        with patch('pathlib.Path.read_text',return_value='{}'),patch('pathlib.Path.read_bytes',return_value=b'{}'):
            with self.assertRaises(ValueError):cli.verify_handover({'based_on':{'report_sha256':'bad'}},gold.ROOT/'reports/unresolved_gold_decision_review_v3.json')

    def test_oversize_parent_and_invalid_parent_fraction_fail_closed(self):
        o,s=fixture('Knowledge of Java web-based applications development')
        s['parent_provenance'][0]['raw_parent_text']='x'*1801
        with self.assertRaises(ValueError):t.build(o,s)
        o,s=fixture('Knowledge of Java web-based applications development')
        s['parent_provenance'][0]['source_group_fraction']=float('nan')
        with self.assertRaises(ValueError):t.build(o,s)

    def test_invalid_shape_and_cli_execution_flags_rejected_before_reads(self):
        o,s=fixture('Knowledge of Java web-based applications development');r=t.build(o,s)
        r['technology_candidates']=['malformed']
        with self.assertRaises(ValueError):t.validate(r,o,s)
        with patch.object(cli,'list_latest_job_match_corpus_snapshots') as read:
            for args in (['--limit','41'],['--execute']):
                with self.assertRaises(SystemExit):cli.main(['--handover','missing.json','--output','reports/new.json',*args])
            read.assert_not_called()

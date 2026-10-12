"""Governed identity batch and contextual review; no live provider transports."""
from copy import deepcopy
from contextlib import ExitStack
from pathlib import Path
import json
import unittest
from unittest.mock import patch
from tests.network_guard_support import block_external_network_allow_loopback
import numpy  # Binary dependencies must predate PublicationFixture rollback.
import pandas

from taxonomy_discovery import technology_identity_remediation as identities
from taxonomy_discovery import contextual_relationship_validation as relationships
from taxonomy_discovery import corpus_gap_resolution as gaps, maintenance_service as maintenance
from taxonomy_discovery.technology_registry import TechnologyRegistry, get_default_registry, resolve_requirement_text, temporary_registry_scope
from tailoring.requirement_scope import technology_identity_scope
from tests.test_technology_knowledge_preview import row
from tests.tqd3_publication_fixture_support import PublicationFixture
from tests.test_taxonomy_maintenance_service import fixture_corpus

CONCEPTS = ('Python', 'SQL', 'Azure', 'JavaScript', 'AWS', 'TypeScript', 'Elasticsearch', 'Java', 'S3', 'FastAPI', 'GCP')


class TechnologyMaintenanceBatchTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.fixture = self.stack.enter_context(PublicationFixture())
        native = get_default_registry()
        self.baseline = TechnologyRegistry(native.version, tuple(e for e in native.entries
            if not any(set(map(str.lower, e['aliases'])) & {c.lower()} for c in CONCEPTS)))
        self.stack.enter_context(temporary_registry_scope(self.baseline))
        proposals = [gaps._bootstrap_proposal({'seed_id':c,'canonical_name':c}, resolution_type='add_technology_identity',
            proposed_change={'technology_id': gaps._technology_id_for(gaps._local_identity(c)['canonical_name']),
                             'identity':gaps._local_identity(c)}, matched=[]) for c in CONCEPTS]
        _, self.shadow = gaps._temporary_knowledge(proposals)

    def check_identity(self, name):
        decision = technology_identity_scope(row(name), registry=self.shadow)
        self.assertTrue(decision['identity_resolved'])
        self.assertIsNone(decision['capability_id'])
        self.assertIsNone(resolve_requirement_text(name, registry=self.shadow)['capability_id'])

    def test_python_exact(self): self.check_identity('Python')
    def test_sql_exact(self): self.check_identity('SQL')
    def test_azure_exact(self): self.check_identity('Azure')
    def test_javascript_exact(self): self.check_identity('JavaScript')
    def test_aws_exact(self): self.check_identity('AWS')
    def test_typescript_exact(self): self.check_identity('TypeScript')
    def test_elasticsearch_exact(self): self.check_identity('Elasticsearch')
    def test_java_exact(self): self.check_identity('Java')
    def test_s3_exact(self): self.check_identity('S3')
    def test_fastapi_exact(self): self.check_identity('FastAPI')
    def test_gcp_exact(self): self.check_identity('GCP')

    def test_java_javascript_owners_distinct(self):
        self.assertNotEqual(resolve_requirement_text('Java', registry=self.shadow)['technology_id'],
                            resolve_requirement_text('JavaScript', registry=self.shadow)['technology_id'])
        self.assertIsNone(resolve_requirement_text('JavaScriptish', registry=self.shadow)['technology_id'])

    def test_sql_server_not_sql_identity(self):
        self.assertNotEqual(resolve_requirement_text('SQL Server', registry=self.shadow)['technology_id'], 'sql')
        self.assertFalse(technology_identity_scope(row('SQL for database design'), registry=self.shadow)['identity_resolved'])

    def test_short_digit_alias_uses_bounded_mentions_not_arbitrary_substrings(self):
        snapshot = maintenance.run_corpus_audit(corpus=fixture_corpus('Hands-on experience with Amazon Web Services (EC2, S3, etc.)'),explicit_execution=True)
        batch = identities.prepare_identity_batch(snapshot,['S3'],explicit_execution=True)
        self.assertEqual(batch['candidates'][0]['temporary_decision'],'INDIVIDUALLY_VALIDATED')
        self.assertEqual(batch['candidates'][0]['requirements_affected'],1)
        self.assertFalse(gaps._technology_concept_present('arbitrary prefixs3ish prose',('S3',)))

    def test_bounded_s3_fastapi_not_substrings(self):
        for text in ('s3ish', 'prefixs3', 'S3 buckets for cloud architecture', 'FastAPIish', 'FastAPI for building APIs'):
            self.assertFalse(technology_identity_scope(row(text), registry=self.shadow)['identity_resolved'])

    def test_activity_never_implies_capability(self):
        for text in ('Python for building internal tools','Java for web application development',
                     'AWS for architecting cloud solutions','MongoDB for designing persistence',
                     'Node.js for building APIs','C# for backend development'):
            d = technology_identity_scope(row(text), registry=self.shadow)
            self.assertFalse(d['identity_resolved']); self.assertIsNone(d['capability_id'])

    def test_and_requires_both_without_duplicate_child_credit(self):
        r = row('Proficiency in Python and SQL is expected')
        d = technology_identity_scope(r, registry=self.shadow)
        self.assertTrue(d['identity_resolved'])
        self.assertEqual(d['structure']['mode'], 'all')
        self.assertTrue(d['structure']['parent_weight_preserved'])
        self.assertFalse(d['structure']['scoring_children_created'])
        missing = TechnologyRegistry(self.shadow.version, tuple(e for e in self.shadow.entries if e['technology_id'] != 'sql'))
        self.assertFalse(technology_identity_scope(r, registry=missing)['identity_resolved'])

    def test_net_and_patterns_not_published(self):
        for text in ('NET','NET MVC','Experience with .NET and teamwork','Microservices','distributed systems','cloud security'):
            self.assertFalse(technology_identity_scope(row(text), registry=self.shadow)['identity_resolved'])

    def test_relationship_requires_identity_first(self):
        with self.assertRaisesRegex(ValueError, 'identity first'):
            relationships.review_technology_contexts({'corpus':{'jobs':[]},'requirements':[]}, ['python'])

    def test_owned_short_alias_contexts_are_visible_without_mapping(self):
        snapshot = maintenance.run_corpus_audit(corpus=fixture_corpus('C# for backend development','S3 for cloud architecture'),explicit_execution=True)
        with temporary_registry_scope(self.shadow):
            reviews = relationships.review_technology_contexts(snapshot['audit'],['csharp','amazon.s3'])
        self.assertEqual({r['technology_id'] for r in reviews},{'csharp','amazon.s3'})
        self.assertTrue(all(r['profile'] is None for r in reviews))
        self.assertTrue(all(r['decision']!='EXISTING_CAPABILITY_RELATIONSHIP_SAFE' for r in reviews))

    def test_mongodb_node_csharp_not_universal_mappings(self):
        for tid, text in (('mongodb','Design robust data solutions using MongoDB and Elasticsearch'),
                          ('node.js','Experience with Node.js'), ('csharp','C# for backend development')):
            self.assertNotEqual(relationships.context(row(text),tid)[2], 'EXISTING_CAPABILITY_RELATIONSHIP_SAFE')
        self.assertFalse(relationships.eligible('Build APIs using Node.js or Python','node_api_implementation'))

    def test_batch_explicit_and_combined_native_replay_deterministic(self):
        snapshot = maintenance.run_corpus_audit(corpus=fixture_corpus('Proficiency in Python'),explicit_execution=True)
        with self.assertRaisesRegex(ValueError,'Explicit'):
            identities.prepare_identity_batch(snapshot, ['Python'])
        batch = identities.prepare_identity_batch(snapshot, ['Python'], explicit_execution=True)
        self.assertEqual(batch['candidates'][0]['temporary_decision'],'INDIVIDUALLY_VALIDATED')
        with self.assertRaisesRegex(ValueError,'Explicit'):
            identities.validate_identity_batch(snapshot,batch)
        a, audit = identities.validate_identity_batch(snapshot,batch,explicit_execution=True)
        b, _ = identities.validate_identity_batch(snapshot,batch,explicit_execution=True)
        self.assertEqual(a,b)
        self.assertEqual(a['validation_status'],'VALIDATED_SAFE')
        self.assertEqual(a['new_capability_resolutions'],[])
        self.assertEqual(a['evidence_deltas'],[])
        self.assertEqual(a['ranking_deltas'],[])
        self.assertEqual(a['frozen_or_duplicate_violations'],[])
        self.assertFalse(a['publication'])
        self.assertEqual(audit['summary']['capability_resolved_requirements'],a['baseline']['capability_resolved_requirements'])
        with self.assertRaisesRegex(ValueError,'Explicit'):
            identities.publish_identity_batch(snapshot,batch,a)
        with self.assertRaisesRegex(ValueError,'authorization'):
            identities.publish_identity_batch(snapshot,batch,a,explicit_publish=True,authorized_ids=[])

    def test_pure_identity_is_not_relationship_review(self):
        snapshot = maintenance.run_corpus_audit(corpus=fixture_corpus('Proficiency in Python'),explicit_execution=True)
        with temporary_registry_scope(self.shadow):
            reviews = relationships.review_technology_contexts(snapshot['audit'],['python'])
        self.assertTrue(all(r['text'] != 'Proficiency in Python' for r in reviews))

    def test_explicit_publication_uses_native_atomic_registry_only(self):
        from taxonomy_discovery.technology_registry import load_registry
        snapshot = maintenance.run_corpus_audit(corpus=fixture_corpus('Proficiency in Python'),explicit_execution=True)
        batch = identities.prepare_identity_batch(snapshot,['Python'],explicit_execution=True)
        result, _ = identities.validate_identity_batch(snapshot,batch,explicit_execution=True)
        receipt = identities.publish_identity_batch(snapshot,batch,result,explicit_publish=True,authorized_ids=['python'])
        self.assertTrue(receipt['publication'])
        self.assertEqual(receipt['capability_mappings_added'],0)
        entry = load_registry(self.fixture.registry_path).by_id()['python']
        self.assertEqual(entry['aliases'],['Python'])
        self.assertEqual(entry['capability_relationships'],[])
        self.assertEqual(self.fixture.real_registry.read_bytes(),self.fixture.real_registry_bytes)

    def test_batch_ui_rerender_never_replays_or_publishes(self):
        from streamlit.testing.v1 import AppTest
        snapshot = maintenance.run_corpus_audit(corpus=fixture_corpus('Proficiency in Python'),explicit_execution=True)
        harness = 'import streamlit as st\nfrom taxonomy_discovery.maintenance_ui import _render_technology_batch\n_render_technology_batch(st, st.session_state["snapshot"], False)'
        with patch.object(identities,'validate_identity_batch',side_effect=AssertionError('Explicit replay only')) as replay, \
             patch.object(identities,'publish_identity_batch',side_effect=AssertionError('No automatic publication')) as publish, \
             patch.object(relationships,'validate_technology_contexts',side_effect=AssertionError('Explicit relationship replay only')):
            app = AppTest.from_string(harness,default_timeout=30)
            app.session_state['snapshot'] = snapshot
            app.run(); app.run()
            app.session_state['tm_relationship_batch_validation'] = {'audit':snapshot['audit_fingerprint'],
                'result':{'implementation_fingerprint':'obsolete_review_policy','safe_profiles':['unsafe_old_hypothesis']}}
            app.run()
            self.assertEqual(len(app.get('download_button')),0)
            self.assertFalse(app.exception)
            replay.assert_not_called(); publish.assert_not_called()
            self.assertTrue(any(e.label=='Technology Maintenance Batch' for e in app.expander))

    def test_nac_never_researched(self):
        snapshot = maintenance.run_corpus_audit(corpus=fixture_corpus(),explicit_execution=True)
        with block_external_network_allow_loopback():
            batch = identities.prepare_identity_batch(snapshot,['Network Access Control','.NET'],explicit_execution=True)
        self.assertEqual(batch['proposals'],[])

    def test_protected_corpus_rows_still_native(self):
        from tailoring.production_requirement_resolver import resolve_requirement_with_production_knowledge
        rows = json.loads((Path(__file__).parent/'fixtures/technology_identity_knowledge_rows.json').read_text())
        with temporary_registry_scope(self.shadow):
            results={(r['job_id'],r['requirement']['requirement_id']): resolve_requirement_with_production_knowledge(r['requirement']) for r in rows}
        self.assertEqual(results[15,'req_d32de03a9826']['decision']['capability_id'],'collaboration.cross_functional')
        self.assertEqual(results[479,'req_379c7eb5d785']['decision']['capability_id'],'collaboration.cross_functional')
        self.assertEqual(results[493,'req_4731e7fdb9f1']['status'],'unresolved')


if __name__ == '__main__': unittest.main()

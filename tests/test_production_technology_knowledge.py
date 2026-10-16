"""Permanent identity-only production regressions; no provider or evidence calls."""
from copy import deepcopy
import unittest
import json
from pathlib import Path
from tailoring.production_requirement_resolver import resolve_requirement_with_production_knowledge as resolve
from taxonomy_discovery.technology_registry import get_default_registry, temporary_registry_scope
from taxonomy_discovery.regression_corpus import requirement_records
from tests import test_technology_knowledge_preview as fixtures
from analysis_stability.stable_evidence_scoring import SCORING_VERSION


row = fixtures.row


class ProductionTechnologyKnowledgeTests(fixtures.KnowledgePreviewTests):
    def test_exact_real_corpus_rows_and_protected_boundaries(self):
        rows = json.loads((Path(__file__).resolve().parent / 'fixtures/technology_identity_knowledge_rows.json').read_text())
        results = {(r['job_id'], r['requirement']['requirement_id']): resolve(r['requirement']) for r in rows}
        identities = {k for k, r in results.items() if r['knowledge_status'] == 'TECHNOLOGY_IDENTITY_RESOLVED'}
        self.assertEqual(identities, {(146,'req_951a4d36e0a9'), (632,'req_ead8b32809ed'),
                                      (632,'req_d63f4a0cdaab'), (632,'req_1cc9a79bdaf0')})
        self.assertEqual(results[15,'req_d32de03a9826']['decision']['capability_id'], 'collaboration.cross_functional')
        self.assertEqual(results[479,'req_379c7eb5d785']['decision']['capability_id'], 'collaboration.cross_functional')
        self.assertEqual(results[493,'req_4731e7fdb9f1']['status'], 'unresolved')
        self.assertEqual(results[556,'req_cb0a1b003784']['status'], 'unresolved')
    # Inherit permanent complete-scope safety fixtures for the shared contract.
    def test_production_atomic_identity_has_no_capability_or_score_label(self):
        for text in ('C#', 'Experience with Node.js', 'Experience with Keycloak', 'Experience with MongoDB'):
            r = row(text, evidence=[], match_label='none', match_value=0)
            before = deepcopy(r)
            result = resolve(r)
            self.assertEqual(result['status'], 'resolved')
            self.assertEqual(result['knowledge_status'], 'TECHNOLOGY_IDENTITY_RESOLVED')
            self.assertEqual(result['resolution_source'], 'technology_identity')
            self.assertEqual(result['knowledge_outcome'], 'RESOLVED_BY_TECHNOLOGY_IDENTITY')
            self.assertIsNone(result['decision']['capability_id'])
            self.assertIsNone(result['decision']['label'])
            self.assertTrue(result['technology_id'])
            self.assertEqual(r, before)

    def test_capability_primary_precedence(self):
        result = resolve(row('React'))
        self.assertEqual(result['knowledge_status'], 'CAPABILITY_RESOLVED')
        self.assertEqual(result['decision']['capability_id'], 'frontend.ui_development')
        self.assertNotEqual(result['resolution_source'], 'technology_identity')

    def test_negative_full_requirement_completion(self):
        for text in ('Build APIs using Node.js', 'Design databases using MongoDB', 'Deploy AI models using AWS',
                     'Experience with distributed systems using Java', 'Secure applications written in C#',
                     'Python for building internal tools', 'Java for web application development',
                     'Generic technology examples such as MongoDB', 'Experience with NET', 'Experience with Microservices'):
            self.assertNotEqual(resolve(row(text))['knowledge_status'], 'TECHNOLOGY_IDENTITY_RESOLVED', text)
        self.assertNotEqual(resolve({'text': 'MongoDB'})['knowledge_status'], 'TECHNOLOGY_IDENTITY_RESOLVED')

    def test_production_missing_identities_and_and_semantics(self):
        native = get_default_registry()
        from taxonomy_discovery.technology_registry import TechnologyRegistry
        missing_sql = TechnologyRegistry(native.version, tuple(e for e in native.entries if e['technology_id'] != 'sql'))
        with temporary_registry_scope(missing_sql):
            self.assertEqual(resolve(row('Proficiency in Python and SQL is expected'))['status'], 'unresolved')
        with temporary_registry_scope(self.registry):
            for text in ('Proficiency in Python and SQL is expected', 'Proficiency in Python or Java'):
                d = resolve(row(text))
                self.assertEqual(d['knowledge_status'], 'TECHNOLOGY_IDENTITY_RESOLVED')
                self.assertIsNone(d['decision']['capability_id'])
        self.assertEqual(get_default_registry(), native)

    def test_structured_optional_snapshot_records_knowledge_without_new_credit(self):
        from tailoring.phase6d_stable_scoring_adapter import cap_requirement_with_taxonomy
        r = row('Experience in languages such as Python or Java', requirement_id='r',
                structured_match_required_terms=['Python','Java'], structured_match_group_mode='any',
                structured_match_kind='programming_language_group', structured_match_status='confirmed_existing_direct',
                match_label='direct', match_value=1, evidence=[{'evidence_id':'frozen','text':'Python'}])
        with temporary_registry_scope(self.registry):
            after = cap_requirement_with_taxonomy(r, retrieval_mode_override='off')
        self.assertEqual(after['knowledge_status'], 'TECHNOLOGY_IDENTITY_RESOLVED')
        for field in ('match_label','match_value','evidence'):
            self.assertEqual(after[field], r[field])
        self.assertIsNone(after.get('capability_id'))
        exported = requirement_records({'canonical_requirements':[after]},job_id=1,snapshot_id=1)[0]
        self.assertEqual(exported['resolution_source'], 'technology_identity')
        self.assertEqual(exported['resolution_status'], 'resolved')

    def test_snapshot_pinned_knowledge_is_not_reinterpreted(self):
        raw = row('MongoDB', requirement_id='r', match_label='none', evidence=[])
        old = requirement_records({'canonical_requirements': [raw]}, job_id=1, snapshot_id=2)[0]
        self.assertEqual(old['resolution_status'], 'unresolved')
        raw['knowledge_resolution'] = {k: v for k, v in resolve(raw).items() if k not in {'decision', 'registry_resolution', 'taxonomy_diagnostics'}}
        new = requirement_records({'canonical_requirements': [raw]}, job_id=1, snapshot_id=2)[0]
        self.assertEqual(new['resolution_status'], 'resolved')
        self.assertEqual(new['knowledge_status'], 'TECHNOLOGY_IDENTITY_RESOLVED')
        self.assertIsNone(new['capability_id'])
        self.assertEqual(new['match_label'], 'none')

    def test_current_analysis_identity_invalidates_old_cached_knowledge(self):
        from job_discovery.matching import current_match_versions
        self.assertEqual(SCORING_VERSION, current_match_versions()['scoring_version'])
        self.assertEqual(current_match_versions()['scoring_version'], SCORING_VERSION)
        self.assertNotEqual(SCORING_VERSION, 'stable-evidence-v1.15-phase6d20')


if __name__ == '__main__':
    unittest.main()

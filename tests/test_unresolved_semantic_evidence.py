"""Offline exploratory boundaries; synthetic controls never become human gold."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from taxonomy_discovery import unresolved_semantic_evidence as d
from scripts import investigate_unresolved_semantic_evidence as report

ROOT = Path(__file__).resolve().parents[1]


class SemanticEvidenceTests(unittest.TestCase):
    def record(self, text):
        return {'evidence_id': 'SYNTHETIC_TEST_ONLY', 'source': 'SYNTHETIC_TEST_LOCATION', 'text': text}

    def connection(self, profile, text):
        return d.discover(profile, 'test_req', [self.record(text)])[0]

    def test_related_sql_not_universal_proficiency(self):
        c = self.connection('database', 'Queried SQL databases.')
        self.assertEqual(c['relevance'], 'DIRECT_RELEVANCE_CANDIDATE')
        self.assertEqual(c['claim_support'], 'BOUNDED_CLAIM_SUPPORTED')
        self.assertFalse(c['claim_authorized'])
        self.assertIn('schema design', c['does_not_prove'])

    def test_sql_server_transferable_not_postgresql_equivalence(self):
        c = self.connection('postgres', 'Developed SQL Server reporting queries.')
        self.assertEqual(c['relevance'], 'TRANSFERABLE_RELEVANCE_CANDIDATE')
        self.assertNotEqual(c['claim_support'], 'EXACT_CLAIM_SUPPORTED')

    def test_robotics_and_cpp_are_adjacent_not_ros(self):
        for text in ['Developed robotics software.', 'Built C++ engine systems.', 'Python']:
            with self.subTest(text=text):
                c = self.connection('ros', text)
                self.assertEqual(c['relevance'], 'ADJACENT_RELEVANCE_CANDIDATE')
                self.assertFalse(c['claim_authorized'])

    def test_absence_and_planned_work_fail_closed(self):
        for text in ['Developed robotics without ROS.', 'Planned LLM integration.']:
            c = self.connection('ros' if 'ROS' in text else 'llm', text)
            self.assertEqual(c['relevance'], 'UNKNOWN')
            self.assertEqual(c['claim_support'], 'CONTRADICTED_OR_UNSUPPORTED')

    def test_chatgpt_use_not_llm_development(self):
        c = self.connection('genai', 'Used ChatGPT.')
        self.assertEqual(c['relevance'], 'ADJACENT_RELEVANCE_CANDIDATE')
        self.assertEqual(c['claim_support'], 'INSUFFICIENT_EVIDENCE')

    def test_bounded_llm_implementation_not_training(self):
        c = self.connection('llm', 'Implemented LLM API integration.')
        self.assertEqual(c['relevance'], 'DIRECT_RELEVANCE_CANDIDATE')
        self.assertEqual(c['claim_support'], 'BOUNDED_CLAIM_SUPPORTED')
        self.assertIn('model training', c['does_not_prove'])

    def test_runtime_cloud_and_deployment_not_advanced_claims(self):
        for profile, text in [('api', 'Node.js'), ('cloud', 'AWS'), ('kubernetes', 'Implemented Docker CI/CD.')]:
            with self.subTest(profile=profile):
                c = self.connection(profile, text)
                self.assertEqual(c['relevance'], 'ADJACENT_RELEVANCE_CANDIDATE')
                self.assertFalse(c['influences_scoring'])
                self.assertNotEqual(c['claim_support'], 'EXACT_CLAIM_SUPPORTED')

    def test_source_reference_required_and_tampering_rejected(self):
        records = [self.record('Queried SQL databases.')]
        c = d.discover('database', 'test_req', records)
        self.assertTrue(d.validate_connections(c, records, 'test_req'))
        altered = deepcopy(c); altered[0]['source_text_sha256'] = '0'*64
        with self.assertRaises(ValueError): d.validate_connections(altered, records, 'test_req')
        with self.assertRaises(ValueError): d.discover('database', 'test_req', [{'text': 'SQL'}])
        with self.assertRaises(ValueError): d.validate_connections(c, records, 'other_req')

    def test_no_raw_private_text_and_deterministic_nonmutating_output(self):
        records = [self.record('Queried SQL databases for PRIVATE SENTINEL.')]
        before = deepcopy(records)
        output = d.discover('database', 'test_req', records)
        self.assertEqual(output, d.discover('database', 'test_req', records))
        self.assertEqual(records, before)
        self.assertNotIn('PRIVATE SENTINEL', json.dumps(output))

    def test_semantic_grounding_rejects_unanchored_spans(self):
        with self.assertRaises(ValueError): d.observation('proficiency', ['Proficiency in:'], 'SQL')


class FrozenInvestigationArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads((ROOT/'reports/unresolved_semantic_layer1_evidence_relevance_v1.json').read_text(encoding='utf-8'))
        cls.packet = json.loads((ROOT/'reports/unresolved_gold_review_packet_v4.json').read_text(encoding='utf-8'))

    def test_exact_four_cases_fingerprints_no_gold_or_scope_drift(self):
        self.assertEqual({(r['case_number'], r['job_id'], r['requirement_id']) for r in self.report['cases']},
                         {(n,j,r) for n,j,r,_ in d.CASES})
        for row in self.report['cases']:
            case = next(c for c in self.packet['cases'] if c['key'] == [row['job_id'],row['requirement_id']])
            semantics = d.semantics(case)
            self.assertEqual(semantics, row['semantic_layer1'])
            self.assertEqual(semantics['frozen_input_fingerprint'], case['input_fingerprint'])
            self.assertFalse(semantics['scoring_children_created'])
            self.assertFalse(semantics['allocations_changed'])
            self.assertEqual(row['benchmark_decision'], 'UNCHANGED_PENDING_HUMAN_REVIEW')
            altered = deepcopy(case); altered['key'][0] = 999
            with self.assertRaises(ValueError): d.semantics(altered)

    def test_heading_parent_only_examples_nested_scope_and_allocation_conservation(self):
        rows = {r['case_number']:r for r in self.report['cases']}
        self.assertEqual(rows[10]['semantic_layer1']['proficiency_level']['basis'], 'VERIFIED_PARENT_ONLY')
        self.assertEqual(len(rows[10]['semantic_layer1']['non_mandatory_examples']), 3)
        self.assertEqual(len(rows[16]['semantic_layer1']['alternative_groups']), 4)
        self.assertEqual(len(rows[16]['semantic_layer1']['conjunctive_groups']), 2)
        self.assertEqual(rows[15]['semantic_layer1']['explicit_activities'][-1]['basis'], 'VERIFIED_PARENT_ONLY')
        for row in rows.values():
            for total in row['allocation_totals'].values(): self.assertAlmostEqual(total, 1, places=5)

    def test_report_has_native_comparisons_and_no_invented_selection(self):
        for row in self.report['cases']:
            self.assertFalse(row['downstream_trace']['hypothetical_ranking_substituted'])
            self.assertFalse(row['downstream_trace']['project_omission_demonstrated'])
            self.assertIsNotNone(row['native_probe'])
            for c in row['evidence_connections']:
                self.assertTrue(c['evidence_id']); self.assertTrue(c['source_location'])
                self.assertEqual(len(c['source_text_sha256']), 64)
                self.assertFalse(c['claim_authorized'])
        self.assertEqual(self.report['findings']['confirmed_discovery_false_negatives'], 0)

    def test_protected_bytes_and_report_seal_unchanged(self):
        self.assertEqual(self.report['protected_artifact_hashes'], report.protected_hashes())
        sealed = deepcopy(self.report); seal = sealed.pop('report_fingerprint')
        self.assertEqual(seal, report.fingerprint(sealed))
        self.assertTrue(self.report['protected_hashes_unchanged'])
        self.assertEqual(self.report['restrictions']['database_writes'], 0)

    def test_repeatable_source_only_builder_without_local_database(self):
        before = report.protected_hashes()
        a = report.build_report(); b = report.build_report()
        self.assertEqual(a, b)
        self.assertEqual(before, report.protected_hashes())
        self.assertTrue(all(c['native_probe'] is None for c in a['cases']))
        self.assertTrue(all(c['kind'] == 'SYNTHETIC_NOT_GOLD' for c in a['synthetic_controls']))


if __name__ == '__main__': unittest.main()

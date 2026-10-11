import unittest
from copy import deepcopy
from taxonomy_discovery.technology_knowledge_preview import classify, PURE, validated_identity_registry, preview, validate_bulk
from taxonomy_discovery.technology_registry import TechnologyRegistry, get_default_registry


def row(text, **extra):
    return {'text': text, 'atomic_focus': text, 'importance': 'core',
            'source_provenance': [{'parent_occurrence_id': 'fixture', 'parent_text': text,
                'raw_parent_text': text, 'source': 'raw_jd.requirements'}], **extra}


class KnowledgePreviewTests(unittest.TestCase):
    def setUp(self):
        # Temporary test identities are fixtures, not admissible real proposals.
        native = get_default_registry()
        baseline = tuple(e for e in native.entries if not {'python','sql','aws','java'}.intersection(a.lower() for a in e['aliases']))
        self.registry = TechnologyRegistry(native.version, baseline + tuple(
            {'technology_id': t.lower(), 'label': t, 'aliases': [t], 'capability_relationships': []}
            for t in ('Python', 'SQL', 'AWS', 'Java')))

    def test_atomic_identity_without_capability_or_credit(self):
        for text in ('Experience with Python', 'SQL', 'Experience with AWS', 'Experience with MongoDB', 'Experience with Node.js'):
            r = row(text, match_label='none', match_value=0, evidence=[])
            saved = deepcopy(r)
            d = classify(r, registry=self.registry)
            self.assertEqual(d['category'], 'PURE_ATOMIC_TECHNOLOGY')
            self.assertTrue(d['identity_resolved'])
            self.assertIsNone(d['capability_id'])
            self.assertEqual(r, saved)

    def test_and_requires_every_component(self):
        r = row('Proficiency in Python and SQL is expected')
        d = classify(r, registry=self.registry)
        self.assertEqual(d['category'], 'PURE_TECHNOLOGY_AND_LIST')
        self.assertTrue(d['identity_resolved'])
        only = TechnologyRegistry(self.registry.version, tuple(e for e in self.registry.entries if e['technology_id'] != 'sql'))
        self.assertFalse(classify(r, registry=only)['identity_resolved'])
        self.assertFalse(d['structure']['scoring_children_created'])

    def test_or_preserves_native_alternatives(self):
        r = row('Proficiency in Python or Java')
        only = TechnologyRegistry(self.registry.version, tuple(e for e in self.registry.entries if e['technology_id'] != 'java'))
        d = classify(r, registry=only)
        self.assertEqual(d['category'], 'PURE_TECHNOLOGY_OR_LIST')
        self.assertEqual(d['structure']['mode'], 'any')
        self.assertTrue(d['identity_resolved'])

    def test_optional_semantics_fail_closed_when_native_unavailable(self):
        d = classify(row('Proficiency in languages such as Python or Java'), registry=self.registry)
        if d['category'] in PURE:
            self.assertEqual(d['category'], 'PURE_TECHNOLOGY_ONE_OF_OR_EXAMPLE_LIST')
            self.assertEqual(d['structure']['mode'], 'any')
        for text in ('Generic technology examples such as Python', 'Proficiency in languages such as Python and Java'):
            self.assertFalse(classify(row(text), registry=self.registry)['identity_resolved'])

    def test_existing_native_optional_contract_with_provenance(self):
        r = row('Experience in languages such as Python or Java',
                structured_match_required_terms=['Python', 'Java'], structured_match_group_mode='any',
                structured_match_kind='programming_language_group')
        only = TechnologyRegistry(self.registry.version, tuple(e for e in self.registry.entries if e['technology_id'] != 'java'))
        d = classify(r, registry=only)
        self.assertEqual(d['category'], 'PURE_TECHNOLOGY_ONE_OF_OR_EXAMPLE_LIST')
        self.assertTrue(d['identity_resolved'])
        self.assertEqual(d['structure']['mode'], 'any')

    def test_activity_and_capability_negatives(self):
        for text in ('Build APIs using Node.js', 'Design databases using MongoDB', 'Deploy AI models using AWS',
                     'Experience with distributed systems using Java', 'Secure applications written in C#',
                     'Programming skills using Python', 'Proficiency in SQL for database design'):
            d = classify(row(text), registry=self.registry)
            self.assertNotIn(d['category'], PURE)
            self.assertFalse(d['identity_resolved'])

    def test_mixed_and_substring_and_net_fail_closed(self):
        for text in ('Experience with Python and teamwork', 'Pythonesque', 'Python developer',
                     'Experience with NET', 'NET MVC', 'Experience with .NET and teamwork'):
            self.assertFalse(classify(row(text), registry=self.registry)['identity_resolved'])

    def test_missing_or_forged_parent_provenance(self):
        r = row('Python'); r['source_provenance'] = []
        self.assertFalse(classify(r, registry=self.registry)['identity_resolved'])
        r = row('Python'); r['source_provenance'][0]['parent_text'] = 'Build APIs using Python'
        self.assertFalse(classify(r, registry=self.registry)['identity_resolved'])

    def test_evidence_labels_and_group_allocation_unchanged(self):
        for label in ('none', 'weak', 'transferable', 'direct'):
            r = row('MongoDB', match_label=label, evidence=[{'evidence_id': 'frozen'}], group_weight_fraction=.25)
            b = deepcopy(r); classify(r, registry=self.registry)
            self.assertEqual(r, b)

    def test_unsealed_proposal_rejected(self):
        with self.assertRaises(ValueError):
            validated_identity_registry([({}, {})])

    def test_partial_native_terms_do_not_resolve_parent(self):
        r = row('Experience building APIs and teamwork', structured_match_required_terms=['Python', 'SQL'], structured_match_group_mode='all')
        self.assertFalse(classify(r, registry=self.registry)['identity_resolved'])
        r = row('Proficiency in Python or SQL', structured_match_required_terms=['Python', 'Java'], structured_match_group_mode='any')
        self.assertFalse(classify(r, registry=self.registry)['identity_resolved'])
        self.assertFalse(classify(row('Proficiency in Python or SQL is preferred for data science'), registry=self.registry)['identity_resolved'])

    def test_architecture_identity_does_not_resolve_capability(self):
        d = classify(row('Experience with Microservices'), registry=self.registry)
        self.assertEqual(d['category'], 'TECHNOLOGY_PLUS_CAPABILITY')
        self.assertFalse(d['identity_resolved'])

    def test_native_child_with_activity_tail_remains_blocked(self):
        r = row('Proficiency in C#')
        r['source_provenance'][0]['raw_parent_text'] = 'Proficiency in C#, .NET and SQL Server for backend development'
        self.assertFalse(classify(r, registry=self.registry)['identity_resolved'])

    def test_alias_collision_fails_closed(self):
        duplicate = TechnologyRegistry(self.registry.version, self.registry.entries + ({'technology_id': 'other', 'aliases': ['Python']},))
        self.assertFalse(classify(row('Python'), registry=duplicate)['identity_resolved'])

    def test_explicit_bulk_execution(self):
        with self.assertRaisesRegex(ValueError, 'Explicit'):
            validate_bulk({})

    def test_unique_union_and_separate_metrics_without_mutation(self):
        r = row('Experience with MongoDB', requirement_id='same', group_weight_fraction=.5, match_label='none', evidence=[])
        audit_row = {'job_id': 1, 'requirement_id': 'same', 'requirement_text': r['text'], 'importance': 'core',
                     'score_eligible': True, 'group_weight_fraction': .5,
                     'current_resolution': {'status': 'recognized_unmapped', 'capability_id': None}}
        a = {'corpus': {'jobs': [{'job_id': 1, 'baseline_stable_analysis': {'canonical_requirements': [r]}}]},
             'queue': [], 'requirements': [audit_row], 'summary': {'meaningful_technical_requirements': 1}}
        original = deepcopy(a)
        out = preview(a)
        self.assertEqual(out['counts'], {'TECHNOLOGY_IDENTITY_RESOLVED': 1})
        self.assertEqual(out['overall_coverage']['total_weight'], 1.5)
        self.assertEqual(a, original)
        a['requirements'].append(deepcopy(audit_row))
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            preview(a)


if __name__ == '__main__':
    unittest.main()

"""Native diagnostic dependency graphs and non-additive review impact."""
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
import unittest
from taxonomy_discovery import gap_reduction_assistant as assistant, maintenance_service as maintenance
from tests.test_taxonomy_maintenance_service import fixture_corpus
from tests.tqd3_publication_fixture_support import PublicationFixture


class GapDependencyTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        self.fixture = self.stack.enter_context(PublicationFixture())
        self.snapshot = maintenance.run_corpus_audit(corpus=fixture_corpus(*[
            "Proficiency in programming languages such as Python, SQL, or Java"] * 8,
            "Experience with cloud platforms such as AWS, Azure, or equivalent tools"),
            explicit_execution=True, review_db_path=self.fixture.tmp / "review.sqlite")

    def plan(self):
        return assistant.build_plan(self.snapshot, review_db_path=self.fixture.tmp / "review.sqlite")

    def test_python_eight_mentions_zero_direct_and_bundle_foundation(self):
        plan = self.plan()
        python = next(a for a in plan["all_actions"] if a["concept"] == "python")
        self.assertEqual(python["mentioned_requirements"], 8)
        self.assertEqual(python["estimated_directly_resolvable"], 0)
        self.assertIsNone(python["validated_resolved"])
        self.assertEqual(python["impact_role"], "FOUNDATIONAL")
        self.assertGreater(python["unlocks_dependency_bundles"], 0)
        self.assertEqual(python["marginal_directly_resolvable"], 0)

    def test_graph_determinism_and_complete_unique_union(self):
        first = self.plan()
        self.assertEqual(first, self.plan())
        graphs = first["requirement_dependency_graphs"]
        keys = {(g["job_id"], g["requirement_id"]) for g in graphs}
        self.assertEqual(len(keys), len(graphs))
        self.assertEqual(len(graphs), first["baseline"]["unresolved"])
        self.assertTrue(all(g["nodes"] and g["edges"] for g in graphs))
        self.assertTrue(all(g["association_semantics"] == "co_occurring_native_diagnostics_not_proven_all" for g in graphs))
        self.assertTrue(all(not g["joint_blockers_proven"] for g in graphs))

    def test_python_sql_and_aws_azure_overlap_not_double_counted(self):
        plan = self.plan()
        identities = {a["concept"]: a for a in plan["all_actions"] if a["fix_layer"] == maintenance.IDENTITY_GAP}
        self.assertEqual(identities["python"]["requirement_keys"], identities["sql"]["requirement_keys"])
        self.assertEqual(identities["aws"]["requirement_keys"], identities["azure"]["requirement_keys"])
        self.assertEqual(plan["dependency_impact_summary"]["unique_identity_mentioned_unresolved_requirements"], 9)
        self.assertEqual(plan["dependency_impact_summary"]["shared_identity_requirements"], 9)
        self.assertEqual(sum(a["marginal_mentioned_requirements"] for a in plan["foundational_priority"]), 9)
        self.assertEqual(plan["dependency_impact_summary"]["estimated_directly_resolvable"], 0)

    def test_parser_priority_separate_from_foundations_and_union_weight(self):
        plan = self.plan()
        self.assertTrue(plan["decomposition_parser_bottlenecks"])
        first = plan["direct_gap_reduction_priority"][0]
        self.assertEqual(first["kind"], "parser_family")
        self.assertEqual(first["impact_role"], "DEPENDENCY")
        self.assertGreater(first["downstream_actions_unlocked_for_review"], 1)
        self.assertEqual(first["required_core_weight"], 27.0)
        self.assertIsNone(first["code_change_required"])
        self.assertEqual(first["estimated_directly_resolvable"], 0)
        self.assertEqual(plan["directly_resolving_actions"], [])
        self.assertFalse(any(a["impact_role"] == "FOUNDATIONAL" for a in plan["direct_gap_reduction_priority"]))

    def test_all_actions_have_required_fields_and_no_knowledge_or_score_changes(self):
        before = deepcopy(self.snapshot)
        scorer = Path("analysis_stability/stable_evidence_scoring.py").read_bytes()
        taxonomy = Path("taxonomy/capability_taxonomy_v1.json").read_bytes()
        plan = self.plan()
        fields = {"impact_role", "mentioned_requirements", "unique_requirements", "atomically_addressable_requirements",
            "estimated_directly_resolvable", "validated_resolved", "dependent_requirement_count", "dependency_ids"}
        self.assertTrue(all(fields <= a.keys() for a in plan["all_actions"]))
        self.assertEqual(self.snapshot, before)
        self.assertEqual(Path("analysis_stability/stable_evidence_scoring.py").read_bytes(), scorer)
        self.assertEqual(Path("taxonomy/capability_taxonomy_v1.json").read_bytes(), taxonomy)
        self.assertEqual(self.fixture.real_registry.read_bytes(), self.fixture.real_registry_bytes)
        self.assertEqual(plan["production_writes"], 0)
        self.assertEqual(plan["planned_external_calls"], 0)
        self.fixture.model_guard.assert_not_called(); self.fixture.network_guard.assert_not_called()


if __name__ == "__main__":
    unittest.main()

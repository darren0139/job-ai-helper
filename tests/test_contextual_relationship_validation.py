from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import unittest

from taxonomy_discovery import contextual_relationship_validation as relationships, maintenance_service as maintenance, gap_reduction_assistant as assistant
from tailoring import production_requirement_resolver as resolver
from tests.test_taxonomy_maintenance_service import fixture_corpus
from tests.tqd3_publication_fixture_support import PublicationFixture


class ContextPredicateTests(unittest.TestCase):
    def resolve(self, text):
        return resolver.resolve_requirement_with_production_knowledge({"text": text})

    def test_identity_only_mongodb_and_node_are_not_capabilities(self):
        with relationships.temporary_context_scope(relationships.PROFILES):
            for text in ("MongoDB", "Experience with MongoDB", "Node.js", "Experience with Node.js"):
                with self.subTest(text=text):
                    self.assertIsNone(self.resolve(text)["decision"]["capability_id"])

    def test_contextual_schema_design_separate_from_persistence_and_querying(self):
        self.assertIsNone(self.resolve("Design MongoDB schema")["decision"]["capability_id"])
        with relationships.temporary_context_scope(["mongodb_schema_design"]):
            result = self.resolve("Design MongoDB schema")
            self.assertEqual(result["decision"]["capability_id"], "database.design")
            for text in ("Administer MongoDB", "Manage data persistence using MongoDB", "Query MongoDB"):
                self.assertIsNone(self.resolve(text)["decision"]["capability_id"])
        for text in ("manage data persistence using MongoDB", "query MongoDB", "administer MongoDB"):
            self.assertEqual(relationships.context({"text": text}, "mongodb")[2], "NEEDS_CAPABILITY_RESEARCH")

    def test_contextual_node_api_is_separate_from_runtime_or_frontend(self):
        self.assertIsNone(self.resolve("Build APIs using Node.js")["decision"]["capability_id"])
        with relationships.temporary_context_scope(["node_api_implementation"]):
            self.assertEqual(self.resolve("Build APIs using Node.js")["decision"]["capability_id"], "backend.api_development")
            self.assertIsNone(self.resolve("Run batch jobs using Node.js")["decision"]["capability_id"])

    def test_negative_contexts_and_global_mappings_unchanged(self):
        self.assertTrue(all(c["passed"] for c in relationships._negative_checks(relationships.PROFILES)))

    def test_dotnet_corruption_blocks_relationships_and_csharp_parent(self):
        for text, technology in (("NET (MVC & Core), and SQL Server", "dotnet"), ("Proficiency in C#", "csharp")):
            row = {"text": text, "source_provenance": [{"raw_parent_text": "Proficiency in C#, .NET (MVC & Core), and SQL Server"}]}
            self.assertEqual(relationships.context(row, technology)[2], "BLOCKED_BY_PARSER_OR_NORMALIZATION")

    def test_other_contexts_do_not_leak_across_threads_or_nested_scopes(self):
        native = resolver.resolve_requirement_text
        with relationships.temporary_context_scope(["node_api_implementation"]):
            with ThreadPoolExecutor(max_workers=1) as worker:
                value = worker.submit(self.resolve, "Build APIs using Node.js").result()
                self.assertIsNone(value["decision"]["capability_id"])
            with relationships.temporary_context_scope(["mongodb_schema_design"]):
                self.assertIsNone(self.resolve("Build APIs using Node.js")["decision"]["capability_id"])
            self.assertEqual(self.resolve("Build APIs using Node.js")["decision"]["capability_id"], "backend.api_development")
        self.assertIs(resolver.resolve_requirement_text, native)

    def test_exception_restores_native_lookup_and_knowledge_files(self):
        files = [Path(p) for p in ("analysis_stability/stable_evidence_scoring.py", "tailoring/production_requirement_resolver.py",
            "tailoring/phase6d6_structured_matching.py", "taxonomy/capability_taxonomy_v1.json", "taxonomy/technology_registry_v1.json")]
        before = [p.read_bytes() for p in files]
        native = resolver.resolve_requirement_text
        with self.assertRaisesRegex(RuntimeError, "fixture abort"):
            with relationships.temporary_context_scope(relationships.PROFILES):
                raise RuntimeError("fixture abort")
        self.assertEqual(before, [p.read_bytes() for p in files])
        self.assertIs(resolver.resolve_requirement_text, native)


class RelationshipInventoryTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        self.fixture = self.stack.enter_context(PublicationFixture())
        self.snapshot = maintenance.run_corpus_audit(corpus=fixture_corpus("Experience with MongoDB", "Experience with Node.js"),
            explicit_execution=True, review_db_path=self.fixture.tmp / "reviews.sqlite")

    def plan(self):
        return assistant.build_plan(self.snapshot, review_db_path=self.fixture.tmp / "reviews.sqlite")

    def test_inventory_deterministic_identity_only_no_automatic_replay(self):
        before = deepcopy(self.snapshot)
        a = self.plan()["contextual_relationship_inventory"]
        self.assertEqual(a, self.plan()["contextual_relationship_inventory"])
        self.assertEqual(before, self.snapshot)
        self.assertTrue(a["action_count"])
        self.assertTrue(all(c["existing_capability_id"] is None for c in a["candidates"]))
        self.assertTrue(all(c["validated_impact"] is None for c in a["candidates"]))
        self.fixture.model_guard.assert_not_called(); self.fixture.network_guard.assert_not_called()

    def test_explicit_validation_and_empty_combined_overlay_are_read_only(self):
        inventory = self.plan()["contextual_relationship_inventory"]
        with self.assertRaisesRegex(ValueError, "Explicit"):
            relationships.validate(self.snapshot, inventory)
        before = deepcopy(self.snapshot)
        report = relationships.validate(self.snapshot, inventory, explicit_execution=True)
        self.assertEqual(report["profiles"], [])
        self.assertEqual(report["combined"]["newly_resolved"], [])
        self.assertEqual(report["combined"]["unexpected_changes"], [])
        self.assertEqual(report["baseline"], report["combined"]["overlay"])
        self.assertEqual(before, self.snapshot)
        self.assertEqual(report["production_writes"], 0)
        self.assertTrue(relationships.report_current(self.snapshot, inventory, report))
        report["profiles"] = ["node_api_implementation"]
        self.assertFalse(relationships.report_current(self.snapshot, inventory, report))

    def test_inventory_keys_are_unique_when_multiple_actions_share_a_requirement(self):
        plan = self.plan()
        actions = [deepcopy(a) for a in plan["all_actions"] if a["fix_layer"] == maintenance.RELATIONSHIP_GAP]
        actions.append(deepcopy(actions[0]))
        inventory = relationships.build_inventory(self.snapshot, actions, self.snapshot["gap_rows"])
        keys = {(r["job_id"], r["requirement_id"]) for c in inventory["candidates"] for r in c["requirements"]}
        self.assertEqual(len(keys), inventory["unique_requirement_count"])
        self.assertEqual(inventory["unique_requirement_count"], plan["contextual_relationship_inventory"]["unique_requirement_count"])

    def test_combined_native_overlay_resolves_each_context_once(self):
        snapshot = maintenance.run_corpus_audit(corpus=fixture_corpus("Design MongoDB schema", "Build APIs using Node.js"),
            explicit_execution=True, review_db_path=self.fixture.tmp / "reviews.sqlite")
        baseline = deepcopy(snapshot)
        result = relationships._replay_report(snapshot, list(relationships.PROFILES))
        keys = {(r["job_id"], r["requirement_id"]) for r in result["newly_resolved"]}
        # Canonical native schema-design knowledge already resolves MongoDB;
        # do not count it again as an overlay gain. Only the Node API gap is new.
        self.assertEqual({job for job, _ in keys}, {2})
        self.assertEqual(len(keys), 1)
        self.assertEqual(len(keys), len(result["newly_resolved"]))
        self.assertEqual(len({(r["job_id"], r["requirement_id"]) for r in result["affected_requirements"]}), 2)
        self.assertEqual(result["newly_unresolved"], [])
        self.assertEqual(result["unexpected_changes"], [])
        self.assertEqual(snapshot, baseline)
        self.fixture.model_guard.assert_not_called(); self.fixture.network_guard.assert_not_called()


if __name__ == "__main__":
    unittest.main()

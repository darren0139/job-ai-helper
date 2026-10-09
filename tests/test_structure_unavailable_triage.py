"""Offline diagnostic partitioning; no parser or scorer overrides."""
from copy import deepcopy
from pathlib import Path
import unittest

from taxonomy_discovery import structure_unavailable_triage as triage
from tests import test_gap_reduction_dependencies as dependency_tests


class StructureDiagnosticTests(unittest.TestCase):
    def diagnose(self, text):
        return triage.diagnose({"text": text, "importance": "core", "score_eligible": True})

    def test_and_or_semantics_not_converted_to_all(self):
        both = self.diagnose("Experience with Python and SQL")
        either = self.diagnose("Experience with Python or SQL")
        self.assertGreater(len(both["native_probe_clauses"]), 1)
        self.assertEqual(either["root_cause"], "alternative_or_slash_scope_review")
        self.assertEqual(either["scope_semantics"], "alternative_or_slash_unproven")
        self.assertIsNone(either["code_change_required"])

    def test_examples_one_of_and_nested_examples_preserved(self):
        for text in ("Experience with cloud platforms such as AWS, Azure, or GCP",
                     "Experience with one or more of Python, Java, SQL"):
            with self.subTest(text=text):
                result = self.diagnose(text)
                self.assertEqual(result["root_cause"], "native_intentionally_coherent_parent")
                self.assertTrue(result["native_behavior_correct"])
                self.assertFalse(result["code_change_required"])
                self.assertEqual(len(result["native_probe_clauses"]), 1)
        nested = self.diagnose("Cloud platforms (e.g., AWS, Azure, GCP, or equivalent tools)")
        self.assertEqual(nested["root_cause"], "example_or_one_of_scope_not_globally_preserved")
        self.assertIsNone(nested["code_change_required"])
        self.assertEqual(nested["estimated_directly_resolvable"], 0)

    def test_missing_identity_and_capability_do_not_prove_parser_issue(self):
        for text in ("Python", "Critical Infrastructure Security: Implement robust security protocols"):
            result = self.diagnose(text)
            self.assertEqual(result["root_cause"], "no_structural_split_demonstrated")
            self.assertFalse(result["code_change_required"])

    def test_bounded_list_is_diagnostic_not_scoring_children(self):
        row = {"text": "Proficient in Groovy, Python, Bash", "importance": "core"}
        before = deepcopy(row)
        first = triage.diagnose(row)
        self.assertEqual(first, triage.diagnose(row))
        self.assertEqual(row, before)
        self.assertEqual(first["root_cause"], "bounded_named_list_wrapper_not_admitted")
        self.assertEqual(len(first["native_probe_clauses"]), 1)
        self.assertEqual(first["estimated_directly_resolvable"], 0)
        self.assertIsNone(first["validated_resolved"])

    def test_canonical_child_keeps_parent_example_boundary_for_review(self):
        row = {"text": "Net and C#", "importance": "core", "source_provenance": [{
            "raw_parent_text": "Proficiency in web technologies such as Angular, .Net and C#"}]}
        result = triage.diagnose(row)
        self.assertEqual(result["root_cause"], "canonical_child_parent_example_scope_review")
        self.assertEqual(result["scope_semantics"], "examples_or_one_of")
        self.assertIsNone(result["code_change_required"])

    def test_presentation_prefix_is_only_a_diagnostic_probe(self):
        text = "\u00b7 Proficient in Groovy, Python, Bash Scripting"
        result = self.diagnose(text)
        self.assertEqual(result["root_cause"], "presentation_prefixed_named_list_review")
        self.assertEqual(result["native_probe_clauses"][0]["text"], text)
        self.assertIsNone(result["code_change_required"])


class StructureProjectionTests(unittest.TestCase):
    # Reuse the native frozen corpus/store and zero-network guards, with no
    # duplicate fixtures or implementation-derived expected scorer outcomes.
    setUp = dependency_tests.GapDependencyTests.setUp
    plan = dependency_tests.GapDependencyTests.plan

    def test_partition_and_dependencies_preserve_unique_native_sets(self):
        first = self.plan()
        projected = first["structure_unavailable_triage"]
        self.assertEqual(projected, self.plan()["structure_unavailable_triage"])
        # This coherent example fixture deliberately has no unavailable rows.
        self.assertEqual(projected["total"], 0)
        raw = {(j["job_id"], r["requirement_id"]): r for j in self.snapshot["audit"]["corpus"]["jobs"]
            for r in j["baseline_stable_analysis"]["canonical_requirements"]}
        requirements = {(r["job_id"], r["requirement_id"]): r for r in self.snapshot["audit"]["requirements"]}
        family = first["decomposition_parser_bottlenecks"][0]
        # The projection itself handles any supplied native family keys; test
        # partition/dependency conservation independently of bucket selection.
        projected = triage.project(self.snapshot, first["requirement_dependency_graphs"], family, raw, requirements)
        self.assertEqual(projected["total"], family["unique_unresolved_requirements"])
        self.assertEqual(projected["partition_unique_requirements"], projected["total"])
        self.assertEqual(sum(r["unique_marginal_requirements"] for r in projected["subfamilies"]), projected["total"])
        self.assertEqual(sum(r["required_core_weight"] for r in projected["subfamilies"]), family["required_core_weight"])
        ids = set().union(*(set(r[k + "_action_ids_for_review"]) for r in projected["subfamilies"] for k in ("identity", "relationship", "capability")))
        self.assertEqual(ids, set(family["downstream_action_ids"]))
        # NEEDS_DECOMPOSITION is a research state, not a replacement for the
        # native capability remediation family. Retain both in review counts.
        graphs = deepcopy(first["requirement_dependency_graphs"])
        node = next(n for g in graphs for n in g["nodes"] if n["fix_layer"] == "TECHNOLOGY_IDENTITY_GAP")
        aid = node["dependency_id"]
        for g in graphs:
            for n in g["nodes"]:
                if n["dependency_id"] == aid:
                    n.update(fix_layer="NEEDS_DECOMPOSITION", remediation_fix_layer="ACTUAL_CAPABILITY_TAXONOMY_GAP")
        changed = triage.project(self.snapshot, graphs, family, raw, requirements)
        self.assertIn(aid, set().union(*(set(r["capability_action_ids_for_review"]) for r in changed["subfamilies"])))
        self.assertTrue(all(r["source_provenance"] and r["decomposition_ran"] for r in projected["requirement_traces"]))
        self.assertEqual(projected["recommendation"], "NO SAFE GENERIC FIX YET")
        self.fixture.model_guard.assert_not_called()
        self.fixture.network_guard.assert_not_called()

    def test_protected_sources_and_snapshot_unchanged(self):
        before = deepcopy(self.snapshot)
        files = [Path(p) for p in ("analysis_stability/stable_evidence_scoring.py",
            "tailoring/phase6d6_structured_matching.py", "taxonomy/capability_taxonomy_v1.json",
            "taxonomy/technology_registry_v1.json")]
        contents = [p.read_bytes() for p in files]
        self.plan()
        self.assertEqual(before, self.snapshot)
        self.assertEqual(contents, [p.read_bytes() for p in files])


if __name__ == "__main__":
    unittest.main()

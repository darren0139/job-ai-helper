"""Native list identity diagnostics without parent scoring or substring matching."""
from copy import deepcopy
import unittest
from unittest.mock import patch
from tailoring.phase6d6_structured_matching import technology_requirement_structure as structure
from tailoring.production_requirement_resolver import resolve_requirement_with_production_knowledge as resolve
from taxonomy_discovery import technology_registry as registry
from taxonomy_discovery import gap_reduction_assistant as assistant, maintenance_service as maintenance
from tests.test_taxonomy_maintenance_service import fixture_corpus
from tests.tqd3_publication_fixture_support import PublicationFixture


class TechnologyCompoundBridgeTests(unittest.TestCase):
    def test_native_and_components_weight_and_provenance(self):
        text = "Proficiency in Python and SQL is expected"
        result = structure({"text": text, "importance": "core"})
        self.assertEqual(result["mode"], "all")
        self.assertEqual([c["atomic_focus"] for c in result["components"]], ["Proficiency in Python", "Proficiency in SQL"])
        self.assertTrue(all(c["parent_text"] == text and c["importance"] == "core" for c in result["components"]))
        self.assertEqual(len({c["atomic_group_id"] for c in result["components"]}), 1)
        self.assertTrue(result["parent_weight_preserved"])
        self.assertFalse(result["scoring_children_created"])

    def test_native_or_mode(self):
        result = structure({"text": "Proficiency in Python, R, or Java", "importance": "core"})
        self.assertEqual(result["mode"], "any")
        self.assertEqual([c["text"] for c in result["components"]], ["Python", "R", "Java"])

    def test_native_coherent_one_of_examples_and_mixed_are_held(self):
        for text in ("Proficiency in one or more programming/scripting languages (python, nodejs, etc.)",
            "Proficiency in one or more of Python, Java",
            "Advanced proficiency in at least one analytical tool such as Python, SQL, Power BI, Tableau, or equivalent tools",
            "Scripting, programming, and automation languages (e.g. Ansible, PowerShell, Python)",
            "develop and enhance modern enterprise applications using React, TypeScript and Python technologies while collaborating within an Agile delivery team",
            "Proficiency in programming languages such as Python, R, or Java, with experience in AI/ML frameworks like TensorFlow"):
            self.assertEqual(structure({"text": text})["components"], [], text)

    def test_existing_successful_one_of_contract_reused(self):
        result = structure({"text": "Experience in languages such as Python or Java", "structured_match_required_terms": ["Python", "Java"],
            "structured_match_group_mode": "any", "structured_match_kind": "programming_language_group"})
        self.assertEqual(result["mode"], "any")
        self.assertEqual(result["source"], "native_structured_match")

    def test_negative_prose_and_heading_do_not_expose_identity(self):
        for text in ("Python picnic club", "Our company Python builds games", "Python is not required",
                     "Knowledge of Python is not required", "Candidates may submit Python examples", "Requirements"):
            self.assertEqual(structure({"text": text})["components"], [], text)

    def test_exact_overlay_component_never_implies_parent_capability(self):
        current = registry.get_default_registry()
        overlay = registry.TechnologyRegistry(current.version, tuple(deepcopy(current.entries)) + ({
            "technology_id": "python", "label": "Python", "aliases": ["Python"], "entry_kind": "language", "capability_relationships": []},))
        original = deepcopy(current.entries)
        with registry.temporary_registry_scope(overlay):
            self.assertEqual(registry.resolve_requirement_text("Proficiency in Python and SQL is expected")["status"], "unresolved")
            result = resolve({"text": "Proficiency in Python and SQL is expected"})
            components = result["registry_resolution"]["native_component_resolution"]["components"]
            self.assertEqual(components[0]["registry_resolution"]["technology_id"], "python")
            self.assertEqual(components[1]["registry_resolution"]["status"], "unresolved")
            self.assertIsNone(result["decision"]["capability_id"])
            self.assertEqual(result["registry_resolution"]["status"], "unresolved")
        self.assertEqual(registry.get_default_registry().entries, original)

    def test_assistant_identity_mentions_not_additive_direct_resolutions(self):
        with PublicationFixture() as f:
            snapshot = maintenance.run_corpus_audit(corpus=fixture_corpus("Advanced proficiency in at least one analytical tool such as Python, SQL, or equivalent tools"),
                explicit_execution=True, review_db_path=f.tmp / "review.sqlite")
            plan = assistant.build_plan(snapshot, review_db_path=f.tmp / "review.sqlite")
            identities = [a for a in plan["all_actions"] if a["fix_layer"] == maintenance.IDENTITY_GAP]
            self.assertGreaterEqual(len(identities), 2)
            self.assertEqual(plan["identity_impact_summary"]["unique_mentioned_requirements"], 1)
            for a in identities:
                self.assertEqual(a["mentioned_requirements"], 1)
                self.assertEqual(a["atomically_addressable_requirements"], 0)
                self.assertEqual(a["estimated_directly_resolvable"], 0)
                self.assertIsNone(a["validated_resolved"])
            f.model_guard.assert_not_called(); f.network_guard.assert_not_called()


if __name__ == "__main__":
    unittest.main()

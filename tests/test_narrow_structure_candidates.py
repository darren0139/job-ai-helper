"""Reject unproven parser hypotheses with native offline contracts."""
from copy import deepcopy
from pathlib import Path
import unittest

from analysis_stability import stable_evidence_scoring as scorer
from tailoring import phase6d6_structured_matching as bridge
from taxonomy_discovery.technology_registry import resolve_requirement_text
from tests.structure_candidate_simulation_support import simulation, view


class NarrowStructureCandidateTests(unittest.TestCase):
    def structure(self, text):
        return bridge.technology_requirement_structure({"text": text, "importance": "core"})

    def test_exact_job370_bullet_removal_is_not_sufficient(self):
        text = "\u00b7 Proficient in Groovy, Python, Bash Scripting"
        before = self.structure(text)
        with simulation("presentation"):
            after = self.structure(text)
        self.assertEqual(before, after)
        self.assertEqual(after["components"], [])
        self.assertEqual(scorer._split_bounded_named_terms(text.lstrip("\u00b7 ")), [])

    def test_existing_controlled_and_rule_can_run_without_new_list_parser(self):
        with simulation("presentation"):
            result = self.structure("\u00b7 Experience with Python and SQL")
        self.assertEqual(result["source"], "native_jd_decomposition")
        self.assertEqual(result["mode"], "all")
        self.assertEqual(len(result["components"]), 2)
        self.assertFalse(result["scoring_children_created"])

    def test_or_one_of_and_examples_never_become_mandatory(self):
        for text in ("\u00b7 Proficient in Python or Java", "\u00b7 Proficient in Python, Java or SQL",
                     "\u00b7 Proficient in languages such as Python, Java, SQL",
                     "\u00b7 Proficient in languages (e.g. Python, Java, SQL)",
                     "\u00b7 Experience with one or more of Python, Java, SQL"):
            with self.subTest(text=text), simulation("presentation"):
                result = self.structure(text)
                self.assertEqual(result["components"], [])
                self.assertIsNone(result["mode"])
        with simulation("presentation"):
            either = self.structure("\u00b7 Proficiency in Python or Java")
        self.assertEqual(either["mode"], "any")  # existing native OR contract
        self.assertFalse(either["scoring_children_created"])

    def test_mixed_prose_protected_but_narrative_admission_rejects_prototype(self):
        for text in ("\u00b7 Proficient in Python, build APIs, deploy systems",
                     "\u00b7 Proficient in Python, documentation and teamwork"):
            with self.subTest(text=text), simulation("presentation"):
                self.assertEqual(self.structure(text)["components"], [])
        # The requested negative validation rejects the broad prototype:
        # native independent-AND decomposition also exposes activity clauses.
        # Do not pretend these are safe named technology components or change
        # production decomposition merely to make the hypothesis pass.
        with simulation("presentation"):
            narrative = self.structure("\u00b7 Design pipelines, analyse data, and write dashboards")
        self.assertEqual(narrative["source"], "native_jd_decomposition")
        self.assertEqual(len(narrative["components"]), 2)
        self.assertFalse(narrative["scoring_children_created"])

    def test_dotted_token_guard_preserves_dot_and_does_not_alias_bare_net(self):
        self.assertEqual(scorer._normalise_requirement_surface(".NET"), ". NET")
        self.assertEqual(scorer._split_requirement_sentences(".NET"), ["NET"])
        with simulation("dotnet"):
            self.assertEqual(scorer._normalise_requirement_surface(".NET"), ".NET")
            self.assertEqual(scorer._split_requirement_sentences(".NET"), [".NET"])
            rows = scorer._split_single_requirement_clause(".NET", "core")
            self.assertEqual(rows[0]["atomic_focus"], ".NET")
            dotted = resolve_requirement_text(rows[0]["atomic_focus"])
            self.assertEqual(dotted["status"], "recognized_unmapped")
            self.assertIsNone(dotted["capability_id"])
            self.assertEqual(resolve_requirement_text("NET")["status"], "unresolved")

    def test_other_technical_punctuation_unchanged(self):
        for text in ("C#", "C++", "Node.js", "React.js", "C/C++", "NET", "NET programming"):
            before = scorer._split_requirement_clauses(text, "core")
            registry = resolve_requirement_text(text)
            with self.subTest(text=text), simulation("dotnet"):
                self.assertEqual(scorer._split_requirement_clauses(text, "core"), before)
                self.assertEqual(resolve_requirement_text(text), registry)

    def test_dotnet_hypothesis_still_loses_dot_in_shared_head_child(self):
        text = "Proficiency in C#, .NET (MVC & Core), and SQL Server for backend development"
        with simulation("dotnet"):
            rows = scorer._split_requirement_clauses(text, "core")
        self.assertIn("Proficiency in NET (MVC & Core)", [r["text"] for r in rows])
        # This concrete failed boundary forbids declaring the prototype READY.
        self.assertNotIn("Proficiency in .NET (MVC & Core)", [r["text"] for r in rows])

    def test_dotnet_raw_source_retained_but_existing_parent_allocation_changes(self):
        text = "Proficiency in C#, .NET (MVC & Core), and SQL Server for backend development"
        with simulation("dotnet"):
            result = scorer.canonicalise_requirements({}, "Requirements\n" + text)
        rows = result["requirements"]
        self.assertEqual(len(rows), 3)
        self.assertEqual(len({r["atomic_group_id"] for r in rows}), 1)
        self.assertAlmostEqual(sum(r["group_weight_fraction"] for r in rows), 1, places=5)
        self.assertTrue(all(r["importance"] == "core" for r in rows))
        self.assertTrue(all(p["raw_parent_text"] == text for r in rows for p in r["source_provenance"]))
        for row in rows:
            row["match_value"] = 1.0
        self.assertEqual(scorer._weighted_coverage(rows, {"core"})[2], scorer.IMPORTANCE_WEIGHTS["core"])

    def test_parent_scope_metadata_conserves_canonical_rows_weight_provenance(self):
        text = "Proficiency in web technologies such as Angular, .Net and C#"
        before = scorer.canonicalise_requirements({}, "Requirements\n" + text)
        with simulation("parent_scope"):
            after = scorer.canonicalise_requirements({}, "Requirements\n" + text)
        annotated = [r for r in after["requirements"] if r.get("simulation_parent_scope")]
        self.assertTrue(annotated)
        for row in annotated:
            meta = row["simulation_parent_scope"]
            self.assertTrue(meta["native_coherent_parent"])
            self.assertFalse(meta["mandatory_children_inferred"])
            self.assertFalse(meta["scoring_effect"])
        clean = deepcopy(after)
        for row in clean["requirements"]:
            row.pop("simulation_parent_scope", None)
        self.assertEqual(clean, before)
        self.assertEqual(sum(r["group_weight_fraction"] for r in clean["requirements"]),
                         sum(r["group_weight_fraction"] for r in before["requirements"]))

    def test_raw_span_example_inheritance_is_not_safe_across_sentences(self):
        text = ("The next phase includes processes, including sourcing documents. "
                "You will work alongside a team to develop a minimum viable product, configure workflows, and test the solution.")
        before = scorer.canonicalise_requirements({}, text)
        with simulation("parent_scope"):
            after = scorer.canonicalise_requirements({}, text)
        obligation = next(r for r in after["requirements"] if "minimum viable product" in r["text"])
        self.assertFalse(scorer._preserves_coherent_parent(obligation["text"]))
        self.assertTrue(obligation["simulation_parent_scope"]["native_coherent_parent"])
        # This observed cross-sentence annotation is a rejection diagnostic,
        # not evidence that the obligation inherits example eligibility.
        self.assertFalse(obligation["simulation_parent_scope"]["scoring_effect"])
        for row in after["requirements"]:
            row.pop("simulation_parent_scope", None)
        self.assertEqual(after, before)

    def test_overlay_exception_restores_all_native_callables_and_sources(self):
        funcs = {name: getattr(scorer, name) for name in ("_normalise_requirement_surface", "_split_requirement_sentences", "_clause_record", "canonicalise_requirements")}
        native_bridge = bridge.technology_requirement_structure
        files = [Path(p) for p in ("analysis_stability/stable_evidence_scoring.py", "tailoring/phase6d6_structured_matching.py",
            "tailoring/production_requirement_resolver.py", "taxonomy/capability_taxonomy_v1.json", "taxonomy/technology_registry_v1.json")]
        before = [p.read_bytes() for p in files]
        for candidate in ("presentation", "dotnet", "parent_scope"):
            with self.assertRaisesRegex(RuntimeError, "deliberate fixture error"):
                with simulation(candidate):
                    raise RuntimeError("deliberate fixture error")
            self.assertEqual(funcs, {name: getattr(scorer, name) for name in funcs})
            self.assertIs(bridge.technology_requirement_structure, native_bridge)
        self.assertEqual(before, [p.read_bytes() for p in files])

    def test_contribution_report_uses_native_required_core_group_allocation(self):
        rows = [{"requirement_id": "one", "text": "Python", "importance": "core", "atomic_group_id": "same", "match_value": 1},
                {"requirement_id": "two", "text": "Java", "importance": "required", "atomic_group_id": "same", "match_value": 1}]
        job = {"baseline_stable_analysis": {"canonical_requirements": rows}, "metrics": {"deterministic_alignment_score": 0}}
        result = view(job)
        _, numerator, denominator = scorer._weighted_coverage(rows, {"required", "core", "deal_breaker"})
        self.assertEqual(sum(r["weight"] for r in result), denominator)
        self.assertEqual(sum(r["score_contribution"] for r in result), numerator)


if __name__ == "__main__":
    unittest.main()

"""Production scoring contracts exercised offline against isolated knowledge."""
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from job_discovery.matching import _default_stable_builder, build_profile_evidence_context
from tailoring.capability_taxonomy import classify_requirement_record, get_default_taxonomy
from tailoring.jd_user_input_overrides import _stable_analysis_is_current
from taxonomy_discovery.technology_registry import get_default_registry, resolve_requirement_text, TechnologyRegistry
from tests.tqd3_publication_fixture_support import PublicationFixture


def canary_analysis(name):
    context = build_profile_evidence_context([{"id": 1, "category": "Project", "title": "Product dashboard",
        "description": f"Built and implemented {name} frontend user interfaces and production applications.",
        "skills": [name], "tools": []}])
    frozen = deepcopy(context)
    result = _default_stable_builder(raw_jd_text="Requirements\n" + name,
        jd_profile={"required_skills": [name]}, context=context)
    assert context == frozen
    return result


class IntegrationCanaries(unittest.TestCase):
    def test_cpp_canonical_and_registry_do_not_double_credit(self):
        with PublicationFixture() as fixture:
            self.assertEqual(classify_requirement_record({"text": "C++"}, get_default_taxonomy())["capability_id"], "language.modern_cpp")
            self.assertEqual(resolve_requirement_text("C++")["capability_id"], "language.modern_cpp")
            before = canary_analysis("C++")
            registry = get_default_registry()
            without_cpp = TechnologyRegistry(registry.version, tuple(e for e in registry.entries if e["label"] != "C++"))
            with patch("taxonomy_discovery.technology_registry.get_default_registry", return_value=without_cpp):
                after = canary_analysis("C++")
            self.assertEqual(before["deterministic_alignment_score"], after["deterministic_alignment_score"])
            self.assertEqual(before["canonical_requirements"], after["canonical_requirements"])
            self.assertEqual(len(before["canonical_requirements"]), 1)
            evidence = before["canonical_requirements"][0]["evidence"]
            self.assertEqual(len({e["evidence_id"] for e in evidence}), len(evidence))
            self.assertEqual(fixture.real_registry.read_bytes(), fixture.real_registry_bytes)

    def test_react_genuine_evidence_credited_once(self):
        with PublicationFixture():
            self.assertIsNone(classify_requirement_record({"text": "React"}, get_default_taxonomy()))
            result = canary_analysis("React")
            rows = result["canonical_requirements"]
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["capability_id"], "frontend.ui_development")
            self.assertEqual(row["capability_resolution_source"], "technology_registry")
            self.assertEqual(row["match_label"], "direct")
            self.assertEqual(len(row["evidence"]), 1)
            self.assertIn("React", row["evidence"][0]["text"])
            self.assertEqual(result["credited_requirement_count"], 1)

    def test_version_identity_invalidates_analysis(self):
        with PublicationFixture() as fixture:
            stable = canary_analysis("React")
            self.assertTrue(_stable_analysis_is_current(stable))
            taxonomy = get_default_taxonomy()
            with patch("tailoring.jd_user_input_overrides.get_default_taxonomy", return_value=SimpleNamespace(version=taxonomy.version + "-changed")):
                self.assertFalse(_stable_analysis_is_current(stable))
            fixture.approve()
            fixture.publish()
            self.assertFalse(_stable_analysis_is_current(stable))
            after = canary_analysis("React")
            self.assertNotEqual(stable["input_fingerprint"], after["input_fingerprint"])
            self.assertTrue(_stable_analysis_is_current(after))

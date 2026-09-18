from __future__ import annotations
from copy import deepcopy
import json
import os
import unittest
from unittest.mock import Mock, patch
from tailoring.capability_taxonomy import get_default_taxonomy
from tailoring.capability_taxonomy_research import (
    SCHEMA_PATH, build_research_queries, proposal_fingerprint,
    validate_research_handover, review_proposal, reviewed_change_proposal,
)
from tailoring.capability_taxonomy_tavily import TavilyCapabilityResearchProvider, MAX_RESPONSE_BYTES


def proposal():
    return {
        "schema_version": "capability-taxonomy-research-handover-v1",
        "generated_at": "2026-09-17T00:00:00Z",
        "taxonomy_base_version": get_default_taxonomy().version,
        "research_provider": "fixture", "status": "proposed",
        "candidates": [{
            "candidate_id": "candidate.test", "intent": "create",
            "observed_term": "Test capability", "normalised_concept": "Test capability",
            "proposed_capability_id": "research.test", "proposed_family": "software",
            "aliases": ["Test alias"],
            "relationships": [{"relationship_id": "rel.test", "target_capability_id": "devops.kubernetes",
                               "target_resolution": "existing", "direction": "candidate_to_target",
                               "relationship": "related_to", "runtime_support_level": "none",
                               "support_conditions": "Related only; no runtime evidence implication"}],
            "positive_examples": [{"requirement": "Explicit capability", "evidence": "Explicit implementation", "expected_outcome": "direct"}],
            "transferable_examples": [{"requirement": "Broad capability", "evidence": "Adjacent implementation", "expected_outcome": "transferable"}],
            "negative_examples": [{"requirement": "Explicit capability", "evidence": "Unrelated token", "expected_outcome": "none"}],
            "research": {"query": "Test official documentation", "sources": [{
                "source_id": "source.test", "url": "https://kubernetes.io/docs/", "title": "Synthetic test attribution",
                "publisher": "Fixture publisher", "source_type": "official_documentation",
                "supports": [{"relationship_id": "candidate", "claim": "Synthetic claim for contract validation only"},
                             {"relationship_id": "rel.test", "claim": "Synthetic relationship claim, not researched"}]}]},
            "assessment": {"relationship_confidence": .8, "source_quality": "high", "ambiguity": "low"},
        }],
    }


def approve(payload):
    return review_proposal(payload, reviewer_identity="Test reviewer", reviewed_at="2026-09-17T01:00:00Z",
                           rationale="Reviewed synthetic contract fixture only", explicit_human_confirmation=True)


class CapabilityResearchTests(unittest.TestCase):
    def setUp(self):
        # No test can fall through to HTTP, even with a real machine credential.
        self.transport_guard = patch("tailoring.capability_taxonomy_tavily._http_transport", side_effect=AssertionError("network forbidden"))
        self.transport_guard.start()
        self.addCleanup(self.transport_guard.stop)

    def test_pending_and_review_bound_to_exact_content(self):
        p = proposal()
        before = deepcopy(p)
        review = approve(p)
        output = reviewed_change_proposal(p, review)
        self.assertFalse(output["installs_taxonomy"])
        self.assertEqual(p, before)
        p["candidates"][0]["aliases"].append("Changed after review")
        with self.assertRaisesRegex(ValueError, "changed"):
            reviewed_change_proposal(p, review)

    def test_provider_cannot_approve(self):
        p = proposal()
        p["status"] = "approved"
        with self.assertRaises(ValueError):
            validate_research_handover(p)
        with self.assertRaises(ValueError):
            reviewed_change_proposal(proposal(), {"status": "approved"})
        with self.assertRaises(ValueError):
            review_proposal(proposal(), reviewer_identity="x", reviewed_at="2026-09-17T00:00:00Z", rationale="Substantive rationale for test")

    def test_rejects_unknown_nested_fields(self):
        p = proposal()
        p["candidates"][0]["research"]["sources"][0]["api_key"] = "not-a-real-key"
        with self.assertRaises(ValueError):
            validate_research_handover(p)

    def test_finite_non_boolean_confidence(self):
        for value in (True, False, float("nan"), float("inf"), -1, 1.1, "0.8"):
            p = proposal()
            p["candidates"][0]["assessment"]["relationship_confidence"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_research_handover(p)

    def test_stale_base_and_duplicate_intents(self):
        p = proposal()
        p["taxonomy_base_version"] = "old"
        with self.assertRaises(ValueError):
            validate_research_handover(p)
        p = proposal()
        p["candidates"].append(deepcopy(p["candidates"][0]))
        with self.assertRaises(ValueError):
            validate_research_handover(p)
        p = proposal()
        p["candidates"][0]["intent"] = "update"
        with self.assertRaises(ValueError):
            validate_research_handover(p)

    def test_unresolved_and_placeholder_are_nonapprovable(self):
        p = proposal()
        rel = p["candidates"][0]["relationships"][0]
        rel.update(target_capability_id="missing.id", target_resolution="unresolved")
        validate_research_handover(p)
        with self.assertRaises(ValueError):
            approve(p)
        p = proposal()
        p["candidates"][0]["research"]["sources"][0]["url"] = "https://example.invalid/source"
        validate_research_handover(p)
        with self.assertRaises(ValueError):
            approve(p)

    def test_missing_target_claim_and_related_direct_rejected(self):
        for field, value in (("target_capability_id", "missing.id"), ("runtime_support_level", "direct"), ("direction", "target_to_candidate")):
            p = proposal()
            p["candidates"][0]["relationships"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_research_handover(p)
        p = proposal()
        p["candidates"][0]["research"]["sources"][0]["supports"].pop()
        with self.assertRaises(ValueError):
            validate_research_handover(p)

    def test_empty_key_never_falls_back_to_environment(self):
        transport = Mock(side_effect=AssertionError("network forbidden"))
        with patch.dict(os.environ, {"TAVILY_API_KEY": "configured-test-secret"}):
            provider = TavilyCapabilityResearchProvider(api_key="", transport=transport)
            with self.assertRaisesRegex(RuntimeError, "credential"):
                provider.search("Android", administrative=True)
        transport.assert_not_called()

    def test_requires_admin_action(self):
        transport = Mock()
        with self.assertRaises(PermissionError):
            TavilyCapabilityResearchProvider("test-secret", transport=transport).search("Android")
        transport.assert_not_called()

    def test_safe_transport_bounds_redaction_and_error(self):
        transport = Mock(return_value=json.dumps({"results": [{"title": "test-secret", "url": "https://docs.test", "content": "untrusted"}]}).encode())
        provider = TavilyCapabilityResearchProvider("test-secret", transport=transport)
        result = provider.search("Android", administrative=True, max_results=1)
        self.assertNotIn("test-secret", json.dumps(result))
        self.assertFalse(result[0]["trusted"])
        self.assertEqual(transport.call_args.kwargs["max_bytes"], MAX_RESPONSE_BYTES)
        transport.side_effect = RuntimeError("test-secret")
        with self.assertRaises(RuntimeError) as error:
            provider.search("Android", administrative=True)
        self.assertNotIn("test-secret", str(error.exception))
        transport.side_effect = None
        transport.return_value = b"x" * (MAX_RESPONSE_BYTES + 1)
        with self.assertRaises(RuntimeError):
            provider.search("Android", administrative=True)
        for count in (0, 11, True):
            with self.assertRaises(ValueError):
                provider.search("Android", administrative=True, max_results=count)

    def test_queries_are_explicit_deduplicated_and_bounded(self):
        self.assertEqual(len(build_research_queries(["Android", " android "])), 1)
        with self.assertRaises(ValueError):
            build_research_queries(["person@example.com"])

    def test_fingerprint_is_order_independent_for_object_keys(self):
        p = proposal()
        self.assertEqual(proposal_fingerprint(p), proposal_fingerprint(dict(reversed(list(p.items())))))

    def test_json_schema_agrees_on_structure(self):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest("Optional JSON Schema checker not installed; no dependency installation")
        validator = Draft202012Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))
        validator.validate(proposal())
        p = proposal()
        p["candidates"][0]["aliases"] = [False]
        self.assertTrue(list(validator.iter_errors(p)))
        with self.assertRaises(ValueError):
            validate_research_handover(p)

from __future__ import annotations
from copy import deepcopy
from dataclasses import replace
import os
import unittest
from unittest.mock import Mock, patch
from tailoring.capability_taxonomy import get_default_taxonomy
from tailoring.phase6d5_retrieval import build_capability_retrieval_trace
from rag import capability_taxonomy_rag as rag


class CapabilityV14BoundaryTests(unittest.TestCase):
    def test_runtime_vector_and_hybrid_never_call_external_retrieval(self):
        for mode in ("vector", "hybrid"):
            with self.subTest(mode=mode), patch.dict(os.environ, {"CAPABILITY_RAG_MODE": mode}), patch(
                "tailoring.phase6d5_retrieval.retrieve_taxonomy_candidates", side_effect=AssertionError("vector forbidden")
            ) as vector, patch.object(rag, "_collection", side_effect=AssertionError("Chroma forbidden")), patch.object(
                rag, "_embed_texts", side_effect=AssertionError("embedding forbidden")
            ):
                trace = build_capability_retrieval_trace({"text": "unknown requirement"}, exact_capability_id=None)
                self.assertFalse(trace["vector_attempted"])
                self.assertEqual(trace["requested_mode"], mode)
                self.assertEqual(trace["effective_mode"], "lexical")
                self.assertEqual(trace["vector_fallback_reason"], "administrative_retrieval_required")
                vector.assert_not_called()

    def test_rag_direct_calls_require_admin_before_side_effects(self):
        with patch.object(rag, "_collection", side_effect=AssertionError("Chroma forbidden")), patch.object(
            rag, "_embed_texts", side_effect=AssertionError("embedding forbidden")
        ):
            with self.assertRaises(PermissionError):
                rag.retrieve_taxonomy_candidates("test")
            with self.assertRaises(PermissionError):
                rag.rebuild_taxonomy_index()

    def test_stale_admin_index_fails_before_embedding_no_auto_rebuild(self):
        collection = Mock(metadata={"index_identity": "old"})
        collection.count.return_value = 10
        with patch.object(rag, "_collection", return_value=collection), patch.object(
            rag, "_embed_texts", side_effect=AssertionError("embedding forbidden")
        ), patch.object(rag, "rebuild_taxonomy_index", side_effect=AssertionError("auto rebuild forbidden")):
            with self.assertRaisesRegex(ValueError, "stale"):
                rag.retrieve_taxonomy_candidates("test", administrative=True)

    def test_index_identity_includes_rules_version_and_embedding_model(self):
        t = get_default_taxonomy()
        original = rag._index_identity(t)
        self.assertNotEqual(original, rag._index_identity(replace(t, version="old")))
        changed = deepcopy(t.capabilities)
        changed[0]["priority"] += 1
        self.assertNotEqual(original, rag._index_identity(replace(t, capabilities=changed)))
        with patch.object(rag, "EMBEDDING_MODEL", "other-model"):
            self.assertNotEqual(original, rag._index_identity(t))

    def test_taxonomy_version_changes_stable_identity_not_source_inputs(self):
        from analysis_stability import stable_evidence_scoring as scoring
        kwargs = {"jd_profile": {"required_skills": ["Python"]},
                  "raw_jd_text": "Requirements\nPython", "resume_profile": {"skills": {"languages": ["Python"]}},
                  "raw_resume_text": "Python", "keyword_match": {"present": [], "missing": []},
                  "retrieval_mode_override": "off"}
        before = deepcopy(kwargs)
        new = scoring.build_stable_analysis(**kwargs)
        with patch.object(scoring, "get_default_taxonomy", return_value=replace(get_default_taxonomy(), version="phase6d-capability-taxonomy-v1.3")):
            old = scoring.build_stable_analysis(**kwargs)
        self.assertNotEqual(new["input_fingerprint"], old["input_fingerprint"])
        self.assertEqual(new["scoring_version"], "stable-evidence-v1.5-phase6d10")
        self.assertEqual(kwargs, before)

    def test_phase9e_does_not_combine_android_and_kotlin_rows(self):
        from analysis_stability.stable_evidence_scoring import canonicalise_requirements
        from tailoring.phase9e_blueprint_selection import build_phase9e_keyword_match
        requirement = "Android application development using Kotlin"
        canonical = canonicalise_requirements(jd_profile={"required_skills": [requirement]}, raw_jd_text="Requirements\n" + requirement)
        profile = {"projects": [{"title": "Application", "bullets": ["Built an Android application in Java", "Implemented a separate Kotlin desktop tool"]}], "skills": {}, "education": [], "experience": []}
        result = build_phase9e_keyword_match(requirements=canonical["requirements"], acronym_map=canonical["acronym_map"], resume_profile=profile, raw_resume_text="")
        # Inspect selected evidence through the authoritative taxonomy cap, not
        # a fabricated joined row or a model-authored label.
        from tailoring.capability_taxonomy import evaluate_evidence
        for row in result.get("present", []):
            if row.get("keyword") == requirement:
                self.assertNotEqual(evaluate_evidence({"text": requirement}, row.get("matched_resume_term", ""))["label"], "direct")

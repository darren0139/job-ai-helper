from __future__ import annotations

import copy
import sys
import types
import unittest
from unittest.mock import Mock, patch

from tailoring.phase9c_blueprint_evaluation import evaluate_blueprint_candidate
from tailoring.phase9d_global_blueprint import (
    PHASE9D_FINGERPRINT_POLICY_VERSION,
    PHASE9D_VERSION,
    Phase9DApprovalError,
    prepare_global_blueprint_approval,
)
from tests.phase9d_test_support import load_phase9d_fixture


class Phase9DGlobalBlueprintTests(unittest.TestCase):
    def setUp(self) -> None:
        fixture = load_phase9d_fixture()
        self.candidate = fixture["candidate"]
        self.jds = fixture["saved_jds"]
        self.evaluation = evaluate_blueprint_candidate(
            candidate=copy.deepcopy(self.candidate),
            selected_jds=[copy.deepcopy(self.jds[0])],
            saved_jds_for_source_resolution=copy.deepcopy(self.jds),
        )
        self.evaluation["evaluation_id"] = self.evaluation[
            "evaluation_fingerprint"
        ][:32]
        self.evaluation["created_at"] = "2026-08-04T00:00:00"

    def prepare(self, **kwargs):
        values = {
            "candidate": copy.deepcopy(self.candidate),
            "evaluation": copy.deepcopy(self.evaluation),
            "selected_jds": [copy.deepcopy(self.jds[0])],
            "all_saved_jds": copy.deepcopy(self.jds),
            "provisional_override": {
                "accepted": True,
                "reason": (
                    "Source parity is strong while additional target JDs "
                    "are collected."
                ),
            },
            "actor_label": "Test approver",
            "accepted_at": "2026-08-04T00:01:00",
        }
        values.update(kwargs)
        return prepare_global_blueprint_approval(**values)

    def test_standalone_snapshot_copies_authoritative_candidate_and_evaluation(self):
        result = self.prepare()
        snapshot = result["blueprint_snapshot"]
        self.assertEqual(result["role_family_label"], self.candidate["role_family"])
        self.assertEqual(
            snapshot["frozen_resume_snapshot"]["resume_profile_snapshot"],
            self.candidate["resume_profile_snapshot"],
        )
        self.assertEqual(
            snapshot["frozen_resume_snapshot"]["resume_text_snapshot"],
            self.candidate["resume_text_snapshot"],
        )
        self.assertEqual(
            snapshot["phase9c_evaluation_snapshot"], self.evaluation
        )
        self.assertEqual(
            snapshot["phase9c_semantic_identity"],
            self.evaluation["semantic_identity"],
        )
        self.assertIn("resume_profile_snapshot", snapshot[
            "phase9b_candidate_semantic_snapshot"
        ])
        self.assertEqual(result["semantic_identity"]["phase9d_version"], PHASE9D_VERSION)
        self.assertEqual(
            result["semantic_identity"]["fingerprint_policy_version"],
            PHASE9D_FINGERPRINT_POLICY_VERSION,
        )

    def test_display_metadata_actor_and_override_are_outside_identity(self):
        first = self.prepare()
        changed_candidate = copy.deepcopy(self.candidate)
        changed_candidate["candidate_name"] = "New display name"
        changed_candidate["notes"] = "Different notes"
        changed_candidate["candidate_metadata"] = {"display_only": True}
        second = self.prepare(
            candidate=changed_candidate,
            provisional_override={
                "accepted": True,
                "reason": "A completely different sufficient override explanation.",
            },
            actor_label="Another actor",
            accepted_at="2026-08-05T00:00:00",
        )
        self.assertEqual(
            first["blueprint_fingerprint"], second["blueprint_fingerprint"]
        )
        identity_text = str(first["semantic_identity"])
        self.assertNotIn("Test approver", identity_text)
        self.assertNotIn("additional target JDs", identity_text)

    def test_provisional_approval_requires_acknowledgement_and_substantive_reason(self):
        cases = (
            {"accepted": False, "reason": "A sufficiently long reason is here."},
            {"accepted": True, "reason": "too short"},
        )
        for override in cases:
            with self.subTest(override=override):
                with self.assertRaises(Phase9DApprovalError):
                    self.prepare(provisional_override=override)

    def test_historical_v2_and_changed_current_jd_fail_closed(self):
        historical = copy.deepcopy(self.evaluation)
        historical["semantic_identity"]["policy"]["policy_version"] = (
            "phase9c-same-family-explicit-scope-v2"
        )
        with self.assertRaisesRegex(Phase9DApprovalError, "inspection-only"):
            self.prepare(evaluation=historical)

        changed = copy.deepcopy(self.jds)
        changed[0]["raw_text"] += " changed"
        with self.assertRaises(Phase9DApprovalError):
            self.prepare(
                selected_jds=[copy.deepcopy(changed[0])],
                all_saved_jds=changed,
            )

    def test_inputs_are_not_mutated_and_zero_call_surfaces_remain_unused(self):
        candidate = copy.deepcopy(self.candidate)
        evaluation = copy.deepcopy(self.evaluation)
        selected = [copy.deepcopy(self.jds[0])]
        all_jds = copy.deepcopy(self.jds)
        originals = copy.deepcopy((candidate, evaluation, selected, all_jds))
        llm = types.ModuleType("llm")
        llm.call_model = Mock(side_effect=AssertionError("model call attempted"))
        chroma = types.ModuleType("rag.jd_chroma_rag")
        chroma._get_chroma_client = Mock(
            side_effect=AssertionError("Chroma call attempted")
        )
        chroma.rebuild_chroma_index = Mock(
            side_effect=AssertionError("Chroma write attempted")
        )
        with patch.dict(sys.modules, {"llm": llm, "rag.jd_chroma_rag": chroma}), patch(
            "tailoring.phase6d5_retrieval.retrieve_taxonomy_candidates",
            side_effect=AssertionError("embedding retrieval attempted"),
        ) as retrieval:
            result = self.prepare(
                candidate=candidate,
                evaluation=evaluation,
                selected_jds=selected,
                all_saved_jds=all_jds,
            )
        self.assertEqual((candidate, evaluation, selected, all_jds), originals)
        self.assertEqual(result["validation"]["model_calls"], 0)
        self.assertEqual(result["validation"]["embedding_calls"], 0)
        retrieval.assert_not_called()
        llm.call_model.assert_not_called()
        chroma._get_chroma_client.assert_not_called()
        chroma.rebuild_chroma_index.assert_not_called()


if __name__ == "__main__":
    unittest.main()

"""Identity-only proposals with native replay and isolated fixture knowledge."""
from copy import deepcopy
from contextlib import ExitStack
import json
import unittest
from unittest.mock import patch

import numpy  # Load before PublicationFixture's module restoration boundary.
import pandas
from streamlit.testing.v1 import AppTest
from taxonomy_discovery import technology_identity_remediation as remediation
from taxonomy_discovery import maintenance_service as maintenance
from taxonomy_discovery import corpus_gap_resolution as gaps
from taxonomy_discovery.technology_registry import (
    TechnologyRegistry, get_default_registry, resolve_requirement_text, temporary_registry_scope,
)
from tailoring.capability_taxonomy import TAXONOMY_PATH
from pathlib import Path
from tests.test_taxonomy_maintenance_service import fixture_corpus
from tests.tqd3_publication_fixture_support import PublicationFixture


class TechnologyIdentityRemediationTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.fixture = self.stack.enter_context(PublicationFixture())
        self.taxonomy_bytes = Path(TAXONOMY_PATH).read_bytes()
        self.snapshot = maintenance.run_corpus_audit(corpus=fixture_corpus("Python", "React"),
            explicit_execution=True, review_db_path=self.fixture.tmp / "review.sqlite")
        self.cid = next(r["candidate_id"] for r in self.snapshot["gap_rows"] if r["concept"] == "python")

    def proposal(self, **kwargs):
        return remediation.prepare_identity_proposal(self.snapshot, self.cid, explicit_execution=True, **kwargs)

    def validate(self, proposal=None):
        return remediation.validate_identity_proposal(self.snapshot, proposal or self.proposal(), explicit_execution=True)

    def test_explicit_actions_only(self):
        with self.assertRaisesRegex(ValueError, "Explicit"):
            remediation.prepare_identity_proposal(self.snapshot, self.cid)
        with self.assertRaisesRegex(ValueError, "Explicit"):
            remediation.validate_identity_proposal(self.snapshot, self.proposal())

    def test_native_identity_without_capability_no_production_mutation(self):
        registry = get_default_registry()
        before = deepcopy(registry.entries)
        proposal = self.proposal()
        self.assertEqual(proposal["canonical_technology_id"], gaps._technology_id_for("Python"))
        self.assertEqual(proposal["aliases"], ["Python"])
        _, overlay = gaps._temporary_knowledge([proposal])
        with temporary_registry_scope(overlay):
            result = resolve_requirement_text("Python")
            self.assertEqual(result["status"], "recognized_unmapped")
            self.assertIsNone(result["capability_id"])
            self.assertEqual(overlay.by_id()["python"]["capability_relationships"], [])
            self.assertNotEqual(resolve_requirement_text("Python and SQL")["status"], "resolved")
            self.assertNotEqual(resolve_requirement_text("Python or SQL")["status"], "resolved")
        self.assertEqual(get_default_registry().entries, before)
        self.assertEqual(self.fixture.real_registry.read_bytes(), self.fixture.real_registry_bytes)
        self.assertEqual(Path(TAXONOMY_PATH).read_bytes(), self.taxonomy_bytes)
        self.fixture.network_guard.assert_not_called()
        self.fixture.model_guard.assert_not_called()

    def test_aliases_fail_closed_broad_alias_and_identity_collision(self):
        for aliases in (["py"], ["Python programming"], ["Python development"], []):
            with self.assertRaisesRegex(ValueError, "Aliases"):
                self.proposal(aliases=aliases)
        _, registry = gaps._temporary_knowledge([self.proposal()])
        with temporary_registry_scope(registry), self.assertRaisesRegex(ValueError, "STALE"):
            self.proposal()
        with patch.object(remediation, "get_default_registry", return_value=registry):
            with self.assertRaisesRegex(ValueError, "collision"):
                self.proposal()

    def test_native_replay_deterministic_estimated_separate_and_no_credit(self):
        first = self.validate()
        self.assertEqual(first, self.validate())
        self.assertTrue(first["validated_impact"]["atomic_identity_recognized"])
        self.assertEqual(first["validated_impact"]["newly_resolved"], 0)
        self.assertGreater(first["estimated_impact"]["requirements"], 0)
        self.assertEqual(first["unexpected_changes"], [])
        self.assertEqual(first["ranking_changes"], [])
        self.assertEqual(first["baseline"], first["temporary_overlay"])
        self.assertFalse(first["approval"])
        self.assertFalse(first["publication"])
        self.assertEqual(first["production_writes"], 0)
        self.assertFalse(any(r["job_id"] == 2 for r in first["all_changed_rows"]))

    def test_currentness_all_native_identities_and_candidate_bound(self):
        proposal = self.proposal()
        for field in ("scoring_version", "taxonomy_version", "technology_registry_version", "registry_fingerprint", "taxonomy_fingerprint"):
            altered = deepcopy(self.snapshot)
            altered["manifest"][field] = "stale"
            maintenance._seal(altered, "audit_fingerprint")
            with self.assertRaisesRegex(ValueError, "STALE"):
                remediation.validate_identity_proposal(altered, proposal, explicit_execution=True)
        for field in ("audit_fingerprint", "candidate_fingerprint", "implementation_fingerprint"):
            altered = deepcopy(proposal)
            altered[field] = "stale"
            maintenance._seal(altered, "proposal_fingerprint")
            with self.assertRaisesRegex(ValueError, "Stale"):
                self.validate(altered)

    def test_no_auto_approval_relationship_injection_or_unsealed_edit(self):
        for field in ("approval", "publication"):
            proposal = self.proposal()
            proposal[field] = True
            maintenance._seal(proposal, "proposal_fingerprint")
            with self.assertRaisesRegex(ValueError, "contract changed"):
                self.validate(proposal)
        proposal = self.proposal()
        proposal["proposed_change"]["capability_id"] = "backend.api_development"
        maintenance._seal(proposal, "proposal_fingerprint")
        with self.assertRaisesRegex(ValueError, "contract changed"):
            self.validate(proposal)
        proposal = self.proposal()
        proposal["aliases"] = ["py"]
        with self.assertRaisesRegex(ValueError, "edited"):
            self.validate(proposal)

    def test_manual_relationship_routes_rejected(self):
        snapshot = maintenance.run_corpus_audit(corpus=fixture_corpus("BigFix", "secure coding practices"),
            explicit_execution=True, review_db_path=self.fixture.tmp / "review.sqlite")
        cid = next(r["candidate_id"] for r in snapshot["gap_rows"] if r["fix_layer"] != maintenance.IDENTITY_GAP)
        with self.assertRaisesRegex(ValueError, "identity gap"):
            remediation.prepare_identity_proposal(snapshot, cid, explicit_execution=True)

    def test_native_compound_list_and_noise_boundaries(self):
        proposal = self.proposal()
        _, registry = gaps._temporary_knowledge([proposal])
        probes = ["Proficiency in Python and SQL is expected", "Python or SQL",
            "Advanced proficiency in at least one analytical tool such as Python, SQL, Power BI, Tableau, or equivalent tools",
            "Candidates can submit a Python example with their application", "Python club picnic schedule",
            "Proficiency in programming languages such as Python, R, or Java"]
        for text in probes:
            before = resolve_requirement_text(text)
            after = resolve_requirement_text(text, registry=registry)
            self.assertEqual(after["status"], before["status"], text)
            self.assertIsNone(after["capability_id"])
        snapshot = maintenance.run_corpus_audit(corpus=fixture_corpus(probes[0], probes[2]), explicit_execution=True,
            review_db_path=self.fixture.tmp / "review.sqlite")
        cid = next(r["candidate_id"] for r in snapshot["gap_rows"] if r["concept"] == "python")
        proposal = remediation.prepare_identity_proposal(snapshot, cid, explicit_execution=True)
        report = remediation.validate_identity_proposal(snapshot, proposal, explicit_execution=True)
        self.assertEqual(report["validated_impact"]["newly_resolved"], 0)
        self.assertEqual(report["ranking_changes"], [])
        self.assertTrue(all(r["compound_provenance"] for r in report["affected_requirement_receipts"]))

    def test_unexpected_unrelated_resolution_blocks_validation(self):
        replay = remediation.replay_current_corpus
        def altered(corpus):
            result = replay(corpus)
            result["jobs"][1]["baseline_stable_analysis"]["canonical_requirements"][0]["match_label"] = "none"
            return result
        with patch.object(remediation, "replay_current_corpus", side_effect=altered):
            result = self.validate()
        self.assertEqual(result["validation_status"], "blocked")
        self.assertTrue(result["unexpected_changes"])

    def test_java_uses_generic_native_contract(self):
        snapshot = maintenance.run_corpus_audit(corpus=fixture_corpus("Java"), explicit_execution=True,
            review_db_path=self.fixture.tmp / "review.sqlite")
        cid = snapshot["gap_rows"][0]["candidate_id"]
        proposal = remediation.prepare_identity_proposal(snapshot, cid, explicit_execution=True)
        self.assertEqual(proposal["canonical_technology_id"], gaps._technology_id_for("Java"))
        self.assertEqual(proposal["aliases"], ["Java"])

    def test_thin_cli_same_service_and_json_markdown(self):
        from scripts.validate_technology_identity_proposal import main
        audit = self.fixture.tmp / "audit.json"
        output = self.fixture.tmp / "validation"
        audit.write_text(json.dumps(self.snapshot), encoding="utf-8")
        with patch.object(remediation, "validate_identity_proposal", wraps=remediation.validate_identity_proposal) as replay:
            self.assertEqual(main(["--candidate-id", self.cid, "--scope", "frozen", "--audit", str(audit),
                "--dry-run", "--output", str(output)]), 0)
            replay.assert_called_once()
        report = json.loads((output / "validation.json").read_text())
        self.assertFalse(report["publication"])
        self.assertTrue((output / "summary.md").exists())

    def test_ui_explicit_handoff_no_rerender_execution(self):
        from taxonomy_discovery.maintenance_ui import _render_identity_remediation
        action = {"candidate_id": self.cid, "requirements_affected": 1, "jobs_affected": 1}
        with patch.object(remediation, "prepare_identity_proposal", wraps=remediation.prepare_identity_proposal) as prepare, \
             patch.object(remediation, "validate_identity_proposal", wraps=remediation.validate_identity_proposal) as validate:
            # AppTest executes the same production renderer/service, with frozen native fixtures.
            def app():
                import streamlit as st
                from taxonomy_discovery.maintenance_ui import _render_identity_remediation
                _render_identity_remediation(st, st.session_state["snapshot"], st.session_state["action"], True)
            at = AppTest.from_function(app, default_timeout=40)
            at.session_state["snapshot"] = self.snapshot
            at.session_state["action"] = action
            at.run()
            prepare.assert_not_called(); validate.assert_not_called()
            at.button(key="tm_identity_inspect").click().run()
            at.button(key="tm_identity_prepare").click().run()
            self.assertEqual(list(at.exception), [])
            prepare.assert_called_once(); validate.assert_not_called()
            at.button(key="tm_identity_validate").click().run()
            self.assertEqual(list(at.exception), [])
            validate.assert_called_once()
            at.run()
            validate.assert_called_once()
            self.assertFalse(at.session_state["tm_identity_validation"]["publication"])
            self.assertFalse(any("Publish" in b.label for b in at.button))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import os
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from database.technology_registry_proposal_manager import (
    import_proposal_bundle, list_proposals, list_proposal_reviews, list_proposal_publications,
    proposal_publication_state,
)
from job_discovery.matching import analyze_job_match, current_match_versions, build_profile_evidence_context
from tailoring.jd_user_input_overrides import refresh_application_session_analysis_report
from tailoring.capability_taxonomy import get_default_taxonomy
from taxonomy_discovery.focused_verification_preview import build_focused_impact_preview
from taxonomy_discovery.technology_registry import get_default_registry, resolve_requirement_text
from tests.tqd3_publication_fixture_support import PublicationFixture


class ExplicitPublicationTests(unittest.TestCase):
    def test_end_to_end_runtime_job_match_and_session_analysis_zero_network_models(self):
        with PublicationFixture() as f:
            before_bytes = f.registry_path.read_bytes()
            versions_before = current_match_versions()
            self.assertEqual(resolve_requirement_text(f.requirement["text"])["status"], "unresolved")
            self.assertEqual(f.interpretation["outcome"], "verified_registry_relationship")
            preview = build_focused_impact_preview(f.draft, f.snapshots())
            self.assertEqual(preview["would_resolve_after"], 1)
            self.assertEqual(f.registry_path.read_bytes(), before_bytes)
            review = f.approve()
            self.assertEqual(resolve_requirement_text(f.requirement["text"])["status"], "unresolved")
            self.assertEqual(f.registry_path.read_bytes(), before_bytes)
            state = proposal_publication_state(f.proposal, review, db_path=f.proposal_db, registry_path=f.registry_path)
            self.assertEqual(state["state"], "human_approved")
            profile = {"required_skills": [f.name], "preferred_skills": [], "responsibilities": [],
                       "soft_skills": [], "tools_technologies": [], "deal_breakers": []}
            context = build_profile_evidence_context([{"id": 1, "category": "Skill", "title": "Python",
                "description": "Built Python scripts.", "skills": ["Python"], "tools": []}])
            job = {"id": 98, "content_hash": "v17-job", "description":
                "We are hiring a software engineer to maintain reliable production tooling and collaborate with the engineering team.\nRequirements\n" + f.name}
            match_before = analyze_job_match(job, context=context, versions=versions_before,
                                            jd_profile_extractor=lambda text: profile)
            report = {"jd_profile": profile, "resume_profile": context["resume_profile"], "keyword_match": {},
                      "raw_jd_text": job["description"], "raw_resume_text": context["raw_resume_text"],
                      "stable_analysis": deepcopy(match_before["snapshot"]["stable_analysis"])}
            frozen_report = deepcopy(report)
            receipt = f.publish()
            self.assertEqual(resolve_requirement_text(f.requirement["text"])["capability_id"], f.capability)
            self.assertNotEqual(current_match_versions()["match_version"], versions_before["match_version"])
            self.assertEqual(current_match_versions()["taxonomy_version"], versions_before["taxonomy_version"])
            self.assertEqual(receipt["promoted_registry_version"], get_default_registry().version)
            state = proposal_publication_state(f.proposal, review, db_path=f.proposal_db, registry_path=f.registry_path)
            self.assertEqual(state["state"], "production_active")
            def no_extraction(*args):
                raise AssertionError("Publication refresh must reuse saved JD profile")
            match_after = analyze_job_match(job, context=context, versions=current_match_versions(),
                                           jd_profile_extractor=no_extraction)
            self.assertFalse(match_after["cache_hit"])
            matched_rows = match_after["snapshot"]["stable_analysis"]["canonical_requirements"]
            self.assertTrue(any(r.get("capability_id") == f.capability for r in matched_rows))
            self.assertTrue(all(r.get("match_label") == "none" for r in matched_rows))
            session = refresh_application_session_analysis_report(report)
            session_rows = session["stable_analysis"]["canonical_requirements"]
            self.assertTrue(any(r.get("capability_id") == f.capability for r in session_rows))
            self.assertTrue(all(r.get("match_label") == "none" for r in session_rows))
            self.assertEqual(session["stable_analysis"]["technology_registry_version"], get_default_registry().version)
            self.assertEqual(report, frozen_report)
            self.assertEqual(f.real_registry.read_bytes(), f.real_registry_bytes)
            f.network_guard.assert_not_called()
            f.embedding_guard.assert_not_called()
            f.model_guard.assert_not_called()

    def test_unapproved_or_nonexplicit_execution_cannot_publish(self):
        with PublicationFixture() as f:
            baseline = f.registry_path.read_bytes()
            with self.assertRaises(ValueError):
                f.publish()
            f.approve()
            with self.assertRaises(ValueError):
                f.publish(explicit_publish=False)
            self.assertEqual(f.registry_path.read_bytes(), baseline)
            receipts = list_proposal_publications(db_path=f.proposal_db)
            self.assertTrue(all(r["status"] != "published" for r in receipts))

    def test_state_transitions_and_idempotent_explicit_publish(self):
        with PublicationFixture() as f:
            self.assertEqual(proposal_publication_state(f.proposal, {}, registry_path=f.registry_path, db_path=f.proposal_db)["state"], "draft")
            review = f.approve()
            receipt = f.publish()
            published = f.registry_path.read_bytes()
            self.assertEqual(f.publish(), receipt)
            self.assertEqual(f.registry_path.read_bytes(), published)
            self.assertEqual(len(list_proposal_publications(db_path=f.proposal_db)), 1)
            # Losing the applied mapping must not claim production_active or auto-republish.
            registry = json.loads(published)
            registry["entries"] = [e for e in registry["entries"] if e["technology_id"] != f.proposal["technology_id"]]
            f.registry_path.write_text(json.dumps(registry), encoding="utf-8")
            self.assertEqual(proposal_publication_state(f.proposal, review, registry_path=f.registry_path, db_path=f.proposal_db)["state"], "explicitly_published")
            with self.assertRaises(ValueError):
                f.publish()

    def test_changed_proposal_invalidates_approval_and_publication(self):
        with PublicationFixture() as f:
            f.approve()
            bundle = deepcopy(f.draft["proposal_bundle"])
            bundle["proposals"][0]["summary"] = "Changed researched content"
            import_proposal_bundle(bundle, db_path=f.proposal_db)
            self.assertEqual(list_proposal_reviews(db_path=f.proposal_db), [])
            with self.assertRaises(ValueError):
                f.publish()

    def test_stale_version_or_fingerprint_fails_closed(self):
        with PublicationFixture() as f:
            f.approve()
            baseline = f.registry_path.read_bytes()
            for overrides in ({"expected_source_fingerprint": "changed"}, {"expected_registry_version": "stale"}):
                with self.assertRaises(ValueError):
                    f.publish(**overrides)
            self.assertEqual(f.registry_path.read_bytes(), baseline)

    def test_taxonomy_change_requires_refresh_and_new_human_review(self):
        from types import SimpleNamespace
        with PublicationFixture() as f:
            f.approve()
            taxonomy = get_default_taxonomy()
            changed = SimpleNamespace(version=taxonomy.version + "-changed", by_id=taxonomy.by_id)
            baseline = f.registry_path.read_bytes()
            with patch("taxonomy_discovery.technology_registry.get_default_taxonomy", return_value=changed):
                with self.assertRaisesRegex(ValueError, "Taxonomy changed"):
                    f.publish()
            self.assertEqual(f.registry_path.read_bytes(), baseline)

    def test_alias_collision_prevents_writes_and_receipts(self):
        with PublicationFixture() as f:
            bundle = deepcopy(f.draft["proposal_bundle"])
            bundle["proposals"][0]["aliases"].append("RabbitMQ")
            import_proposal_bundle(bundle, db_path=f.proposal_db)
            f.proposal = list_proposals(db_path=f.proposal_db)[0]
            f.approve()
            baseline = f.registry_path.read_bytes()
            with self.assertRaises(ValueError):
                f.publish()
            self.assertEqual(f.registry_path.read_bytes(), baseline)
            self.assertEqual(list_proposal_publications(db_path=f.proposal_db), [])

    def test_conflicting_production_mapping_is_not_overwritten(self):
        with PublicationFixture() as f:
            bundle = deepcopy(f.draft["proposal_bundle"])
            bundle["proposals"][0].update(technology_id="rabbitmq", aliases=["RabbitMQ"])
            import_proposal_bundle(bundle, db_path=f.proposal_db)
            f.proposal = list_proposals(db_path=f.proposal_db)[0]
            f.approve()
            baseline = f.registry_path.read_bytes()
            with self.assertRaises(ValueError):
                f.publish()
            self.assertEqual(f.registry_path.read_bytes(), baseline)

    def test_identity_and_alias_publication_preserve_relationships(self):
        with PublicationFixture() as f:
            bundle = deepcopy(f.draft["proposal_bundle"])
            proposal = bundle["proposals"][0]
            proposal.update(proposal_classification="recognized_unmapped", proposed_capability_id=None, relationship_type=None)
            import_proposal_bundle(bundle, db_path=f.proposal_db)
            f.proposal = list_proposals(db_path=f.proposal_db)[0]
            f.approve("approve_identity")
            f.publish()
            self.assertEqual(resolve_requirement_text(f.name)["status"], "recognized_unmapped")
            # The same contract also adds aliases to an existing approved identity/mapping.
            bundle["registry_version"] = get_default_registry().version
            proposal.update(proposal_id="v17-safe-alias", technology_id="rabbitmq", label="RabbitMQ",
                            aliases=["RabbitMQ", "Fixture Rabbit Alias"])
            import_proposal_bundle(bundle, db_path=f.proposal_db)
            f.proposal = next(p for p in list_proposals(db_path=f.proposal_db) if p["proposal_id"] == "v17-safe-alias")
            f.baseline_version = get_default_registry().version
            f.approve("approve_identity")
            f.publish()
            self.assertEqual(resolve_requirement_text("Fixture Rabbit Alias")["capability_id"], "realtime.messaging_streaming")

    def test_wrong_identity_approval_and_capability_creation_cannot_publish(self):
        with PublicationFixture() as f:
            f.approve("approve_identity")
            with self.assertRaises(ValueError):
                f.publish()
            bundle = deepcopy(f.draft["proposal_bundle"])
            bundle["proposals"][0].update(proposal_classification="new_capability_candidate", proposed_capability_id=None, relationship_type=None)
            import_proposal_bundle(bundle, db_path=f.proposal_db)
            f.proposal = list_proposals(db_path=f.proposal_db)[0]
            f.approve("new_capability_needed")
            with self.assertRaises(ValueError):
                f.publish()

    def test_staging_failure_does_not_publish(self):
        with PublicationFixture() as f:
            f.approve()
            baseline = f.registry_path.read_bytes()
            with patch("database.technology_registry_proposal_manager.os.replace", side_effect=OSError("fixture write failure")):
                with self.assertRaises(OSError):
                    f.publish()
            self.assertEqual(f.registry_path.read_bytes(), baseline)
            receipts = list_proposal_publications(db_path=f.proposal_db)
            self.assertEqual(len(receipts), 1)
            self.assertEqual(receipts[0]["status"], "prepared")
            review = list_proposal_reviews(db_path=f.proposal_db)[0]
            self.assertEqual(proposal_publication_state(f.proposal, review, registry_path=f.registry_path,
                                                       db_path=f.proposal_db)["state"], "human_approved")
            self.assertEqual(list(f.tmp.glob(".tqd3-publish-*")), [])
            # The persisted intent is retryable only through another explicit click.
            self.assertEqual(f.publish()["status"], "published")

    def test_other_process_publication_invalidates_runtime_cache_without_manual_clear(self):
        with PublicationFixture() as f:
            cached = get_default_registry()
            raw = json.loads(f.registry_path.read_bytes())
            prefix, minor = raw["registry_version"].rsplit(".", 1)
            raw["registry_version"] = prefix + "." + str(int(minor) + 1)
            replacement = f.tmp / "external-publication.json"
            replacement.write_text(json.dumps(raw), encoding="utf-8")
            os.replace(replacement, f.registry_path)
            self.assertNotEqual(get_default_registry().version, cached.version)
            self.assertEqual(current_match_versions()["technology_registry_version"], raw["registry_version"])

    def test_interrupted_receipt_commit_recovers_without_second_registry_write(self):
        from database import technology_registry_proposal_manager as manager
        with PublicationFixture() as f:
            f.approve()
            original_connect = manager._connect
            commits = []
            class CommitFailure:
                def __init__(self, conn):
                    self.conn = conn
                def __getattr__(self, name):
                    return getattr(self.conn, name)
                def commit(self):
                    commits.append(1)
                    if len(commits) == 3:  # schema, intent journal, final receipt
                        raise OSError("fixture receipt commit failure")
                    self.conn.commit()
            with patch.object(manager, "_connect", side_effect=lambda *a, **k: CommitFailure(original_connect(*a, **k))):
                with self.assertRaises(OSError):
                    f.publish()
            self.assertEqual(resolve_requirement_text(f.name)["capability_id"], f.capability)
            receipt = list_proposal_publications(db_path=f.proposal_db)[0]
            self.assertEqual(receipt["status"], "prepared")
            review = list_proposal_reviews(db_path=f.proposal_db)[0]
            self.assertTrue(proposal_publication_state(f.proposal, review, registry_path=f.registry_path,
                                                      db_path=f.proposal_db)["production_active"])
            published = f.registry_path.read_bytes()
            self.assertEqual(f.publish()["status"], "published")
            self.assertEqual(f.registry_path.read_bytes(), published)


if __name__ == "__main__":
    unittest.main()

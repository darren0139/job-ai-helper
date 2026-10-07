from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from database.taxonomy_discovery_review_manager import (
    list_focused_verification_results, save_focused_verification_result,
    save_focused_verification_decision,
)
from database.technology_registry_proposal_manager import import_proposal_bundle, list_proposals, list_proposal_reviews
from tailoring.capability_taxonomy import get_default_taxonomy
from taxonomy_discovery.focused_verification_targets import build_focused_verification_target
from taxonomy_discovery.focused_verification import (
    execute_focused_verification, focused_search_target, interpret_focused_verification, build_focused_draft,
)
from taxonomy_discovery.focused_verification_preview import build_focused_impact_preview
from taxonomy_discovery.technology_registry import TechnologyRegistry, get_default_registry


def target(name="QuasarTool", capabilities=None):
    return build_focused_verification_target({"bucket": "confirmed", "candidate_id": name,
        "canonical_name": name, "taxonomy_capabilities": capabilities or []})


class FocusedVerificationPipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "review.sqlite3"
        self.authority = Path(self.tmp.name) / "authority.json"
        self.authority.write_text(json.dumps({"version": "test", "technology_domains": [
            {"technology_aliases": ["QuasarTool"], "official_domains": ["quasar.example"]}
        ]}), encoding="utf-8")
        self.calls = []

    def transport(self, endpoint, payload, headers, timeout):
        self.calls.append(deepcopy(payload))
        return {"request_id": "request-" + str(len(self.calls)), "response_time": 0.2,
                "usage": {"credits": 1}, "answer": "Untrusted provider answer",
                "results": [{"title": "QuasarTool", "url": "https://quasar.example/docs",
                             "content": "QuasarTool is a tool for Docker containers and containerisation.",
                             "authoritative": True, "extra_raw_field": [1, 2]}]}

    def execute(self, t=None, **kwargs):
        return execute_focused_verification([t or target()], selected_target_ids=[(t or target())["target_id"]],
            explicit_execution=True, db_path=self.db, api_key="fake", transport=self.transport, **kwargs)[0]

    def derive(self, t=None):
        row = self.execute(t)
        interpretation = interpret_focused_verification(row["result"], authority_registry_path=self.authority)
        return row, interpretation, build_focused_draft(row["result"], interpretation)

    def snapshots(self):
        return [{"id": 1, "discovered_job_id": 7, "taxonomy_version": get_default_taxonomy().version,
                 "stable_analysis": {"canonical_requirements": [
                     {"requirement_id": "r1", "text": "Experience with QuasarTool", "importance": "required"},
                     {"requirement_id": "r2", "text": "Docker containers", "importance": "required"},
                     {"requirement_id": "r3", "text": "UnrecognisedExample", "importance": "required"},
                 ]}}]

    def test_explicit_execution_and_selected_only(self):
        ts = [target(), target("OtherTool")]
        with self.assertRaises(ValueError):
            execute_focused_verification(ts, selected_target_ids=[ts[0]["target_id"]], transport=self.transport)
        self.assertEqual(self.calls, [])
        result = execute_focused_verification(ts, selected_target_ids=[ts[0]["target_id"]],
            explicit_execution=True, db_path=self.db, api_key="fake", transport=self.transport)
        self.assertEqual(len(result), 1)
        self.assertEqual(len(self.calls), 1)
        self.assertNotIn("OtherTool", self.calls[0]["query"])

    def test_identity_and_relationship_questions_verbatim(self):
        for t in (target(), target(capabilities=["devops.containerisation"])):
            adapted = focused_search_target(t)
            self.assertEqual(adapted["research_question"], "\n".join(t["questions"]))
            self.execute(t)
            self.assertEqual(self.calls[-1]["query"], "\n".join(t["questions"]))
            self.assertEqual(self.calls[-1]["search_depth"], "basic")

    def test_prevalidate_whole_batch_and_limit(self):
        ts = [target(), target("OtherTool")]
        ts[1]["questions"] = []
        with self.assertRaises(ValueError):
            execute_focused_verification(ts, selected_target_ids=[t["target_id"] for t in ts],
                explicit_execution=True, db_path=self.db, api_key="fake", transport=self.transport)
        with self.assertRaises(ValueError):
            execute_focused_verification([], selected_target_ids=["1", "2", "3", "4"], explicit_execution=True)
        self.assertEqual(self.calls, [])

    def test_persistence_raw_roundtrip_idempotence_reload_without_network(self):
        row = self.execute()
        raw = row["result"]["raw_provider_response"]
        self.assertEqual(raw["results"][0]["extra_raw_field"], [1, 2])
        again = save_focused_verification_result(row["result"], db_path=self.db)
        self.assertEqual(row, again)
        self.assertEqual(len(list_focused_verification_results(db_path=self.db)), 1)
        with patch("taxonomy_discovery.focused_verification.research_target_with_tavily", side_effect=AssertionError("network")):
            self.assertEqual(self.execute(), row)
        changed = deepcopy(row["result"])
        changed["raw_provider_response"]["answer"] = "overwritten"
        with self.assertRaises(ValueError):
            save_focused_verification_result(changed, db_path=self.db)
        self.assertEqual(list_focused_verification_results(db_path=self.db)[0]["result"]["raw_provider_response"], raw)

    def test_partial_batch_success_is_saved_and_retry_reuses_it(self):
        ts = [target(), target("OtherTool")]
        def failing(*args):
            if self.calls:
                raise RuntimeError("second request failed")
            return self.transport(*args)
        with self.assertRaises(RuntimeError):
            execute_focused_verification(ts, selected_target_ids=[t["target_id"] for t in ts],
                explicit_execution=True, db_path=self.db, api_key="fake", transport=failing)
        self.assertEqual(len(list_focused_verification_results(db_path=self.db)), 1)
        self.execute()
        self.assertEqual(len(self.calls), 1)

    def test_changing_display_metadata_reuses_saved_evidence(self):
        self.execute()
        t = target()
        t["source_summary"]["supporting_sources"] = 12
        self.execute(t)
        self.assertEqual(len(self.calls), 1)

    def test_deterministic_identity_and_relationship_drafts(self):
        row, interpretation, draft = self.derive()
        self.assertEqual(interpretation["outcome"], "verified_identity")
        self.assertEqual(draft["action"], "add_technology_identity")
        self.assertEqual(interpretation, interpret_focused_verification(row["result"], authority_registry_path=self.authority))
        _, relationship, draft = self.derive(target(capabilities=["devops.containerisation"]))
        self.assertEqual(relationship["outcome"], "verified_registry_relationship")
        self.assertEqual(draft["action"], "add_technology_capability_relationship")
        self.assertEqual(draft["status"], "draft")
        self.assertTrue(draft["requires_human_approval"])

    def test_ambiguous_insufficient_and_relationship_fail_closed(self):
        row = self.execute(target(capabilities=["devops.containerisation"]))
        for content, url, expected in (
            ("QuasarTool is a different product. QuasarTool is not this technology.", "https://quasar.example", "ambiguous_identity"),
            ("QuasarTool is a tool for Docker containers.", "https://untrusted.example", "insufficient_evidence"),
            ("QuasarTool", "https://quasar.example", "insufficient_evidence"),
            ("QuasarTool is a calendar tool.", "https://quasar.example", "needs_more_research"),
        ):
            result = deepcopy(row["result"])
            result["raw_provider_response"]["results"][0].update(content=content, url=url, authoritative=True)
            interpreted = interpret_focused_verification(result, authority_registry_path=self.authority)
            self.assertEqual(interpreted["outcome"], expected)
            self.assertEqual(build_focused_draft(result, interpreted)["action"], "research_more")


    def test_cpp_saved_evidence_reinterprets_without_network(self):
        cpp_target = target("C++", capabilities=["language.modern_cpp"])
        result = {
            "provider_request_id": "persisted-cpp-request",
            "target_id": cpp_target["target_id"],
            "candidate_id": cpp_target["candidate_id"],
            "target": cpp_target,
            "raw_provider_response": {
                "results": [
                    {
                        "title": "The Standard : Standard C++",
                        "url": "https://isocpp.org/std/the-standard",
                        "content": "The current ISO C++ standard is C++23.",
                    },
                    {
                        "title": "ISO C++ Standards Committee",
                        "url": "https://www.open-std.org/jtc1/sc22/wg21/",
                        "content": "ISO/IEC JTC1/SC22/WG21 is the international standardization working group for the programming language C++.",
                    },
                    {
                        "title": "ISO/IEC 14882 Programming languages C++",
                        "url": "https://www.iso.org/standard/68564.html",
                        "content": "C++ is a general purpose programming language.",
                    },
                ]
            },
        }
        with patch(
            "taxonomy_discovery.focused_verification.research_target_with_tavily",
            side_effect=AssertionError("saved evidence reinterpretation must not call network"),
        ), patch("taxonomy_discovery.focused_verification.get_default_registry",
                 return_value=TechnologyRegistry(version="unpublished-test", entries=())):
            interpretation = interpret_focused_verification(result)
        self.assertEqual(interpretation["outcome"], "verified_registry_relationship")
        self.assertEqual(interpretation["proposed_capability_id"], "language.modern_cpp")
        self.assertEqual(interpretation["relationship_evidence"]["basis"], "exact_internal_taxonomy")
        self.assertIn("C++ programming language", interpretation["safe_aliases"])
        self.assertNotIn("C++23", interpretation["safe_aliases"])
        self.assertNotIn("ISO/IEC 14882:2024", interpretation["safe_aliases"])
        draft = build_focused_draft(result, interpretation)
        self.assertEqual(draft["action"], "add_technology_capability_relationship")
        proposal = draft["proposal_bundle"]["proposals"][0]
        self.assertEqual(proposal["entry_kind"], "language")
        self.assertEqual(proposal["proposed_capability_id"], "language.modern_cpp")
        published = interpret_focused_verification(result)
        self.assertEqual(published["outcome"], "no_change")
        self.assertEqual(published["existing_registry_knowledge"]["capability_id"], "language.modern_cpp")
        self.assertEqual(build_focused_draft(result, published)["action"], "no_change")

    def test_exact_production_knowledge_remains_authoritative(self):
        row = self.execute(target("RabbitMQ"))
        result = deepcopy(row["result"])
        result["raw_provider_response"]["results"] = []
        interpreted = interpret_focused_verification(result)
        self.assertEqual(interpreted["outcome"], "no_change")
        self.assertEqual(build_focused_draft(result, interpreted)["action"], "no_change")

    def test_aliases_provider_claims_and_answers_not_trusted(self):
        row = self.execute()
        row["result"]["raw_provider_response"].update(safe_aliases=["Docker"], canonical_identity="Docker")
        interpretation = interpret_focused_verification(row["result"], authority_registry_path=self.authority)
        self.assertEqual(interpretation["safe_aliases"], ["QuasarTool"])
        self.assertEqual(interpretation["canonical_name"], "QuasarTool")

    def test_shadow_preview_before_after_without_mutation_or_score(self):
        registry_before = deepcopy(get_default_registry())
        _, _, draft = self.derive(target(capabilities=["devops.containerisation"]))
        snapshots = self.snapshots()
        snapshots_before = deepcopy(snapshots)
        preview = build_focused_impact_preview(draft, snapshots)
        self.assertTrue(preview["available"])
        self.assertEqual(preview["requirements_evaluated"], 3)
        self.assertEqual(preview["unresolved_before"], 2)
        self.assertEqual(preview["would_resolve_after"], 1)
        self.assertEqual(preview["changed_requirement_ids"], ["r1"])
        self.assertEqual(preview["rows"][0]["after"]["capability_id"], "devops.containerisation")
        self.assertEqual(preview["unchanged_requirements"], 2)
        self.assertEqual(snapshots, snapshots_before)
        self.assertEqual(get_default_registry(), registry_before)
        self.assertFalse(preview["score_changes_claimed"])

    def test_missing_snapshot_context_and_collision_fail_closed(self):
        _, _, draft = self.derive()
        for snapshots in ([], [{}], [{"taxonomy_version": get_default_taxonomy().version, "stable_analysis": {}}]):
            self.assertFalse(build_focused_impact_preview(draft, snapshots)["available"])
        collision = deepcopy(draft)
        collision["proposal_bundle"]["proposals"][0]["aliases"].append("RabbitMQ")
        self.assertFalse(build_focused_impact_preview(collision, self.snapshots())["available"])

    def test_governed_review_decision_is_local_and_not_approval(self):
        row, _, draft = self.derive()
        save_focused_verification_decision(artifact_id=row["artifact_id"], decision="send_to_review", draft=draft, db_path=self.db)
        saved = list_focused_verification_results(db_path=self.db)[0]
        self.assertEqual(saved["decision"], "send_to_review")
        self.assertEqual(saved["review_draft"], draft)
        with self.assertRaises(ValueError):
            save_focused_verification_decision(artifact_id=row["artifact_id"], decision="approve_mapping", draft=draft, db_path=self.db)
        wrong = deepcopy(draft)
        wrong["provider_request_id"] = "unrelated-request"
        with self.assertRaises(ValueError):
            save_focused_verification_decision(artifact_id=row["artifact_id"], decision="send_to_review", draft=wrong, db_path=self.db)

    def test_draft_reuses_existing_proposal_queue_without_approval(self):
        _, _, draft = self.derive(target(capabilities=["devops.containerisation"]))
        proposal_db = Path(self.tmp.name) / "proposals.sqlite3"
        import_proposal_bundle(draft["proposal_bundle"], db_path=proposal_db)
        self.assertEqual(len(list_proposals(db_path=proposal_db)), 1)
        self.assertEqual(list_proposal_reviews(db_path=proposal_db), [])

    def test_safe_alias_and_capability_research_actions(self):
        row = self.execute()
        production = get_default_registry()
        for aliases, expected in ((["OldQuasarName"], "add_safe_alias"),
                                  (["QuasarTool"], "route_to_capability_research")):
            entry = {"technology_id": "test.quasar", "label": "QuasarTool", "entry_kind": "tool",
                     "aliases": aliases, "capability_relationships": []}
            registry = TechnologyRegistry(production.version, production.entries + (entry,))
            with patch("taxonomy_discovery.focused_verification.get_default_registry", return_value=registry):
                interpreted = interpret_focused_verification(row["result"], authority_registry_path=self.authority)
                self.assertEqual(build_focused_draft(row["result"], interpreted)["action"], expected)

    def test_generation_execution_interpretation_preview_do_not_mutate_production_files(self):
        paths = [Path("taxonomy/technology_registry_v1.json"), Path("taxonomy/capability_taxonomy_v1.json")]
        before = [p.read_bytes() for p in paths]
        _, _, draft = self.derive(target(capabilities=["devops.containerisation"]))
        build_focused_impact_preview(draft, self.snapshots())
        self.assertEqual([p.read_bytes() for p in paths], before)
        self.assertFalse(draft["scoring_influence"])


if __name__ == "__main__":
    unittest.main()

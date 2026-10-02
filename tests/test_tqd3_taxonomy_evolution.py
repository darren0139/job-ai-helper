"""H.0 machinery exercised only with synthetic gaps, fake research and temp stores."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import sys
import unittest
from unittest.mock import Mock, patch

from database.taxonomy_discovery_review_manager import (save_taxonomy_evolution_proposal,
    list_taxonomy_evolution_proposals, save_taxonomy_evolution_review)
from tailoring.capability_taxonomy import TAXONOMY_PATH, get_default_taxonomy, temporary_taxonomy_scope, classify_requirement
from taxonomy_discovery import taxonomy_evolution as evolution
from taxonomy_discovery.taxonomy_gaps import GAP_VERSION
from taxonomy_discovery.regression_corpus import build_regression_corpus
from tests.test_tqd3_regression_corpus import frozen_snapshot
from tests.tqd3_publication_fixture_support import PublicationFixture


def gap(text="crystalline computing protocols", route="capability_gap"):
    return {"gap_id":"synthetic-gap","normalized_cluster":text,"examples":[text],"occurrence_count":2,"job_count":1,
        "importance_distribution":{"required":2},"technology_terms":[],"retrieval_suggestions":[],
        "provenance":[{"job_id":4,"snapshot_id":1,"requirement_id":"synthetic-r","job_content_hash":"same-hash",
            "observed_versions":{"scoring_version":"old-scorer","taxonomy_version":"old-taxonomy","technology_registry_version":"old-registry"}}],
        "taxonomy_version":"observed-taxonomy","registry_version":"observed-registry",
        "recommended_research_route":route,"research_input_only":True}


def candidate(text="crystalline computing protocols", route="capability_gap"):
    return evolution.gap_candidates({"gap_version":GAP_VERSION,"observations":[gap(text,route)]})[0]


def draft(f, text="crystalline computing protocols", capability_id="test.crystalline_computing"):
    c=candidate(text)
    target=evolution.research_target(c,domain_hypothesis="distributed_systems")
    rules=f.tmp/"taxonomy_authority.json"
    rules.write_text(json.dumps({"version":"synthetic-only","technology_domains":[
        {"technology_aliases":[text],"official_domains":["fixture.example"]}]}),encoding="utf-8")
    transport=Mock(return_value={"request_id":"synthetic-request","results":[{"url":"https://fixture.example/definition",
        "content":text+" has distinct computing protocol responsibilities and observable evidence.","authoritative":True}]})
    research=evolution.research_with_transport(target,transport=transport,explicit_execution=True,authority_registry_path=rules)
    return evolution.draft_proposal(c,research,capability_id=capability_id,label=text,domain="distributed_systems",
        definition="Synthetic capability used only in tests.",match_concepts=[text],aliases=[],
        does_not_prove=["Mention of a protocol without demonstrated implementation"],
        evidence_expectations={"policy_references":["existing deterministic evidence tiers"],
            "evidence_tiers":[{"label":"direct","all_groups":[[text],["built","implemented"]],"reason":"explicit_application","concepts":[text]}]}),rules


class EvolutionTests(unittest.TestCase):
    def test_provenance_versions_and_routing(self):
        with PublicationFixture():
            c=candidate()
            self.assertEqual(c["candidate_route"],"possible_new_capability")
            source=gap()
            for key,value in source.items():
                self.assertEqual(c[key],value)
            self.assertEqual(c["observed_scoring_versions"],["old-scorer"])
            self.assertEqual(c,candidate())
            cases=(("UnknownTool", "technology_identity","technology_identity"),
                ("Node.js","technology_relationship","technology_relationship"),
                ("Bachelor degree in computing","capability_gap","administrative_or_non_capability"),
                ("5 years of experience","capability_gap","existing_capability_resolver_issue"),
                ("passionate and motivated","capability_gap","ambiguous_or_noise"),
                ("comfortable attending meetings","capability_gap","insufficient_signal"),
                ("C++ programming","capability_gap","existing_capability_resolver_issue"))
            for text,original,expected in cases:
                self.assertEqual(candidate(text,original)["candidate_route"],expected,text)

    def test_overlap_diagnostic_and_no_automatic_creation(self):
        with PublicationFixture():
            c=candidate("C++ programming")
            self.assertTrue(c["overlap"]["exact_matches"])
            self.assertTrue(c["overlap"]["lexical_retrieval"])
            self.assertTrue(c["overlap"]["diagnostic_only"])
            with self.assertRaises(ValueError):
                evolution.research_target(c)

    def test_research_explicit_fake_only_raw_preserved_and_untrusted_label(self):
        with PublicationFixture() as f:
            target=evolution.research_target(candidate())
            fake=Mock(return_value={"request_id":"fake","results":[{"url":"https://unknown.example","content":"definition","authoritative":True}]})
            with self.assertRaises(ValueError):
                evolution.research_with_transport(target,transport=fake)
            fake.assert_not_called()
            result=evolution.research_with_transport(target,transport=fake,explicit_execution=True)
            self.assertEqual(result["sources"][0]["classification"]["authority"],"unclassified")
            self.assertTrue(result["raw_provider_evidence"]["results"][0]["authoritative"])
            self.assertFalse(result["approval"])
            f.network_guard.assert_not_called(); f.model_guard.assert_not_called()

    def test_fingerprint_all_material_fields_and_proposal_only(self):
        with PublicationFixture() as f:
            p,_=draft(f)
            self.assertEqual(p["proposal_fingerprint"],evolution.proposal_fingerprint(deepcopy(p)))
            for key in ("taxonomy_base_version","proposed_capability_id","domain","parent","definition","positive_match_concepts", "aliases",
                        "does_not_prove","evidence_expectations","source_gap_ids","source_provenance","research_evidence","overlap"):
                changed=deepcopy(p); changed[key]={"changed":True}
                self.assertNotEqual(evolution.proposal_fingerprint(changed),p["proposal_fingerprint"],key)
            self.assertEqual(p["proposal_status"],"proposal_only")
            self.assertIsNone(classify_requirement({"text":"crystalline computing protocols"}))

    def test_overlay_isolated_schema_duplicate_domain_parent_and_bytes(self):
        with PublicationFixture() as f:
            original=TAXONOMY_PATH.read_bytes(); base=get_default_taxonomy()
            p,_=draft(f)
            overlay=evolution.temporary_overlay([p])
            self.assertIn("+proposal-",overlay.version)
            self.assertEqual(overlay,evolution.temporary_overlay([p]))
            self.assertNotIn(p["proposed_capability_id"],base.by_id())
            with temporary_taxonomy_scope(overlay):
                self.assertEqual(classify_requirement({"text":"crystalline computing protocols"}),p["proposed_capability_id"])
                with ThreadPoolExecutor(max_workers=1) as executor:
                    self.assertEqual(executor.submit(lambda:get_default_taxonomy().version).result(),base.version)
            self.assertIs(get_default_taxonomy(),base)
            for key,value in (("proposed_capability_id",base.capabilities[0]["capability_id"]),("domain","unknown"),
                ("parent","missing.parent"),("positive_match_concepts",[]),("evidence_expectations",{"policy_references":["fixture"],"evidence_tiers":[{"label":"direct"}]})):
                bad=deepcopy(p); bad[key]=value; bad["proposal_fingerprint"]=evolution.proposal_fingerprint(bad)
                with self.assertRaises(ValueError,msg=key):
                    evolution.temporary_overlay([bad])
            with self.assertRaises(ValueError):
                evolution.temporary_overlay([p,p])
            self.assertEqual(TAXONOMY_PATH.read_bytes(),original)
            self.assertEqual(f.real_registry.read_bytes(),f.real_registry_bytes)

    def test_regression_overlay_changes_reviewonly_attribution_and_immutability(self):
        with PublicationFixture() as f:
            p,_=draft(f)
            corpus=build_regression_corpus([frozen_snapshot("crystalline computing protocols")])
            original=deepcopy(corpus); base=get_default_taxonomy()
            result=evolution.temporary_regression(corpus,[p])
            self.assertEqual(corpus,original)
            self.assertIs(get_default_taxonomy(),base)
            self.assertEqual(result["classification_counts"],{"requires_review":1})
            change=result["jobs"][0]["requirement_changes"][0]
            self.assertTrue(change["newly_resolved"])
            self.assertEqual(change["responsible_proposal_ids"],[p["proposal_id"]])
            self.assertEqual(result["affected_jobs"],[4])
            self.assertTrue(result["review_only"])
            f.network_guard.assert_not_called(); f.embedding_guard.assert_not_called(); f.model_guard.assert_not_called()

    def test_tranche_interactions_visible_and_duplicate_credit_not_hidden(self):
        with PublicationFixture() as f:
            p,_=draft(f)
            other,_=draft(f,"holographic computing lattices","test.holographic_computing")
            corpus=build_regression_corpus([frozen_snapshot("crystalline computing protocols")])
            stable=corpus["jobs"][0]["baseline_stable_analysis"]
            stable["canonical_requirements"].append(deepcopy(stable["canonical_requirements"][0]))
            result=evolution.temporary_regression(corpus,[p,other])
            self.assertEqual(result["single_or_tranche"],"tranche")
            self.assertEqual(result["classification_counts"],{"hard_regression/invariant_violation":1})
            self.assertTrue(result["jobs"][0]["duplicate_credit_violations"])
            self.assertTrue(result["jobs"][0]["requirement_changes"][0]["interaction_review_required"])

    def test_score_increase_stays_review_only(self):
        with PublicationFixture() as f:
            p,_=draft(f)
            corpus=build_regression_corpus([frozen_snapshot("crystalline computing protocols")])
            stable=deepcopy(corpus["jobs"][0]["baseline_stable_analysis"])
            stable["deterministic_alignment_score"] += 5
            with patch("taxonomy_discovery.regression_corpus._default_stable_builder",return_value=stable):
                report=evolution.temporary_regression(corpus,[p])
            self.assertEqual(report["jobs"][0]["classification"],"requires_review")
            self.assertEqual(report["jobs"][0]["job_score_deltas"]["deterministic_alignment_score"],5)

    def test_edited_candidate_target_evidence_fails_closed(self):
        with PublicationFixture() as f:
            edited=candidate(); edited["occurrence_count"] += 1
            with self.assertRaises(ValueError):
                evolution.research_target(edited)
            target=evolution.research_target(candidate()); target["questions"].append("edited")
            provider=Mock()
            with self.assertRaises(ValueError):
                evolution.research_with_transport(target,transport=provider,explicit_execution=True)
            provider.assert_not_called()

    def test_one_tranche_blocker_zero_writes(self):
        with PublicationFixture() as f:
            p,rules=draft(f)
            other,_=draft(f,"holographic computing lattices","test.holographic_computing")
            corpus=build_regression_corpus([frozen_snapshot("crystalline computing protocols")])
            report=evolution.temporary_regression(corpus,[p,other])
            decision={"decision":"approve_for_publication","reviewer":"human","proposal_fingerprint":p["proposal_fingerprint"],"regression_fingerprint":report["regression_fingerprint"]}
            original=TAXONOMY_PATH.read_bytes()
            result=evolution.publication_preflight([p,other],{p["proposal_id"]:decision},report,corpus=corpus,authority_registry_path=rules)
            self.assertFalse(result["eligible_for_future_publication"])
            self.assertEqual(result["production_writes"],0)
            self.assertEqual(TAXONOMY_PATH.read_bytes(),original)

    def test_local_persistence_review_approval_separate_and_preflight(self):
        with PublicationFixture() as f:
            p,rules= draft(f)
            original=TAXONOMY_PATH.read_bytes()
            save_taxonomy_evolution_proposal(p,db_path=f.review_db)
            first=list_taxonomy_evolution_proposals(db_path=f.review_db)
            self.assertEqual(first[0]["review"]["decision"],"undecided")
            self.assertEqual(first[0]["proposal"],p)
            corpus=build_regression_corpus([frozen_snapshot("crystalline computing protocols")])
            regression=evolution.temporary_regression(corpus,[p])
            blocked=evolution.publication_preflight([p],{},regression,corpus=corpus,authority_registry_path=rules)
            self.assertFalse(blocked["eligible_for_future_publication"])
            decision=save_taxonomy_evolution_review(p["proposal_id"],proposal_fingerprint=p["proposal_fingerprint"],
                decision="approve_for_publication",reviewer="fixture human",regression=regression,db_path=f.review_db)
            preflight=evolution.publication_preflight([p],{p["proposal_id"]:decision},regression,corpus=corpus,authority_registry_path=rules)
            self.assertTrue(preflight["eligible_for_future_publication"],preflight)
            self.assertFalse(preflight["publication_available"])
            self.assertEqual(preflight["production_writes"],0)
            self.assertEqual(TAXONOMY_PATH.read_bytes(),original)
            self.assertFalse(list_taxonomy_evolution_proposals(db_path=f.review_db)[0]["review"]["publication"])
            with self.assertRaises(ValueError):
                save_taxonomy_evolution_review(p["proposal_id"],proposal_fingerprint="stale",decision="approve_for_publication",reviewer="human",db_path=f.review_db)

    def test_preflight_failclosed_stale_regression_sources_tranche(self):
        with PublicationFixture() as f:
            p,rules=draft(f)
            corpus=build_regression_corpus([frozen_snapshot("crystalline computing protocols")])
            regression=evolution.temporary_regression(corpus,[p])
            decision={"decision":"approve_for_publication","reviewer":"human","proposal_fingerprint":p["proposal_fingerprint"],"regression_fingerprint":regression["regression_fingerprint"]}
            stale=deepcopy(regression); stale["current_versions"]={}
            result=evolution.publication_preflight([p],{p["proposal_id"]:decision},stale,corpus=corpus)
            self.assertFalse(result["eligible_for_future_publication"])
            self.assertEqual(result["production_writes"],0)
            missing=deepcopy(corpus); missing["jobs"][0]["replay_available"]=False
            missing["jobs"][0]["replay_blockers"]=["missing history"]
            report=evolution.temporary_regression(missing,[p])
            self.assertFalse(report["jobs"][0]["available"])
            self.assertFalse(evolution.publication_preflight([p],{},report,corpus=missing)["eligible_for_future_publication"])

    def test_ui_render_no_research_write_or_approval(self):
        from tests.test_tqd3_publication_ui import FakeStreamlit
        from taxonomy_discovery.taxonomy_evolution_ui import render_taxonomy_evolution
        fake=FakeStreamlit(); fake.file_uploader=lambda *a,**k:None
        with patch.dict(sys.modules,{"streamlit":fake}), patch("database.taxonomy_discovery_review_manager.list_taxonomy_evolution_proposals",return_value=[]), \
            patch("database.taxonomy_discovery_review_manager.save_taxonomy_evolution_proposal") as save, \
            patch("database.taxonomy_discovery_review_manager.save_taxonomy_evolution_review") as decide, \
            patch.object(evolution,"research_with_transport") as research:
            render_taxonomy_evolution()
            save.assert_not_called(); decide.assert_not_called(); research.assert_not_called()
        self.assertFalse(any("Publish" in label for label,_ in fake.buttons))


if __name__ == "__main__":
    unittest.main()

"""H.1.2: synthetic frozen job 566, native replay and isolated review receipts."""
from copy import deepcopy
import unittest
from unittest.mock import patch, Mock

from tests.test_tqd3_h1_1 import REST, local_result
from tests.test_tqd3_taxonomy_evolution import candidate
from tests.test_tqd3_regression_corpus import frozen_snapshot
from tests.tqd3_publication_fixture_support import PublicationFixture
from tailoring.capability_taxonomy import classify_requirement, temporary_taxonomy_scope, TAXONOMY_PATH
from taxonomy_discovery.resolver_improvement import resolver_overlay
from taxonomy_discovery import governed_research as h1
from taxonomy_discovery.regression_corpus import build_regression_corpus
from taxonomy_discovery.corpus_expansion import fingerprint
from job_discovery.matching import _default_stable_builder, build_profile_evidence_context
from database.taxonomy_discovery_review_manager import (save_governed_research_draft,
    save_governed_research_review, save_governed_temporary_impact, list_governed_research_results)

AWS = "Hands-on experience with Amazon Web Services (EC2, Cognito, S3, DynamoDB, etc.)"
TARGET = "backend.api_development"


def fixture(f):
    snapshot = frozen_snapshot(REST)
    snapshot["discovered_job_id"] = 566
    snapshot["jd_profile"] = {"required_skills":[REST, AWS]}
    snapshot["raw_jd_text"] = "Requirements\n"+REST+"\n"+AWS
    snapshot["stable_analysis"] = _default_stable_builder(raw_jd_text=snapshot["raw_jd_text"],
        jd_profile=snapshot["jd_profile"], context=build_profile_evidence_context(snapshot["evidence_snapshot"]))
    corpus = build_regression_corpus([snapshot])
    # Native canonicalization splits the comma list; retain that contract.
    intended = next(r for r in corpus["jobs"][0]["requirements"] if r["requirement_text"] == "Knowledge of web services")
    c = candidate(REST)
    c["provenance"][0].update(job_id=566,requirement_id=intended["requirement_id"])
    c["candidate_fingerprint"]=fingerprint({k:v for k,v in c.items() if k not in {"candidate_id","candidate_fingerprint"}})
    c["candidate_id"]="tqd3taxgap_"+c["candidate_fingerprint"][:24]
    with patch("tests.test_tqd3_h1_1.candidate", return_value=c):
        result = local_result(f)
    draft = h1.create_draft(result,explicit_creation=True)
    return result,draft,corpus


class PhraseTests(unittest.TestCase):
    def test_native_singular_guarded_plural_boundaries_and_product_context(self):
        with PublicationFixture() as f:
            result,draft,corpus=fixture(f)
            taxonomy=TAXONOMY_PATH.read_bytes()
            self.assertEqual(draft,h1.create_draft(result,explicit_creation=True))
            self.assertEqual(draft["status"],"proposal_only")
            self.assertTrue(draft["requires_human_approval"])
            self.assertEqual(classify_requirement({"text":"Develop web service"}),TARGET)
            self.assertNotEqual(classify_requirement({"text":REST}),TARGET)
            with temporary_taxonomy_scope(resolver_overlay(draft)):
                for text in (REST,"Experience developing web services and REST APIs",
                             "Amazon Web Services; develop web services and REST APIs"):
                    self.assertEqual(classify_requirement({"text":text}),TARGET,text)
                for text in (AWS,"Experience with Amazon Web Services","Experience with web servicesx"):
                    self.assertNotEqual(classify_requirement({"text":text}),TARGET,text)
                self.assertNotEqual(classify_requirement({"text":AWS,"atomic_focus":"web services"}),TARGET)
                # Existing governed technology vocabulary, not a sentence-specific AWS exception.
                from taxonomy_discovery.technology_registry import TechnologyRegistry, get_default_registry, temporary_registry_scope
                base=get_default_registry()
                entity={"technology_id":"test.hosted_web_services","aliases":["Acme Web Services"],
                    "canonical_name":"Acme Web Services","entry_kind":"technology","capability_relationships":[]}
                with temporary_registry_scope(TechnologyRegistry(base.version,base.entries+(entity,))):
                    self.assertNotEqual(classify_requirement({"text":"Use Acme Web Services"}),TARGET)
            self.assertEqual(TAXONOMY_PATH.read_bytes(),taxonomy)
            self.assertEqual(f.real_registry.read_bytes(),f.real_registry_bytes)
            self.assertNotEqual(classify_requirement({"text":REST}),TARGET)
            f.network_guard.assert_not_called(); f.model_guard.assert_not_called()

    def test_guard_fingerprinted_and_unguarded_legacy_draft_rejected(self):
        with PublicationFixture() as f:
            _,draft,_=fixture(f)
            changed=deepcopy(draft)
            changed["proposed_resolver_change"].pop("product_context_guard")
            self.assertNotEqual(fingerprint(changed),fingerprint(draft))
            with self.assertRaises(ValueError): resolver_overlay(changed)
            changed.pop("draft_fingerprint"); changed.pop("resolver_draft_id")
            changed["draft_fingerprint"]=fingerprint(changed)
            changed["resolver_draft_id"]="tqd3resolver_"+changed["draft_fingerprint"][:24]
            with self.assertRaisesRegex(ValueError,"guards"): resolver_overlay(changed)

    def test_job_566_native_replay_one_intended_change_no_collateral(self):
        with PublicationFixture() as f:
            _,draft,corpus=fixture(f)
            before=deepcopy(corpus)
            with patch.object(h1,"tavily_transport",Mock(side_effect=AssertionError("No Tavily"))):
                report=h1.temporary_impact(corpus,draft)
            self.assertEqual(report["newly_resolved_count"],1)
            self.assertEqual(report["unexpectedly_changed_requirements"],[])
            self.assertEqual(report["publication_blockers"],[])
            self.assertEqual(len(report["intended_changed_requirements"]),1)
            self.assertEqual(report["affected_jobs"],[566])
            self.assertEqual(report["jobs"][0]["duplicate_credit_violations"],[])
            changes=report["jobs"][0]["requirement_changes"]
            self.assertEqual(len(changes),1)
            self.assertEqual(changes[0]["before"]["requirement_text"],"Knowledge of web services")
            self.assertEqual(changes[0]["after"]["capability_id"],TARGET)
            self.assertEqual(corpus,before)
            f.network_guard.assert_not_called(); f.model_guard.assert_not_called()


class ApprovalTests(unittest.TestCase):
    def test_rejected_legacy_receipt_preserved_when_explicitly_replaced(self):
        import sqlite3
        import json
        from contextlib import closing
        with PublicationFixture() as f:
            result,draft,_=fixture(f)
            db=f.tmp/"h11.sqlite"
            old=deepcopy(draft)
            old["resolver_draft_version"]="tqd3-resolver-improvement-h1.1-v1"
            old["proposed_resolver_change"].pop("product_context_guard")
            old["proposed_resolver_change"].pop("phrase_boundary")
            old["draft_fingerprint"]=fingerprint({k:v for k,v in old.items() if k not in {"draft_fingerprint","resolver_draft_id"}})
            old["resolver_draft_id"]="tqd3resolver_"+old["draft_fingerprint"][:24]
            with closing(sqlite3.connect(db)) as conn:
                conn.execute("UPDATE governed_research_results SET draft_json=? WHERE result_id=?",(json.dumps(old),result["research_result_id"]))
                conn.commit()
            with self.assertRaises(ValueError): save_governed_research_draft(result,draft,db_path=db)
            save_governed_research_review(result["research_result_id"],result_fingerprint=result["result_fingerprint"],
                decision="reject",reviewer="TEST",notes="AWS collateral false positive",db_path=db)
            save_governed_research_draft(result,draft,db_path=db)
            saved=list_governed_research_results(db_path=db)[0]
            self.assertEqual(saved["draft"],draft)
            self.assertEqual(saved["review"]["decision"],"undecided")
            with closing(sqlite3.connect(db)) as conn:
                archived=conn.execute("SELECT draft_json,review_json FROM governed_resolver_draft_history").fetchone()
            self.assertEqual(json.loads(archived[0]),old)
            self.assertEqual(json.loads(archived[1])["decision"],"reject")

    def test_clean_explicit_review_and_missing_stale_collateral_duplicate_blockers(self):
        with PublicationFixture() as f:
            result,draft,corpus=fixture(f)
            db=f.tmp/"h11.sqlite"
            save_governed_research_draft(result,draft,db_path=db)
            report=h1.temporary_impact(corpus,draft)
            args=dict(result_fingerprint=result["result_fingerprint"],decision="approve_for_publication",reviewer="TEST",db_path=db)
            rid=result["research_result_id"]
            with self.assertRaises(ValueError): save_governed_research_review(rid,regression=report,**args)
            save_governed_temporary_impact(rid,report,db_path=db)
            self.assertEqual(list_governed_research_results(db_path=db)[0]["review"]["decision"],"undecided")
            self.assertFalse(save_governed_research_review(rid,regression=report,**args)["publication"])
            for field in ("unexpected","duplicate","missing_duplicates","stale_versions","stale_knowledge","stale_draft","missing_identity","missing_changes","edited"):
                bad=deepcopy(report)
                if field=="unexpected": bad["unexpectedly_changed_requirements"]=[{"requirement_id":"AWS"}]
                elif field=="duplicate": bad["jobs"][0]["duplicate_credit_violations"]=["duplicate"]
                elif field=="missing_duplicates": bad["jobs"][0].pop("duplicate_credit_violations")
                elif field=="stale_versions": bad["current_versions"]={}
                elif field=="stale_knowledge": bad["knowledge_fingerprint"]="stale"
                elif field=="stale_draft": bad["draft_fingerprint"]="stale"
                elif field=="missing_identity": bad.pop("temporary_resolver_identity")
                elif field=="missing_changes": bad.pop("unexpectedly_changed_requirements")
                if field!="edited": bad["regression_fingerprint"]=fingerprint({k:v for k,v in bad.items() if k!="regression_fingerprint"})
                else: bad["affected_jobs"]=[]
                if field not in {"stale_draft","edited"}: save_governed_temporary_impact(rid,bad,db_path=db)
                with self.subTest(field=field),self.assertRaises(ValueError):
                    save_governed_research_review(rid,regression=bad,**args)
            # A once-clean report cannot supersede the most recent unsafe preview.
            with self.assertRaises(ValueError): save_governed_research_review(rid,regression=report,**args)

"""H.1 focused tests: synthetic candidates, fake transports, temporary stores only."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3
import sys
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

from taxonomy_discovery import governed_research as h1
from taxonomy_discovery.corpus_expansion import fingerprint
from taxonomy_discovery.taxonomy_gaps import aggregate_corpus_gaps, GAP_VERSION
from taxonomy_discovery.regression_corpus import build_regression_corpus
from taxonomy_discovery.technology_registry import get_default_registry, resolve_requirement_text, temporary_registry_scope
from database.taxonomy_discovery_review_manager import (list_governed_research_results, save_governed_research_result, save_broad_mining_candidate_review,
    save_governed_research_review, save_governed_research_draft, list_broad_mining_candidate_reviews)
from tests.test_tqd3_taxonomy_evolution import candidate, draft as capability_draft
from tests.test_tqd3_regression_corpus import frozen_snapshot
from tests.test_tqd3_taxonomy_gaps import gap_corpus
from tests.test_tqd3_publication_ui import FakeStreamlit
from tests.tqd3_publication_fixture_support import PublicationFixture


def rules(f, names):
    path = f.tmp/"h1_authority.json"
    path.write_text(json.dumps({"version":"test-only", "technology_domains":[
        {"technology_aliases":[n], "official_domains":["fixture.example"]} for n in names]}))
    return path


def fake_raw(name="ZetaNovelTool", content=None, request_id="h1-fake"):
    return {"request_id":request_id, "results":[{"url":"https://fixture.example/docs", "title":name,
        "content":content or f"{name} is a concrete software engineering tool.", "authoritative":True, "stars":999999}]}


def execute(f, c=None, raw=None, **kwargs):
    c = c or candidate("ZetaNovelTool")
    p = h1.research_plan([c], selected_candidate_ids=[c["candidate_id"]])
    receipt = h1.execute_plan(p,[c],explicit_execution=True, transport=Mock(return_value=raw or fake_raw()),
        db_path=f.tmp/"h1.sqlite", authority_registry_path=rules(f,[p["targets"][0]["subject"]]), **kwargs)
    if receipt["failures"]:
        raise AssertionError(receipt["failures"])
    return receipt["results"][0]


class PlanningTests(unittest.TestCase):
    def test_prepare_native_equivalence_and_cli_contracts(self):
        with PublicationFixture() as f:
            corpus = gap_corpus()
            with patch.object(h1, "tavily_transport", side_effect=AssertionError("no research")):
                prepared = h1.prepare_gap_review(corpus=corpus)
            self.assertEqual(prepared["gaps"],aggregate_corpus_gaps(corpus))
            from scripts.tqd3_regression_corpus import main
            gaps, report, csv = f.tmp/"gaps.json", f.tmp/"report.json", f.tmp/"report.csv"
            gaps.write_text(json.dumps(prepared["gaps"]))
            self.assertEqual(main(["taxonomy-candidates","--gaps",str(gaps),"--output",str(report),"--csv",str(csv)]),0)
            self.assertEqual(json.loads(report.read_text()), prepared["report"])
            self.assertEqual(csv.read_text().replace("\r\n","\n"),prepared["csv"].replace("\r\n","\n"))
            self.assertEqual(prepared["corpus"],corpus)
            f.network_guard.assert_not_called(); f.model_guard.assert_not_called(); f.embedding_guard.assert_not_called()

    def test_prepare_saved_export_and_gap_upload(self):
        with PublicationFixture():
            corpus = gap_corpus()
            with patch("taxonomy_discovery.regression_corpus.export_saved_corpus",return_value=corpus) as export:
                p = h1.prepare_gap_review(db_path="test-path")
            export.assert_called_once_with(db_path="test-path")
            manual = h1.prepare_gap_review(gaps=p["gaps"])
            self.assertEqual(manual["report"],p["report"])
            self.assertIsNone(manual["corpus"])

    def test_plan_deterministic_full_provenance_no_mutation(self):
        with PublicationFixture() as f:
            c = candidate("ZetaNovelTool")
            before = deepcopy(c)
            p = h1.research_plan([c],selected_candidate_ids=[c["candidate_id"]])
            self.assertEqual(p,h1.research_plan([c],selected_candidate_ids=[c["candidate_id"]]))
            self.assertEqual(p["plan_fingerprint"],fingerprint({k:v for k,v in p.items() if k!="plan_fingerprint"}))
            self.assertEqual(p["targets"][0]["candidate"],c)
            self.assertEqual(c,before)
            self.assertEqual(p["queries_per_candidate"],1)
            self.assertFalse((f.tmp/"h1.sqlite").exists())
            f.network_guard.assert_not_called(); f.model_guard.assert_not_called()

    def test_selection_limit_and_ineligible_routes(self):
        with PublicationFixture():
            cs = [candidate(name) for name in ("ZetaNovelTool","AnotherNovelTool","ThirdNovelTool","FourthNovelTool")]
            for selected in ([],["missing"],[c["candidate_id"] for c in cs]):
                with self.assertRaises(ValueError):
                    h1.research_plan(cs,selected_candidate_ids=selected)
            for text in ("only shortlisted candidates will be notified","passionate and motivated","comfortable attending meetings"):
                c = candidate(text)
                with self.assertRaises(ValueError):
                    h1.research_plan([c],selected_candidate_ids=[c["candidate_id"]])

    def test_known_entity_uses_registry_canonical_label_not_incidental_alias(self):
        with PublicationFixture():
            c=candidate("Node JS")
            p=h1.research_plan([c],selected_candidate_ids=[c["candidate_id"]])
            self.assertEqual(p["targets"][0]["subject"],get_default_registry().by_id()["node.js"]["label"])

    def test_stale_candidate_current_selection_and_versions_no_spend(self):
        with PublicationFixture() as f:
            c = candidate("ZetaNovelTool")
            p = h1.research_plan([c],selected_candidate_ids=[c["candidate_id"]])
            fake = Mock(return_value=fake_raw())
            modified = deepcopy(c); modified["examples"].append("changed")
            r = h1.execute_plan(p,[modified],explicit_execution=True,transport=fake,db_path=f.tmp/"h1.sqlite")
            self.assertTrue(r["failures"])
            for key in ("taxonomy_version","technology_registry_version"):
                versions = deepcopy(p["current_versions"]); versions[key]+="-changed"
                with patch.object(h1,"current_match_versions",return_value=versions):
                    r = h1.execute_plan(p,[c],explicit_execution=True,transport=fake,db_path=f.tmp/"h1.sqlite")
                self.assertTrue(r["failures"])
            fake.assert_not_called()


class ExecutionTests(unittest.TestCase):
    def test_explicit_followup_round_new_request_then_reuses_that_round(self):
        with PublicationFixture() as f:
            result=execute(f); c=result["candidate"]
            p=h1.research_plan([c],selected_candidate_ids=[c["candidate_id"]],research_round=1)
            self.assertNotEqual(p["plan_fingerprint"],result["research_plan_fingerprint"])
            fake=Mock(return_value=fake_raw(request_id="followup-only-fake"))
            opts={"explicit_execution":True,"transport":fake,"db_path":f.tmp/"h1.sqlite","authority_registry_path":f.tmp/"h1_authority.json"}
            first=h1.execute_plan(p,[c],**opts)
            second=h1.execute_plan(p,[c],**opts)
            self.assertEqual(first,second); fake.assert_called_once()
            self.assertEqual(len(list_governed_research_results(db_path=f.tmp/"h1.sqlite")),2)

    def test_explicit_selected_only_and_raw_roundtrip(self):
        with PublicationFixture() as f:
            cs = [candidate("ZetaNovelTool"), candidate("AnotherNovelTool")]
            p = h1.research_plan(cs,selected_candidate_ids=[cs[0]["candidate_id"]])
            fake = Mock(return_value=fake_raw())
            with self.assertRaises(ValueError):
                h1.execute_plan(p,cs,transport=fake,db_path=f.tmp/"h1.sqlite")
            fake.assert_not_called()
            r = h1.execute_plan(p,cs,explicit_execution=True,transport=fake,db_path=f.tmp/"h1.sqlite")
            self.assertFalse(r["failures"])
            fake.assert_called_once()
            saved = list_governed_research_results(db_path=f.tmp/"h1.sqlite")
            self.assertEqual(saved[0]["result"],r["results"][0])
            self.assertEqual(saved[0]["result"]["research"]["raw_provider_evidence"],fake_raw())
            self.assertFalse(saved[0]["result"]["approval"])
            self.assertEqual(saved[0]["review"]["decision"],"undecided")
            self.assertIsNone(saved[0]["draft"])

    def test_idempotent_reload_and_missing_read_does_not_create_store(self):
        with PublicationFixture() as f:
            path = f.tmp/"h1.sqlite"
            self.assertEqual(list_governed_research_results(db_path=path),[])
            self.assertFalse(path.exists())
            result = execute(f)
            self.assertEqual(save_governed_research_result(result,db_path=path), result)
            c = result["candidate"]
            fake = Mock(side_effect=AssertionError("must reuse"))
            p = h1.research_plan([c],selected_candidate_ids=[c["candidate_id"]])
            r = h1.execute_plan(p,[c],explicit_execution=True,transport=fake,db_path=path,authority_registry_path=f.tmp/"h1_authority.json")
            self.assertEqual(r["results"],[result]); fake.assert_not_called()
            self.assertEqual(len(list_governed_research_results(db_path=path)),1)

    def test_failure_isolation_retry_bound_and_resume(self):
        with PublicationFixture() as f:
            cs = [candidate(n) for n in ("ZetaNovelTool","AnotherNovelTool","ThirdNovelTool")]
            p = h1.research_plan(cs,selected_candidate_ids=[c["candidate_id"] for c in cs])
            failed = p["targets"][1]["candidate"]["candidate_id"]
            calls=[]
            def fake(t):
                cid=t["candidate"]["candidate_id"]; calls.append(cid)
                if cid==failed:
                    raise TimeoutError("fake timeout")
                return fake_raw(t["subject"],request_id=cid)
            authority=rules(f,[t["subject"] for t in p["targets"]])
            r=h1.execute_plan(p,cs,explicit_execution=True,transport=fake,db_path=f.tmp/"h1.sqlite",authority_registry_path=authority)
            self.assertEqual(len(r["results"]),2); self.assertEqual(len(r["failures"]),1)
            self.assertEqual(calls.count(failed),h1.MAX_ATTEMPTS)
            calls.clear()
            def recovered(t):
                calls.append(t["candidate"]["candidate_id"])
                return fake_raw(t["subject"],request_id=t["candidate"]["candidate_id"])
            r=h1.execute_plan(p,cs,explicit_execution=True,transport=recovered,db_path=f.tmp/"h1.sqlite",authority_registry_path=authority)
            self.assertEqual(calls,[failed]); self.assertEqual(len(r["results"]),3)

    def test_tavily_adapter_one_query_raw_request_metadata(self):
        with PublicationFixture():
            c=candidate("ZetaNovelTool"); t=h1.research_plan([c],selected_candidate_ids=[c["candidate_id"]])["targets"][0]
            response={"provider_request_id":"adapter-fake","raw_provider_response":fake_raw(),"request_payload":{"query":"fake query"}}
            with patch("taxonomy_discovery.tavily_research.research_target_with_tavily",return_value=response) as adapter:
                with self.assertRaises(ValueError): h1.tavily_transport(t)
                adapter.assert_not_called()
                raw=h1.tavily_transport(t,explicit_execution=True)
            adapter.assert_called_once()
            self.assertEqual(adapter.call_args.args[0]["research_question"],"\n".join(t["questions"]))
            self.assertEqual(raw["raw_response"],fake_raw()); self.assertEqual(raw["request_id"],"adapter-fake")

    def test_authority_rule_change_does_not_reuse_old_interpretation(self):
        with PublicationFixture() as f:
            result=execute(f); c=result["candidate"]
            authority=f.tmp/"h1_authority.json"; authority.write_text(json.dumps({"version":"changed"}))
            fake=Mock(return_value=fake_raw(request_id="changed-rules"))
            r=h1.execute_plan(h1.research_plan([c],selected_candidate_ids=[c["candidate_id"]]),[c],explicit_execution=True,
                transport=fake,db_path=f.tmp/"h1.sqlite",authority_registry_path=authority)
            fake.assert_called_once(); self.assertEqual(r["results"][0]["recommended_next_action"],"research_more")


class RouteEvidenceTests(unittest.TestCase):
    def test_repository_entity_and_popularity_do_not_establish_new_capability(self):
        with PublicationFixture() as f:
            c=candidate(); subject=c["concept_key"]
            raw=fake_raw(subject,subject+" is a software tool. Official repository https://github.com/official/zeta")
            raw["results"].append({"url":"https://github.com/official/zeta", "content":subject+" is an engineering capability.", "stars":9999999})
            result=execute(f,c,raw)
            self.assertEqual(result["recommended_next_action"],"research_more")
            self.assertFalse(result["approval"])
            with self.assertRaises(ValueError): h1.create_draft(result,explicit_creation=True)

    def test_resolver_local_first_and_boundaries_retained(self):
        with PublicationFixture() as f:
            c=candidate("C++ programming"); fake=Mock(side_effect=AssertionError("local first"))
            p=h1.research_plan([c],selected_candidate_ids=[c["candidate_id"]])
            r=h1.execute_plan(p,[c],explicit_execution=True,transport=fake,db_path=f.tmp/"h1.sqlite")
            self.assertEqual(r["results"][0]["recommended_next_action"],"no_change")
            self.assertEqual(r["results"][0]["existing_capability_assessment"]["canonical_match"],"language.modern_cpp")
            fake.assert_not_called()

    def test_identity_authority_and_negative_conflict_fail_closed(self):
        with PublicationFixture() as f:
            result=execute(f)
            self.assertEqual(result["recommended_next_action"],"technology_identity_proposal")
            self.assertEqual(result["sources"][0]["source_class"],"first_party_official_docs")
            self.assertFalse(result["approval"])
        for content,url in (("ZetaNovelTool is not a concrete technology.","https://fixture.example/docs"),
                            ("ZetaNovelTool mentioned in navigation.","https://fixture.example/docs"),
                            ("ZetaNovelTool is a concrete technology.","https://random.example/docs")):
            with PublicationFixture() as f:
                raw=fake_raw(content=content); raw["results"][0]["url"]=url
                result=execute(f,raw=raw)
                self.assertEqual(result["recommended_next_action"],"research_more")
                with self.assertRaises(ValueError): h1.create_draft(result,explicit_creation=True)

    def test_relationship_existing_capability_and_supported_mapping(self):
        with PublicationFixture() as f:
            c=candidate("Node.js")
            self.assertEqual(c["candidate_route"],"technology_relationship")
            result=execute(f,c,fake_raw("Node.js", "Node.js is a runtime for backend API development."))
            supported=result["relationship_finding"]["supported_existing_capability_ids"]
            self.assertTrue(supported)
            self.assertTrue(set(supported).issubset(h1.get_default_taxonomy().by_id()))
            self.assertEqual(result["recommended_next_action"],"relationship_proposal")
            draft=h1.create_draft(result,explicit_creation=True)
            self.assertEqual(draft["proposal_bundle"]["proposals"][0]["proposed_capability_id"],supported[0])

    def test_possible_new_draft_explicit_no_auto_capability(self):
        with PublicationFixture() as f:
            c=candidate(); subject=c["concept_key"]
            result=execute(f,c,fake_raw(subject,subject+" is an engineering capability for implementing distinct computing protocols."))
            self.assertEqual(result["recommended_next_action"],"new_capability_proposal")
            with self.assertRaises(ValueError): h1.create_draft(result)
            fields={"capability_id":"test.crystalline_computing","label":subject,"domain":"distributed_systems",
                "definition":"Synthetic only computing protocols.", "match_concepts":[subject],"does_not_prove":["Name mention only"],
                "evidence_expectations":{"policy_references":["existing native evidence contract"],
                    "evidence_tiers":[{"label":"direct","all_groups":[[subject],["built","implemented"]],"reason":"explicit_application","concepts":[subject]}]}}
            draft=h1.create_draft(result,explicit_creation=True,capability_fields=fields)
            self.assertEqual(draft["proposal"]["governed_research"]["result_fingerprint"],result["result_fingerprint"])
            self.assertNotIn(fields["capability_id"],h1.get_default_taxonomy().by_id())

    def test_github_exact_official_link_random_repo_and_stars_ignored(self):
        with PublicationFixture() as f:
            authority=rules(f,["ZetaNovelTool"])
            raw=fake_raw(content="ZetaNovelTool is a concrete tool. Official repository https://github.com/official/zeta")
            raw["results"] += [{"url":"https://github.com/official/zeta","content":"ZetaNovelTool is a software tool.","stars":0},
                               {"url":"https://github.com/random/zeta","content":"ZetaNovelTool is a software tool.","stars":9999999,"authoritative":True}]
            classified=h1.classify_sources("ZetaNovelTool",raw,authority_registry_path=authority)
            self.assertEqual([s["source_class"] for s in classified], ["first_party_official_docs","first_party_official_repository","secondary_supporting"])
            del raw["results"][0]
            self.assertTrue(all(s["source_class"]=="secondary_supporting" for s in h1.classify_sources("ZetaNovelTool",raw,authority_registry_path=authority)))


class GovernanceImpactTests(unittest.TestCase):
    def test_approval_requires_saved_draft_and_current_reviewed_impact_never_publishes(self):
        with PublicationFixture() as f:
            result=execute(f,candidate("Node.js"),fake_raw("Node.js","Node.js is a runtime for backend API development."))
            options={"result_fingerprint":result["result_fingerprint"],"decision":"approve_for_publication","reviewer":"test human","db_path":f.tmp/"h1.sqlite"}
            with self.assertRaises(ValueError): save_governed_research_review(result["research_result_id"],**options)
            draft=h1.create_draft(result,explicit_creation=True)
            save_governed_research_draft(result,draft,db_path=f.tmp/"h1.sqlite",proposal_db_path=f.proposal_db)
            corpus=build_regression_corpus([frozen_snapshot("Node.js")])
            report=h1.temporary_impact(corpus,draft)
            modified=deepcopy(report); modified["affected_jobs"].append(999)
            with self.assertRaises(ValueError): save_governed_research_review(result["research_result_id"],regression=modified,**options)
            before=f.registry_path.read_bytes()
            review=save_governed_research_review(result["research_result_id"],regression=report,**options)
            self.assertFalse(review["publication"])
            self.assertEqual(f.registry_path.read_bytes(),before)
            self.assertEqual(f.real_registry.read_bytes(),f.real_registry_bytes)

    def test_edited_result_and_missing_saved_result_fail_closed_before_proposal_import(self):
        with PublicationFixture() as f:
            result=execute(f)
            modified=deepcopy(result); modified["recommended_next_action"]="new_capability_proposal"
            with self.assertRaises(ValueError): h1.create_draft(modified,explicit_creation=True)
            draft=h1.create_draft(result,explicit_creation=True)
            with patch("database.technology_registry_proposal_manager.import_proposal_bundle") as importer:
                with self.assertRaises(sqlite3.OperationalError):
                    save_governed_research_draft(result,draft,db_path=f.tmp/"missing.sqlite",proposal_db_path=f.proposal_db)
                importer.assert_not_called()

    def test_native_draft_persistence_separate_review_no_broad_mining_injection(self):
        with PublicationFixture() as f:
            before=list_broad_mining_candidate_reviews(db_path=f.review_db)
            result=execute(f)
            draft=h1.create_draft(result,explicit_creation=True)
            save_governed_research_draft(result,draft,db_path=f.tmp/"h1.sqlite",proposal_db_path=f.proposal_db)
            saved=list_governed_research_results(db_path=f.tmp/"h1.sqlite")[0]
            self.assertEqual(saved["draft"],draft); self.assertEqual(saved["review"]["decision"],"undecided")
            self.assertEqual(draft["proposal_bundle"]["proposals"][0]["governed_research"]["research_result_id"],result["research_result_id"])
            save_governed_research_review(result["research_result_id"],result_fingerprint=result["result_fingerprint"],decision="research_more",reviewer="test human",db_path=f.tmp/"h1.sqlite")
            self.assertEqual(list_governed_research_results(db_path=f.tmp/"h1.sqlite")[0]["review"]["decision"],"research_more")
            self.assertEqual(list_broad_mining_candidate_reviews(db_path=f.review_db),before)
            self.assertEqual(f.real_registry.read_bytes(),f.real_registry_bytes)

    def test_temporary_registry_native_replay_changes_resolution_and_isolates_threads(self):
        with PublicationFixture() as f:
            c=candidate("Node.js")
            result=execute(f,c,fake_raw("Node.js","Node.js is a runtime for backend API development."))
            draft=h1.create_draft(result,explicit_creation=True)
            corpus=build_regression_corpus([frozen_snapshot("Node.js")]); frozen=deepcopy(corpus)
            before=get_default_registry(); bytes_before=f.registry_path.read_bytes()
            report=h1.temporary_impact(corpus,draft)
            self.assertTrue(report["jobs"][0]["requirement_changes"])
            self.assertTrue(report["review_only"])
            self.assertNotEqual(report["temporary_registry_identity"],before.version)
            self.assertEqual(report["jobs"][0]["duplicate_credit_violations"],[])
            self.assertEqual(corpus,frozen); self.assertEqual(f.registry_path.read_bytes(),bytes_before)
            self.assertIs(get_default_registry(),before)
            from taxonomy_discovery.focused_verification_preview import _shadow_registry
            with temporary_registry_scope(_shadow_registry(draft)):
                self.assertEqual(resolve_requirement_text("Node.js")["status"],"resolved")
                with ThreadPoolExecutor(max_workers=1) as pool:
                    self.assertNotEqual(pool.submit(resolve_requirement_text,"Node.js").result()["status"],"resolved")
            self.assertNotEqual(resolve_requirement_text("Node.js")["status"],"resolved")
            self.assertEqual(f.real_registry.read_bytes(),f.real_registry_bytes)

    def test_temp_capability_duplicate_reporting_and_missing_context_closed(self):
        with PublicationFixture() as f:
            proposal,_=capability_draft(f)
            draft={"kind":"capability","proposal":proposal}
            corpus=build_regression_corpus([frozen_snapshot("crystalline computing protocols")])
            report=h1.temporary_impact(corpus,draft)
            self.assertTrue(report["affected_jobs"])
            row=deepcopy(corpus["jobs"][0]["baseline_stable_analysis"]["canonical_requirements"][0])
            corpus["jobs"][0]["baseline_stable_analysis"]["canonical_requirements"].append(row)
            report=h1.temporary_impact(corpus,draft)
            self.assertTrue(report["jobs"][0]["duplicate_credit_violations"])
            corpus["jobs"][0]["replay_available"]=False
            with self.assertRaises(ValueError): h1.temporary_impact(corpus,draft)

    def test_registry_preview_surfaces_original_duplicate_failures(self):
        with PublicationFixture() as f:
            result=execute(f,candidate("Node.js"),fake_raw("Node.js","Node.js is a runtime for backend API development."))
            draft=h1.create_draft(result,explicit_creation=True)
            corpus=build_regression_corpus([frozen_snapshot("Node.js")])
            stable=corpus["jobs"][0]["baseline_stable_analysis"]
            stable["canonical_requirements"].append(deepcopy(stable["canonical_requirements"][0]))
            report=h1.temporary_impact(corpus,draft)
            self.assertTrue(report["jobs"][0]["duplicate_credit_violations"])
            self.assertEqual(report["jobs"][0]["classification"],"hard_regression/invariant_violation")

    def test_isolated_test_publication_canary_not_real_discovery_evidence(self):
        with PublicationFixture() as f:
            save_broad_mining_candidate_review(candidate={"candidate_id":"real-persisted-review-test", "canonical_name":"Apache ActiveMQ", "status":"possible_new_technology"},
                decision="research_further",db_path=f.review_db)
            before=list_broad_mining_candidate_reviews(db_path=f.review_db)
            self.assertNotEqual(resolve_requirement_text(f.name)["status"],"resolved")
            f.approve(); f.publish()  # Test/temp registry only.
            self.assertEqual(resolve_requirement_text(f.name)["status"],"resolved")
            self.assertEqual(list_broad_mining_candidate_reviews(db_path=f.review_db),before)
            self.assertEqual(before[0]["canonical_name"],"Apache ActiveMQ")
            self.assertEqual(f.real_registry.read_bytes(),f.real_registry_bytes)
            status=h1.canary_status()
            self.assertIn("TEST / TEMPORARY ONLY",status["isolated unresolved -> verified -> approved -> test-published -> resolved"])
            self.assertEqual(status["Production registry mutated"],"No")
            self.assertFalse(status["Broad Mining fixtures injected"])


class UITests(unittest.TestCase):
    def test_render_no_execute_plan_or_prepare_and_honest_canary(self):
        from taxonomy_discovery.taxonomy_evolution_ui import render_governed_research
        with PublicationFixture():
            st=FakeStreamlit()
            with patch.dict(sys.modules,{"streamlit":st}), patch.object(h1,"execute_plan") as execute_mock, patch.object(h1,"prepare_gap_review") as prepare:
                render_governed_research(); render_governed_research()
            execute_mock.assert_not_called(); prepare.assert_not_called()
            self.assertTrue(any(m[0]=="json" and isinstance(m[1][0],dict) and m[1][0].get("Production registry mutated")=="No" for m in st.messages))

    def test_explicit_prepare_manual_upload_routes_and_selection(self):
        from taxonomy_discovery.taxonomy_evolution_ui import render_governed_research
        with PublicationFixture():
            st=FakeStreamlit(); st.button=lambda label,**kw: kw.get("key")=="tqd3_h1_manual"
            st.file_uploader=lambda label,**kw: SimpleNamespace(getvalue=lambda:json.dumps(gap_corpus()).encode()) if kw.get("key")=="tqd3_h1_corpus" else None
            with patch.dict(sys.modules,{"streamlit":st}), patch.object(h1,"execute_plan") as execute_mock:
                render_governed_research()
            execute_mock.assert_not_called()
            self.assertIn("tqd3_h1_prepared",st.session_state)
            rows=next(m[1][0] for m in st.messages if m[0]=="dataframe")
            self.assertIn("Initial Phase-G research route",rows[0]); self.assertIn("Refined candidate route",rows[0])

    def test_execute_only_button_and_plan_selection_change_blocks(self):
        from taxonomy_discovery.taxonomy_evolution_ui import render_governed_research
        with PublicationFixture():
            c=candidate("ZetaNovelTool"); prepared=h1.prepare_gap_review(gaps={"gap_version":GAP_VERSION,"observations":[]})
            prepared["candidates"]=[c]
            st=FakeStreamlit(); st.session_state["tqd3_h1_prepared"]=prepared
            st.session_state["tqd3_h1_plan"]=h1.research_plan([c],selected_candidate_ids=[c["candidate_id"]])
            st.multiselect=lambda *a,**kw:[c["candidate_id"]]; st.checkbox=lambda *a,**kw:False
            st.button=lambda label,**kw:kw.get("key")=="tqd3_h1_execute"
            with patch.dict(sys.modules,{"streamlit":st}),patch.object(h1,"execute_plan",return_value={"failures":[],"results":[]}) as run:
                render_governed_research()
                self.assertTrue(run.call_args.kwargs["explicit_execution"])
                st.multiselect=lambda *a,**kw:[]
                render_governed_research()
                self.assertEqual(run.call_count,1)


if __name__ == "__main__":
    unittest.main()

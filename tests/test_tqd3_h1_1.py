"""H.1.1 real-shaped regressions; fake transports and temporary stores only."""
from copy import deepcopy
import json
import os
import sys
import unittest
from unittest.mock import Mock, patch

from taxonomy_discovery import governed_research as h1
from taxonomy_discovery.research_atomicity import candidate_atomicity
from taxonomy_discovery.resolver_improvement import resolver_overlay, RESOLVER_DRAFT_VERSION
from taxonomy_discovery.source_authority import classify_candidate_source_url, default_source_authority_registry_path
from taxonomy_discovery.regression_corpus import build_regression_corpus
from taxonomy_discovery.corpus_expansion import fingerprint
from tailoring.capability_taxonomy import TAXONOMY_PATH, get_default_taxonomy
from database.taxonomy_discovery_review_manager import (list_governed_research_results, save_governed_research_draft,
    save_governed_research_review, list_taxonomy_evolution_proposals)
from tests.test_tqd3_taxonomy_evolution import candidate
from tests.test_tqd3_regression_corpus import frozen_snapshot
from tests.test_tqd3_publication_ui import FakeStreamlit
from tests.tqd3_publication_fixture_support import PublicationFixture

REST = "Knowledge of web services, API, REST, and gRPC"


def local_result(f,text=REST):
    c=candidate(text)
    plan=h1.research_plan([c],selected_candidate_ids=[c["candidate_id"]])
    receipt=h1.execute_plan(plan,[c],explicit_execution=True,transport=Mock(side_effect=AssertionError("local only")),db_path=f.tmp/"h11.sqlite")
    if receipt["failures"]: raise AssertionError(receipt["failures"])
    return receipt["results"][0]


def old_result(f,name,rows):
    legacy=f.tmp/(name.replace(" ","_")+"_old_rules.json")
    legacy.write_text(json.dumps({"version":"legacy-fixture", "organization_domains":[
        {"organization_aliases":["Microsoft"],"official_domains":["learn.microsoft.com"]},
        {"organization_aliases":["Red Hat"],"official_domains":["docs.redhat.com"]}]}))
    c=candidate(name)
    plan=h1.research_plan([c],selected_candidate_ids=[c["candidate_id"]])
    raw={"request_id":"cached-"+name,"results":rows,"usage":{"credits":1}}
    result=h1.execute_plan(plan,[c],explicit_execution=True,transport=Mock(return_value=raw),db_path=f.tmp/"h11.sqlite",authority_registry_path=legacy)
    if result["failures"]: raise AssertionError(result["failures"])
    return result["results"][0]


class ResolverTests(unittest.TestCase):
    def test_local_resolver_record_does_not_depend_on_external_authority_update(self):
        with PublicationFixture(pre_resolver_publication=True) as f:
            result=local_result(f)
            result["authority_rules_fingerprint"]="older-external-authority-rules"
            result.pop("result_fingerprint"); result.pop("research_result_id")
            result["result_fingerprint"]=fingerprint(result); result["research_result_id"]="tqd3h1_"+result["result_fingerprint"][:24]
            draft=h1.create_draft(result,explicit_creation=True)
            self.assertEqual(draft["target_capability_id"],"backend.api_development")

    def test_real_shape_deterministic_existing_capability_draft_no_mutation(self):
        with PublicationFixture(pre_resolver_publication=True) as f:
            taxonomy=TAXONOMY_PATH.read_bytes(); registry=f.registry_path.read_bytes()
            result=local_result(f)
            self.assertEqual(result["recommended_next_action"],"resolver_improvement")
            with self.assertRaises(ValueError): h1.create_draft(result)
            draft=h1.create_draft(result,explicit_creation=True)
            self.assertEqual(draft,h1.create_draft(result,explicit_creation=True))
            self.assertEqual(draft["resolver_draft_version"],RESOLVER_DRAFT_VERSION)
            self.assertEqual(draft["target_capability_id"],"backend.api_development")
            self.assertEqual(draft["proposed_resolver_change"]["add_requirement_phrases"],["web services"])
            self.assertNotIn("proposed_capability_id",draft)
            overlay=resolver_overlay(draft)
            self.assertEqual(set(overlay.by_id()),set(get_default_taxonomy().by_id()))
            for cid,entry in get_default_taxonomy().by_id().items():
                expected=deepcopy(entry)
                if cid==draft["target_capability_id"]:
                    expected["requirement"]["contextual_phrase_variants"]=[{"phrase":"web services",
                        "product_context_guard":"exclude_recognized_multiword_technology_spans"}]
                self.assertEqual(overlay.by_id()[cid],expected)
            save_governed_research_draft(result,draft,db_path=f.tmp/"h11.sqlite")
            saved=list_governed_research_results(db_path=f.tmp/"h11.sqlite")[0]
            self.assertEqual(saved["draft"],draft); self.assertEqual(saved["review"]["decision"],"undecided")
            self.assertEqual(list_taxonomy_evolution_proposals(db_path=f.tmp/"h11.sqlite"),[])
            self.assertEqual(TAXONOMY_PATH.read_bytes(),taxonomy); self.assertEqual(f.registry_path.read_bytes(),registry)

    def test_ambiguous_targets_and_unsupported_change_fail_closed(self):
        with PublicationFixture(pre_resolver_publication=True) as f:
            result=local_result(f,"web services and software system level integration")
            self.assertGreater(len(result["existing_capability_assessment"]["high_overlap_candidates"]),1)
            with self.assertRaises(ValueError): h1.create_draft(result,explicit_creation=True)
            result=local_result(f)
            draft=h1.create_draft(result,explicit_creation=True)
            draft["proposed_resolver_change"]["add_requirement_phrases"]=["python"]
            with self.assertRaises(ValueError): resolver_overlay(draft)

    def test_native_temp_impact_unrelated_changes_visible_and_duplicates_retained(self):
        with PublicationFixture(pre_resolver_publication=True) as f:
            result=local_result(f); draft=h1.create_draft(result,explicit_creation=True)
            first=frozen_snapshot(REST)
            second=frozen_snapshot("Maintain web services")
            second.update(id=2,discovered_job_id=5)
            unrelated=frozen_snapshot("Python"); unrelated.update(id=3,discovered_job_id=6)
            corpus=build_regression_corpus([first,second,unrelated]); before=deepcopy(corpus)
            report=h1.temporary_impact(corpus,draft)
            self.assertGreaterEqual(report["newly_resolved_count"],1)
            self.assertIn(4,report["affected_jobs"]); self.assertNotIn(6,report["affected_jobs"])
            self.assertTrue(report["unexpectedly_changed_requirements"])
            self.assertGreaterEqual(report["unchanged_count"],1)
            self.assertFalse(report["score_increase_is_correctness"])
            self.assertEqual(corpus,before)
            stable=corpus["jobs"][0]["baseline_stable_analysis"]
            stable["canonical_requirements"].append(deepcopy(stable["canonical_requirements"][0]))
            report=h1.temporary_impact(corpus,draft)
            self.assertTrue(report["jobs"][0]["duplicate_credit_violations"])
            self.assertEqual(f.real_registry.read_bytes(),f.real_registry_bytes)

    def test_not_exact_sentence_rule_and_human_approval_separate(self):
        with PublicationFixture(pre_resolver_publication=True) as f:
            text="Design and operate reliable web services"
            snapshot=frozen_snapshot(text)
            corpus=build_regression_corpus([snapshot])
            c=candidate(text)
            c["provenance"][0]["requirement_id"]=corpus["jobs"][0]["requirements"][0]["requirement_id"]
            c["candidate_fingerprint"]=fingerprint({k:v for k,v in c.items() if k not in {"candidate_id","candidate_fingerprint"}})
            c["candidate_id"]="tqd3taxgap_"+c["candidate_fingerprint"][:24]
            with patch("tests.test_tqd3_h1_1.candidate",return_value=c):
                result=local_result(f,text)
            draft=h1.create_draft(result,explicit_creation=True)
            self.assertEqual(draft["target_capability_id"],"backend.api_development")
            save_governed_research_draft(result,draft,db_path=f.tmp/"h11.sqlite")
            options=dict(result_fingerprint=result["result_fingerprint"],decision="approve_for_publication",reviewer="TEST ONLY",db_path=f.tmp/"h11.sqlite")
            with self.assertRaises(ValueError): save_governed_research_review(result["research_result_id"],**options)
            report=h1.temporary_impact(corpus,draft)
            report["unexpectedly_changed_requirements"]=[{
                "requirement_text":"Amazon Web Services",
                "reason":"Unsafe H.1.1 plural resolver collateral",
            }]
            report["regression_fingerprint"]=fingerprint({
                key:value for key,value in report.items()
                if key!="regression_fingerprint"
            })
            from database.taxonomy_discovery_review_manager import save_governed_temporary_impact
            save_governed_temporary_impact(result["research_result_id"],report,db_path=f.tmp/"h11.sqlite")
            with self.assertRaisesRegex(
                ValueError,
                "Resolver approval blocked: missing regression identity or unexpected requirement changes",
            ):
                save_governed_research_review(result["research_result_id"],regression=report,**options)
            saved=list_governed_research_results(db_path=f.tmp/"h11.sqlite")[0]
            self.assertEqual(saved["review"]["decision"],"undecided")


class CachedAuthorityTests(unittest.TestCase):
    def test_associations_are_subject_specific(self):
        for subject,url in (("Keycloak","https://keycloak.org/docs"),("Microsoft SCCM","https://learn.microsoft.com/mem/configmgr")):
            self.assertEqual(classify_candidate_source_url({"canonical_name":subject},url)["authority"],"primary_official")
            self.assertNotEqual(classify_candidate_source_url({"canonical_name":"UnrelatedTool"},url)["authority"],"primary_official")

    def test_keycloak_cached_lineage_raw_history_and_no_usage(self):
        with PublicationFixture() as f:
            rows=[{"url":"https://keycloak.org/docs","content":"Keycloak is an identity and access management tool."},
                {"url":"https://docs.redhat.com/keycloak","content":"Keycloak is an identity and access management tool."},
                {"url":"https://random.example","content":"Keycloak is a system.","authoritative":True}]
            original=old_result(f,"Keycloak",rows); frozen=deepcopy(original)
            self.assertEqual(original["quality_diagnostics"]["primary_definitions"],0)
            with patch.object(h1,"tavily_transport",side_effect=AssertionError("no search")),patch("database.tavily_usage_manager.record_tavily_usage",side_effect=AssertionError("no event")):
                updated=h1.re_evaluate_saved_evidence(original,explicit_execution=True,authority_registry_path=default_source_authority_registry_path(),persist=True,db_path=f.tmp/"h11.sqlite")
            self.assertGreater(updated["quality_diagnostics"]["primary_definitions"],0)
            self.assertTrue(updated["identity_finding"]["verified"])
            self.assertFalse(updated["relationship_finding"]["verified"])
            self.assertNotEqual(updated["result_fingerprint"],original["result_fingerprint"])
            self.assertEqual(updated["research"]["raw_provider_evidence"],original["research"]["raw_provider_evidence"])
            self.assertEqual(updated["interpretation_lineage"]["previous_research_result_id"],original["research_result_id"])
            self.assertEqual(original,frozen)
            stored=list_governed_research_results(db_path=f.tmp/"h11.sqlite")
            self.assertEqual(len(stored),2); self.assertIn(frozen,[r["result"] for r in stored])
            self.assertFalse(updated["approval"]); f.network_guard.assert_not_called(); f.model_guard.assert_not_called()

    def test_sccm_governed_alias_definition_and_community_answers_fail_closed(self):
        with PublicationFixture() as f:
            original=old_result(f,"Microsoft SCCM",[{"url":"https://learn.microsoft.com/en-us/mem/configmgr/core/understand/introduction",
                "content":"Microsoft Configuration Manager is an endpoint management tool."}])
            updated=h1.re_evaluate_saved_evidence(original,explicit_execution=True,authority_registry_path=default_source_authority_registry_path())
            self.assertTrue(updated["identity_finding"]["verified"])
            self.assertEqual(updated["identity_finding"]["canonical_name"],"Microsoft Configuration Manager")
            self.assertEqual(updated["authority_rules_version"],"source-authority-registry-v1.3")
            self.assertEqual(updated["provider_request_id"],original["provider_request_id"])
        with PublicationFixture() as f:
            original=old_result(f,"Microsoft SCCM",[{"url":"https://learn.microsoft.com/en-us/answers/questions/123/naming",
                "content":"Microsoft Configuration Manager is an endpoint management tool.","authoritative":True}])
            updated=h1.re_evaluate_saved_evidence(original,explicit_execution=True,authority_registry_path=default_source_authority_registry_path())
            self.assertFalse(updated["identity_finding"]["verified"])
            self.assertEqual(updated["recommended_next_action"],"research_more")

    def test_release_notes_are_not_forced_to_verify_and_explicit_operation_required(self):
        with PublicationFixture() as f:
            original=old_result(f,"Keycloak",[{"url":"https://keycloak.org/releases","content":"Keycloak continues to improve its authentication features."}])
            with self.assertRaises(ValueError): h1.re_evaluate_saved_evidence(original)
            updated=h1.re_evaluate_saved_evidence(original,explicit_execution=True,authority_registry_path=default_source_authority_registry_path())
            self.assertEqual(updated["quality_diagnostics"]["primary_definitions"],0)
            self.assertFalse(updated["identity_finding"]["verified"])


class AtomicityPreflightTests(unittest.TestCase):
    def test_changed_refinement_inputs_do_not_repeat_saved_gap_search(self):
        with PublicationFixture() as f:
            original=old_result(f,"Microsoft SCCM",[{"url":"https://learn.microsoft.com/en-us/mem/configmgr","content":"Microsoft Configuration Manager is an endpoint management tool."}])
            c=deepcopy(original["candidate"]); c["routing_reason"]+=" updated refinement metadata"
            c.pop("candidate_fingerprint"); c.pop("candidate_id")
            c["candidate_fingerprint"]=fingerprint(c); c["candidate_id"]="tqd3taxgap_"+c["candidate_fingerprint"][:24]
            plan=h1.research_plan([c],selected_candidate_ids=[c["candidate_id"]]); fake=Mock()
            with self.assertRaisesRegex(ValueError,"Re-evaluate saved evidence"):
                h1.execute_plan(plan,[c],explicit_execution=True,transport=fake,db_path=f.tmp/"h11.sqlite")
            fake.assert_not_called()

    def test_config_key_value_is_not_exposed_in_execution_result(self):
        with PublicationFixture() as f:
            c=candidate("UnknownNovelTool"); plan=h1.research_plan([c],selected_candidate_ids=[c["candidate_id"]])
            secret="FIXTURE_SECRET_NEVER_DISPLAY"
            with patch.dict(os.environ,{"TAVILY_API_KEY":secret}),patch.object(h1,"tavily_transport",return_value={"request_id":"fake-only","results":[]}) as provider:
                receipt=h1.execute_plan(plan,[c],explicit_execution=True,db_path=f.tmp/"h11.sqlite")
            provider.assert_called_once(); self.assertNotIn(secret,json.dumps(receipt))

    def test_ui_cached_re_evaluation_only_on_explicit_click(self):
        from taxonomy_discovery.taxonomy_evolution_ui import render_governed_research
        from taxonomy_discovery.candidate_refinement import candidate_report
        with PublicationFixture() as f:
            result=local_result(f); st=FakeStreamlit()
            st.session_state["tqd3_h1_prepared"]={"candidates":[result["candidate"]],"report":candidate_report([result["candidate"]]),"corpus":None,
                "gaps":None,"csv":"","current_versions":h1.current_match_versions(),"artifact_fingerprint":"fixture"}
            rows=[{"result":result,"draft":None,"review":{"decision":"undecided"}}]
            with patch.dict(sys.modules,{"streamlit":st}),patch("database.taxonomy_discovery_review_manager.list_governed_research_results",return_value=rows),\
                    patch.object(h1,"re_evaluate_saved_evidence",return_value=result) as re_evaluate,patch.object(h1,"execute_plan") as execute:
                render_governed_research(); re_evaluate.assert_not_called()
                st.button=lambda label,**kwargs:kwargs.get("key")==result["research_result_id"]+"_reevaluate"
                render_governed_research()
                re_evaluate.assert_called_once_with(result,explicit_execution=True,persist=True)
                execute.assert_not_called()

    def test_atomic_coherent_compound_relations_and_parent_provenance(self):
        with PublicationFixture():
            for text in ("Keycloak","Microsoft SCCM","Node.js"):
                self.assertEqual(candidate_atomicity(candidate(text))["atomicity_status"],"atomic")
            self.assertEqual(candidate_atomicity(candidate(REST))["atomicity_status"],"coherent_capability_concept")
            for text in ("C#, JavaScript, HTML, CSS","MongoDB, Redis, Elasticsearch","Git, Mercurial, Nexus, Artifactory, Maven, Jira, Jenkins",
                         "Python or Java","AWS Glue, Azure Data Factory, Google Dataflow or Databricks"):
                c=candidate(text); before=deepcopy(c); meta=candidate_atomicity(c)
                self.assertEqual(meta["atomicity_status"],"compound_requires_decomposition",text)
                self.assertEqual(meta["source_provenance"],c["provenance"]); self.assertEqual(c,before)
                with self.assertRaises(ValueError): h1.research_plan([c],selected_candidate_ids=[c["candidate_id"]])
            self.assertEqual(candidate_atomicity(candidate("Python or Java"))["logical_relation"],"or")
            self.assertEqual(candidate_atomicity(candidate("AWS Glue, Azure Data Factory, Google Dataflow or Databricks"))["logical_relation"],"alternative_list")

    def test_server_rejects_preexisting_compound_plan_no_transport(self):
        with PublicationFixture() as f:
            c=candidate("Python or Java")
            # Simulate an old H.1 plan assembled before the new atomicity guard.
            with patch("taxonomy_discovery.research_atomicity.candidate_atomicity",return_value={"atomicity_status":"atomic","detected_entities":["Python","Java"]}):
                plan=h1.research_plan([c],selected_candidate_ids=[c["candidate_id"]])
            fake=Mock()
            with self.assertRaisesRegex(ValueError,"decomposition"):
                h1.execute_plan(plan,[c],explicit_execution=True,transport=fake,db_path=f.tmp/"h11.sqlite")
            fake.assert_not_called(); self.assertFalse((f.tmp/"h11.sqlite").exists())

    def test_global_missing_key_fails_before_any_local_or_external_execution(self):
        with PublicationFixture(pre_resolver_publication=True) as f:
            cs=[candidate(REST),candidate("UnknownNovelTool")]
            plan=h1.research_plan(cs,selected_candidate_ids=[c["candidate_id"] for c in cs])
            with patch.dict(os.environ,{"TAVILY_API_KEY":""}),patch.object(h1,"tavily_transport") as provider:
                with self.assertRaisesRegex(ValueError,"Tavily research is not configured. TAVILY_API_KEY is unavailable"):
                    h1.execute_plan(plan,cs,explicit_execution=True,db_path=f.tmp/"h11.sqlite")
            provider.assert_not_called(); self.assertEqual(list_governed_research_results(db_path=f.tmp/"h11.sqlite"),[])
            self.assertEqual(local_result(f)["recommended_next_action"],"resolver_improvement")

    def test_ui_selector_quarantine_compounds_and_no_select_all(self):
        from taxonomy_discovery.taxonomy_evolution_ui import render_governed_research
        with PublicationFixture():
            cs=[candidate(t) for t in (REST,"Keycloak","Microsoft SCCM","Python or Java","only shortlisted candidates will be notified")]
            from taxonomy_discovery.candidate_refinement import candidate_report
            st=FakeStreamlit(); st.session_state["tqd3_h1_prepared"]={"candidates":cs,"report":candidate_report(cs),"corpus":None,"gaps":None,"csv":"","current_versions":h1.current_match_versions(),"artifact_fingerprint":"fixture"}
            options=[]
            def select(label,values,**kwargs):
                if label.startswith("Research candidate "): options.append(values)
                return None
            st.selectbox=select
            with patch.dict(sys.modules,{"streamlit":st}),patch.object(h1,"execute_plan") as execute:
                render_governed_research()
            self.assertEqual(len(options),3)
            self.assertEqual(set(options[0][1:]),{c["candidate_id"] for c in cs[:3]})
            self.assertTrue(any("Needs decomposition" in str(m) for m in st.messages))
            self.assertFalse(any("Select all" in str(m) for m in st.messages)); execute.assert_not_called()


if __name__ == "__main__": unittest.main()

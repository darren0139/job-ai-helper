"""Native receipts and local UI only; no production eligibility changes."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from tests.network_guard_support import block_external_network_allow_loopback

from streamlit.testing.v1 import AppTest
from scripts import calibrate_jd_scoring_eligibility as calibration
from taxonomy_discovery import coverage_presentation as coverage

FIXTURE = Path(__file__).with_name("fixtures") / "per_jd_scoring_audit.json"


class AnalyzedJobsSummaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle=json.loads(FIXTURE.read_text(encoding="utf-8"))

    def setUp(self):
        self.current=patch.object(coverage.maintenance,"currentness",return_value={"current":True,"blockers":[]})
        self.current.start();self.addCleanup(self.current.stop)

    def record(self,jid):
        j=next(j for j in self.bundle["snapshot"]["audit"]["corpus"]["jobs"] if j["job_id"]==jid)
        return {"job_id":jid,"status":"current","raw_jd_text":j["frozen_inputs"]["raw_jd_text"],
            "stable_analysis":j["baseline_stable_analysis"]}

    def summary(self,rows):
        return coverage.analyzed_jobs_coverage(self.bundle["snapshot"],self.bundle["plan"],rows)

    def test_occurrences_not_percentage_average_and_native_gap_identity(self):
        result=self.summary([self.record(163),self.record(566)])
        self.assertEqual((result["numerator"],result["denominator"]),(17,19))
        self.assertAlmostEqual(result["percentage"],100*17/19)
        self.assertNotEqual(result["percentage"],(75+100)/2)
        self.assertEqual(result["proven_gap_occurrences"],2)
        self.assertEqual(result["unique_missing_capabilities"],1)
        self.assertEqual(result["gap_concept_ids"],["network.access_control"])
        self.assertEqual(result["jobs_affected"],1)

    def test_same_governed_concept_across_jobs_preserves_occurrences(self):
        gap={"proof":{"profile":{"new_capability":{"capability_id":"network.access_control"}}}}
        views=[{"capability_resolved":3,"proven_gap_count":2,"proven_gaps":[gap,gap]},
               {"capability_resolved":4,"proven_gap_count":1,"proven_gaps":[gap]}]
        with patch.object(coverage,"jd_coverage",side_effect=views):
            result=self.summary([self.record(163),self.record(566)])
        self.assertEqual((result["numerator"],result["denominator"]),(7,10))
        self.assertEqual((result["proven_gap_occurrences"],result["unique_missing_capabilities"],result["jobs_affected"]),(3,1,2))

    def test_stale_unavailable_summary_only_and_unanalyzed_are_separate(self):
        stale={**self.record(566),"status":"stale"}
        summary_only={**self.record(31),"stable_analysis":None}
        mismatch={**self.record(16),"raw_jd_text":"another JD"}
        result=self.summary([self.record(163),stale,summary_only,mismatch,{"job_id":999,"status":"none"}])
        self.assertEqual((result["eligible_analyzed_jobs"],result["pending_analyzed_jobs"],result["unanalyzed_jobs"]),(1,3,1))
        self.assertEqual((result["numerator"],result["denominator"]),(6,8))
        with patch.object(coverage.maintenance,"currentness",return_value={"current":False,"blockers":["stale"]}):
            result=self.summary([self.record(163)])
            self.assertEqual(result["percentage"],100)
            self.assertEqual(result["proven_gap_occurrences"],0)
            self.assertEqual(result["pending_analyzed_jobs"],0)

    def test_unknown_concept_and_duplicate_job_fail_closed(self):
        view={"capability_resolved":3,"proven_gap_count":1,"proven_gaps":[{"proof":{}}]}
        with patch.object(coverage,"jd_coverage",return_value=view):
            result=self.summary([self.record(163)])
        self.assertEqual(result["pending_analyzed_jobs"],1)
        self.assertIsNone(result["percentage"])
        with self.assertRaises(ValueError): self.summary([self.record(163),self.record(163)])

    def test_full_receipt_identity_and_snapshot_must_match(self):
        jobs=[{"id":163,"description":self.record(163)["raw_jd_text"]}]
        state={"status":"current","identity":{"version":"current"},"snapshot":{"id":7,"summary":{"score":14}}}
        full=deepcopy(state);full["snapshot"]["stable_analysis"]=self.record(163)["stable_analysis"]
        records=coverage.analyzed_job_records(jobs,{163:state},{163:full})
        self.assertEqual(self.summary(records)["eligible_analyzed_jobs"],1)
        for field,value in (("identity",{"version":"old"}),("snapshot",{"id":6,"stable_analysis":full["snapshot"]["stable_analysis"]})):
            old=deepcopy(full);old[field]=value
            records=coverage.analyzed_job_records(jobs,{163:state},{163:old})
            self.assertEqual(self.summary(records)["pending_analyzed_jobs"],1)

    def test_global_and_per_jd_preserved(self):
        self.assertEqual(coverage.confirmed_coverage(self.bundle["snapshot"],self.bundle["plan"])["denominator"],194)
        result=self.summary([self.record(j) for j in (163,566,31,16)])
        self.assertEqual((result["numerator"],result["denominator"]),(29,31))
        self.assertEqual([j["percentage"] for j in result["jobs"]],[75,100,100,100])

    def test_summary_ui_missing_receipt_and_rerender_are_read_only(self):
        code='''import streamlit as st
from taxonomy_discovery.coverage_presentation import render_analyzed_jobs_summary
render_analyzed_jobs_summary(st,[{"job_id":1,"status":"current","stable_analysis":{"canonical_requirements":[{}]}}])
'''
        with block_external_network_allow_loopback(), \
            patch.object(coverage.maintenance,"execute_research",side_effect=AssertionError("Research")), \
            patch.object(coverage.maintenance,"publish_validated",side_effect=AssertionError("Publish")):
            app=AppTest.from_string(code,default_timeout=30).run();app.run()
        self.assertEqual(list(app.exception),[])
        self.assertEqual(app.metric[0].value,"Not enough classified capability requirements yet")
        self.assertTrue(any("Review pending: 1" in c.value for c in app.caption))

    def test_summary_ui_shows_own_occurrences_and_rerenders_without_execution(self):
        code='''import streamlit as st
from taxonomy_discovery.coverage_presentation import render_analyzed_jobs_summary
render_analyzed_jobs_summary(st,st.session_state["analyses"])
'''
        app=AppTest.from_string(code,default_timeout=30)
        app.session_state["tm_coverage_receipt"]=self.bundle
        app.session_state["analyses"]=[self.record(163),self.record(566)]
        with block_external_network_allow_loopback(), \
            patch.object(coverage.maintenance,"execute_research",side_effect=AssertionError("Research")), \
            patch.object(coverage.maintenance,"publish_validated",side_effect=AssertionError("Publish")):
            app.run();app.run()
        self.assertEqual(list(app.exception),[])
        self.assertEqual([m.value for m in app.metric],["89.47%","2 currently established","1"])
        self.assertTrue(any("17 / 19" in c.value for c in app.caption))


class CalibrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle=json.loads(FIXTURE.read_text(encoding="utf-8"))
        with patch.object(coverage.maintenance,"currentness",return_value={"current":True,"blockers":[]}):
            cls.result=calibration.build_calibration(cls.bundle["snapshot"],cls.bundle["plan"])

    def test_all_34_receipts_are_retained_with_six_condition_review(self):
        r=self.result
        self.assertEqual(r["limitation_count"],34)
        original={(x["job_id"],x["requirement_id"]):x for x in r["native_audit"]["requirements"] if x["evaluability"]=="NOT_RELIABLY_EVALUABLE"}
        self.assertEqual(set(original),{(x["job_id"],x["requirement_id"]) for x in r["reviews"]})
        for row in r["reviews"]:
            self.assertEqual(len(row["proof_conditions"]),6)
            for k,v in original[row["job_id"],row["requirement_id"]].items(): self.assertEqual(row[k],v)
        self.assertEqual(r["decisions"],{calibration.AMBIGUOUS:34})
        self.assertEqual(r["verdict"],"MORE_POLICY_REVIEW_REQUIRED")

    def test_none_unresolved_not_addressable_and_gap_do_not_prove_limitation(self):
        for route in ("NEEDS_SCOPE_REVIEW","NOT_TAXONOMY_ADDRESSABLE","TRUE_CAPABILITY_TAXONOMY_GAP"):
            decision=calibration.calibrate_requirement({"knowledge_status":"UNRESOLVED","evidence_label":"none","route":route}, {})
            self.assertEqual(decision["decision"],calibration.AMBIGUOUS)
        native={"structured_match_status":"applied", "structured_match_kind":"programming_language_group",
            "structured_match_group_mode":"any"}
        self.assertEqual(calibration.calibrate_requirement({"knowledge_status":"UNRESOLVED"},native)["decision"],calibration.LEGITIMATE)
        self.assertEqual(calibration.calibrate_requirement({"knowledge_status":"UNRESOLVED"},
            {"structured_match_status":"applied"})["decision"],calibration.AMBIGUOUS)

    def test_production_nac_and_job566_protected(self):
        rows=self.result["native_audit"]["requirements"]
        nac=[r for r in rows if r["route"]=="TRUE_CAPABILITY_TAXONOMY_GAP"]
        self.assertEqual(len(nac),2)
        self.assertTrue(all(r["evidence_label"]=="direct" and r["score_eligible"] for r in nac))
        grpc=next(r for r in rows if r["requirement_id"]=="req_86d57d2e033d")
        self.assertEqual(grpc["evidence_label"],"none")
        self.assertEqual(next(j for j in self.result["preview"] if j["job_id"]==566)["production_score"],23)

    def test_positive_structural_receipts_keep_bounded_transfer_separate(self):
        positives=self.result["structural_positive_reviews"]
        self.assertEqual(len(positives),18)
        safe=[r for r in positives if r["review"]=="VALIDATED_BOUNDED_BEHAVIORAL_TRANSFER"]
        self.assertEqual(len(safe),1)
        self.assertEqual(safe[0]["job_id"],359)
        self.assertEqual(safe[0]["evidence_label"],"transferable")
        self.assertEqual(sum(r["review"]==calibration.AMBIGUOUS for r in positives),17)

    def test_preview_is_bounded_zero_exclusions_and_immutable(self):
        before=deepcopy(self.bundle)
        with patch.object(coverage.maintenance,"currentness",return_value={"current":True,"blockers":[]}), \
            block_external_network_allow_loopback(), \
            patch.object(coverage.maintenance,"execute_research",side_effect=AssertionError("Research")), \
            patch.object(coverage.maintenance,"publish_validated",side_effect=AssertionError("Publish")):
            repeated=calibration.build_calibration(self.bundle["snapshot"],self.bundle["plan"])
        self.assertEqual(repeated,self.result)
        self.assertEqual(before,self.bundle)
        self.assertEqual(len(repeated["preview"]),30)
        self.assertTrue(all(j["delta"]==j["rank_delta"]==j["rows_neutralized"]==0 for j in repeated["preview"]))
        self.assertEqual(repeated["tailoring_actions"],{"AMBIGUOUS_DO_NOT_AUTO_RECOMMEND":34})


class FinalAdjudicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle=json.loads(FIXTURE.read_text(encoding="utf-8"))
        with patch.object(coverage.maintenance,"currentness",return_value={"current":True,"blockers":[]}), \
            patch.object(calibration.audit,"counterfactual",side_effect=AssertionError("No speculative preview")):
            cls.result=calibration.build_adjudication(cls.bundle["snapshot"],cls.bundle["plan"])

    def test_34_native_receipts_preserved_and_policy_frozen(self):
        self.assertEqual(len(self.result["reviews"]),34)
        original={(r["job_id"],r["requirement_id"]):r for r in self.result["native_audit"]["requirements"] if r["evaluability"]=="NOT_RELIABLY_EVALUABLE"}
        for row in self.result["reviews"]:
            for key,value in original[row["job_id"],row["requirement_id"]].items():
                # Final tailoring advice replaces the prior report-only advice.
                if key != "tailoring_action": self.assertEqual(row[key],value)
        self.assertEqual(self.result["decisions"],{"AMBIGUOUS_FREEZE":34})
        self.assertEqual(self.result["verdict"],"SCORING_POLICY_FROZEN_NO_CHANGE")
        self.assertIsNone(self.result["preview"])
        self.assertEqual(self.result["preview_status"],"NO_BOUNDED_EXCLUSION_SET_PROVEN")

    def test_none_unresolved_and_missing_export_do_not_prove_failure(self):
        row={"evidence_label":"none","knowledge_status":"UNRESOLVED","evaluability_evidence":{
            "native_structure":{"source":"native_structure_unavailable","components":[],"mode":None}}}
        r=calibration.adjudicate_requirement(row,{})
        self.assertEqual(r["final_adjudication"],"AMBIGUOUS_FREEZE")
        self.assertEqual(r["satisfaction_scope"],"UNKNOWN")
        self.assertEqual(r["negative_evidence_status"],"UNKNOWN")
        self.assertEqual(r["independent_evidence_path"],"UNKNOWN")
        self.assertEqual(len(r["system_limitation_proof"]),7)

    def test_native_scope_is_not_guessed_from_text(self):
        row={"text":"Python or SQL and cloud security","evaluability_evidence":{}}
        self.assertEqual(calibration.adjudicate_requirement(row,{})["satisfaction_scope"],"UNKNOWN")
        self.assertEqual(calibration.adjudicate_requirement(row,{"is_atomic":True})["satisfaction_scope"],"ATOMIC")
        for mode,scope in (("any","ONE_OF"),("all","ALL_OF")):
            row["evaluability_evidence"]={"native_structure":{"components":[{"text":"Python"},{"text":"SQL"}],"mode":mode}}
            self.assertEqual(calibration.adjudicate_requirement(row,{})["satisfaction_scope"],scope)
        self.assertEqual(self.result["satisfaction_scopes"],{"NON_EVIDENCE_CONTEXT":1,"UNKNOWN":31,"ATOMIC":1,"COHERENT_PARENT":1})

    def test_negative_trace_distinguishes_rejection_without_inventing_absence(self):
        row={"evidence_label":"none","knowledge_status":"UNRESOLVED"}
        for candidate,status in (({"evidence_id":"observed-test-candidate"},"CANDIDATE_REJECTED"),(None,"SEARCHED_BUT_SCOPE_LIMITED")):
            trace={"keyword_outcome":"missing","keyword_search":{"candidate":candidate,"evidence_index_count":10}}
            a=calibration.adjudicate_requirement(row,{},trace)
            self.assertEqual(a,calibration.adjudicate_requirement(row,{},trace))
            self.assertEqual(a["negative_evidence_status"],status)
            self.assertEqual(a["final_adjudication"],"AMBIGUOUS_FREEZE")

    def test_independent_validated_path_and_nac_are_orthogonal(self):
        native={"structured_match_status":"applied","structured_match_kind":"collaborative_system_integration_transfer","structured_match_group_mode":"behavioral_transfer"}
        self.assertEqual(calibration.adjudicate_requirement({},native)["independent_evidence_path"],"YES")
        nac=[r for r in self.result["native_audit"]["requirements"] if r["route"]=="TRUE_CAPABILITY_TAXONOMY_GAP"]
        self.assertEqual(len(nac),2)
        self.assertTrue(all(r["evidence_label"]=="direct" and r["score_eligible"] for r in nac))

    def test_positive_controls_retain_original_component_evidence(self):
        controls=self.result["structural_positive_reviews"]
        self.assertEqual(len(controls),18)
        self.assertTrue(all(r["support_scope"]=="BOUNDED_COMPONENT_SUPPORT" and not r["whole_parent_support_proven"] for r in controls))
        native={r["requirement_id"]:r for r in self.result["native_audit"]["requirements"]}
        for r in controls: self.assertEqual(r["selected_evidence"],native[r["requirement_id"]]["selected_evidence"])
        j359=next(r for r in controls if r["job_id"]==359)
        self.assertEqual(j359["native_match_contract"]["structured_match_kind"],"collaborative_system_integration_transfer")

    def test_read_only_final_build_never_runs_unproven_preview(self):
        before=deepcopy(self.bundle)
        with patch.object(coverage.maintenance,"currentness",return_value={"current":True,"blockers":[]}), \
            patch.object(calibration.audit,"counterfactual",side_effect=AssertionError("Unproven preview")), \
            block_external_network_allow_loopback(), \
            patch.object(coverage.maintenance,"execute_research",side_effect=AssertionError("Research")), \
            patch.object(coverage.maintenance,"publish_validated",side_effect=AssertionError("Publish")):
            result=calibration.build_adjudication(self.bundle["snapshot"],self.bundle["plan"])
        self.assertEqual(before,self.bundle)
        self.assertEqual(result,self.result)
        self.assertEqual(result["production_scores"]["163"],14)
        self.assertEqual(result["production_scores"]["566"],23)
        self.assertEqual(result["tailoring_actions"],{"UNKNOWN_DO_NOT_AUTO_RECOMMEND":34})

    def test_actual_native_replay_observation_restores_functions(self):
        self._assert_native_replay_observation()

    def _assert_native_replay_observation(self):
        from taxonomy_discovery.regression_corpus import build_regression_corpus
        from taxonomy_discovery.offline_execution import offline_execution
        from tests.test_tqd3_regression_corpus import frozen_snapshot
        from analysis_stability import stable_evidence_scoring as scorer
        original=scorer._best_resume_evidence
        # The production replay is offline. Freeze its input under the same
        # existing context, including retrieval diagnostic metadata.
        with block_external_network_allow_loopback(), \
                offline_execution("Native calibration fixture is offline"):
            corpus=build_regression_corpus([frozen_snapshot("React")])
            before=deepcopy(corpus)
            trace,replay=calibration.trace_native_corpus(corpus)
        self.assertIs(scorer._best_resume_evidence,original)
        self.assertEqual(corpus,before)
        self.assertEqual(replay["analysis_changes"],[])
        self.assertEqual(replay["jobs_replayed"],1)
        self.assertTrue(all("canonical_scope" in r and "keyword_search" in r for r in trace.values()))

    def test_native_replay_fixture_is_independent_of_ambient_retrieval_mode(self):
        import os
        from taxonomy_discovery import offline_execution as offline
        from analysis_stability import stable_evidence_scoring as scorer
        original=scorer._best_resume_evidence
        for mode in ("lexical","hybrid"):
            with self.subTest(mode=mode), patch.dict(os.environ, {"CAPABILITY_RAG_MODE":mode}):
                self._assert_native_replay_observation()
                self.assertEqual(os.environ["CAPABILITY_RAG_MODE"],mode)
                self.assertIs(scorer._best_resume_evidence,original)
                self.assertIsNone(offline._reason.get())
                self.assertEqual(offline._users,0)


if __name__ == "__main__":
    unittest.main()

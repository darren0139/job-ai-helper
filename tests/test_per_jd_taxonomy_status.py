"""Native 30-job frozen receipts; no provider/research/lifecycle changes."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from tests.network_guard_support import block_external_network_allow_loopback
from streamlit.testing.v1 import AppTest
from taxonomy_discovery import coverage_presentation as coverage
from scripts import audit_jd_scoring_eligibility as audit
from tests.governed_review_fixtures import isolated_taxonomy

FIXTURE = Path(__file__).with_name("fixtures") / "per_jd_scoring_audit.json"


class PerJDTaxonomyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.native = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def setUp(self):
        self.enterContext(isolated_taxonomy())
        self.receipt = deepcopy(self.native)
        self.current = patch.object(coverage.maintenance, "currentness", return_value={"current": True,"blockers":[]})
        self.current.start(); self.addCleanup(self.current.stop)

    def job(self, jid):
        return next(j for j in self.receipt["snapshot"]["audit"]["corpus"]["jobs"] if j["job_id"] == jid)

    def view(self, jid, **changes):
        job = self.job(jid)
        args = {"job_id":jid,"raw_jd_text":job["frozen_inputs"]["raw_jd_text"],"stable_analysis":job["baseline_stable_analysis"]}
        args.update(changes)
        return coverage.jd_coverage(self.receipt["snapshot"], self.receipt["plan"], **args)

    def test_global_is_global_and_preserved(self):
        v = coverage.confirmed_coverage(self.receipt["snapshot"],self.receipt["plan"])
        self.assertEqual((v["numerator"],v["denominator"]),(192,194))
        self.assertAlmostEqual(v["weighted"]["required_core"]["percentage"],99.29447630210572)

    def live_analysis(self, resolved, other, identities=0):
        from tailoring.job_match_ab_analysis import current_ab_identity
        from tailoring.phase9f_starting_source_ranking import canonical_requirement_scope_fingerprint
        stable=deepcopy(self.job(566)['baseline_stable_analysis'])
        positive=next(r for r in stable['canonical_requirements'] if r.get('knowledge_status')=='CAPABILITY_RESOLVED')
        unknown=next(r for r in stable['canonical_requirements'] if r.get('knowledge_status')=='UNRESOLVED')
        rows=[]
        for i in range(resolved+other+identities):
            r=deepcopy(positive if i<resolved else unknown)
            r['requirement_id']=f'live_{i}'
            if i>=resolved+other:
                r['knowledge_status']='TECHNOLOGY_IDENTITY_RESOLVED'
            rows.append(r)
        stable['canonical_requirements']=rows
        raw='\n'.join(r['text'] for r in rows)
        stable['jd_fingerprint']=current_ab_identity(raw)['jd_fingerprint']
        stable['canonical_requirement_fingerprint']=canonical_requirement_scope_fingerprint(rows)
        return raw,stable

    def test_live_without_review_is_available_and_occurrences_exclude_unknowns(self):
        for resolved,other,identities in ((8,12,0),(11,11,0),(7,14,0),(5,20,1)):
            with self.subTest(resolved=resolved):
                raw,stable=self.live_analysis(resolved,other,identities)
                before=deepcopy(stable)
                v=coverage.jd_coverage(None,None,raw_jd_text=raw,stable_analysis=stable)
                self.assertEqual((v['capability_resolved'],v['denominator'],v['percentage']),(resolved,resolved,100))
                self.assertEqual(v['proven_gap_count'],0)
                self.assertEqual(v['additional_analysis_items'],other+identities)
                self.assertEqual(v['technology_identity_resolved'],identities)
                self.assertEqual(stable,before)

    def test_all_dependency_noise_and_deferred_classes_stay_outside_denominator(self):
        raw,stable=self.live_analysis(1,8)
        classes=['TECHNOLOGY_IDENTITY_DEPENDENCY','CONTEXTUAL_RELATIONSHIP_DEPENDENCY',
            'PARSER_OR_CANONICALISATION_BLOCKED','DECOMPOSITION_OR_MIXED_SCOPE_BLOCKED',
            'NOT_TAXONOMY_ADDRESSABLE','UNDETERMINED','DEFERRED','NEEDS_SCOPE_REVIEW']
        for r,category in zip(stable['canonical_requirements'][1:],classes):
            r['knowledge_status']=category
            r['semantic_addressability']='PROVEN_TRUE_CAPABILITY_GAP'  # untrusted row label is not proof
        v=coverage.jd_coverage(None,None,raw_jd_text=raw,stable_analysis=stable)
        self.assertEqual((v['denominator'],v['proven_gap_count'],v['additional_analysis_items']),(1,0,8))

    def test_zero_denominator_is_not_fabricated_100(self):
        raw,stable=self.live_analysis(0,12)
        v=coverage.jd_coverage(None,None,raw_jd_text=raw,stable_analysis=stable)
        self.assertIsNone(v['percentage'])
        self.assertEqual((v['denominator'],v['additional_analysis_items']),(0,12))

    def test_live_identity_corruption_and_stale_analysis_fail_closed(self):
        raw,stable=self.live_analysis(3,4)
        for field,value in [('jd_fingerprint','wrong'),('canonical_requirement_fingerprint','wrong'),
                ('scoring_version','stale'),('technology_registry_version','stale'),
                ('jd_structure_inference_version','stale')]:
            bad=deepcopy(stable);bad[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                coverage.jd_coverage(None,None,raw_jd_text=raw,stable_analysis=bad)
        bad=deepcopy(stable);bad['canonical_requirements'][0]['capability_id']=None
        with self.assertRaises(ValueError): coverage.jd_coverage(None,None,raw_jd_text=raw,stable_analysis=bad)
        bad=deepcopy(stable);bad['canonical_requirements'][1]['requirement_id']=bad['canonical_requirements'][0]['requirement_id']
        with self.assertRaises(ValueError): coverage.jd_coverage(None,None,raw_jd_text=raw,stable_analysis=bad)

    def test_live_aggregate_without_review_sums_occurrences_and_additional_items(self):
        analyses=[]
        for jid,n,other in [(1,11,11),(2,7,14),(3,5,20)]:
            raw,stable=self.live_analysis(n,other)
            analyses.append({'job_id':jid,'status':'current','raw_jd_text':raw,'stable_analysis':stable})
        v=coverage.analyzed_jobs_coverage(None,None,analyses)
        self.assertEqual((v['numerator'],v['denominator'],v['percentage']),(23,23,100))
        self.assertEqual((v['eligible_analyzed_jobs'],v['pending_analyzed_jobs'],v['additional_analysis_items']),(3,0,45))

    def test_invalid_gap_proof_does_not_invent_a_gap_or_hide_native_resolutions(self):
        reviewed=self.receipt['plan']['taxonomy_addressability']
        gap=next(r for r in reviewed['rows'] if r['semantic_addressability']==coverage.address.GAP)
        gap['proof']['gap_contract'].pop('not_primary_relationship')
        coverage.maintenance._seal(reviewed,'addressability_fingerprint')
        v=self.view(163)
        self.assertEqual((v['denominator'],v['percentage'],v['proven_gap_count']),(6,100,0))
        self.assertIn('proof',v['review_blocker'])

    def test_live_ui_without_review_is_passive_and_zero_denominator_is_explained(self):
        raw,stable=self.live_analysis(8,12)
        app=AppTest.from_string('''import streamlit as st
from taxonomy_discovery.coverage_presentation import render_jd_taxonomy_status
render_jd_taxonomy_status(st,raw_jd_text=st.session_state['raw'],stable_analysis=st.session_state['stable'])
''',default_timeout=30)
        app.session_state['raw']=raw;app.session_state['stable']=stable
        with patch('litellm.completion',side_effect=AssertionError('Model')), \
                patch('litellm.embedding',side_effect=AssertionError('Embedding')), \
                block_external_network_allow_loopback(), \
                patch.object(coverage.maintenance,'run_corpus_audit',side_effect=AssertionError('Replay')):
            app.run();app.run()
        self.assertFalse(app.exception)
        self.assertEqual([m.value for m in app.metric],['100.00%','0 currently established'])
        self.assertTrue(any('8 / 8' in c.value and 'Additional analysis items: 12' in c.value for c in app.caption))
        raw,stable=self.live_analysis(0,12)
        app.session_state['raw']=raw;app.session_state['stable']=stable;app.run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value,'Not enough classified capability requirements yet')

    def test_job163_only_own_proved_gaps(self):
        v = self.view(163)
        self.assertEqual(v["proven_gap_count"],2)
        self.assertEqual(v["denominator"],v["capability_resolved"]+2)
        self.assertTrue(all(r["job_id"]==163 for r in v["routes"]+v["proven_gaps"]))

    def test_other_job_gap_cannot_affect_job566(self):
        v = self.view(566)
        self.assertEqual(v["proven_gap_count"],0)
        self.assertEqual(v["denominator"],v["capability_resolved"])
        self.assertGreater(v["additional_analysis_items"],0)
        self.assertEqual(v["percentage"],100)

    def test_deferred_and_identity_not_denominator(self):
        for jid in (16,31):
            v=self.view(jid)
            self.assertEqual(v["denominator"],v["capability_resolved"])
            self.assertEqual(v["proven_gap_count"],0)
            self.assertGreater(v["additional_analysis_items"],0)

    def test_bound_jd_and_generation_must_match(self):
        with self.assertRaisesRegex(ValueError,"unique reviewed"):
            self.view(163,raw_jd_text=self.job(566)["frozen_inputs"]["raw_jd_text"])
        stable=deepcopy(self.job(163)["baseline_stable_analysis"])
        stable["canonical_requirements"][0]["importance"]="preferred"
        with self.assertRaises(ValueError): self.view(163,stable_analysis=stable)
        stable=deepcopy(self.job(163)["baseline_stable_analysis"])
        stable["scoring_version"]="stale"
        with self.assertRaises(ValueError): self.view(163,stable_analysis=stable)

    def test_incomplete_accounting_keeps_positive_proofs_without_requiring_all_rows(self):
        p=self.receipt["plan"]["taxonomy_addressability"]
        p["rows"].pop();coverage.maintenance._seal(p,"addressability_fingerprint")
        v=self.view(163)
        self.assertEqual((v['capability_resolved'],v['proven_gap_count'],v['denominator']),(6,2,8))
        self.assertEqual(v['percentage'],75)

    def test_stale_review_cannot_supply_gaps_but_native_resolutions_remain_available(self):
        with patch.object(coverage.maintenance,"currentness",return_value={"current":False,"blockers":["stale"]}):
            v=self.view(163)
            self.assertEqual((v['capability_resolved'],v['proven_gap_count'],v['percentage']),(6,0,100))

    def test_corrupt_review_cannot_supply_gaps_or_hide_native_resolutions(self):
        for corrupt in ('row', 'proof'):
            with self.subTest(corrupt=corrupt):
                self.receipt=deepcopy(self.native)
                reviewed=self.receipt['plan']['taxonomy_addressability']
                if corrupt=='row':
                    reviewed['rows'].append(None)
                else:
                    next(r for r in reviewed['rows'] if r['semantic_addressability']==coverage.address.GAP)['proof']=None
                coverage.maintenance._seal(reviewed,'addressability_fingerprint')
                view=self.view(163)
                self.assertEqual((view['capability_resolved'],view['proven_gap_count'],view['percentage']),(6,0,100))
                self.assertIn('review_blocker',view)

    def test_same_application_status_survives_resume_and_tailoring(self):
        before=self.view(163)
        stable=deepcopy(self.job(163)["baseline_stable_analysis"])
        stable["input_fingerprint"]="another_resume"
        for r in stable["canonical_requirements"]:
            r["evidence"]=[];r["match_label"]="none";r["match_value"]=0
        # Same helper for both entry surfaces; candidate scoring isn't taxonomy accounting.
        self.assertEqual(before,self.view(163,stable_analysis=stable,job_id=None))

    def test_render_unanalyzed_and_missing_never_falls_back_global(self):
        code='''import streamlit as st
from taxonomy_discovery.coverage_presentation import render_jd_taxonomy_status
render_jd_taxonomy_status(st,raw_jd_text="unknown",analyzed=st.session_state.get("analyzed",False))
'''
        app=AppTest.from_string(code,default_timeout=30)
        app.session_state["tm_coverage_receipt"]=self.receipt
        app.run();self.assertEqual(list(app.exception),[])
        self.assertTrue(any("Analyze job to view" in c.value for c in app.caption))
        self.assertEqual(len(app.metric),0)
        app.session_state["analyzed"]=True;app.run()
        self.assertTrue(any("review pending" in c.value for c in app.caption))
        self.assertEqual(len(app.metric),0)

    def test_ui_scope_and_no_execution_on_rerender(self):
        from taxonomy_discovery import governed_research,governed_publication,taxonomy_addressability
        job=self.job(566)
        code='''import streamlit as st
from taxonomy_discovery.coverage_presentation import render_jd_taxonomy_status
j=st.session_state["job"]
render_jd_taxonomy_status(st,raw_jd_text=j["frozen_inputs"]["raw_jd_text"],stable_analysis=j["baseline_stable_analysis"],job_id=j["job_id"])
'''
        app=AppTest.from_string(code,default_timeout=30)
        app.session_state["tm_coverage_receipt"]=self.receipt;app.session_state["job"]=job
        with patch.object(governed_research,"execute_plan") as research,patch.object(governed_publication,"publish_approved_change") as publish,patch.object(taxonomy_addressability,"classify") as classify:
            for _ in range(2): app.run();self.assertEqual(list(app.exception),[])
            metrics={m.label:m.value for m in app.metric}
            self.assertEqual(metrics["This JD's confirmed taxonomy coverage"],"100.00%")
            self.assertEqual(metrics["This JD's proven capability gaps"],"0 currently established")
            research.assert_not_called();publish.assert_not_called();classify.assert_not_called()


class ScoringEligibilityAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.native = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def setUp(self):
        self.enterContext(isolated_taxonomy())
        self.receipt=deepcopy(self.native)
        current=patch.object(coverage.maintenance,"currentness",return_value={"current":True,"blockers":[]})
        current.start();self.addCleanup(current.stop)
    def test_receipts_reproduce_every_production_score_and_do_not_mutate(self):
        before=deepcopy(self.receipt)
        result=audit.build_audit(self.receipt["snapshot"],self.receipt["plan"])
        self.assertEqual(len(result["requirements"]),474)
        self.assertEqual(len(result["jobs"]),30)
        self.assertTrue(all(j["production_receipt"]["score_parity"] for j in result["jobs"]))
        self.assertEqual(self.receipt,before)
        self.assertEqual(next(j for j in result["jobs"] if j["job_id"]==566)["current_score"],23)
        self.assertTrue(any(r["knowledge_status"]=="UNRESOLVED" and r["evidence_label"]=="direct" for r in result["requirements"]))
        self.assertTrue(any(r["knowledge_status"]=="UNRESOLVED" and r["evaluability"]==audit.EVALUABLE for r in result["requirements"]))
        self.assertTrue(any(r["knowledge_status"]=="UNRESOLVED" and r["evaluability"]==audit.LIMITED for r in result["requirements"]))
        self.assertEqual(audit.build_audit(self.receipt["snapshot"],self.receipt["plan"]),result)

    def test_counterfactual_preserves_original_sibling_allocation(self):
        rows=[{"requirement_id":str(i),"text":"bounded","importance":"core","atomic_group_id":g,
               "match_label":label,"match_value":v,"evidence_strength":s,"score_eligible":True}
              for i,g,label,v,s in [(1,"same","direct",1,5),(2,"same","none",0,0),(3,"other","none",0,0)]]
        stable={"canonical_requirements":rows,**audit.compute_deterministic_alignment(rows)}
        receipt=audit._receipt(stable)
        frozen=audit.counterfactual(stable,receipt,{"2"})
        redistributed=audit.compute_deterministic_alignment([rows[0],rows[2]])["deterministic_alignment_score"]
        self.assertEqual(frozen,40)  # original 1.5 / (1.5 + 3) * .9 + 10
        self.assertEqual(redistributed,55)

    def test_proven_gap_does_not_automatically_mean_unscoreable(self):
        result=audit.build_audit(self.receipt["snapshot"],self.receipt["plan"])
        nac=[r for r in result["requirements"] if r["route"]==coverage.campaign.GAP]
        self.assertEqual(len(nac),2)
        self.assertTrue(all(r["evidence_label"]=="direct" and r["score_eligible"] and r["evaluability"]==audit.AMBIGUOUS for r in nac))

    def test_unresolved_alone_never_proves_evaluation_limit(self):
        row={"knowledge_status":"UNRESOLVED","match_label":"none","evidence":[]}
        self.assertEqual(audit.evaluability(row,None)[0],audit.AMBIGUOUS)
        reviewed={"lane":coverage.campaign.PARSER,"structure_diagnostics":{"source":"native_structure_unavailable","components":[],"mode":None}}
        self.assertEqual(audit.evaluability(row,reviewed),(audit.LIMITED,"PARSER_NORMALIZATION_BLOCKED"))
        row.update(match_label="direct",evidence=[{"text":"subset"}])
        self.assertEqual(audit.evaluability(row,reviewed)[0],audit.AMBIGUOUS)

    def test_supporting_evidence_stays_in_native_strength_component(self):
        row={"requirement_id":"support","text":"working with teams","importance":"supporting","match_label":"direct","match_value":1,"evidence_strength":5,"score_eligible":True}
        stable={"canonical_requirements":[row],**audit.compute_deterministic_alignment([row])}
        receipt=audit._receipt(stable)
        self.assertEqual(receipt["requirements"],[])
        self.assertEqual(audit.counterfactual(stable,receipt,set()),10)
        self.assertEqual(audit.counterfactual(stable,receipt,{"support"}),0)


if __name__=="__main__": unittest.main()

"""Only copied native knowledge and temporary databases; no real publication."""
from contextlib import contextmanager, closing, nullcontext
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import unittest
from unittest.mock import patch, Mock

from tailoring import capability_taxonomy as taxonomy
from taxonomy_discovery import governed_research as h1, governed_publication as publication
from database import taxonomy_discovery_review_manager as reviews
from database import job_match_manager as matches
from job_discovery.matching import current_match_versions, inspect_job_match, build_profile_evidence_context
from tests.test_tqd3_h1_2 import fixture, REST, AWS, TARGET
from tests.tqd3_publication_fixture_support import PublicationFixture
from tests.test_tqd3_publication_ui import FakeStreamlit


@contextmanager
def isolated():
    real_path=Path(taxonomy.TAXONOMY_PATH)
    before=real_path.read_bytes()
    with PublicationFixture(pre_resolver_publication=True) as f:
        yield f
        taxonomy.get_default_taxonomy.cache_clear()
        assert real_path.read_bytes()==before
        assert f.real_registry.read_bytes()==f.real_registry_bytes


def approved(f):
    result,draft,corpus=fixture(f)
    db=f.tmp/"h11.sqlite"
    reviews.save_governed_research_draft(result,draft,db_path=db)
    report=h1.temporary_impact(corpus,draft)
    reviews.save_governed_temporary_impact(result["research_result_id"],report,db_path=db)
    reviews.save_governed_research_review(result["research_result_id"],result_fingerprint=result["result_fingerprint"],
        decision="approve_for_publication",reviewer="ISOLATED TEST",regression=report,db_path=db)
    return result,draft,corpus,report


def saved_job(corpus):
    frozen=corpus["jobs"][0]
    inputs=frozen["frozen_inputs"]
    context=inputs["context"]
    versions=current_match_versions()
    old=matches.save_job_match_snapshot(discovered_job_id=566,job_content_hash=frozen["job_content_hash"],
        evidence_fingerprint=context["evidence_fingerprint"],match_version=versions["match_version"],
        scoring_version=versions["scoring_version"],taxonomy_version=versions["taxonomy_version"],jd_profile=inputs["jd_profile"],
        evidence_snapshot=inputs["evidence_snapshot"],stable_analysis=frozen["baseline_stable_analysis"],summary={})
    with closing(sqlite3.connect(matches.DB_PATH)) as conn:
        conn.execute("CREATE TABLE discovered_jobs(id INTEGER PRIMARY KEY,content_hash TEXT,description TEXT)")
        conn.execute("INSERT INTO discovered_jobs VALUES (566,?,?)",(frozen["job_content_hash"],inputs["raw_jd_text"]))
        conn.commit()
    return {"id":566,"content_hash":frozen["job_content_hash"],"description":inputs["raw_jd_text"]},context,old


def approved_capability(f, *, aliases=None):
    from tests.test_tqd3_governed_research import execute, fake_raw, candidate
    from tests.test_tqd3_regression_corpus import frozen_snapshot
    from taxonomy_discovery.regression_corpus import build_regression_corpus
    c=candidate(); subject=c["concept_key"]
    result=execute(f,c,fake_raw(subject,subject+" is an engineering capability for implementing distinct computing protocols."))
    fields={"capability_id":"test.crystalline_computing","label":subject,"domain":"distributed_systems",
        "definition":"Synthetic only computing protocols.","match_concepts":[subject],"does_not_prove":["Name mention alone"],"aliases":aliases or [],
        "evidence_expectations":{"policy_references":["existing native evidence contract"],
            "evidence_tiers":[{"label":"direct","all_groups":[[subject],["built","implemented"]],"reason":"explicit_application","concepts":[subject]}]}}
    draft=h1.create_draft(result,explicit_creation=True,capability_fields=fields); db=f.tmp/"h1.sqlite"
    reviews.save_governed_research_draft(result,draft,db_path=db)
    report=h1.temporary_impact(build_regression_corpus([frozen_snapshot(subject)]),draft)
    reviews.save_governed_temporary_impact(result["research_result_id"],report,db_path=db)
    reviews.save_governed_research_review(result["research_result_id"],result_fingerprint=result["result_fingerprint"],decision="approve_for_publication",reviewer="TEST",regression=report,db_path=db)
    return result,draft


class ResolverPublicationTests(unittest.TestCase):
    @staticmethod
    def _capability_source(text, capability_id):
        marker='    {\n      "capability_id": '+json.dumps(capability_id)
        start=text.index(marker)+4
        _,length=json.JSONDecoder().raw_decode(text[start:])
        return text[start:start+length]

    def test_taxonomy_publication_preserves_layout_and_only_expected_semantics(self):
        with isolated() as f:
            result,_,_,_=approved(f)
            db=f.tmp/"h11.sqlite"
            before=f.taxonomy_path.read_bytes()
            before_json=json.loads(before)
            unrelated_before=self._capability_source(before.decode(),"motivation.subjective")

            receipt=publication.publish_approved_change(
                result["research_result_id"],explicit_publish=True,db_path=db)
            after=f.taxonomy_path.read_bytes()
            after_json=json.loads(after)

            expected=deepcopy(before_json)
            expected["taxonomy_version"]=publication._next_version(
                before_json["taxonomy_version"],"phase6d-capability-taxonomy-v")
            target=next(c for c in expected["capabilities"] if c["capability_id"]==TARGET)
            target["requirement"]["contextual_phrase_variants"]=receipt["change_applied"]["contextual_phrase_variants"]
            self.assertEqual(after_json,expected)
            self.assertEqual(receipt["version_before"],before_json["taxonomy_version"])
            self.assertEqual(receipt["version_after"],expected["taxonomy_version"])
            self.assertEqual(
                self._capability_source(after.decode(),"motivation.subjective"),
                unrelated_before,
            )

    def test_receipt_reads_and_repeated_publication_do_not_rewrite_artifact(self):
        with isolated() as f:
            result,_,_,_=approved(f)
            db=f.tmp/"h11.sqlite"
            receipt=publication.publish_approved_change(
                result["research_result_id"],explicit_publish=True,db_path=db)
            artifact=f.taxonomy_path.read_bytes()
            artifact_hash=hashlib.sha256(artifact).hexdigest()
            artifact_mtime=f.taxonomy_path.stat().st_mtime_ns
            db_before=db.read_bytes()

            self.assertEqual(publication.list_publications(db_path=db),[receipt])
            self.assertEqual(db.read_bytes(),db_before)
            self.assertEqual(f.taxonomy_path.read_bytes(),artifact)
            self.assertEqual(f.taxonomy_path.stat().st_mtime_ns,artifact_mtime)

            repeated=publication.publish_approved_change(
                result["research_result_id"],explicit_publish=True,db_path=db)
            self.assertEqual(repeated,receipt)
            self.assertEqual(len(publication.list_publications(db_path=db)),1)
            self.assertEqual(hashlib.sha256(f.taxonomy_path.read_bytes()).hexdigest(),artifact_hash)
            self.assertEqual(f.taxonomy_path.stat().st_mtime_ns,artifact_mtime)
            self.assertEqual(json.loads(artifact)["taxonomy_version"],receipt["version_after"])

    def test_unrelated_snapshot_is_preserved_and_not_rebuilt(self):
        from job_discovery.matching import _default_stable_builder, summarize_stable_match
        with isolated() as f:
            result,_,corpus,_=approved(f)
            _,context,_=saved_job(corpus)
            versions=current_match_versions()
            profile={"required_skills":["Python"]}
            raw="Requirements\nDevelop Python programs and maintain automated software systems for internal users in the engineering department."
            stable=_default_stable_builder(raw_jd_text=raw,jd_profile=profile,context=context)
            other=matches.save_job_match_snapshot(discovered_job_id=567,job_content_hash="other-hash",evidence_fingerprint=context["evidence_fingerprint"],
                match_version=versions["match_version"],scoring_version=versions["scoring_version"],taxonomy_version=versions["taxonomy_version"],
                jd_profile=profile,evidence_snapshot=context["evidence_items"],stable_analysis=stable,summary=summarize_stable_match(stable))
            with closing(sqlite3.connect(matches.DB_PATH)) as conn:
                conn.execute("INSERT INTO discovered_jobs VALUES (567,'other-hash',?)",(raw,)); conn.commit()
            with patch("job_discovery.matching.current_evidence_context",return_value=context):
                receipt=publication.publish_approved_change(result["research_result_id"],explicit_publish=True,db_path=f.tmp/"h11.sqlite")
            self.assertEqual(receipt["affected_jobs"],[566])
            self.assertEqual(matches.get_latest_job_match_snapshot(567),other)
            self.assertEqual(inspect_job_match({"id":567,"content_hash":"other-hash","description":raw},context=context)["status"],"stale")

    def test_preflight_and_publish_fail_closed_without_production_writes(self):
        cases=("missing_approval","rejected","reviewer","draft","regression","unexpected","duplicates","product_vocabulary",
               "latest_regression","source","candidate","taxonomy","registry","scoring","guard")
        for case in cases:
            with self.subTest(case=case), isolated() as f:
                result,draft,_,report=approved(f)
                db=f.tmp/"h11.sqlite"
                row=reviews.list_governed_research_results(db_path=db)[0]
                review=deepcopy(row["review"])
                changed=deepcopy(row["result"])
                if case=="missing_approval": review=None
                elif case=="rejected": review["decision"]="reject"
                elif case=="reviewer": review["reviewer"]=""
                elif case=="draft": draft["normalized_concept"]="edited"
                elif case=="regression": review["regression"]["regression_fingerprint"]="edited"
                elif case=="unexpected": review["regression"]["unexpectedly_changed_requirements"]=[{"requirement_id":"AWS"}]
                elif case=="duplicates": review["regression"]["jobs"][0]["duplicate_credit_violations"]=["duplicate"]
                elif case=="product_vocabulary": review["regression"].pop("resolver_product_context_fingerprint")
                elif case=="source": changed["research"]["raw_provider_evidence"]={"edited":True}
                elif case=="candidate": changed["candidate"]["candidate_fingerprint"]="edited"
                elif case=="guard": draft["proposed_resolver_change"].pop("product_context_guard")
                elif case in {"taxonomy","registry"}:
                    path=f.taxonomy_path if case=="taxonomy" else f.registry_path
                    raw=json.loads(path.read_bytes()); raw["taxonomy_version" if case=="taxonomy" else "registry_version"]+="-changed"
                    path.write_text(json.dumps(raw))
                with closing(sqlite3.connect(db)) as conn:
                    conn.execute("UPDATE governed_research_results SET result_json=?,draft_json=?,review_json=?",(json.dumps(changed),json.dumps(draft),json.dumps(review) if review else None))
                    if case=="latest_regression": conn.execute("DELETE FROM governed_temporary_impacts")
                    conn.commit()
                before=f.taxonomy_path.read_bytes(); registry=f.registry_path.read_bytes()
                with patch("job_discovery.matching.current_match_versions",return_value={}) if case=="scoring" else nullcontext():
                    self.assertFalse(publication.prepare_publication(result["research_result_id"],db_path=db)["ready"])
                    with self.assertRaises(ValueError): publication.publish_approved_change(result["research_result_id"],explicit_publish=True,db_path=db)
                self.assertEqual(f.taxonomy_path.read_bytes(),before)
                self.assertEqual(f.registry_path.read_bytes(),registry)

    def test_atomic_failure_and_recovery_after_file_replacement(self):
        from database.technology_registry_proposal_manager import _replace_knowledge
        with isolated() as f:
            result,_,_,_=approved(f)
            db=f.tmp/"h11.sqlite"; before=f.taxonomy_path.read_bytes()
            with patch("database.technology_registry_proposal_manager._replace_knowledge",side_effect=ValueError("staging failed")):
                with self.assertRaises(ValueError): publication.publish_approved_change(result["research_result_id"],explicit_publish=True,db_path=db)
            self.assertEqual(f.taxonomy_path.read_bytes(),before)
            def interrupted(*args):
                _replace_knowledge(*args)
                raise RuntimeError("simulated crash after atomic replace")
            with patch("database.technology_registry_proposal_manager._replace_knowledge",side_effect=interrupted):
                with self.assertRaises(RuntimeError): publication.publish_approved_change(result["research_result_id"],explicit_publish=True,db_path=db)
            after=f.taxonomy_path.read_bytes()
            self.assertNotEqual(before,after)
            receipt=publication.publish_approved_change(result["research_result_id"],explicit_publish=True,db_path=db)
            self.assertEqual(receipt["status"],"published")
            self.assertEqual(f.taxonomy_path.read_bytes(),after)
            self.assertEqual(len(publication.list_publications(db_path=db)),1)

    def test_changed_jd_or_missing_inputs_stay_stale_without_extraction(self):
        with isolated() as f:
            result,_,corpus,_=approved(f)
            job,context,_=saved_job(corpus)
            with closing(sqlite3.connect(matches.DB_PATH)) as conn:
                conn.execute("UPDATE discovered_jobs SET content_hash='changed' WHERE id=566"); conn.commit()
            with patch("job_discovery.matching.current_evidence_context",return_value=context),patch("job_discovery.matching._default_extract_jd_profile",side_effect=AssertionError("No extraction")) as extract:
                publication.publish_approved_change(result["research_result_id"],explicit_publish=True,db_path=f.tmp/"h11.sqlite")
            extract.assert_not_called()
            link=publication.list_linkage_receipts(db_path=f.tmp/"h11.sqlite")[0]
            self.assertEqual(link["jobs"][0]["status"],"stale_currentness_required")
            self.assertEqual(inspect_job_match(job,context=context)["status"],"stale")

    def test_rejected_legacy_and_replacement_have_independent_ledger_history(self):
        from taxonomy_discovery.corpus_expansion import fingerprint
        with isolated() as f:
            result,draft,_,report=approved(f)
            db=f.tmp/"h11.sqlite"
            old=deepcopy(draft); old["resolver_draft_version"]="tqd3-resolver-improvement-h1.1-v1"
            old["proposed_resolver_change"].pop("product_context_guard")
            old["draft_fingerprint"]=fingerprint({k:v for k,v in old.items() if k not in {"draft_fingerprint","resolver_draft_id"}})
            old["resolver_draft_id"]="tqd3resolver_"+old["draft_fingerprint"][:24]
            with closing(sqlite3.connect(db)) as conn:
                conn.execute("UPDATE governed_research_results SET draft_json=?,review_json=NULL",(json.dumps(old),)); conn.commit()
            reviews.save_governed_research_review(result["research_result_id"],result_fingerprint=result["result_fingerprint"],decision="reject",reviewer="TEST",db_path=db)
            reviews.save_governed_research_draft(result,draft,db_path=db)
            reviews.save_governed_temporary_impact(result["research_result_id"],report,db_path=db)
            reviews.save_governed_research_review(result["research_result_id"],result_fingerprint=result["result_fingerprint"],decision="approve_for_publication",reviewer="TEST",regression=report,db_path=db)
            ledger=publication.review_ledger(db_path=db)
            self.assertEqual({r["status"] for r in ledger},{"superseded","approved_pending_publication"})
            historical=next(r for r in ledger if r["status"]=="superseded")
            self.assertEqual(historical["human_decision"],"reject")
            self.assertEqual(historical["superseded_by"],draft["resolver_draft_id"])

    def test_explicit_atomic_publish_idempotence_job_currentness_session_and_history(self):
        with isolated() as f:
            result,draft,corpus,report=approved(f)
            db=f.tmp/"h11.sqlite"
            raw=f.taxonomy_path.read_bytes(); registry=f.registry_path.read_bytes()
            versions=current_match_versions()
            job,context,old=saved_job(corpus)
            self.assertEqual(inspect_job_match(job,context=context)["status"],"current")
            self.assertNotEqual(taxonomy.classify_requirement({"text":REST}),TARGET)
            preflight=publication.prepare_publication(result["research_result_id"],db_path=db)
            self.assertTrue(preflight["ready"],preflight)
            self.assertEqual(f.taxonomy_path.read_bytes(),raw)
            with self.assertRaises(ValueError): publication.publish_approved_change(result["research_result_id"],db_path=db)
            with patch("job_discovery.matching.current_evidence_context",return_value=context):
                receipt=publication.publish_approved_change(result["research_result_id"],explicit_publish=True,db_path=db)
            after=f.taxonomy_path.read_bytes()
            self.assertNotEqual(after,raw)
            self.assertEqual(receipt["version_after"],preflight["version_after"])
            self.assertEqual(taxonomy.get_default_taxonomy().version,receipt["version_after"])
            self.assertNotEqual(current_match_versions()["taxonomy_version"],versions["taxonomy_version"])
            self.assertEqual(current_match_versions()["scoring_version"],versions["scoring_version"])
            self.assertEqual(taxonomy.classify_requirement({"text":REST}),TARGET)
            # Research authority labels never become an unversioned production
            # resolver dependency. Production guard uses native registry/hints.
            with patch("taxonomy_discovery.candidate_refinement.load_source_authority_registry",side_effect=AssertionError("Research-only knowledge")):
                self.assertNotEqual(taxonomy.classify_requirement({"text":AWS}),TARGET)
                self.assertNotEqual(taxonomy.classify_requirement({"text":"web Amazon Web Services services"}),TARGET)
            state=inspect_job_match(job,context=context)
            self.assertEqual(state["status"],"current")
            self.assertNotEqual(state["snapshot"]["id"],old["id"])
            with closing(sqlite3.connect(matches.DB_PATH)) as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM job_match_snapshots").fetchone()[0],2)
            self.assertEqual(f.registry_path.read_bytes(),registry)
            self.assertEqual(publication.publish_approved_change(result["research_result_id"],explicit_publish=True,db_path=db),receipt)
            self.assertEqual(f.taxonomy_path.read_bytes(),after)
            self.assertEqual(len(publication.list_publications(db_path=db)),1)
            self.assertEqual(publication.review_ledger(db_path=db)[0]["status"],"published")
            from tailoring.jd_user_input_overrides import refresh_application_session_analysis_report
            session={"resume_profile":context["resume_profile"],"raw_resume_text":context["raw_resume_text"],
                "jd_profile":corpus["jobs"][0]["frozen_inputs"]["jd_profile"],"raw_jd_text":job["description"],"stable_analysis":old["stable_analysis"]}
            historic=deepcopy(session)
            current=refresh_application_session_analysis_report(session)
            self.assertEqual(current["stable_analysis"]["capability_taxonomy_version"],receipt["version_after"])
            self.assertEqual(session,historic)
            self.assertTrue(any(r.get("capability_id")==TARGET for r in current["stable_analysis"]["canonical_requirements"]))
            f.network_guard.assert_not_called(); f.model_guard.assert_not_called(); f.embedding_guard.assert_not_called()


class NativeFamilyTests(unittest.TestCase):
    def test_native_capability_conflicts_rejection_and_duplicate_id_fail_closed(self):
        for case in ("alias","rejected","duplicate_id"):
            with self.subTest(case=case),isolated() as f:
                result,draft=approved_capability(f,aliases=["web service"] if case=="alias" else None)
                db=f.tmp/"h1.sqlite"
                if case=="rejected":
                    with closing(sqlite3.connect(db)) as conn:
                        conn.execute("INSERT INTO taxonomy_evolution_reviews VALUES (?,?,?)",(draft["proposal"]["proposal_id"],json.dumps({"decision":"reject"}),"TEST")); conn.commit()
                elif case=="duplicate_id":
                    payload=json.loads(f.taxonomy_path.read_bytes())
                    payload["capabilities"].append(deepcopy(payload["capabilities"][0]))
                    f.taxonomy_path.write_text(json.dumps(payload))
                before=f.taxonomy_path.read_bytes()
                self.assertFalse(publication.prepare_publication(result["research_result_id"],db_path=db)["ready"])
                with self.assertRaises(ValueError): publication.publish_approved_change(result["research_result_id"],explicit_publish=True,db_path=db)
                self.assertEqual(f.taxonomy_path.read_bytes(),before)

    def test_rejected_native_registry_review_cannot_be_silently_reapproved(self):
        from tests.test_tqd3_governed_research import execute, fake_raw, candidate
        from tests.test_tqd3_regression_corpus import frozen_snapshot
        from taxonomy_discovery.regression_corpus import build_regression_corpus
        from database.technology_registry_proposal_manager import save_proposal_review
        with isolated() as f:
            result=execute(f,candidate("Node.js"),fake_raw("Node.js","Node.js is a runtime for backend API development."))
            draft=h1.create_draft(result,explicit_creation=True); db=f.tmp/"h1.sqlite"
            reviews.save_governed_research_draft(result,draft,db_path=db,proposal_db_path=f.proposal_db)
            report=h1.temporary_impact(build_regression_corpus([frozen_snapshot("Node.js")]),draft)
            reviews.save_governed_temporary_impact(result["research_result_id"],report,db_path=db)
            reviews.save_governed_research_review(result["research_result_id"],result_fingerprint=result["result_fingerprint"],decision="approve_for_publication",reviewer="TEST",regression=report,db_path=db)
            save_proposal_review(proposal_id=draft["draft_id"],proposal_bundle_version=draft["proposal_bundle"]["proposal_bundle_version"],decision="reject_proposal",db_path=f.proposal_db)
            before=f.registry_path.read_bytes()
            self.assertFalse(publication.prepare_publication(result["research_result_id"],db_path=db,proposal_db_path=f.proposal_db)["ready"])
            with self.assertRaises(ValueError): publication.publish_approved_change(result["research_result_id"],explicit_publish=True,db_path=db,proposal_db_path=f.proposal_db)
            self.assertEqual(f.registry_path.read_bytes(),before)

    def test_job_finder_ranks_existing_current_scores_and_excludes_stale(self):
        from job_discovery.ranking import rank_current_job_matches, lexical_relevance
        jobs=[{"id":1,"title":"Python"},{"id":2},{"id":3}]
        states={1:{"status":"stale","snapshot":{"summary":{"deterministic_alignment_score":100}}},
            2:{"status":"current","snapshot":{"summary":{"deterministic_alignment_score":20}}},
            3:{"status":"current","snapshot":{"summary":{"deterministic_alignment_score":70}}}}
        before=lexical_relevance(jobs[0],"Python")
        with patch("job_discovery.matching.inspect_job_match",side_effect=lambda j,**kw:states[j["id"]]):
            self.assertEqual([j["id"] for j in rank_current_job_matches(jobs,context={})],[3,2,1])
        self.assertEqual(lexical_relevance(jobs[0],"Python"),before)

    def test_unavailable_session_inputs_are_stale_not_fabricated_current(self):
        from tailoring.jd_user_input_overrides import refresh_application_session_analysis_report
        source={"stable_analysis":{"scoring_version":"old","capability_taxonomy_version":"old"}}
        before=deepcopy(source)
        with patch("tailoring.jd_user_input_overrides._rebuild_stable_analysis",side_effect=AssertionError("No fabricated inputs")):
            output=refresh_application_session_analysis_report(source)
        self.assertTrue(output["meta"]["stable_analysis_currentness"]["stale_requires_refresh"])
        self.assertEqual(output["stable_analysis"],source["stable_analysis"])
        self.assertEqual(source,before)

    def test_identity_and_relationship_reuse_native_publisher(self):
        from tests.test_tqd3_governed_research import execute, fake_raw, candidate
        from tests.test_tqd3_regression_corpus import frozen_snapshot
        from taxonomy_discovery.regression_corpus import build_regression_corpus
        from taxonomy_discovery.technology_registry import resolve_requirement_text
        from database.technology_registry_proposal_manager import list_proposal_publications
        for subject,definition,kind in (("ZetaNovelTool","ZetaNovelTool is a concrete software engineering tool.","technology_identity"),
                ("Node.js","Node.js is a runtime for backend API development.","technology_relationship")):
            with self.subTest(kind=kind),isolated() as f:
                result=execute(f,candidate(subject),fake_raw(subject,definition))
                draft=h1.create_draft(result,explicit_creation=True)
                db=f.tmp/"h1.sqlite"
                reviews.save_governed_research_draft(result,draft,db_path=db,proposal_db_path=f.proposal_db)
                report=h1.temporary_impact(build_regression_corpus([frozen_snapshot(subject)]),draft)
                reviews.save_governed_temporary_impact(result["research_result_id"],report,db_path=db)
                reviews.save_governed_research_review(result["research_result_id"],result_fingerprint=result["result_fingerprint"],
                    decision="approve_for_publication",reviewer="TEST",regression=report,db_path=db)
                preflight=publication.prepare_publication(result["research_result_id"],db_path=db,proposal_db_path=f.proposal_db)
                self.assertTrue(preflight["ready"],preflight)
                before=f.registry_path.read_bytes(); taxonomy=f.taxonomy_path.read_bytes()
                receipt=publication.publish_approved_change(result["research_result_id"],explicit_publish=True,db_path=db,proposal_db_path=f.proposal_db)
                self.assertEqual(receipt["kind"],kind)
                self.assertNotEqual(f.registry_path.read_bytes(),before)
                self.assertEqual(f.taxonomy_path.read_bytes(),taxonomy)
                self.assertEqual(len(list_proposal_publications(db_path=f.proposal_db)),1)
                self.assertEqual(publication.publish_approved_change(result["research_result_id"],explicit_publish=True,db_path=db,proposal_db_path=f.proposal_db),receipt)
                if kind=="technology_relationship": self.assertEqual(resolve_requirement_text(subject)["capability_id"],TARGET)
                else: self.assertNotEqual(resolve_requirement_text(subject)["status"],"resolved")
                self.assertEqual(resolve_requirement_text("C++")["capability_id"],"language.modern_cpp")

    def test_capability_publication_uses_native_taxonomy_entry_contract(self):
        from tests.test_tqd3_governed_research import execute, fake_raw, candidate
        from tests.test_tqd3_regression_corpus import frozen_snapshot
        from taxonomy_discovery.regression_corpus import build_regression_corpus
        with isolated() as f:
            c=candidate(); subject=c["concept_key"]
            result=execute(f,c,fake_raw(subject,subject+" is an engineering capability for implementing distinct computing protocols."))
            fields={"capability_id":"test.crystalline_computing","label":subject,"domain":"distributed_systems",
                "definition":"Synthetic only computing protocols.","match_concepts":[subject],"does_not_prove":["Name mention alone"],
                "evidence_expectations":{"policy_references":["existing native evidence contract"],
                    "evidence_tiers":[{"label":"direct","all_groups":[[subject],["built","implemented"]],"reason":"explicit_application","concepts":[subject]}]}}
            draft=h1.create_draft(result,explicit_creation=True,capability_fields=fields)
            db=f.tmp/"h1.sqlite"
            reviews.save_governed_research_draft(result,draft,db_path=db)
            report=h1.temporary_impact(build_regression_corpus([frozen_snapshot(subject)]),draft)
            reviews.save_governed_temporary_impact(result["research_result_id"],report,db_path=db)
            reviews.save_governed_research_review(result["research_result_id"],result_fingerprint=result["result_fingerprint"],
                decision="approve_for_publication",reviewer="TEST",regression=report,db_path=db)
            preflight=publication.prepare_publication(result["research_result_id"],db_path=db)
            self.assertTrue(preflight["ready"],preflight)
            receipt=publication.publish_approved_change(result["research_result_id"],explicit_publish=True,db_path=db)
            self.assertEqual(taxonomy.classify_requirement({"text":subject}),"test.crystalline_computing")
            self.assertEqual(receipt["kind"],"capability")
            self.assertEqual(publication.publish_approved_change(result["research_result_id"],explicit_publish=True,db_path=db),receipt)


class LedgerUITests(unittest.TestCase):
    def test_guarded_replacement_and_preview_persist_then_rerun(self):
        from taxonomy_discovery.taxonomy_evolution_ui import render_governed_research
        from taxonomy_discovery.corpus_expansion import fingerprint
        with isolated() as f:
            result,draft,corpus,_=approved(f); db=f.tmp/"h11.sqlite"
            old=deepcopy(draft); old["resolver_draft_version"]="tqd3-resolver-improvement-h1.1-v1"
            old["proposed_resolver_change"].pop("product_context_guard")
            old["draft_fingerprint"]=fingerprint({k:v for k,v in old.items() if k not in {"draft_fingerprint","resolver_draft_id"}})
            old["resolver_draft_id"]="tqd3resolver_"+old["draft_fingerprint"][:24]
            with closing(sqlite3.connect(db)) as conn:
                conn.execute("UPDATE governed_research_results SET draft_json=?,review_json=NULL",(json.dumps(old),)); conn.commit()
            reviews.save_governed_research_review(result["research_result_id"],result_fingerprint=result["result_fingerprint"],decision="reject",reviewer="TEST",db_path=db)
            st=FakeStreamlit(); st.selectbox=lambda *a,**k:None; st.checkbox=lambda *a,**k:False
            st.session_state["tqd3_h1_prepared"]=h1.prepare_gap_review(corpus=corpus)
            st.session_state[result["research_result_id"]+"_decision"]="reject"
            st.button=lambda *a,**k:k.get("key")==result["research_result_id"]+"_draft"
            with patch.dict(sys.modules,{"streamlit":st}),patch.object(reviews,"_resolved_path",return_value=db):
                render_governed_research()
                saved=reviews.list_governed_research_results(db_path=db)[0]
                self.assertEqual(saved["draft"],draft); self.assertEqual(saved["review"]["decision"],"undecided")
                self.assertNotIn(result["research_result_id"]+"_decision",st.session_state)
                self.assertTrue(any(m[0]=="rerun" for m in st.messages))
                st.messages=[]; st.button=lambda *a,**k:k.get("key")==result["research_result_id"]+"_impact"
                render_governed_research()
                self.assertTrue(publication.latest_impact(result["research_result_id"],db_path=db))
                self.assertTrue(any(m[0]=="rerun" for m in st.messages))
                self.assertEqual(reviews.list_governed_research_results(db_path=db)[0]["review"]["decision"],"undecided")

    def test_explicit_confirmation_publish_rerun_and_published_filter(self):
        from taxonomy_discovery.governed_publication_ui import render_governed_review_ledger
        with isolated() as f:
            result,draft,_,_=approved(f)
            db=f.tmp/"h11.sqlite"
            st=FakeStreamlit()
            st.selectbox=lambda *a,**k:"all"
            st.checkbox=lambda *a,**k:True
            st.button=lambda *a,**k:k.get("key")==draft["resolver_draft_id"]+"_publish"
            real_publish=publication.publish_approved_change
            with patch.dict(sys.modules,{"streamlit":st}),patch.object(reviews,"_resolved_path",return_value=db), \
                    patch.object(publication,"publish_approved_change",side_effect=lambda rid,**kw:real_publish(rid,db_path=db,**kw)) as publish:
                render_governed_review_ledger()
                render_governed_review_ledger()
                self.assertEqual(publish.call_count,1)
            self.assertTrue(any(m[0]=="rerun" for m in st.messages))
            self.assertTrue(any(m[0]=="success" and "Published to production" in m[1][0] for m in st.messages))
            st.messages=[]; st.selectbox=lambda *a,**k:"published"
            with patch.dict(sys.modules,{"streamlit":st}),patch.object(reviews,"_resolved_path",return_value=db): render_governed_review_ledger()
            rows=next(m[1][0] for m in st.messages if m[0]=="dataframe")
            self.assertEqual([r["status"] for r in rows],["published"])

    def test_render_and_unconfirmed_click_never_publish(self):
        from taxonomy_discovery.governed_publication_ui import render_governed_review_ledger
        with isolated() as f:
            _,_,_,_=approved(f); db=f.tmp/"h11.sqlite"
            st=FakeStreamlit(); st.selectbox=lambda *a,**k:"approved_pending_publication"
            st.checkbox=lambda *a,**k:False
            with patch.dict(sys.modules,{"streamlit":st}),patch.object(reviews,"_resolved_path",return_value=db),patch.object(publication,"publish_approved_change") as publish:
                render_governed_review_ledger(); render_governed_review_ledger()
                st.button=lambda *a,**k:k.get("key","").endswith("_publish")
                render_governed_review_ledger()
                publish.assert_not_called()

    def test_saved_decision_reruns_and_rereads_persisted_status(self):
        from taxonomy_discovery.taxonomy_evolution_ui import render_governed_research
        with isolated() as f:
            result,_,corpus,_=approved(f); db=f.tmp/"h11.sqlite"
            st=FakeStreamlit()
            st.session_state["tqd3_h1_prepared"]=h1.prepare_gap_review(corpus=corpus)
            st.selectbox=lambda *a,**k:"reject" if k.get("key")==result["research_result_id"]+"_decision" else None
            st.text_input=lambda *a,**k:"TEST"
            st.checkbox=lambda *a,**k:False
            st.button=lambda *a,**k:k.get("key")==result["research_result_id"]+"_review"
            with patch.dict(sys.modules,{"streamlit":st}),patch.object(reviews,"_resolved_path",return_value=db),patch.object(publication,"publish_approved_change") as publish:
                render_governed_research()
                self.assertEqual(reviews.list_governed_research_results(db_path=db)[0]["review"]["decision"],"reject")
                self.assertTrue(any(m[0]=="rerun" for m in st.messages))
                st.button=lambda *a,**k:False; st.messages=[]
                render_governed_research()
                self.assertEqual(publication.review_ledger(db_path=db)[0]["status"],"rejected")
                publish.assert_not_called()

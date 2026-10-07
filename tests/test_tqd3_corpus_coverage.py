"""Coverage and zero-cost backfill using temporary native SQLite fixtures."""
import io
import json
import sqlite3
import unittest
from contextlib import closing, redirect_stdout
from copy import deepcopy
from unittest.mock import patch

from database import job_match_manager as store
from job_discovery.matching import _default_stable_builder, build_profile_evidence_context, current_match_versions
from taxonomy_discovery.corpus_coverage import corpus_coverage, deterministic_backfill, model_required_queue
from tests.tqd3_publication_fixture_support import PublicationFixture


class CorpusCoverageTests(unittest.TestCase):
    def setup_database(self, f):
        self.path = f.tmp/"coverage.sqlite3"
        self.evidence = [{"id":1,"category":"Project","title":"Product dashboard",
            "description":"Built React frontend user interfaces.","skills":["React"],"tools":[],
            "subtitle":"","period":"","impact":"","source_type":"manual","resume_header_tools":[],
            "resume_header_context":[],"created_at":"2026","updated_at":"2026"}]
        self.context = build_profile_evidence_context(self.evidence)
        self.profile = {"required_skills":["React"]}
        self.jobs = {jid:{"id":jid,"title":f"Role {jid}","company":"Fixture","content_hash":f"hash-{jid}",
            "description":f"Hiring engineers for role {jid} to maintain reliable products and collaborate with engineering teams on production systems and high-quality software.\nRequirements\nReact"}
            for jid in range(1,11)}
        self.jobs[5]["description"] = "short"
        store.init_job_match_schema(self.path)
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute("CREATE TABLE discovered_jobs(id INTEGER PRIMARY KEY,title TEXT,company TEXT,description TEXT,content_hash TEXT,lifecycle_status TEXT)")
            for job in self.jobs.values():
                conn.execute("INSERT INTO discovered_jobs VALUES (?,?,?,?,?,?)",(job["id"],job["title"],job["company"],job["description"],job["content_hash"],"active"))
            conn.execute("CREATE TABLE job_description_versions(id INTEGER PRIMARY KEY,raw_text TEXT,jd_profile_json TEXT)")
            for jid in (2,7,8,10):
                conn.execute("INSERT INTO job_description_versions(raw_text,jd_profile_json) VALUES (?,?)",(self.jobs[jid]["description"],json.dumps(self.profile)))
            conn.execute("INSERT INTO job_description_versions(raw_text,jd_profile_json) VALUES (?,?)",(self.jobs[10]["description"],json.dumps({"required_skills":["Python"]})))
            conn.execute("CREATE TABLE user_evidence(id INTEGER,category TEXT,title TEXT,subtitle TEXT,description TEXT,period TEXT,skills_json TEXT,tools_json TEXT,resume_header_tools_json TEXT,resume_header_context_json TEXT,impact TEXT,source_type TEXT,created_at TEXT,updated_at TEXT)")
            e=self.evidence[0]
            conn.execute("INSERT INTO user_evidence VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(e["id"],e["category"],e["title"],"",e["description"],"",json.dumps(e["skills"]),"[]","[]","[]","","manual","2026","2026"))
            conn.commit()
        versions = current_match_versions()
        for jid in (1,3,6,7,8,9):
            job = self.jobs[jid]
            stable = _default_stable_builder(raw_jd_text=job["description"],jd_profile=self.profile,context=self.context) if jid==1 else {}
            store.save_job_match_snapshot(discovered_job_id=jid,job_content_hash=job["content_hash"] if jid not in (8,9) else "old-hash",
                evidence_fingerprint=self.context["evidence_fingerprint"],match_version=versions["match_version"] if jid in (1,7,8,9) else
                "job-match-snapshot-v2.1.0" if jid==3 else "unknown-legacy",scoring_version=versions["scoring_version"] if jid==1 else "old-scorer",
                taxonomy_version=versions["taxonomy_version"] if jid==1 else "old-taxonomy",jd_profile=self.profile,
                evidence_snapshot=self.evidence if jid!=7 else [],stable_analysis=stable,summary={},db_path=self.path)

    def test_exactly_one_state_read_only_and_full_coverage(self):
        with PublicationFixture() as f:
            self.setup_database(f)
            before = self.path.read_bytes()
            with patch.object(store,"init_job_match_schema",side_effect=AssertionError("write")):
                report=corpus_coverage(db_path=self.path)
            self.assertEqual(before,self.path.read_bytes())
            self.assertEqual(report["discovered_jobs"],10)
            self.assertEqual(report["existing_snapshots"],6)
            self.assertEqual(report["replayable_jobs_before"],1)
            self.assertEqual(report["zero_cost_backfillable"],3)
            self.assertEqual(report["model_required"],3)
            self.assertEqual(report["blocked"],3)
            self.assertEqual(report["stale_hash_mismatched"],2)
            self.assertEqual(sum(report["state_counts"].values()),10)
            states={r["discovered_job_id"]:r["status"] for r in report["jobs"]}
            self.assertEqual(states,{1:"replayable_snapshot",2:"cached_inputs_backfillable",3:"stale_snapshot_backfillable",4:"requires_jd_extraction",
                5:"missing_or_invalid_jd",6:"legacy_incompatible",7:"other_blocker",8:"stale_snapshot_backfillable",9:"requires_jd_extraction",10:"other_blocker"})
            f.network_guard.assert_not_called()
            f.model_guard.assert_not_called()

    def test_dry_run_zero_writes_and_no_deterministic_execution(self):
        with PublicationFixture() as f:
            self.setup_database(f)
            before=self.path.read_bytes()
            with patch("taxonomy_discovery.corpus_coverage._default_stable_builder",side_effect=AssertionError("dry run must not score")), \
                    patch.object(store,"save_job_match_snapshot",side_effect=AssertionError("dry run must not save")):
                result=deterministic_backfill(db_path=self.path)
            self.assertEqual((result["would_create"],result["would_reuse"],result["skipped"]),(3,1,6))
            self.assertTrue(result["dry_run"])
            self.assertEqual(self.path.read_bytes(),before)

    def test_explicit_backfill_native_path_provenance_and_idempotency(self):
        with PublicationFixture() as f:
            self.setup_database(f)
            result=deterministic_backfill(db_path=self.path,execute=True)
            self.assertEqual((result["created"],result["reused"]),(3,1))
            self.assertTrue(all(r["discovered_job_id"] in (1,2,3,8) for r in result["jobs"]))
            with closing(sqlite3.connect(self.path)) as conn:
                records=conn.execute("SELECT discovered_job_id,summary_json FROM job_match_snapshots WHERE id>6").fetchall()
            self.assertEqual(len(records),3)
            self.assertTrue(all("deterministic_backfill_provenance" in json.loads(r[1]) for r in records))
            frozen=self.path.read_bytes()
            again=deterministic_backfill(db_path=self.path,execute=True)
            self.assertEqual((again["created"],again["reused"]),(0,4))
            self.assertEqual(frozen,self.path.read_bytes())
            f.network_guard.assert_not_called()
            f.embedding_guard.assert_not_called()
            f.model_guard.assert_not_called()
            self.assertEqual(f.real_registry.read_bytes(),f.real_registry_bytes)

    def test_missing_inputs_and_unknown_legacy_are_never_guessed(self):
        with PublicationFixture() as f:
            self.setup_database(f)
            with closing(sqlite3.connect(self.path)) as conn:
                conn.execute("DELETE FROM user_evidence")
                conn.commit()
            report=corpus_coverage(db_path=self.path)
            self.assertFalse(next(r for r in report["jobs"] if r["discovered_job_id"]==2)["backfill_eligible"])
            self.assertFalse(next(r for r in report["jobs"] if r["discovered_job_id"]==7)["backfill_eligible"])
            missing=f.tmp/"does-not-exist.sqlite3"
            with self.assertRaises(sqlite3.OperationalError):
                corpus_coverage(db_path=missing)
            self.assertFalse(missing.exists())

    def test_bounded_model_queue_no_execution(self):
        with PublicationFixture() as f:
            self.setup_database(f)
            before=self.path.read_bytes()
            report=model_required_queue(db_path=self.path,limit=2)
            self.assertEqual(report["model_required_jobs"],3)
            self.assertEqual(report["estimated_model_analyses"],3)
            self.assertEqual([r["discovered_job_id"] for r in report["jobs"]],[4,6])
            self.assertEqual(report["jobs"][1]["job_state"],"stale")
            for limit in (0,101,-1):
                with self.assertRaises(ValueError):
                    model_required_queue(db_path=self.path,limit=limit)
            self.assertEqual(before,self.path.read_bytes())
            f.model_guard.assert_not_called()
            with closing(sqlite3.connect(self.path)) as conn:
                conn.execute("UPDATE discovered_jobs SET lifecycle_status='expired' WHERE id=4")
                conn.commit()
            active_first=model_required_queue(db_path=self.path,limit=2)
            self.assertEqual([r["discovered_job_id"] for r in active_first["jobs"]],[6,9])
            self.assertEqual(active_first["lifecycle_counts"],{"active":2,"expired":1})

    def test_cached_application_extraction_requires_exact_text_and_compatible_contract(self):
        from database.analysis_cache_manager import ANALYSIS_CACHE_VERSION, ANALYSIS_PIPELINE_CONTRACT_VERSION
        with PublicationFixture() as f:
            self.setup_database(f)
            with closing(sqlite3.connect(self.path)) as conn:
                conn.execute("CREATE TABLE application_analysis_versions(id INTEGER PRIMARY KEY,report_json TEXT,cache_version TEXT,pipeline_contract_version TEXT,status TEXT)")
                for jid,contract in ((4,ANALYSIS_PIPELINE_CONTRACT_VERSION),(9,"unknown")):
                    report={"raw_jd_text":self.jobs[jid]["description"],"jd_profile":self.profile}
                    conn.execute("INSERT INTO application_analysis_versions VALUES (?,?,?,?,?)",(jid,json.dumps(report),ANALYSIS_CACHE_VERSION,contract,"active"))
                conn.commit()
            report=corpus_coverage(db_path=self.path)
            rows={r["discovered_job_id"]:r for r in report["jobs"]}
            self.assertTrue(rows[4]["backfill_eligible"])
            self.assertEqual(rows[4]["profile_source"]["table"],"application_analysis_versions")
            self.assertFalse(rows[9]["backfill_eligible"])
            self.assertEqual(rows[9]["status"],"legacy_incompatible")
            self.assertTrue(rows[9]["model_required"])
            with closing(sqlite3.connect(self.path)) as conn:
                conn.execute("UPDATE discovered_jobs SET description=REPLACE(description,'Hiring engineers','Hiring   engineers') WHERE id=4")
                conn.commit()
            whitespace_only=next(r for r in corpus_coverage(db_path=self.path)["jobs"] if r["discovered_job_id"]==4)
            self.assertTrue(whitespace_only["backfill_eligible"])
            with closing(sqlite3.connect(self.path)) as conn:
                conn.execute("UPDATE discovered_jobs SET description=description || ' Changed substantive requirements',content_hash='changed' WHERE id=4")
                conn.commit()
            changed=next(r for r in corpus_coverage(db_path=self.path)["jobs"] if r["discovered_job_id"]==4)
            self.assertFalse(changed["backfill_eligible"])
            self.assertTrue(changed["model_required"])

    def test_corrupt_snapshot_metadata_or_evidence_fails_closed_per_job(self):
        with PublicationFixture() as f:
            self.setup_database(f)
            with closing(sqlite3.connect(self.path)) as conn:
                conn.execute("UPDATE job_match_snapshots SET stable_analysis_json='[]', evidence_snapshot_json=? WHERE discovered_job_id=3",
                             (json.dumps([{"id":"invalid-id","category":"Project"}]),))
                conn.commit()
            report=corpus_coverage(db_path=self.path)
            self.assertEqual(report["discovered_jobs"],10)
            row=next(r for r in report["jobs"] if r["discovered_job_id"]==3)
            self.assertFalse(row["backfill_eligible"])
            self.assertFalse(row["replayable"])
            self.assertEqual(row["status"],"other_blocker")

    def test_cli_coverage_dry_run_queue_and_execute_only_on_fixture(self):
        from scripts.tqd3_regression_corpus import main
        with PublicationFixture() as f:
            self.setup_database(f)
            out=f.tmp/"report.json"
            before=self.path.read_bytes()
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["coverage","--db-path",str(self.path),"--output",str(out),"--csv",str(f.tmp/"coverage.csv")]),0)
                self.assertEqual(json.loads(out.read_text())["discovered_jobs"],10)
                self.assertEqual(main(["backfill","--db-path",str(self.path),"--dry-run","--output",str(out)]),0)
                self.assertTrue(json.loads(out.read_text())["dry_run"])
                self.assertEqual(main(["model-queue","--db-path",str(self.path),"--limit","2","--output",str(out)]),0)
                self.assertEqual(len(json.loads(out.read_text())["jobs"]),2)
                self.assertEqual(before,self.path.read_bytes())
                self.assertEqual(main(["backfill","--db-path",str(self.path),"--execute","--output",str(out)]),0)
                self.assertEqual(json.loads(out.read_text())["created"],3)

    def test_ui_only_execute_button_can_write(self):
        import sys
        from taxonomy_discovery import corpus_review_ui as ui
        from tests.test_tqd3_publication_ui import FakeStreamlit
        with PublicationFixture() as f:
            self.setup_database(f)
            report=corpus_coverage(db_path=self.path)
            for key, expected in ((None,None),("tqd3_backfill_dry_run",{}),("tqd3_backfill_execute",{"execute":True})):
                st=FakeStreamlit()
                st.columns=lambda n:[st]*n
                st.spinner=lambda *args:st
                st.button=lambda label,**kwargs:kwargs.get("key")==key
                with patch.dict(sys.modules,{"streamlit":st}),patch.object(ui,"corpus_coverage",return_value=report), \
                        patch.object(ui,"deterministic_backfill",return_value={"created":0,"reused":1}) as backfill:
                    ui.render_corpus_coverage()
                    if expected is None:
                        backfill.assert_not_called()
                    else:
                        backfill.assert_called_once_with(**expected)

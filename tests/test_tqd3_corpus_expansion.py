"""F.4 uses real native persistence and matching with fake paid extraction."""
import io
import json
import sqlite3
import unittest
from contextlib import closing, redirect_stdout
from unittest.mock import Mock, patch

from database import jd_library_manager as library, job_match_manager as snapshots
from taxonomy_discovery.corpus_expansion import classify_role, model_plan, model_run, execution_preview
from tests import test_tqd3_corpus_coverage as coverage_tests
from tests.tqd3_publication_fixture_support import PublicationFixture


class ExpansionTests(unittest.TestCase):
    def setup_database(self, f):
        fixture = coverage_tests.CorpusCoverageTests()
        fixture.setup_database(f)
        self.path = fixture.path
        self.profile = fixture.profile
        with closing(sqlite3.connect(self.path)) as conn:
            # This fixture originally has a deliberately minimal versions table.
            conn.execute("ALTER TABLE job_description_versions ADD COLUMN job_description_id INTEGER")
            conn.execute("ALTER TABLE job_description_versions ADD COLUMN source_version_id TEXT")
            conn.execute("ALTER TABLE job_description_versions ADD COLUMN created_at TEXT")
            for jid, title, company in ((4,"Backend Engineer","One"),(6,"Frontend Developer","Two"),(9,"Software Engineer","Three")):
                conn.execute("UPDATE discovered_jobs SET title=?,company=? WHERE id=?",(title,company,jid))
            conn.commit()

    def test_classification_conservative(self):
        cases = {"Backend Engineer":"backend", "Frontend Developer":"frontend", "Fullstack Developer":"fullstack",
            "Product Manager":"non_software", "Biology Engineer":"non_software", "Mechanical Engineer":"non_software",
            "Administrator":"non_software", "Specialist":"ambiguous", "Engineer":"ambiguous", "Data Engineer":"data_engineering"}
        for title, expected in cases.items():
            family, reason = classify_role({"title":title,"description":""})
            self.assertEqual(family,expected)
            self.assertTrue(reason)

    def test_plan_readonly_determinism_diversity_duplicates_and_limit(self):
        with PublicationFixture() as f:
            self.setup_database(f)
            with closing(sqlite3.connect(self.path)) as conn:
                conn.execute("UPDATE discovered_jobs SET content_hash='hash-4',description=(SELECT description FROM discovered_jobs WHERE id=4) WHERE id=6")
                conn.commit()
            original = self.path.read_bytes()
            plan = model_plan(db_path=self.path, limit=25)
            self.assertEqual(plan,model_plan(db_path=self.path, limit=25))
            self.assertEqual(original,self.path.read_bytes())
            self.assertEqual(plan["summary"]["exact_duplicates_excluded"],1)
            self.assertEqual(len(plan["jobs"]),2)
            self.assertEqual(plan["exact_duplicate_groups"][0]["canonical_job_id"],4)
            self.assertEqual(len(plan["summary"]["selected_companies"]),2)
            self.assertEqual(len(plan["summary"]["selected_role_families"]),2)
            for limit in (0,51,True):
                with self.assertRaises(ValueError):
                    model_plan(db_path=self.path,limit=limit)
            f.model_guard.assert_not_called()
            f.network_guard.assert_not_called()

    def test_similar_titles_distinct_content_active_tie_preference(self):
        with PublicationFixture() as f:
            self.setup_database(f)
            with closing(sqlite3.connect(self.path)) as conn:
                conn.execute("UPDATE discovered_jobs SET title='Software Engineer',company='Same' WHERE id IN (4,6,9)")
                conn.execute("UPDATE discovered_jobs SET lifecycle_status='expired' WHERE id=4")
                conn.commit()
            plan=model_plan(db_path=self.path)
            self.assertEqual(len(plan["jobs"]),3)
            self.assertEqual(plan["summary"]["exact_duplicates_excluded"],0)
            self.assertEqual(plan["jobs"][0]["discovered_job_id"],6)

    def test_execute_explicit_fingerprint_versions_and_stale_hash(self):
        with PublicationFixture() as f:
            self.setup_database(f)
            plan=model_plan(db_path=self.path)
            with self.assertRaises(ValueError):
                model_run(plan,db_path=self.path)
            altered=json.loads(json.dumps(plan)); altered["jobs"][0]["title"]="edited"
            with self.assertRaises(ValueError):
                execution_preview(altered,db_path=self.path)
            with patch("taxonomy_discovery.corpus_expansion.current_match_versions",return_value={}):
                with self.assertRaises(ValueError):
                    execution_preview(plan,db_path=self.path)
            with closing(sqlite3.connect(self.path)) as conn:
                conn.execute("UPDATE discovered_jobs SET content_hash='changed' WHERE id=4")
                conn.commit()
            extractor=Mock(return_value=self.profile)
            result=model_run(plan,db_path=self.path,limit=1,execute=True,extractor=extractor)
            self.assertEqual(result["stale_plan_jobs"],1)
            self.assertEqual(extractor.call_count,1)
            self.assertEqual(result["jobs_attempted"],1)
            self.assertEqual(result["jobs_succeeded"],1,result)

    def test_success_failure_isolation_resume_idempotence_and_growth(self):
        with PublicationFixture() as f:
            self.setup_database(f)
            plan=model_plan(db_path=self.path)
            extractor=Mock(side_effect=[self.profile,ValueError("fake provider failed"),self.profile])
            receipts=[]
            result=model_run(plan,db_path=self.path,execute=True,extractor=extractor,receipt_callback=receipts.append)
            self.assertEqual((result["jobs_succeeded"],result["jobs_failed"]),(2,1),result)
            self.assertEqual(result["model_analysis_tasks_attempted"],3)
            self.assertEqual(result["growth"]["newly_replayable_distinct_jobs"],2)
            self.assertIn("execution_preview",receipts[0])
            retry=Mock(return_value=self.profile)
            second=model_run(plan,db_path=self.path,execute=True,extractor=retry)
            self.assertEqual(second["already_completed"],2)
            self.assertEqual(second["jobs_succeeded"],1)
            self.assertEqual(retry.call_count,1)
            original=self.path.read_bytes()
            final=model_run(plan,db_path=self.path,execute=True,extractor=Mock(side_effect=AssertionError("repeat spend")))
            self.assertEqual(final["already_completed"],3)
            self.assertEqual(original,self.path.read_bytes())
            self.assertEqual(f.real_registry.read_bytes(),f.real_registry_bytes)

    def test_extraction_persists_before_failed_matching(self):
        with PublicationFixture() as f:
            self.setup_database(f)
            plan=model_plan(db_path=self.path,limit=1)
            with patch("taxonomy_discovery.corpus_expansion._default_stable_builder",side_effect=ValueError("match failure")):
                failed=model_run(plan,db_path=self.path,execute=True,extractor=Mock(return_value=self.profile))
            self.assertEqual(failed["jobs_failed"],1)
            self.assertIn("jd_cache_identity",failed["jobs"][0])
            retry=Mock(side_effect=AssertionError("must reuse extraction"))
            passed=model_run(plan,db_path=self.path,execute=True,extractor=retry)
            self.assertEqual(passed["jobs_succeeded"],1,passed)
            retry.assert_not_called()

    def test_cli_requires_execute_before_provider_or_writes(self):
        from scripts.tqd3_regression_corpus import main
        with redirect_stdout(io.StringIO()), patch("sys.stderr",new=io.StringIO()):
            with self.assertRaises(SystemExit):
                main(["model-run","--plan","missing.json"])

    def test_ui_rerender_and_explicit_execution(self):
        import sys
        from tests.test_tqd3_publication_ui import FakeStreamlit
        from taxonomy_discovery.corpus_review_ui import render_model_expansion
        fake=FakeStreamlit()
        fake.selectbox=lambda *a,**k:25
        fake.checkbox=lambda *a,**k:False
        with patch.dict(sys.modules,{"streamlit":fake}), patch("taxonomy_discovery.corpus_expansion.model_plan") as plan, \
                patch("taxonomy_discovery.corpus_expansion.model_run") as run:
            render_model_expansion()
            plan.assert_not_called(); run.assert_not_called()

    def test_ui_model_execution_requires_both_confirmation_and_action(self):
        import sys
        from tests.test_tqd3_publication_ui import FakeStreamlit
        from taxonomy_discovery.corpus_review_ui import render_model_expansion
        fake=FakeStreamlit(); fake.selectbox=lambda *a,**k:25
        fake.session_state["tqd3_model_plan"]={"summary":{},"jobs":[]}
        fake.checkbox=lambda *a,**k:False
        fake.button=lambda label,**k:label=="Run bounded JD analysis batch"
        preview={"jobs_remaining":1,"maximum_jd_analysis_tasks":1,"jobs":[]}
        with patch.dict(sys.modules,{"streamlit":fake}), patch("taxonomy_discovery.corpus_expansion.execution_preview",return_value=preview), \
            patch("taxonomy_discovery.corpus_expansion.model_run",return_value={}) as run:
            render_model_expansion(); run.assert_not_called()
            fake.checkbox=lambda *a,**k:True
            render_model_expansion()
            self.assertTrue(run.call_args.kwargs["execute"])
            self.assertEqual(run.call_args.kwargs["limit"],25)

    def test_cli_plan_and_fake_run_receipt(self):
        from scripts.tqd3_regression_corpus import main
        with PublicationFixture() as f:
            self.setup_database(f)
            output=f.tmp/"plan.json"
            with redirect_stdout(io.StringIO()) as printed:
                main(["model-plan","--db-path",str(self.path),"--software-only","--limit","1","--output",str(output)])
                with patch("taxonomy_discovery.corpus_expansion._default_extract_jd_profile",return_value=self.profile) as extract:
                    main(["model-run","--db-path",str(self.path),"--plan",str(output),"--limit","1","--execute"])
            self.assertEqual(extract.call_count,1)
            receipt=json.loads(output.with_suffix(".run.json").read_text())
            self.assertEqual(receipt["jobs_succeeded"],1)
            self.assertIn("maximum_jd_analysis_tasks",printed.getvalue())

    def test_changed_raw_jd_without_metadata_hash_update_is_stale(self):
        with PublicationFixture() as f:
            self.setup_database(f)
            plan=model_plan(db_path=self.path,limit=1)
            jid=plan["jobs"][0]["discovered_job_id"]
            with closing(sqlite3.connect(self.path)) as conn:
                conn.execute("UPDATE discovered_jobs SET description=description||' new content' WHERE id=?",(jid,))
                conn.commit()
            extractor=Mock()
            result=model_run(plan,db_path=self.path,execute=True,extractor=extractor)
            extractor.assert_not_called()
            self.assertEqual(result["stale_plan_jobs"],1)


if __name__ == "__main__":
    unittest.main()

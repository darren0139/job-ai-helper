import json
import sqlite3
import unittest
from copy import deepcopy
from contextlib import closing
from unittest.mock import patch

from job_discovery.matching import _default_stable_builder, build_profile_evidence_context, current_match_versions
from database.job_match_manager import save_job_match_snapshot
from taxonomy_discovery.regression_corpus import build_regression_corpus, export_saved_corpus, corpus_csv, compare_regression_corpus
from tests.tqd3_publication_fixture_support import PublicationFixture


def frozen_snapshot(name="React"):
    evidence = [{"id":1,"category":"Project","title":"Product dashboard",
                 "description":f"Built {name} frontend user interfaces and production applications.","skills":[name],"tools":[]}]
    context = build_profile_evidence_context(evidence)
    text = "Requirements\n" + name
    profile = {"required_skills":[name]}
    stable = _default_stable_builder(raw_jd_text=text,jd_profile=profile,context=context)
    return {"id":1,"discovered_job_id":4,"job_content_hash":"same-hash","evidence_fingerprint":context["evidence_fingerprint"],
            "raw_jd_text":text,"jd_profile":profile,"evidence_snapshot":evidence,"stable_analysis":stable}


class RegressionCorpusTests(unittest.TestCase):
    def test_roundtrip_fields_csv_offline_unchanged_and_no_mutation(self):
        with PublicationFixture() as f:
            snapshot = frozen_snapshot()
            corpus = build_regression_corpus([snapshot])
            frozen = deepcopy(corpus)
            report = compare_regression_corpus(json.loads(json.dumps(corpus)))
            self.assertEqual(report["classification_counts"], {"unchanged":1})
            self.assertEqual(corpus, frozen)
            row = corpus["jobs"][0]["requirements"][0]
            self.assertEqual(row["resolution_source"], "technology_registry")
            self.assertTrue(row["selected_evidence"][0]["evidence_id"])
            self.assertIn("source",row["selected_evidence"][0])
            self.assertIn("React", corpus_csv(corpus))
            self.assertIn("evidence_strength_score", corpus_csv(corpus))
            self.assertEqual(f.real_registry.read_bytes(),f.real_registry_bytes)
            f.network_guard.assert_not_called()
            f.embedding_guard.assert_not_called()
            f.model_guard.assert_not_called()

    def test_read_only_export_hash_matched_jd_and_missing_context_closed(self):
        with PublicationFixture() as f:
            snapshot = frozen_snapshot()
            versions = current_match_versions()
            save_job_match_snapshot(discovered_job_id=4,job_content_hash="same-hash",evidence_fingerprint=snapshot["evidence_fingerprint"],
                match_version=versions["match_version"],scoring_version=versions["scoring_version"],taxonomy_version=versions["taxonomy_version"],
                jd_profile=snapshot["jd_profile"],evidence_snapshot=snapshot["evidence_snapshot"],stable_analysis=snapshot["stable_analysis"],summary={})
            from database.job_match_manager import DB_PATH
            with closing(sqlite3.connect(DB_PATH)) as conn:
                conn.execute("CREATE TABLE discovered_jobs(id INTEGER,content_hash TEXT,description TEXT)")
                conn.execute("INSERT INTO discovered_jobs VALUES (4,?,?)",("same-hash",snapshot["raw_jd_text"]))
                conn.commit()
            before = DB_PATH.read_bytes()
            corpus = export_saved_corpus(db_path=DB_PATH)
            self.assertTrue(corpus["jobs"][0]["replay_available"])
            self.assertEqual(DB_PATH.read_bytes(),before)
            from scripts.tqd3_regression_corpus import main
            frozen_file, csv_file, report_file = f.tmp/"corpus.json", f.tmp/"corpus.csv", f.tmp/"comparison.json"
            self.assertEqual(main(["export","--db-path",str(DB_PATH),"--output",str(frozen_file),"--csv",str(csv_file)]),0)
            self.assertEqual(main(["compare","--corpus",str(frozen_file),"--output",str(report_file)]),0)
            self.assertEqual(json.loads(report_file.read_text())["classification_counts"],{"unchanged":1})
            self.assertTrue(csv_file.exists())
            self.assertEqual(DB_PATH.read_bytes(),before)
            with closing(sqlite3.connect(DB_PATH)) as conn:
                conn.execute("UPDATE discovered_jobs SET content_hash='changed'")
                conn.commit()
            before = DB_PATH.read_bytes()
            unavailable = export_saved_corpus(db_path=DB_PATH)
            self.assertFalse(unavailable["jobs"][0]["replay_available"])
            with patch("taxonomy_discovery.regression_corpus._default_stable_builder",side_effect=AssertionError("must not replay")):
                self.assertFalse(compare_regression_corpus(unavailable)["jobs"][0]["available"])
            self.assertEqual(DB_PATH.read_bytes(),before)
            missing = f.tmp/"missing.sqlite"
            with self.assertRaises(sqlite3.OperationalError):
                export_saved_corpus(db_path=missing)
            self.assertFalse(missing.exists())

    def test_resolution_improvement_has_no_score_or_evidence_creation(self):
        with PublicationFixture() as f:
            snapshot = frozen_snapshot(f.name)
            # This technology has no genuine C++ evidence; registry publication
            # must not create it even though the fixture mentions the technology.
            snapshot["evidence_snapshot"] = [{"id":2,"category":"Skill","title":"Python","description":"Built Python scripts.","skills":["Python"]}]
            context = build_profile_evidence_context(snapshot["evidence_snapshot"])
            snapshot["evidence_fingerprint"] = context["evidence_fingerprint"]
            snapshot["stable_analysis"] = _default_stable_builder(raw_jd_text=snapshot["raw_jd_text"],jd_profile=snapshot["jd_profile"],context=context)
            corpus = build_regression_corpus([snapshot])
            f.approve()
            f.publish()
            report = compare_regression_corpus(corpus)["jobs"][0]
            self.assertEqual(report["classification"],"expected_improvement")
            self.assertTrue(report["requirement_changes"][0]["newly_resolved"])
            self.assertTrue(all(v==0 for v in report["job_score_deltas"].values()))
            self.assertEqual(report["duplicate_credit_violations"],[])

    def test_duplicate_credit_and_newly_unresolved_are_hard_regressions(self):
        with PublicationFixture() as f:
            snapshot = frozen_snapshot()
            corpus = build_regression_corpus([snapshot])
            duplicated = deepcopy(corpus)
            duplicated["jobs"][0]["baseline_stable_analysis"]["canonical_requirements"].append(deepcopy(snapshot["stable_analysis"]["canonical_requirements"][0]))
            self.assertEqual(compare_regression_corpus(duplicated)["jobs"][0]["classification"],"hard_regression/invariant_violation")
            raw = json.loads(f.registry_path.read_text())
            raw["entries"] = [e for e in raw["entries"] if e["technology_id"] != "react"]
            f.registry_path.write_text(json.dumps(raw))
            result = compare_regression_corpus(corpus)["jobs"][0]
            self.assertTrue(result["requirement_changes"][0]["newly_unresolved"])
            self.assertEqual(result["classification"],"hard_regression/invariant_violation")

    def test_score_increase_requires_review(self):
        with PublicationFixture():
            snapshot = frozen_snapshot()
            corpus = build_regression_corpus([snapshot])
            changed = deepcopy(snapshot["stable_analysis"])
            changed["deterministic_alignment_score"] += 5
            with patch("taxonomy_discovery.regression_corpus._default_stable_builder",return_value=changed):
                result = compare_regression_corpus(corpus)["jobs"][0]
            self.assertEqual(result["classification"],"requires_review")
            self.assertEqual(result["job_score_deltas"]["deterministic_alignment_score"],5)

    def test_missing_evidence_and_frozen_context_tampering_closed(self):
        with PublicationFixture():
            snapshot = frozen_snapshot()
            snapshot.pop("evidence_snapshot")
            self.assertFalse(build_regression_corpus([snapshot])["jobs"][0]["replay_available"])
            missing_baseline = frozen_snapshot()
            missing_baseline.pop("stable_analysis")
            self.assertFalse(build_regression_corpus([missing_baseline])["jobs"][0]["replay_available"])
            corpus = build_regression_corpus([frozen_snapshot()])
            corpus["jobs"][0]["frozen_inputs"]["context"]["raw_resume_text"] += " invented evidence"
            self.assertEqual(compare_regression_corpus(corpus)["jobs"][0]["classification"],"hard_regression/invariant_violation")

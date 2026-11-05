"""Deterministic read-only Stage 0 contract tests; no production DB or network."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from unittest.mock import patch
from datetime import datetime, timezone
from pathlib import Path

from job_agent.dry_run import read_job_finder_states, build_read_only_plan
from job_agent.planner import _safe_https_url, plan_jobs
from job_agent.planner import RANKING_VERSION

NOW = datetime(2026, 11, 4, tzinfo=timezone.utc)
VERSIONS = {"match_version": "match-test|registry=v1", "scoring_version": "score-test", "taxonomy_version": "taxonomy-test"}


def job(jid=1, **kw):
    row = {
        "id": jid, "source": "greenhouse", "source_job_id": f"example-{jid}",
        "company": "Sample", "title": "Developer", "description": "Write safe Python code. " * 12,
        "content_hash": f"hash-{jid}", "source_url": f"https://boards.greenhouse.io/sample/jobs/{jid}",
        "apply_url": "", "lifecycle_status": "active", "expires_at": "",
    }
    row.update(kw)
    return row


def state(jid=1, score=60, **kw):
    snap = {"id": jid + 100, "discovered_job_id": jid,
            "job_content_hash": f"hash-{jid}", "evidence_fingerprint": "evidence-v1",
            **VERSIONS,
            "summary": {"ranking_eligible": True, "ranking_version": RANKING_VERSION,
                        "deterministic_alignment_score": score, "important_gap_count": 0}}
    snap.update(kw)
    return {"status": "current", "snapshot": snap}


def plan(jobs, states, **kw):
    return plan_jobs(jobs, states, evidence_fingerprint="evidence-v1",
                     versions=VERSIONS, evidence_item_count=4, now_utc=NOW,
                     ranking_sort_key=lambda snap, discovered_job_id: (int(snap["summary"].get("deterministic_alignment_score", 0)), -discovered_job_id),
                     **kw)


class PurePlannerTests(unittest.TestCase):
    def test_current_eligible_is_review_candidate_not_application(self):
        value = plan([job()], {1: state()})
        self.assertEqual(value["counts"]["review_candidate"], 1)
        self.assertTrue(value["dry_run"])
        self.assertTrue(value["no_application_actions"])
        self.assertEqual(value["rows"][0]["status"], "review_candidate")

    def test_match_identity_components_are_all_required(self):
        for field, change in [("job_content_hash", "old"), ("evidence_fingerprint", "old"),
                              ("match_version", "old"), ("scoring_version", "old"),
                              ("taxonomy_version", "old"), ("discovered_job_id", 999)]:
            with self.subTest(field=field):
                got = plan([job()], {1: state(**{field: change})})
                self.assertEqual(got["rows"][0]["reason_codes"], ["snapshot_identity_mismatch"])
                self.assertEqual(got["counts"]["review_candidate"], 0)

    def test_stale_none_ineligible_and_version_mismatch_hold(self):
        for candidate, expected in [({"status": "stale"}, "match_stale"),
                                    ({"status": "none"}, "match_none"),
                                    (state(summary={"ranking_eligible": False, "ranking_version": RANKING_VERSION}), "ranking_not_eligible"),
                                    (state(summary={"ranking_eligible": True, "ranking_version": "old"}), "ranking_version_mismatch")]:
            with self.subTest(expected=expected):
                got = plan([job()], {1: candidate})
                self.assertIn(expected, got["rows"][0]["reason_codes"])
                self.assertEqual(got["counts"]["review_candidate"], 0)

    def test_invalid_url_blocks(self):
        urls = ["http://boards.greenhouse.io/a", "https://127.0.0.1/", "https://localhost/",
                "https://greenhouse.io@evil.com/a", "https://greenhouse.io.evil.com/a",
                "javascript:alert(1)", "https://evil.com", "https://boards.greenhouse.io:8443/a"]
        for url in urls:
            with self.subTest(url=url):
                got = plan([job(apply_url=url, source_url="")], {1: state()})
                self.assertEqual(got["counts"]["review_candidate"], 0)
                self.assertEqual(got["counts"]["reject"], 1)

    def test_applies_safe_source_fallback_for_external_application(self):
        got = plan([job(apply_url="https://company.example/apply")], {1: state()})
        self.assertEqual(got["rows"][0]["status"], "review_candidate")
        self.assertIn("apply_destination_unapproved_using_source", got["rows"][0]["reason_codes"])

    def test_hidden_removed_expired_and_missing_evidence_hold(self):
        hidden = {"rule_type": "company", "value": "Sample", "enabled": 1}
        for row, extra, reason in [
            (job(), {"hide_rules": [hidden]}, "hidden_by_job_finder_rule"),
            (job(lifecycle_status="removed"), {}, "job_not_active"),
            (job(expires_at="2026-10-01T00:00:00Z"), {}, "job_expired"),
            (job(description="short"), {}, "insufficient_job_content"),
        ]:
            with self.subTest(reason=reason):
                got = plan([row], {1: state()}, **extra)
                self.assertEqual(got["counts"]["review_candidate"], 0)
                self.assertIn(reason, got["rows"][0]["reason_codes"])
        got = plan_jobs([job()], {1: state()}, evidence_fingerprint="", versions=VERSIONS,
                        evidence_item_count=0, now_utc=NOW,
                        ranking_sort_key=lambda snap, discovered_job_id: (0, -discovered_job_id))
        self.assertEqual(got["counts"]["review_candidate"], 0)

    def test_duplicate_id_source_identity_and_url_skip(self):
        examples = [job(1), job(1), job(2, source_job_id="example-1"),
                    job(3, source_url="https://boards.greenhouse.io/sample/jobs/1")]
        got = plan(examples, {1: state(1), 2: state(2), 3: state(3)})
        self.assertEqual(got["counts"], {"review_candidate": 1, "hold": 0, "reject": 0, "skip": 3})

    def test_uses_jobfinder_best_match_order_and_queue_limit(self):
        got = plan([job(1), job(2), job(3)],
                   {1: state(1, 10), 2: state(2, 80), 3: state(3, 40)}, max_candidates=2)
        self.assertEqual([r["discovered_job_id"] for r in got["rows"][:2]], [2, 3])
        self.assertEqual(got["counts"]["hold"], 1)
        self.assertIn("review_queue_limit", got["rows"][2]["reason_codes"])

    def test_is_deterministic_and_does_not_mutate_inputs(self):
        data = [job(1), job(2)]
        states = {1: state(1), 2: state(2)}
        original = json.dumps((data, states), sort_keys=True)
        first = plan(data, states)
        self.assertEqual(first, plan(data, states))
        self.assertEqual(original, json.dumps((data, states), sort_keys=True))

    def test_host_allowlist_requires_real_domain_suffix(self):
        good, _ = _safe_https_url("https://job-boards.greenhouse.io/acme/jobs/5#frag", ("greenhouse.io",))
        self.assertEqual(good, "https://job-boards.greenhouse.io/acme/jobs/5")
        bad, _ = _safe_https_url("https://job-boards.greenhouse.io.fake.tld/a", ("greenhouse.io",))
        self.assertEqual(bad, "")


class ReadOnlyLoaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "jobs.sqlite"
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.executescript("""
                CREATE TABLE discovered_jobs (id INTEGER PRIMARY KEY, source TEXT,source_job_id TEXT,
                company TEXT,title TEXT,description TEXT,content_hash TEXT,source_url TEXT,apply_url TEXT,
                lifecycle_status TEXT,expires_at TEXT,last_seen_at TEXT);
                CREATE TABLE job_match_snapshots (id INTEGER PRIMARY KEY,discovered_job_id INTEGER,
                job_content_hash TEXT,evidence_fingerprint TEXT,match_version TEXT,scoring_version TEXT,
                taxonomy_version TEXT,summary_json TEXT);
                CREATE TABLE job_discovery_hide_rules (id INTEGER PRIMARY KEY,rule_type TEXT,value TEXT,normalized_value TEXT,enabled INTEGER);
            """)
            for j in (job(1), job(2), job(3)):
                conn.execute("INSERT INTO discovered_jobs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                             tuple(j[k] for k in ("id", "source", "source_job_id", "company", "title", "description", "content_hash", "source_url", "apply_url", "lifecycle_status", "expires_at")) + ("2026-11-04",))
            a = state(1)["snapshot"]
            b = state(2)["snapshot"]
            b["evidence_fingerprint"] = "old-fingerprint"
            for s in (a, b):
                conn.execute("INSERT INTO job_match_snapshots VALUES (?,?,?,?,?,?,?,?)",
                             tuple(s[k] for k in ("id", "discovered_job_id", "job_content_hash", "evidence_fingerprint", "match_version", "scoring_version", "taxonomy_version")) + (json.dumps(s["summary"]),))
            conn.execute("INSERT INTO job_discovery_hide_rules VALUES (1,'company','Sample','sample',0)")

    def test_reads_current_stale_none_without_modifying_database(self):
        before = self.db.read_bytes()
        jobs, states, hidden = read_job_finder_states(self.db,
            evidence_fingerprint="evidence-v1", versions=VERSIONS)
        self.assertEqual(len(jobs), 3)
        self.assertEqual([states[i]["status"] for i in (1, 2, 3)], ["current", "stale", "none"])
        self.assertEqual(hidden, [])
        self.assertEqual(self.db.read_bytes(), before)

    def test_bounded_loader_prioritizes_active_before_newer_expired(self):
        # Regression: later refresh of an expired source must not crowd all
        # active records out of a max_jobs-limited read-only sampling window.
        with closing(sqlite3.connect(self.db)) as conn, conn:
            for jid in range(4, 10):
                j = job(jid, lifecycle_status="expired",
                        expires_at="2026-10-01T00:00:00+00:00")
                conn.execute(
                    "INSERT INTO discovered_jobs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    tuple(j[k] for k in (
                        "id", "source", "source_job_id", "company", "title",
                        "description", "content_hash", "source_url", "apply_url",
                        "lifecycle_status", "expires_at")) + ("2026-11-05",),
                )
        original = self.db.read_bytes()
        jobs, states, _ = read_job_finder_states(
            self.db, evidence_fingerprint="evidence-v1", versions=VERSIONS,
            max_jobs=2,
        )
        self.assertEqual([row["id"] for row in jobs], [3, 2])
        self.assertEqual([states[3]["status"], states[2]["status"]],
                         ["none", "stale"])
        self.assertEqual(self.db.read_bytes(), original)

    def test_integrated_read_only_dry_run_uses_existing_snapshots(self):
        before = self.db.read_bytes()
        with patch("job_agent.dry_run.current_profile_identity", return_value=("evidence-v1", 4, VERSIONS)):
            result = build_read_only_plan(
                self.db, max_jobs=3, now_utc=NOW,
                ranking_sort_key=lambda snap, discovered_job_id: (int(snap["summary"].get("deterministic_alignment_score", 0)), -discovered_job_id),
            )
        self.assertEqual(result["counts"], {"review_candidate": 1, "hold": 2, "reject": 0, "skip": 0})
        self.assertEqual(self.db.read_bytes(), before)

    def test_fails_closed_on_missing_db_and_empty_schema(self):
        with self.assertRaises(FileNotFoundError):
            read_job_finder_states(self.db.parent / "missing.sqlite", evidence_fingerprint="x", versions=VERSIONS)
        empty = self.db.parent / "empty.sqlite"
        with closing(sqlite3.connect(empty)):
            pass
        with self.assertRaises(ValueError):
            read_job_finder_states(empty, evidence_fingerprint="x", versions=VERSIONS)


if __name__ == "__main__":
    unittest.main()

from collections import Counter
from contextlib import closing
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3
import unittest
from unittest.mock import patch

from analysis_stability import jd_knowledge_preview as knowledge


class ReviewedJDReleaseTests(unittest.TestCase):
    def test_bundle_has_all_review_decisions_and_verified_parent_rows(self):
        sources = knowledge._reviewed_sources()
        self.assertEqual(len(sources), 30)
        reviews = [item["number"] for source in sources.values() for item in source["reviews"]]
        self.assertEqual(sorted(reviews), list(range(1, 420)))
        outcomes = Counter(row["understanding"] for source in sources.values()
                           for row in source["requirements"])
        self.assertEqual(outcomes["COMPLETE_GENERIC_SOURCE_PARENT"], 20)

    def test_hash_exact_match_returns_copy_and_edits_never_inherit_review(self):
        raw = "Requirements\nDevelop REST APIs."
        pinned = {"requirements": [], "reviews": [{"number": 1}]}
        with patch.object(knowledge, "_reviewed_sources", return_value={
                hashlib.sha256(raw.encode()).hexdigest(): pinned}):
            result = knowledge.build_jd_knowledge(raw)
            result["reviews"].clear()
            self.assertTrue(knowledge.build_jd_knowledge(raw)["reviews"])
            self.assertFalse(knowledge.build_jd_knowledge(raw + "\n")["reviews"])

    def test_bundle_integrity_accepts_git_line_endings_and_rejects_content_drift(self):
        payload = knowledge.BUNDLE.read_bytes()
        self.addCleanup(knowledge._reviewed_sources.cache_clear)
        with patch.object(knowledge, "BUNDLE") as bundle:
            knowledge._reviewed_sources.cache_clear()
            bundle.read_bytes.return_value = payload.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
            self.assertEqual(len(knowledge._reviewed_sources()), 30)
            knowledge._reviewed_sources.cache_clear()
            bundle.read_bytes.return_value = payload + b" "
            with self.assertRaisesRegex(ValueError, "integrity"):
                knowledge._reviewed_sources()

    def test_source_loader_requires_exact_version_without_mutation(self):
        with TemporaryDirectory() as directory:
            database = Path(directory) / "fixture.db"
            with closing(sqlite3.connect(database)) as conn, conn:
                conn.executescript("""
                    CREATE TABLE applications(id INTEGER);
                    CREATE TABLE application_job_links(application_id INTEGER,
                        job_description_id INTEGER, source_version_id TEXT);
                    CREATE TABLE job_description_versions(job_description_id INTEGER,
                        source_version_id TEXT, raw_text TEXT);
                    INSERT INTO applications VALUES (154);
                    INSERT INTO application_job_links VALUES (154, 3, 'pinned');
                    INSERT INTO job_description_versions VALUES (3, 'latest', 'Other source');
                    INSERT INTO job_description_versions VALUES (3, 'pinned', 'Original source');
                """)
            before = database.read_bytes()
            self.assertEqual(knowledge.load_pinned_jd(154, database), "Original source")
            with self.assertRaisesRegex(ValueError, "unique pinned"):
                knowledge.load_pinned_jd(152, database)
            self.assertEqual(database.read_bytes(), before)

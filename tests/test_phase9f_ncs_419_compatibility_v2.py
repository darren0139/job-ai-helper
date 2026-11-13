"""NCS formatting + immutable 419 exact-source compatibility regressions.

Fixtures do not create or update a user database. Optional live-source tests
open SQLite with mode=ro/query_only and explicitly SKIP when no exact source.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch

from analysis_stability import reviewed_jd_exclusions as reviewed
from analysis_stability.stable_evidence_scoring import (
    _REVIEW419_LEGACY_PARSER,
    _split_safe_independent_and_pair,
    canonicalise_requirements,
)
NCS_JD = "Company: NCS\n\nJob Description\n\nYour role is only the beginning\n\nJoin NCS and experience a collaborative work environment where you can develop and grow your career through well-defined career tracks.\n\nAs part of our Nucleus Graduate Programme, you'll have the opportunity to work on impactful projects with a team that shares your passion for making a difference in the world.\n\nOur comprehensive training, professional coaching, and technical expertise will help you attain a Master of Technology with NUS-ISS or industry-recognized certifications.\n\nAt NCS, we are committed to empowering our people to achieve their fullest potential and create an extraordinary future together.\n\nAre you excited about the opportunity to tackle complex problems and develop solutions that make a real difference in people's lives? Do you thrive in a fast-paced, dynamic environment where you're encouraged to take risks and think outside the box? Are you looking to make an impact and contribute to the development of innovative software solutions?\n\nWhat will you do?\n\nPartner with stakeholders to understand business and system requirements\n\nDevelop and enhance software applications to meet functional and technical specifications\n\nContinually improve and maintain software applications\n\nExecute unit, integration, system and user acceptance testing\n\nUsing configuration management, integration and build automation tools to deploy applications\n\nIdentify opportunities and suggest recommendations for system improvement\n\nQualifications\n\nThe ideal candidate should possess:\n\nProficiency in one or more frontend framework (HTML5/Angular/React JS)\n\nProficiency in one or more backend languages (Java/.NET/Python/PHP)\n\nProficiency in database will be an added advantage\n\nExperience in frontend and backend web application development will be an added advantage\n\nDegree in Computer Science or related Engineering fields\n\nRecent graduates with up to 2 years of working experience.\n"

# Exact 419 scopes proven to match their pre-NCS original scope in the
# 2026-11-13 before/after attribution audit. Do not change these hashes.
NEWLY_DRIFTED_SOURCES = frozenset({
    "122ac0ad539a4ed24f864765572e7a6ea4854c824e0512f7e3aa80a490a5067e",
    "376f0712ef93b7f6a012e0cd1ad55d8108ba98f2b7e6e4786e1c5091e5ab273a",
    "505f49dde53ac88721429a299e194d2ae66bc2b8334b7a512ed8131d115ba817",
    "e87e63390b703809f1c88f529f2d81f41ea7750b40a5058ca417b14904b56cfd",
})


def _scope_text(raw, profile):
    return canonicalise_requirements(profile, raw)["requirements"]


def _source_candidates(db: Path):
    with sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True) as conn:
        conn.execute("PRAGMA query_only = ON")
        names = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        for table in ("job_description_versions", "job_descriptions"):
            if table not in names:
                continue
            fields = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            if not {"raw_text", "jd_profile_json"}.issubset(fields):
                continue
            for raw, serialized in conn.execute(f"SELECT raw_text, jd_profile_json FROM {table}"):
                if not isinstance(raw, str) or not raw:
                    continue
                sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()
                if sha not in NEWLY_DRIFTED_SOURCES:
                    continue
                try:
                    profile = json.loads(serialized) if serialized else {}
                except (ValueError, TypeError):
                    continue
                if isinstance(profile, dict):
                    yield sha, raw, profile


class NCSFormattingAnd419CandidateTests(unittest.TestCase):
    def test_original_and_single_newline_ncs_have_same_twelve_requirements(self):
        inputs = {
            "original": NCS_JD,
            "crlf": NCS_JD.replace("\n", "\r\n"),
            "single_newline": "\n".join(line for line in NCS_JD.splitlines() if line.strip()) + "\n",
            "extra_paragraphs": NCS_JD.replace("\n\n", "\n\n\n"),
        }
        baseline = None
        for label, text in inputs.items():
            with self.subTest(variant=label):
                rows = _scope_text(text, {})
                keys = [(row["requirement_id"], row["importance"]) for row in rows]
                self.assertEqual(12, len(rows))
                self.assertTrue(any("Identify opportunities and suggest recommendations" in row["text"] for row in rows))
                self.assertFalse(any("your role is only the beginning" in row["text"].lower() for row in rows))
                self.assertTrue(any("Java/.NET/Python/PHP" in row["text"] for row in rows))
                self.assertTrue(any("Continually improve and maintain" in row["text"] for row in rows))
                if baseline is None:
                    baseline = keys
                else:
                    self.assertEqual(baseline, keys)

    def test_legacy_parser_is_only_active_with_authenticated_review_candidate(self):
        sample = "Responsibilities\nContinually improve and maintain software applications"
        modern = _scope_text(sample, {})
        self.assertEqual(1, len(modern))
        self.assertFalse(_REVIEW419_LEGACY_PARSER.get())
        self.assertFalse(reviewed.reviewed_exact_source_legacy_parser_active(sample))
        # Stub candidate selection, NOT any production manifest or source hash.
        with patch.object(reviewed, "_selected", return_value=({"id": "synthetic"},)):
            historical = _scope_text(sample, {})
            self.assertEqual(2, len(historical))
            self.assertTrue(any(row["text"] == "Continually improve" for row in historical))
        self.assertFalse(_REVIEW419_LEGACY_PARSER.get())
        self.assertEqual(modern, _scope_text(sample, {}))

    def test_419_manifest_integrity_and_exact_source_membership(self):
        manifest = reviewed._manifest()  # Verifies its pinned content hash.
        self.assertEqual(16, sum(len(v) for v in manifest["sources"].values()))
        self.assertEqual(10, len(manifest["sources"]))
        self.assertTrue(NEWLY_DRIFTED_SOURCES.issubset(manifest["sources"]))
        self.assertTrue(NEWLY_DRIFTED_SOURCES.issubset(manifest["scopes"]))
        self.assertFalse(_REVIEW419_LEGACY_PARSER.get())

    def test_four_newly_drifted_review_scopes_remain_exactly_replayable(self):
        db = Path("data/applications.db")
        if not db.is_file():
            self.skipTest("Local SQLite JD sources unavailable; production 419 fixture still verified")
        sources = {}
        for sha, raw, profile in _source_candidates(db):
            sources.setdefault(sha, (raw, profile))
        if not NEWLY_DRIFTED_SOURCES.issubset(sources):
            self.skipTest("Not all four exact original reviewed JD sources are present")
        manifest = reviewed._manifest()
        for sha in sorted(NEWLY_DRIFTED_SOURCES):
            raw, profile = sources[sha]
            with self.subTest(source_sha=sha):
                with reviewed.reviewed_exclusions_candidate():
                    rows = _scope_text(raw, profile)
                    expected = manifest["scopes"][sha]
                    self.assertEqual(
                        expected["original_requirement_scope_sha256"],
                        reviewed.requirement_scope_sha256(rows),
                    )
                    filtered = reviewed.apply_reviewed_exclusions(raw, {"requirements": rows})
                    self.assertEqual(
                        expected["effective_requirement_scope_sha256"],
                        reviewed.requirement_scope_sha256(filtered["requirements"]),
                    )
                    self.assertEqual(
                        len(manifest["sources"][sha]),
                        len(filtered["filtered_non_requirement_rows"]),
                    )
                self.assertFalse(_REVIEW419_LEGACY_PARSER.get())

    def test_missing_candidate_context_does_not_activate_419_compatibility(self):
        manifest = reviewed._manifest()
        sha = next(iter(NEWLY_DRIFTED_SOURCES))
        self.assertIn(sha, manifest["sources"])
        # Exact hash presence alone never switches normal parsing.
        self.assertFalse(reviewed.reviewed_exact_source_legacy_parser_active("not the original JD"))
        self.assertFalse(_REVIEW419_LEGACY_PARSER.get())


if __name__ == "__main__":
    unittest.main()


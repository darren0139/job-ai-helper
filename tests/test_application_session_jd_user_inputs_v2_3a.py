from __future__ import annotations

from contextlib import ExitStack, contextmanager
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from analysis_stability.stable_evidence_scoring import (
    compute_deterministic_alignment,
)
from database.analysis_cache_manager import (
    activate_analysis_snapshot,
    build_analysis_input_fingerprint,
    save_analysis_snapshot,
)
from database import db_manager
from database import jd_library_manager as jd_library_manager
from tailoring.jd_user_input_overrides import (
    JD_USER_OVERRIDE_POLICY_VERSION,
    PREFERRED_REQUIREMENTS_HELP,
    PREFERRED_REQUIREMENTS_LABEL,
    apply_application_session_jd_user_inputs,
    apply_preferred_requirement_overrides_to_profile,
    canonical_jd_profile_for_application_session,
    normalise_requirement_override_lines,
    preferred_requirement_override_cache_identity,
)


ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def _forbid_paid_calls():
    """Make a deterministic 2.3a test fail on a model or embedding call."""
    def unexpected(*_args, **_kwargs):
        raise AssertionError("unexpected paid/model call")

    with ExitStack() as stack:
        stack.enter_context(patch("llm.completion", unexpected))
        stack.enter_context(
            patch("llm._run_completion_with_retries", unexpected)
        )
        stack.enter_context(
            patch("rag.jd_chroma_rag._get_chroma_client", unexpected)
        )
        stack.enter_context(
            patch("rag.jd_chroma_rag.get_chroma_collection", unexpected)
        )
        stack.enter_context(patch("rag.jd_chroma_rag.embed_texts", unexpected))
        stack.enter_context(patch("rag.jd_chroma_rag.embedding", unexpected))
        stack.enter_context(
            patch("rag.capability_taxonomy_rag._embed_texts", unexpected)
        )
        stack.enter_context(
            patch("rag.capability_taxonomy_rag._collection", unexpected)
        )
        yield


def _report() -> dict:
    return {
        "jd_profile": {
            "company": "Parsed Co",
            "job_title": "Software Engineer",
            "location": "Singapore",
            "required_skills": ["Experience with Kotlin", "React"],
            "preferred_skills": [],
            "responsibilities": [],
            "soft_skills": [],
            "tools_technologies": [],
            "deal_breakers": [],
        },
        "keyword_match": {"present": [], "missing": []},
        "resume_profile": {},
        "bullets": {"bullet_quality_avg": 80},
        "structure": {"structure_score": 100},
    }


BONUS_REQUIREMENTS = [
    "Good foundation in linear algebra, calculus and geometry",
    "Understanding and familiarity with 3D Data Structures/Algorithms",
    "Experience working with OpenGLand/or Vulkan",
    "Experience working with Android app development and Kotlin",
    "Familiarity with Nvidia CUDA",
]


def _full_raw_jd_with_bonus_requirements() -> str:
    """App-127-style JD with natural preferred ownership from its heading."""
    return "\n".join(
        [
            "Requirements and Skills",
            "Build reliable APIs",
            "Bonus Requirements and Skills",
            *(f"- {item}" for item in BONUS_REQUIREMENTS),
        ]
    )


class JDUserInputOverrideUnitTests(unittest.TestCase):
    def test_override_lines_remove_bullets_and_dedupe(self) -> None:
        self.assertEqual(
            normalise_requirement_override_lines(
                "• Kotlin\n- Android\n1. Kotlin\n\n"
            ),
            ["Kotlin", "Android"],
        )

    def test_exact_profile_requirement_moves_to_preferred(self) -> None:
        profile, diagnostics = apply_preferred_requirement_overrides_to_profile(
            {
                "required_skills": ["Experience with Kotlin", "React"],
                "preferred_skills": [],
            },
            ["Experience with Kotlin"],
        )
        self.assertEqual(profile["required_skills"], ["React"])
        self.assertEqual(profile["preferred_skills"], ["Experience with Kotlin"])
        self.assertEqual(diagnostics["matched_override_count"], 1)

    def test_non_exact_short_text_stays_out_of_profile_reclassification(self) -> None:
        profile, diagnostics = apply_preferred_requirement_overrides_to_profile(
            {
                "required_skills": ["Experience with native Android development"],
                "preferred_skills": [],
            },
            ["Android"],
        )
        self.assertEqual(
            profile["required_skills"],
            ["Experience with native Android development"],
        )
        self.assertEqual(profile["preferred_skills"], ["Android"])
        # This helper only transforms the effective profile.  The public
        # application-level path accepts this input as a local supplement.
        self.assertEqual(diagnostics["unmatched_preferred_overrides"], ["Android"])

    def test_exact_override_has_highest_canonical_importance_precedence(self) -> None:
        with _forbid_paid_calls():
            result = apply_application_session_jd_user_inputs(
                _report(),
                raw_jd_text="",
                raw_resume_text="Experience with Kotlin",
                company="Override Co",
                preferred_requirements=["Experience with Kotlin"],
            )
        kotlin = next(
            row
            for row in result["stable_analysis"]["canonical_requirements"]
            if row["text"] == "Experience with Kotlin"
        )
        react = next(
            row
            for row in result["stable_analysis"]["canonical_requirements"]
            if row["text"] == "React"
        )
        self.assertEqual(kotlin["importance"], "preferred")
        self.assertEqual(kotlin["importance_source"], "user_override")
        self.assertEqual(react["importance"], "required")
        self.assertEqual(result["jd_profile"]["company"], "Override Co")
        self.assertEqual(
            result["meta"]["jd_user_inputs"]["policy_version"],
            JD_USER_OVERRIDE_POLICY_VERSION,
        )
        expected_score = compute_deterministic_alignment(
            result["stable_analysis"]["canonical_requirements"],
            bullet_quality_score=80,
            structure_score=100,
        )
        self.assertEqual(
            result["stable_analysis"]["deterministic_alignment_score"],
            expected_score["deterministic_alignment_score"],
        )

    def test_clearing_override_restores_original_profile_and_stable_analysis(self) -> None:
        with _forbid_paid_calls():
            overridden = apply_application_session_jd_user_inputs(
                _report(),
                raw_jd_text="",
                raw_resume_text="Candidate résumé",
                preferred_requirements=["Experience with Kotlin"],
            )
            cleared = apply_application_session_jd_user_inputs(
                overridden,
                raw_jd_text="",
                raw_resume_text="Candidate résumé",
                preferred_requirements=[],
            )
        kotlin = next(
            row
            for row in cleared["stable_analysis"]["canonical_requirements"]
            if row["text"] == "Experience with Kotlin"
        )
        self.assertEqual(kotlin["importance"], "required")
        self.assertNotIn("importance_source", kotlin)
        self.assertEqual(
            cleared["jd_profile"]["required_skills"],
            ["Experience with Kotlin", "React"],
        )
        self.assertEqual(cleared["jd_profile"]["preferred_skills"], [])
        self.assertNotIn(
            "jd_user_override_policy_version", cleared["stable_analysis"]
        )

    def test_blank_metadata_restores_original_extracted_values(self) -> None:
        cached = _report()
        cached["jd_profile"].update(
            {
                "company": "Old User Override",
                "job_title": "Old User Role",
                "location": "Old User Location",
            }
        )
        cached["meta"] = {
            "jd_user_inputs": {
                "original_extracted_metadata": {
                    "company": "Parsed Co",
                    "job_title": "Software Engineer",
                    "location": "Singapore",
                }
            }
        }
        result = apply_application_session_jd_user_inputs(
            cached,
            raw_jd_text="JD",
            raw_resume_text="Résumé",
        )
        self.assertEqual(result["jd_profile"]["company"], "Parsed Co")
        self.assertEqual(result["jd_profile"]["job_title"], "Software Engineer")
        self.assertEqual(result["jd_profile"]["location"], "Singapore")

    def test_override_cache_identity_is_order_independent_and_separated(self) -> None:
        kotlin_react = preferred_requirement_override_cache_identity(
            ["Kotlin", "React"]
        )
        react_kotlin = preferred_requirement_override_cache_identity(
            ["React", "Kotlin"]
        )
        android = preferred_requirement_override_cache_identity(["Android"])
        self.assertEqual(kotlin_react, react_kotlin)
        self.assertNotEqual(kotlin_react, android)

        common = {
            "resume_text": "Candidate résumé",
            "jd_text": "Example JD",
            "degree": "IMGD",
            "actual_page_count": 1,
            "model_id": "analysis-model",
        }
        first = build_analysis_input_fingerprint(
            **common,
            retrieval_config={"jd_user_override_identity": kotlin_react},
        )
        reordered = build_analysis_input_fingerprint(
            **common,
            retrieval_config={"jd_user_override_identity": react_kotlin},
        )
        changed = build_analysis_input_fingerprint(
            **common,
            retrieval_config={"jd_user_override_identity": android},
        )
        self.assertEqual(first, reordered)
        self.assertNotEqual(first, changed)
        self.assertEqual(
            kotlin_react["policy_version"],
            "application-session-jd-user-overrides-v2",
        )
        self.assertNotEqual(kotlin_react["policy_version"], "application-session-jd-user-overrides-v1")

    def test_full_raw_jd_applies_all_exact_bonus_preferences_to_atomic_rows(self) -> None:
        """Reproduces App 122: whole parent texts must override atomic rows."""
        with _forbid_paid_calls():
            result = apply_application_session_jd_user_inputs(
                _report(),
                raw_jd_text=_full_raw_jd_with_bonus_requirements(),
                raw_resume_text="Candidate résumé",
                preferred_requirements=BONUS_REQUIREMENTS,
            )

        rows = result["stable_analysis"]["canonical_requirements"]
        heading_texts = {
            "Requirements and Skills",
            "Bonus Requirements and Skills",
        }
        self.assertFalse(
            heading_texts
            & {str(row.get("text") or "") for row in rows}
        )
        self.assertFalse(
            any(
                str(merge.get("kept_text") or "") in heading_texts
                or str(merge.get("merged_text") or "") in heading_texts
                for merge in (
                    result["stable_analysis"].get("canonicalisation_debug", {})
                    .get("merged_requirements", [])
                    or []
                )
            )
        )
        for requirement in BONUS_REQUIREMENTS:
            matching_rows = [
                row
                for row in rows
                if row.get("text") == requirement
                or row.get("parent_text") == requirement
            ]
            self.assertTrue(matching_rows, requirement)
            self.assertTrue(
                all(row["importance"] == "preferred" for row in matching_rows),
                requirement,
            )
            self.assertTrue(
                all(
                    row.get("importance_source") == "user_override"
                    for row in matching_rows
                ),
                requirement,
            )

        baseline = next(row for row in rows if row["text"] == "Build reliable APIs")
        self.assertEqual(baseline["importance"], "required")
        self.assertEqual(
            set(result["meta"]["jd_user_inputs"]["canonical_preferred_matches"]),
            set(BONUS_REQUIREMENTS),
        )
        self.assertEqual(
            result["meta"]["jd_user_inputs"]["unmatched_preferred_overrides"],
            [],
        )
        self.assertEqual(
            result["meta"]["jd_user_inputs"]["supplemental_preferred_requirements"],
            [],
        )
        self.assertGreaterEqual(
            result["stable_analysis"]["preferred_requirement_count"],
            len(BONUS_REQUIREMENTS),
        )
        self.assertEqual(
            len(
                {
                    row["requirement_id"]
                    for row in rows
                    if row.get("requirement_id")
                }
            ),
            len([row for row in rows if row.get("requirement_id")]),
        )

    def test_missing_raw_requirement_becomes_application_local_supplement(self) -> None:
        bonus = "Experience working with Android app development and Kotlin"
        raw_jd = "Job Requirements\nBuild reliable APIs.\n"
        report = _report()
        report["jd_profile"]["required_skills"] = [
            "Build reliable APIs",
            bonus,
        ]
        with _forbid_paid_calls():
            result = apply_application_session_jd_user_inputs(
                report,
                raw_jd_text=raw_jd,
                raw_resume_text="Candidate résumé",
                preferred_requirements=[bonus],
            )

        texts = {
            item["text"]
            for item in result["stable_analysis"]["canonical_requirements"]
        }
        self.assertIn(bonus, texts)
        self.assertEqual(
            result["meta"]["jd_user_inputs"]["canonical_preferred_matches"],
            [],
        )
        self.assertEqual(
            result["meta"]["jd_user_inputs"]["unmatched_preferred_overrides"],
            [],
        )
        self.assertEqual(
            result["meta"]["jd_user_inputs"]["supplemental_preferred_requirements"],
            [bonus],
        )
        supplemental = next(
            item
            for item in result["stable_analysis"]["canonical_requirements"]
            if item.get("user_supplied_requirement") == bonus
        )
        self.assertEqual(supplemental["importance"], "preferred")
        self.assertEqual(
            supplemental["application_requirement_scope"], "application_local"
        )
        self.assertFalse(supplemental["canonical_shared"])
        self.assertEqual(
            result["meta"]["jd_user_inputs"]["original_extracted_jd_profile"],
            report["jd_profile"],
        )
        self.assertEqual(
            result["raw_jd_text"],
            raw_jd.strip(),
        )
        self.assertNotIn(bonus, result["raw_jd_text"])

    def test_app_121_style_manual_bonus_set_is_supplemental_and_order_independent(self) -> None:
        raw_jd = "Job Requirements\nBuild reliable APIs\n"
        report = _report()
        report["jd_profile"]["required_skills"] = ["Build reliable APIs"]
        report["resume_profile"] = {
            "education": [],
            "experience": [],
            "projects": [
                {
                    "name": "Android graphics application",
                    "bullets": [
                        "Experience working with Android app development and Kotlin."
                    ],
                }
            ],
            "skills": ["Android", "Kotlin"],
        }
        android_resume_text = (
            "Experience working with Android app development and Kotlin, "
            "including mobile user-interface testing."
        )
        with _forbid_paid_calls():
            first = apply_application_session_jd_user_inputs(
                report,
                raw_jd_text=raw_jd,
                raw_resume_text=android_resume_text,
                preferred_requirements=BONUS_REQUIREMENTS,
            )
            reordered = apply_application_session_jd_user_inputs(
                report,
                raw_jd_text=raw_jd,
                raw_resume_text=android_resume_text,
                preferred_requirements=list(reversed(BONUS_REQUIREMENTS)),
            )

        for result in (first, reordered):
            self.assertEqual(
                set(
                    result["meta"]["jd_user_inputs"][
                        "supplemental_preferred_requirements"
                    ]
                ),
                set(BONUS_REQUIREMENTS),
            )
            supplemental = [
                row
                for row in result["stable_analysis"]["canonical_requirements"]
                if row.get("application_requirement_scope") == "application_local"
            ]
            self.assertEqual(len(supplemental), len(BONUS_REQUIREMENTS))
            self.assertEqual(
                result["stable_analysis"]["preferred_requirement_count"],
                len(BONUS_REQUIREMENTS),
            )
            self.assertTrue(
                all(row["importance"] == "preferred" for row in supplemental)
            )
            self.assertTrue(
                all(row["canonical_shared"] is False for row in supplemental)
            )
            self.assertTrue(
                all(
                    row["importance_source"] == "user_supplied"
                    and row["application_requirement_scope"]
                    == "application_local"
                    and row["user_supplied_requirement"] in BONUS_REQUIREMENTS
                    for row in supplemental
                )
            )
            self.assertEqual(
                result["stable_analysis"]["score_weights"][
                    "preferred_coverage"
                ],
                0.10,
            )
            self.assertGreater(
                result["stable_analysis"]["preferred_coverage_score"],
                0,
            )
            android_kotlin = next(
                row
                for row in supplemental
                if row.get("user_supplied_requirement")
                == "Experience working with Android app development and Kotlin"
            )
            self.assertNotEqual(android_kotlin["match_label"], "none")
            self.assertGreater(android_kotlin["evidence_strength"], 0)
            self.assertTrue(android_kotlin["evidence"])
            self.assertEqual(result["raw_jd_text"], raw_jd.strip())
            self.assertEqual(
                result["meta"]["jd_user_inputs"][
                    "original_extracted_jd_profile"
                ],
                report["jd_profile"],
            )
            self.assertEqual(
                canonical_jd_profile_for_application_session(result),
                report["jd_profile"],
            )

        self.assertEqual(
            first["stable_analysis"]["input_fingerprint"],
            reordered["stable_analysis"]["input_fingerprint"],
        )
        self.assertEqual(
            [
                row["requirement_id"]
                for row in first["stable_analysis"]["canonical_requirements"]
            ],
            [
                row["requirement_id"]
                for row in reordered["stable_analysis"]["canonical_requirements"]
            ],
        )

    def test_short_input_is_supplemental_without_fuzzy_reclassification(self) -> None:
        longer_requirement = (
            "Experience working with Android app development and Kotlin"
        )
        with _forbid_paid_calls():
            result = apply_application_session_jd_user_inputs(
                _report(),
                raw_jd_text=f"Job Requirements\n{longer_requirement}\n",
                raw_resume_text="Candidate résumé",
                preferred_requirements=["Android", " android "],
            )

        canonical = next(
            row
            for row in result["stable_analysis"]["canonical_requirements"]
            if row["text"] == longer_requirement
        )
        self.assertEqual(canonical["importance"], "required")
        self.assertNotIn("importance_source", canonical)
        supplemental = [
            row
            for row in result["stable_analysis"]["canonical_requirements"]
            if row.get("user_supplied_requirement") == "Android"
        ]
        self.assertEqual(len(supplemental), 1)
        self.assertEqual(supplemental[0]["importance"], "preferred")

    def test_clearing_removes_matched_and_supplemental_requirements(self) -> None:
        matched = "Experience working with Kotlin"
        supplemental = "Familiarity with Nvidia CUDA"
        raw_jd = f"Job Requirements\n{matched}\n"
        with _forbid_paid_calls():
            overridden = apply_application_session_jd_user_inputs(
                _report(),
                raw_jd_text=raw_jd,
                raw_resume_text="Candidate résumé",
                preferred_requirements=[matched, supplemental],
            )
            cleared = apply_application_session_jd_user_inputs(
                overridden,
                raw_jd_text=raw_jd,
                raw_resume_text="Candidate résumé",
                preferred_requirements=[],
            )

        restored = next(
            row
            for row in cleared["stable_analysis"]["canonical_requirements"]
            if row["text"] == matched
        )
        self.assertEqual(restored["importance"], "required")
        self.assertNotIn("importance_source", restored)
        self.assertFalse(
            any(
                row.get("application_requirement_scope") == "application_local"
                for row in cleared["stable_analysis"]["canonical_requirements"]
            )
        )
        self.assertEqual(
            cleared["stable_analysis"]["preferred_requirement_count"], 0
        )


class JDUserInputOverrideCanonicalIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_application_db_path = db_manager.DB_PATH
        self.original_db_path = jd_library_manager.DB_PATH
        temporary_db_path = Path(self.temp_dir.name) / "applications.db"
        db_manager.DB_PATH = temporary_db_path
        jd_library_manager.DB_PATH = temporary_db_path
        db_manager.init_db()
        jd_library_manager.init_jd_library()

    def tearDown(self) -> None:
        db_manager.DB_PATH = self.original_application_db_path
        jd_library_manager.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_forced_refresh_application_report_and_snapshot_keep_effective_scope(self) -> None:
        """Reproduce App 124 through the Application Session persistence path.

        The production flow writes the processed report, snapshots it after a
        forced refresh, then writes the report again with the snapshot ID.  A
        metadata-only implementation would pass helper tests but fail both of
        these persisted reports.
        """
        raw_jd = "Job Requirements\nBuild reliable APIs\n"
        raw_resume = (
            "Experience working with Android app development and Kotlin, "
            "including mobile user-interface testing."
        )
        report = _report()
        report["jd_profile"]["required_skills"] = ["Build reliable APIs"]
        report["resume_profile"] = {
            "education": [],
            "experience": [],
            "projects": [
                {
                    "name": "Workout Buddy",
                    "bullets": [raw_resume],
                }
            ],
            "skills": ["Android", "Kotlin"],
        }
        application_id = db_manager.create_empty_application_session(
            degree="IMGD"
        )
        with _forbid_paid_calls():
            processed = apply_application_session_jd_user_inputs(
                report,
                raw_jd_text=raw_jd,
                raw_resume_text=raw_resume,
                preferred_requirements=BONUS_REQUIREMENTS,
            )
            # This is the production forced-refresh write before cache-snapshot
            # creation.  The cache fingerprint itself is intentionally distinct
            # from the effective stable-analysis fingerprint.
            db_manager.update_application_report(
                application_id=application_id,
                resume_filename="workout_buddy.docx",
                report=processed,
            )
            snapshot = save_analysis_snapshot(
                application_id=application_id,
                input_fingerprint="forced-refresh-app-124",
                report=processed,
                analysis_model="test-analysis-model",
                resume_filename="workout_buddy.docx",
            )
            processed["meta"]["analysis_cache"] = {
                "status": "forced_refresh",
                "input_fingerprint": "forced-refresh-app-124",
                "analysis_id": snapshot["analysis_id"],
            }
            # This is the final production report write after cache-snapshot
            # creation, which is where App 124 previously appeared to lose scope.
            db_manager.update_application_report(
                application_id=application_id,
                resume_filename="workout_buddy.docx",
                report=processed,
            )

        persisted = db_manager.get_application_by_id(application_id)["report"]
        activated = activate_analysis_snapshot(
            application_id=application_id,
            analysis_id=snapshot["analysis_id"],
        )["report"]
        for stored_report in (persisted, activated):
            stable = stored_report["stable_analysis"]
            supplemental = [
                row
                for row in stable["canonical_requirements"]
                if row.get("application_requirement_scope")
                == "application_local"
            ]
            self.assertEqual(stable["preferred_requirement_count"], 5)
            self.assertEqual(stable["requirement_count"], 6)
            self.assertEqual(stable["required_core_requirement_count"], 1)
            self.assertEqual(stable["score_weights"]["preferred_coverage"], 0.10)
            self.assertEqual(len(supplemental), 5)
            self.assertTrue(
                all(
                    row.get("importance") == "preferred"
                    and row.get("importance_source") == "user_supplied"
                    and row.get("canonical_shared") is False
                    for row in supplemental
                )
            )
            android_kotlin = next(
                row
                for row in supplemental
                if row.get("user_supplied_requirement")
                == "Experience working with Android app development and Kotlin"
            )
            self.assertNotEqual(android_kotlin["match_label"], "none")
            self.assertGreater(android_kotlin["evidence_strength"], 0)
            self.assertTrue(android_kotlin["evidence"])
            self.assertGreater(stable["preferred_coverage_score"], 0)

        stored_jd = jd_library_manager.get_exact_job_description_for_application(
            application_id
        )
        self.assertIsNone(stored_jd)

    def test_local_metadata_overrides_and_url_do_not_mutate_shared_jd(self) -> None:
        raw_jd = "Job Requirements\nExperience with Kotlin.\n"
        supplemental = "Familiarity with Nvidia CUDA"
        with _forbid_paid_calls():
            first_report = apply_application_session_jd_user_inputs(
                _report(),
                raw_jd_text=raw_jd,
                raw_resume_text="Candidate résumé",
            )
            first_profile = canonical_jd_profile_for_application_session(
                first_report
            )
            first = jd_library_manager.save_or_link_job_description_for_application(
                application_id=101,
                raw_text=raw_jd,
                jd_profile=first_profile,
                source_url="https://canonical.example/original",
            )
            before = jd_library_manager.get_exact_job_description_for_application(
                101
            )

            second_report = apply_application_session_jd_user_inputs(
                _report(),
                raw_jd_text=raw_jd,
                raw_resume_text="Candidate résumé",
                company="Application-local Company",
                job_title="Application-local Role",
                location="Application-local Location",
                source_url="https://application.example/override",
                preferred_requirements=[
                    "Experience with Kotlin",
                    supplemental,
                ],
            )
            second_profile = canonical_jd_profile_for_application_session(
                second_report
            )
            second = jd_library_manager.save_or_link_job_description_for_application(
                application_id=102,
                raw_text=raw_jd,
                jd_profile=second_profile,
                source_url=None,
            )
            after = jd_library_manager.get_exact_job_description_for_application(
                101
            )

        self.assertEqual(first["job_description_id"], second["job_description_id"])
        self.assertEqual(first["canonical_jd_id"], second["canonical_jd_id"])
        self.assertEqual(before["canonical_jd_id"], after["canonical_jd_id"])
        self.assertEqual(before["source_version_id"], after["source_version_id"])
        self.assertEqual(
            after["source_application_link"]["application_id"], 101
        )
        self.assertEqual(second_profile["company"], "Parsed Co")
        self.assertEqual(second_profile["job_title"], "Software Engineer")
        self.assertEqual(second_profile["location"], "Singapore")
        self.assertNotIn(
            "user_requirement_importance_overrides", second_profile
        )
        self.assertEqual(
            second_report["meta"]["jd_user_inputs"]["company"],
            "Application-local Company",
        )
        self.assertEqual(
            second_report["meta"]["jd_user_inputs"]["source_url"],
            "https://application.example/override",
        )
        self.assertEqual(
            second_report["meta"]["jd_user_inputs"][
                "supplemental_preferred_requirements"
            ],
            [supplemental],
        )
        self.assertTrue(
            any(
                row.get("user_supplied_requirement") == supplemental
                and row.get("application_requirement_scope")
                == "application_local"
                for row in second_report["stable_analysis"][
                    "canonical_requirements"
                ]
            )
        )
        saved = jd_library_manager.get_job_description_by_id(
            first["job_description_id"]
        )
        self.assertEqual(saved["source_url"], "https://canonical.example/original")
        self.assertNotIn(
            "user_requirement_importance_overrides", saved["jd_profile"]
        )


class JDUserInputOverrideAppWiringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (ROOT / "app.py").read_text(encoding="utf-8")

    def test_application_session_exposes_optional_jd_metadata(self) -> None:
        self.assertIn('"Optional JD metadata"', self.source)
        self.assertIn('"Job title / Role"', self.source)
        self.assertIn('key=f"jd_company_{input_suffix}"', self.source)
        self.assertIn('key=f"jd_source_url_{input_suffix}"', self.source)

    def test_application_session_exposes_and_applies_preferred_overrides(self) -> None:
        self.assertIn('"Optional JD requirement overrides"', self.source)
        self.assertIn("PREFERRED_REQUIREMENTS_LABEL", self.source)
        self.assertIn("PREFERRED_REQUIREMENTS_HELP", self.source)
        self.assertIn("preferred_requirement_override_cache_identity(", self.source)
        self.assertIn("apply_application_session_jd_user_inputs(", self.source)
        self.assertEqual(
            PREFERRED_REQUIREMENTS_LABEL,
            "Preferred / bonus / optional JD requirements",
        )
        self.assertIn("new entries are added only to this application.", PREFERRED_REQUIREMENTS_HELP)

    def test_override_semantics_are_in_analysis_cache_identity(self) -> None:
        self.assertIn('"jd_user_override_identity": override_cache_identity', self.source)

    def test_source_url_is_report_local_without_coupling_phase9f_intake(self) -> None:
        self.assertIn("source_url=jd_source_url_input", self.source)
        self.assertIn("source_url=None", self.source)
        self.assertIn(
            "canonical_jd_profile_for_application_session(report)", self.source
        )
        self.assertIn("render_phase9f_jd_intake()", self.source)


if __name__ == "__main__":
    unittest.main()

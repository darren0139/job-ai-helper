from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from analysis_stability.stable_evidence_scoring import build_stable_analysis
from database import db_manager, tailoring_version_manager
from database.tailoring_generation_control import get_tailoring_generation, list_tailoring_generations
from tailoring.candidate_context import build_candidate_context, candidate_context_downloads
from tailoring import evidence_grounded_bullet_tailoring as feature
from tailoring.project_section_tailor import build_project_candidate_pool
from tailoring.stable_tailoring_ranking import build_candidate_evidence_profile, rank_projects_deterministically


def fixture(raw="Requirements\nExperience working with Android app development and Kotlin"):
    evidence = "Implemented an Android application using Kotlin and Jetpack Compose."
    profile = {"projects": [{"title": "Workout Buddy", "bullets": [evidence]}],
               "skills": {}, "education": [], "experience": []}
    pool = build_project_candidate_pool(resume_profile=profile, evidence_items=[])
    report = {"raw_jd_text": raw, "jd_profile": {}, "resume_profile": profile,
              "keyword_match": {"present": [], "missing": []}}
    report["stable_analysis"] = build_stable_analysis(jd_profile={}, keyword_match={},
        raw_jd_text=raw, resume_profile=profile, raw_resume_text=evidence,
        retrieval_mode_override="lexical")
    ranked, _ = rank_projects_deterministically(ranked_rows=[{"title": "Workout Buddy"}],
        project_candidates=pool, stable_analysis=report["stable_analysis"])
    pid = ranked[0]["project_id"]
    generation = {"generation_id": "draft-a", "status": "draft", "candidate_pool": pool,
        "project_inputs": {"resume_projects": deepcopy(profile["projects"]), "evidence_items": []},
        "projects": {"recommended_projects": [{"project_id": pid, "title": "Workout Buddy",
            "draft_bullets": ["Implemented an application using Kotlin and Jetpack Compose."],
            "selected_blueprint_bullets": [evidence],
            "project_relevance": ranked[0]["project_relevance"]}]},
        "skills": {"skill_lines": []}, "fit_result": None}
    return generation, report


def arguments(generation, report):
    return dict(generation=generation, report=report, project_index=0, bullet_index=0,
                requirement_id=report["stable_analysis"]["canonical_requirements"][0]["requirement_id"])


def suggestion(generation, report, bullet=None):
    args = arguments(generation, report)
    target = feature.prepare_bullet_target(**args)
    record = target["evidence_records"][0]
    return {"target_fingerprint": target["target_fingerprint"], "project_index": 0,
        "bullet_index": 0, "requirement_id": args["requirement_id"],
        "selected_evidence_id": record["evidence_id"], "model": "mock-model",
        "response": {"target_requirement_id": args["requirement_id"],
            "project_id": target["project_id"], "bullet_index": 0,
            "evidence_ids": [record["evidence_id"]],
            "candidate_bullet": bullet or record["text"]}}


class EvidenceGroundedBulletTests(unittest.TestCase):
    def test_unsupported_is_zero_call_and_does_not_trust_saved_metadata(self):
        for text in ("Experience with CUDA", "Experience with OpenGL and/or Vulkan",
                     "Memory and cache optimisation", "Modern C++ development"):
            with self.subTest(text=text):
                generation, report = fixture("Requirements\n" + text)
                generation["projects"]["recommended_projects"][0]["project_relevance"] = {"match_label": "direct"}
                with patch.object(feature, "ask_json") as model:
                    result = feature.suggest_grounded_bullet(**arguments(generation, report),
                        evidence_id="invented", model="test")
                model.assert_not_called()
                self.assertEqual("unsupported", result["status"])
                self.assertNotIn("response", result)

    def test_deterministic_grounded_baseline_is_zero_call_and_verifies(self):
        generation, report = fixture()
        generation["projects"]["recommended_projects"][0]["draft_bullets"] = [
            "Implemented frontend application features for users."
        ]
        target = feature.prepare_bullet_target(**arguments(generation, report))
        evidence_id = target["evidence_records"][0]["evidence_id"]

        with patch.object(feature, "ask_json") as model:
            baseline = feature.build_grounded_baseline_suggestion(
                **arguments(generation, report),
                evidence_id=evidence_id,
            )

        model.assert_not_called()
        self.assertEqual("grounded_baseline", baseline["status"])
        self.assertEqual(
            "deterministic_grounded_source", baseline["suggestion_kind"]
        )
        self.assertEqual(0, baseline["model_call_count"])
        self.assertEqual(
            target["evidence_records"][0]["text"],
            baseline["response"]["candidate_bullet"],
        )

        evaluated = feature.evaluate_grounded_bullet(
            generation=generation,
            report=report,
            suggestion=baseline,
        )
        self.assertTrue(evaluated["safe_to_apply"], evaluated.get("reasons"))
        self.assertTrue(evaluated["target_improved"])

    def test_existing_relevance_is_used_and_one_row_is_bounded(self):
        generation, report = fixture()
        before = deepcopy(generation)
        target = feature.prepare_bullet_target(**arguments(generation, report))
        expected = generation["projects"]["recommended_projects"][0]["project_relevance"]["requirement_relationships"][0]
        self.assertEqual(expected, target["relationship"])
        exported_ids = {r["evidence_id"] for p in target["candidate_context"]["project_evidence_profile"]["projects"]
                        for r in p["evidence_records"]}
        self.assertTrue({r["evidence_id"] for r in target["evidence_records"]} <= exported_ids)
        with patch.object(feature, "ask_json", return_value=suggestion(generation, report)["response"]) as model:
            result = feature.suggest_grounded_bullet(**arguments(generation, report),
                evidence_id=target["evidence_records"][0]["evidence_id"], model="test")
        prompt = json.loads(model.call_args.args[1])
        self.assertEqual(target["evidence_records"][0], prompt["evidence"])
        self.assertNotIn("evidence_library", prompt)
        self.assertEqual(1, result["model_call_count"])
        self.assertEqual(before, generation)

    def test_explicit_provider_output_keeps_deterministic_target_identity(self):
        generation, report = fixture()
        generation["projects"]["recommended_projects"][0]["draft_bullets"] = [
            "Implemented frontend application features for users."
        ]
        target = feature.prepare_bullet_target(**arguments(generation, report))
        evidence_id = target["evidence_records"][0]["evidence_id"]

        class FakeResult:
            candidate_bullet = (
                "Implemented an Android application with Kotlin and Jetpack Compose."
            )
            evidence_ids = [evidence_id]
            provider_id = "github_copilot"
            model = "auto"
            call_count = 1
            metadata = {"raw_response": "synthetic"}

        class FakeProvider:
            def polish(self, contract):
                self.contract = contract
                return FakeResult()

        fake_provider = FakeProvider()
        with patch.object(
            feature,
            "create_rewrite_provider",
            return_value=fake_provider,
        ) as factory, patch.object(feature, "ask_json") as configured_model:
            result = feature.suggest_grounded_bullet(
                **arguments(generation, report),
                evidence_id=evidence_id,
                model="ignored-for-copilot",
                provider="github_copilot",
            )

        configured_model.assert_not_called()
        factory.assert_called_once()
        self.assertEqual("github_copilot", result["provider"])
        self.assertEqual("auto", result["model"])
        self.assertEqual(1, result["model_call_count"])
        self.assertEqual(
            target["project_id"],
            result["response"]["project_id"],
        )
        self.assertEqual(
            arguments(generation, report)["requirement_id"],
            result["response"]["target_requirement_id"],
        )
        self.assertEqual(0, result["response"]["bullet_index"])
        self.assertEqual([evidence_id], result["response"]["evidence_ids"])
        self.assertEqual(evidence_id, fake_provider.contract.evidence_id)
        self.assertEqual(
            target["evidence_records"][0],
            fake_provider.contract.evidence_record,
        )

    def test_split_rows_and_weak_support_do_not_enable_generation(self):
        generation, report = fixture()
        for bullets in (["Implemented a Kotlin backend utility.", "Configured Android Studio tooling."],
                        ["Worked with Android tools."]):
            pool = build_project_candidate_pool(resume_profile={"projects": [
                {"title": "Workout Buddy", "bullets": bullets}]}, evidence_items=[])
            generation["candidate_pool"] = pool
            with patch.object(feature, "ask_json") as model:
                result = feature.suggest_grounded_bullet(**arguments(generation, report),
                    evidence_id="unavailable", model="mock")
            self.assertEqual("unsupported", result["status"])
            model.assert_not_called()

    def test_response_cannot_retarget_bullet_or_requirement(self):
        generation, report = fixture()
        for field, value in (("project_id", "other"), ("bullet_index", 1),
                             ("target_requirement_id", "other")):
            candidate = suggestion(generation, report)
            candidate["response"][field] = value
            result = feature.evaluate_grounded_bullet(generation=generation, report=report, suggestion=candidate)
            self.assertFalse(result["safe_to_apply"])

    def test_unknown_and_outside_selected_evidence_ids_fail(self):
        generation, report = fixture()
        for ids in (["unknown"], [], ["unknown", "extra"]):
            candidate = suggestion(generation, report)
            candidate["response"]["evidence_ids"] = ids
            result = feature.evaluate_grounded_bullet(generation=generation, report=report, suggestion=candidate)
            self.assertFalse(result["safe_to_apply"])
            self.assertIn("response_identity_outside_selected_context", result["reasons"])

    def test_unsupported_claim_insertions_are_rejected(self):
        generation, report = fixture()
        for claim in ("CUDA", "Vulkan", "OpenGL", "memory cache optimisation", "modern C++", "500 users", "25% performance", "5 years"):
            with self.subTest(claim=claim):
                candidate = suggestion(generation, report,
                    "Implemented an Android application using Kotlin and Jetpack Compose with " + claim + ".")
                result = feature.evaluate_grounded_bullet(generation=generation, report=report, suggestion=candidate)
                self.assertFalse(result["safe_to_apply"])

    def test_lineage_failure_blocks_apply(self):
        generation, report = fixture()
        with patch.object(feature, "audit_claim_lineage_v2", return_value={"claim_review_required_count": 1}):
            result = feature.evaluate_grounded_bullet(generation=generation, report=report,
                suggestion=suggestion(generation, report))
        self.assertFalse(result["safe_to_apply"])
        self.assertIn("claim_lineage_failed", result["reasons"])

    def test_protected_requirement_loss_blocks_even_with_target_improvement(self):
        generation, report = fixture("Requirements\nExperience working with Android app development and Kotlin\nBuild Python applications")
        generation["projects"]["recommended_projects"][0]["draft_bullets"] = [
            "Built Python applications."]
        candidate = suggestion(generation, report)
        result = feature.evaluate_grounded_bullet(generation=generation, report=report, suggestion=candidate)
        self.assertFalse(result["safe_to_apply"])
        self.assertIn("protected_requirement_regression", result["reasons"])
        self.assertTrue(result["comparison"]["improved_requirements"])
        self.assertTrue(result["comparison"]["important_regressions"])

    def test_project_first_opportunities_only_offer_exact_supported_bullets(self):
        generation, report = fixture()
        # Add an unrelated fallback-style project. It must never inherit the
        # Android/Kotlin opportunity merely because another selected project has it.
        unrelated_profile = {
            "projects": [
                {"title": "Workout Buddy", "bullets": [
                    "Implemented an Android application using Kotlin and Jetpack Compose."
                ]},
                {"title": "Job AI Helper", "bullets": [
                    "Built a Python resume workflow with automated tests."
                ]},
            ],
            "skills": {}, "education": [], "experience": [],
        }
        pool = build_project_candidate_pool(resume_profile=unrelated_profile, evidence_items=[])
        ranked, _ = rank_projects_deterministically(
            ranked_rows=[{"title": "Workout Buddy"}, {"title": "Job AI Helper"}],
            project_candidates=pool,
            stable_analysis=report["stable_analysis"],
        )
        by_title = {row["title"]: row for row in ranked}
        generation["candidate_pool"] = pool
        generation["project_inputs"] = {
            "resume_projects": deepcopy(unrelated_profile["projects"]),
            "evidence_items": [],
        }
        generation["projects"]["recommended_projects"] = [
            {
                "project_id": by_title["Workout Buddy"]["project_id"],
                "title": "Workout Buddy",
                "draft_bullets": ["Implemented an application using Kotlin and Jetpack Compose."],
                "selected_blueprint_bullets": [
                    "Implemented an Android application using Kotlin and Jetpack Compose."
                ],
                "project_relevance": by_title["Workout Buddy"]["project_relevance"],
            },
            {
                "project_id": by_title["Job AI Helper"]["project_id"],
                "title": "Job AI Helper",
                "draft_bullets": ["Built a Python resume workflow with automated tests."],
                "selected_blueprint_bullets": [
                    "Built a Python resume workflow with automated tests."
                ],
                "project_relevance": by_title["Job AI Helper"]["project_relevance"],
            },
        ]
        opportunities = feature.list_grounded_bullet_opportunities(
            generation=generation, report=report
        )
        rows = {row["title"]: row for row in opportunities["projects"]}
        self.assertEqual(1, len(rows["Workout Buddy"]["bullets"]))
        self.assertEqual([], rows["Job AI Helper"]["bullets"])
        self.assertGreater(opportunities["opportunity_count"], 0)

    def test_already_supported_bullet_is_zero_call_and_not_a_score_opportunity(self):
        generation, report = fixture()
        exact = "Implemented an Android application using Kotlin and Jetpack Compose."
        generation["projects"]["recommended_projects"][0]["draft_bullets"] = [exact]
        generation["projects"]["recommended_projects"][0]["selected_blueprint_bullets"] = [exact]

        target = feature.prepare_bullet_target(**arguments(generation, report))
        self.assertEqual("already_at_ceiling", target["status"])
        self.assertEqual("direct", target["current_match_label"])
        self.assertEqual("direct", target["safe_evidence_ceiling"])
        self.assertFalse(target["deterministic_promotion_available"])

        opportunities = feature.list_grounded_bullet_opportunities(
            generation=generation, report=report
        )
        project = opportunities["projects"][0]
        self.assertEqual([], project["bullets"])
        self.assertEqual(1, len(project["already_strong_bullets"]))
        self.assertEqual(0, opportunities["opportunity_count"])
        self.assertEqual(1, opportunities["already_strong_count"])
        self.assertEqual("already_at_ceiling", project["diagnostic"]["code"])

        with patch.object(feature, "ask_json") as model:
            result = feature.suggest_grounded_bullet(
                **arguments(generation, report), evidence_id="unused", model="test"
            )
        model.assert_not_called()
        self.assertEqual("already_at_ceiling", result["status"])
        self.assertEqual(0, result["model_call_count"])

    def test_promotion_gate_uses_current_wording_not_canonical_wording(self):
        generation, report = fixture()
        # The current draft is deliberately generic, while the frozen canonical/source
        # bullet explicitly proves Android + Kotlin. That is a real deterministic
        # promotion opportunity rather than a wording-only rewrite.
        generation["projects"]["recommended_projects"][0]["draft_bullets"] = [
            "Implemented frontend application features for users."
        ]
        generation["projects"]["recommended_projects"][0]["selected_blueprint_bullets"] = [
            "Implemented an Android application using Kotlin and Jetpack Compose."
        ]
        target = feature.prepare_bullet_target(**arguments(generation, report))
        self.assertTrue(target["evidence_records"])
        self.assertTrue(target["deterministic_promotion_available"])
        self.assertLess(
            feature._LABEL_ORDER[target["current_match_label"]],
            feature._LABEL_ORDER[target["safe_evidence_ceiling"]],
        )
        self.assertEqual("ready", target["status"])

    def test_label_promotion_helper_rejects_same_or_lower_ceiling(self):
        self.assertTrue(feature._promotion_available("none", "transferable"))
        self.assertTrue(feature._promotion_available("transferable", "direct"))
        self.assertFalse(feature._promotion_available("direct", "direct"))
        self.assertFalse(feature._promotion_available("transferable", "transferable"))
        self.assertFalse(feature._promotion_available("direct", "transferable"))


    def test_project_diagnostic_explains_exact_source_mapping_mismatch(self):
        generation, report = fixture()
        # Keep project-level Android/Kotlin support, but make the current/selected
        # bullet a supported paraphrase rather than an exact frozen evidence row.
        paraphrase = "Built an Android application with Kotlin and Jetpack Compose for mobile users."
        generation["projects"]["recommended_projects"][0]["draft_bullets"] = [paraphrase]
        generation["projects"]["recommended_projects"][0]["selected_blueprint_bullets"] = [paraphrase]

        opportunities = feature.list_grounded_bullet_opportunities(
            generation=generation, report=report
        )
        project = opportunities["projects"][0]
        self.assertEqual([], project["bullets"])
        self.assertEqual(
            "supported_project_but_no_exact_bullet_evidence",
            project["diagnostic"]["code"],
        )
        self.assertTrue(project["diagnostic"]["project_supported_requirements"])
        checks = [
            check
            for bullet in project["diagnostic"]["bullet_checks"]
            for check in bullet["requirement_checks"]
        ]
        self.assertTrue(any(
            check["reason"] == "current_bullet_not_exactly_mapped_to_frozen_supporting_evidence"
            for check in checks
        ))

    def test_exact_frozen_bullet_identity_does_not_pair_unrelated_parallel_slots(self):
        chroma = "Integrated ChromaDB RAG over analysed job descriptions for Job Market Insights and market-fit comparison."
        ci = "Added automated unit tests and GitHub Actions CI across Ubuntu and Windows."
        records = [
            {"evidence_id": "evidence_chroma", "kind": "bullet", "source": "evidence_library", "text": chroma},
            {"evidence_id": "evidence_ci", "kind": "bullet", "source": "resume", "text": ci},
        ]
        resolved, mapping = feature._resolve_bullet_source_records(
            source_records=records, current_bullet=chroma, canonical_bullet=chroma
        )
        self.assertEqual(["evidence_chroma"], [row["evidence_id"] for row in resolved])
        self.assertEqual("exact_frozen_bullet_evidence", mapping["method"])
        self.assertNotIn("evidence_ci", mapping["source_evidence_ids"])

    def test_same_project_different_ci_row_cannot_create_rewrite_opportunity(self):
        chroma = "Integrated ChromaDB RAG over analysed job descriptions for Job Market Insights and market-fit comparison."
        ci = "Added automated unit tests and GitHub Actions CI across Ubuntu and Windows, running dependency checks, compilation, the full test suite, and a Streamlit startup health check."
        raw = "Requirements\nFamiliarity with CI/CD tools (Terraform, Jenkins, etc.)\nManage and set up automated CI/CD systems"
        profile = {"projects": [{"title": "Job AI Helper", "bullets": [chroma, ci]}],
                   "skills": {}, "education": [], "experience": []}
        pool = build_project_candidate_pool(resume_profile=profile, evidence_items=[])
        report = {"raw_jd_text": raw, "jd_profile": {}, "resume_profile": profile,
                  "keyword_match": {"present": [], "missing": []}}
        report["stable_analysis"] = build_stable_analysis(
            jd_profile={}, keyword_match={}, raw_jd_text=raw, resume_profile=profile,
            raw_resume_text=chroma + "\n" + ci, retrieval_mode_override="lexical"
        )
        ranked, _ = rank_projects_deterministically(
            ranked_rows=[{"title": "Job AI Helper"}], project_candidates=pool,
            stable_analysis=report["stable_analysis"]
        )
        pid = ranked[0]["project_id"]
        generation = {
            "generation_id": "draft-ci", "status": "draft", "candidate_pool": pool,
            "project_inputs": {"resume_projects": deepcopy(profile["projects"]), "evidence_items": []},
            "projects": {"recommended_projects": [{
                "project_id": pid, "title": "Job AI Helper",
                "draft_bullets": [chroma, ci],
                "selected_blueprint_bullets": [chroma, ci],
                "project_relevance": ranked[0]["project_relevance"],
            }]},
            "skills": {"skill_lines": []}, "fit_result": None,
        }
        opportunities = feature.list_grounded_bullet_opportunities(
            generation=generation, report=report
        )
        project = opportunities["projects"][0]
        chroma_row = next(row for row in project["diagnostic"]["bullet_checks"] if row["bullet_index"] == 0)
        ci_checks = [
            check for check in chroma_row["requirement_checks"]
            if "ci/cd" in str(check.get("text") or "").lower()
        ]
        self.assertTrue(ci_checks)
        self.assertTrue(all(not check["eligible"] for check in ci_checks))
        self.assertTrue(all(check["safe_evidence_ceiling"] == "none" for check in ci_checks))
        self.assertFalse(any(row["bullet_index"] == 0 for row in project["bullets"]))

    def test_canonical_source_row_can_still_enable_real_promotion(self):
        generation, report = fixture()
        generation["projects"]["recommended_projects"][0]["draft_bullets"] = [
            "Implemented frontend application features for users."
        ]
        target = feature.prepare_bullet_target(**arguments(generation, report))
        self.assertEqual("ready", target["status"])
        self.assertTrue(target["deterministic_promotion_available"])
        self.assertEqual("exact_frozen_bullet_evidence", target["source_mapping"]["method"])
        self.assertEqual(1, len(target["source_mapping"]["source_evidence_ids"]))

    def test_deterministic_preview_and_stale_context_rejection(self):
        generation, report = fixture()
        candidate = suggestion(generation, report)
        first = feature.evaluate_grounded_bullet(generation=generation, report=report, suggestion=candidate)
        second = feature.evaluate_grounded_bullet(generation=generation, report=report, suggestion=candidate)
        self.assertEqual(first, second)
        self.assertTrue(first["safe_to_apply"])
        # Volatile bookkeeping must not invalidate an otherwise identical preview.
        report["api_cost_summary"] = {"call_count": 1, "estimated_total_cost_usd": 0.01}
        self.assertTrue(feature.evaluate_grounded_bullet(generation=generation, report=report,
            suggestion=candidate)["safe_to_apply"])
        report["raw_jd_text"] += "\nNew requirement"
        self.assertFalse(feature.evaluate_grounded_bullet(generation=generation, report=report,
            suggestion=candidate)["safe_to_apply"])

    def test_real_draft_persistence_lifecycle_is_explicit_and_source_immutable(self):
        from database import phase9f_tailoring_execution_manager as manager
        with tempfile.TemporaryDirectory() as root:
            db = Path(root) / "test.db"
            with patch.object(db_manager, "DB_PATH", db), patch.object(tailoring_version_manager, "DB_PATH", db):
                db_manager.init_db()
                generation, report = fixture()
                app = db_manager.save_application(resume_filename="synthetic.txt", report=report)
                # Phase 8's existing resolver uses the persisted evidence profile.
                from tailoring.stable_tailoring_ranking import build_candidate_evidence_profile
                generation["projects"]["candidate_evidence_profile"] = build_candidate_evidence_profile(generation["candidate_pool"])
                tailoring_version_manager.save_application_tailoring_generation(application_id=app,
                    generation_id="draft-a", candidate_pool=generation["candidate_pool"],
                    project_inputs=generation["project_inputs"], projects=generation["projects"], skills=generation["skills"])
                source = get_tailoring_generation(app, "draft-a")
                frozen = deepcopy(source)
                candidate = suggestion(source, report)
                with patch.object(feature, "ask_json", return_value=candidate["response"]) as model:
                    candidate = feature.suggest_grounded_bullet(**arguments(source, report),
                        evidence_id=candidate["selected_evidence_id"], model="mock")
                self.assertEqual(1, model.call_count)
                evaluated = feature.evaluate_grounded_bullet(generation=source, report=report, suggestion=candidate)
                self.assertTrue(evaluated["safe_to_apply"], evaluated.get("reasons"))
                self.assertEqual(1, len(list_tailoring_generations(app)))
                result = feature.apply_grounded_bullet(application_id=app, source_generation_id="draft-a", suggestion=candidate)
                self.assertEqual("draft", result["generation"]["status"])
                self.assertEqual(2, len(list_tailoring_generations(app)))
                self.assertEqual(frozen, get_tailoring_generation(app, "draft-a"))
                self.assertEqual(report, db_manager.get_application_by_id(app)["report"])


class CandidateContextTests(unittest.TestCase):
    def test_preserves_exact_evidence_ids_text_and_provenance_without_jd_data(self):
        items = [{"id": 7, "project_id": "p7", "description": "  C++ evidence\n\nunchanged  ",
                  "canonical_bullets": ["A", "B"], "tools": ["C++"], "subtitle": "Engine",
                  "provenance": {"source": "user"}, "final_score": 99, "requirement_matches": ["bad"]},
                 {"id": 2, "description": "Other"}]
        before = deepcopy(items)
        a = build_candidate_context({}, items)
        b = build_candidate_context({}, list(reversed(items)))
        self.assertEqual(a, b)
        row = next(r for r in a["evidence_library"] if r["id"] == 7)
        for key in ("project_id", "description", "canonical_bullets", "tools", "subtitle", "provenance"):
            self.assertEqual(items[0][key], row[key])
        self.assertNotIn("final_score", row)
        self.assertNotIn("requirement_matches", row)
        self.assertEqual(before, items)
        self.assertEqual(5, len(candidate_context_downloads({}, items)))


class GroundedBulletUITests(unittest.TestCase):
    def test_step2_diagnostics_snapshot_includes_ready_project_checks(self):
        from tailoring import evidence_grounded_bullet_ui as ui

        generation, report = fixture()
        opportunities = feature.list_grounded_bullet_opportunities(
            generation=generation, report=report
        )
        payload = ui._build_step2_diagnostics(
            application_id=17,
            generation=generation,
            opportunities=opportunities,
            selected=(0, 0),
            report=report,
        )

        self.assertEqual("grounded-bullet-step2-diagnostics-v3", payload["schema_version"])
        self.assertEqual(feature.BULLET_TAILORING_VERSION, payload["policy_version"])
        self.assertEqual(17, payload["application_id"])
        self.assertEqual("draft-a", payload["generation_id"])
        self.assertEqual({"project_index": 0, "bullet_index": 0}, payload["selected_bullet"])
        self.assertEqual(opportunities["projects"], payload["projects"])
        self.assertEqual(1, payload["summary"]["actionable_project_count"])
        self.assertEqual(0, payload["summary"]["already_strong_project_count"])
        self.assertEqual(0, payload["summary"]["unavailable_project_count"])
        self.assertGreater(payload["summary"]["opportunity_count"], 0)
        self.assertEqual(0, payload["summary"]["already_strong_count"])
        self.assertTrue(payload["projects"][0]["diagnostic"]["bullet_checks"])
        self.assertIn("ui_sections", payload)
        self.assertEqual(
            payload, json.loads(ui._diagnostics_json(payload))
        )


    def test_applied_change_notice_payload_is_generation_scoped(self):
        from tailoring import evidence_grounded_bullet_ui as ui

        payload = ui._build_applied_change_notice(
            project_title="Workout Buddy",
            previous_bullet="Implemented frontend application features for users.",
            applied_bullet="Implemented an Android application using Kotlin and Jetpack Compose.",
            before_label="none",
            after_label="direct",
            source_generation_id="source-generation",
            new_generation_id="new-generation",
            suggestion_kind="deterministic_grounded_source",
        )

        self.assertEqual("Workout Buddy", payload["project_title"])
        self.assertEqual("none", payload["before_label"])
        self.assertEqual("direct", payload["after_label"])
        self.assertEqual("source-generation", payload["source_generation_id"])
        self.assertEqual("new-generation", payload["new_generation_id"])
        self.assertEqual(
            "deterministic_grounded_source",
            payload["suggestion_kind"],
        )

    def test_step2_ui_sections_separate_scored_gaps_from_non_scored_context(self):
        from tailoring import evidence_grounded_bullet_ui as ui

        raw = """Requirements
Experience working with Android app development and Kotlin
Experience with CUDA
You will be working alongside industry experts
At the same time, you will be familiarised with the entire robotics development and software workflow
"""
        generation, report = fixture(raw)
        opportunities = feature.list_grounded_bullet_opportunities(
            generation=generation, report=report
        )
        sections = ui._step2_ui_sections(
            report=report, opportunities=opportunities
        )

        self.assertTrue(any(
            "CUDA" in row["text"] for row in sections["unsupported_gaps"]
        ))
        context = {
            row["semantic_type"]: row["text"]
            for row in sections["non_scored_context"]
        }
        self.assertIn("role_context", context)
        self.assertIn("industry experts", context["role_context"])
        self.assertIn("training_outcome", context)
        self.assertIn("familiarised", context["training_outcome"])
        self.assertFalse(any(
            "industry experts" in row["text"]
            or "familiarised" in row["text"]
            for row in sections["unsupported_gaps"]
        ))

    def test_passive_render_grounded_apply_and_optional_ai_polish(self):
        from streamlit.testing.v1 import AppTest
        source = '''
from tests.test_evidence_grounded_bullet_tailoring import fixture
from tailoring.evidence_grounded_bullet_ui import render_grounded_bullet_tailoring
generation, report = fixture()
generation["projects"]["recommended_projects"][0]["draft_bullets"] = [
    "Implemented frontend application features for users."
]
render_grounded_bullet_tailoring(application_id=1, generation=generation, report=report, model="mock")
'''
        generation, report = fixture()
        generation["projects"]["recommended_projects"][0]["draft_bullets"] = [
            "Implemented frontend application features for users."
        ]
        with patch.object(
            feature,
            "ask_json",
            return_value=suggestion(
                generation,
                report,
                "Implemented an Android application with Kotlin and Jetpack Compose.",
            )["response"],
        ) as model, patch(
            "tailoring.evidence_grounded_bullet_ui.apply_grounded_bullet"
        ) as apply:
            app = AppTest.from_string(source).run()
            self.assertEqual([], list(app.exception))
            model.assert_not_called()
            apply.assert_not_called()

            next(
                b for b in app.button if b.label == "Strengthen this bullet"
            ).click().run()
            self.assertEqual([], list(app.exception))
            model.assert_not_called()

            review_grounded = next(
                b
                for b in app.button
                if b.label == "Review & apply grounded replacement"
            )
            self.assertFalse(review_grounded.disabled)
            review_grounded.click().run()
            apply.assert_not_called()

            self.assertTrue(
                any(
                    b.label == "Confirm apply grounded replacement"
                    for b in app.button
                )
            )
            next(
                b
                for b in app.button
                if b.label == "Cancel grounded apply"
            ).click().run()
            apply.assert_not_called()

            polish = next(
                b
                for b in app.button
                if b.label == "Polish grounded wording with AI"
            )
            polish.click().run()
            self.assertEqual([], list(app.exception))
            self.assertEqual(1, model.call_count)
            apply.assert_not_called()

            review_ai = next(
                b
                for b in app.button
                if b.label == "Review & apply AI-polished bullet"
            )
            self.assertFalse(review_ai.disabled)
            review_ai.click().run()
            apply.assert_not_called()

            confirm_ai = next(
                b
                for b in app.button
                if b.label == "Confirm apply AI-polished bullet"
            )
            confirm_ai.click().run()
            apply.assert_called_once()
            self.assertEqual(1, model.call_count)

    def test_unsupported_ui_has_no_generate_action(self):
        from streamlit.testing.v1 import AppTest
        with patch.object(feature, "ask_json") as model:
            app = AppTest.from_string('''
from tests.test_evidence_grounded_bullet_tailoring import fixture
from tailoring.evidence_grounded_bullet_ui import render_grounded_bullet_tailoring
generation, report = fixture("Requirements\\nExperience with CUDA")
render_grounded_bullet_tailoring(application_id=1, generation=generation, report=report, model="mock")
''').run()
        self.assertEqual([], list(app.exception))
        self.assertFalse(any(b.label == "Strengthen this bullet" for b in app.button))
        self.assertFalse(
            any(b.label == "Polish grounded wording with AI" for b in app.button)
        )
        self.assertFalse(
            any(
                b.label == "Apply grounded replacement as new draft"
                for b in app.button
            )
        )
        self.assertTrue(
            any("Unsupported evidence-bearing JD gaps" in item.value for item in app.markdown)
        )
        model.assert_not_called()


if __name__ == "__main__":
    unittest.main()

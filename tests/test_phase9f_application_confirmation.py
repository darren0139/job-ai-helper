from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database import db_manager, jd_library_manager, tailoring_version_manager
import database.phase9f_application_confirmation_manager as confirmation_manager
from database.application_blueprint_manager import (
    get_current_application_blueprint_decision,
    resolve_current_phase9e_generation_context,
)
from database.global_blueprint_manager import (
    remove_global_blueprint_from_reuse,
)
from database.phase9f_application_confirmation_manager import (
    confirm_phase9f_application_session,
    get_phase9f_application_confirmation,
    init_phase9f_application_confirmation_schema,
)
from database.jd_library_manager import (
    get_exact_job_description_for_application,
)
from tailoring.phase9f_application_confirmation import (
    PHASE9E_PHASE9F_D_EXACT_BINDING_VERSION,
    PHASE9F_D_EXECUTION_NOT_STARTED_STATUS,
    Phase9FDConfirmationError,
    build_application_baseline_report,
    prepare_phase9f_d_confirmation,
)
from tailoring.phase9f_application_confirmation_ui import (
    prepare_persisted_exact_jd_for_confirmation,
)
from tailoring.phase9e1_workflow_ui import (
    build_application_workflow_overview,
)
from tests.phase9f_d_test_support import (
    build_scope,
    configure_database,
    insert_base_resume,
    insert_blueprint,
    save_exact_jd,
)
from tests.test_phase9f_starting_source_ranking import make_exact_jd


class Phase9FApplicationConfirmationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary.name) / "applications.db"
        self.old_paths = (
            db_manager.DB_PATH,
            jd_library_manager.DB_PATH,
            tailoring_version_manager.DB_PATH,
        )
        configure_database(self.database_path)
        self.base = insert_base_resume(self.database_path, strong=False)
        self.blueprint = insert_blueprint(self.database_path, strong=True)
        self.original_jd = make_exact_jd()
        self.persisted_jd = save_exact_jd(self.database_path)
        self.ranking, self.recommendation = build_scope(
            self.database_path,
            phase9f_a_snapshot=self.original_jd,
        )
        init_phase9f_application_confirmation_schema()

    def tearDown(self) -> None:
        (
            db_manager.DB_PATH,
            jd_library_manager.DB_PATH,
            tailoring_version_manager.DB_PATH,
        ) = self.old_paths
        self.temporary.cleanup()

    def confirm(self, *, source_fingerprint=None, intensity=None, intent="intent-1"):
        winner = self.ranking["recommended_source"]
        return confirm_phase9f_application_session(
            phase9f_a_snapshot=self.original_jd,
            persisted_exact_jd_snapshot=self.persisted_jd,
            ranking_result=self.ranking,
            phase9f_c_recommendation=self.recommendation,
            confirmed_normalized_source_fingerprint=(
                source_fingerprint
                or winner["normalized_source_fingerprint"]
            ),
            confirmed_intensity=(
                intensity or self.recommendation["recommended_intensity"]
            ),
            application_intent_id=intent,
        )

    def counts(self) -> dict[str, int]:
        connection = tailoring_version_manager._connect()
        try:
            names = (
                "applications",
                "application_job_links",
                "application_analysis_versions",
                "application_blueprint_decisions",
                "application_blueprint_binding_events",
                "phase9f_application_confirmations",
                "phase9f_application_confirmation_events",
                "application_tailoring_versions",
            )
            existing = {
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            return {
                name: (
                    int(
                        connection.execute(
                            f"SELECT COUNT(*) FROM {name}"
                        ).fetchone()[0]
                    )
                    if name in existing
                    else 0
                )
                for name in names
            }
        finally:
            connection.close()

    def test_recommended_blueprint_creates_one_complete_session(self):
        result = self.confirm()
        self.assertEqual(result["cache_status"], "created")
        application_id = result["confirmation"]["application_id"]
        self.assertIsNotNone(db_manager.get_application_by_id(application_id))
        decision = get_current_application_blueprint_decision(application_id)
        self.assertEqual(
            decision["phase9e_version"],
            PHASE9E_PHASE9F_D_EXACT_BINDING_VERSION,
        )
        self.assertEqual(decision["current_scope_status"], "current")
        self.assertEqual(
            decision["selection"]["selected_source"], "global_blueprint"
        )
        self.assertEqual(
            decision["role_family_classification"]["role_family_label"],
            "AI & Full-Stack Software Engineering",
        )
        self.assertEqual(self.counts()["application_analysis_versions"], 1)
        self.assertEqual(self.counts()["application_tailoring_versions"], 0)
        self.assertEqual(
            get_phase9f_application_confirmation(application_id)[
                "confirmation_id"
            ],
            result["confirmation"]["confirmation_id"],
        )

    def test_recommended_base_resume_is_bound_exactly(self):
        connection = tailoring_version_manager._connect()
        try:
            connection.execute(
                "UPDATE global_blueprint_versions SET status='superseded'"
            )
            connection.commit()
        finally:
            connection.close()
        ranking, recommendation = build_scope(
            self.database_path,
            phase9f_a_snapshot=self.original_jd,
        )
        self.assertEqual(
            ranking["recommended_source"]["source_type"], "base_resume"
        )
        result = confirm_phase9f_application_session(
            phase9f_a_snapshot=self.original_jd,
            persisted_exact_jd_snapshot=self.persisted_jd,
            ranking_result=ranking,
            phase9f_c_recommendation=recommendation,
            confirmed_normalized_source_fingerprint=ranking[
                "recommended_source"
            ]["normalized_source_fingerprint"],
            confirmed_intensity=recommendation["recommended_intensity"],
            application_intent_id="recommended-base",
        )
        decision = get_current_application_blueprint_decision(
            result["confirmation"]["application_id"]
        )
        self.assertEqual(decision["current_scope_status"], "current")
        self.assertEqual(decision["selection"]["selected_source"], "base_resume")
        self.assertEqual(
            decision["starting_snapshot"]["source_identity"]["source_id"],
            self.base["master_version_id"],
        )

    def test_base_override_uses_base_candidate_analysis_not_winner(self):
        base = next(
            row
            for row in self.ranking["ranked_candidates"]
            if row["source_type"] == "base_resume"
        )
        result = self.confirm(
            source_fingerprint=base["normalized_source_fingerprint"],
            intensity="minor",
        )
        confirmation = result["confirmation"]["confirmation_snapshot"]
        self.assertEqual(
            confirmation["selected_candidate"]["source_type"], "base_resume"
        )
        self.assertEqual(
            confirmation["selected_candidate"][
                "candidate_analysis_snapshot_fingerprint"
            ],
            base["candidate_analysis_snapshot_fingerprint"],
        )
        self.assertNotEqual(
            confirmation["selected_candidate"][
                "candidate_analysis_snapshot_fingerprint"
            ],
            self.ranking["recommended_source"][
                "candidate_analysis_snapshot_fingerprint"
            ],
        )
        self.assertEqual(
            result["confirmation"]["override_classification"],
            "source_and_intensity_override",
        )
        content = confirmation["semantic_identity"][
            "confirmation_content_identity"
        ]
        self.assertEqual(
            content["recommendation"]["recommended_source"][
                "normalized_source_fingerprint"
            ],
            self.ranking["recommended_source"][
                "normalized_source_fingerprint"
            ],
        )
        self.assertEqual(
            content["recommendation"][
                "recommended_intensity_for_recommended_source"
            ],
            self.recommendation["recommended_intensity"],
        )
        self.assertEqual(content["confirmation"]["confirmed_intensity"], "minor")
        self.assertEqual(
            content["confirmation"][
                "selected_candidate_analysis_snapshot_fingerprint"
            ],
            base["candidate_analysis_snapshot_fingerprint"],
        )

    def test_same_operation_is_idempotent_but_new_intent_creates_session(self):
        first = self.confirm(intent="one-intent")
        counts = self.counts()
        second = self.confirm(intent="one-intent")
        self.assertEqual(second["cache_status"], "exact_operation_reused")
        self.assertEqual(
            first["confirmation"]["application_id"],
            second["confirmation"]["application_id"],
        )
        self.assertEqual(self.counts(), counts)
        third = self.confirm(intent="new-intent")
        self.assertNotEqual(
            first["confirmation"]["application_id"],
            third["confirmation"]["application_id"],
        )

    def test_changed_ranking_scope_fails_closed_with_zero_rows(self):
        connection = tailoring_version_manager._connect()
        try:
            connection.execute(
                "UPDATE global_blueprint_versions SET status='superseded'"
            )
            connection.commit()
        finally:
            connection.close()
        before = self.counts()
        with self.assertRaisesRegex(Phase9FDConfirmationError, "scope changed"):
            self.confirm()
        self.assertEqual(self.counts(), before)

    def test_removed_blueprint_fails_closed_with_zero_d_rows(self):
        remove_global_blueprint_from_reuse(
            blueprint_id=self.blueprint["blueprint_id"],
            blueprint_fingerprint=self.blueprint["blueprint_fingerprint"],
            acknowledged=True,
            reason="Focused Phase 9F-D removed-source test.",
        )
        before = self.counts()
        with self.assertRaisesRegex(Phase9FDConfirmationError, "scope changed"):
            self.confirm(intent="removed-blueprint")
        self.assertEqual(self.counts(), before)

    def test_changed_exact_jd_rolls_back_every_d_row(self):
        connection = tailoring_version_manager._connect()
        try:
            connection.execute(
                """
                UPDATE job_description_versions
                SET raw_text = raw_text || ' changed after preparation'
                WHERE job_description_id = ? AND source_version_id = ?
                """,
                (
                    self.persisted_jd["library_jd_id"],
                    self.persisted_jd["source_version_id"],
                ),
            )
            connection.commit()
        finally:
            connection.close()
        before = self.counts()
        with self.assertRaisesRegex(ValueError, "changed after"):
            self.confirm(intent="changed-jd")
        self.assertEqual(self.counts(), before)

    def test_stale_phase9f_c_fails_before_any_write(self):
        stale = copy.deepcopy(self.recommendation)
        stale["recommended_intensity"] = (
            "minor"
            if self.recommendation["recommended_intensity"] != "minor"
            else "reuse"
        )
        before = self.counts()
        with self.assertRaisesRegex(Phase9FDConfirmationError, "stale"):
            confirm_phase9f_application_session(
                phase9f_a_snapshot=self.original_jd,
                persisted_exact_jd_snapshot=self.persisted_jd,
                ranking_result=self.ranking,
                phase9f_c_recommendation=stale,
                confirmed_normalized_source_fingerprint=self.ranking[
                    "recommended_source"
                ]["normalized_source_fingerprint"],
                confirmed_intensity="minor",
                application_intent_id="stale-c",
            )
        self.assertEqual(self.counts(), before)

    def test_phase9e_failure_rolls_back_the_whole_transaction(self):
        before = self.counts()
        with patch.object(
            confirmation_manager,
            "persist_exact_phase9f_d_binding_with_connection",
            side_effect=RuntimeError("injected Phase 9E failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "injected Phase 9E"):
                self.confirm(intent="phase9e-failure")
        self.assertEqual(self.counts(), before)

    def test_confirmation_event_failure_rolls_back_the_whole_transaction(self):
        before = self.counts()
        with patch.object(
            confirmation_manager,
            "_insert_confirmation_event",
            side_effect=RuntimeError("injected event failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "injected event"):
                self.confirm(intent="event-failure")
        self.assertEqual(self.counts(), before)

    def test_intensity_override_remains_separate_from_recommendation(self):
        alternate = (
            "minor"
            if self.recommendation["recommended_intensity"] != "minor"
            else "reuse"
        )
        result = self.confirm(intensity=alternate)
        snapshot = result["confirmation"]["confirmation_snapshot"]
        content = snapshot["semantic_identity"][
            "confirmation_content_identity"
        ]
        self.assertEqual(
            content["recommendation"][
                "recommended_intensity_for_recommended_source"
            ],
            self.recommendation["recommended_intensity"],
        )
        self.assertEqual(
            content["confirmation"]["confirmed_intensity"], alternate
        )

    def test_baseline_adapter_preserves_exact_existing_report_contract(self):
        prepared = prepare_phase9f_d_confirmation(
            phase9f_a_snapshot=self.original_jd,
            persisted_exact_jd_snapshot=self.persisted_jd,
            ranking_result=self.ranking,
            phase9f_c_recommendation=self.recommendation,
            confirmed_normalized_source_fingerprint=self.ranking[
                "recommended_source"
            ]["normalized_source_fingerprint"],
            confirmed_intensity=self.recommendation[
                "recommended_intensity"
            ],
        )
        report = build_application_baseline_report(prepared)
        for key in (
            "resume_profile",
            "raw_resume_text",
            "jd_profile",
            "raw_jd_text",
            "keyword_match",
            "stable_analysis",
            "bullets",
            "structure",
            "overall_score",
            "summary",
        ):
            self.assertIn(key, report)
        self.assertEqual(
            report["stable_analysis"]["canonical_requirements"],
            prepared["selected_candidate_analysis"][
                "candidate_analysis_snapshot"
            ]["stable_analysis_snapshot"]["canonical_requirements"],
        )

    def test_d_stops_before_execution(self):
        result = self.confirm()
        application_id = result["confirmation"]["application_id"]
        context = resolve_current_phase9e_generation_context(application_id)
        self.assertEqual(
            context["status"],
            PHASE9F_D_EXECUTION_NOT_STARTED_STATUS,
        )
        self.assertFalse(context["can_generate"])
        self.assertEqual(context["source_binding_status"], "bound")
        self.assertEqual(context["execution_status"], "not_started")
        self.assertEqual(
            context["confirmed_intensity"],
            result["confirmation"]["confirmed_intensity"],
        )
        self.assertEqual(
            result["zero_cost_diagnostics"],
            {
                "model_call_count": 0,
                "embedding_call_count": 0,
                "chroma_read_count": 0,
                "chroma_write_count": 0,
                "generation_call_count": 0,
                "fitting_call_count": 0,
            },
        )

    def test_application_workflow_summary_shows_confirmed_setup_only(self):
        result = self.confirm(intensity="minor", intent="summary")
        application_id = result["confirmation"]["application_id"]
        decision = get_current_application_blueprint_decision(application_id)
        overview = build_application_workflow_overview(
            application_id=application_id,
            application_record=db_manager.get_application_by_id(application_id),
            baseline_report=db_manager.get_application_by_id(application_id)[
                "report"
            ],
            exact_jd=get_exact_job_description_for_application(application_id),
            current_decision=decision,
            current_result=None,
            phase9f_d_confirmation=get_phase9f_application_confirmation(
                application_id
            ),
        )
        self.assertEqual(
            overview["workflow_mode"],
            "Phase 9F-D configured Application Session",
        )
        self.assertEqual(overview["current_result"], "No tailored result yet")
        self.assertEqual(overview["next_action"], "Begin Minor tailoring")
        self.assertTrue(overview["phase9f_d_recommended_source"])
        self.assertTrue(overview["phase9f_d_confirmed_source"])
        self.assertEqual(overview["phase9f_d_confirmed_intensity"], "minor")

    def test_tampered_selected_analysis_fails_before_any_write(self):
        broken = copy.deepcopy(self.ranking)
        broken["recommended_source"]["candidate_analysis_snapshot"][
            "resume_text_snapshot"
        ] += " tampered"
        broken["ranked_candidates"][0] = broken["recommended_source"]
        before = self.counts()
        with self.assertRaises(Phase9FDConfirmationError):
            confirm_phase9f_application_session(
                phase9f_a_snapshot=self.original_jd,
                persisted_exact_jd_snapshot=self.persisted_jd,
                ranking_result=broken,
                phase9f_c_recommendation=self.recommendation,
                confirmed_normalized_source_fingerprint=broken[
                    "recommended_source"
                ]["normalized_source_fingerprint"],
                confirmed_intensity=self.recommendation[
                    "recommended_intensity"
                ],
                application_intent_id="tampered",
            )
        self.assertEqual(self.counts(), before)

    def test_pre_d_automatic_save_then_exact_reuse_is_explicit_and_idempotent(self):
        separate = Path(self.temporary.name) / "preparation.db"
        configure_database(separate)
        jd_library_manager.init_jd_library()
        connection = jd_library_manager._connect()
        try:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM job_descriptions"
                ).fetchone()[0],
                0,
            )
        finally:
            connection.close()
        indexed: list[int] = []
        first, first_receipt = prepare_persisted_exact_jd_for_confirmation(
            self.original_jd,
            index_fn=lambda jd_id: indexed.append(jd_id) or 3,
        )
        second, second_receipt = prepare_persisted_exact_jd_for_confirmation(
            self.original_jd,
            index_fn=lambda jd_id: indexed.append(jd_id) or 3,
        )
        self.assertEqual(first["library_jd_id"], second["library_jd_id"])
        self.assertEqual(first["source_version_id"], second["source_version_id"])
        self.assertTrue(first_receipt["chroma_indexing_occurred"])
        self.assertTrue(second_receipt["exact_existing_version_reused"])
        self.assertEqual(indexed, [first["library_jd_id"]])

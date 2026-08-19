"""Real temporary-database, zero-cost Phase 9F-D smoke check."""

from __future__ import annotations

import tempfile
from pathlib import Path

from database import db_manager, jd_library_manager, tailoring_version_manager
from database.application_blueprint_manager import (
    get_current_application_blueprint_decision,
    resolve_current_phase9e_generation_context,
)
from database.phase9f_application_confirmation_manager import (
    confirm_phase9f_application_session,
)
from tests.phase9f_d_test_support import (
    build_scope,
    configure_database,
    insert_base_resume,
    insert_blueprint,
    save_exact_jd,
)
from tests.test_phase9f_starting_source_ranking import make_exact_jd
from tailoring.phase9f_application_confirmation import (
    PHASE9F_D_EXECUTION_NOT_STARTED_STATUS,
)


def main() -> None:
    old_paths = (
        db_manager.DB_PATH,
        jd_library_manager.DB_PATH,
        tailoring_version_manager.DB_PATH,
    )
    try:
        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "phase9f-d-smoke.db"
            configure_database(database_path)
            insert_base_resume(database_path, strong=False)
            insert_blueprint(database_path, strong=True, marker="d-smoke")
            exact_jd = make_exact_jd()
            persisted_jd = save_exact_jd(database_path)
            ranking, recommendation = build_scope(
                database_path,
                phase9f_a_snapshot=exact_jd,
            )
            winner = ranking["recommended_source"]
            arguments = {
                "phase9f_a_snapshot": exact_jd,
                "persisted_exact_jd_snapshot": persisted_jd,
                "ranking_result": ranking,
                "phase9f_c_recommendation": recommendation,
                "confirmed_normalized_source_fingerprint": winner[
                    "normalized_source_fingerprint"
                ],
                "confirmed_intensity": recommendation[
                    "recommended_intensity"
                ],
                "application_intent_id": "phase9f-d-smoke-intent",
            }
            first = confirm_phase9f_application_session(**arguments)
            repeated = confirm_phase9f_application_session(**arguments)
            application_id = first["confirmation"]["application_id"]
            decision = get_current_application_blueprint_decision(application_id)
            generation_context = resolve_current_phase9e_generation_context(
                application_id
            )

            assert first["cache_status"] == "created"
            assert repeated["cache_status"] == "exact_operation_reused"
            assert (
                repeated["confirmation"]["application_id"] == application_id
            )
            assert decision is not None
            assert decision["current_scope_status"] == "current"
            assert generation_context["status"] == (
                PHASE9F_D_EXECUTION_NOT_STARTED_STATUS
            )
            assert generation_context["can_generate"] is False
            assert generation_context["source_binding_status"] == "bound"
            assert generation_context["execution_status"] == "not_started"
            assert first["zero_cost_diagnostics"] == {
                "model_call_count": 0,
                "embedding_call_count": 0,
                "chroma_read_count": 0,
                "chroma_write_count": 0,
                "generation_call_count": 0,
                "fitting_call_count": 0,
            }
            connection = tailoring_version_manager._connect()
            try:
                assert connection.execute(
                    "SELECT COUNT(*) FROM applications"
                ).fetchone()[0] == 1
                assert connection.execute(
                    "SELECT COUNT(*) FROM phase9f_application_confirmations"
                ).fetchone()[0] == 1
                assert connection.execute(
                    "SELECT COUNT(*) FROM application_analysis_versions"
                ).fetchone()[0] == 1
            finally:
                connection.close()
            print(
                "Phase 9F-D smoke PASS: application_sessions=1 "
                "confirmations=1 analysis_rows=1 exact_operation_reuse=yes "
                f"source={winner['source_type']} "
                f"intensity={recommendation['recommended_intensity']} "
                "execution_started=no model_calls=0 embedding_calls=0 "
                "chroma_reads=0 chroma_writes=0 generation_calls=0 "
                "fitting_calls=0"
            )
    finally:
        (
            db_manager.DB_PATH,
            jd_library_manager.DB_PATH,
            tailoring_version_manager.DB_PATH,
        ) = old_paths


if __name__ == "__main__":
    main()

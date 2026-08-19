"""Real temporary-database, zero-cost Phase 9F-E Reuse smoke check."""

from __future__ import annotations

import tempfile
from pathlib import Path

from database import db_manager, jd_library_manager, tailoring_version_manager
from database.application_resume_output_manager import (
    resolve_application_resume_output,
)
from database.application_resume_result_manager import (
    list_application_resume_results,
)
from database.phase9f_application_execution_manager import (
    execute_phase9f_reuse,
)
from tests.phase9f_d_test_support import configure_database
from tests.phase9f_e_test_support import create_d_reuse_session


def main() -> None:
    old_paths = (
        db_manager.DB_PATH,
        jd_library_manager.DB_PATH,
        tailoring_version_manager.DB_PATH,
    )
    try:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database_path = root / "phase9f-e-smoke.db"
            source_root = root / "source-artifacts"
            source_root.mkdir()
            result_root = root / "application-results"
            configure_database(database_path)
            state = create_d_reuse_session(
                database_path,
                source_type="global_blueprint",
                artifact_root=source_root,
            )
            application_id = state["application_id"]
            first = execute_phase9f_reuse(
                application_id=application_id,
                actor_label="Phase 9F-E smoke",
                artifact_root=result_root,
            )
            repeated = execute_phase9f_reuse(
                application_id=application_id,
                actor_label="Phase 9F-E smoke",
                artifact_root=result_root,
            )
            result = first["application_result"]
            output = resolve_application_resume_output(application_id)

            assert first["execution"]["status"] == "completed"
            assert first["execution"]["phase8_mode"] == (
                "strict_inherited_source_phase8"
            )
            assert repeated["cache_status"] == "completed_reused"
            assert repeated["execution"]["execution_id"] == (
                first["execution"]["execution_id"]
            )
            assert repeated["application_result"]["application_result_id"] == (
                result["application_result_id"]
            )
            assert len(list_application_resume_results(application_id)) == 1
            assert output["output_kind"] == "immutable_application_result"
            assert output["output_id"] == result["application_result_id"]
            assert output["artifacts"]
            assert all(
                Path(row["materialized_path"]).is_file()
                for row in output["artifacts"]
            )
            assert first["zero_cost_diagnostics"] == {
                "analysis_model_call_count": 0,
                "chatbot_model_call_count": 0,
                "embedding_call_count": 0,
                "chroma_read_count": 0,
                "chroma_write_count": 0,
                "resume_generation_call_count": 0,
                "content_rewrite_call_count": 0,
                "content_changing_fit_call_count": 0,
            }
            connection = tailoring_version_manager._connect()
            try:
                draft_count = int(
                    connection.execute(
                        """
                        SELECT COUNT(*) FROM application_tailoring_versions
                        WHERE application_id=?
                        """,
                        (application_id,),
                    ).fetchone()[0]
                )
            finally:
                connection.close()
            assert draft_count == 0
            print(
                "Phase 9F-E smoke PASS: executions=1 results=1 drafts=0 "
                "source=global_blueprint content_changed=no editable=no "
                "page_count=1 phase8=strict_inherited_source_phase8 "
                "exact_reuse=yes output_resolver=yes model_calls=0 "
                "embedding_calls=0 chroma_reads=0 chroma_writes=0 "
                "generation_calls=0 rewrite_calls=0 fitting_calls=0"
            )
    finally:
        (
            db_manager.DB_PATH,
            jd_library_manager.DB_PATH,
            tailoring_version_manager.DB_PATH,
        ) = old_paths


if __name__ == "__main__":
    main()

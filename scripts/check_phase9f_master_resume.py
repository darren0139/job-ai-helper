"""Zero-cost Phase 9F-Master persistence and exact-reuse smoke check."""

from __future__ import annotations

import tempfile
from pathlib import Path

from database import global_master_resume_manager as manager
from database import tailoring_version_manager as base_manager
from tailoring.phase9f_master_resume import (
    build_prepared_master_resume_snapshot,
    prepare_master_resume_from_reusable_profile,
    sha256_bytes,
    sha256_text,
)


def main() -> None:
    with tempfile.TemporaryDirectory() as name:
        old_path = base_manager.DB_PATH
        try:
            base_manager.DB_PATH = Path(name) / "phase9f-master-smoke.sqlite"
            manager.init_global_master_resume_registry()
            artifact = b"phase9f-master-zero-cost-smoke-artifact"
            text = "Phase 9F Master Resume\n" + ("Verified evidence. " * 20)
            inspection = {
                "artifact_sha256": sha256_bytes(artifact),
                "artifact_type": "docx",
                "artifact_size_bytes": len(artifact),
                "original_filename": "master.docx",
                "media_type": (
                    "application/vnd.openxmlformats-officedocument."
                    "wordprocessingml.document"
                ),
                "artifact_bytes": artifact,
                "resume_text": text,
                "resume_text_sha256": sha256_text(text),
                "resume_text_char_count": len(text),
            }
            prepared = build_prepared_master_resume_snapshot(
                inspection=inspection,
                structured_profile={
                    "name": "Smoke Candidate",
                    "contact": {
                        "email": "",
                        "phone": "",
                        "linkedin": "",
                        "github": "",
                        "portfolio": "",
                    },
                    "summary": "",
                    "education": [],
                    "experience": [],
                    "projects": [],
                    "skills": {
                        "languages": ["Python"],
                        "frameworks": [],
                        "tools": [],
                        "concepts": [],
                        "platforms": [],
                    },
                },
                extraction_provenance={
                    "method": "zero_cost_smoke_fixture",
                    "call_count": 0,
                    "embedding_call_count": 0,
                    "api_usage": {"call_count": 0},
                },
                current_master=None,
                preparation_mode="zero_cost_smoke_fixture",
            )
            first = manager.commit_prepared_global_master_resume(prepared)
            current = manager.get_current_global_master_resume()
            reused = prepare_master_resume_from_reusable_profile(
                inspection=inspection,
                reusable_master=current,
                current_master=current,
            )
            second = manager.commit_prepared_global_master_resume(reused)
            versions = manager.list_global_master_resume_versions()
            events = manager.list_global_master_resume_events()
            assert first["outcome"] == "master_set"
            assert second["outcome"] == "exact_current_reused"
            assert len(versions) == 1
            assert len(events) == 2
            assert current["resume_text"] == text

            removed = manager.clear_current_global_master_resume(
                expected_master_version_id=current["master_version_id"],
                expected_master_version_fingerprint=current[
                    "master_version_fingerprint"
                ],
            )
            assert removed["outcome"] == "current_master_removed"
            assert manager.get_current_global_master_resume() is None
            assert len(manager.list_global_master_resume_versions()) == 1
            assert len(manager.list_global_master_resume_events()) == 3
            print(
                "Phase 9F-Master smoke PASS: "
                f"version={current['version_number']} "
                f"master_id={current['master_version_id'][:12]} "
                "model_calls=0 embedding_calls=0 exact_reuse=yes "
                "clear_current=yes history_preserved=yes"
            )
        finally:
            base_manager.DB_PATH = old_path


if __name__ == "__main__":
    main()

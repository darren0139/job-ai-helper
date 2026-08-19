from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from database import tailoring_version_manager
from database.phase9f_tailoring_execution_manager import (
    _canonical_fit_settings,
    build_phase9f_normal_fit_input_fingerprint,
    build_phase9f_private_fit_input_payload,
    run_phase9f_tailoring_fit,
)
from database.tailoring_generation_control import (
    find_cached_tailoring_generation,
    record_generation_metadata,
)
from resume_builder.fitting_provenance import (
    PHASE6C_LEGACY_EXHAUSTIVE_SEARCH_ALGORITHM_VERSION,
    PHASE6C_LEGACY_EXHAUSTIVE_FITTING_OPTIMIZATION_VERSION,
    PHASE6C_SEARCH_ALGORITHM_VERSION,
    UNKNOWN_LEGACY_FITTING_SEARCH_ALGORITHM_VERSION,
    normalise_fitting_search_algorithm_provenance,
    resolve_fitting_search_algorithm_version,
)
from tailoring.tailoring_generation_fingerprint import (
    build_tailoring_input_fingerprint,
)


def _input_fingerprint(
    *,
    generation_settings: dict,
    approved_generation: dict | None = None,
    lock_projects: bool = False,
) -> str:
    return build_tailoring_input_fingerprint(
        report={
            "meta": {"analysis_cache": {"input_fingerprint": "analysis"}},
            "stable_analysis": {"input_fingerprint": "stable"},
            "resume_profile": {},
            "jd_profile": {},
            "raw_jd_text": "Role requirements",
        },
        evidence_items=[],
        generation_settings=generation_settings,
        generation_kind="fit_only",
        model_id="deterministic-local-fit",
        approved_generation=approved_generation,
        lock_projects=lock_projects,
    )


class Phase6CFitSearchProvenanceTests(unittest.TestCase):
    def test_historical_results_are_normalised_without_assuming_bounded(self) -> None:
        exhaustive = {
            "fitting_optimization_version": (
                PHASE6C_LEGACY_EXHAUSTIVE_FITTING_OPTIMIZATION_VERSION
            ),
        }
        self.assertEqual(
            resolve_fitting_search_algorithm_version(exhaustive),
            PHASE6C_LEGACY_EXHAUSTIVE_SEARCH_ALGORITHM_VERSION,
        )
        self.assertEqual(
            normalise_fitting_search_algorithm_provenance(exhaustive)[
                "fitting_search_algorithm_version"
            ],
            PHASE6C_LEGACY_EXHAUSTIVE_SEARCH_ALGORITHM_VERSION,
        )

        unknown = {"fitting_optimization_version": "unrecognised-v0"}
        self.assertEqual(
            resolve_fitting_search_algorithm_version(unknown),
            UNKNOWN_LEGACY_FITTING_SEARCH_ALGORITHM_VERSION,
        )
        self.assertEqual(
            resolve_fitting_search_algorithm_version({}),
            UNKNOWN_LEGACY_FITTING_SEARCH_ALGORITHM_VERSION,
        )
        self.assertEqual(
            resolve_fitting_search_algorithm_version(
                {
                    "fitting_optimization_version": (
                        PHASE6C_SEARCH_ALGORITHM_VERSION
                    )
                }
            ),
            UNKNOWN_LEGACY_FITTING_SEARCH_ALGORITHM_VERSION,
        )
        self.assertEqual(
            resolve_fitting_search_algorithm_version(
                {
                    "fitting_search_algorithm_version": (
                        PHASE6C_SEARCH_ALGORITHM_VERSION
                    )
                }
            ),
            PHASE6C_SEARCH_ALGORITHM_VERSION,
        )

    def test_normal_fit_identity_changes_only_for_search_strategy(self) -> None:
        common = {
            "lifecycle": {"generation_input_fingerprint": "generation"},
            "projects": {"recommended_projects": []},
            "skills": {"skill_lines": []},
            "canonical_fit_settings": {"spacing_mode": "paragraph_spacing"},
            "source_artifact": {"sha256": "source"},
            "section_scope_fingerprint": "scope",
        }
        exhaustive = build_phase9f_normal_fit_input_fingerprint(
            **common,
            fitting_search_algorithm_version=(
                PHASE6C_LEGACY_EXHAUSTIVE_SEARCH_ALGORITHM_VERSION
            ),
        )
        bounded = build_phase9f_normal_fit_input_fingerprint(**common)

        self.assertNotEqual(exhaustive, bounded)
        self.assertEqual(
            _canonical_fit_settings({})[
                "fitting_search_algorithm_version"
            ],
            PHASE6C_SEARCH_ALGORITHM_VERSION,
        )

    def test_fit_only_cache_does_not_reuse_legacy_search_identity(self) -> None:
        with TemporaryDirectory() as temporary:
            previous_path = tailoring_version_manager.DB_PATH
            tailoring_version_manager.DB_PATH = Path(temporary) / "test.db"
            try:
                legacy_fingerprint = _input_fingerprint(
                    generation_settings={
                        "fitting_search_algorithm_version": (
                            PHASE6C_LEGACY_EXHAUSTIVE_SEARCH_ALGORITHM_VERSION
                        )
                    }
                )
                bounded_fingerprint = _input_fingerprint(
                    generation_settings={
                        "fitting_search_algorithm_version": (
                            PHASE6C_SEARCH_ALGORITHM_VERSION
                        )
                    }
                )
                tailoring_version_manager.save_application_tailoring_generation(
                    application_id=1,
                    generation_id="legacy-fit",
                    projects={"recommended_projects": []},
                    skills={"skill_lines": []},
                    fit_result={"fit_one_page": True},
                )
                record_generation_metadata(
                    application_id=1,
                    generation_id="legacy-fit",
                    input_fingerprint=legacy_fingerprint,
                    generation_kind="fit_only",
                )

                self.assertIsNotNone(
                    find_cached_tailoring_generation(
                        application_id=1,
                        input_fingerprint=legacy_fingerprint,
                        generation_kind="fit_only",
                    )
                )
                self.assertIsNone(
                    find_cached_tailoring_generation(
                        application_id=1,
                        input_fingerprint=bounded_fingerprint,
                        generation_kind="fit_only",
                    )
                )
            finally:
                tailoring_version_manager.DB_PATH = previous_path

    def test_private_fit_payload_and_completed_history_behavior(self) -> None:
        fit_snapshot = {
            "settings": _canonical_fit_settings({}),
            "settings_fingerprint": "fit-settings",
            "fitting_search_algorithm_version": (
                PHASE6C_SEARCH_ALGORITHM_VERSION
            ),
        }
        payload = build_phase9f_private_fit_input_payload(
            fit_snapshot=fit_snapshot,
            projects={"recommended_projects": []},
            skills={"skill_lines": []},
            source_artifact={"sha256": "source"},
            section_scope_fingerprint="scope",
        )
        self.assertEqual(
            payload["fitting_search_algorithm_version"],
            PHASE6C_SEARCH_ALGORITHM_VERSION,
        )
        self.assertEqual(
            payload["fit_snapshot"]["fitting_search_algorithm_version"],
            PHASE6C_SEARCH_ALGORITHM_VERSION,
        )

        historical = {
            "status": "completed",
            "stage_outputs": {
                "fitting": {
                    "status": "completed",
                    "result": {
                        "fitting_optimization_version": (
                        PHASE6C_LEGACY_EXHAUSTIVE_FITTING_OPTIMIZATION_VERSION
                        )
                    },
                }
            },
        }
        historical_before = deepcopy(historical)
        fit_writer = Mock()
        with patch(
            "database.phase9f_tailoring_execution_manager."
            "prepare_or_reuse_phase9f_tailoring_execution",
            return_value={"execution": historical, "prepared": {}},
        ):
            result = run_phase9f_tailoring_fit(
                application_id=1,
                fit_writer=fit_writer,
            )

        self.assertEqual(result["cache_status"], "reused")
        fit_writer.assert_not_called()
        self.assertEqual(historical, historical_before)

    def test_approval_content_identity_ignores_search_strategy(self) -> None:
        final_projects = {"recommended_projects": [{"title": "Project"}]}
        approved_legacy = {
            "generation_id": "approved",
            "fit_result": {
                "tailored_projects_used": final_projects,
                "tailored_skills_used": {"skill_lines": []},
                "fitting_search_algorithm_version": (
                    PHASE6C_LEGACY_EXHAUSTIVE_SEARCH_ALGORITHM_VERSION
                ),
            },
        }
        approved_bounded = deepcopy(approved_legacy)
        approved_bounded["fit_result"][
            "fitting_search_algorithm_version"
        ] = PHASE6C_SEARCH_ALGORITHM_VERSION

        self.assertEqual(
            _input_fingerprint(
                generation_settings={"max_projects": 3},
                approved_generation=approved_legacy,
                lock_projects=True,
            ),
            _input_fingerprint(
                generation_settings={"max_projects": 3},
                approved_generation=approved_bounded,
                lock_projects=True,
            ),
        )


if __name__ == "__main__":
    unittest.main()

"""Run the deterministic Phase 6C fitter from a saved Full Debug Bundle.

This is intentionally a benchmark-only entry point.  It never imports the
Streamlit application, the database layer, or a Projects/Skills writer.  The
input must contain an explicit fitting-settings snapshot plus the source
artifact SHA-256 and byte size; the script does not infer current defaults.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Callable, Iterable, Mapping


REQUIRED_FIT_SETTING_KEYS = (
    "max_projects",
    "max_bullets_per_project",
    "spacing_mode",
    "project_spacing_pt",
    "after_projects_spacing_pt",
    "blank_lines_between_projects",
    "blank_lines_after_projects",
    "add_spacing_before_first_project",
    "use_compact_before_delete",
    "prefer_balanced_bullets",
    "allow_skills_compaction",
    "lock_projects",
    "lock_skills",
    "minimum_total_skills",
    "page_density_mode",
    "allow_margin_compaction",
)

FIT_SETTING_ALIASES: dict[str, tuple[str, ...]] = {
    "max_projects": ("max_projects",),
    "max_bullets_per_project": (
        "max_bullets_per_project",
        "fit_effective_max_bullets",
        "fit_max_bullets_per_project",
    ),
    "spacing_mode": ("spacing_mode",),
    "project_spacing_pt": ("project_spacing_pt",),
    "after_projects_spacing_pt": ("after_projects_spacing_pt",),
    "blank_lines_between_projects": ("blank_lines_between_projects",),
    "blank_lines_after_projects": ("blank_lines_after_projects",),
    "add_spacing_before_first_project": (
        "add_spacing_before_first_project",
    ),
    "use_compact_before_delete": ("use_compact_before_delete",),
    "prefer_balanced_bullets": ("prefer_balanced_bullets",),
    "allow_skills_compaction": ("allow_skills_compaction",),
    "lock_projects": ("lock_projects",),
    "lock_skills": ("lock_skills",),
    "minimum_total_skills": ("minimum_total_skills",),
    "page_density_mode": ("page_density_mode",),
    "allow_margin_compaction": ("allow_margin_compaction",),
}

FIT_SETTINGS_PATHS = (
    ("fitting_settings",),
    ("generation_settings",),
    ("one_page_fitting_result", "fitting_settings"),
    ("one_page_fitting_result", "fit_settings"),
    ("one_page_fitting_result", "generation_settings"),
)

SOURCE_SIGNATURE_PATHS = (
    ("source_docx_sha256",),
    ("source_docx_signature",),
    ("source_artifact", "sha256"),
    ("source_artifact", "source_docx_sha256"),
    ("source_docx", "sha256"),
    ("one_page_fitting_result", "source_docx_sha256"),
    ("one_page_fitting_result", "source_docx_signature"),
    ("one_page_fitting_result", "source_signature"),
    ("debug_meta", "source_docx_sha256"),
)

SOURCE_BYTE_SIZE_PATHS = (
    ("source_docx_byte_size",),
    ("source_artifact", "byte_size"),
    ("source_docx", "byte_size"),
    ("one_page_fitting_result", "source_docx_byte_size"),
    ("debug_meta", "source_docx_byte_size"),
)

FITTING_INPUT_SNAPSHOT_PATHS = (
    ("fitting_input_snapshot",),
    ("one_page_fitting_result", "fitting_input_snapshot"),
)


class BenchmarkInputError(ValueError):
    """The bundle lacks an exact, durable Phase 6C fitting input."""


@dataclass(frozen=True)
class BenchmarkInput:
    """The immutable input snapshot needed to run the deterministic fitter."""

    projects: dict[str, Any]
    skills: dict[str, Any]
    fit_settings: dict[str, Any]
    source_docx_sha256: str
    source_docx_byte_size: int
    fields_used: dict[str, str]


def _path_label(path: Iterable[str]) -> str:
    return ".".join(path)


def _mapping_at_path(
    payload: Mapping[str, Any], path: tuple[str, ...]
) -> Mapping[str, Any] | None:
    current: Any = payload
    for part in path:
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current if isinstance(current, Mapping) else None


def _value_at_path(
    payload: Mapping[str, Any], path: tuple[str, ...]
) -> Any | None:
    current: Any = payload
    for part in path:
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def _first_mapping(
    payload: Mapping[str, Any], paths: tuple[tuple[str, ...], ...]
) -> tuple[Mapping[str, Any] | None, str | None]:
    for path in paths:
        value = _mapping_at_path(payload, path)
        if value is not None:
            return value, _path_label(path)
    return None, None


def _first_value(
    payload: Mapping[str, Any], paths: tuple[tuple[str, ...], ...]
) -> tuple[Any | None, str | None]:
    for path in paths:
        value = _value_at_path(payload, path)
        if value is not None:
            return value, _path_label(path)
    return None, None


def _require_mapping(
    bundle: Mapping[str, Any], key: str
) -> dict[str, Any]:
    value = bundle.get(key)
    if not isinstance(value, Mapping):
        raise BenchmarkInputError(
            "Full Debug Bundle cannot reproduce exact Phase 6C fitting "
            f"input: missing mapping `{key}`. No fitter was run."
        )
    return deepcopy(dict(value))


def _normalise_sha256(value: Any, field: str) -> str:
    signature = str(value or "").strip().lower()
    if len(signature) != 64 or any(
        character not in "0123456789abcdef" for character in signature
    ):
        raise BenchmarkInputError(
            "Full Debug Bundle cannot reproduce exact Phase 6C fitting "
            f"input: `{field}` is not a SHA-256 value. No fitter was run."
        )
    return signature


def _normalise_byte_size(value: Any, field: str) -> int:
    try:
        byte_size = int(value)
    except (TypeError, ValueError) as exc:
        raise BenchmarkInputError(
            "Full Debug Bundle cannot reproduce exact Phase 6C fitting "
            f"input: `{field}` is not a byte size. No fitter was run."
        ) from exc
    if byte_size < 0:
        raise BenchmarkInputError(
            "Full Debug Bundle cannot reproduce exact Phase 6C fitting "
            f"input: `{field}` is negative. No fitter was run."
        )
    return byte_size


def _extract_snapshot_input(
    bundle: Mapping[str, Any],
) -> BenchmarkInput | None:
    """Use the fitter-authored snapshot when the bundle contains one."""
    snapshot, snapshot_path = _first_mapping(
        bundle, FITTING_INPUT_SNAPSHOT_PATHS
    )
    if snapshot is None:
        return None
    caller_input = snapshot.get("caller_input")
    projects = (
        caller_input.get("projects")
        if isinstance(caller_input, Mapping)
        else None
    )
    skills = (
        caller_input.get("skills")
        if isinstance(caller_input, Mapping)
        else None
    )
    invocation = snapshot.get("fitter_invocation")
    source_artifact = snapshot.get("source_artifact")
    missing: list[str] = []
    if not isinstance(projects, Mapping):
        missing.append(f"`{snapshot_path}.caller_input.projects`")
    if not isinstance(skills, Mapping):
        missing.append(f"`{snapshot_path}.caller_input.skills`")
    if not isinstance(invocation, Mapping):
        missing.append(f"`{snapshot_path}.fitter_invocation`")
    if not isinstance(source_artifact, Mapping):
        missing.append(f"`{snapshot_path}.source_artifact`")
    if missing:
        raise BenchmarkInputError(
            "Full Debug Bundle has an incomplete fitter-authored input "
            "snapshot; the following durable fields are missing:\n- "
            + "\n- ".join(missing)
            + "\nNo fitter was run."
        )
    assert isinstance(projects, Mapping)
    assert isinstance(skills, Mapping)
    assert isinstance(invocation, Mapping)
    assert isinstance(source_artifact, Mapping)

    missing_settings = [
        key for key in REQUIRED_FIT_SETTING_KEYS if key not in invocation
    ]
    if missing_settings:
        raise BenchmarkInputError(
            "Full Debug Bundle cannot reproduce exact Phase 6C fitting "
            "input: fitter-authored snapshot is missing invocation setting(s): "
            + ", ".join(f"`{key}`" for key in missing_settings)
            + ". No fitter was run."
        )
    source_sha256 = _normalise_sha256(
        source_artifact.get("sha256"),
        f"{snapshot_path}.source_artifact.sha256",
    )
    source_byte_size = _normalise_byte_size(
        source_artifact.get("byte_size"),
        f"{snapshot_path}.source_artifact.byte_size",
    )
    return BenchmarkInput(
        projects=deepcopy(dict(projects)),
        skills=deepcopy(dict(skills)),
        fit_settings=deepcopy(dict(invocation)),
        source_docx_sha256=source_sha256,
        source_docx_byte_size=source_byte_size,
        fields_used={
            "projects": f"{snapshot_path}.caller_input.projects",
            "skills": f"{snapshot_path}.caller_input.skills",
            "fit_settings": f"{snapshot_path}.fitter_invocation",
            "source_docx_sha256": f"{snapshot_path}.source_artifact.sha256",
            "source_docx_byte_size": f"{snapshot_path}.source_artifact.byte_size",
        },
    )


def extract_benchmark_input(bundle: Mapping[str, Any]) -> BenchmarkInput:
    """Extract only explicit, reproducible fitter inputs from a bundle.

    In particular, current fitter defaults are deliberately never substituted
    for omitted historical settings.  A successful load therefore proves
    exactly which values will be passed to the fitter.
    """
    if not isinstance(bundle, Mapping):
        raise BenchmarkInputError(
            "Full Debug Bundle root must be a JSON object. No fitter was run."
        )

    snapshot_input = _extract_snapshot_input(bundle)
    if snapshot_input is not None:
        return snapshot_input

    projects = _require_mapping(bundle, "tailored_projects_result")
    skills = _require_mapping(bundle, "tailored_skills_result")

    recorded_settings, settings_path = _first_mapping(
        bundle, FIT_SETTINGS_PATHS
    )
    missing: list[str] = []
    if recorded_settings is None:
        missing.append(
            "recorded fitting settings (expected one of: "
            + ", ".join(f"`{_path_label(path)}`" for path in FIT_SETTINGS_PATHS)
            + ")"
        )
        fit_settings: dict[str, Any] = {}
        settings_field = ""
    else:
        fit_settings = {}
        missing_settings: list[str] = []
        for target_key in REQUIRED_FIT_SETTING_KEYS:
            source_key = next(
                (
                    alias
                    for alias in FIT_SETTING_ALIASES[target_key]
                    if alias in recorded_settings
                ),
                None,
            )
            if source_key is None:
                missing_settings.append(target_key)
                continue
            fit_settings[target_key] = deepcopy(recorded_settings[source_key])
        if missing_settings:
            missing.append(
                "recorded fitting setting(s) under "
                f"`{settings_path}`: "
                + ", ".join(f"`{key}`" for key in missing_settings)
            )
        settings_field = str(settings_path)

    source_signature, source_signature_path = _first_value(
        bundle, SOURCE_SIGNATURE_PATHS
    )
    source_byte_size, source_byte_size_path = _first_value(
        bundle, SOURCE_BYTE_SIZE_PATHS
    )
    if source_signature is None:
        missing.append(
            "source DOCX SHA-256 metadata (expected one of: "
            + ", ".join(
                f"`{_path_label(path)}`" for path in SOURCE_SIGNATURE_PATHS
            )
            + ")"
        )
        normalised_source_signature = ""
    else:
        normalised_source_signature = _normalise_sha256(
            source_signature, str(source_signature_path)
        )
    if source_byte_size is None:
        missing.append(
            "source DOCX byte-size metadata (expected one of: "
            + ", ".join(
                f"`{_path_label(path)}`" for path in SOURCE_BYTE_SIZE_PATHS
            )
            + ")"
        )
        normalised_source_byte_size = 0
    else:
        normalised_source_byte_size = _normalise_byte_size(
            source_byte_size, str(source_byte_size_path)
        )

    if missing:
        raise BenchmarkInputError(
            "Full Debug Bundle cannot reproduce exact Phase 6C fitting "
            "input; the following durable fields are missing:\n- "
            + "\n- ".join(missing)
            + "\nNo fitter was run. The benchmark does not infer current "
            "defaults or substitute a different source artifact."
        )

    return BenchmarkInput(
        projects=projects,
        skills=skills,
        fit_settings=fit_settings,
        source_docx_sha256=normalised_source_signature,
        source_docx_byte_size=normalised_source_byte_size,
        fields_used={
            "projects": "tailored_projects_result",
            "skills": "tailored_skills_result",
            "fit_settings": settings_field,
            "source_docx_sha256": str(source_signature_path),
            "source_docx_byte_size": str(source_byte_size_path),
        },
    )


def load_debug_bundle(path: str | Path) -> dict[str, Any]:
    """Load a JSON bundle without importing application code."""
    bundle_path = Path(path).expanduser().resolve()
    if not bundle_path.is_file():
        raise BenchmarkInputError(
            f"Debug bundle was not found: {bundle_path}. No fitter was run."
        )
    try:
        raw = json.loads(bundle_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BenchmarkInputError(
            f"Could not load debug bundle `{bundle_path}`: {exc}. "
            "No fitter was run."
        ) from exc
    if not isinstance(raw, dict):
        raise BenchmarkInputError(
            "Full Debug Bundle root must be a JSON object. No fitter was run."
        )
    return raw


def sha256_file(path: str | Path) -> str:
    """Hash the source DOCX using the fitter's source-artifact algorithm."""
    source = Path(path).expanduser().resolve()
    digest = hashlib.sha256()
    with source.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_source_docx(
    source_docx: str | Path, *, expected_sha256: str, expected_byte_size: int
) -> Path:
    """Verify the user-supplied source is exactly the recorded artifact."""
    source = Path(source_docx).expanduser().resolve()
    if not source.is_file():
        raise BenchmarkInputError(
            f"Source DOCX was not found: {source}. No fitter was run."
        )
    if source.suffix.lower() != ".docx":
        raise BenchmarkInputError(
            f"Source artifact is not a DOCX: {source}. No fitter was run."
        )
    actual_byte_size = source.stat().st_size
    if actual_byte_size != expected_byte_size:
        raise BenchmarkInputError(
            "Source DOCX byte size does not match the debug bundle; "
            "refusing an inexact benchmark.\n"
            f"- bundle: {expected_byte_size}\n"
            f"- source: {actual_byte_size}\n"
            "No fitter was run."
        )
    actual_sha256 = sha256_file(source)
    if actual_sha256 != expected_sha256:
        raise BenchmarkInputError(
            "Source DOCX SHA-256 does not match the debug bundle; "
            "refusing an inexact benchmark.\n"
            f"- bundle: {expected_sha256}\n"
            f"- source: {actual_sha256}\n"
            "No fitter was run."
        )
    return source


def _count_input(
    projects: Mapping[str, Any], skills: Mapping[str, Any]
) -> dict[str, int]:
    recommended_projects = projects.get("recommended_projects", []) or []
    project_rows = [
        project for project in recommended_projects if isinstance(project, Mapping)
    ]
    skill_lines = skills.get("skill_lines", []) or []
    return {
        "project_count": len(project_rows),
        "project_bullet_count": sum(
            len(project.get("draft_bullets", []) or [])
            for project in project_rows
        ),
        "skill_item_count": sum(
            len(line.get("items", []) or [])
            for line in skill_lines
            if isinstance(line, Mapping)
        ),
    }


def _initial_page_count(result: Mapping[str, Any]) -> int | None:
    attempts = result.get("attempts", []) or []
    if not isinstance(attempts, list):
        return None
    initial_attempt = next(
        (
            attempt
            for attempt in attempts
            if isinstance(attempt, Mapping)
            and attempt.get("attempt_type") == "initial"
        ),
        None,
    )
    if initial_attempt is None:
        initial_attempt = next(
            (attempt for attempt in attempts if isinstance(attempt, Mapping)), None
        )
    if not isinstance(initial_attempt, Mapping):
        return None
    page_count = initial_attempt.get("page_count")
    return int(page_count) if isinstance(page_count, int) else None


def _bullet_rows(projects: Mapping[str, Any]) -> list[str]:
    """Return compact, comparison-stable retained bullet descriptions."""
    output: list[str] = []
    for project_position, project in enumerate(
        projects.get("recommended_projects", []) or [], start=1
    ):
        if not isinstance(project, Mapping):
            continue
        project_id = str(
            project.get("project_id")
            or project.get("id")
            or project.get("display_title")
            or project.get("title")
            or f"project-{project_position}"
        )
        metadata_by_index = {
            int(row.get("bullet_index")): row
            for row in (project.get("bullet_evidence_priorities", []) or [])
            if isinstance(row, Mapping)
            and isinstance(row.get("bullet_index"), int)
        }
        for bullet_index, bullet in enumerate(project.get("draft_bullets", []) or []):
            text = str(bullet).strip()
            if not text:
                continue
            metadata = metadata_by_index.get(bullet_index, {})
            stored_id = metadata.get("bullet_id") or metadata.get("id")
            comparison_id = str(stored_id or hashlib.sha256(
                text.encode("utf-8")
            ).hexdigest()[:12])
            requirements = metadata.get("supported_requirement_ids", []) or []
            requirement_label = ",".join(str(value) for value in requirements)
            output.append(
                f"project={project_id} bullet_id={comparison_id} "
                f"requirements=[{requirement_label}] text={text}"
            )
    return output


def build_summary(
    benchmark_input: BenchmarkInput, result: Mapping[str, Any]
) -> str:
    """Format the comparison data after the fitter has completed."""
    starting = _count_input(benchmark_input.projects, benchmark_input.skills)
    final_projects = result.get("tailored_projects_used")
    final_skills = result.get("tailored_skills_used")
    final = _count_input(
        final_projects if isinstance(final_projects, Mapping) else {},
        final_skills if isinstance(final_skills, Mapping) else {},
    )
    lines = [
        "",
        "PHASE 6C FITTER-ONLY BENCHMARK SUMMARY",
        "debug bundle fields used:",
        *(
            f"  {label}: {field}"
            for label, field in benchmark_input.fields_used.items()
        ),
        "input and result:",
        f"  starting project count: {starting['project_count']}",
        f"  starting project bullets: {starting['project_bullet_count']}",
        f"  starting skills: {starting['skill_item_count']}",
        f"  initial pages: {_initial_page_count(result)}",
        f"  final pages: {result.get('page_count')}",
        f"  final project bullets: {final['project_bullet_count']}",
        f"  page_fill_ratio: {result.get('page_fill_ratio')}",
        f"  fit_one_page: {result.get('fit_one_page')}",
        f"  fit_status: {result.get('fit_status')}",
        "performance:",
        f"  total fitting elapsed: {result.get('fitting_elapsed_seconds')}",
        "  candidate-generation elapsed: "
        f"{result.get('candidate_generation_elapsed_seconds')}",
        f"  render elapsed: {result.get('render_elapsed_seconds')}",
        f"  LibreOffice elapsed: {result.get('libreoffice_elapsed_seconds')}",
        "  search candidate renders: "
        f"{result.get('reduction_candidates_rendered')}",
        "  total physical renders: "
        f"{result.get('candidate_states_rendered')}",
        "  LibreOffice process count: "
        f"{result.get('libreoffice_process_count')}",
        f"  cache hits/misses: {result.get('render_cache_hits')}"
        f"/{result.get('render_cache_misses')}",
        f"  coarse renders: {result.get('coarse_render_count')}",
        f"  exact-boundary renders: {result.get('exact_render_count')}",
        "  local-refinement renders: "
        f"{result.get('local_refinement_render_count')}",
        f"  restoration renders: {result.get('restoration_candidates_rendered')}",
        "  render budget used/max: "
        f"{result.get('render_budget_used')}/{result.get('render_budget')}",
        "final retained project bullets:",
    ]
    bullet_rows = _bullet_rows(
        final_projects if isinstance(final_projects, Mapping) else {}
    )
    lines.extend(f"  - {row}" for row in bullet_rows)
    if not bullet_rows:
        lines.append("  - none")
    return "\n".join(lines)


Fitter = Callable[..., dict[str, Any]]


def run_fitter_benchmark(
    benchmark_input: BenchmarkInput,
    source_docx: str | Path,
    *,
    fitter: Fitter | None = None,
) -> dict[str, Any]:
    """Run only the deterministic fitter in an auto-cleaned workspace.

    ``application_id=None`` prevents application-scoped output naming, and the
    temporary current directory confines fitter-generated DOCX/PDF candidates.
    No database function, API client, or writer is loaded or called here.
    """
    source = validate_source_docx(
        source_docx,
        expected_sha256=benchmark_input.source_docx_sha256,
        expected_byte_size=benchmark_input.source_docx_byte_size,
    )
    repo_root = Path(__file__).resolve().parents[1]
    original_cwd = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="phase6c-fit-benchmark-") as work:
        try:
            os.chdir(work)
            if fitter is None:
                repo_root_text = str(repo_root)
                if repo_root_text not in sys.path:
                    sys.path.insert(0, repo_root_text)
                from resume_builder.docx_projects_skills_replacer import (
                    generate_tailored_resume_copy_fit_one_page,
                )

                fitter = generate_tailored_resume_copy_fit_one_page
            return fitter(
                saved_resume_docx_path=source,
                tailored_projects=deepcopy(benchmark_input.projects),
                tailored_skills=deepcopy(benchmark_input.skills),
                application_id=None,
                generation_id=None,
                **deepcopy(benchmark_input.fit_settings),
            )
        finally:
            # Windows cannot remove the active directory. Restore before the
            # temporary-workspace context attempts its deterministic cleanup.
            os.chdir(original_cwd)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Benchmark only the current deterministic Phase 6C fitter using "
            "an exact Full Debug Bundle snapshot."
        )
    )
    parser.add_argument(
        "--debug-bundle",
        required=True,
        help="Path to the historical Full Debug Bundle JSON.",
    )
    parser.add_argument(
        "--source-docx",
        required=True,
        help="Path to the original source DOCX recorded by the bundle.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        benchmark_input = extract_benchmark_input(
            load_debug_bundle(args.debug_bundle)
        )
        result = run_fitter_benchmark(benchmark_input, args.source_docx)
    except BenchmarkInputError as exc:
        print(f"[BENCHMARK] {exc}", file=sys.stderr)
        return 2

    print(build_summary(benchmark_input, result))
    if result.get("page_count") is None:
        print(
            "[BENCHMARK] LibreOffice PDF verification did not complete; "
            "the benchmark result is not comparable.",
            file=sys.stderr,
        )
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

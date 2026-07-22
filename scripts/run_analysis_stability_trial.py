r"""
Run several fresh Phase 6A.1C analyses against the same résumé and JD.

This is a developer-only stability test:
- it makes real LLM API calls;
- it does not create application sessions;
- it does not generate Projects, Skills, DOCX files, or database rows;
- it saves each full report plus JSON/CSV/Markdown comparisons.

Typical usage from the project root:

    python -m scripts.run_analysis_stability_trial ^
      --resume "test_inputs\Resume_SoftwareEngineer.docx" ^
      --jd "test_inputs\garena_jd.txt" ^
      --degree IMGD ^
      --runs 3

When test_inputs contains exactly one DOCX/PDF and one TXT file, the paths
may be omitted:

    python -m scripts.run_analysis_stability_trial --degree IMGD --runs 3
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalise_band(value: Any) -> str:
    return _clean_text(value).lower()


def _resolve_user_path(value: str | None) -> Path | None:
    if not value:
        return None

    path = Path(value).expanduser()

    if not path.is_absolute():
        path = Path.cwd() / path

    return path.resolve()


def _discover_single_input(
    *,
    folder: Path,
    suffixes: tuple[str, ...],
    label: str,
) -> Path:
    if not folder.exists():
        raise ValueError(
            f"{folder} does not exist. Create it or pass --{label} explicitly."
        )

    candidates = sorted(
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in suffixes
    )

    if len(candidates) == 1:
        return candidates[0].resolve()

    if not candidates:
        suffix_text = ", ".join(suffixes)
        raise ValueError(
            f"No {label} file was found in {folder}. "
            f"Expected exactly one file with: {suffix_text}."
        )

    names = ", ".join(path.name for path in candidates)
    raise ValueError(
        f"Multiple {label} files were found in {folder}: {names}. "
        f"Pass --{label} with the file to use."
    )


def _resolve_inputs(
    resume_arg: str | None,
    jd_arg: str | None,
) -> tuple[Path, Path]:
    input_folder = PROJECT_ROOT / "test_inputs"

    resume_path = _resolve_user_path(resume_arg)
    jd_path = _resolve_user_path(jd_arg)

    if resume_path is None:
        resume_path = _discover_single_input(
            folder=input_folder,
            suffixes=(".docx", ".pdf"),
            label="resume",
        )

    if jd_path is None:
        jd_path = _discover_single_input(
            folder=input_folder,
            suffixes=(".txt",),
            label="jd",
        )

    if not resume_path.exists():
        raise ValueError(f"Résumé file does not exist: {resume_path}")

    if resume_path.suffix.lower() not in {".docx", ".pdf"}:
        raise ValueError(
            "Résumé must be a DOCX or text-based PDF: "
            f"{resume_path}"
        )

    if not jd_path.exists():
        raise ValueError(f"JD file does not exist: {jd_path}")

    if jd_path.suffix.lower() != ".txt":
        raise ValueError(f"JD must be a UTF-8 text file: {jd_path}")

    return resume_path, jd_path


def _read_inputs(
    resume_path: Path,
    jd_path: Path,
) -> tuple[str, str]:
    from parse import (
        read_jd_text,
        read_resume_docx,
        read_resume_pdf,
    )

    if resume_path.suffix.lower() == ".docx":
        resume_text = read_resume_docx(str(resume_path))
    else:
        resume_text = read_resume_pdf(str(resume_path))

    jd_text = read_jd_text(str(jd_path))
    return resume_text, jd_text


def _find_libreoffice() -> str | None:
    for command in ("soffice", "libreoffice"):
        resolved = shutil.which(command)
        if resolved:
            return resolved

    candidates: list[Path] = []

    for environment_name in (
        "PROGRAMFILES",
        "PROGRAMFILES(X86)",
    ):
        root = os.getenv(environment_name)
        if root:
            candidates.append(
                Path(root) / "LibreOffice" / "program" / "soffice.exe"
            )

    candidates.extend(
        [
            Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
            Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"),
        ]
    )

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    return None


def _auto_page_count(resume_path: Path) -> int | None:
    from pypdf import PdfReader

    if resume_path.suffix.lower() == ".pdf":
        try:
            return len(PdfReader(str(resume_path)).pages)
        except Exception as exc:
            print(
                f"[warning] Could not count PDF pages: {exc}",
                file=sys.stderr,
            )
            return None

    libreoffice = _find_libreoffice()
    if not libreoffice:
        print(
            "[warning] LibreOffice was not found; DOCX page count will be "
            "reported as unknown. Pass --actual-page-count to fix it.",
            file=sys.stderr,
        )
        return None

    with tempfile.TemporaryDirectory(
        prefix="job_ai_helper_stability_"
    ) as temporary_directory:
        temporary_root = Path(temporary_directory)
        output_directory = temporary_root / "pdf"
        profile_directory = (
            temporary_root / f"lo_profile_{uuid.uuid4().hex}"
        )
        output_directory.mkdir(parents=True, exist_ok=True)
        profile_directory.mkdir(parents=True, exist_ok=True)

        command = [
            libreoffice,
            "--headless",
            f"-env:UserInstallation={profile_directory.resolve().as_uri()}",
            "--convert-to",
            "pdf",
            "--outdir",
            str(output_directory),
            str(resume_path),
        ]

        conversion_env = os.environ.copy()
        conversion_env.pop("PYTHONHOME", None)
        conversion_env.pop("PYTHONPATH", None)

        try:
            completed = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=90,
                env=conversion_env,
                check=False,
            )
        except Exception as exc:
            print(
                f"[warning] LibreOffice page-count conversion failed: {exc}",
                file=sys.stderr,
            )
            return None

        generated_pdf = (
            output_directory / f"{resume_path.stem}.pdf"
        )

        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            if (
                generated_pdf.exists()
                and generated_pdf.stat().st_size > 0
            ):
                break
            time.sleep(0.1)

        if (
            completed.returncode != 0
            or not generated_pdf.exists()
            or generated_pdf.stat().st_size <= 0
        ):
            print(
                "[warning] LibreOffice did not create a usable PDF for "
                "page counting.\n"
                f"STDOUT: {completed.stdout.strip()}\n"
                f"STDERR: {completed.stderr.strip()}",
                file=sys.stderr,
            )
            return None

        try:
            return len(PdfReader(str(generated_pdf)).pages)
        except Exception as exc:
            print(
                f"[warning] Could not read converted PDF pages: {exc}",
                file=sys.stderr,
            )
            return None


def _run_full_analysis(
    *,
    resume_text: str,
    jd_text: str,
    degree: str,
    actual_page_count: int | None,
    include_legacy_summary: bool,
) -> dict[str, Any]:
    from analysis_stability import build_stable_analysis
    from analyzer import (
        analyse_bullets,
        analyse_degree_alignment,
        analyse_jargon,
        analyse_keyword_match,
        analyse_structure,
        compute_overall_score,
        extract_jd_profile,
        extract_resume_profile,
        summarise_overall,
    )
    from llm import get_active_model

    resume_profile = extract_resume_profile(resume_text)
    jd_profile = extract_jd_profile(jd_text)

    keyword_match = analyse_keyword_match(
        resume_profile,
        jd_profile,
        resume_text,
        jd_text,
    )
    bullets = analyse_bullets(resume_profile)
    jargon = analyse_jargon(
        resume_profile,
        degree,
        jd_profile,
        jd_text,
    )
    structure = analyse_structure(
        resume_text,
        actual_page_count=actual_page_count,
        resume_profile=resume_profile,
    )
    degree_alignment = analyse_degree_alignment(
        jd_profile,
        degree,
    )

    report: dict[str, Any] = {
        "meta": {
            "created_at": datetime.now().isoformat(
                timespec="seconds"
            ),
            "model": get_active_model("analysis"),
            "degree": degree,
            "actual_page_count": actual_page_count,
            "trial_mode": True,
        },
        "resume_profile": resume_profile,
        "jd_profile": jd_profile,
        "keyword_match": keyword_match,
        "bullets": bullets,
        "jargon": jargon,
        "structure": structure,
        "degree_alignment": degree_alignment,
        "raw_jd_text": jd_text,
    }

    report["stable_analysis"] = build_stable_analysis(
        jd_profile=jd_profile,
        keyword_match=keyword_match,
        raw_jd_text=jd_text,
        raw_resume_text=resume_text,
        resume_profile=resume_profile,
        bullet_quality_score=bullets.get(
            "bullet_quality_avg",
            0,
        ),
        structure_score=structure.get(
            "structure_score",
            0,
        ),
    )

    report["legacy_overall_score"] = compute_overall_score(
        report
    )

    if include_legacy_summary:
        report["legacy_summary"] = summarise_overall(
            {
                **report,
                "overall_score": report[
                    "legacy_overall_score"
                ],
                "passes_ats_threshold": (
                    report["legacy_overall_score"] >= 60
                ),
            }
        )

    return report


def _requirement_map(
    report: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    stable = report.get("stable_analysis", {}) or {}
    requirements = (
        stable.get("canonical_requirements", [])
        or []
    )

    return {
        str(item.get("requirement_id", "")): item
        for item in requirements
        if str(item.get("requirement_id", "")).strip()
    }


def _build_comparison(
    reports: list[dict[str, Any]],
    *,
    max_score_spread: int,
) -> dict[str, Any]:
    if not reports:
        raise ValueError("At least one report is required.")

    rows: list[dict[str, Any]] = []
    requirement_maps = [
        _requirement_map(report)
        for report in reports
    ]

    for index, report in enumerate(reports, start=1):
        stable = report.get("stable_analysis", {}) or {}

        rows.append(
            {
                "run": index,
                "score": int(
                    stable.get(
                        "deterministic_alignment_score",
                        0,
                    )
                    or 0
                ),
                "band": _normalise_band(
                    stable.get("alignment_band", "")
                ),
                "requirement_count": int(
                    stable.get("requirement_count", 0)
                    or 0
                ),
                "credited_requirement_count": int(
                    stable.get(
                        "credited_requirement_count",
                        0,
                    )
                    or 0
                ),
                "required_core_coverage": int(
                    stable.get(
                        "required_core_coverage_score",
                        0,
                    )
                    or 0
                ),
                "preferred_coverage": int(
                    stable.get(
                        "preferred_coverage_score",
                        0,
                    )
                    or 0
                ),
                "credited_evidence_strength": int(
                    stable.get(
                        "evidence_strength_score",
                        0,
                    )
                    or 0
                ),
                "bullet_quality": int(
                    stable.get(
                        "bullet_quality_component",
                        0,
                    )
                    or 0
                ),
                "structure": int(
                    stable.get(
                        "structure_component",
                        0,
                    )
                    or 0
                ),
                "input_fingerprint": str(
                    stable.get("input_fingerprint", "")
                ),
            }
        )

    scores = [row["score"] for row in rows]
    bands = [row["band"] for row in rows]
    requirement_id_sets = [
        set(requirement_map)
        for requirement_map in requirement_maps
    ]

    all_requirement_ids = sorted(
        set().union(*requirement_id_sets)
    )

    label_differences: list[dict[str, Any]] = []
    core_label_differences: list[dict[str, Any]] = []

    for requirement_id in all_requirement_ids:
        labels: list[str | None] = []
        texts: list[str] = []
        importances: list[str] = []

        for requirement_map in requirement_maps:
            item = requirement_map.get(requirement_id)

            if item is None:
                labels.append(None)
                continue

            labels.append(
                _clean_text(item.get("match_label", "")).lower()
            )
            texts.append(_clean_text(item.get("text", "")))
            importances.append(
                _clean_text(item.get("importance", "")).lower()
            )

        if len(set(labels)) > 1:
            difference = {
                "requirement_id": requirement_id,
                "text": texts[0] if texts else "",
                "importance": (
                    importances[0] if importances else ""
                ),
                "labels_by_run": labels,
            }
            label_differences.append(difference)

            if difference["importance"] in {
                "deal_breaker",
                "required",
                "core",
            }:
                core_label_differences.append(difference)

    missing_ids_by_run: list[list[str]] = []
    complete_id_set = set(all_requirement_ids)

    for requirement_ids in requirement_id_sets:
        missing_ids_by_run.append(
            sorted(complete_id_set - requirement_ids)
        )

    score_spread = max(scores) - min(scores)
    bands_stable = len(set(bands)) == 1
    requirement_ids_stable = (
        all(
            requirement_ids == requirement_id_sets[0]
            for requirement_ids in requirement_id_sets[1:]
        )
        if len(requirement_id_sets) > 1
        else True
    )
    fingerprints_stable = (
        len(
            {
                row["input_fingerprint"]
                for row in rows
            }
        )
        == 1
    )

    passed = all(
        (
            score_spread <= max_score_spread,
            bands_stable,
            requirement_ids_stable,
            not core_label_differences,
            fingerprints_stable,
        )
    )

    return {
        "run_count": len(reports),
        "runs": rows,
        "scores": scores,
        "score_spread": score_spread,
        "bands": bands,
        "bands_stable": bands_stable,
        "requirement_ids_stable": (
            requirement_ids_stable
        ),
        "missing_requirement_ids_by_run": (
            missing_ids_by_run
        ),
        "input_fingerprints_stable": (
            fingerprints_stable
        ),
        "label_differences": label_differences,
        "core_label_differences": (
            core_label_differences
        ),
        "criteria": {
            "maximum_score_spread": (
                max_score_spread
            ),
            "same_alignment_band_required": True,
            "same_requirement_ids_required": True,
            "no_core_label_differences_required": True,
            "same_input_fingerprint_required": True,
        },
        "passed": passed,
    }


def _write_csv(
    comparison: dict[str, Any],
    destination: Path,
) -> None:
    rows = comparison.get("runs", []) or []

    if not rows:
        return

    with destination.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=list(rows[0]),
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_markdown(
    comparison: dict[str, Any],
    destination: Path,
    *,
    resume_path: Path,
    jd_path: Path,
    model: str,
    reasoning_effort: str | None,
) -> None:
    status = "PASS" if comparison["passed"] else "FAIL"

    lines = [
        "# Phase 6A.1C Stability Trial",
        "",
        f"**Result:** {status}",
        "",
        f"- Résumé: `{resume_path}`",
        f"- Job description: `{jd_path}`",
        f"- Analysis model: `{model}`",
        (
            "- Reasoning effort: "
            f"`{reasoning_effort or 'provider/default'}`"
        ),
        (
            "- Score spread: "
            f"`{comparison['score_spread']}`"
        ),
        (
            "- Alignment bands stable: "
            f"`{comparison['bands_stable']}`"
        ),
        (
            "- Requirement IDs stable: "
            f"`{comparison['requirement_ids_stable']}`"
        ),
        (
            "- Core label differences: "
            f"`{len(comparison['core_label_differences'])}`"
        ),
        "",
        "## Run comparison",
        "",
        (
            "| Run | Score | Band | Requirements | Credited | "
            "Required/Core | Preferred | Evidence strength |"
        ),
        "|---:|---:|---|---:|---:|---:|---:|---:|",
    ]

    for row in comparison.get("runs", []):
        lines.append(
            "| "
            f"{row['run']} | "
            f"{row['score']} | "
            f"{row['band']} | "
            f"{row['requirement_count']} | "
            f"{row['credited_requirement_count']} | "
            f"{row['required_core_coverage']}% | "
            f"{row['preferred_coverage']}% | "
            f"{row['credited_evidence_strength']}% |"
        )

    differences = (
        comparison.get("core_label_differences", [])
        or []
    )

    lines.extend(
        [
            "",
            "## Core label differences",
            "",
        ]
    )

    if differences:
        for difference in differences:
            lines.append(
                "- "
                f"`{difference['requirement_id']}` "
                f"{difference['text']}: "
                f"{difference['labels_by_run']}"
            )
    else:
        lines.append("None.")

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            (
                "- A passing result means the fresh runs remained "
                "within the configured score spread, used the same "
                "alignment band and requirement IDs, and did not "
                "change required/core match labels."
            ),
            (
                "- This tests Phase 6A.1C analysis stability only. "
                "It does not generate or rank Projects and Skills; "
                "that belongs to Phase 6B."
            ),
        ]
    )

    destination.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run several fresh Phase 6A.1C analyses and compare "
            "their deterministic results."
        )
    )
    parser.add_argument(
        "--resume",
        help=(
            "DOCX or PDF résumé path. When omitted, exactly one "
            "DOCX/PDF must exist in test_inputs."
        ),
    )
    parser.add_argument(
        "--jd",
        help=(
            "UTF-8 TXT job-description path. When omitted, "
            "exactly one TXT must exist in test_inputs."
        ),
    )
    parser.add_argument(
        "--degree",
        required=True,
        help="Degree code used by the app, for example IMGD.",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Number of fresh analyses. Default: 3.",
    )
    parser.add_argument(
        "--analysis-model",
        help=(
            "Optional model label or provider-prefixed model ID. "
            "When omitted, the existing ANALYSIS_MODEL/MODEL "
            "configuration is used."
        ),
    )
    parser.add_argument(
        "--reasoning-effort",
        choices=("low", "medium", "high"),
        help=(
            "Optional reasoning effort for supported models. "
            "When omitted, existing environment settings are used."
        ),
    )
    parser.add_argument(
        "--actual-page-count",
        type=int,
        help=(
            "Optional fixed rendered page count. When omitted, "
            "the script tries to count pages automatically."
        ),
    )
    parser.add_argument(
        "--output-dir",
        help=(
            "Optional result directory. Default: "
            "stability_results/trial_<timestamp>."
        ),
    )
    parser.add_argument(
        "--max-score-spread",
        type=int,
        default=5,
        help="Maximum accepted score spread. Default: 5.",
    )
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=1.0,
        help="Delay between runs to reduce rate-limit risk.",
    )
    parser.add_argument(
        "--include-legacy-summary",
        action="store_true",
        help=(
            "Also make the legacy summary LLM call. Not needed "
            "for Phase 6A.1C stability testing."
        ),
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "Return exit code 2 when the comparison fails. "
            "Useful for an optional manually triggered CI job."
        ),
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.runs < 2:
        parser.error("--runs must be at least 2.")

    if args.max_score_spread < 0:
        parser.error("--max-score-spread cannot be negative.")

    try:
        resume_path, jd_path = _resolve_inputs(
            args.resume,
            args.jd,
        )
        resume_text, jd_text = _read_inputs(
            resume_path,
            jd_path,
        )
    except ValueError as exc:
        parser.error(str(exc))

    if args.reasoning_effort:
        os.environ["ANALYSIS_REASONING_EFFORT"] = (
            args.reasoning_effort
        )

    from llm import (
        get_active_model,
        set_runtime_model,
    )

    if args.analysis_model:
        set_runtime_model(
            args.analysis_model,
            route="analysis",
        )

    active_model = get_active_model("analysis")

    actual_page_count = args.actual_page_count
    if actual_page_count is None:
        actual_page_count = _auto_page_count(
            resume_path
        )

    if args.output_dir:
        output_directory = _resolve_user_path(
            args.output_dir
        )
        assert output_directory is not None
    else:
        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )
        output_directory = (
            PROJECT_ROOT
            / "stability_results"
            / f"trial_{timestamp}"
        )

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    trial_metadata = {
        "created_at": datetime.now().isoformat(
            timespec="seconds"
        ),
        "resume_path": str(resume_path),
        "jd_path": str(jd_path),
        "degree": args.degree,
        "run_count": args.runs,
        "analysis_model": active_model,
        "reasoning_effort": (
            args.reasoning_effort
            or os.getenv(
                "ANALYSIS_REASONING_EFFORT"
            )
            or os.getenv("REASONING_EFFORT")
            or None
        ),
        "actual_page_count": actual_page_count,
        "include_legacy_summary": (
            args.include_legacy_summary
        ),
    }

    (
        output_directory / "trial_metadata.json"
    ).write_text(
        json.dumps(
            trial_metadata,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("Phase 6A.1C stability trial")
    print(f"Résumé: {resume_path}")
    print(f"JD: {jd_path}")
    print(f"Model: {active_model}")
    print(
        "Reasoning effort: "
        f"{trial_metadata['reasoning_effort'] or 'provider/default'}"
    )
    print(
        "Rendered page count: "
        f"{actual_page_count if actual_page_count is not None else 'unknown'}"
    )
    print(
        "This test makes real API calls and does not create "
        "application sessions."
    )
    print()

    reports: list[dict[str, Any]] = []

    for run_index in range(1, args.runs + 1):
        print(
            f"[run {run_index}/{args.runs}] "
            "Starting fresh analysis..."
        )

        started = time.monotonic()

        try:
            report = _run_full_analysis(
                resume_text=resume_text,
                jd_text=jd_text,
                degree=args.degree,
                actual_page_count=actual_page_count,
                include_legacy_summary=(
                    args.include_legacy_summary
                ),
            )
        except Exception as exc:
            error_payload = {
                "run": run_index,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            (
                output_directory
                / f"run_{run_index:02d}_error.json"
            ).write_text(
                json.dumps(
                    error_payload,
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            print(
                f"[run {run_index}] Failed: "
                f"{type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            return 1

        elapsed_seconds = round(
            time.monotonic() - started,
            2,
        )
        report["trial_run"] = {
            "run": run_index,
            "elapsed_seconds": elapsed_seconds,
        }

        report_path = (
            output_directory
            / f"run_{run_index:02d}_report.json"
        )
        report_path.write_text(
            json.dumps(
                report,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        reports.append(report)

        stable = report.get(
            "stable_analysis",
            {},
        ) or {}

        print(
            f"[run {run_index}] "
            f"score={stable.get('deterministic_alignment_score', 0)}, "
            f"band={stable.get('alignment_band', '')}, "
            f"requirements={stable.get('requirement_count', 0)}, "
            f"credited={stable.get('credited_requirement_count', 0)}, "
            f"elapsed={elapsed_seconds}s"
        )

        if (
            run_index < args.runs
            and args.delay_seconds > 0
        ):
            time.sleep(args.delay_seconds)

    comparison = _build_comparison(
        reports,
        max_score_spread=args.max_score_spread,
    )
    comparison["metadata"] = trial_metadata

    comparison_json = (
        output_directory / "comparison.json"
    )
    comparison_json.write_text(
        json.dumps(
            comparison,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    _write_csv(
        comparison,
        output_directory / "comparison.csv",
    )
    _write_markdown(
        comparison,
        output_directory / "comparison.md",
        resume_path=resume_path,
        jd_path=jd_path,
        model=active_model,
        reasoning_effort=trial_metadata[
            "reasoning_effort"
        ],
    )

    print()
    print("Comparison complete")
    print(f"Scores: {comparison['scores']}")
    print(
        f"Score spread: {comparison['score_spread']} "
        f"(maximum accepted: {args.max_score_spread})"
    )
    print(
        "Bands stable: "
        f"{comparison['bands_stable']}"
    )
    print(
        "Requirement IDs stable: "
        f"{comparison['requirement_ids_stable']}"
    )
    print(
        "Core label differences: "
        f"{len(comparison['core_label_differences'])}"
    )
    print(
        "Result: "
        f"{'PASS' if comparison['passed'] else 'FAIL'}"
    )
    print(f"Reports saved to: {output_directory}")

    if args.strict and not comparison["passed"]:
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

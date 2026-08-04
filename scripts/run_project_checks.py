#!/usr/bin/env python3
# Cross-platform test runner for Job AI Helper.

from __future__ import annotations

import argparse
import py_compile
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

COMPILE_TARGETS = (
    Path("app.py"),
    Path("analysis_stability"),
    Path("tailoring"),
    Path("resume_builder"),
    Path("database"),
    Path("rag"),
    Path("scripts"),
    Path("tests"),
)

QUICK_TEST_MODULES = (
    "tests.test_stable_evidence_scoring",
    "tests.test_phase6d_stable_scoring_integration",
    "tests.test_phase8_requirement_reconciliation",
    "tests.test_phase8_verification",
    "tests.test_phase9b_blueprint_candidate",
    "tests.test_phase9b_role_family_metadata",
    "tests.test_phase9c_shared_scoring_regression",
    "tests.test_phase9c_blueprint_evaluation",
    "tests.test_blueprint_evaluation_manager",
    "tests.test_phase9d_global_blueprint",
    "tests.test_global_blueprint_manager",
    "tests.test_phase9d_streamlit_acceptance",
)

SAFE_SMOKE_MODULES = (
    "scripts.check_phase8_new_evidence_reconciliation",
    "scripts.check_jd_section_heading_filter",
    "scripts.check_phase8_current_baseline_rebuild",
    "scripts.check_phase9b_blueprint_candidate",
    "scripts.check_phase9b_resolved_baseline_provenance",
    "scripts.check_phase9b_role_family_metadata",
    "scripts.check_phase9c_blueprint_evaluation",
    "scripts.check_phase9d_global_blueprint",
)


def print_heading(title: str) -> None:
    border = "=" * 72
    print()
    print(border)
    print(title)
    print(border)


def iter_python_files() -> list[Path]:
    files: set[Path] = set()

    for target in COMPILE_TARGETS:
        absolute = REPO_ROOT / target

        if absolute.is_file() and absolute.suffix == ".py":
            files.add(absolute)
            continue

        if not absolute.is_dir():
            continue

        for path in absolute.rglob("*.py"):
            relative_parts = path.relative_to(REPO_ROOT).parts
            if any(
                part in {".venv", "venv", "__pycache__"}
                for part in relative_parts
            ):
                continue
            if ".bak." in path.name:
                continue
            files.add(path)

    return sorted(files)


def compile_project() -> None:
    print_heading("1. Compile Python source files")
    files = iter_python_files()
    if not files:
        raise RuntimeError("No Python files were found to compile.")

    failures: list[tuple[Path, str]] = []

    for index, path in enumerate(files, start=1):
        relative = path.relative_to(REPO_ROOT)
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as exc:
            failures.append((relative, str(exc)))
            print(f"[FAIL] {relative}")
        else:
            print(f"[{index:03d}/{len(files):03d}] {relative}")

    if failures:
        print()
        for relative, message in failures:
            print(f"Compilation failure: {relative}")
            print(message)
        raise RuntimeError(
            f"{len(failures)} Python file(s) failed compilation."
        )

    print(f"Compiled {len(files)} Python files successfully.")


def module_file(module_name: str) -> Path:
    return REPO_ROOT / (module_name.replace(".", "/") + ".py")


def run_command(command: list[str], label: str) -> None:
    print()
    print(f"> {label}")
    print("  " + " ".join(command))

    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"{label} failed with exit code {completed.returncode}."
        )


def run_smoke_checks() -> None:
    print_heading("2. Zero-cost smoke checks")
    ran = 0

    for module_name in SAFE_SMOKE_MODULES:
        path = module_file(module_name)
        if not path.exists():
            print(f"[SKIP] {module_name} (file not present)")
            continue

        run_command(
            [sys.executable, "-m", module_name],
            f"Smoke check: {module_name}",
        )
        ran += 1

    if ran == 0:
        print("No configured smoke-check modules were present.")
    else:
        print(f"Completed {ran} smoke check(s).")


def run_quick_tests() -> None:
    print_heading("3. Focused unit tests")
    modules = [
        module_name
        for module_name in QUICK_TEST_MODULES
        if module_file(module_name).exists()
    ]

    if not modules:
        raise RuntimeError("No configured quick-test modules were found.")

    run_command(
        [
            sys.executable,
            "-m",
            "unittest",
            *modules,
            "-v",
        ],
        "Focused unittest suite",
    )


def run_full_tests() -> None:
    print_heading("3. Complete unit and regression suite")
    run_command(
        [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-v",
        ],
        "Full unittest discovery",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compile Job AI Helper and run deterministic smoke/unit tests."
        )
    )
    parser.add_argument(
        "--mode",
        choices=("quick", "full"),
        default="full",
        help="quick runs focused modules; full runs unittest discovery.",
    )
    parser.add_argument(
        "--skip-compile",
        action="store_true",
        help="Skip Python compilation.",
    )
    parser.add_argument(
        "--skip-smoke",
        action="store_true",
        help="Skip configured zero-cost smoke checks.",
    )
    parser.add_argument(
        "--ci",
        action="store_true",
        help="Mark the invocation as CI in the summary.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    environment = "CI" if args.ci else "local"

    print_heading(
        f"Job AI Helper automated checks ({args.mode}, {environment})"
    )
    print(f"Python: {sys.executable}")
    print(f"Repository: {REPO_ROOT}")

    try:
        if not args.skip_compile:
            compile_project()

        if not args.skip_smoke:
            run_smoke_checks()

        if args.mode == "quick":
            run_quick_tests()
        else:
            run_full_tests()
    except (RuntimeError, OSError) as exc:
        print_heading("CHECKS FAILED")
        print(exc)
        return 1

    print_heading("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

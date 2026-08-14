"""Evaluate existing resume extraction through API and Codex backends.

The same raw resume text is passed to the existing
``analyzer.extract_resume_profile`` function for both backends. The only
difference is the active analysis backend in llm.py.

Examples:

    python scripts/evaluate_codex_resume_extraction.py --skip-api --repeat 1
    python scripts/evaluate_codex_resume_extraction.py --repeat 1
    python scripts/evaluate_codex_resume_extraction.py --repeat 1 --report-out experimental/reports/api_vs_codex_resume_r1.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from analyzer import extract_resume_profile
from experimental.ai_backend_core import (
    get_active_ai_backend,
    set_runtime_ai_backend,
)
from experimental.codex_llm_backend import (
    get_last_codex_call_metadata,
)
from experimental.resume_profile_contract import (
    validate_resume_profile_contract,
)
from llm import get_call_ledger, reset_call_ledger


DEFAULT_FIXTURE = Path(
    "experimental/fixtures/resume_extraction_poc_inputs.json"
)


def _profile_fingerprint(profile: dict[str, Any]) -> str:
    payload = json.dumps(
        profile,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalise(value: object) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _flatten_skills(profile: dict[str, Any]) -> list[str]:
    skills = profile.get("skills")
    if not isinstance(skills, dict):
        return []

    output: list[str] = []
    for key in (
        "languages",
        "frameworks",
        "tools",
        "concepts",
        "platforms",
    ):
        values = skills.get(key)
        if isinstance(values, list):
            output.extend(
                str(item)
                for item in values
                if isinstance(item, str)
            )
    return output


def evaluate_expected_anchors(
    profile: dict[str, Any],
    expected: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate deterministic exact/normalised anchors from the fixture."""
    actual_project_titles = [
        str(item.get("title", ""))
        for item in profile.get("projects", [])
        if isinstance(item, dict)
    ]
    actual_companies = [
        str(item.get("company", ""))
        for item in profile.get("experience", [])
        if isinstance(item, dict)
    ]
    actual_skills = _flatten_skills(profile)

    def contains_normalised(
        values: list[str],
        wanted: str,
    ) -> bool:
        wanted_key = _normalise(wanted)
        return any(
            _normalise(value) == wanted_key
            for value in values
        )

    project_checks = {
        title: contains_normalised(
            actual_project_titles,
            title,
        )
        for title in expected.get("project_titles", [])
    }
    company_checks = {
        company: contains_normalised(
            actual_companies,
            company,
        )
        for company in expected.get(
            "experience_companies",
            [],
        )
    }
    skill_checks = {
        skill: contains_normalised(
            actual_skills,
            skill,
        )
        for skill in expected.get("skills", [])
    }

    name_expected = str(expected.get("name", ""))
    email_expected = str(expected.get("email", ""))

    checks: dict[str, Any] = {
        "name": (
            _normalise(profile.get("name"))
            == _normalise(name_expected)
            if name_expected
            else None
        ),
        "email": (
            _normalise(
                (profile.get("contact") or {}).get("email")
                if isinstance(profile.get("contact"), dict)
                else ""
            )
            == _normalise(email_expected)
            if email_expected
            else None
        ),
        "project_titles": project_checks,
        "experience_companies": company_checks,
        "skills": skill_checks,
    }

    flat_bools: list[bool] = []
    for key in ("name", "email"):
        if isinstance(checks[key], bool):
            flat_bools.append(checks[key])
    for group in (
        project_checks,
        company_checks,
        skill_checks,
    ):
        flat_bools.extend(group.values())

    checks["passed"] = all(flat_bools) if flat_bools else None
    checks["passed_count"] = sum(1 for value in flat_bools if value)
    checks["total_count"] = len(flat_bools)
    return checks


def _run_backend_once(
    resume_text: str,
    *,
    backend: str,
    expected_anchors: dict[str, Any],
) -> dict[str, Any]:
    previous_backend = get_active_ai_backend("analysis")
    reset_call_ledger()
    started_at = time.perf_counter()

    try:
        set_runtime_ai_backend(
            backend,
            route="analysis",
        )
        profile = validate_resume_profile_contract(
            extract_resume_profile(resume_text)
        )
        elapsed = round(
            time.perf_counter() - started_at,
            3,
        )

        result: dict[str, Any] = {
            "ok": True,
            "profile": profile,
            "schema_valid": True,
            "anchor_checks": evaluate_expected_anchors(
                profile,
                expected_anchors,
            ),
            "latency_seconds": elapsed,
            "error": None,
        }

        if backend == "api":
            result["metadata"] = {
                "backend": "api",
                "api_calls": get_call_ledger(),
            }
        else:
            result["metadata"] = (
                get_last_codex_call_metadata()
                or {"backend": "codex"}
            )

        return result

    except Exception as exc:
        return {
            "ok": False,
            "profile": None,
            "schema_valid": False,
            "anchor_checks": None,
            "latency_seconds": round(
                time.perf_counter() - started_at,
                3,
            ),
            "metadata": None,
            "error": f"{type(exc).__name__}: {exc}",
        }

    finally:
        set_runtime_ai_backend(
            previous_backend,
            route="analysis",
        )


def _repeat_backend(
    resume_text: str,
    *,
    backend: str,
    repeat: int,
    expected_anchors: dict[str, Any],
) -> dict[str, Any]:
    runs = [
        _run_backend_once(
            resume_text,
            backend=backend,
            expected_anchors=expected_anchors,
        )
        for _ in range(repeat)
    ]

    successful = [
        run
        for run in runs
        if run.get("ok")
        and isinstance(run.get("profile"), dict)
    ]
    fingerprints = [
        _profile_fingerprint(run["profile"])
        for run in successful
    ]

    exact_deterministic = (
        None
        if len(fingerprints) < 2
        else len(set(fingerprints)) == 1
    )

    return {
        "status": "completed",
        "runs": runs,
        "successful_run_count": len(successful),
        "profile_fingerprints": fingerprints,
        "exact_output_deterministic": exact_deterministic,
        "consistency_note": (
            "Exact determinism is reported only when at least two successful "
            "runs exist. A single run is insufficient to establish repeatability."
        ),
    }


def _not_run_backend_result() -> dict[str, Any]:
    return {
        "status": "not_run",
        "runs": [],
        "successful_run_count": 0,
        "profile_fingerprints": [],
        "exact_output_deterministic": None,
        "consistency_note": (
            "Backend was intentionally skipped."
        ),
    }


def compare_backend_results(
    api_result: dict[str, Any],
    codex_result: dict[str, Any],
) -> dict[str, Any]:
    api_runs = api_result.get("runs") or []
    codex_runs = codex_result.get("runs") or []

    api_first = (
        api_runs[0]
        if api_runs and api_runs[0].get("ok")
        else None
    )
    codex_first = (
        codex_runs[0]
        if codex_runs and codex_runs[0].get("ok")
        else None
    )

    api_profile = (
        api_first.get("profile")
        if isinstance(api_first, dict)
        else None
    )
    codex_profile = (
        codex_first.get("profile")
        if isinstance(codex_first, dict)
        else None
    )

    return {
        "schema_validity": {
            "api": (
                bool(api_first.get("schema_valid"))
                if api_first is not None
                else None
            ),
            "codex": (
                bool(codex_first.get("schema_valid"))
                if codex_first is not None
                else None
            ),
        },
        "anchor_checks": {
            "api": (
                api_first.get("anchor_checks")
                if api_first is not None
                else None
            ),
            "codex": (
                codex_first.get("anchor_checks")
                if codex_first is not None
                else None
            ),
        },
        "exact_profile_equal": (
            api_profile == codex_profile
            if isinstance(api_profile, dict)
            and isinstance(codex_profile, dict)
            else None
        ),
        "profile_counts": {
            "api": _profile_counts(api_profile),
            "codex": _profile_counts(codex_profile),
        },
    }


def _profile_counts(
    profile: dict[str, Any] | None,
) -> dict[str, int] | None:
    if not isinstance(profile, dict):
        return None

    return {
        "education": len(profile.get("education") or []),
        "projects": len(profile.get("projects") or []),
        "experience": len(profile.get("experience") or []),
        "skills": len(_flatten_skills(profile)),
    }


def _load_fixture(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    resumes = payload.get("resumes")
    if not isinstance(resumes, list) or not resumes:
        raise ValueError(
            "Fixture must contain a non-empty 'resumes' list."
        )
    return resumes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fixture",
        type=Path,
        default=DEFAULT_FIXTURE,
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
    )
    parser.add_argument(
        "--skip-api",
        action="store_true",
    )
    parser.add_argument(
        "--skip-codex",
        action="store_true",
    )
    parser.add_argument(
        "--codex-model",
        default="",
    )
    parser.add_argument(
        "--report-out",
        type=Path,
        default=None,
    )
    args = parser.parse_args()

    if args.repeat < 1:
        parser.error("--repeat must be at least 1.")
    if args.skip_api and args.skip_codex:
        parser.error(
            "Cannot skip both API and Codex."
        )

    original_codex_model = os.environ.get(
        "CODEX_ANALYSIS_MODEL"
    )
    if args.codex_model.strip():
        os.environ["CODEX_ANALYSIS_MODEL"] = (
            args.codex_model.strip()
        )

    try:
        results: list[dict[str, Any]] = []

        for fixture in _load_fixture(args.fixture):
            resume_text = str(
                fixture.get("resume_text") or ""
            )
            expected = fixture.get(
                "expected_anchors"
            ) or {}

            if not resume_text.strip():
                raise ValueError(
                    "Each fixture needs non-empty resume_text."
                )

            api = (
                _not_run_backend_result()
                if args.skip_api
                else _repeat_backend(
                    resume_text,
                    backend="api",
                    repeat=args.repeat,
                    expected_anchors=expected,
                )
            )
            codex = (
                _not_run_backend_result()
                if args.skip_codex
                else _repeat_backend(
                    resume_text,
                    backend="codex",
                    repeat=args.repeat,
                    expected_anchors=expected,
                )
            )

            results.append(
                {
                    "resume_id": fixture.get(
                        "resume_id",
                        "",
                    ),
                    "api": api,
                    "codex": codex,
                    "comparison": compare_backend_results(
                        api,
                        codex,
                    ),
                }
            )

        report = {
            "poc": "codex-resume-extraction",
            "fixture": str(args.fixture),
            "repeat": args.repeat,
            "api_enabled": not args.skip_api,
            "codex_enabled": not args.skip_codex,
            "results": results,
        }

        rendered = json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        )
        print(rendered)

        if args.report_out is not None:
            args.report_out.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            args.report_out.write_text(
                rendered + "\n",
                encoding="utf-8",
            )

        return 0

    finally:
        if args.codex_model.strip():
            if original_codex_model is None:
                os.environ.pop(
                    "CODEX_ANALYSIS_MODEL",
                    None,
                )
            else:
                os.environ[
                    "CODEX_ANALYSIS_MODEL"
                ] = original_codex_model


if __name__ == "__main__":
    raise SystemExit(main())

"""Evaluate one existing analyzer stage through API and/or Codex.

Run as a module from the repository root. Examples:

    python -m scripts.evaluate_codex_analysis_stages --stage keyword --skip-api
    python -m scripts.evaluate_codex_analysis_stages --stage bullets --skip-api
    python -m scripts.evaluate_codex_analysis_stages --stage jargon --skip-api
    python -m scripts.evaluate_codex_analysis_stages --stage structure --skip-api
    python -m scripts.evaluate_codex_analysis_stages --stage degree --skip-api
    python -m scripts.evaluate_codex_analysis_stages --stage summary --skip-api

There is intentionally no "all" stage. One invocation evaluates one semantic
operation so Codex allowance is spent deliberately.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Callable

from analyzer import (
    analyse_bullets,
    analyse_degree_alignment,
    analyse_jargon,
    analyse_keyword_match,
    analyse_structure,
    summarise_overall,
)
from experimental.ai_backend_core import (
    get_active_ai_backend,
    set_runtime_ai_backend,
)
from experimental.analysis_stage_contracts import (
    validate_bullets_result,
    validate_degree_result,
    validate_jargon_result,
    validate_keyword_result,
    validate_structure_result,
    validate_summary_result,
)
from experimental.codex_llm_backend import (
    get_last_codex_call_metadata,
)
from llm import get_call_ledger, reset_call_ledger


DEFAULT_FIXTURE = Path(
    "experimental/fixtures/analysis_stages_poc_inputs.json"
)
STAGES = (
    "keyword",
    "bullets",
    "jargon",
    "structure",
    "degree",
    "summary",
)


def _fingerprint(value: Any) -> str:
    if isinstance(value, str):
        payload = value.strip()
    else:
        payload = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    return hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()


def _normalise(value: object) -> str:
    return " ".join(
        str(value or "").strip().lower().split()
    )


def _source_bullets(
    resume_profile: dict[str, Any],
) -> list[str]:
    output: list[str] = []
    for section in ("projects", "experience"):
        for item in resume_profile.get(section, []) or []:
            if not isinstance(item, dict):
                continue
            for bullet in item.get("bullets", []) or []:
                if isinstance(bullet, str):
                    output.append(bullet)
    return output


def _stage_call(
    stage: str,
    fixture: dict[str, Any],
) -> Any:
    resume_profile = fixture["resume_profile"]
    jd_profile = fixture["jd_profile"]
    resume_text = fixture["resume_text"]
    jd_text = fixture["jd_text"]
    degree_program = fixture["degree_program"]
    page_count = fixture.get("actual_page_count")

    if stage == "keyword":
        return analyse_keyword_match(
            resume_profile,
            jd_profile,
            resume_text,
            jd_text,
        )
    if stage == "bullets":
        return analyse_bullets(
            resume_profile
        )
    if stage == "jargon":
        return analyse_jargon(
            resume_profile,
            degree_program,
            jd_profile,
            raw_jd_text=jd_text,
        )
    if stage == "structure":
        return analyse_structure(
            resume_text,
            actual_page_count=page_count,
            resume_profile=resume_profile,
        )
    if stage == "degree":
        return analyse_degree_alignment(
            jd_profile,
            degree_program,
        )
    if stage == "summary":
        return summarise_overall(
            fixture["summary_report"]
        )

    raise ValueError(
        f"Unsupported stage: {stage!r}."
    )


def _validate_stage(
    stage: str,
    value: Any,
    fixture: dict[str, Any],
) -> Any:
    if stage == "keyword":
        return validate_keyword_result(value)
    if stage == "bullets":
        return validate_bullets_result(
            value,
            expected_bullets=_source_bullets(
                fixture["resume_profile"]
            ),
        )
    if stage == "jargon":
        return validate_jargon_result(value)
    if stage == "structure":
        return validate_structure_result(
            value,
            actual_page_count=fixture.get(
                "actual_page_count"
            ),
        )
    if stage == "degree":
        return validate_degree_result(value)
    if stage == "summary":
        return validate_summary_result(value)

    raise ValueError(
        f"Unsupported stage: {stage!r}."
    )


def _keyword_anchor_checks(
    value: dict[str, Any],
    expected: dict[str, Any],
) -> dict[str, Any]:
    present = [
        _normalise(item.get("keyword"))
        for item in value.get("present", [])
        if isinstance(item, dict)
    ]
    missing = [
        _normalise(item.get("keyword"))
        for item in value.get("missing", [])
        if isinstance(item, dict)
    ]

    def loose_contains(
        haystack: list[str],
        needle: str,
    ) -> bool:
        wanted = _normalise(needle)
        return any(
            wanted in item
            or item in wanted
            for item in haystack
            if item
        )

    present_checks = {
        item: loose_contains(present, item)
        for item in expected.get(
            "present_any",
            [],
        )
    }
    missing_checks = {
        item: loose_contains(missing, item)
        for item in expected.get(
            "missing_any",
            [],
        )
    }

    values = [
        *present_checks.values(),
        *missing_checks.values(),
    ]
    return {
        "present": present_checks,
        "missing": missing_checks,
        "passed": all(values) if values else None,
    }


def _anchor_checks(
    stage: str,
    value: Any,
    fixture: dict[str, Any],
) -> dict[str, Any]:
    expected_all = fixture.get(
        "expected_anchors",
        {},
    )
    expected = expected_all.get(
        stage,
        {},
    )

    if stage == "keyword":
        return _keyword_anchor_checks(
            value,
            expected,
        )

    if stage == "bullets":
        expected_count = len(
            _source_bullets(
                fixture["resume_profile"]
            )
        )
        actual_count = len(
            value.get("bullets", [])
        )
        return {
            "expected_bullet_count": expected_count,
            "actual_bullet_count": actual_count,
            "passed": (
                actual_count == expected_count
            ),
        }

    if stage == "jargon":
        needle = _normalise(
            expected.get(
                "flag_term_contains",
                "",
            )
        )
        terms = [
            _normalise(item.get("term_used"))
            for item in value.get("flags", [])
            if isinstance(item, dict)
        ]
        passed = (
            any(
                needle in term
                or term in needle
                for term in terms
                if term and needle
            )
            if needle
            else None
        )
        return {
            "expected_term": needle or None,
            "returned_terms": terms,
            "passed": passed,
        }

    if stage == "structure":
        return {
            "actual_page_count": fixture.get(
                "actual_page_count"
            ),
            "returned_page_count": value.get(
                "page_count_estimate"
            ),
            "page_count_source": value.get(
                "page_count_source"
            ),
            "passed": (
                value.get("page_count_estimate")
                == fixture.get("actual_page_count")
                and value.get("page_count_source")
                == "rendered_document"
            ),
        }

    if stage == "degree":
        minimum = int(
            expected.get(
                "minimum_score",
                0,
            )
        )
        checks = {
            "jd_title": (
                _normalise(value.get("jd_title"))
                == _normalise(
                    expected.get("jd_title")
                )
            ),
            "title_on_suggested_list": (
                value.get(
                    "title_on_suggested_list"
                )
                is expected.get(
                    "title_on_suggested_list"
                )
            ),
            "minimum_score": (
                int(
                    value.get(
                        "degree_alignment_score",
                        0,
                    )
                )
                >= minimum
            ),
        }
        return {
            **checks,
            "passed": all(checks.values()),
        }

    if stage == "summary":
        checks = {
            item: (
                str(item).lower()
                in str(value).lower()
            )
            for item in expected.get(
                "must_contain",
                [],
            )
        }
        return {
            "contains": checks,
            "passed": (
                all(checks.values())
                if checks
                else None
            ),
        }

    return {"passed": None}


def _run_once(
    *,
    stage: str,
    backend: str,
    fixture: dict[str, Any],
) -> dict[str, Any]:
    previous_backend = get_active_ai_backend(
        "analysis"
    )
    reset_call_ledger()
    started_at = time.perf_counter()

    try:
        set_runtime_ai_backend(
            backend,
            route="analysis",
        )
        raw = _stage_call(
            stage,
            fixture,
        )
        validated = _validate_stage(
            stage,
            raw,
            fixture,
        )
        elapsed = round(
            time.perf_counter() - started_at,
            3,
        )

        if backend == "api":
            metadata: Any = {
                "backend": "api",
                "api_calls": get_call_ledger(),
            }
        else:
            metadata = (
                get_last_codex_call_metadata()
                or {"backend": "codex"}
            )

        return {
            "ok": True,
            "stage": stage,
            "backend": backend,
            "result": validated,
            "contract_valid": True,
            "anchor_checks": _anchor_checks(
                stage,
                validated,
                fixture,
            ),
            "latency_seconds": elapsed,
            "metadata": metadata,
            "error": None,
        }

    except Exception as exc:
        return {
            "ok": False,
            "stage": stage,
            "backend": backend,
            "result": None,
            "contract_valid": False,
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
    *,
    stage: str,
    backend: str,
    fixture: dict[str, Any],
    repeat: int,
) -> dict[str, Any]:
    runs = [
        _run_once(
            stage=stage,
            backend=backend,
            fixture=fixture,
        )
        for _ in range(repeat)
    ]

    successful = [
        run
        for run in runs
        if run.get("ok")
    ]
    fingerprints = [
        _fingerprint(run["result"])
        for run in successful
    ]

    return {
        "status": "completed",
        "runs": runs,
        "successful_run_count": len(successful),
        "result_fingerprints": fingerprints,
        "exact_output_deterministic": (
            None
            if len(fingerprints) < 2
            else len(set(fingerprints)) == 1
        ),
        "consistency_note": (
            "Exact determinism is reported only with at least two successful "
            "runs. Different fingerprints do not by themselves prove a "
            "meaningful semantic disagreement."
        ),
    }


def _not_run() -> dict[str, Any]:
    return {
        "status": "not_run",
        "runs": [],
        "successful_run_count": 0,
        "result_fingerprints": [],
        "exact_output_deterministic": None,
        "consistency_note": "Backend was intentionally skipped.",
    }


def _first_success(
    backend_result: dict[str, Any],
) -> dict[str, Any] | None:
    for run in backend_result.get(
        "runs",
        [],
    ):
        if run.get("ok"):
            return run
    return None


def _comparison(
    api: dict[str, Any],
    codex: dict[str, Any],
) -> dict[str, Any]:
    api_first = _first_success(api)
    codex_first = _first_success(codex)

    return {
        "contract_validity": {
            "api": (
                bool(
                    api_first.get(
                        "contract_valid"
                    )
                )
                if api_first is not None
                else None
            ),
            "codex": (
                bool(
                    codex_first.get(
                        "contract_valid"
                    )
                )
                if codex_first is not None
                else None
            ),
        },
        "anchor_checks": {
            "api": (
                api_first.get(
                    "anchor_checks"
                )
                if api_first is not None
                else None
            ),
            "codex": (
                codex_first.get(
                    "anchor_checks"
                )
                if codex_first is not None
                else None
            ),
        },
        "exact_result_equal": (
            api_first.get("result")
            == codex_first.get("result")
            if api_first is not None
            and codex_first is not None
            else None
        ),
    }


def _load_fixture(
    path: Path,
) -> dict[str, Any]:
    payload = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )
    required = {
        "resume_text",
        "jd_text",
        "resume_profile",
        "jd_profile",
        "degree_program",
        "summary_report",
    }
    missing = sorted(
        required - set(payload)
    )
    if missing:
        raise ValueError(
            "Fixture missing fields: "
            + ", ".join(missing)
        )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--stage",
        required=True,
        choices=STAGES,
    )
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
        parser.error(
            "--repeat must be at least 1."
        )
    if (
        args.skip_api
        and args.skip_codex
    ):
        parser.error(
            "Cannot skip both API and Codex."
        )

    original_codex_model = os.environ.get(
        "CODEX_ANALYSIS_MODEL"
    )
    if args.codex_model.strip():
        os.environ[
            "CODEX_ANALYSIS_MODEL"
        ] = args.codex_model.strip()

    try:
        fixture = _load_fixture(
            args.fixture
        )

        api = (
            _not_run()
            if args.skip_api
            else _repeat_backend(
                stage=args.stage,
                backend="api",
                fixture=fixture,
                repeat=args.repeat,
            )
        )
        codex = (
            _not_run()
            if args.skip_codex
            else _repeat_backend(
                stage=args.stage,
                backend="codex",
                fixture=fixture,
                repeat=args.repeat,
            )
        )

        report = {
            "poc": "codex-analysis-stages",
            "fixture": str(
                args.fixture
            ),
            "stage": args.stage,
            "repeat": args.repeat,
            "api_enabled": not args.skip_api,
            "codex_enabled": not args.skip_codex,
            "api": api,
            "codex": codex,
            "comparison": _comparison(
                api,
                codex,
            ),
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

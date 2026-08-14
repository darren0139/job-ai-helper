"""Compare production API JD extraction with the isolated local-Codex POC.

This script never changes saved JDs or application state.  It prints JSON to
stdout by default; ``--report-out`` is an explicit, caller-selected artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from experimental.codex_jd_extraction import (
    extract_job_description_with_codex_result,
    validate_jd_profile_contract,
)


COMPARE_FIELDS = (
    "job_title",
    "company",
    "responsibilities",
    "required_skills",
    "preferred_skills",
    "experience_level",
    "tools_technologies",
)
WORD_RE = re.compile(r"[a-z0-9+#.]+")
EXACT_CONSISTENCY_NOTE = (
    "Fingerprint equality compares exact normalized JSON only; different "
    "fingerprints do not by themselves imply semantic disagreement."
)


def _fingerprint(profile: dict[str, Any]) -> str:
    payload = json.dumps(profile, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _tokens(value: str) -> set[str]:
    return set(WORD_RE.findall(value.lower()))


def _field_values(profile: dict[str, Any], field: str) -> list[str]:
    value = profile.get(field, "")
    return value if isinstance(value, list) else [value]


def _potentially_unsupported(profile: dict[str, Any], raw_jd: str) -> dict[str, list[str]]:
    source_tokens = _tokens(raw_jd)
    result: dict[str, list[str]] = {}
    for field in COMPARE_FIELDS:
        unsupported = []
        for value in _field_values(profile, field):
            value_tokens = _tokens(value)
            if value_tokens and not value_tokens.issubset(source_tokens):
                unsupported.append(value)
        if unsupported:
            result[field] = unsupported
    return result


def _run_extraction(
    backend: str,
    jd_text: str,
    *,
    codex_model: str | None,
) -> dict[str, Any]:
    started_at = time.perf_counter()
    try:
        if backend == "api":
            # Keep --skip-api usable in a minimal local Codex POC environment.
            from analyzer import extract_jd_profile
            from llm import get_call_ledger, reset_call_ledger

            reset_call_ledger()
            profile = extract_jd_profile(jd_text)
            metadata: dict[str, Any] = {"api_calls": get_call_ledger()}
        else:
            result = extract_job_description_with_codex_result(
                jd_text,
                model=codex_model,
            )
            profile = result.profile
            metadata = result.metadata.to_dict()

        validated = validate_jd_profile_contract(profile)
        return {
            "ok": True,
            "profile": validated,
            "schema_valid": True,
            "latency_seconds": round(time.perf_counter() - started_at, 3),
            "metadata": metadata,
            "error": None,
        }
    except Exception as exc:  # Harness must report all invocation failures.
        return {
            "ok": False,
            "profile": None,
            "schema_valid": False,
            "latency_seconds": round(time.perf_counter() - started_at, 3),
            "metadata": {},
            "error": f"{type(exc).__name__}: {exc}",
        }


def _repeat_backend(
    backend: str,
    jd_text: str,
    repeats: int,
    *,
    codex_model: str | None,
) -> dict[str, Any]:
    runs = [
        _run_extraction(
            backend,
            jd_text,
            codex_model=codex_model,
        )
        for _ in range(repeats)
    ]
    fingerprints = [
        _fingerprint(run["profile"])
        for run in runs
        if run["ok"] and isinstance(run["profile"], dict)
    ]
    exact_deterministic = (
        len(fingerprints) == repeats and len(set(fingerprints)) == 1
    )
    return {
        "status": "completed",
        "runs": runs,
        # Preserve the original field for compatibility, but make its exact
        # string/JSON meaning explicit in the additional fields below.
        "deterministic_across_successful_runs": exact_deterministic,
        "exact_output_deterministic": exact_deterministic,
        "consistency_note": EXACT_CONSISTENCY_NOTE,
        "successful_run_count": len(fingerprints),
        "profile_fingerprints": fingerprints,
    }


def _not_run_backend_result() -> dict[str, Any]:
    return {
        "status": "not_run",
        "runs": [],
        "deterministic_across_successful_runs": None,
        "exact_output_deterministic": None,
        "consistency_note": EXACT_CONSISTENCY_NOTE,
        "successful_run_count": 0,
        "profile_fingerprints": [],
    }


def _schema_validity(run: dict[str, Any]) -> bool | None:
    if not run or run.get("status") == "not_run":
        return None
    return bool(run.get("schema_valid"))


def compare_profiles(
    raw_jd: str,
    api_run: dict[str, Any],
    codex_run: dict[str, Any],
) -> dict[str, Any]:
    """Summarise requested field-level deltas without claiming semantic truth."""
    api_profile = api_run.get("profile") if api_run.get("ok") else None
    codex_profile = codex_run.get("profile") if codex_run.get("ok") else None
    comparison: dict[str, Any] = {
        "schema_validity": {
            "api": _schema_validity(api_run),
            "codex": _schema_validity(codex_run),
        },
        "api_missing_fields": None,
        "codex_missing_fields": None,
        "api_potentially_unsupported_fields": None,
        "codex_potentially_unsupported_fields": None,
        "fields": {},
    }
    if isinstance(api_profile, dict):
        comparison["api_missing_fields"] = [
            field for field, value in api_profile.items() if value in ("", [])
        ]
        comparison["api_potentially_unsupported_fields"] = _potentially_unsupported(
            api_profile, raw_jd
        )
    if isinstance(codex_profile, dict):
        comparison["codex_missing_fields"] = [
            field for field, value in codex_profile.items() if value in ("", [])
        ]
        comparison["codex_potentially_unsupported_fields"] = _potentially_unsupported(
            codex_profile, raw_jd
        )
    if not isinstance(api_profile, dict) or not isinstance(codex_profile, dict):
        return comparison
    for field in COMPARE_FIELDS:
        api_values = _field_values(api_profile, field)
        codex_values = _field_values(codex_profile, field)
        comparison["fields"][field] = {
            "api": api_values,
            "codex": codex_values,
            "same": api_values == codex_values,
            "only_api": [value for value in api_values if value not in codex_values],
            "only_codex": [value for value in codex_values if value not in api_values],
        }
    return comparison


def _load_fixture_jds(path: Path) -> list[dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    inputs = None
    if isinstance(payload, dict):
        inputs = payload.get("inputs") or payload.get("saved_jds")
    if not isinstance(inputs, list):
        raise ValueError("Fixture must contain an inputs or saved_jds list.")
    entries = []
    for index, jd in enumerate(inputs, start=1):
        raw_text = jd.get("raw_text") if isinstance(jd, dict) else None
        if isinstance(raw_text, str) and raw_text.strip():
            entries.append({"id": str(jd.get("id", index)), "raw_text": raw_text})
    if not entries:
        raise ValueError("Fixture contains no non-empty JD raw_text values.")
    return entries


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path("experimental/fixtures/jd_extraction_poc_inputs.json"),
    )
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument(
        "--codex-model",
        help="Optional model passed to the Codex SDK; omit for its configured default.",
    )
    parser.add_argument("--skip-api", action="store_true")
    parser.add_argument("--report-out", type=Path)
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error("--repeat must be at least 1")

    report: dict[str, Any] = {
        "poc": "codex-jd-extraction",
        "fixture": str(args.fixture),
        "repeat": args.repeat,
        "api_enabled": not args.skip_api,
        "results": [],
    }
    for jd in _load_fixture_jds(args.fixture):
        api_result = (
            _repeat_backend(
                "api",
                jd["raw_text"],
                args.repeat,
                codex_model=args.codex_model,
            )
            if not args.skip_api
            else _not_run_backend_result()
        )
        codex_result = _repeat_backend(
            "codex",
            jd["raw_text"],
            args.repeat,
            codex_model=args.codex_model,
        )
        api_first = api_result["runs"][0] if api_result["runs"] else {}
        codex_first = codex_result["runs"][0]
        report["results"].append(
            {
                "jd_id": jd["id"],
                "api": api_result,
                "codex": codex_result,
                "comparison": compare_profiles(jd["raw_text"], api_first, codex_first),
            }
        )

    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    if args.report_out:
        args.report_out.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    sys.exit(main())

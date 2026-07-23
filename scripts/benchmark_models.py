r"""
Compare tailoring stability, latency, token usage, and estimated cost by model.

This script uses one fixed Phase 6A.1C/6B.1 debug bundle. It makes real API
calls and does not create application sessions or DOCX/PDF files.

Example:

    python -m scripts.benchmark_models ^
      --debug-bundle "test_inputs\phase6b_debug_bundle.json" ^
      --models openai/gpt-5.6-terra openai/gpt-5.6-luna openai/gpt-5.4-mini ^
      --runs 2 ^
      --reasoning-effort low

The first model is the quality baseline. Other models are compared against its
selected project IDs, requirement labels, and final Skills lines.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _resolve_path(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def _load_bundle(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    report = payload.get("analysis_report") or payload
    inputs = payload.get("project_tailoring_inputs", {}) or {}
    evidence_items = inputs.get("evidence_items", []) or []

    if not isinstance(report, dict) or not report.get("stable_analysis"):
        raise ValueError(
            "Debug bundle must contain analysis_report.stable_analysis."
        )
    if not isinstance(evidence_items, list) or not evidence_items:
        raise ValueError(
            "Debug bundle must contain project_tailoring_inputs.evidence_items."
        )
    return report, evidence_items


def _usage_number(usage: Any, *keys: str) -> int:
    if not isinstance(usage, dict):
        return 0

    for key in keys:
        value = usage.get(key)
        if isinstance(value, (int, float)):
            return int(value)

    for nested_key in ("prompt_tokens_details", "input_tokens_details"):
        nested = usage.get(nested_key)
        if isinstance(nested, dict):
            for key in keys:
                value = nested.get(key)
                if isinstance(value, (int, float)):
                    return int(value)

    return 0


def normalise_usage(metadata: dict[str, Any]) -> dict[str, int]:
    usage = metadata.get("usage") or {}

    input_tokens = _usage_number(
        usage,
        "prompt_tokens",
        "input_tokens",
    )
    output_tokens = _usage_number(
        usage,
        "completion_tokens",
        "output_tokens",
    )
    cached_tokens = _usage_number(
        usage,
        "cached_tokens",
        "cached_input_tokens",
        "cache_read_input_tokens",
    )

    if cached_tokens > input_tokens:
        cached_tokens = 0

    return {
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_tokens,
        "uncached_input_tokens": max(0, input_tokens - cached_tokens),
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
    }


def estimate_cost(
    usage: dict[str, int],
    pricing: dict[str, Any] | None,
) -> float | None:
    if not pricing:
        return None

    input_rate = float(pricing.get("input", 0.0) or 0.0)
    cached_rate = float(
        pricing.get("cached_input", input_rate) or input_rate
    )
    output_rate = float(pricing.get("output", 0.0) or 0.0)

    return round(
        (
            usage["uncached_input_tokens"] * input_rate
            + usage["cached_input_tokens"] * cached_rate
            + usage["output_tokens"] * output_rate
        )
        / 1_000_000,
        6,
    )


def _selected_signature(project_result: dict[str, Any]) -> dict[str, Any]:
    ranking = project_result.get("candidate_project_ranking", []) or []
    selected = [
        row
        for row in ranking
        if row.get("recommendation") == "include"
    ]

    return {
        "project_ids": [_clean(row.get("project_id")) for row in selected],
        "project_titles": [
            _clean(row.get("display_title") or row.get("title"))
            for row in selected
        ],
        "requirement_labels": {
            _clean(row.get("project_id")): {
                _clean(match.get("requirement_id")): _clean(
                    match.get("match_label")
                )
                for match in row.get("requirement_matches", []) or []
                if _clean(match.get("requirement_id"))
            }
            for row in selected
        },
    }


def _skills_signature(skills_result: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "category": _clean(line.get("category")),
            "items": [_clean(item) for item in line.get("items", []) or []],
        }
        for line in skills_result.get("skill_lines", []) or []
        if isinstance(line, dict)
    ]


def _run_one(
    *,
    report: dict[str, Any],
    evidence_items: list[dict[str, Any]],
    model: str,
    reasoning_effort: str | None,
    max_projects: int,
    max_bullets: int,
    max_skill_items: int,
    pricing: dict[str, Any] | None,
) -> dict[str, Any]:
    from llm import (
        get_last_call_metadata,
        set_runtime_model,
    )
    from tailoring.project_section_tailor import tailor_projects_section
    from tailoring.skills_section_tailor import tailor_skills_section

    set_runtime_model(model, route="analysis")
    if reasoning_effort:
        os.environ["ANALYSIS_REASONING_EFFORT"] = reasoning_effort

    started = time.perf_counter()

    project_result = tailor_projects_section(
        resume_profile=report.get("resume_profile", {}),
        jd_profile=report.get("jd_profile", {}),
        evidence_items=evidence_items,
        max_projects=max_projects,
        max_bullets_per_project=max_bullets,
        keyword_match=report.get("keyword_match", {}),
        raw_jd_text=report.get("raw_jd_text", ""),
        stable_analysis=report.get("stable_analysis", {}),
    )
    project_metadata = get_last_call_metadata()
    project_usage = normalise_usage(project_metadata)

    skills_result = tailor_skills_section(
        resume_profile=report.get("resume_profile", {}),
        jd_profile=report.get("jd_profile", {}),
        evidence_items=evidence_items,
        stable_analysis=report.get("stable_analysis", {}),
        selected_projects_result=project_result,
        max_items=max_skill_items,
    )
    skills_metadata = get_last_call_metadata()
    skills_usage = normalise_usage(skills_metadata)

    elapsed = round(time.perf_counter() - started, 3)

    combined_usage = {
        key: project_usage[key] + skills_usage[key]
        for key in project_usage
    }

    return {
        "model": model,
        "elapsed_seconds": elapsed,
        "project_call": {
            "metadata": project_metadata,
            "usage": project_usage,
            "estimated_cost_usd": estimate_cost(project_usage, pricing),
        },
        "skills_call": {
            "metadata": skills_metadata,
            "usage": skills_usage,
            "estimated_cost_usd": estimate_cost(skills_usage, pricing),
        },
        "combined_usage": combined_usage,
        "estimated_cost_usd": estimate_cost(combined_usage, pricing),
        "selected": _selected_signature(project_result),
        "skills": _skills_signature(skills_result),
        "bullet_text": {
            _clean(project.get("title")): project.get("draft_bullets", []) or []
            for project in project_result.get("recommended_projects", []) or []
        },
        "ranking_version": _clean(
            (project_result.get("selection_debug", {}) or {}).get(
                "ranking_version"
            )
        ),
        "evidence_mapping_version": _clean(
            (project_result.get("selection_debug", {}) or {}).get(
                "evidence_mapping_version"
            )
        ),
    }


def _aggregate(
    model: str,
    runs: list[dict[str, Any]],
    baseline: dict[str, Any],
) -> dict[str, Any]:
    selected_orders = [run["selected"]["project_ids"] for run in runs]
    skills = [run["skills"] for run in runs]
    labels = [run["selected"]["requirement_labels"] for run in runs]
    bullets = [run["bullet_text"] for run in runs]

    costs = [
        run["estimated_cost_usd"]
        for run in runs
        if isinstance(run["estimated_cost_usd"], (int, float))
    ]
    latencies = [run["elapsed_seconds"] for run in runs]
    inputs = [run["combined_usage"]["input_tokens"] for run in runs]
    outputs = [run["combined_usage"]["output_tokens"] for run in runs]

    baseline_order = baseline["selected"]["project_ids"]
    baseline_skills = baseline["skills"]
    baseline_labels = baseline["selected"]["requirement_labels"]

    return {
        "model": model,
        "run_count": len(runs),
        "selected_order_stable": all(
            value == selected_orders[0] for value in selected_orders[1:]
        ),
        "skills_stable": all(value == skills[0] for value in skills[1:]),
        "requirement_labels_stable": all(
            value == labels[0] for value in labels[1:]
        ),
        "bullet_wording_stable": all(
            value == bullets[0] for value in bullets[1:]
        ),
        "matches_baseline_project_order": selected_orders[0] == baseline_order,
        "matches_baseline_skills": skills[0] == baseline_skills,
        "matches_baseline_requirement_labels": labels[0] == baseline_labels,
        "median_elapsed_seconds": round(statistics.median(latencies), 3),
        "median_input_tokens": int(statistics.median(inputs)),
        "median_output_tokens": int(statistics.median(outputs)),
        "median_estimated_cost_usd": (
            round(statistics.median(costs), 6) if costs else None
        ),
        "selected_project_titles": runs[0]["selected"]["project_titles"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark model cost and stability for Phase 6B.1 tailoring."
    )
    parser.add_argument("--debug-bundle", required=True)
    parser.add_argument("--models", nargs="+", required=True)
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--max-projects", type=int, default=3)
    parser.add_argument("--max-bullets", type=int, default=3)
    parser.add_argument("--max-skill-items", type=int, default=20)
    parser.add_argument(
        "--reasoning-effort",
        choices=("none", "low", "medium", "high"),
        default="low",
    )
    parser.add_argument(
        "--price-catalog",
        default="config/model_benchmark_catalog.json",
    )
    parser.add_argument("--delay-seconds", type=float, default=1.0)
    parser.add_argument("--output-dir")
    args = parser.parse_args()

    if args.runs < 1:
        parser.error("--runs must be at least 1")

    bundle_path = _resolve_path(args.debug_bundle)
    catalog_path = _resolve_path(args.price_catalog)
    report, evidence_items = _load_bundle(bundle_path)

    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    prices = catalog.get("models", {}) or {}

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = (
        _resolve_path(args.output_dir)
        if args.output_dir
        else PROJECT_ROOT / "benchmark_results" / f"models_{timestamp}"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    all_results: dict[str, list[dict[str, Any]]] = {}
    baseline_run: dict[str, Any] | None = None

    for model_index, model in enumerate(args.models):
        model_runs: list[dict[str, Any]] = []
        print(f"\nModel: {model}")

        for run_index in range(1, args.runs + 1):
            print(f"  Run {run_index}/{args.runs}...")
            result = _run_one(
                report=report,
                evidence_items=evidence_items,
                model=model,
                reasoning_effort=args.reasoning_effort,
                max_projects=args.max_projects,
                max_bullets=args.max_bullets,
                max_skill_items=args.max_skill_items,
                pricing=prices.get(model),
            )
            model_runs.append(result)

            if baseline_run is None:
                baseline_run = result

            print(
                "    selected="
                f"{result['selected']['project_titles']} "
                f"elapsed={result['elapsed_seconds']}s "
                f"tokens={result['combined_usage']['total_tokens']} "
                f"cost=${result['estimated_cost_usd']}"
            )

            if args.delay_seconds > 0:
                time.sleep(args.delay_seconds)

        all_results[model] = model_runs
        (output_dir / f"{model_index + 1:02d}_{model.replace('/', '_')}.json").write_text(
            json.dumps(model_runs, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    assert baseline_run is not None

    summary = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "debug_bundle": str(bundle_path),
        "baseline_model": args.models[0],
        "reasoning_effort": args.reasoning_effort,
        "price_catalog_updated_at": catalog.get("updated_at"),
        "models": [
            _aggregate(model, runs, baseline_run)
            for model, runs in all_results.items()
        ],
    }

    (output_dir / "comparison.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    with (output_dir / "comparison.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        fieldnames = [
            "model",
            "run_count",
            "selected_order_stable",
            "skills_stable",
            "requirement_labels_stable",
            "bullet_wording_stable",
            "matches_baseline_project_order",
            "matches_baseline_skills",
            "matches_baseline_requirement_labels",
            "median_elapsed_seconds",
            "median_input_tokens",
            "median_output_tokens",
            "median_estimated_cost_usd",
            "selected_project_titles",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in summary["models"]:
            writer.writerow(
                {
                    **row,
                    "selected_project_titles": " | ".join(
                        row["selected_project_titles"]
                    ),
                }
            )

    print(f"\nResults saved to: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

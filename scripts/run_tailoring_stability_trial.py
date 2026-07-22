"""
Run repeated Phase 6B.1 project/skill tailoring from one fixed debug bundle.

This developer tool makes real LLM calls but does not create application
sessions, modify the database, or generate DOCX/PDF files. It compares the
Python-selected project IDs, deterministic project scores, requirement links,
and deterministic Skills output. Bullet wording is saved for inspection but is
not a pass/fail criterion because wording remains an AI editing stage.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _clean_text(value: Any) -> str:
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
            "The bundle does not contain analysis_report.stable_analysis. "
            "Use a Phase 6A.1C or later debug bundle."
        )
    if not isinstance(evidence_items, list) or not evidence_items:
        raise ValueError(
            "The bundle does not contain project_tailoring_inputs.evidence_items. "
            "Generate Projects + Skills once and download the full debug bundle."
        )
    return report, evidence_items


def _run_once(
    *,
    report: dict[str, Any],
    evidence_items: list[dict[str, Any]],
    max_projects: int,
    max_bullets: int,
    max_skill_items: int,
) -> dict[str, Any]:
    from tailoring.project_section_tailor import tailor_projects_section
    from tailoring.skills_section_tailor import tailor_skills_section

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
    skills_result = tailor_skills_section(
        resume_profile=report.get("resume_profile", {}),
        jd_profile=report.get("jd_profile", {}),
        evidence_items=evidence_items,
        stable_analysis=report.get("stable_analysis", {}),
        selected_projects_result=project_result,
        max_items=max_skill_items,
    )
    return {
        "project_result": project_result,
        "skills_result": skills_result,
    }


def _run_summary(payload: dict[str, Any], run: int) -> dict[str, Any]:
    project_result = payload["project_result"]
    skills_result = payload["skills_result"]
    selection = project_result.get("selection_debug", {}) or {}
    ranking = project_result.get("candidate_project_ranking", []) or []
    recommended = project_result.get("recommended_projects", []) or []

    selected_by_id = {
        _clean_text(row.get("project_id")): row
        for row in ranking
        if row.get("recommendation") == "include" and _clean_text(row.get("project_id"))
    }
    selected_ids = [
        _clean_text(row.get("project_id"))
        for row in ranking
        if row.get("recommendation") == "include" and _clean_text(row.get("project_id"))
    ]
    selected_titles = [
        _clean_text(row.get("display_title") or row.get("title"))
        for row in ranking
        if row.get("recommendation") == "include"
    ]

    project_scores = {
        _clean_text(row.get("project_id")): int(row.get("final_score", 0) or 0)
        for row in ranking
        if _clean_text(row.get("project_id"))
    }
    requirement_labels = {
        _clean_text(row.get("project_id")): {
            _clean_text(match.get("requirement_id")): _clean_text(match.get("match_label"))
            for match in row.get("requirement_matches", []) or []
            if _clean_text(match.get("requirement_id"))
        }
        for row in ranking
        if _clean_text(row.get("project_id"))
    }
    skill_lines = skills_result.get("skill_lines", []) or []
    skill_signature = [
        {
            "category": _clean_text(line.get("category")),
            "items": [_clean_text(item) for item in line.get("items", []) or []],
        }
        for line in skill_lines
        if isinstance(line, dict)
    ]

    return {
        "run": run,
        "selected_project_ids": selected_ids,
        "selected_project_titles": selected_titles,
        "selected_project_set": sorted(selected_ids),
        "project_scores": project_scores,
        "requirement_labels": requirement_labels,
        "candidate_profile_fingerprint": _clean_text(
            selection.get("candidate_profile_fingerprint")
        ),
        "ranking_version": _clean_text(selection.get("ranking_version")),
        "evidence_mapping_version": _clean_text(
            selection.get("evidence_mapping_version")
        ),
        "skill_ranking_version": _clean_text(
            skills_result.get("skill_ranking_version")
        ),
        "skill_selection_owner": _clean_text(
            skills_result.get("skill_selection_owner")
        ),
        "skill_lines": skill_signature,
        "bullet_text_by_project": {
            _clean_text(project.get("title")): project.get("draft_bullets", []) or []
            for project in recommended
        },
        "selected_project_rows": selected_by_id,
    }


def _compare(runs: list[dict[str, Any]], max_score_spread: int) -> dict[str, Any]:
    first = runs[0]
    selected_order_stable = all(
        row["selected_project_ids"] == first["selected_project_ids"] for row in runs[1:]
    )
    selected_set_stable = all(
        row["selected_project_set"] == first["selected_project_set"] for row in runs[1:]
    )
    skill_lines_stable = all(row["skill_lines"] == first["skill_lines"] for row in runs[1:])
    fingerprints_stable = len({row["candidate_profile_fingerprint"] for row in runs}) == 1
    ranking_versions_stable = len({row["ranking_version"] for row in runs}) == 1
    skill_versions_stable = len({row["skill_ranking_version"] for row in runs}) == 1
    evidence_mapping_versions_stable = len(
        {row["evidence_mapping_version"] for row in runs}
    ) == 1
    skill_selection_owners_stable = len(
        {row["skill_selection_owner"] for row in runs}
    ) == 1

    all_project_ids = sorted(
        set().union(*(set(row["project_scores"]) for row in runs))
    )
    score_spreads: dict[str, int] = {}
    for project_id in all_project_ids:
        values = [row["project_scores"].get(project_id, 0) for row in runs]
        score_spreads[project_id] = max(values) - min(values)

    selected_ids = set(first["selected_project_ids"])
    selected_score_spreads = {
        project_id: spread
        for project_id, spread in score_spreads.items()
        if project_id in selected_ids
    }
    selected_scores_stable = all(
        spread <= max_score_spread for spread in selected_score_spreads.values()
    )

    core_link_differences: list[dict[str, Any]] = []
    for project_id in sorted(selected_ids):
        labels_by_run = [row["requirement_labels"].get(project_id, {}) for row in runs]
        requirement_ids = sorted(set().union(*(set(labels) for labels in labels_by_run)))
        for requirement_id in requirement_ids:
            values = [labels.get(requirement_id) for labels in labels_by_run]
            if len(set(values)) > 1:
                core_link_differences.append(
                    {
                        "project_id": project_id,
                        "requirement_id": requirement_id,
                        "labels_by_run": values,
                    }
                )

    passed = all(
        (
            selected_order_stable,
            selected_set_stable,
            skill_lines_stable,
            fingerprints_stable,
            ranking_versions_stable,
            skill_versions_stable,
            evidence_mapping_versions_stable,
            skill_selection_owners_stable,
            selected_scores_stable,
            not core_link_differences,
        )
    )

    bullet_wording_stable = all(
        row["bullet_text_by_project"] == first["bullet_text_by_project"] for row in runs[1:]
    )

    return {
        "run_count": len(runs),
        "runs": runs,
        "selected_project_order_stable": selected_order_stable,
        "selected_project_set_stable": selected_set_stable,
        "skill_lines_stable": skill_lines_stable,
        "candidate_profile_fingerprints_stable": fingerprints_stable,
        "ranking_versions_stable": ranking_versions_stable,
        "skill_ranking_versions_stable": skill_versions_stable,
        "evidence_mapping_versions_stable": evidence_mapping_versions_stable,
        "skill_selection_owners_stable": skill_selection_owners_stable,
        "project_score_spreads": score_spreads,
        "selected_project_score_spreads": selected_score_spreads,
        "maximum_selected_project_score_spread": max_score_spread,
        "selected_project_scores_stable": selected_scores_stable,
        "selected_project_requirement_label_differences": core_link_differences,
        "bullet_wording_stable": bullet_wording_stable,
        "bullet_wording_is_pass_fail_criterion": False,
        "passed": passed,
    }


def _write_csv(comparison: dict[str, Any], path: Path) -> None:
    rows = []
    for run in comparison["runs"]:
        rows.append(
            {
                "run": run["run"],
                "selected_projects": " | ".join(run["selected_project_titles"]),
                "ranking_version": run["ranking_version"],
                "skill_ranking_version": run["skill_ranking_version"],
                "evidence_mapping_version": run["evidence_mapping_version"],
                "skill_lines": json.dumps(run["skill_lines"], ensure_ascii=False),
            }
        )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run repeated Phase 6B Project and Skills tailoring."
    )
    parser.add_argument("--debug-bundle", required=True)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--max-projects", type=int, default=3)
    parser.add_argument("--max-bullets", type=int, default=3)
    parser.add_argument("--max-skill-items", type=int, default=20)
    parser.add_argument("--max-score-spread", type=int, default=5)
    parser.add_argument("--analysis-model")
    parser.add_argument("--reasoning-effort", choices=("low", "medium", "high"))
    parser.add_argument("--delay-seconds", type=float, default=1.0)
    parser.add_argument("--output-dir")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    if args.runs < 2:
        parser.error("--runs must be at least 2")

    bundle_path = _resolve_path(args.debug_bundle)
    if not bundle_path.exists():
        parser.error(f"Debug bundle not found: {bundle_path}")

    try:
        report, evidence_items = _load_bundle(bundle_path)
    except ValueError as exc:
        parser.error(str(exc))

    if args.reasoning_effort:
        os.environ["ANALYSIS_REASONING_EFFORT"] = args.reasoning_effort

    from llm import get_active_model, set_runtime_model

    if args.analysis_model:
        set_runtime_model(args.analysis_model, route="analysis")

    model = get_active_model("analysis")
    if args.output_dir:
        output_dir = _resolve_path(args.output_dir)
    else:
        output_dir = (
            PROJECT_ROOT
            / "stability_results"
            / f"tailoring_trial_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Phase 6B.1 tailoring stability trial")
    print(f"Debug bundle: {bundle_path}")
    print(f"Model: {model}")
    print(f"Runs: {args.runs}")
    print("This makes real API calls but does not create app sessions or DOCX files.")
    print()

    summaries: list[dict[str, Any]] = []
    for index in range(1, args.runs + 1):
        print(f"[run {index}/{args.runs}] Generating Projects + Skills...")
        started = time.monotonic()
        payload = _run_once(
            report=report,
            evidence_items=evidence_items,
            max_projects=args.max_projects,
            max_bullets=args.max_bullets,
            max_skill_items=args.max_skill_items,
        )
        elapsed = round(time.monotonic() - started, 2)
        (output_dir / f"run_{index:02d}.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        summary = _run_summary(payload, index)
        summary["elapsed_seconds"] = elapsed
        summaries.append(summary)
        print(
            f"[run {index}] selected={summary['selected_project_titles']} "
            f"skills={sum(len(line['items']) for line in summary['skill_lines'])} "
            f"elapsed={elapsed}s"
        )
        if index < args.runs and args.delay_seconds > 0:
            time.sleep(args.delay_seconds)

    comparison = _compare(summaries, args.max_score_spread)
    comparison["metadata"] = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "debug_bundle": str(bundle_path),
        "analysis_model": model,
        "reasoning_effort": args.reasoning_effort,
        "max_projects": args.max_projects,
        "max_bullets": args.max_bullets,
        "max_skill_items": args.max_skill_items,
    }
    (output_dir / "comparison.json").write_text(
        json.dumps(comparison, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    _write_csv(comparison, output_dir / "comparison.csv")

    print()
    print(f"Selected project order stable: {comparison['selected_project_order_stable']}")
    print(f"Selected project set stable: {comparison['selected_project_set_stable']}")
    print(f"Skills stable: {comparison['skill_lines_stable']}")
    print(f"Selected score spreads: {comparison['selected_project_score_spreads']}")
    print(
        "Selected requirement-label differences: "
        f"{len(comparison['selected_project_requirement_label_differences'])}"
    )
    print(
        "Bullet wording stable (informational only): "
        f"{comparison['bullet_wording_stable']}"
    )
    print(f"Result: {'PASS' if comparison['passed'] else 'FAIL'}")
    print(f"Reports saved to: {output_dir}")

    if args.strict and not comparison["passed"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

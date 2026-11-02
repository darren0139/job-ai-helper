"""Conservative project-count and fit-time project selection (V3).

Only previously generated project records are selectable at fit time. The preview
for pre-generation Auto count is deterministic and may elect one further project
with independently supported technology breadth. No model calls or scoring.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

POLICY_VERSION = "adaptive-project-selection-v3"
MODES = ("legacy", "balanced", "preserve_generated", "jd_focused", "manual")
MAX_PROJECTS = 8


def _name(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def _key(row: dict[str, Any]) -> str:
    project_id = str(row.get("project_id") or "").strip()
    if project_id:
        return "id:" + project_id.casefold()
    title = _name(row.get("title") or row.get("display_title"))
    return "title:" + title if title else ""


def _generated_pool(projects: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(projects, dict):
        return []
    rows = projects.get("adaptive_fit_original_projects")
    if rows is None:
        rows = projects.get("recommended_projects")
    if not isinstance(rows, list) or len(rows) > MAX_PROJECTS:
        raise ValueError("Malformed or oversized saved generated-project pool")
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or not _key(row):
            raise ValueError("Missing saved generated project identity")
        if _key(row) in seen:
            raise ValueError("Duplicate saved generated project identity")
        if not isinstance(row.get("draft_bullets"), list) or not any(
            isinstance(bullet, str) and bullet.strip()
            for bullet in row["draft_bullets"]
        ):
            raise ValueError("Project has no saved generated bullets")
        seen.add(_key(row))
    return rows


def generated_project_options(projects: dict[str, Any] | None) -> list[dict[str, str]]:
    return [
        {"key": _key(r), "label": str(r.get("display_title") or r.get("title") or ""),
         "priority": str(r.get("priority") or "")}
        for r in _generated_pool(projects)
    ]


def normalise_adaptive_project_settings(
    mode: Any, selected_keys: Any = None,
) -> tuple[str, list[str]]:
    mode = str(mode or "").strip().lower()
    if mode not in MODES:
        raise ValueError("Unsupported adaptive Projects mode")
    if selected_keys is None:
        selected_keys = []
    if not isinstance(selected_keys, (list, tuple)):
        raise ValueError("Manual projects must be a list")
    keys = []
    for raw in selected_keys:
        if not isinstance(raw, str):
            raise ValueError("Invalid manual project identity")
        key = raw.strip()
        if not key or key in keys or len(key) > 256:
            raise ValueError("Duplicate or empty manual project identity")
        keys.append(key)
    if len(keys) > MAX_PROJECTS:
        raise ValueError("Too many manual projects")
    if mode == "manual" and not keys:
        raise ValueError("Select at least one generated project")
    if mode != "manual" and keys:
        raise ValueError("Manual project keys are only accepted in Manual mode")
    return mode, keys


def _proven(row: dict[str, Any]) -> bool:
    return any(
        isinstance(m, dict)
        and str(m.get("match_label") or "").casefold() in {"direct", "transferable"}
        for m in (row.get("requirement_matches") or [])
    )


def apply_adaptive_project_selection(
    projects: dict[str, Any] | None, *, mode: str = "legacy",
    selected_keys: list[str] | None = None,
) -> dict[str, Any] | None:
    """Filter a saved, already-generated project set; never synthesize content."""
    mode, selected_keys = normalise_adaptive_project_settings(mode, selected_keys)
    if mode == "legacy" or not projects:
        return deepcopy(projects)
    pool = _generated_pool(projects)
    if not pool:
        raise ValueError("No saved generated projects available")
    if mode == "preserve_generated":
        chosen = pool
    elif mode == "manual":
        offered = {_key(row) for row in pool}
        if not set(selected_keys).issubset(offered):
            raise ValueError("Manual selection contains a project not in the saved generation")
        chosen = [row for row in pool if _key(row) in set(selected_keys)]
    elif mode == "jd_focused":
        chosen = [row for row in pool if _proven(row)]
        if not chosen:
            raise ValueError("No generated project has proven direct/transferable JD evidence")
    else:
        # Balanced: prioritize proven JD coverage; reserve room for one distinct
        # broader project when possible. Use existing native project-fit score only.
        ranked = sorted(pool, key=lambda row: (
            not _proven(row),
            -float(row.get("project_fit_score") or 0),
            pool.index(row),
        ))
        chosen_keys = {_key(row) for row in ranked[:5]}
        chosen = [row for row in pool if _key(row) in chosen_keys]
    result = deepcopy(projects)
    result["adaptive_fit_original_projects"] = deepcopy(pool)
    result["recommended_projects"] = deepcopy(chosen)
    result["adaptive_fit_selection"] = {
        "policy_version": POLICY_VERSION,
        "mode": mode,
        "selected_project_ids": [_key(row) for row in chosen],
        "excluded_project_ids": [_key(row) for row in pool if _key(row) not in {_key(c) for c in chosen}],
        "original_generated_count": len(pool),
        "selected_count": len(chosen),
        "source": "saved_generated_project_bullets_only",
        "no_new_content_or_job_match_credit": True,
    }
    return result


def select_auto_project_count(
    project_candidates: list[dict[str, Any]],
    preview: dict[str, Any], *, maximum: int = 5,
) -> tuple[int, str]:
    """Pick 1..5 projects before generation using only saved candidate evidence.

    At least four projects are considered when available. A fifth is admitted
    only when canonical evidence contains >=2 approved bullets and contributes
    a technical tool/skill not already represented in the first four.
    """
    if isinstance(maximum, bool) or not isinstance(maximum, int) or not 1 <= maximum <= 5:
        raise ValueError("Auto project maximum must be 1..5")
    if not isinstance(project_candidates, list) or not isinstance(preview, dict):
        raise ValueError("Invalid deterministic project preview")
    selections = preview.get("system_selected_projects")
    if not isinstance(selections, list) or not selections:
        raise ValueError("Auto project count requires a deterministic preview")
    by_title = {}
    for row in project_candidates:
        if not isinstance(row, dict):
            continue
        key = _name(row.get("title") or row.get("display_title"))
        if key in by_title:
            raise ValueError("Duplicate project candidate identity")
        by_title[key] = row
    rows = selections[:maximum]
    baseline = min(4, len(rows))
    if baseline < 4 or len(rows) < 5:
        return baseline, "Available ranked candidates; no fifth slot to evaluate"
    def terms(row: dict[str, Any]) -> set[str]:
        data = row.get("evidence_library_evidence") or {}
        raw = [*(row.get("canonical_tools") or []), *(data.get("skills") or []), *(data.get("tools") or [])]
        return {_name(v) for v in raw if isinstance(v, str) and _name(v)}
    def candidate(selection: dict[str, Any]) -> dict[str, Any]:
        key = _name(selection.get("title") or selection.get("display_title"))
        if key not in by_title:
            raise ValueError("Preview references a project not in candidate pool")
        return by_title[key]
    first = [candidate(row) for row in rows[:4]]
    fifth = candidate(rows[4])
    seen_terms = set().union(*(terms(row) for row in first))
    evidence = fifth.get("evidence_library_evidence") or {}
    bullets = [b.strip() for b in (evidence.get("bullets") or []) if isinstance(b, str) and b.strip()]
    if len(bullets) >= 2 and terms(fifth) - seen_terms:
        return 5, "Fifth project has approved canonical bullets and additional technical breadth"
    return 4, "Fifth project did not establish sufficient additional supported breadth"

"""Opt-in V3.1 variable-count source-grounded PROJECTS challenger.

Uses the existing V2.6 source-bound evaluator, immutable final-DOCX audit,
independent one-page renderer and V3.0 actual-DOCX A/B scorer. This is a bounded
JD-coverage *candidate selector*, not a proof of global optimality, semantic
factual validity, or the cause of the original fitter's deletion choices.
"""
from __future__ import annotations

from itertools import combinations
from typing import Any, Callable

from tailoring.phase9f_joint_resume_optimizer_v2_6 import (
    _get_rank, _key, _points, _rank_weights, _source_pool, _support,
    _text, _words, MAX_BULLETS_PER_PROJECT, MAX_POOL_PER_PROJECT,
    MAX_PROJECTS, MAX_WORDS,
)

VERSION = "phase9f-auto-optimize-v3.1-flexible-count-v1"
MAX_LOCAL_SLATES = 110
BEAM_SIZE = 160
MAX_TOTAL_BULLETS = 48
HARD = {"required", "core", "deal_breaker"}


def _hold(reason: str) -> dict[str, Any]:
    return {"version": VERSION, "status": "withheld", "reason": reason, "projects": []}


def build_flexible_optimization(
    audit: dict, projects: dict, *,
    evaluator: Callable[..., list[dict]] | None = None,
) -> dict[str, Any]:
    """Bounded, deterministic beam over 1..8 bullets per existing project.

    Only actual saved Base, Library or Current-final wording is eligible; no
    cross-project bullet movement, rewriting, new projects, or source mutation.
    The baseline total project-bullet word count is a conservative *proxy*
    budget; actual fitting is checked later by independently rendering a PDF.
    """
    if not isinstance(audit, dict) or audit.get("verified") is not True or not isinstance(projects, dict):
        return _hold("Verified actual-final audit and saved project ranking required.")
    sections = audit.get("projects")
    if not isinstance(sections, list) or not 1 <= len(sections) <= MAX_PROJECTS:
        return _hold("Project count outside bounded range.")
    names = [_text(s.get("project")) for s in sections if isinstance(s, dict)]
    if len(names) != len(sections) or not all(names) or len({_key(n) for n in names}) != len(names):
        return _hold("Final project identities missing or ambiguous.")
    if evaluator is None:
        from tailoring.stable_tailoring_ranking import build_bullet_evidence_priorities
        evaluator = build_bullet_evidence_priorities

    items = []
    global_weights: dict[str, float] = {}
    kinds: dict[str, str] = {}
    baseline_ids: set[str] = set()
    baseline_words = 0
    baseline_count = 0
    considered_slates = 0
    for section in sections:
        name = _text(section["project"])
        rank = _get_rank(projects, name)
        if rank is None:
            return _hold("Saved ranking missing or ambiguous for " + name)
        weights, error = _rank_weights(rank)
        if error:
            return _hold(name + ": " + error)
        for rid, weight in weights.items():
            global_weights[rid] = max(weight, global_weights.get(rid, 0.0))
        for req in rank.get("requirement_matches", []):
            if not isinstance(req, dict):
                return _hold(name + ": malformed requirement metadata.")
            rid = _text(req.get("requirement_id"))
            if rid not in weights:
                continue
            kind = _text(req.get("importance")).casefold()
            if kind not in HARD | {"preferred"}:
                # Conservative: unknown importance may not be sacrificed.
                kind = "unknown"
            if rid in kinds and kinds[rid] != kind:
                return _hold("Conflicting importance for JD requirement " + rid)
            kinds[rid] = kind
        pool, error = _source_pool(section)
        if error:
            return _hold(name + ": " + error)
        original = section.get("final")
        if not isinstance(original, list) or not 1 <= len(original) <= MAX_BULLETS_PER_PROJECT:
            return _hold(name + ": cannot safely preserve at least one final project bullet.")
        initial = [_text(x.get("text")) if isinstance(x, dict) else "" for x in original]
        if not all(initial) or len({_key(x) for x in initial}) != len(initial):
            return _hold(name + ": duplicate or missing actual final bullet.")
        found = {_key(x["text"]): i for i, x in enumerate(pool)}
        try:
            indices = tuple(sorted(found[_key(t)] for t in initial))
        except KeyError:
            return _hold(name + ": actual final wording not present in frozen source pool.")
        support, error = _support(pool, rank, evaluator)
        if support is None:
            return _hold(name + ": " + error)
        for row, ids in zip(pool, support):
            row["ids"] = sorted(ids & set(weights))
        baseline_ids.update(*(set(pool[i]["ids"]) for i in indices))
        baseline_words += sum(_words(x) for x in initial)
        baseline_count += len(initial)
        slates = []
        for count in range(1, min(len(pool), MAX_BULLETS_PER_PROJECT) + 1):
            for combo in combinations(range(len(pool)), count):
                considered_slates += 1
                ids = set().union(*(set(pool[i]["ids"]) for i in combo))
                words = sum(pool[i]["words"] for i in combo)
                edits = len(set(combo) ^ set(indices))
                slates.append({"indices": combo, "ids": ids, "words": words,
                               "edits": edits, "count": count})
        # Per-project candidate budget keeps a mixture of coverage-rich,
        # compact and baseline-compatible choices for cross-project trade-offs.
        by_coverage = sorted(slates, key=lambda s: (-_points(s["ids"], weights),
                                 s["words"], s["edits"], s["count"], s["indices"]))
        by_space = sorted(slates, key=lambda s: (s["words"], -_points(s["ids"], weights),
                              s["edits"], s["indices"]))
        by_stability = sorted(slates, key=lambda s: (s["edits"], -_points(s["ids"], weights),
                                  s["words"], s["indices"]))
        retained, seen = [], set()
        for choice in by_coverage[:60] + by_space[:25] + by_stability[:25]:
            if choice["indices"] not in seen:
                seen.add(choice["indices"])
                retained.append(choice)
        original_key = indices
        if original_key not in seen:
            retained.append(next(s for s in slates if s["indices"] == original_key))
        items.append({"project": name, "pool": pool, "initial": initial, "slates": retained})
    if not global_weights:
        return _hold("No saved matched JD requirements available to compare.")
    if baseline_words > MAX_WORDS or baseline_count > MAX_TOTAL_BULLETS:
        return _hold("Verified final bullet words or counts exceed bounded range.")

    baseline_points = _points(baseline_ids, global_weights)
    # Preserve every baseline Required/Core ID and, conservatively, IDs with
    # unrecognized importance. Phase V3.0 also independently rejects any actual
    # document Required/Core loss, even if this proxy missed it.
    required_ids = {rid for rid in baseline_ids if kinds.get(rid) != "preferred"}
    beam = [{"ids": set(), "words": 0, "count": 0, "edits": 0,
             "selected": [], "signature": ()}]
    for item in items:
        expanded = []
        for state in beam:
            for slate in item["slates"]:
                words = state["words"] + slate["words"]
                count = state["count"] + slate["count"]
                if words > baseline_words or count > MAX_TOTAL_BULLETS:
                    continue
                expanded.append({"ids": state["ids"] | slate["ids"],
                    "words": words, "count": count,
                    "edits": state["edits"] + slate["edits"],
                    "selected": state["selected"] + [slate],
                    "signature": state["signature"] + (slate["indices"],)})
        if not expanded:
            return _hold("No source-grounded slate meets the conservative word budget.")
        priority = lambda s: (-_points(s["ids"], global_weights), s["edits"],
                              s["words"], s["count"], s["signature"])
        leading = sorted(expanded, key=priority)[:120]
        lean = sorted(expanded, key=lambda s: (s["words"], -_points(s["ids"], global_weights),
                                                    s["edits"], s["signature"]))[:40]
        beam, seen = [], set()
        for state in leading + lean:
            signature = (frozenset(state["ids"]), state["words"], state["count"], state["edits"])
            if signature not in seen:
                seen.add(signature)
                beam.append(state)
                if len(beam) >= BEAM_SIZE:
                    break
    feasible = [s for s in beam if required_ids <= s["ids"]]
    if not feasible:
        return _hold("Every bounded alternative loses saved Required/Core/unknown baseline JD coverage.")
    feasible.sort(key=lambda s: (-_points(s["ids"], global_weights), s["edits"],
                                 s["words"], s["count"], s["signature"]))
    best = feasible[0]
    gained = sorted(best["ids"] - baseline_ids)
    lost = sorted(baseline_ids - best["ids"])
    changed = False
    base_only = False
    rows = []
    all_bullets = []
    for item, slate in zip(items, best["selected"]):
        chosen = [item["pool"][i] for i in slate["indices"]]
        after = [x["text"] for x in chosen]
        changed |= after != item["initial"]
        base_only |= any("Selected Base" in x["sources"] and "Evidence Library" not in x["sources"]
                         and "Current final" not in x["sources"] for x in chosen)
        all_bullets.extend(chosen)
        rows.append({"project": item["project"], "before": item["initial"],
                     "after": after, "sources": [list(x["sources"]) for x in chosen],
                     "supported_jd_ids": [list(x["ids"]) for x in chosen],
                     "before_count": len(item["initial"]), "after_count": len(after)})
    # Explain the bounded whole-slate decision without inventing pairwise winners.
    # This enumerates the actual *eligible* exact wordings and their provenance.
    # The recorded "not selected" status is an outcome, not a proof of lower
    # standalone quality (overlap and space depend on the entire slate).
    decision_rows = []
    for item, row in zip(items, rows):
        chosen_keys = {_key(t) for t in row["after"]}
        a_keys = {_key(t) for t in row["before"]}
        decisions = []
        for bullet in item["pool"]:
            ids = set(bullet["ids"])
            decisions.append({
                "text": bullet["text"],
                "source_labels": list(bullet["sources"]),
                "in_original_a": _key(bullet["text"]) in a_keys,
                "selected_for_proposed_b": _key(bullet["text"]) in chosen_keys,
                "saved_jd_ids": sorted(ids),
                "standalone_saved_coverage_points": _points(ids, global_weights),
                "word_count": bullet["words"],
            })
        decision_rows.append({"project": item["project"], "candidates": decisions})
    source_comparison = {
        "meaning": "Exact wording membership in saved Base, Library and/or Current final; not proof of causal source or an individual Base-vs-Library winner.",
        "decision_basis": "Bounded whole-resume distinct JD coverage with conservative word budget, hard-coverage preservation and tie-breaking for edits and space.",
        "limits": "Not every combination is tested; unselected bullets have no verified pairwise defeat reason; final B must pass actual DOCX scoring and one-page fitting.",
        "projects": decision_rows,
    }
    proxy = _points(best["ids"], global_weights)
    if not changed or proxy <= baseline_points:
        return {"version": VERSION, "status": "no_proxy_gain", "changed": False,
            "reason": "No higher-coverage, no-hard-loss variable-count slate within the bounded word budget.",
            "projects": rows, "baseline_points": baseline_points, "proposed_points": proxy,
            "source_comparison": source_comparison}
    multiplicity = {rid: sum(rid in x["ids"] for x in all_bullets) for rid in best["ids"]}
    for row in rows:
        row["selection_explanations"] = []
        for text, sources, ids in zip(row["after"], row["sources"], row["supported_jd_ids"]):
            exclusive = sorted(rid for rid in ids if multiplicity.get(rid) == 1)
            row["selection_explanations"].append({
                "text": text, "source_labels": list(sources),
                "saved_jd_ids": list(ids), "unique_in_selected_slate_ids": exclusive,
                "new_vs_a_ids": sorted(set(ids) & set(gained)),
                "selection_basis": "Part of a bounded whole-résumé JD coverage/space proposal; not an individual head-to-head quality verdict.",
                "fit_basis": "Must occur in a separately rendered verified one-page candidate; original fitting survival cause not established.",
            })
    return {"version": VERSION, "status": "candidate", "changed": True,
        "reason": "Better saved distinct-JD-coverage proxy under a flexible bullet-count and conservative word budget; actual DOCX scoring still required.",
        "projects": rows, "project_set_unchanged": True, "variable_bullet_counts": True,
        "baseline_points": baseline_points, "proposed_points": proxy,
        "baseline_words": baseline_words, "proposed_words": best["words"],
        "baseline_bullet_count": baseline_count, "proposed_bullet_count": best["count"],
        "baseline_jd_ids": sorted(baseline_ids), "proposed_jd_ids": sorted(best["ids"]),
        "gained_jd_ids": gained, "lost_jd_ids": lost,
        "protected_baseline_jd_ids": sorted(required_ids),
        "requires_base_review": base_only,
        "source_comparison": source_comparison,
        "selection_receipt": {
            "algorithm": "deterministic-bounded-beam-variable-per-project-count",
            "evaluated_local_slates": considered_slates,
            "total_candidate_word_cap": baseline_words,
            "limits": "Existing project set; 1-8 exact source bullets/project; no rewriting; no exhaustive global optimality guarantee.",
            "verified_fitting_explanation": False,
            "actual_docx_comparison_required": True,
        }}

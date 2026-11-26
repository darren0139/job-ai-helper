"""V3.10 grounded lead-first selection for prepared project bullets.

This is a conservative, source-wording-only policy. It never writes a new claim.
It follows V3.9 same-work dedupe, before the prepared snapshot is frozen.
The ordinary fitter/Phase 8 own the final native outcome; this module verifies
actual DOCX lead placement and never rewrites a historical generation.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import re
import unicodedata
from typing import Any

VERSION = "phase9f-v310-lead-first-intro-dedupe-v1"
_ACTION = {"built", "developed", "created", "designed", "engineered"}
_PRODUCT = re.compile(r"\b(?:platform|application|app|assistant|system|website|dashboard|game|chatbot|service)\b", re.I)
_STOP = {
    "a", "an", "and", "or", "the", "of", "in", "on", "with", "using", "for",
    "that", "to", "as", "end", "from", "into", "including", "built", "created",
    "developed", "designed", "engineered", "application", "app", "platform",
    "system", "assistant", "workflows", "service", "project", "support", "supports",
    "features", "tool", "users", "team", "technical", "software", "aided",
}


def _key(text: Any) -> str:
    return " ".join(str(text or "").split()).casefold()


def _tokens(text: str) -> set[str]:
    norm = unicodedata.normalize("NFKD", text.casefold())
    norm = "".join(c for c in norm if not unicodedata.combining(c))
    return {t for t in re.findall(r"[a-z0-9]+", norm) if len(t) > 2 and t not in _STOP}


def _lead_role(text: str, project: str) -> str | None:
    """Require a whole-product object, not just a 'Built' action verb.

    Read only the grammatical object before the first for/that/including/etc.
    E.g. 'Built a C++ asset manager for a game engine' is NOT a game lead.
    """
    cleaned = " ".join(str(text or "").split())
    if not cleaned or cleaned.split()[0].casefold() not in _ACTION:
        return None
    head = re.split(r"\b(?:for|that|which|including|enabling|to|with)\b|[,;:]", cleaned, maxsplit=1, flags=re.I)[0]
    if _PRODUCT.search(head):
        # 'Built game features' is not a whole-game introduction.
        if re.search(r"\b(?:game|app|application|system)\s+(?:features|workflows|mechanics|screens|modules)\b", head, re.I):
            return None
        return "whole_product"
    if (re.search(r"\bfull[- ]stack\b", head, re.I)
            and re.search(r"\bworkflows\b", head, re.I)
            and ("help desk" in project.casefold() or "help-desk" in project.casefold())):
        return "fullstack_product_workflows"
    return None


def _breadth(text: str) -> int:
    """Auditable, approximate number of distinct described product capabilities.

    Never infer JD credit from this count. Only use it to break introduction ties.
    """
    pieces = re.split(r",\s*|\s+and\s+(?=(?:supports?|offers?|provides?|enables?|integrates?|[a-z-]+\s+(?:analysis|parsing|tracking|tailoring)))", text, flags=re.I)
    count = sum(1 for part in pieces if len(_tokens(part)) >= 2)
    return min(6, max(1, count))


def _overlap(a: str, b: str) -> bool:
    """Independent domain overlap before treating two product leads as duplicates."""
    aa, bb = _tokens(a), _tokens(b)
    shared = aa & bb
    # Distinct products inside the same project shouldn't be merged by 'app' alone.
    return len(shared) >= 2 and len(shared) / max(1, min(len(aa), len(bb))) >= .19


def _source_tags(project: dict[str, Any], bullets: list[str]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for item in project.get("bullet_decision_receipts") or []:
        if isinstance(item, dict) and isinstance(item.get("bullet"), str):
            result.setdefault(_key(item["bullet"]), set()).update(str(t).casefold() for t in item.get("sources") or [])
    old = project.get("selected_blueprint_bullets")
    sources = project.get("selected_bullet_sources")
    if isinstance(old, list) and isinstance(sources, list) and len(old) == len(sources):
        for text, tags in zip(old, sources):
            if isinstance(text, str) and isinstance(tags, (list, tuple)):
                result.setdefault(_key(text), set()).update(str(tag).casefold() for tag in tags)
    return result


def _opposite_sources(a: set[str], b: set[str]) -> bool:
    base = {"base", "base resume", "selected base", "resume"}
    library = {"library", "evidence library", "evidence_library"}
    return bool((a & base and b & library) or (a & library and b & base))


def _matching_metadata(project: dict[str, Any], bullets: list[str]) -> list[dict[str, Any]] | None:
    raw = project.get("bullet_evidence_priorities")
    if not isinstance(raw, list):
        return None
    # V3.9 may have removed intermediate bullets. Match exact text, NEVER stale index.
    buckets: dict[str, list[dict[str, Any]]] = {}
    for item in raw:
        if not isinstance(item, dict) or not item.get("bullet_text"):
            return None
        buckets.setdefault(_key(item["bullet_text"]), []).append(item)
    ordered = []
    for bullet in bullets:
        items = buckets.get(_key(bullet), [])
        if len(items) != 1:  # including ambiguous duplicate source rows
            return None
        ordered.append(deepcopy(items[0]))
    return ordered


def _candidate_points(meta: dict[str, Any]) -> float:
    try:
        value = float(meta.get("evidence_value") or 0)
        return value if 0 <= value < 1e9 else 0.0
    except (TypeError, ValueError, OverflowError):
        return 0.0


def _rank_intro(index: int, bullet: str, row: dict[str, Any]) -> tuple:
    """Whole-app coverage first, existing JD evidence second; no invented native score."""
    return (_breadth(bullet), _candidate_points(row),
            int(bool(row.get("protect_during_fitting"))), -index)


def apply_lead_first_prepared(payload: dict[str, Any], *, enabled: bool = True) -> dict[str, Any]:
    """Return independent prepared copy; preserve source pool, evidence alignment."""
    if not isinstance(payload, dict):
        return payload
    out = deepcopy(payload)
    projects = out.get("recommended_projects")
    receipt: dict[str, Any] = {
        "version": VERSION, "status": "no_eligible_changes", "policy": "one_grounded_project_lead_before_features",
        "notes": "Roles and tie-breaks are wording-based. JD points are saved evidence links, not native bullet scores.",
        "projects": [], "removals": [],
    }
    if not enabled:
        receipt["status"] = "projects_locked"
    elif not isinstance(projects, list):
        receipt["status"] = "no_project_list"
    else:
        any_change = False
        for project in projects:
            if not isinstance(project, dict):
                continue
            name = str(project.get("display_title") or project.get("title") or "Project")
            bullets = project.get("draft_bullets")
            if not isinstance(bullets, list) or not bullets or not all(isinstance(t, str) and t.strip() for t in bullets):
                receipt["projects"].append({"project": name, "status": "invalid_bullets"})
                continue
            metas = _matching_metadata(project, bullets)
            if metas is None:
                receipt["projects"].append({"project": name, "status": "metadata_not_aligned"})
                continue
            leads = [(i, _lead_role(b, name)) for i, b in enumerate(bullets)]
            leads = [(i, role) for i, role in leads if role]
            if not leads:
                receipt["projects"].append({"project": name, "status": "no_grounded_product_introduction"})
                continue
            tags = _source_tags(project, bullets)
            winner = max((i for i, _ in leads), key=lambda i: _rank_intro(i, bullets[i], metas[i]))
            # Deduplicate OTHER product introductions only when same work is source-grounded.
            removed = set()
            for i, role in leads:
                if i == winner:
                    continue
                a, b = bullets[winner], bullets[i]
                if not _overlap(a, b):
                    continue
                if _key(a) != _key(b) and not _opposite_sources(tags.get(_key(a), set()), tags.get(_key(b), set())):
                    continue
                removed.add(i)
                receipt["removals"].append({
                    "project": name, "removed": b, "retained": a,
                    "reason": "related whole-application introductions; exact same project and cross-source provenance",
                    "removed_saved_evidence_points": _candidate_points(metas[i]),
                    "retained_saved_evidence_points": _candidate_points(metas[winner]),
                    "stage": "pre_fitting_v310",
                })
            unresolved = [bullets[i] for i, role in leads if i != winner and i not in removed
                          and _overlap(bullets[winner], bullets[i])]
            # Permutation retains every non-duplicate feature bullet in its original relative order.
            order = [winner] + [i for i in range(len(bullets)) if i != winner and i not in removed]
            changed = order != list(range(len(bullets)))
            if changed:
                any_change = True
            new_bullets = [bullets[i] for i in order]
            new_meta = [deepcopy(metas[i]) for i in order]
            for index, (text, row) in enumerate(zip(new_bullets, new_meta)):
                row["bullet_index"] = index
                row["bullet_text"] = text
            # One explicit verified lead per project, protected from shortening/fusion/deletion.
            new_meta[0]["protect_during_fitting"] = True
            new_meta[0]["lead_first_policy_version"] = VERSION
            new_meta[0]["evidence_priority"] = 1
            project["draft_bullets"] = new_bullets
            project["bullet_evidence_priorities"] = new_meta
            project["protected_bullet_indexes"] = [i for i, row in enumerate(new_meta)
                if row.get("protect_during_fitting") or row.get("protected_requirement_ids")
                or int(row.get("unique_required_core_count") or 0) > 0]
            compact = project.get("compact_bullets")
            if isinstance(compact, list) and len(compact) == len(bullets):
                project["compact_bullets"] = [compact[i] for i in order]
                # Protected introductions should not be compacted or fused.
                project["compact_bullets"][0] = new_bullets[0]
            elif compact:
                project["compact_bullets"] = []
            # Keep historical selection receipts aligned to their original source pool; don't mutate.
            receipt["projects"].append({
                "project": name,
                "status": (("lead_first_with_unresolved_intro" if changed else "lead_already_first_with_unresolved_intro")
                           if unresolved else ("selected_lead_first" if changed else "lead_already_first")),
                "lead": new_bullets[0], "lead_sha256": sha256(_key(new_bullets[0]).encode()).hexdigest(),
                "lead_sources": sorted(tags.get(_key(new_bullets[0]), ())),
                "lead_saved_evidence_points": _candidate_points(metas[winner]),
                "lead_role": next(role for i, role in leads if i == winner),
                "lead_breadth": _breadth(new_bullets[0]),
                "source_candidate_count": len(leads), "removed_intro_count": len(removed),
                "unresolved_intro_count": len(unresolved), "unresolved_intros": unresolved,
                "original_first_was_lead": winner == 0,
                "selection_reason": ("Only eligible whole-product introduction recorded" if len(leads) == 1
                    else "Most complete recorded whole-product introduction; saved JD points break breadth ties; original order breaks exact ties"),
                "prepared_bullet_count": len(new_bullets),
            })
        if any_change:
            receipt["status"] = "applied_before_fit"
    out["_v310_lead_intro"] = receipt
    return out


def verify_fitted_leads(fit: dict[str, Any], *, repo_root: Path, application_id: int) -> dict[str, Any]:
    receipt = fit.get("v310_lead_intro") if isinstance(fit, dict) else None
    if not isinstance(receipt, dict) or receipt.get("version") != VERSION:
        return {"status": "unavailable", "reason": "No V3.10 lead-first receipt"}
    if fit.get("fit_one_page") is not True:
        return {"status": "unverified", "reason": "A verified one-page fit is required", "receipt": receipt}
    names = [r["project"] for r in receipt.get("projects") or [] if r.get("lead")]
    if not names:
        return {"status": "no_eligible_leads", "receipt": receipt}
    from tailoring.phase9f_final_evidence_comparison_v2_4 import _docx_path, _read_exact_docx_bullets
    path, err = _docx_path(fit, Path(repo_root), int(application_id))
    if path is None:
        return {"status": "unverified", "reason": err, "receipt": receipt}
    actual, err = _read_exact_docx_bullets(path, names)
    if err:
        return {"status": "unverified", "reason": err, "receipt": receipt}
    checks = []
    for row in receipt["projects"]:
        if not row.get("lead"):
            continue
        bullets = actual.get(row["project"], [])
        first = bool(bullets and _key(bullets[0]) == _key(row["lead"]))
        absent = all(_key(item["removed"]) not in {_key(b) for b in bullets}
                     for item in receipt.get("removals") or [] if item["project"] == row["project"])
        unresolved = any(_key(text) in {_key(b) for b in bullets} for text in row.get("unresolved_intros") or [])
        checks.append({"project": row["project"], "lead_first": first, "removed_intros_absent": absent,
                       "unresolved_intro_present": unresolved, "verified": first and absent and not unresolved})
    return {"status": "verified" if checks and all(r["verified"] for r in checks) else "withheld",
            "checks": checks, "receipt": receipt, "docx_sha256": sha256(path.read_bytes()).hexdigest()}


def render_v310_lead_receipt(st: Any, *, fit_result: Any, repo_root: Path, application_id: int) -> None:
    if not isinstance(fit_result, dict) or not isinstance(fit_result.get("v310_lead_intro"), dict):
        return
    with st.expander("V3.10 — lead-first introductions & duplicate removals (actual DOCX)", expanded=False):
        result = verify_fitted_leads(fit_result, repo_root=repo_root, application_id=application_id)
        if result["status"] == "verified":
            st.success("Grounded project introductions verified first in the saved one-page DOCX.")
        elif result["status"] in ("unverified", "withheld"):
            st.warning("Lead-first verification withheld; do not claim a finalized lead without DOCX readback. " + result.get("reason", ""))
        elif result["status"] == "no_eligible_leads":
            st.caption("No eligible whole-product introduction was identified in the prepared project bullets.")
        for row in result.get("receipt", {}).get("projects") or []:
            st.write("**" + row["project"] + "** · " + row["status"])
            if row.get("unresolved_intro_count"):
                st.warning(str(row["unresolved_intro_count"]) + " possible duplicate introduction(s) unresolved: source provenance is insufficient for automatic removal.")
            if row.get("lead"):
                st.write("Lead first: " + row["lead"])
                st.caption("Base/Library sources: " + (", ".join(row.get("lead_sources") or []) or "unverified") +
                           " · Saved JD points: " + str(row["lead_saved_evidence_points"]) +
                           " · " + row["selection_reason"])
        for item in result.get("receipt", {}).get("removals") or []:
            st.write("Removed duplicate introduction in " + item["project"] + ": " + item["removed"])
            st.caption("Retained: " + item["retained"] + ". " + item["reason"])
        st.caption("No new wording is generated. The protected lead is a product overview; features follow. "
                   "Lead-first ordering is verified against the actual fitted DOCX, not a proposal.")

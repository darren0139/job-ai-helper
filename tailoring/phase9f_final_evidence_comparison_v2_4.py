"""Read-only Phase 8 final-fitted-DOCX bullet audit, scoped to confirmed Phase 9F sources.

This is a source/retention audit, NOT an optimizer or a proof of globally best
bullets. It never modifies DOCX, evidence, scoring, or SQLite.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from zipfile import BadZipFile
from typing import Any


def _txt(value: Any) -> str:
    return " ".join(str(value or "").split())


def _key(value: Any) -> str:
    return _txt(value).casefold()


def _docx_path(fit: dict[str, Any], root: Path, application_id: int) -> tuple[Path | None, str]:
    raw = str(fit.get("docx_path") or "").strip()
    if not raw:
        return None, "Saved fitted DOCX path is absent."
    root = root.resolve()
    path = Path(raw)
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    try:
        path.relative_to((root / "outputs" / "tailored_resumes").resolve())
    except ValueError:
        return None, "Saved fitted DOCX is outside the expected generated-output directory."
    if path.suffix.casefold() != ".docx" or not path.name.casefold().startswith(f"app_{int(application_id)}_"):
        return None, "Saved fitted DOCX filename does not match this Application Session."
    if not path.is_file() or path.stat().st_size > 12 * 1024 * 1024:
        return None, "Fitted DOCX is absent or exceeds the audit size limit."
    return path, ""


def _read_exact_docx_bullets(path: Path, titles: list[str]) -> tuple[dict[str, list[str]], str]:
    """Extract the rendered PROJECTS section; no inferred source-to-source pairing."""
    try:
        from docx import Document
        paragraphs = Document(str(path)).paragraphs
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, BadZipFile) as exc:
        return {}, f"Fitted DOCX could not be opened: {exc}"
    name_map = {_key(title): title for title in titles}
    if len(name_map) != len(titles) or not all(name_map):
        return {}, "Generated project identities are ambiguous."
    found = {name: [] for name in titles}
    in_projects = False
    current = None
    allow_metadata = False
    heading_count = 0
    seen_headings = set()
    section_count = 0
    for paragraph in paragraphs:
        raw = str(paragraph.text or "").strip()
        if not raw:
            continue
        if _key(raw) == "projects":
            section_count += 1
            in_projects = True
            current = None
            allow_metadata = False
            continue
        if in_projects and _key(raw) in {"skills", "technical skills", "certifications", "additional information"}:
            in_projects = False
        if not in_projects:
            continue
        stripped = raw.lstrip("•●▪‣·- \t")
        is_bullet = raw.startswith(("•", "●", "▪", "‣", "·", "- "))
        style = _key(getattr(getattr(paragraph, "style", None), "name", ""))
        is_bullet = is_bullet or "list bullet" in style
        if is_bullet:
            if current is None:
                return {}, "Fitted PROJECTS section has bullets without a verified project heading."
            found[current].append(_txt(stripped))
            allow_metadata = False
            continue
        matched = []
        for normalized, title in name_map.items():
            if _key(raw).startswith(normalized):
                suffix = raw[len(title):]
                if not suffix or suffix[0] in "\t |":
                    matched.append(title)
        if len(matched) != 1:
            if current is not None and allow_metadata:
                # Project tools / team metadata directly after its title.
                allow_metadata = False
                continue
            current = None
            continue
        title = matched[0]
        if title in seen_headings:
            return {}, "A project heading occurs twice in the fitted document."
        # Same heading twice with no bullets should also fail.
        seen_headings.add(title)
        heading_count += 1
        current = title
        allow_metadata = True
    if section_count != 1 or heading_count == 0:
        return {}, "Fitted DOCX has no unique, recognizable PROJECTS section."
    return found, ""


def _expected_final_counts(fit: dict[str, Any], titles: list[str]) -> tuple[dict[str, int] | None, dict[str, list[dict]], str]:
    prepared = (((fit.get("fitting_input_snapshot") or {}).get("prepared_initial_state") or {}).get("projects") or {}).get("recommended_projects")
    reductions = fit.get("remaining_active_reductions")
    if not isinstance(prepared, list) or not isinstance(reductions, list):
        return None, {}, "Saved fitter starting bullets or active reduction history is unavailable."
    initial = {}
    bykey = {_key(x): x for x in titles}
    for row in prepared:
        if not isinstance(row, dict):
            return None, {}, "Fitter starting project is malformed."
        title = bykey.get(_key(row.get("display_title") or row.get("title")))
        bullets = row.get("draft_bullets")
        if not title or title in initial or not isinstance(bullets, list) or not all(isinstance(x, str) for x in bullets):
            return None, {}, "Fitter starting project identity/bullets could not be verified."
        initial[title] = len(bullets)
    if set(initial) != set(titles):
        return None, {}, "Fitter starting project set differs from the generated-project set."
    events = {name: [] for name in titles}
    counts = dict(initial)
    for event in reductions:
        if not isinstance(event, dict):
            return None, {}, "Invalid active fitting event."
        kind = _txt(event.get("change_type"))
        section = _key(event.get("section"))
        if section in {"skills", "layout", "education", "experience"} or kind in {"reduce_skill", "remove_skill"}:
            continue
        title = bykey.get(_key(event.get("project")))
        if title is None or kind not in {"remove_bullet", "remove_project", "compact_rewrite", "shorten", "compact"}:
            return None, {}, "An active fitting event cannot be matched to a known project."
        events[title].append(event)
        if kind == "remove_bullet":
            counts[title] -= 1
        if kind == "remove_project":
            return None, {}, "Project-removal evidence requires a separately verified heading-absence audit."
        if counts[title] < 0:
            return None, {}, "Saved active fitting reductions remove more bullets than available."
    return counts, events, ""


def build_final_evidence_audit(
    projects: dict[str, Any] | None,
    fit: dict[str, Any] | None,
    candidates: Any,
    *,
    repo_root: Path,
    application_id: int,
    expected_generation_id: str = "",
) -> dict[str, Any]:
    """Fail closed unless the final DOCX, source list and fitting receipts agree."""
    def withheld(reason: str) -> dict[str, Any]:
        return {"projects": [], "notice": "Final evidence audit withheld: " + reason, "verified": False}

    if not isinstance(projects, dict) or not isinstance(fit, dict):
        return withheld("Saved project and fitting results are required.")
    if fit.get("fit_one_page") is not True or fit.get("page_count") != 1 or fit.get("fit_status") != "verified_one_page":
        return withheld("An exactly verified one-page fitting receipt is required.")
    saved_gen = _txt(fit.get("generation_id"))
    if expected_generation_id and saved_gen != _txt(expected_generation_id):
        return withheld("Selected generation does not match the saved fitting receipt.")
    from tailoring.phase9f_project_bullet_sources_v2_3 import build_project_bullet_source_view
    source = build_project_bullet_source_view(projects, candidates)
    sources = source.get("projects") or []
    if not sources:
        return withheld(source.get("notice") or "Frozen source comparison unavailable.")
    names = [row["project"] for row in sources]
    counts, events, reason = _expected_final_counts(fit, names)
    if counts is None:
        return withheld(reason)
    path, error = _docx_path(fit, repo_root, application_id)
    if path is None:
        return withheld(error)
    actual, error = _read_exact_docx_bullets(path, names)
    if error:
        return withheld(error)
    if any(len(actual[name]) != counts[name] for name in names):
        return withheld("The actual DOCX bullet counts disagree with saved active fitting reductions.")
    results = []
    for row in sources:
        name = row["project"]
        bullets = actual[name]
        base = row["base_bullets"]
        library = row["library_bullets"]
        draft = row["draft_bullets"]
        exact_base = {_key(x["Base Resume bullet"]) for x in base}
        exact_library = {_key(x["Evidence Library bullet"]) for x in library}
        draft_lookup = {_key(x["Generated draft bullet"]): x for x in draft}
        selected_library = {_key(x["Evidence Library bullet"]) for x in library if x["Canonical selection"] == "Selected"}
        final_rows = []
        for n, bullet in enumerate(bullets, 1):
            k = _key(bullet)
            base_exact, library_exact = k in exact_base, k in exact_library
            if base_exact and library_exact:
                lineage = "Exact wording exists in both sources; which source caused selection is not proven."
            elif library_exact:
                lineage = "Exact canonical Evidence Library wording; library is preferred by policy."
            elif base_exact:
                lineage = "Exact Base wording; generation route cannot be inferred from text equality."
            else:
                lineage = "Changed wording; no exact source-to-final attribution available."
            from_draft = draft_lookup.get(k)
            final_rows.append({
                "number": n, "text": bullet, "exact_base": base_exact, "exact_library": library_exact,
                "exact_generated_draft": bool(from_draft), "lineage": lineage,
                "jd_requirement_ids": (from_draft or {}).get("Saved JD requirement IDs") or "",
                "saved_evidence_priority": (from_draft or {}).get("Saved evidence priority"),
                "fit_protected": (from_draft or {}).get("Protected for fitting?") or "Not established",
            })
        outcome_base = [
            {"number": r["#"], "text": r["Base Resume bullet"], "exact_final": _key(r["Base Resume bullet"]) in {_key(x) for x in bullets},
             "reason": "Base bullets were comparison evidence; they were not direct canonical writer candidates by source policy."}
            for r in base
        ]
        outcome_library = [
            {"number": r["#"], "text": r["Evidence Library bullet"], "exact_final": _key(r["Evidence Library bullet"]) in {_key(x) for x in bullets},
             "selected": r["Canonical selection"] == "Selected",
             "reason": ("Selected for generation; any later shortening/removal must be checked against the fitting receipt."
                        if r["Canonical selection"] == "Selected" else "Available in canonical pool but not selected for the draft.")}
            for r in library
        ]
        changes = []
        for event in events.get(name, []):
            kind = _txt(event.get("change_type"))
            if kind == "remove_bullet":
                changes.append({"action": "Removed during fitting", "text": _txt(event.get("removed_bullet")),
                                "reason": _txt(event.get("evidence_loss_reason")) or "Saved removal reason not available",
                                "saved_evidence_value": event.get("evidence_value")})
            elif kind == "remove_project":
                changes.append({"action": "Project removed during fitting", "text": "", "reason": "Saved project-removal event", "saved_evidence_value": None})
            elif kind in {"compact_rewrite", "shorten", "compact"}:
                changes.append({"action": "Compaction/rewording action", "text": "", "reason": "Saved fitting action, not an independent bullet-quality result", "saved_evidence_value": None})
        results.append({"project": name, "base": outcome_base, "library": outcome_library,
                        "final": final_rows, "changes": changes, "base_count": len(base),
                        "library_count": len(library), "final_count": len(final_rows),
                        "selection_source": row["source"], "rank": row["rank"]})
    digest = sha256(path.read_bytes()).hexdigest()
    return {
        "verified": True, "projects": results,
        "docx_sha256": digest, "generation_id": saved_gen,
        "notice": "Final bullets independently read from the DOCX referenced by the saved one-page fit, cross-checked against active reductions. "
                  "This is NOT proof that the best possible bullets were chosen: no validated Base-vs-Library bullet optimizer ran. "
                  "File SHA-256 is computed now; the fit receipt does not contain a pinned DOCX digest.",
    }


def _render_bullet(st: Any, prefix: str, bullet: str, reason: str) -> None:
    with st.container(border=True):
        st.write("**" + prefix + "**")
        st.write(bullet)
        st.caption(reason)


def render_final_evidence_audit(
    st: Any, *, application_id: int, projects: dict[str, Any] | None,
    fit: dict[str, Any] | None, execution: dict[str, Any] | None,
    decision: dict[str, Any] | None, generation_id: str, repo_root: Path,
) -> bool:
    """Render after Phase 8, never rerun the scorer/model or access live Library."""
    with st.expander("Phase 8 — Final DOCX bullets vs Selected Base and Evidence Library", expanded=True):
        st.caption("Compare what is **actually present** in the final fitted document against both frozen source bullet lists. No new scoring or generation.")
        from tailoring.phase9f_project_bullet_sources_v2_3 import _bound_candidate_sources
        candidates, msg = _bound_candidate_sources(execution, decision)
        if candidates is None:
            st.info("Final evidence comparison withheld: " + msg)
            return False
        result = build_final_evidence_audit(projects, fit, candidates, repo_root=repo_root,
                                            application_id=application_id, expected_generation_id=generation_id)
        if not result["verified"]:
            st.info(result["notice"])
            return False
        st.caption(result["notice"])
        rows = result["projects"]
        options = list(range(len(rows)))
        picked = st.selectbox("Project — inspect actual final bullets and alternative sources", options,
                              format_func=lambda i: rows[i]["project"],
                              key=f"phase9f_final_evidence_v24_{int(application_id)}")
        if picked is None:
            return True
        chosen = rows[picked]
        c1, c2, c3 = st.columns(3)
        c1.metric("Original Base", chosen["base_count"])
        c2.metric("Canonical Library", chosen["library_count"])
        c3.metric("In final DOCX", chosen["final_count"])
        tab_final, tab_base, tab_library, tab_fit, tab_quality = st.tabs([
            "Final DOCX bullets", "Selected Base alternatives", "Evidence Library alternatives", "Fitting decisions", "Coverage-quality pilot (shadow)"
        ])
        with tab_final:
            for row in chosen["final"]:
                detail = row["lineage"]
                detail += " Exact generated draft: " + ("Yes" if row["exact_generated_draft"] else "No; wording or fitting changed")
                if row["jd_requirement_ids"]:
                    detail += " Saved draft JD IDs: " + row["jd_requirement_ids"]
                if row["saved_evidence_priority"] is not None:
                    detail += f" · Saved draft evidence value: {row['saved_evidence_priority']}"
                detail += " · Draft-level fit protection: " + str(row["fit_protected"])
                _render_bullet(st, f"Final F{row['number']}", row["text"], detail)
            if not chosen["final"]:
                st.caption("Project absent from final DOCX.")
        with tab_base:
            st.caption("Base bullets were not direct writer candidates under the current canonical-library policy. An omission does not prove lower quality.")
            for row in chosen["base"]:
                status = "Exact wording in final" if row["exact_final"] else "Not present verbatim in final"
                _render_bullet(st, f"Base B{row['number']} — {status}", row["text"], row["reason"])
        with tab_library:
            for row in chosen["library"]:
                status = "Exact wording in final" if row["exact_final"] else "Not present verbatim in final"
                selected = "Selected canonical" if row["selected"] else "Not selected for draft"
                _render_bullet(st, f"Library L{row['number']} — {selected}", row["text"], status + ". " + row["reason"])
        with tab_fit:
            if not chosen["changes"]:
                st.caption("No active project-fitting changes recorded for this project.")
            for row in chosen["changes"]:
                _render_bullet(st, row["action"], row["text"] or "Saved fitting action", row["reason"])
            st.caption("Fitting protects or removes evidence according to recorded constraints; this does not establish a global best alternative.")
        with tab_quality:
            from tailoring.phase9f_bullet_quality_shadow_v2_5 import (
                render_shadow_bullet_quality_trial,
            )
            render_shadow_bullet_quality_trial(
                st, audit_project=chosen, projects=projects,
                application_id=application_id,
            )
        with st.popover("Audit provenance"):
            st.code("Saved generation: " + result["generation_id"] + "\nCurrent DOCX SHA-256: " + result["docx_sha256"])
    return True

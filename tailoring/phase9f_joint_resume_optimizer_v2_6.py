"""Phase 9F V2.6 opt-in whole-slate bullet optimization with real, reversible DOCX output.

This is a PRODUCTION-CANDIDATE WRITER (not a shadow score): user-authorized
candidates are saved separately and checked by actual PDF render. The existing
accepted DOCX, saved generation, resume sources, and Evidence Library are never
modified. The project *set* is frozen in this first bounded implementation;
all project bullets are optimized jointly against one global JD-coverage proxy.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from itertools import combinations
from math import isfinite
from pathlib import Path
from typing import Any, Callable
import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid

VERSION = "phase9f-joint-bullet-optimizer-v2.6"
MAX_PROJECTS = 8
MAX_POOL_PER_PROJECT = 16
MAX_BULLETS_PER_PROJECT = 8
MAX_LOCAL_SLATES = 90
BEAM_SIZE = 128
MAX_WORDS = 1500


def _text(v: Any) -> str:
    return " ".join(str(v or "").split())


def _key(v: Any) -> str:
    return _text(v).casefold()


def _words(v: Any) -> int:
    return len(_text(v).split())


def _reject(reason: str) -> dict[str, Any]:
    return {"status": "withheld", "reason": reason, "version": VERSION, "projects": []}


def _get_rank(project_result: dict, name: str) -> dict | None:
    rows = project_result.get("candidate_project_ranking")
    if not isinstance(rows, list):
        return None
    found = [r for r in rows if isinstance(r, dict) and
             _key(r.get("display_title") or r.get("title")) == _key(name)]
    return found[0] if len(found) == 1 else None


def _rank_weights(rank: dict) -> tuple[dict[str, float], str]:
    matches = rank.get("requirement_matches")
    if not isinstance(matches, list):
        return {}, "No saved requirement-match receipt."
    weights: dict[str, float] = {}
    for row in matches:
        if not isinstance(row, dict):
            return {}, "Invalid requirement-match row."
        rid = _text(row.get("requirement_id"))
        if not rid or rid in weights:
            return {}, "Missing or duplicate requirement ID in ranking."
        if row.get("match_label") in {"direct", "transferable", "weak"}:
            try:
                n = float(row.get("coverage_points"))
            except (ValueError, TypeError):
                return {}, "Unknown JD coverage value."
            if not isfinite(n) or n <= 0 or n > 10000:
                return {}, "Invalid JD coverage value."
            weights[rid] = n
        elif row.get("match_label") != "none":
            return {}, "Unknown requirement match label."
    return weights, ""


def _source_pool(row: dict, *, max_pool: int = MAX_POOL_PER_PROJECT) -> tuple[list[dict], str]:
    pool: list[dict] = []
    by_key: dict[str, dict] = {}
    for source, field in (("Selected Base", "base"), ("Evidence Library", "library"), ("Current final", "final")):
        values = row.get(field)
        if not isinstance(values, list):
            return [], "Missing frozen source or verified final bullets."
        for n, item in enumerate(values, 1):
            if not isinstance(item, dict) or not isinstance(item.get("text"), str):
                return [], "Invalid source bullet record."
            text = _text(item["text"])
            if not text or len(text) > 1200 or text.startswith(("•", "- ")):
                return [], "Malformed source bullet text."
            key = _key(text)
            if key in by_key:
                if source not in by_key[key]["sources"]:
                    by_key[key]["sources"].append(source)
            else:
                candidate = {"text": text, "sources": [source], "words": _words(text), "ids": []}
                by_key[key] = candidate
                pool.append(candidate)
    if len(pool) > max_pool:
        return [], f"Too many distinct bullet candidates ({len(pool)} > {max_pool})."
    return pool, ""


def _support(rows: list[dict], rank: dict, evaluator: Callable) -> tuple[list[set[str]] | None, str]:
    try:
        result = evaluator(bullets=[r["text"] for r in rows], ranking_row=rank)
    except Exception as exc:
        return None, "JD support evaluator failed: " + type(exc).__name__
    known = {m.get("requirement_id") for m in rank.get("requirement_matches", []) if isinstance(m, dict)}
    if not isinstance(result, list) or len(result) != len(rows):
        return None, "JD support evaluator returned incomplete results."
    found = []
    for index, (item, row) in enumerate(zip(result, rows)):
        if (not isinstance(item, dict) or item.get("bullet_index") != index or
            _key(item.get("bullet_text")) != _key(row["text"])):
            return None, "JD support evaluator changed bullet ordering or identity."
        ids = item.get("supported_requirement_ids")
        if not isinstance(ids, list) or not all(isinstance(x, str) and x in known for x in ids):
            return None, "JD support evaluator returned unknown requirement identities."
        found.append(set(ids))
    return found, ""


def _points(ids: set[str], weights: dict[str, float]) -> float:
    return round(sum(weights.get(rid, 0.0) for rid in ids), 4)


def build_joint_optimization(
    audit: dict, projects: dict, *,
    evaluator: Callable[..., list[dict]] | None = None,
) -> dict:
    """Select a bounded best *tested* whole-project-bullet slate.

    Existing project set and per-project final count remain fixed to preserve
    template/space. Joint objective de-duplicates canonical JD coverage across
    *all* projects. Exact source bullets only; never fabricate or auto-rewrite.
    No source/fit argument is mutated. Deterministic beam approximation, not a
    mathematical global optimum or verified applicant evidence judge.
    """
    if not isinstance(audit, dict) or not audit.get("verified") or not isinstance(projects, dict):
        return _reject("Exact verified final DOCX audit and saved project ranking are required.")
    sections = audit.get("projects")
    if not isinstance(sections, list) or not 1 <= len(sections) <= MAX_PROJECTS:
        return _reject("Project count outside the bounded production range.")
    names = [_text(p.get("project")) for p in sections if isinstance(p, dict)]
    if len(names) != len(sections) or len({_key(n) for n in names}) != len(names):
        return _reject("Missing or ambiguous final project names.")
    if evaluator is None:
        from tailoring.stable_tailoring_ranking import build_bullet_evidence_priorities
        evaluator = build_bullet_evidence_priorities
    global_weights: dict[str, float] = {}
    all_sections = []
    total_words = 0
    baseline_ids: set[str] = set()
    baseline_items = []
    for section in sections:
        name = _text(section["project"])
        rank = _get_rank(projects, name)
        if rank is None:
            return _reject("Saved ranking is missing or ambiguous for " + name)
        weights, error = _rank_weights(rank)
        if error:
            return _reject(name + ": " + error)
        for rid, weight in weights.items():
            global_weights[rid] = max(global_weights.get(rid, 0.0), weight)
        pool, error = _source_pool(section)
        if error:
            return _reject(name + ": " + error)
        actual = section["final"]
        count = len(actual)
        if not 1 <= count <= MAX_BULLETS_PER_PROJECT or count > len(pool):
            return _reject(name + ": final bullet count exceeds bounded available source pool.")
        support, error = _support(pool, rank, evaluator)
        if support is None:
            return _reject(name + ": " + error)
        for row, ids in zip(pool, support):
            row["ids"] = sorted(ids & set(weights))
        initial_texts = [_text(row["text"]) for row in actual]
        if len({_key(t) for t in initial_texts}) != len(initial_texts):
            return _reject(name + ": repeated final bullet text cannot be replaced safely.")
        idx = {_key(x["text"]): n for n, x in enumerate(pool)}
        try:
            baseline_indices = tuple(idx[_key(t)] for t in initial_texts)
        except KeyError:
            return _reject(name + ": final content is absent from source/final pool.")
        baseline_set = set().union(*(set(pool[i]["ids"]) for i in baseline_indices))
        baseline_ids.update(baseline_set)
        baseline_items.append({"project": name, "selected": deepcopy(initial_texts)})
        total_words += sum(_words(x) for x in initial_texts)
        # Enumerate bounded, deduplicated per-project subsets; same number of bullets.
        slates = []
        for combo in combinations(range(len(pool)), count):
            ids = set().union(*(set(pool[i]["ids"]) for i in combo))
            used = sum(pool[i]["words"] for i in combo)
            edits = sum(_key(pool[i]["text"]) not in {_key(x) for x in initial_texts} for i in combo)
            slates.append({"indices": combo, "ids": ids, "words": used, "edits": edits})
        # Keep the baseline and both high-coverage and short alternatives so
        # cross-project de-duplication has room to improve the global objective.
        slates.sort(key=lambda s: (-_points(s["ids"], weights), s["edits"], s["words"], s["indices"]))
        least_words = sorted(slates, key=lambda s: (s["words"], -_points(s["ids"], weights), s["edits"]))[:20]
        chosen_slates, seen = [], set()
        for slate in (slates[:MAX_LOCAL_SLATES - len(least_words)] + least_words):
            if slate["indices"] not in seen:
                chosen_slates.append(slate)
                seen.add(slate["indices"])
        basekey = tuple(sorted(baseline_indices))
        if basekey not in seen:
            chosen_slates.append(next(s for s in slates if s["indices"] == basekey))
        all_sections.append({"project": name, "pool": pool, "slates": chosen_slates,
                             "baseline": initial_texts, "count": count})
    if total_words > MAX_WORDS:
        return _reject("Fitted source project bullets exceed the bounded global word limit.")
    if not global_weights:
        return _reject("No saved matched JD requirements; no justified selection improvement.")
    baseline_points = _points(baseline_ids, global_weights)
    # Deterministic beam search over all projects, single global word budget.
    beam = [{"ids": set(), "words": 0, "edits": 0, "chosen": [], "indices": ()}]
    for section in all_sections:
        expanded = []
        for state in beam:
            for choice in section["slates"]:
                words = state["words"] + choice["words"]
                if words > total_words:
                    continue
                expanded.append({"ids": state["ids"] | choice["ids"], "words": words,
                                 "edits": state["edits"] + choice["edits"],
                                 "chosen": state["chosen"] + [choice],
                                 "indices": state["indices"] + (choice["indices"],)})
        if not expanded:
            return _reject("No tested alternative stayed within the final DOCX word budget.")
        # Keep some sparse low-word states for later projects as well as top coverage.
        expanded.sort(key=lambda s: (-_points(s["ids"], global_weights), s["edits"], s["words"], s["indices"]))
        lean = sorted(expanded, key=lambda s: (s["words"], -_points(s["ids"], global_weights), s["edits"]))[:BEAM_SIZE // 4]
        unique, seen = [], set()
        for row in expanded[:BEAM_SIZE] + lean:
            signature = (frozenset(row["ids"]), row["words"], row["edits"])
            if signature not in seen:
                unique.append(row)
                seen.add(signature)
                if len(unique) >= BEAM_SIZE:
                    break
        beam = unique
    # Prefer retention on equal proxy values; no churn for wording-only ties.
    beam.sort(key=lambda s: (-_points(s["ids"], global_weights), s["edits"], s["words"], s["indices"]))
    best = beam[0]
    gained = sorted(best["ids"] - baseline_ids)
    lost = sorted(baseline_ids - best["ids"])
    rows = []
    base_only = False
    for sec, choice in zip(all_sections, best["chosen"]):
        pool = sec["pool"]
        selected = [pool[n] for n in choice["indices"]]
        base_only |= any("Selected Base" in x["sources"] and "Evidence Library" not in x["sources"]
                         and "Current final" not in x["sources"] for x in selected)
        rows.append({"project": sec["project"], "before": sec["baseline"],
                     "after": [x["text"] for x in selected],
                     "sources": [list(x["sources"]) for x in selected],
                     "supported_jd_ids": [x["ids"] for x in selected]})
    value = _points(best["ids"], global_weights)
    changed = any(r["before"] != r["after"] for r in rows)
    if not changed or value <= baseline_points:
        return {"status": "no_proxy_gain", "reason": "No coverage-proxy improvement over the current fitted DOCX under the bounded candidate pool/word budget.",
                "version": VERSION, "projects": rows, "baseline_points": baseline_points,
                "proposed_points": value, "changed": False, "requires_base_review": False,
                "baseline_jd_ids": sorted(baseline_ids), "proposed_jd_ids": sorted(best["ids"]),
                "gained_jd_ids": [], "lost_jd_ids": []}
    return {"status": "candidate", "reason": "Higher distinct JD-coverage proxy among bounded tested slates, not independently verified factual quality.",
            "version": VERSION, "projects": rows, "baseline_points": baseline_points,
            "proposed_points": value, "baseline_words": total_words, "proposed_words": best["words"],
            "changed": True, "requires_base_review": base_only,
            "baseline_jd_ids": sorted(baseline_ids), "proposed_jd_ids": sorted(best["ids"]),
            "gained_jd_ids": gained, "lost_jd_ids": lost,
            "project_set_unchanged": True}


def _bullet_locations(document: Any, expected: list[dict]) -> list[list[Any]]:
    """Locate bullet paragraphs by exact final audit text and unique headings.

    Fail closed if template format cannot be paired without ambiguity.
    """
    titles = [r["project"] for r in expected]
    matches = {_key(t): t for t in titles}
    if len(matches) != len(titles):
        raise ValueError("Duplicate selected project titles.")
    found: dict[str, list[Any]] = {x: [] for x in titles}
    seen = set()
    in_projects = False
    current = None
    allow_metadata = False
    section_count = 0
    for p in document.paragraphs:
        raw = (p.text or "").strip()
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
        stylename = _key(getattr(getattr(p, "style", None), "name", ""))
        is_bullet = raw.startswith(("•", "●", "▪", "‣", "·", "- ")) or "list bullet" in stylename
        if is_bullet:
            if current is None:
                raise ValueError("Unmatched bullet in project section.")
            found[current].append(p)
            allow_metadata = False
            continue
        headings = []
        for normalized, title in matches.items():
            if _key(raw).startswith(normalized):
                suffix = raw[len(title):]
                if not suffix or suffix[0] in "\t |":
                    headings.append(title)
        if len(headings) != 1:
            if current and allow_metadata:
                allow_metadata = False
                continue
            current = None
            continue
        title = headings[0]
        if title in seen:
            raise ValueError("Duplicate project heading in source DOCX.")
        seen.add(title)
        current = title
        allow_metadata = True
    if section_count != 1 or seen != set(titles):
        raise ValueError("Final DOCX PROJECTS headings differ from verified audit.")
    for row in expected:
        actual = [_text(p.text.lstrip("•●▪‣·- \t")) for p in found[row["project"]]]
        if actual != row["before"]:
            raise ValueError("Exact saved final bullets do not match DOCX paragraphs.")
    return [found[row["project"]] for row in expected]


def _replace_content(paragraph: Any, text: str) -> None:
    """Preserve paragraph + numbering formatting; do not edit non-project sections."""
    raw = paragraph.text
    prefix_match = re.match(r"^(\s*[•●▪‣·]|\s*-)(\s*)", raw)
    prefix = prefix_match.group(0) if prefix_match else ""
    if not prefix and "list bullet" not in _key(paragraph.style.name):
        raise ValueError("Unrecognized bullet formatting; refusing to write.")
    runs = list(paragraph.runs)
    if not runs:
        raise ValueError("Bullet paragraph is missing text runs.")
    meaningful = [r for r in runs if r.text.strip() and r.text.strip() not in {"•", "●", "▪", "‣", "·", "-"}]
    def fingerprint(r: Any) -> tuple:
        return (r.bold, r.italic, r.underline, r.font.name, r.font.size.pt if r.font.size else None)
    if meaningful and len({fingerprint(r) for r in meaningful}) > 1:
        raise ValueError("Mixed character formatting in a project bullet; refusing lossy rewrite.")
    target = meaningful[0] if meaningful else runs[0]
    for run in runs:
        if run._element is target._element:
            run.text = (prefix if run._element is runs[0]._element else "") + text
        elif prefix and run._element is runs[0]._element:
            run.text = prefix
        else:
            run.text = ""


def write_optimized_docx(*, source_path: Path, audit_sha: str, proposal: dict,
                         destination: Path) -> None:
    """Produce an *uncommitted, separate* actual DOCX. Never change source."""
    from docx import Document
    src = Path(source_path).resolve()
    target = Path(destination).resolve()
    if not src.is_file() or src == target or sha256(src.read_bytes()).hexdigest() != audit_sha:
        raise ValueError("Verified source DOCX changed or destination is the same file.")
    if target.exists():
        raise ValueError("Refusing to overwrite an existing candidate file.")
    if proposal.get("status") != "candidate" or not proposal.get("changed"):
        raise ValueError("Only an improved candidate can be materialized.")
    if "lead_contract" in proposal:
        from tailoring.phase9f_v37_lead_candidate import VERSION as LEAD_POLICY_VERSION
        from tailoring.phase9f_v37_project_leads import validate_fitted_order

        contract = proposal["lead_contract"]
        if (not isinstance(contract, dict) or contract.get("version") != LEAD_POLICY_VERSION
                or contract.get("source_docx_sha256") != audit_sha or not isinstance(contract.get("leads"), dict)):
            raise ValueError("The reviewed lead contract is invalid for the fitted source DOCX.")
        validate_fitted_order(proposal["projects"], contract["leads"])
    doc = Document(str(src))
    locations = _bullet_locations(doc, proposal["projects"])
    variable = proposal.get("variable_bullet_counts") is True
    if variable:
        from tailoring.phase9f_auto_optimize_v31 import VERSION as V31_VERSION
        from tailoring.phase9f_evidence_optimizer_v33 import VERSION as V33_VERSION
        from tailoring.phase9f_jd_relevance_optimizer_v35 import VERSION as V35_VERSION
        if proposal.get("version") not in (V31_VERSION, V33_VERSION, V35_VERSION) or not proposal.get("project_set_unchanged"):
            raise ValueError("Variable-count editing requires an identified V3.1/V3.3/V3.5 proposal.")
    for row, paragraphs in zip(proposal["projects"], locations):
        after = row.get("after")
        if not isinstance(after, list) or not 1 <= len(after) <= MAX_BULLETS_PER_PROJECT or not all(
            isinstance(x, str) and x.strip() and len(x) <= 1200 for x in after
        ):
            raise ValueError("Unsafe target bullet text or count.")
        if not variable and len(paragraphs) != len(after):
            raise ValueError("Project bullet count changed; cannot preserve source layout safely.")
        if variable:
            from docx.text.paragraph import Paragraph
            # Clone exactly the verified bullet paragraph (including style and
            # numbering); only this section is edited. Post-write re-audit below.
            while len(paragraphs) < len(after):
                template = paragraphs[-1]
                element = deepcopy(template._element)
                template._element.addnext(element)
                paragraphs.append(Paragraph(element, template._parent))
        for paragraph, replacement in zip(paragraphs, after):
            _replace_content(paragraph, replacement)
        if variable:
            for paragraph in paragraphs[len(after):]:
                paragraph._element.getparent().remove(paragraph._element)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        doc.save(str(target))
        verify = Document(str(target))
        reread = _bullet_locations(verify, [{**row, "before": row["after"]} for row in proposal["projects"]])
        if sum(map(len, reread)) != sum(len(row["after"]) for row in proposal["projects"]):
            raise ValueError("Post-write project bullet integrity verification failed.")
    except Exception:
        target.unlink(missing_ok=True)
        raise


def _soffice() -> str:
    for program in ("soffice", "libreoffice"):
        executable = shutil.which(program)
        if executable:
            return executable
    for p in (Path("C:/Program Files/LibreOffice/program/soffice.exe"),
              Path("C:/Program Files (x86)/LibreOffice/program/soffice.exe")):
        if p.exists():
            return str(p)
    raise RuntimeError("LibreOffice could not be found for actual page-fit verification.")


def _render_pdf(docx: Path, directory: Path) -> Path:
    binary = _soffice()
    # Distinct temporary profile prevents contention with a user-open LibreOffice.
    profile = (directory / "lo_profile").resolve().as_uri()
    command = [binary, f"-env:UserInstallation={profile}", "--headless", "--convert-to",
               "pdf", "--outdir", str(directory), str(docx)]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=120)
    pdf = directory / (docx.stem + ".pdf")
    if completed.returncode != 0 or not pdf.is_file():
        raise RuntimeError("Actual PDF conversion failed; optimized DOCX not accepted.")
    return pdf


def materialize_verified_candidate(*, source_docx: Path, audit_sha: str, proposal: dict,
                                   repo_root: Path, application_id: int,
                                   generation_id: str,
                                   converter: Callable[[Path, Path], Path] | None = None) -> dict:
    """Render PDF and save versioned real DOCX+PDF only after 1-page verification.

    All durable files are distinct under outputs/tailored_resumes/optimizations;
    no accepted generation, session state, or DB row is changed.
    """
    if not re.fullmatch(r"[0-9a-zA-Z_-]{4,100}", str(generation_id or "")):
        raise ValueError("Verified generation ID required.")
    outdir = (Path(repo_root).resolve() / "outputs" / "tailored_resumes" / "optimizations")
    source = Path(source_docx).resolve()
    try:
        source.relative_to((Path(repo_root).resolve() / "outputs" / "tailored_resumes").resolve())
    except ValueError as exc:
        raise ValueError("Source is outside the expected generated-output directory.") from exc
    if not source.name.casefold().startswith(f"app_{int(application_id)}_"):
        raise ValueError("Foreign application source DOCX.")
    if proposal.get("status") != "candidate":
        raise ValueError("Proposal has no proven improvement.")
    with tempfile.TemporaryDirectory(prefix="phase9f_v26_") as tmp:
        work = Path(tmp)
        path = work / f"app_{int(application_id)}_v26_{uuid.uuid4().hex[:12]}.docx"
        write_optimized_docx(source_path=source, audit_sha=audit_sha, proposal=proposal, destination=path)
        pdf = (converter or _render_pdf)(path, work)
        if Path(pdf).resolve().parent != work.resolve() or not Path(pdf).is_file():
            raise RuntimeError("Page verifier did not return a local temporary PDF.")
        try:
            from pypdf import PdfReader
            pages = len(PdfReader(str(pdf)).pages)
        except ImportError:
            import fitz
            with fitz.open(str(pdf)) as document:
                pages = len(document)
        if pages != 1:
            raise RuntimeError(f"Optimized output was {pages} pages; no candidate saved. Original remains unchanged.")
        outdir.mkdir(parents=True, exist_ok=True)
        dest_docx = outdir / path.name
        dest_pdf = outdir / (path.stem + ".pdf")
        manifest = outdir / (path.stem + ".json")
        # Unique UUID filenames and exclusive writes; never overwrite existing files.
        saved = []
        try:
            for src, dst in ((path, dest_docx), (Path(pdf), dest_pdf)):
                with open(dst, "xb") as handle:
                    handle.write(src.read_bytes())
                saved.append(dst)
            variable = proposal.get("variable_bullet_counts") is True
            receipt = {"version": proposal.get("version") if variable else VERSION, "application_id": int(application_id),
                       "generation_id": generation_id, "original_sha256": audit_sha,
                       "candidate_docx_sha256": sha256(dest_docx.read_bytes()).hexdigest(),
                       "verified_pdf_pages": pages, "saved_project_count": len(proposal["projects"]),
                       "baseline_points": proposal["baseline_points"],
                       "proposed_points": proposal["proposed_points"],
                       "gained_jd_ids": proposal["gained_jd_ids"],
                       "lost_jd_ids": proposal["lost_jd_ids"],
                       "candidate_is_approved": False,
                       "requires_base_review": proposal["requires_base_review"],
                       "source_to_final_bullet_provenance": proposal["projects"],
                       "proposal_scope": ("fixed-project-set-variable-bullet-count-selection" if variable
                                          else "fixed-project-set-global-bullet-selection"),
                       "selection_receipt": proposal.get("selection_receipt") if variable else None,
                       "verification_limits": ["JD coverage is a deterministic proxy",
                           "Factual accuracy is not independently verified",
                           "One-page PDF count is verified; full layout quality needs review"]}
            with open(manifest, "x", encoding="utf-8") as handle:
                json.dump(receipt, handle, indent=2)
            saved.append(manifest)
        except Exception:
            for p in saved:
                p.unlink(missing_ok=True)
            raise
    return {"status": "generated", "docx_path": str(dest_docx),
            "pdf_path": str(dest_pdf), "receipt_path": str(manifest), "pages": 1,
            "proposal": proposal}


def render_v26_optimizer(st: Any, *, application_id: int, audit: dict,
                         projects: dict, fit: dict, repo_root: Path,
                         generation_id: str) -> None:
    st.markdown("**V2.6 — Generate an optimized résumé copy**")
    st.caption("This creates an actual rendered one-page DOCX/PDF candidate. It never overwrites the approved résumé or changes your generation. Source projects and their bullet counts stay fixed in this bounded first implementation; bullets are optimized jointly across the full Projects section.")
    if not audit.get("verified") or str(audit.get("generation_id")) != str(generation_id):
        st.info("Exact verified generation/source audit is required before optimization.")
        return
    if not st.checkbox("Evaluate joint bullet combinations for this application",
                       value=False, key=f"phase9f_v26_evaluate_{application_id}"):
        st.caption("No selection computation or DOCX generation runs until you opt in.")
        return
    proposal = build_joint_optimization(audit, projects)
    if proposal["status"] != "candidate":
        st.info(proposal["reason"])
        return
    a, b, c = st.columns(3)
    a.metric("Current JD coverage proxy", f"{proposal['baseline_points']:.2f}")
    b.metric("Proposed JD coverage proxy", f"{proposal['proposed_points']:.2f}")
    c.metric("Net proxy change", f"+{proposal['proposed_points']-proposal['baseline_points']:.2f}")
    st.caption("Coverage proxy is not the Phase 8 score, factual approval, or proof of the globally best résumé. Candidate uses exact saved bullets only, no LLM rewriting. Must pass actual one-page PDF conversion before it is saved.")
    changed = [x for x in proposal["projects"] if x["before"] != x["after"]]
    for row in changed:
        with st.expander(row["project"] + " — source-to-final changes", expanded=False):
            st.write("**Current final bullets**")
            for bullet in row["before"]:
                st.write("• " + bullet)
            st.write("**Proposed bullets**")
            for bullet, origins, ids in zip(row["after"], row["sources"], row["supported_jd_ids"]):
                st.write("• " + bullet)
                st.caption("Source: " + ", ".join(origins) + "; supported JD IDs: " + (", ".join(ids) or "not established"))
    confirm = st.checkbox("I want to generate a separate, unapproved optimized résumé candidate; the original stays unchanged.",
                          key=f"phase9f_v26_confirm_{application_id}")
    if proposal["requires_base_review"]:
        reviewed = st.checkbox("I have reviewed the Base-only bullets for factual accuracy before using them.",
                              key=f"phase9f_v26_base_review_{application_id}")
    else:
        reviewed = True
    key = f"phase9f_v26_generated_{application_id}_{generation_id}"
    if st.button("Generate real one-page candidate", disabled=not (confirm and reviewed),
                 key=f"phase9f_v26_generate_{application_id}"):
        from tailoring.phase9f_final_evidence_comparison_v2_4 import _docx_path
        path, error = _docx_path(fit, repo_root, application_id)
        if path is None:
            st.error(error)
        else:
            with st.spinner("Creating candidate and verifying its PDF is one page..."):
                try:
                    output = materialize_verified_candidate(source_docx=path, audit_sha=audit["docx_sha256"],
                        proposal=proposal, repo_root=repo_root, application_id=application_id,
                        generation_id=generation_id)
                    st.session_state[key] = output
                except (ValueError, RuntimeError, OSError) as exc:
                    st.error("Optimized candidate not saved: " + str(exc))
    output = st.session_state.get(key)
    if isinstance(output, dict) and output.get("status") == "generated":
        path = Path(output["docx_path"])
        pdf = Path(output["pdf_path"])
        if path.is_file() and pdf.is_file() and output.get("proposal", {}).get("version") == VERSION:
            st.success("Separate verified one-page candidate generated. Existing approved résumé is unchanged.")
            st.download_button("Download optimized DOCX", data=path.read_bytes(),
                               file_name=path.name, mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                               key=f"phase9f_v26_download_{application_id}")
            st.download_button("Download verified PDF", data=pdf.read_bytes(),
                               file_name=pdf.name, mime="application/pdf",
                               key=f"phase9f_v26_pdf_{application_id}")
            st.caption("PDF page count was verified, but readability and factual claims still need review. To undo: keep the existing approved résumé or ignore this unapproved candidate. Git checkpoint and installer --rollback can undo V2.6 code changes.")
            if st.button("Hide candidate from this view (files remain saved)", key=f"phase9f_v26_discard_{application_id}"):
                st.session_state.pop(key, None)
                st.rerun()

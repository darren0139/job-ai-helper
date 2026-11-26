"""V3.12-B1: portfolio-only fitter-boundary evidence-conserving same-work cleanup.

The normal one-page fitter still determines the real document. This helper
makes a bounded, deterministic improvement to the ACTUAL project-bullet input,
not just the Portfolio preview, then reports post-fit wording with provenance.
No invented bullets, scorer changes, model calls or persistence operations.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import re
from typing import Any

VERSION = 'portfolio-quality-v312b1-fit-input-marginal-v1'
MODE = 'portfolio_quality'


def _normal(text: str) -> str:
    return ' '.join(str(text).split())


def _text_key(text: str) -> str:
    return re.sub(r'[^a-z0-9]+', ' ', _normal(text).casefold()).strip()


def _work_family(text: str) -> str:
    """Only concrete, narrowly scoped same-work motifs (NOT broad keywords)."""
    t = _text_key(text)
    if ('github actions' in t and ('frontend' in t and 'backend' in t)
            and ('test' in t or 'tests' in t)
            and ('build' in t or 'builds' in t)):
        return 'ci_frontend_backend_build_tests'
    if ('gameplay mechanics' in t and 'lua' in t and 'engine' in t
            and ('custom' in t or 'c++' in text.casefold())):
        return 'lua_gameplay_mechanics_custom_engine'
    return ''


def _semantic_richness(text: str) -> tuple[int, int, int]:
    t = _text_key(text)
    details = ('github actions', 'trivy', 'prometheus', 'grafana', 'ghcr',
               'docker', 'vulnerabilit', 'monitoring', 'scanning',
               'role based', 'authentication', 'production', 'kubernetes',
               'lua', 'engine', 'gameplay')
    return (sum(s in t for s in details), min(len(t.split()), 42), -len(t))


def _linked(m: dict[str, Any]) -> set[str]:
    return {str(x).strip() for x in m.get('supported_requirement_ids', [])
            if isinstance(x, str) and x.strip()}


def _protected(m: dict[str, Any]) -> set[str]:
    return {str(x).strip() for x in m.get('protected_requirement_ids', [])
            if isinstance(x, str) and x.strip()}


def _guarded_reductions(project: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Remove ONLY genuinely repeated work when all tracked JD links survive.

    Missing/inconsistent alignment is a conservative HOLD: leave the project
    intact, never mutate original data. Distinct CI from testing-only work
    remains separate. Preserve the exact surviving text and source metadata.
    """
    bullets = project.get('draft_bullets')
    if not isinstance(bullets, list) or not bullets or any(not isinstance(b, str) or not b.strip() for b in bullets):
        raise ValueError('Invalid fitter project draft bullets; no B1 rewrite')
    metadata = project.get('bullet_evidence_priorities')
    if metadata is None:
        metadata = []
    if not isinstance(metadata, list):
        raise ValueError('Invalid fitter evidence priorities; no B1 rewrite')
    metas = []
    if metadata:
        if len(metadata) != len(bullets) or any(not isinstance(m, dict) for m in metadata):
            return project, [{'status': 'HOLD_UNALIGNED_METADATA'}]
        if any(_normal(m.get('bullet_text', '')) != _normal(b)
               for m, b in zip(metadata, bullets)):
            return project, [{'status': 'HOLD_UNALIGNED_METADATA'}]
        metas = metadata
    else:
        metas = [{} for _ in bullets]
    compact = project.get('compact_bullets') or []
    if not isinstance(compact, list) or (compact and len(compact) != len(bullets)):
        return project, [{'status': 'HOLD_UNALIGNED_COMPACT'}]
    # Only apply semantic duplicate checks with exact per-bullet metadata.
    families = [_work_family(b) if metadata else '' for b in bullets]
    indexed = {}
    for i, (b, family) in enumerate(zip(bullets, families)):
        # Exact identical text is safe even without other metadata.
        key = ('family', family) if family else ('exact', _text_key(b))
        indexed.setdefault(key, []).append(i)
    removed = set()
    receipts = []
    for key, members in indexed.items():
        if len(members) <= 1:
            continue
        # Never silently delete two distinct activities on a generic keyword.
        if key[0] == 'family' and key[1] not in (
                'ci_frontend_backend_build_tests', 'lua_gameplay_mechanics_custom_engine'):
            continue
        # Keep protected rows and retain strongest exact-source explanatory detail.
        ranked = sorted(members, key=lambda i: (
            bool(_protected(metas[i])), len(_linked(metas[i])),
            _semantic_richness(bullets[i]), -i), reverse=True)
        keep = ranked[0]
        for i in ranked[1:]:
            if _protected(metas[i]):
                receipts.append({'status':'HOLD_PROTECTED_EVIDENCE', 'index':i, 'family':key[1]})
                continue
            # Source-owned JD identities cannot be lost due to word similarity.
            remaining = set().union(*(_linked(m) for j,m in enumerate(metas)
                                      if j not in removed and j != i))
            if _linked(metas[i]) - remaining:
                receipts.append({'status':'HOLD_UNIQUE_JD_LINK', 'index':i, 'family':key[1]})
                continue
            removed.add(i)
            receipts.append({
                'status': 'REMOVED_SAME_WORK', 'family':key[1],
                'removed_index':i, 'kept_index':keep,
                'removed_text_sha256':sha256(_normal(bullets[i]).encode()).hexdigest(),
                'kept_text_sha256':sha256(_normal(bullets[keep]).encode()).hexdigest(),
                'covered_requirement_ids':sorted(_linked(metas[i])),
            })
    if not removed:
        return project, receipts
    chosen = [i for i in range(len(bullets)) if i not in removed]
    if not chosen:
        raise ValueError('B1 would remove all project bullets')
    out = deepcopy(project)
    out['draft_bullets'] = [bullets[i] for i in chosen]
    if compact:
        out['compact_bullets'] = [compact[i] for i in chosen]
    if metadata:
        updated = []
        for idx, old_idx in enumerate(chosen):
            row = deepcopy(metas[old_idx])
            row['bullet_index'] = idx
            row['bullet_text'] = bullets[old_idx]
            updated.append(row)
        out['bullet_evidence_priorities'] = updated
    return out, receipts


def improve_portfolio_fit_input(projects: dict[str, Any] | None, *, mode: str,
                                stage: str) -> dict[str, Any] | None:
    """Fit-time only; caller must be an explicitly selected Portfolio policy.

    Called before the fitted payload is submitted, and again on the final
    prepared payload to cover source-derived lead-bullet reconstruction.
    """
    if mode != MODE:
        return projects
    if not isinstance(projects, dict):
        raise ValueError('B1 requires a validated portfolio projects mapping')
    rows = projects.get('recommended_projects')
    if not isinstance(rows, list) or not rows:
        raise ValueError('B1 requires a nonempty fitted project slate')
    if stage not in ('caller', 'prepared'):
        raise ValueError('Unknown B1 lifecycle stage')
    out = deepcopy(projects)
    processed = []
    all_actions = []
    for i, project in enumerate(rows):
        if not isinstance(project, dict):
            raise ValueError('B1 refuses non-mapping project')
        improved, actions = _guarded_reductions(project)
        processed.append(improved)
        for action in actions:
            all_actions.append({**action,'project_index':i,
                'project_title':str(project.get('display_title') or project.get('title') or '')})
    out['recommended_projects'] = processed
    past = out.get('portfolio_quality_b1_fit_audit')
    stages = deepcopy(past.get('stages')) if isinstance(past, dict) and isinstance(past.get('stages'), list) else []
    stages = [x for x in stages if x.get('stage') != stage]
    stages.append({'stage':stage, 'before_counts':[len(x['draft_bullets']) for x in rows],
                   'after_counts':[len(x['draft_bullets']) for x in processed],
                   'actions':all_actions})
    out['portfolio_quality_b1_fit_audit'] = {
        'version':VERSION, 'mode':MODE, 'status':'fit_input_changed_not_native_verified',
        'stages':stages,
        'no_native_score_claim':True, 'no_document_fit_claim':True,
        'no_content_invented':True,
    }
    out['portfolio_quality_b1_active'] = VERSION
    return out


def audit_fitted_portfolio_docx(fit_result: dict[str, Any]) -> dict[str, Any]:
    """Read back exact fitted Word text, never using the pre-fit proxy as truth.

    This reports *observed* overlaps; it does not approve/score a resume.
    """
    out = {'version':VERSION, 'status':'HOLD_NOT_VERIFIED',
           'is_actual_docx_readback':False, 'native_score_checked':False,
           'required_core_evidence_checked':False, 'editorial_approval':False}
    if not isinstance(fit_result, dict) or not fit_result.get('fit_one_page') or fit_result.get('page_count') != 1:
        out['reason']='not_verified_one_page';return out
    path=Path(str(fit_result.get('docx_path') or ''))
    if not path.is_file():
        out['reason']='fitted_docx_missing';return out
    try:
        from docx import Document
        doc=Document(str(path))
        # B1.8: Generated DOCX templates may use Normal instead of a named
        # "Entry" style. Only a bold, tab-delimited heading matching a saved
        # project title can establish a project in that format. Unknown bold
        # headings HOLD rather than silently assigning later bullets to the
        # preceding project. No reconstruction from bullet similarity.
        saved = fit_result.get('tailored_projects_used')
        saved_rows = saved.get('recommended_projects') if isinstance(saved, dict) else None
        saved_titles = set()
        if isinstance(saved_rows, list):
            for row in saved_rows:
                if not isinstance(row, dict):
                    out['reason']='invalid_saved_project_heading';return out
                label=_normal(row.get('display_title') or row.get('title') or '')
                if not label or label in saved_titles:
                    out['reason']='invalid_saved_project_heading';return out
                saved_titles.add(label)
        in_projects=False
        projects: dict[str, list[str]]={}
        current=None
        for para in doc.paragraphs:
            t=_normal(para.text)
            if t.upper() == 'PROJECTS':
                in_projects=True;continue
            if in_projects and t.upper() == 'SKILLS':break
            if not in_projects or not t:continue
            style=(para.style.name or '').lower()
            # Normal-style project headers contain an explicitly bold title,
            # followed by a tab and a date. The title must be source-owned.
            visual_header=(bool(saved_titles) and '\t' in para.text
                           and bool(para.runs) and para.runs[0].bold is True)
            if ('entry' in style and 'subentry' not in style) or visual_header:
                name=_normal(para.text.split('\t',1)[0])
                if saved_titles and name not in saved_titles:
                    out['reason']='unexpected_project_heading';return out
                if name in projects:
                    out['reason']='duplicate_project_heading';return out
                projects[name]=[];current=name
                continue
            if ('bullet' in style or
                (para._p.pPr is not None and para._p.pPr.numPr is not None) or
                bool(re.match(r'^[•●▪◦‣]\s*',t))):
                if current is None:
                    out['reason']='unassigned_project_bullet';return out
                projects[current].append(re.sub(r'^[•●▪◦‣]\s*','',t))
        if not projects or not any(projects.values()):
            out['reason']='project_bullets_unreadable';return out
        actual=[b for rows in projects.values() for b in rows]
        expected=fit_result.get('tailored_projects_used')
        expect_rows=expected.get('recommended_projects') if isinstance(expected,dict) else None
        exact_expected=False
        if isinstance(expect_rows,list) and expect_rows:
            expect_map={str(x.get('display_title') or x.get('title') or ''):
                        [_normal(b) for b in x.get('draft_bullets',[])]
                        for x in expect_rows if isinstance(x,dict)}
            exact_expected=(expect_map==projects)
        overlapping={}
        for title,bullets in projects.items():
            families=Counter(x for x in map(_work_family,bullets) if x)
            duplicates={k:v for k,v in families.items() if v>1}
            if duplicates:overlapping[title]=duplicates
        out.update({'status':'DOCX_READBACK_EDITORIAL_REVIEW' if exact_expected else 'HOLD_DOCX_READBACK_MISMATCH',
            'is_actual_docx_readback':True, 'docx_sha256':sha256(path.read_bytes()).hexdigest(),
            'project_bullet_count':len(actual), 'project_count':len(projects),
            'one_bullet_projects':sum(len(x)==1 for x in projects.values()),
            'project_bullet_counts':{k:len(v) for k,v in projects.items()},
            'same_work_groups_remaining_by_project':overlapping,
            'exact_saved_fitted_bullets_match_docx':exact_expected,
            'one_page_verified_from_fit_receipt':True, 'no_native_score_claim':True})
    except Exception as exc:
        out['reason']='document_readback_failed:'+type(exc).__name__
    return out

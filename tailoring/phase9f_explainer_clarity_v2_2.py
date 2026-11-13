"""Read-only clarity for Phase 9F project selection and Phase 8 comparison.

All decisions come from recorded selection/fit receipts. No scoring or writes.
"""
from __future__ import annotations
from collections import Counter
from typing import Any


def _txt(value: Any) -> str:
    return " ".join(str(value or "").split())


def _pid(row: dict[str, Any]) -> str:
    return _txt(row.get('project_id')) or 'title:' + _txt(row.get('display_title') or row.get('title')).casefold()


def _title(row: dict[str, Any]) -> str:
    return _txt(row.get('display_title') or row.get('title'))


def project_selection_summary(projects: dict[str, Any] | None) -> dict[str, Any]:
    """Explain selection identity and saved low-confidence fallbacks, without invented JD matches."""
    if not isinstance(projects, dict):
        return {'rows': [], 'notice': 'No saved project selection.'}
    ranked = projects.get('candidate_project_ranking')
    generated = projects.get('recommended_projects')
    if (not isinstance(ranked, list) or not isinstance(generated, list)
        or not all(isinstance(p, dict) for p in ranked + generated)):
        return {'rows': [], 'notice': 'Saved ranking or generated-project pool unavailable.'}
    selected = [_pid(p) for p in generated]
    if not all(selected) or len(selected) != len(set(selected)):
        return {'rows': [], 'notice': 'Generated project identities are missing or ambiguous.'}
    low = projects.get('low_confidence_selection') or {}
    fallback_ids = set(low.get('default_low_confidence_project_ids') or [])
    fallback_rows = { _txt(p.get('project_id')):p for p in low.get('eligible_low_confidence_candidates') or [] if isinstance(p,dict) }
    # A manual/application-local override may replace the deterministic defaults.
    final_selection = (low.get('final_selection') or {}).get('project_ids')
    if isinstance(final_selection,list) and final_selection:
        fallback_ids &= set(final_selection)
    seen = set()
    rows = []
    for p in ranked:
        pid=_pid(p)
        if not pid or pid in seen:
            return {'rows': [], 'notice': 'Saved ranking has duplicate or missing identities.'}
        seen.add(pid)
        selected_here=pid in selected
        matches=[m for m in p.get('requirement_matches') or [] if isinstance(m,dict) and _txt(m.get('match_label')) in {'direct','transferable','weak'}]
        matched=[_txt(m.get('requirement_text')) for m in matches if _txt(m.get('requirement_text'))]
        fallback = _txt(p.get('project_id')) in fallback_ids
        if fallback and selected_here and matched:
            # A fallback cannot simultaneously be characterized as proven JD coverage.
            return {'rows': [], 'notice': 'Saved fallback and JD evidence identities disagree.'}
        if selected_here and fallback:
            selection = 'Evidence-quality fallback (no proven JD coverage)'
            reasons = fallback_rows.get(_txt(p.get('project_id')),{}).get('fallback_reasons') or []
            why = '; '.join(_txt(s) for s in reasons[:2]) or 'Saved fallback suitability only'
        elif selected_here and matched:
            selection = 'Supported JD coverage'
            why = f"{len(matched)} saved JD requirement match(es)"
        elif selected_here:
            selection = 'Selected; JD basis unproven'
            why = 'No grounded requirement link available in saved ranking'
        else:
            selection = 'Not generated'
            why = 'Not in saved generated-project set'
        rows.append({
            'Rank': p.get('selection_rank'), 'Project': _title(p),
            'Selected': 'Yes' if selected_here else 'No',
            'Selection basis': selection,
            'Ranking score': p.get('selection_score'),
            'Matched JD requirement': matched[0] if matched else 'None proven',
            'Why chosen': why,
        })
    if set(selected)-seen:
        return {'rows': [], 'notice': 'Generated projects not represented in saved candidate ranking.'}
    return {
        'rows': rows,
        'notice': f"{sum(bool(r['Selected']=='Yes') for r in rows)} selected; "
                  f"{sum(r['Selected']=='Yes' and r['Selection basis']=='Supported JD coverage' for r in rows)} with saved JD evidence; "
                  f"{sum(r['Selected']=='Yes' and r['Selection basis'].startswith('Evidence-quality fallback') for r in rows)} explicit fallback(s).",
        'selection_source': _txt(low.get('selection_source')) or 'Not recorded',
    }


def fit_stage_summary(projects: dict[str, Any] | None, fit_result: dict[str, Any] | None) -> dict[str, Any]:
    """Reconstruct fitted bullet COUNTS from the final active reduction receipt.

    Never treat tailored_projects_used as final: it is the fitter's caller input.
    Unknown reductions, ambiguous names or unverified fitting withhold a claim.
    """
    if not isinstance(projects, dict) or not isinstance(fit_result, dict):
        return {'rows': [], 'notice': 'No saved one-page fitting result yet.'}
    if fit_result.get('fit_one_page') is not True or int(fit_result.get('page_count') or 0)!=1 or not _txt(fit_result.get('docx_path')):
        return {'rows': [], 'notice': 'No verified one-page fitting receipt.'}
    generated=projects.get('recommended_projects')
    snapshot=fit_result.get('fitting_input_snapshot') or {}
    initial=((snapshot.get('prepared_initial_state') or {}).get('projects') or {}).get('recommended_projects')
    reductions=fit_result.get('remaining_active_reductions')
    if not (isinstance(generated,list) and isinstance(initial,list) and isinstance(reductions,list)
            and all(isinstance(p,dict) for p in generated+initial)
            and all(isinstance(r,dict) for r in reductions)):
        return {'rows': [], 'notice': 'Exact starting pool or active fitting reduction receipt not saved.'}
    # Track full project IDs from the saved fitter input; reduction events own only title strings.
    starts={}
    byname={}
    for p in initial:
        name=_title(p)
        if not name or name in starts:
            return {'rows': [], 'notice': 'Fitter starting projects have ambiguous titles.'}
        starts[name]=p;byname[name]=name
    generated_ids={_title(p):p for p in generated}
    if (not all(generated_ids) or len(generated_ids)!=len(generated)
            or set(generated_ids)!=set(starts)):
        return {'rows': [], 'notice': 'Generated titles do not uniquely match saved fitter starting pool.'}
    for name, initial_project in starts.items():
        before_id=_txt(generated_ids[name].get('project_id'))
        fit_id=_txt(initial_project.get('project_id'))
        if before_id and fit_id and before_id!=fit_id:
            return {'rows': [], 'notice': 'Fitter project ID conflicts with the generated project ID.'}
    changes={key:Counter() for key in starts}
    for row in reductions:
        name=_txt(row.get('project'))
        kind=_txt(row.get('change_type'))
        section=_txt(row.get('section')).casefold()
        if section in {'skills', 'layout', 'education', 'experience'} or kind in {'reduce_skill', 'remove_skill'}:
            continue
        key=byname.get(name)
        if not key or kind not in {'remove_bullet','compact_rewrite','remove_project','shorten','compact'}:
            return {'rows': [], 'notice': 'An active fitter project reduction cannot be attributed safely to a saved project.'}
        changes[key][kind]+=1
    out=[]
    for p in generated:
        key=_title(p)
        start=starts[key]
        raw=start.get('draft_bullets')
        draft=p.get('draft_bullets')
        if not isinstance(raw,list) or not isinstance(draft,list):
            return {'rows': [], 'notice': 'Saved bullet lists missing for a project.'}
        original=len(raw)
        removed=changes[key]['remove_bullet']
        removed_project=changes[key]['remove_project']
        if removed_project>1 or removed>original or (removed_project and removed):
            return {'rows': [], 'notice': 'Conflicting active reduction history; final counts withheld.'}
        final_count=0 if removed_project else original-removed
        selection='Fallback — no JD coverage' if _txt(p.get('project_id')) in set((projects.get('low_confidence_selection') or {}).get('default_low_confidence_project_ids') or []) else 'JD evidence / saved rank'
        out.append({
            'Project': _title(p),
            'Selection basis': selection,
            'Generated draft bullets': len(draft),
            'Fitter starting bullets': original,
            'Bullets removed': removed,
            'Bullets after active reductions': final_count,
            'Fitted project': 'No' if removed_project else 'Yes',
            'Fitting changes': (' · '.join(filter(None, [f'{removed} bullet(s) removed' if removed else '', f"{changes[key]['compact_rewrite']} compacting action(s)" if changes[key]['compact_rewrite'] else ''])) or 'No active reduction'),
        })
    return {
        'rows': out,
        'notice': 'Final counts reconstructed from the saved fitter starting snapshot and final ACTIVE reductions. '
                  'This is not an independent visual DOCX extraction. The source-generated draft and fitter starting pool can differ.'
    }


def compact_snapshot_rows(snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Small legible summary; keep full scorer diagnostics in the existing UI."""
    out=[]
    for row in (snapshot or {}).get('requirements') or []:
        if isinstance(row,dict):
            out.append({'JD requirement': _txt(row.get('requirement_text')),
                        'Priority': _txt(row.get('importance')),
                        'Match': _txt(row.get('final_match') or row.get('match_label')),
                        'Evidence': _txt(row.get('evidence_provenance') or '')[:140] if isinstance(row.get('evidence_provenance'),str) else ('Present' if row.get('evidence_provenance') else 'None')})
    return out


def compact_comparison_rows(full_rows: list[dict[str, Any]], baseline: str) -> list[dict[str, Any]]:
    """Readable, named side-by-side match labels; leave full receipts untouched."""
    output=[]
    for row in full_rows:
        transition=_txt(row.get('Match transition'))
        if '→' in transition:
            left,right=transition.split('→',1)
        elif '->' in transition:
            left,right=transition.split('->',1)
        else:
            left,right=transition,''
        output.append({
            'JD requirement': _txt(row.get('Requirement')),
            'Priority': _txt(row.get('Importance')),
            baseline+' match': left.strip(),
            'Tailored match': right.strip() if right else 'Unavailable',
            'Outcome': _txt(row.get('Classification')).replace('_',' ').title(),
            'Points Δ': row.get('Contribution Δ'),
        })
    return output

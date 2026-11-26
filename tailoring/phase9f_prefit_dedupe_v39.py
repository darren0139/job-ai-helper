"""V3.9 automatic, auditable same-work deduplication BEFORE the actual DOCX fit.

Applies to fresh fits, never edits historical files.  This is a wording-selection
policy (not a native score verdict); the ordinary fitter and Phase 8 subsequently
score the actual saved DOCX.  Source provenance is required for non-identical
wordings.  Do not silently claim unmeasured JD requirements are retained.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from typing import Any
import re

VERSION = 'phase9f-v39-pre-fit-dedupe-v1'


def _key(value: Any) -> str:
    return ' '.join(str(value or '').split()).casefold()


def _source_name(tags: Any) -> list[str]:
    out = set()
    for tag in tags if isinstance(tags, (list, tuple, set)) else []:
        label = _key(tag)
        if label in ('base', 'selected base', 'base resume', 'resume'):
            out.add('Base Resume')
        if label in ('library', 'evidence library', 'evidence_library'):
            out.add('Evidence Library')
    return sorted(out)


def _metadata(project: dict[str, Any], bullets: list[str]) -> list[dict[str, Any]]:
    choices = {}
    for item in project.get('bullet_decision_receipts') or []:
        if isinstance(item, dict) and item.get('bullet'):
            choices.setdefault(_key(item['bullet']), set()).update(_source_name(item.get('sources')))
    originals = project.get('selected_blueprint_bullets') or []
    labels = project.get('selected_bullet_sources') or []
    if isinstance(originals, list) and isinstance(labels, list) and len(originals) == len(labels):
        for text, sources in zip(originals, labels):
            choices.setdefault(_key(text), set()).update(_source_name(sources))
    scores = {}
    for item in project.get('bullet_evidence_priorities') or []:
        if not isinstance(item, dict) or not item.get('bullet_text'):
            continue
        key = _key(item['bullet_text'])
        if key in scores: continue
        try:
            points = float(item.get('evidence_value') or 0.0)
            if not (-1e9 < points < 1e9): points = 0.0
        except (TypeError, ValueError, OverflowError):
            points = 0.0
        scores[key] = {
            'saved_evidence_points': round(max(0.0, points), 6),
            'unique_required_core_count': max(0, int(item.get('unique_required_core_count') or 0)),
            'supported_requirement_count': len(item.get('supported_requirement_ids') or []),
            'protected': bool(item.get('protect_during_fitting')),
        }
    rows = []
    for index, text in enumerate(bullets):
        key = _key(text)
        rows.append({'index': index, 'text': text, 'sources': sorted(choices.get(key, ())),
                     **scores.get(key, {'saved_evidence_points': None,
                                         'unique_required_core_count': 0,
                                         'supported_requirement_count': 0,
                                         'protected': False})})
    return rows


def _rank(row: dict[str, Any]) -> tuple:
    # Strong protected native/fitter evidence is preferred; only *recorded*
    # JD-related points take part.  Library is a stable tie break, NOT a score.
    return (int(row['protected']), row['unique_required_core_count'],
            float(row['saved_evidence_points'] or 0.0), row['supported_requirement_count'],
            int('Evidence Library' in row['sources']), -row['index'])


def _same_work(a: dict, b: dict) -> tuple[bool, str]:
    if _key(a['text']) == _key(b['text']):
        return True, 'same_wording'
    sa, sb = set(a['sources']), set(b['sources'])
    # Do not pair unrelated arbitrary bullets. Non-identical work must have
    # verified cross-source origin, within the SAME project.
    if not (('Base Resume' in sa and 'Evidence Library' in sb) or
            ('Evidence Library' in sa and 'Base Resume' in sb)):
        return False, 'no_cross_source_pair'
    from tailoring.phase9f_bullet_redundancy import compare_project_bullets
    result = compare_project_bullets(a['text'], b['text'], same_project=True)
    return result.get('status') == 'likely_same_work', str(result.get('status') or 'unavailable')


def dedupe_prepared_projects(payload: dict[str, Any], *, enabled: bool = True) -> dict[str, Any]:
    """Copy and remove confidently overlapping *prepared* draft bullets.

    This runs in prepare_fitting_input_snapshot, before the fitter freezes its
    prepared-state hash. Only the copied prepared payload changes. This policy
    intentionally does NOT require a projected native increase; native Phase 8
    measures the actual resulting DOCX later. Removed/kept facts are logged.
    """
    if not isinstance(payload, dict):
        return payload
    out = deepcopy(payload)
    projects = out.get('recommended_projects')
    receipt = {'version': VERSION, 'status': 'not_applicable',
               'policy': 'automatic_cross_source_same_work_before_fit',
               'note': ('Saved JD evidence points rank wording candidates. They are not native '
                        'Job Match points; Phase 8 must score the actual fitted document.'),
               'removals': [], 'project_scores': []}
    if not enabled:
        receipt['status'] = 'projects_locked'
    elif not isinstance(projects, list):
        receipt['status'] = 'no_project_list'
    else:
        receipt['status'] = 'checked_no_duplicates'
        for project in projects:
            if not isinstance(project, dict):
                continue
            title = str(project.get('display_title') or project.get('title') or 'Project').strip()
            bullets = project.get('draft_bullets')
            if not isinstance(bullets, list) or not all(isinstance(b, str) and b.strip() for b in bullets):
                receipt['project_scores'].append({'project': title, 'status': 'invalid_draft_bullets'})
                continue
            rows = _metadata(project, bullets)
            keep = set(range(len(rows)))
            for a in range(len(rows)):
                for b in range(a + 1, len(rows)):
                    if a not in keep or b not in keep:
                        continue
                    conflict, reason = _same_work(rows[a], rows[b])
                    if not conflict:
                        continue
                    retained, removed = (a, b) if _rank(rows[a]) >= _rank(rows[b]) else (b, a)
                    keep.remove(removed)
                    kept, gone = rows[retained], rows[removed]
                    explanation = ('Greater recorded JD evidence / protection rank' if
                                   _rank(kept)[:4] != _rank(gone)[:4]
                                   else 'Equal recorded JD evidence; deterministic source/order tie break')
                    receipt['removals'].append({
                        'project': title, 'removed': gone['text'], 'retained': kept['text'],
                        'removed_sources': gone['sources'], 'retained_sources': kept['sources'],
                        'removed_saved_evidence_points': gone['saved_evidence_points'],
                        'retained_saved_evidence_points': kept['saved_evidence_points'],
                        'match_reason': reason, 'selection_reason': explanation,
                        'recorded_at_stage': 'pre_fitting',
                    })
            survivors = [rows[i] for i in range(len(rows)) if i in keep]
            if len(survivors) != len(rows):
                project['draft_bullets'] = [row['text'] for row in survivors]
                compact = project.get('compact_bullets')
                if isinstance(compact, list) and len(compact) == len(rows):
                    project['compact_bullets'] = [compact[i] for i in range(len(rows)) if i in keep]
                else:
                    # Avoid stale compact candidates referring to removed work.
                    project['compact_bullets'] = []
            receipt['project_scores'].append({
                'project': title, 'status': 'checked', 'prepared_bullet_count': len(survivors),
                'bullets': [{'text': row['text'],
                             'saved_evidence_points': row['saved_evidence_points'],
                             'source': row['sources']} for row in survivors]
            })
        if receipt['removals']:
            receipt['status'] = 'removed_before_fit'
    out['_v39_auto_dedupe'] = receipt
    return out


def verify_saved_fit_removals(fit: dict[str, Any], *, repo_root: Path,
                               application_id: int) -> dict[str, Any]:
    """Verify readback of exact saved DOCX; never infer success from proposal."""
    receipt = fit.get('v39_auto_dedupe') if isinstance(fit, dict) else None
    if not isinstance(receipt, dict) or receipt.get('version') != VERSION:
        return {'status': 'unavailable', 'reason': 'No V3.9 pre-fit receipt'}
    if fit.get('fit_one_page') is not True:
        return {'status': 'unverified', 'reason': 'Fitted one-page receipt is missing', 'receipt': receipt}
    from tailoring.phase9f_final_evidence_comparison_v2_4 import _docx_path, _read_exact_docx_bullets
    path, reason = _docx_path(fit, Path(repo_root), int(application_id))
    if path is None:
        return {'status': 'unverified', 'reason': reason, 'receipt': receipt}
    names = [p['project'] for p in receipt.get('project_scores') or [] if p.get('status') == 'checked']
    if not names:
        return {'status': 'verified_no_project_scores', 'receipt': receipt, 'docx_sha256': sha256(path.read_bytes()).hexdigest()}
    actual, reason = _read_exact_docx_bullets(path, names)
    if reason:
        return {'status': 'unverified', 'reason': reason, 'receipt': receipt}
    keys = {name: {_key(b) for b in bullets} for name, bullets in actual.items()}
    checked = []
    for item in receipt.get('removals') or []:
        project = item['project']
        removed_absent = _key(item['removed']) not in keys.get(project, set())
        retained_present = _key(item['retained']) in keys.get(project, set())
        checked.append({**item, 'removed_absent_from_docx': removed_absent,
                        'retained_present_in_docx': retained_present,
                        'verified': removed_absent and retained_present})
    return {'status': 'verified' if all(row['verified'] for row in checked) else 'partial',
            'removals': checked, 'receipt': receipt,
            'docx_sha256': sha256(path.read_bytes()).hexdigest(),
            'actual_project_bullets': actual}


def render_v39_dedupe_receipt(st: Any, *, fit_result: Any, repo_root: Path,
                               application_id: int) -> None:
    """Read-only status beside the real fitted DOCX; no approval or DB changes."""
    if not isinstance(fit_result, dict) or not isinstance(fit_result.get('v39_auto_dedupe'), dict):
        return
    receipt = fit_result['v39_auto_dedupe']
    with st.expander('Automatic deduplication — actual fitted résumé', expanded=False):
        result = verify_saved_fit_removals(fit_result, repo_root=repo_root,
                                           application_id=application_id)
        if result['status'] == 'unverified':
            st.warning('Deduplication document verification unavailable: ' + result.get('reason', ''))
        elif result['status'] == 'partial':
            st.warning('A pre-fit removal occurred, but the retained wording was not confirmed in the actual DOCX.')
        elif result['status'] == 'verified':
            st.success(str(len(result['removals'])) + ' pre-fit duplicate(s) removed and verified in the actual DOCX.')
        else:
            st.caption('No qualifying same-work bullets were removed in this fit.')
        if receipt.get('status') == 'projects_locked':
            st.info('Projects were locked; automatic deduplication was skipped.')
        for row in result.get('removals') or receipt.get('removals') or []:
            st.write('**Project:** ' + row['project'])
            st.write('Removed: ' + row['removed'])
            st.write('Kept: ' + row['retained'])
            st.caption('Saved JD evidence points · removed ' + str(row.get('removed_saved_evidence_points')) +
                       ' · kept ' + str(row.get('retained_saved_evidence_points')) +
                       '. ' + row['selection_reason'])
        if result.get('actual_project_bullets'):
            for project, bullets in result['actual_project_bullets'].items():
                st.write('**Final DOCX · ' + project + '**')
                scores = { _key(item['text']): item['saved_evidence_points']
                           for info in receipt.get('project_scores') or []
                           if info.get('project') == project
                           for item in info.get('bullets') or [] }
                for text in bullets:
                    points = scores.get(_key(text))
                    st.caption('JD evidence points: ' + (str(points) if points is not None else 'unavailable') + ' · ' + text)
        st.caption('Scores are saved bullet evidence points, not native per-bullet Job Match. '
                   'The normal Phase 8 result scores this exact final DOCX.')

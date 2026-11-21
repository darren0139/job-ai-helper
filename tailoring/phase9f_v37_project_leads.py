"""Research-only project introductions bound to frozen source wording."""
from __future__ import annotations

from hashlib import sha256

SOURCES = {'base': 'Selected Base', 'library': 'Evidence Library'}


def wording_digest(wording: str) -> str:
    return sha256(wording.encode('utf-8')).hexdigest()


def bind_project_leads(audit: dict, review: dict, permitted: set[str]) -> dict:
    """Choose the first eligible reviewed lead, with canonical wording first."""
    if not audit.get('verified') or review.get('source_docx_sha256') != audit.get('docx_sha256'):
        raise ValueError('Lead review is not bound to the audited fitted document.')
    if not permitted or not permitted <= SOURCES.keys():
        raise ValueError('Lead selection needs eligible Base or Library sources.')
    leads, missing = {}, []
    for section in audit['projects']:
        name = section['project']
        decisions = review['projects'].get(name) or []
        if not decisions:
            missing.append({'project': name, 'reason': 'lead_review_missing'})
            continue
        candidates = []
        for index, attestation in enumerate(decisions):
            source, position = attestation['source'], attestation['position']
            if source not in SOURCES or type(position) is not int or not 1 <= position <= len(section[source]):
                raise ValueError(f'Invalid reviewed source position for {name}.')
            wording = section[source][position - 1]['text']
            if wording_digest(wording) != attestation['sha256'] or not attestation.get('basis'):
                raise ValueError(f'Reviewed lead wording or basis is missing or stale for {name}.')
            owners = [tag for tag in SOURCES if any(row['text'] == wording for row in section[tag])]
            if permitted.intersection(owners):
                candidates.append({'wording': wording, 'sources': owners,
                                   'eligible_sources': sorted(permitted.intersection(owners)),
                                   'role': 'canonical' if index == 0 else 'reviewed_equivalent',
                                   'review_basis': attestation['basis'], 'sha256': attestation['sha256']})
        if candidates:
            leads[name] = {**candidates[0], 'reviewed_alternatives': candidates[1:]}
        else:
            missing.append({'project': name, 'reason': 'missing_source_eligible_lead'})
    return {'status': 'structurally_infeasible' if missing else 'ready', 'leads': leads, 'missing': missing}


def lead_first(project: str, bullets: list[str], leads: dict) -> list[str]:
    opening = leads[project]['wording']
    if bullets.count(opening) != 1:
        raise ValueError(f'{project} must contain exactly one copy of its reviewed introduction.')
    return [opening, *(wording for wording in bullets if wording != opening)]


def validate_fitted_order(projects: list[dict], leads: dict) -> None:
    titles = [row['project'] for row in projects]
    if len(titles) != len(leads) or set(titles) != leads.keys():
        raise ValueError('Fitting did not retain the exact reviewed project set.')
    for row in projects:
        project, bullets = row['project'], row['after']
        if lead_first(project, bullets, leads) != bullets:
            raise ValueError(f'{project} does not open with its reviewed introduction.')


def evaluate_lead_document(case: dict, proposal: dict, leads: dict, *, work_root=None,
                           renderer=None, scorer=None) -> dict:
    from docx import Document

    from tailoring.phase9f_joint_resume_optimizer_v2_6 import _bullet_locations, _render_pdf
    from tailoring.phase9f_v37_document_trial import evaluate_document_trial

    projects = proposal['projects']
    validate_fitted_order(projects, leads)
    render = renderer or _render_pdf
    actual_projects = []

    def checked_render(docx_path, folder):
        locations = _bullet_locations(Document(docx_path), [
            {'project': row['project'], 'before': row['after']} for row in projects
        ])
        actual_projects.extend({
            'project': row['project'],
            'after': [' '.join(p.text.lstrip('•●▪‣·- \t').split()) for p in paragraphs],
        } for row, paragraphs in zip(projects, locations, strict=True))
        validate_fitted_order(actual_projects, leads)
        return render(docx_path, folder)

    options = {'scorer': scorer} if scorer is not None else {}
    result = evaluate_document_trial(case, proposal, work_root=work_root, renderer=checked_render, **options)
    return {**result, 'docx_leads_verified': bool(actual_projects) and result['pages'] == 1,
            'docx_project_order': actual_projects}


def audit_saved_order(projects: list[dict], leads: dict, *, field: str = 'after') -> list[dict]:
    """Describe historical document order without reordering it."""
    rows = []
    for project in projects:
        name, bullets = project['project'], project[field]
        lead = leads.get(name) or {}
        wording = lead.get('wording')
        placement = bullets.index(wording) + 1 if wording in bullets else None
        equivalent = next((alt['wording'] for alt in lead.get('reviewed_alternatives', [])
                           if alt['wording'] in bullets), None)
        if placement is None and equivalent is not None:
            placement = bullets.index(equivalent) + 1
        rows.append({'project': name, 'first_bullet': bullets[0] if bullets else None,
                     'reviewed_lead': wording, 'lead_position': placement,
                     'equivalent_present': equivalent,
                     'status': 'first' if placement == 1 else 'out_of_order' if placement else 'missing'})
    return rows

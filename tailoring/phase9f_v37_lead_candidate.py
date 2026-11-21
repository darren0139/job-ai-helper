"""Explicit preview adapter for the existing certified candidate pipeline."""
from __future__ import annotations

from tailoring.phase9f_auto_optimize_v31 import build_flexible_optimization
from tailoring.phase9f_certified_selection_v36 import (
    SOLVER_LIMIT_SECONDS, V35_VERSION, _candidate, _matrix_program, _solve,
)
from tailoring.phase9f_v37_project_leads import SOURCES, bind_project_leads, lead_first, validate_fitted_order

VERSION = 'phase9f-v37-reviewed-lead-candidate-v1'


def build_lead_guarded_candidate(audit: dict, projects: dict, *, lead_review: dict, evaluator=None) -> dict:
    """Preview one candidate with hard lead constraints and existing V3.6 limits.

    This entry point requires a reviewed artifact and is separate from the
    automatic selector. The ordinary native/scorer/approval checks still apply.
    """
    def withheld(reason: str) -> dict:
        return {'status': 'withheld', 'version': V35_VERSION, 'lead_policy_version': VERSION,
                'reason': reason}

    try:
        bound = bind_project_leads(audit, lead_review, set(SOURCES))
        if bound['missing']:
            return {**withheld('A retained project lacks a reviewed eligible lead.'), 'missing': bound['missing']}
        source = build_flexible_optimization(audit, projects, evaluator=evaluator)
        if source.get('status') == 'withheld' or not source.get('source_comparison'):
            return withheld(source.get('reason') or 'The verified candidate pool is unavailable.')
        model = _matrix_program(audit, source, projects)
        leads = bound['leads']
        index_by_wording = {
            (row['project'], row['text']): index for index, row in enumerate(model['bullets'])
            if set(row['source_labels']).intersection(SOURCES.values())
        }
        forced = {index_by_wording[(name, lead['wording'])]: 1 for name, lead in leads.items()}
        solution = _solve(model, [], time_limit=SOLVER_LIMIT_SECONDS, forced=forced)
        if solution.get('status') != 'optimal_proxy':
            return withheld(solution.get('reason') or 'The reviewed leads do not fit the existing selection limits.')
        proposal = _candidate(model, source, solution, 1)
        for row in proposal['projects']:
            after = lead_first(row['project'], row['after'], leads)
            positions = [row['after'].index(wording) for wording in after]
            for field in ('after', 'sources', 'supported_jd_ids'):
                row[field] = [row[field][i] for i in positions]
        validate_fitted_order(proposal['projects'], leads)
        if all(row['before'] == row['after'] for row in proposal['projects']):
            return {**withheld('The current fitted slate already has the selected lead order.'), 'status': 'no_proxy_gain'}
        proposal['lead_contract'] = {'version': VERSION, 'source_docx_sha256': audit['docx_sha256'],
                                     'leads': leads}
        return proposal
    except (KeyError, TypeError, ValueError, OverflowError, RuntimeError) as error:
        return withheld(str(error))

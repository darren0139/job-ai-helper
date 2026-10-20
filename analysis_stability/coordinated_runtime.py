"""Request-local gate plumbing. No environment variable or global activation."""
from contextvars import ContextVar

CONTEXT = ContextVar('coordinated_action_evaluation', default=None)


def preserves_parent(text):
    if CONTEXT.get() is None:
        return False
    from .coordinated_ownership import extract_obligation
    obligation = extract_obligation({'source_provenance': [{
        'raw_parent_text': text, 'parent_occurrence_id': 'parser_probe',
        'grounding': {'kind': 'parser_probe'},
    }]})
    return obligation['status'] == 'SUPPORTED' and obligation['conjunction'] == 'AND'


def source_allowed(requirement, record):
    state = CONTEXT.get()
    if state is None or state.get('filter') is None:
        return True
    return state['filter'](requirement, record)


def review_pending(rows):
    return any(row.get('coordinated_action_receipt', {}).get('disposition') == 'REVIEW_REQUIRED'
               or (row.get('coordinated_action_receipt') and row.get('match_value') is None)
               for row in rows)


def is_development_preview(analysis):
    return bool(analysis.get('development_preview_only')
            or analysis.get('scoring_version') in (
                'stable-evidence-v1.18-phase6d22', 'stable-evidence-v1.19-phase6d23',
                'stable-evidence-v1.20-phase6d24', 'stable-evidence-v1.21-phase6d25')
            or analysis.get('preview_namespace')
            or analysis.get('score_publication_status') == 'WITHHELD_PENDING_POLICY_REVIEW'
            or review_pending(analysis.get('canonical_requirements', [])))


def assert_analysis_publishable(analysis):
    """Reject development payloads before opening a DB or publishing a score."""
    if is_development_preview(analysis):
        raise ValueError('Coordinated-action development preview cannot be persisted or published')

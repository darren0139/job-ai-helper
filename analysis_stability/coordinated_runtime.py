"""Request-local gate plumbing. No environment variable or global activation."""
from contextvars import ContextVar
from contextlib import contextmanager

CONTEXT = ContextVar('coordinated_action_evaluation', default=None)
# Explicit Phase 3A experiment only. Never inferred from the production gate.
ELIGIBLE_WEAK_FALLBACK = ContextVar('eligible_single_record_weak_fallback', default=False)
ELIGIBLE_WEAK_SCORER = 'stable-evidence-v1.25-phase6d29'
ELIGIBLE_WEAK_POLICY = 'eligible-single-record-weak-fallback-v1'
APPROVED_ALIAS_SURFACE = ContextVar('approved_alias_surface_preview', default=None)
APPROVED_ALIAS_SCORER = 'stable-evidence-v1.26-phase6d30'
APPROVED_ALIAS_POLICY = 'approved-registry-alias-punctuation-v1'


@contextmanager
def approved_alias_surface_preview():
    """Explicit offline/developer invocation; approved registry bytes only.

    No new alias, taxonomy entry, list semantics or evidence credit is supplied.
    Compile once per request and restore the context even on failure.
    """
    import re
    import hashlib
    import json
    from taxonomy_discovery.technology_registry import get_default_registry
    registry = get_default_registry()
    aliases = sorted({a for entry in registry.entries for a in entry['aliases'] if '.' in a},
                     key=lambda a: (-len(a), a))
    pattern = re.compile(r'(?<![\w+#.])(?:'+'|'.join(re.escape(a) for a in aliases)+r')(?![\w+#]|\.[\w+#])', re.I) if aliases else re.compile(r'(?!)')
    knowledge = hashlib.sha256(json.dumps(registry.entries,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    token = APPROVED_ALIAS_SURFACE.set({'pattern': pattern, 'registry_version': registry.version,
                                      'knowledge_fingerprint':knowledge})
    try:
        yield
    finally:
        APPROVED_ALIAS_SURFACE.reset(token)


def stamp_eligible_weak_preview(analysis):
    """Never let a request-local experiment escape with a published identity."""
    if not ELIGIBLE_WEAK_FALLBACK.get() and APPROVED_ALIAS_SURFACE.get() is None:
        return analysis
    import hashlib
    import json
    if APPROVED_ALIAS_SURFACE.get() is not None:
        analysis.update(base_scoring_version=analysis['scoring_version'],
                        scoring_version=APPROVED_ALIAS_SCORER,
                        approved_alias_surface_policy_version=APPROVED_ALIAS_POLICY,
                        development_preview_only=True,
                        preview_namespace='developer-approved-alias-surface-v1',
                        eligible_weak_fallback_enabled=ELIGIBLE_WEAK_FALLBACK.get())
        analysis['input_fingerprint'] = hashlib.sha256(json.dumps({
            'base': analysis['input_fingerprint'], 'policy': APPROVED_ALIAS_POLICY,
            'version': APPROVED_ALIAS_SCORER, 'eligible_weak_fallback': ELIGIBLE_WEAK_FALLBACK.get(),
            'approved_registry':APPROVED_ALIAS_SURFACE.get()['knowledge_fingerprint'],
        }, sort_keys=True).encode()).hexdigest()
        return analysis
    analysis.update(base_scoring_version=analysis['scoring_version'],
                    scoring_version=ELIGIBLE_WEAK_SCORER,
                    eligible_weak_fallback_policy_version=ELIGIBLE_WEAK_POLICY,
                    development_preview_only=True,
                    preview_namespace='developer-eligible-weak-fallback-v1')
    analysis['input_fingerprint'] = hashlib.sha256(json.dumps({
        'base': analysis['input_fingerprint'], 'policy': ELIGIBLE_WEAK_POLICY,
        'version': ELIGIBLE_WEAK_SCORER,
    }, sort_keys=True).encode()).hexdigest()
    return analysis


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
                'stable-evidence-v1.20-phase6d24', 'stable-evidence-v1.21-phase6d25',
                'stable-evidence-v1.22-phase6d26', 'stable-evidence-v1.23-phase6d27',
                'stable-evidence-v1.24-phase6d28', 'stable-evidence-v1.25-phase6d29',
                'stable-evidence-v1.26-phase6d30')
            or analysis.get('preview_namespace')
            or analysis.get('score_publication_status') == 'WITHHELD_PENDING_POLICY_REVIEW'
            or review_pending(analysis.get('canonical_requirements', [])))


def assert_analysis_publishable(analysis):
    """Reject development payloads before opening a DB or publishing a score."""
    if is_development_preview(analysis):
        raise ValueError('Coordinated-action development preview cannot be persisted or published')

"""Shared passive presentation; never resolves requirements or grants credit."""


def score_text(value, suffix=''):
    return 'Unavailable' if value is None else f'{value}{suffix}'


def score_delta(after, before):
    return None if after is None or before is None else after - before


def assessment_label(row):
    importance = row.get('importance')
    if row.get('score_eligible') is False:
        return 'Non-scored context'
    if importance in ('required', 'deal_breaker'):
        return 'Mandatory applicant qualification'
    if importance == 'preferred':
        return 'Preferred qualification'
    if importance == 'supporting':
        return 'Supporting attribute'
    if (row.get('assessment_basis') == 'role_relevance_not_prior_experience_prerequisite'
            or row.get('semantic_type') == 'role_responsibility'):
        return 'Core role relevance / future responsibility'
    return 'Core applicant qualification'


def render_alignment_metrics(st, analysis):
    for col, label, key, suffix in zip(st.columns(4),
            ('Job Match', 'Qualification / core alignment', 'Preferred', 'Evidence strength'),
            ('deterministic_alignment_score', 'required_core_coverage_score',
             'preferred_coverage_score', 'evidence_strength_score'), ('/100', '%', '%', '%')):
        col.metric(label, score_text(analysis.get(key), suffix))
    if analysis.get('deterministic_alignment_score') is None:
        st.info(analysis.get('score_interpretation') or 'Alignment unavailable')


def render_requirement_context(st, analysis):
    """Reuse the current result view's expander, preserving original receipts."""
    if not analysis.get('requirement_context_policy_version'):
        return
    st.caption('Core alignment includes job responsibilities. Future duties are assessed for role relevance; '
               'they do not assert mandatory prior experience. Preferred and supporting items are separate.')
    with st.expander('Qualification, role relevance and non-scored context'):
        rows = [{'Requirement': r.get('text'), 'Assessment basis': assessment_label(r),
                 'Importance': r.get('importance'), 'Evidence': r.get('match_label'),
                 'Source': ' | '.join(r.get('sources') or [])}
                for r in analysis.get('canonical_requirements', [])]
        debug = analysis.get('canonicalisation_debug') or {}
        exclusions = list(debug.get('filtered_non_requirement_rows') or [])
        exclusions += (debug.get('decomposition') or {}).get('unheaded_raw_exclusions') or []
        rows += [{'Requirement': r.get('text'), 'Assessment basis': 'Non-scored context',
                  'Importance': None, 'Evidence': None, 'Source': r.get('source') or r.get('span_id'),
                  'Reason': r.get('eligibility_rule') or r.get('reason')}
                 for r in exclusions]
        st.dataframe(rows, hide_index=True, width='stretch')

"""Read-only inspection of saved source candidates and whole-slate decisions."""
from __future__ import annotations

import json
from typing import Any

from tailoring.phase9f_v365_jd_evidence import rank_bullets, requirement_catalog

TITLE = 'Inspect project bullets & Base/Library decisions'
NO_WINNER = 'No independent Base-versus-Library winner measured.'


def source_group(row: dict) -> str:
    sources = set(row.get('sources') or [])
    if {'Selected Base', 'Evidence Library'} <= sources:
        return 'Base + Library (identical wording)'
    if 'Selected Base' in sources:
        return 'Base-only'
    if 'Evidence Library' in sources:
        return 'Library-only'
    if sources == {'Current final'}:
        return 'Current-fitted-only'
    return 'Unknown'


def inspector_rows(calc: dict, audit: dict) -> tuple[list[dict], bool]:
    """Use the saved pool, or inspect source audit with proposal status unknown."""
    if calc.get('rows'):
        return calc['rows'], calc.get('status') == 'available'
    rows = {}
    for project in audit.get('projects') or []:
        for field, source in (('base', 'Selected Base'), ('library', 'Evidence Library'), ('final', 'Current final')):
            for bullet in project.get(field) or []:
                key = (project['project'], bullet['text'])
                row = rows.setdefault(key, {'project': key[0], 'bullet': key[1], 'sources': [],
                                            'in_actual_a': False, 'in_proposed_b': False,
                                            'saved_jd_ids': [], 'words': len(key[1].split())})
                if source not in row['sources']:
                    row['sources'].append(source)
                row['in_actual_a'] |= field == 'final'
    return list(rows.values()), False


def pair_explanation(base: dict, library: dict) -> dict:
    """Compare links and native excerpts without inferring a causal winner."""
    left, right = set(base['saved_jd_ids']), set(library['saved_jd_ids'])
    return {
        'shared': sorted(left & right),
        'base_unique_native': sorted(set(base['native_requirement_ids']) - set(library['native_requirement_ids'])),
        'library_unique_native': sorted(set(library['native_requirement_ids']) - set(base['native_requirement_ids'])),
        'base_only_cues': sorted(set(base['jd_wide_term_cues']) - set(library['jd_wide_term_cues'])),
        'library_only_cues': sorted(set(library['jd_wide_term_cues']) - set(base['jd_wide_term_cues'])),
        'library_words_saved': (base['words'] - library['words']
                                if isinstance(base['words'], int) and isinstance(library['words'], int) else None),
        'conclusion': NO_WINNER,
    }


def inspector_evidence(*, calc, audit, result, baseline_report, raw_jd_text, projects):
    """Shared preparation for the existing B3 inspector and surfaced B4 panel."""
    from tailoring.phase9f_bullet_pair_ui import selection_available
    rows, recorded = inspector_rows(calc, audit)
    compatible = selection_available(calc, audit, result, baseline_report, raw_jd_text)
    if recorded and not compatible and audit.get('projects'):
        rows, _ = inspector_rows({}, audit)
    recorded = recorded and compatible
    catalog = requirement_catalog(baseline_report, projects)
    ranked = rank_bullets(rows, catalog, raw_jd_text=raw_jd_text, result=result if compatible else {},
                         expected_jd_text=baseline_report.get('raw_jd_text') or '',
                         selection_recorded=recorded)
    for row in ranked:
        row['existing_membership_verified'] = bool(audit.get('verified'))
    return ranked, recorded, catalog


def render_bullet_inspector(st: Any, *, calc: dict, audit: dict, proposal: dict,
                            result: dict, baseline_report: dict, raw_jd_text: str,
                            projects: dict, application_id: int, context: str, offline_trial: dict | None = None,
                            show_pair_comparison: bool = True) -> None:
    from tailoring.phase9f_v364_decision_explorer import _render_bullet

    st.markdown('#### ' + TITLE)
    st.caption('Inspect saved source evidence, mathematical proposals and fitted-document results here. '
               'Phase 8 verification and explicit approval follow separately.')
    from tailoring.phase9f_bullet_pair_ui import render_pair_comparison
    ranked, recorded, catalog = inspector_evidence(calc=calc, audit=audit, result=result,
        baseline_report=baseline_report, raw_jd_text=raw_jd_text, projects=projects)
    if not recorded:
        st.info('A reliable selection receipt is unavailable for this generation. Source inspection is available '
                'where the saved document audit exists. Proposed membership and selection reasons are unknown.')
    if not ranked:
        st.caption('The saved generation has no eligible source pool or verified source audit to inspect.')
        return
    key = f'bullet_inspector_{application_id}_{context}'
    project = st.selectbox('Inspector project', ['All projects', *sorted({r['project'] for r in ranked})], key=key+'_project')
    if show_pair_comparison:
        render_pair_comparison(st, ranked=ranked, recorded=recorded, calc=calc, audit=audit,
                              proposal=proposal, result=result, catalog=catalog, projects=projects,
                              jd=raw_jd_text, report=baseline_report, key=key+'_b4', project=project,
                              offline_trial=offline_trial)
    membership = st.selectbox('Proposal membership', ['All eligible', 'Selected', 'Excluded', 'Changed'], key=key+'_membership')
    source = st.selectbox('Source wording', ['All sources', 'Base-only', 'Library-only',
                            'Base + Library (identical wording)', 'Current-fitted-only', 'Unknown'], key=key+'_source')
    importance = st.selectbox('Requirement relevance', ['All requirements', 'Required/Core', 'Preferred/Supporting'], key=key+'_importance')
    order = st.selectbox('Inspector sort', ['JD relevance', 'Fewest words', 'Selection status'], key=key+'_sort')
    visible = []
    for row in ranked:
        if project != 'All projects' and row['project'] != project:
            continue
        if source != 'All sources' and source_group(row) != source:
            continue
        if membership != 'All eligible':
            if not recorded:
                continue
            if membership == 'Selected' and not row['in_proposed_b']:
                continue
            if membership == 'Excluded' and row['in_proposed_b']:
                continue
            if membership == 'Changed' and row['in_actual_a'] == row['in_proposed_b']:
                continue
        kinds = {link['importance'] for link in row['jd_links']}
        if importance == 'Required/Core' and not kinds & {'core', 'required', 'deal_breaker'}:
            continue
        if importance == 'Preferred/Supporting' and not kinds & {'preferred', 'bonus', 'supporting'}:
            continue
        visible.append(row)
    if order == 'Fewest words':
        visible.sort(key=lambda row: (row['words'] is None, row['words'] or 0))
    elif order == 'Selection status':
        visible.sort(key=lambda row: not row['in_proposed_b'])
    st.caption(f'{len(visible)} eligible wordings match these filters. Saved links and terminology cues '
               'carry no new native Job Match credit.')
    if not visible:
        return
    page_count = (len(visible) + 11) // 12
    page = st.selectbox('Inspector page', list(range(1, page_count + 1)), key=key+'_page')
    page_rows = visible[(page-1)*12:page*12]
    table = []
    for row in page_rows:
        links = '\n'.join(f"{link['text']} ({link['importance']}) — {link['status']}" for link in row['jd_links'])
        table.append({'Project': row['project'], 'Exact bullet wording': row['bullet'],
                      'Source provenance': source_group(row), 'Existing fitted résumé':
                      ('Yes' if row['in_actual_a'] else 'No') if recorded or row['existing_membership_verified'] else 'Unknown',
                      'Optimized proposal': ('Included' if row['in_proposed_b'] else 'Excluded') if recorded else 'Unknown',
                      'Words': row['words'], 'Saved JD links / evidence': links or 'No resolved saved link or native excerpt'})
    # Static table limits DOM work and permits full wrapping without canvas truncation.
    st.table(table)
    st.download_button('Export filtered bullet inspector (JSON)', json.dumps(visible, ensure_ascii=False, indent=2),
                       file_name='bullet_inspector.json', mime='application/json', key=key+'_export', on_click='ignore')
    with st.expander('Inspect exact bullet JD evidence', expanded=False):
        chosen = st.selectbox('Evidence bullet', range(len(visible)),
                             format_func=lambda i: visible[i]['project'] + ' · ' + visible[i]['bullet'], key=key+'_evidence')
        row = visible[chosen]
        if {'Selected Base', 'Evidence Library'}.intersection(row['sources']):
            from tailoring.phase9f_bullet_pair_ui import anchor_id, request_comparison
            st.button('Compare this bullet with related source wording', key=key+'_compare_current',
                      on_click=request_comparison, args=(st, key+'_b4', row['project'], row['bullet']))
            st.markdown('[View the comparison panel](#'+anchor_id(key+'_b4')+')')
        _render_bullet(st, row, info={'source_receipt_present': recorded}, title=row['bullet'], peers=[])
        for link in row['jd_links']:
            for role, match in link['native_evidence'].items():
                st.write(f"{link['text']} · {role} native evidence · strength {match.get('strength', 'Unknown')}/5")
                st.write(match['excerpt'])
        for evidence_type, buckets in row['coverage'].items():
            for coverage, requirements in buckets.items():
                if requirements:
                    st.caption(evidence_type + ' · ' + coverage + ' · ' +
                               '; '.join(req['text'] for req in requirements))
        st.caption('Factual-review status · ' + ('The saved proposal requires Base-only factual review.'
                   if proposal.get('requires_base_review') else 'No additional review flag recorded in this proposal.'
                   if recorded else 'Unknown without a selection receipt.'))
    with st.expander('Recorded selection hierarchy and constraints', expanded=False):
        if calc.get('objective_stages'):
            st.write('The selector prioritizes weighted saved JD coverage, distinct JD terminology minus overlap, '
                     'membership changes, then word cost. Lexical overlap supplies terminology cues.')
        else:
            st.caption('Objective-stage measurements were not saved for this generation.')
        st.write('Solver receipt · ' + str(calc.get('solver_status') or 'Unavailable'))
        st.json({'objective_stages': calc.get('objective_stages') or [],
                 'constraints': (proposal.get('mathematical_certificate') or {}).get('constraints') or
                                (proposal.get('selection_receipt') or {}).get('constraints') or {},
                 'factual_review_required': proposal.get('requires_base_review') if recorded else None})
        st.caption('Per-bullet eligibility exclusions and fitting causes are unavailable unless recorded by a '
                   'controlled comparison. The optional mathematical inclusion/exclusion test above is proxy-only.')

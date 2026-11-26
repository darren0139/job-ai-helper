"""Compact Decision Explorer over saved selection and verification receipts."""
from __future__ import annotations

from hashlib import sha256
import json
import math
import re
from typing import Any

from tailoring.phase9f_v365_jd_evidence import (
    PREFERRED, REQUIRED, rank_bullets, requirement_catalog, requirement_fragment,
)

CHANGES = 'Changes between existing résumé and optimized alternative'
INCLUDED = 'Bullets included in optimized alternative'
ALL = 'All eligible bullets'


def resume_terms(message: Any) -> str:
    """Present older saved explanations without changing their stored values."""
    text = str(message or '')
    text = re.sub(r'\bA/B\b', 'résumé comparison', text)
    text = re.sub(r'\b(?:existing fitted|actual fitted|saved fitted|existing|actual|native|fitted|original|current|saved|final|candidate) A\b',
                  'existing fitted résumé', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(?:candidate|challenger|proposal|optimized|proposed) B\b',
                  'optimized alternative', text, flags=re.IGNORECASE)
    text = re.sub(r'\bA (?=document|score|requirement|comparison|JD|analysis|scoring)', 'existing résumé ',
                  text)
    text = re.sub(r'\bB (?=has|is|may|remains|was|document|score)', 'optimized alternative ', text)
    text = re.sub(r'\bScored A\b', 'Scored existing fitted résumé', text)
    text = re.sub(r'\bScored B\b', 'Scored optimized alternative', text)
    text = re.sub(r'\bkeep A\b', 'keep the existing fitted résumé', text, flags=re.IGNORECASE)
    return text


def decision_summary(calc: dict, result: dict) -> dict:
    existing, alternative = result.get('a_score'), result.get('b_score')
    verified = result.get('status') == 'verified' and all(
        isinstance(score, (int, float)) and not isinstance(score, bool) and math.isfinite(score)
        for score in (existing, alternative))
    delta = round(alternative - existing, 6) if verified else None
    if not verified:
        verdict = 'Native résumé comparison unavailable'
    elif result.get('winner') == 'optimized_candidate':
        verdict = 'Recommended résumé is the optimized alternative. Approval is a separate step.'
    elif result.get('hard_regressed_ids'):
        verdict = 'Keep the existing fitted résumé. Required/Core strength declined.'
    elif delta == 0:
        verdict = 'Keep the existing fitted résumé. Native Job Match scores tied.'
    elif delta < 0:
        verdict = 'Keep the existing fitted résumé. The optimized alternative scored lower.'
    else:
        verdict = 'Keep the existing fitted résumé. The optimized alternative did not clear the recommendation checks.'
    changed = [row for row in calc.get('rows') or []
               if bool(row.get('in_actual_a')) != bool(row.get('in_proposed_b'))]
    return {'verdict': verdict, 'native_delta': delta, 'changed_count': len(changed),
            'changed_rows': changed, 'a_score': existing if verified else None,
            'b_score': alternative if verified else None,
            'native_verification_status': result.get('status'),
            'source_receipt_present': calc.get('status') == 'available',
            'baseline_status': (calc.get('actual_verification') or {}).get('starting_resumes') or {},
            'no_head_to_head_bullet_score': True}


def _plain_row_reason(row: dict, summary: dict) -> str:
    if not summary.get('source_receipt_present'):
        return 'The saved record contains the eligible wording and has no selected slate.'
    if row.get('in_proposed_b'):
        return 'Included in the saved whole-résumé selection under its coverage and fit constraints.'
    return 'Not included in this combination. An independent comparison is a separate test.'


def _verified_coverage_changes(result: dict, catalog: dict) -> list[dict]:
    from tailoring.phase9f_automatic_bestof_v30 import RANK

    snapshots = result.get('native_document_evidence') or {}
    states = []
    for role, key in (('existing', 'a_docx_sha256'), ('alternative', 'b_docx_sha256')):
        snapshot = snapshots.get(role) or {}
        if not result.get(key) or result[key] != snapshot.get('docx_sha256'):
            return []
        states.append({row['requirement_id']: row['match_label']
                       for row in snapshot.get('requirements') or []})
    old, new = states
    if old.keys() != catalog.keys() or new.keys() != old.keys():
        return []
    return [{'text': catalog[rid]['text'], 'importance': catalog[rid]['importance'],
             'before': old[rid], 'after': new[rid]}
            for rid in old if old[rid] in RANK and new[rid] in RANK and old[rid] != new[rid]]


def _render_coverage(st: Any, row: dict) -> None:
    for evidence_label, buckets in row['coverage'].items():
        for membership, requirements in buckets.items():
            for label, kinds in (('Required/Core', REQUIRED), ('Preferred/bonus', PREFERRED)):
                titles = [req['text'] for req in requirements if req['importance'] in kinds]
                if titles:
                    st.caption(f'{label} · {membership.lower()} · {evidence_label.lower()}')
                    for title in titles:
                        st.write(title)
    if not any(reqs for buckets in row['coverage'].values() for reqs in buckets.values()):
        st.caption('No traceable coverage comparison is available for this bullet.')


def _render_bullet(st: Any, row: dict, *, info: dict, title: str, peers: list[dict]) -> None:
    with st.expander(title, expanded=False):
        st.write(row['bullet'])
        st.caption(_plain_row_reason(row, info))
        for req in row['jd_links']:
            st.write(f"{req['text']} ({req['importance'].replace('_', ' ').title()})")
            st.caption(req['status'])
            if req['keyword_overlap']:
                st.caption('Shared terms · ' + ', '.join(req['keyword_overlap']))
            for role, match in req['native_evidence'].items():
                doc = 'Existing fitted résumé' if role == 'existing' else 'Optimized alternative'
                st.caption(f"{doc} · recorded requirement match {match['match_label']}")
            if req['fragment_status'] != 'source_span_present':
                st.caption(req['fragment_warning'])
        if row['unresolved_jd_ids']:
            st.caption(f"{len(row['unresolved_jd_ids'])} saved links have no readable requirement in this receipt.")
        technologies = ', '.join(row['jd_wide_technology_cues']) or 'none recorded'
        activities = ', '.join(row['matched_action_families']) or 'none recorded'
        st.caption(f'Technology cues · {technologies} | Activity cues · {activities}')
        if row['unlinked_jd_term_cues']:
            st.caption('Other JD-wide keyword cues · ' + ', '.join(row['unlinked_jd_term_cues']))
        for cue in row['possible_unlinked_bonus_cues']:
            st.caption(f"Preferred/bonus wording cue · {cue['text']} ({', '.join(cue['terms'])})")
        _render_coverage(st, row)
        if peers:
            for peer in peers:
                words, peer_words = row.get('words'), peer.get('words')
                difference = ''
                if isinstance(words, int) and isinstance(peer_words, int):
                    difference = f' · {abs(peer_words - words)} words ' + (
                        'longer' if peer_words > words else 'shorter' if peer_words < words else 'difference')
                st.caption(f"Same-project source alternative · rank {peer['rank']} · {peer['source_label']}{difference}")


def _render_offline_receipts(st, *, trial, bonus, audit, catalog, raw_jd, scorer, project_rows, project, key):
    if trial is None and bonus is None:
        return
    from tailoring.phase9f_v37_bonus_view import load_bonus_view, render_bonus_view
    from tailoring.phase9f_v37_trial_view import controlled_trial_rows, render_controlled_trials

    bonus_view = load_bonus_view(bonus, raw_jd, catalog, audit) if (
        isinstance(bonus, dict) and scorer and bonus.get('scoring_version') == scorer) else None
    trials = []
    if (isinstance(trial, dict) and isinstance(trial.get('data'), bytes)
            and scorer and trial.get('scoring_version') == scorer):
        trials = controlled_trial_rows(
            trial.get('data', b''), receipt_sha256=trial.get('receipt_sha256'),
            jd_sha256=sha256(raw_jd.encode()).hexdigest(), scoring_version=scorer,
            baseline_sha256=trial.get('baseline_sha256'), trial_sha256=trial.get('trial_sha256'),
            catalog=catalog, audit=audit,
        )
    if (bonus_view is not None or trials) and st.checkbox('Show verified offline evidence (read-only)', key=key):
        if bonus_view is not None:
            render_bonus_view(st, bonus_view, project, project_rows)
        if trials:
            render_controlled_trials(st, trials, project_rows, project)


def render_compact_decision_explorer(st: Any, *, calc: dict, result: dict, proposal: dict,
                                     audit: dict, projects: dict, application_id: int,
                                     context: str, baseline_report: dict | None = None,
                                     raw_jd_text: str = '', offline_trial: dict | None = None,
                                     offline_bonus: dict | None = None, repo_root=None) -> None:
    st.markdown('### Decision Explorer')
    info = decision_summary(calc, result)
    catalog = requirement_catalog(baseline_report, projects)
    if info['native_delta'] is not None:
        st.info(f"{info['verdict']} Existing fitted résumé {info['a_score']:g} · "
                f"Optimized alternative {info['b_score']:g} ({info['native_delta']:+g} Job Match points). "
                'Both documents passed the one-page check.')
        if result.get('base_floor_reason'):
            st.caption(resume_terms(result['base_floor_reason']))
        verified_changes = _verified_coverage_changes(result, catalog)
        if verified_changes:
            with st.expander('Verified whole-résumé requirement changes', expanded=False):
                for entry in verified_changes:
                    st.write(f"{entry['text']} ({entry['importance'].replace('_', ' ').title()})")
                    st.caption(f"Recorded strength · {entry['before']} → {entry['after']}")
    elif result.get('status') != 'not_run':
        st.info(info['verdict'] + '. ' + resume_terms(result.get('reason')))

    basics = calc.get('summary') or {}
    counts = [basics.get(key) for key in (
        'actual_a_bullets_in_pool', 'selected_bullets_in_b', 'word_cost_baseline', 'word_cost_proposed')]
    if all(isinstance(v, int) for v in counts):
        old_count, new_count, old_words, new_words = counts
        st.caption(f'Project selection · {old_count} → {new_count} bullets · {old_words} → {new_words} words.')
        if old_words > new_words:
            savings = old_words - new_words
            additional = (f'The alternative contains {new_count - old_count} more bullets.'
                          if new_count > old_count else 'The alternative contains no net additional bullet.')
            st.caption(f'{savings} project-bullet words saved. {additional} '
                       'The receipt leaves the layout benefit and the use of freed space unverified.')
    if basics.get('proxy_points_baseline') is not None and basics.get('proxy_points_proposed') is not None:
        st.caption(f"Recorded selection objective (proxy) · {basics['proxy_points_baseline']} → "
                   f"{basics['proxy_points_proposed']} weighted saved-link units.")
    if calc.get('solver_status') == 'optimal_proxy' and calc.get('objective_stages'):
        st.caption('The mathematical selector compared whole résumés by saved JD coverage, terminology and '
                   'overlap, changes to existing wording, and word cost in that order.')

    from tailoring.phase9f_wording_explanation_ui import render_why_slate, render_primary_bullet_explanation
    # Reuse B3's exact evidence/currentness preparation and B4's existing component.
    # Keep the established key so detailed-inspector callbacks target this one panel.
    from tailoring.phase9f_bullet_inspector import inspector_evidence
    from tailoring.phase9f_v39_final_bullet_review import render_verified_final_bullets
    pair_rows, pair_recorded, pair_catalog = inspector_evidence(
        calc=calc, audit=audit, result=result, baseline_report=baseline_report or {},
        raw_jd_text=raw_jd_text, projects=projects)
    render_why_slate(st, info, calc if pair_recorded else {'status':'unavailable'})
    # Never display saved JD points when the proposal/JD source receipt is stale.
    final_view_available = render_verified_final_bullets(st, audit=audit, result=result,
        proposal=(proposal if pair_recorded else {}),
        ranked=pair_rows, catalog=pair_catalog, application_id=application_id,
        context=context, repo_root=repo_root,
        prefit_receipt=((projects or {}).get('_v39_auto_dedupe') if isinstance(projects, dict) else None))

    # Only the verified final view is primary. Retain the source-only inspector
    # as an explicit diagnostic, or fallback if no chosen DOCX is verified.
    source_key = f'bullet_inspector_{application_id}_{context}_b4'
    show_source = not final_view_available
    if pair_rows and final_view_available:
        toggle = source_key+'_advanced_open'
        if st.session_state.get(source_key+'_request'):
            st.session_state[toggle] = True
        show_source = st.checkbox('Inspect other source wordings (advanced)', key=toggle)
    if pair_rows and show_source:
        from tailoring.phase9f_bullet_pair_ui import render_pair_comparison
        render_pair_comparison(
            st, ranked=pair_rows, recorded=pair_recorded,
            calc=(calc if pair_recorded else {'status': 'unavailable'}),
            audit=audit, proposal=(proposal if pair_recorded else {}),
            result=result, catalog=pair_catalog, projects=projects,
            jd=raw_jd_text, report=(baseline_report or {}),
            key=f'bullet_inspector_{application_id}_{context}_b4',
            primary=True, application_id=application_id,
        )

    rows = calc.get('rows') or []
    receipt_scope = dict(trial=offline_trial, bonus=offline_bonus, audit=audit, catalog=catalog,
                         raw_jd=raw_jd_text, scorer=((baseline_report or {}).get('stable_analysis') or {}).get('scoring_version'),
                         key=f'v37_read_only_receipts_{application_id}_{context}')
    if not rows:
        _render_offline_receipts(st, project_rows=[], project='All projects', **receipt_scope)
        st.caption(resume_terms(calc.get('reason') or 'No eligible bullet pool was saved for this generation.'))
        from tailoring.phase9f_bullet_inspector import render_bullet_inspector
        render_bullet_inspector(st, calc=calc, audit=audit, proposal=proposal, result=result,
                               baseline_report=baseline_report or {}, raw_jd_text=raw_jd_text,
                               projects=projects, application_id=application_id, context=context, offline_trial=offline_trial, show_pair_comparison=False)
        return
    frozen_jd_text = (baseline_report or {}).get('raw_jd_text') or ''
    ranked = rank_bullets(rows, catalog, raw_jd_text=raw_jd_text, result=result,
                        expected_jd_text=frozen_jd_text, selection_recorded=info['source_receipt_present'])
    for index, row in enumerate(ranked, 1):
        row['rank'] = index
    with st.expander('Advanced Diagnostics — JD ranking and detailed evidence', expanded=False):
        st.markdown('#### JD Bullet Relevance Ranking')
        st.caption('Ranking uses distinct JD parents in this order: Required/Core native evidence, Required/Core saved links '
                   'with lexical cues, preferred/bonus native evidence, preferred/bonus saved links with lexical cues, '
                   'then matched technology count. Coverage here describes eligible project bullets. '
                   'Native per-bullet impact is unknown unless a controlled document comparison is recorded.')
        if not catalog:
            st.warning('This receipt lacks readable JD requirements.')
        options = ['All projects', *sorted({row['project'] for row in ranked})]
        project = st.selectbox('Project', options, key=f'v364_project_{application_id}_{context}')
        scope = st.selectbox('Show bullets', [ALL, CHANGES, INCLUDED] if info['source_receipt_present'] else [ALL],
                             key=f'v364_scope_v37_{application_id}_{context}')
        order = st.selectbox('Sort bullets', ['Highest JD relevance', 'Lowest JD relevance', 'Fewest words'],
                             key=f'v37_sort_{application_id}_{context}')
        project_rows = [row for row in ranked if project == options[0] or row['project'] == project]
        _render_offline_receipts(st, project_rows=project_rows, project=project, **receipt_scope)
        visible = [row for row in project_rows if scope == ALL
                   or (scope == CHANGES and bool(row.get('in_actual_a')) != bool(row.get('in_proposed_b')))
                   or (scope == INCLUDED and row.get('in_proposed_b'))]
        if order == 'Lowest JD relevance':
            visible.reverse()
        elif order == 'Fewest words':
            visible.sort(key=lambda row: (row['words'] is None, row['words'] or 0))
        st.caption(f'{len(visible)} of {len(ranked)} eligible wordings'
                   + (' · Ranks are across all projects' if project != options[0] else ''))
        for row in visible:
            existing, alternative = bool(row.get('in_actual_a')), bool(row.get('in_proposed_b'))
            membership = {
                (True, True): 'Both résumés', (True, False): 'Existing fitted résumé only',
                (False, True): 'Added to optimized alternative', (False, False): 'Outside this combination',
            }[existing, alternative] if info['source_receipt_present'] else 'Eligible wording'
            text = ' '.join(row['bullet'].split())
            preview = text if len(text) <= 72 else text[:69] + '…'
            cost = 'Word count unavailable' if row['words'] is None else f"{row['words']} words"
            project_label = f"{row['project']} · " if project == options[0] else ''
            title = f"{row['rank']}. {project_label}{row['source_label']} · {cost} · {membership} · {preview}"
            peers = []
            if info['source_receipt_present'] and existing != alternative and row['source_label'] in ('Base bullet', 'Library bullet'):
                opposite = 'Library bullet' if row['source_label'] == 'Base bullet' else 'Base bullet'
                ids = {req['id'] for req in row['jd_links']}
                peers = [peer for peer in project_rows if peer['project'] == row['project']
                         and peer['source_label'] == opposite and any(req['id'] in ids for req in peer['jd_links'])]
            _render_bullet(st, row, info=info, title=title, peers=peers)

        fragments = [{'requirement': req['text'], 'group_weight_fraction': req.get('group_weight_fraction'),
                      **requirement_fragment(req, raw_jd_text, expected_jd_text=frozen_jd_text)}
                     for req in catalog.values()]
        with st.expander('JD source and fragment diagnostics', expanded=False):
            flagged = [item for item in fragments if item['status'] != 'source_span_present'
                       or item['source_status'] != 'exact_span']
            if not flagged:
                st.caption('No source or fragment warning in the readable requirements.')
            for item in flagged:
                st.write(item['requirement'])
                st.caption(item['source_reason'])
                if item['grammar_status'] == 'clipped_boundary':
                    st.warning(item['reason'])
                if item['parent']:
                    st.write('Original parent · ' + item['parent'])
                for source in item['source_provenance']:
                    grounding = source.get('grounding') or {}
                    if grounding.get('line_index') is not None:
                        st.caption(f"Saved JD line {grounding['line_index']}")
                if item['group_weight_fraction'] is not None:
                    st.caption(f"Preserved parent allocation · {item['group_weight_fraction']}")

        if proposal and info['source_receipt_present']:
            _render_forced_comparison(st, project_rows, proposal, audit, projects, application_id, context)
        from tailoring.phase9f_bullet_inspector import render_bullet_inspector
        render_bullet_inspector(st, calc=calc, audit=audit, proposal=proposal, result=result,
                               baseline_report=baseline_report or {}, raw_jd_text=raw_jd_text,
                               projects=projects, application_id=application_id, context=context, offline_trial=offline_trial, show_pair_comparison=False)
        with st.expander('Advanced selection diagnostics', expanded=False):
            st.download_button('Export JD evidence and selection receipts (JSON)',
                data=json.dumps({'schema': 'phase9f-v37-decision-explorer-v1',
                    'native_whole_resume': {k: info[k] for k in ('a_score', 'b_score', 'native_delta', 'native_verification_status')},
                    'selection_calculation': calc, 'jd_requirements': list(catalog.values()),
                    'bullet_evidence': ranked, 'fragment_warnings': fragments},
                    ensure_ascii=False, indent=2, default=str),
                file_name=f'phase9f_app_{int(application_id)}_v37_jd_decisions.json',
                mime='application/json', key=f'v365_export_{application_id}_{context}', on_click='ignore')


def _render_forced_comparison(st: Any, rows: list[dict], proposal: dict, audit: dict,
                              projects: dict, application_id: int, context: str) -> None:
    with st.expander('Test one bullet in the mathematical model', expanded=False):
        options = [(row['project'], row['bullet']) for row in rows]
        if not options:
            return
        choice = st.selectbox('Bullet to test', range(len(options)),
            format_func=lambda i: ' · '.join(options[i]),
            key=f'v364_forced_choice_{application_id}_{context}')
        project, bullet = options[choice]
        identity = sha256(f'{project}\0{bullet}'.encode('utf-8')).hexdigest()[:12]
        test_key = f'v364_force_test_{application_id}_{context}_{identity}'
        if st.button('Compare required inclusion and exclusion (proxy only)',
                     key=f'v364_force_run_{application_id}_{context}'):
            from tailoring.phase9f_certified_selection_v36 import compare_forced_bullet
            with st.spinner('Running two constrained mathematical optimizations…'):
                st.session_state[test_key] = compare_forced_bullet(
                    audit, projects, proposal, project=project, bullet=bullet)
        outcome = st.session_state.get(test_key)
        if not isinstance(outcome, dict):
            return
        if outcome.get('status') != 'calculated':
            st.warning('Mathematical comparison unavailable. ' + resume_terms(outcome.get('reason')))
            return
        captions = {
            'force_in_proxy_preferred': 'The mathematical model preferred including this bullet.',
            'force_out_proxy_preferred': 'The mathematical model preferred excluding this bullet.',
            'proxy_tie': 'Both options tied under all four mathematical priorities.',
            'not_proven': 'At least one constrained solve did not establish a feasible optimum.',
        }
        st.info(captions.get(outcome['comparison'], 'Mathematical comparison unavailable'))
        for title, detail in [('Forced inclusion', outcome['force_in']), ('Forced exclusion', outcome['force_out'])]:
            st.markdown('**' + title + '**')
            if detail.get('status') != 'optimal_proxy':
                st.caption(resume_terms(detail.get('reason') or 'Infeasible or timeout'))
                continue
            values = [item['minimization_objective'] for item in detail.get('objectives') or []]
            if len(values) >= 3:
                st.caption(f'Weighted saved links {abs(values[0]) / 1000:g} · terminology and overlap {-values[1]:g} · membership cost {values[2]:g}')
            st.caption(f"Selected project-bullet words · {detail.get('selected_words', 'unavailable')}")

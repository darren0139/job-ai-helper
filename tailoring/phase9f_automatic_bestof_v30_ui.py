"""Run automatic actual-DOCX A/B best-of once per explicit Build and Fit attempt."""
from __future__ import annotations
from pathlib import Path
from typing import Any

from tailoring.phase9f_v364_decision_explorer import decision_summary, resume_terms
from tailoring.phase9f_v365_jd_evidence import source_wording_label
from tailoring.phase9f_same_work_selection_v37 import build_same_work_optimization


# Ordinary UI keeps the original V2.6 reference and the unified V3.5 mode.
# Older modes remain runnable for historical receipts, regression and rollback,
# but are no longer presented as competing user choices.
ACTIVE_MODES = ('v35-relevance', 'v37-same-work', 'v26-fixed')
LEGACY_MODES = ('v31-flexible', 'v33-evidence')
MODES = ACTIVE_MODES + LEGACY_MODES


def _mode_key(application_id: int) -> str:
    return f'phase9f_bestof_next_mode_{int(application_id)}'


def configured_mode(st: Any, application_id: int) -> str:
    """New requests use V3.5; legacy stored choices migrate without rewriting history."""
    choice = st.session_state.get(_mode_key(application_id))
    return choice if choice in ACTIVE_MODES else 'v37-same-work'  # _V38_DEFAULT_GUARDED_DEDUPE


def render_optimizer_mode_selector(st: Any, application_id: int) -> str:
    """Only V3.5 automatic and original V2.6 are user-facing modes."""
    key = _mode_key(application_id)
    if st.session_state.get(key) not in ACTIVE_MODES:
        st.session_state[key] = 'v37-same-work'  # _V38_DEFAULT_GUARDED_DEDUPE
    st.radio('JD-aware bullet optimization (for the next Generate and Fit)',
        options=ACTIVE_MODES, key=key, horizontal=False,
        format_func=lambda mode: ('V3.5 — JD-aware comparison (existing behavior)'
                                  if mode=='v35-relevance' else
                                  'V3.7 — Prefer one wording per same-work Base/Library pair'
                                  if mode=='v37-same-work' else
                                  'V2.6 — Original fixed-count comparison'))
    if configured_mode(st, application_id) in ('v35-relevance','v37-same-work'):
        st.caption('Rank exact grounded Base + Library bullets by saved JD coverage, '
                   'JD terminology and evidence overlap; test up to three complete '
                   'one-page DOCX challengers with native Job Match. Library wording '
                   'only breaks otherwise equal source ties.')
    if configured_mode(st, application_id)=='v37-same-work':
        st.caption('V3.7 adds an at-most-one rule for confidently overlapping Base/Library work within the same project. A safe, independently verified alternative is required; otherwise the existing fitted résumé stays unchanged.')
    st.caption('The existing fitted résumé is built first. '
               'Each optimized alternative requires an independent one-page check and native Job Match comparison. '
               'This setting applies to the next generation.')
    return configured_mode(st, application_id)


def mark_fit_request(st: Any, application_id: int, generation_id: Any) -> None:
    """Capture the visible mode on successful Build and Fit; history is immutable."""
    if generation_id:
        identifier = int(application_id)
        token = str(generation_id)
        st.session_state[f'phase9f_auto_bestof_pending_{identifier}'] = token
        mode = configured_mode(st, identifier)
        st.session_state[f'phase9f_auto_bestof_run_mode_{identifier}'] = {
            'generation_id':token, 'mode':mode}


def _source_comparison_rows(proposal: dict, jd_labels: dict | None = None) -> list[dict]:
    jd_labels = jd_labels or {}
    gained = set(proposal.get('gained_jd_ids') or []) if isinstance(proposal, dict) else set()
    comparison = proposal.get('source_comparison') if isinstance(proposal, dict) else None
    groups = comparison.get('projects') if isinstance(comparison, dict) else None
    if not isinstance(groups, list):
        return []
    rows = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        for bullet in group.get('candidates') or []:
            if not isinstance(bullet, dict):
                continue
            rows.append({
                'Project': str(group.get('project') or 'Project'),
                'Exact bullet wording': str(bullet.get('text') or ''),
                'Found in': source_wording_label(bullet.get('source_labels')),
                'In existing fitted résumé': 'Yes' if bullet.get('in_original_a') else 'No',
                'In optimized alternative': 'Yes' if bullet.get('selected_for_proposed_b') else 'No',
                'JD requirements linked': '; '.join(jd_labels.get(str(rid), 'Requirement text unavailable')
                                                    for rid in bullet.get('saved_jd_ids') or []) or 'None recorded',
                'New saved links vs existing résumé': '; '.join(jd_labels.get(str(rid), 'Requirement text unavailable')
                                                    for rid in bullet.get('saved_jd_ids') or [] if rid in gained) or 'None',
                'Standalone saved-link proxy': bullet.get('standalone_saved_coverage_points'),
                'Grounded JD term cues (advisory)': ', '.join(bullet.get('v35_jd_term_hits') or []) or 'None',
                'Link corroboration cue (if measured)': bullet.get('v35_link_corroboration'),
                'Words': bullet.get('word_count'),
            })
    return rows


def _render_source_comparison(st: Any, *, application_id: int, context: str,
                              run_mode: str, result: dict, audit: dict,
                              projects: dict | None = None) -> None:
    """Make provenance and collective selection visible even for no challenger."""
    import json
    proposal = result.get('proposal') if isinstance(result.get('proposal'), dict) else {}
    status = str(result.get('status') or 'not_run')
    jd_labels = {}
    for rank in (projects or {}).get('candidate_project_ranking') or []:
        if not isinstance(rank, dict): continue
        for requirement in rank.get('requirement_matches') or []:
            if isinstance(requirement, dict) and requirement.get('requirement_id'):
                rid = str(requirement['requirement_id'])
                jd_labels[rid] = str(requirement.get('requirement_text') or rid)
    original = []
    for section in audit.get('projects') or []:
        for item in section.get('final') or []:
            if not isinstance(item, dict):
                continue
            tags = []
            if item.get('exact_base'):
                tags.append('Selected Base')
            if item.get('exact_library'):
                tags.append('Evidence Library')
            original.append({
                'Project': str(section.get('project') or 'Project'),
                'Existing fitted résumé bullet': str(item.get('text') or ''),
                'Matching saved wording': source_wording_label(tags or ['Current final']),
            })
    # V3.5.0 accidentally stored a shortlist envelope inside its first
    # candidate, and then the envelope contained that very candidate.
    # Export a detached shortlist even for a stale, already-cached failure;
    # do not mutate the stored optimizer result or hide its trial evidence.
    exported_proposal = proposal
    if isinstance(proposal.get('candidate_variants'), list):
        exported_proposal = {k: v for k, v in proposal.items() if k != 'candidate_variants'}
        exported_proposal['candidate_variants'] = [
            {k: v for k, v in candidate.items() if k != 'candidate_variants'}
            if isinstance(candidate, dict) else candidate
            for candidate in proposal['candidate_variants']
        ]
    from tailoring.phase9f_v363_selection_receipts import build_bullet_selection_calculation
    selection_calculation = (build_bullet_selection_calculation(exported_proposal, result)
                             if run_mode == 'v35-relevance' else {'status':'not_applicable'})
    receipt = {
        'bullet_selection_calculation': selection_calculation,
        'schema': 'phase9f-bestof-source-explanation-v1',
        'generation_id': audit.get('generation_id'),
        'a_docx_sha256': audit.get('docx_sha256'),
        'optimizer_mode_used': run_mode,
        'comparison_status': status,
        'comparison_reason': result.get('reason'),
        'comparison_winner': result.get('winner'),
        'verification_stage': result.get('verification_stage') or '',
        'candidate_verified': result.get('status') == 'verified',
        'original_actual_a': original,
        'candidate_wording_diagnostics': _source_comparison_rows(exported_proposal, jd_labels),
        'existing_fitting_audit': audit,
        'proposal': exported_proposal,
        'actual_a_vs_starting': result.get('a_vs_starting'),
        'v35_trial_receipts': result.get('v35_trial_receipts') or [],
        'source_wording_is_causal_proof': False,
        'head_to_head_base_library_winner_recorded': False,
    }
    try:
        debug_json = json.dumps(receipt, indent=2, ensure_ascii=False, default=str).encode('utf-8')
    except (ValueError, TypeError, OverflowError) as exc:
        # Never crash the Streamlit app just because a diagnostic object is
        # malformed. The actual A/B result and original DOCX stay untouched.
        st.error('Selection debug export unavailable: '+type(exc).__name__+
                 '.')
        return
    st.download_button('Export Base/Library selection & fitting debug (JSON)',
        data=debug_json,
        file_name=f'phase9f_app_{int(application_id)}_{context}_selection_debug.json',
        mime='application/json', key=f'phase9f_bestof_explain_export_{int(application_id)}_{context}',
        on_click='ignore')


def render_automatic_bestof(st:Any, *, application_id:int, generation_id:str,
                            projects:dict|None, fit:dict|None, baseline_report:dict,
                            raw_jd_text:str, execution:dict|None, decision:dict|None,
                            repo_root:Path, trusted_offline_trial:dict|None=None,
                            trusted_offline_bonus:dict|None=None) -> None:
    """Render comparison plus explicitly supplied, read-only receipt bindings."""
    from tailoring.phase9f_automatic_bestof_v30 import evaluate_auto,hold,verify_fitted_a_against_baselines
    from tailoring.phase9f_project_bullet_sources_v2_3 import _bound_candidate_sources
    from tailoring.phase9f_final_evidence_comparison_v2_4 import build_final_evidence_audit,_docx_path
    from tailoring.phase9f_joint_resume_optimizer_v2_6 import build_joint_optimization,materialize_verified_candidate
    from tailoring.phase9f_auto_optimize_v31 import build_flexible_optimization
    from tailoring.phase9f_evidence_optimizer_v33 import build_evidence_aware_optimization
    from tailoring.phase9f_certified_selection_v36 import (
        build_certified_optimization, selected_base_floor_gate)
    from database.tailoring_generation_control import get_tailoring_generation
    st.caption('Verified Best-of tests complete, one-page optimized alternatives after Build and Fit.')
    mode_receipt = st.session_state.get(f'phase9f_auto_bestof_run_mode_{int(application_id)}')
    if (isinstance(mode_receipt, dict) and
            str(mode_receipt.get('generation_id') or '') == str(generation_id) and
            mode_receipt.get('mode') in MODES):
        run_mode = mode_receipt['mode']
        if mode_receipt.get('manual_existing_fit_trial') is True:
            st.caption('Manual optimizer recheck of the existing fitted résumé.')
        else:
            st.caption('Optimizer used for this Build and Fit: **'+
                       ('V3.7 one-of-two same-work' if run_mode == 'v37-same-work' else
                        'V3.5 JD relevance-first' if run_mode == 'v35-relevance' else
                        'V3.3 evidence-aware (historical)' if run_mode == 'v33-evidence' else
                        'V3.1 flexible allocation' if run_mode == 'v31-flexible' else
                        'V2.6 fixed counts')+'**.')
    else:
        # Legacy runs did not snapshot the mode on the Build and Fit click.
        run_mode = 'v26-fixed'
        # A durable snapshot may be restored after the fitted audit is validated.
    if not generation_id or not isinstance(projects,dict) or not isinstance(fit,dict) or fit.get('fit_one_page') is not True:
        st.info('Build and Fit a normal one-page generation to run this comparison.')
        return
    candidates,reason=_bound_candidate_sources(execution,decision)
    if candidates is None:
        st.info('Frozen source evidence unavailable: '+str(reason));return
    audit=build_final_evidence_audit(projects,fit,candidates,repo_root=repo_root,
                                    application_id=application_id,expected_generation_id=generation_id)
    if not audit.get('verified'):
        st.info('Actual fitted DOCX audit withheld: '+str(audit.get('notice') or ''))
        return
    from database.phase9f_bestof_review_state import (
        load_bestof_display_receipt, save_bestof_display_receipt)
    import hashlib
    pending_key=f'phase9f_auto_bestof_pending_{int(application_id)}'
    pending=str(st.session_state.get(pending_key) or '')
    scorer_version=str((baseline_report.get('stable_analysis') or {}).get('scoring_version') or '')
    saved_display=None
    if pending != str(generation_id):
        try:
            saved_display=load_bestof_display_receipt(
                application_id=int(application_id), generation_id=str(generation_id),
                docx_sha256=audit['docx_sha256'], raw_jd_text=raw_jd_text,
                scorer_version=scorer_version)
        except Exception:
            saved_display=None  # Never convert display restoration into approval authority.
    if saved_display and not (isinstance(mode_receipt,dict) and
            str(mode_receipt.get('generation_id') or '')==str(generation_id) and
            mode_receipt.get('mode') in MODES):
        recovered=saved_display.get('mode_receipt') or {}
        if (isinstance(recovered,dict) and
                recovered.get('mode')==saved_display.get('run_mode') and
                str(recovered.get('generation_id') or '')==str(generation_id) and
                recovered.get('mode') in MODES):
            mode_receipt=recovered
            run_mode=recovered['mode']
            st.session_state[f'phase9f_auto_bestof_run_mode_{int(application_id)}']=recovered
            st.caption('Restored the saved comparison for this exact fitted document and JD.')
        else:
            saved_display=None
    tie_preference=(isinstance(mode_receipt,dict) and run_mode=='v33-evidence' and
                    mode_receipt.get('library_tie_preference') is True)
    if run_mode=='v37-same-work':
        selected_optimizer=build_same_work_optimization
    elif run_mode in ('v35-relevance','v37-same-work'):
        selected_optimizer=build_certified_optimization
    elif run_mode=='v33-evidence':
        selected_optimizer=lambda a,p: build_evidence_aware_optimization(
            a,p,library_tie_preference=tie_preference)
    else:
        selected_optimizer=(build_flexible_optimization if run_mode=='v31-flexible'
                             else build_joint_optimization)
    mode_label=run_mode+'|library_tie='+str(bool(tie_preference))
    context=hashlib.sha256((str(generation_id)+'|'+audit['docx_sha256']+'|'+raw_jd_text+'|'+mode_label).encode('utf-8')).hexdigest()[:16]
    key=f'phase9f_auto_bestof_receipt_{int(application_id)}_{context}'

    def save_display_review(display, *, receipt_context=context, mode=run_mode, mode_snapshot=None):
        try:
            return save_bestof_display_receipt(
                application_id=int(application_id), generation_id=str(generation_id),
                context=receipt_context, docx_sha256=audit['docx_sha256'],
                raw_jd_text=raw_jd_text, scorer_version=scorer_version,
                run_mode=mode, mode_receipt=(mode_snapshot or mode_receipt or {
                    'generation_id':str(generation_id), 'mode':mode,
                    'legacy_mode_inferred_for_display':True}),
                result=display)
        except Exception:
            return False
    # On the first rerun after the explicit successful fit only.
    if pending == str(generation_id):
        st.session_state.pop(pending_key,None)
        docx,err=_docx_path(fit,repo_root,application_id)
        if docx is None:
            result=hold('Fitted source DOCX is not accessible: '+str(err))
        else:
            generation=get_tailoring_generation(application_id,generation_id)
            with st.spinner('Comparing actual one-page candidate documents...'):
                result=evaluate_auto(audit=audit,projects=projects,fit=fit,
                    generation=generation,baseline_report=baseline_report,
                    raw_jd_text=raw_jd_text,source_docx=docx,repo_root=repo_root,
                    application_id=application_id,optimizer=selected_optimizer,
                    generator=materialize_verified_candidate)
        # The Phase 8 comparison must be available even when the selector
        # reports no challenger, or B is withheld. This never changes A/B winner.
        if docx is not None and isinstance(generation,dict):
            result['a_vs_starting']=verify_fitted_a_against_baselines(
                audit=audit,fit=fit,generation=generation,
                baseline_report=baseline_report,raw_jd_text=raw_jd_text,
                source_docx=docx)
        else:
            result['a_vs_starting']={'status':'unavailable',
                'reason':'Fitted DOCX or saved generation is missing.'}
        if run_mode in ('v35-relevance','v37-same-work'):
            result=selected_base_floor_gate(result,result.get('a_vs_starting'))
        st.session_state[key]=result
        if not save_display_review(result):
            st.caption('Comparison is visible in this session, but its display receipt could not be saved.')
    result=st.session_state.get(key)
    if not isinstance(result,dict) and saved_display and saved_display.get('context')==context:
        result=saved_display['result']
        st.session_state[key]=result
    if not isinstance(result,dict):
        st.caption('Start a comparison of this fitted résumé using its saved evidence.')
        result={'status':'not_run'}
    # Recovery from a withheld candidate does NOT require re-generating
    # Projects/Skills or the fitted A. The button reruns full source, document,
    # one-page and native-score gates on the unchanged, hashed saved generation.
    if result.get('status')=='withheld' and run_mode in ('v33-evidence','v35-relevance','v37-same-work'):
        st.caption('Candidate verification stopped at: '+str(result.get('verification_stage') or 'unrecorded stage')+
                   '. Use the existing fitted résumé.')
        if st.button('Retry native comparison using the existing fitted résumé',
                     key=f'phase9f_v34_retry_{application_id}_{context}'):
            retry_docx,retry_err=_docx_path(fit,repo_root,application_id)
            retry_generation=get_tailoring_generation(application_id,generation_id)
            if retry_docx is None or not isinstance(retry_generation,dict):
                st.error('Retry unavailable: saved DOCX or generation missing. '+str(retry_err or ''))
            else:
                with st.spinner('Verifying the existing fitted résumé and rendering and scoring the optimized alternative…'):
                    retry=evaluate_auto(audit=audit,projects=projects,fit=fit,
                        generation=retry_generation,baseline_report=baseline_report,
                        raw_jd_text=raw_jd_text,source_docx=retry_docx,repo_root=repo_root,
                        application_id=application_id,optimizer=selected_optimizer,
                        generator=materialize_verified_candidate)
                    retry['a_vs_starting']=verify_fitted_a_against_baselines(
                        audit=audit,fit=fit,generation=retry_generation,
                        baseline_report=baseline_report,raw_jd_text=raw_jd_text,
                        source_docx=retry_docx)
                    if run_mode in ('v35-relevance','v37-same-work'):
                        retry=selected_base_floor_gate(retry,retry.get('a_vs_starting'))
                    st.session_state[key]=retry
                    save_display_review(retry)
                st.rerun()
    # A Streamlit restart can clear the transient run-mode snapshot and
    # withheld result. Offer a separate *explicit new trial* using the saved A
    # when V3.5 is selected above; never rewrite the historical Build&Fit mode.
    if (result.get('status')=='not_run' and
            configured_mode(st,application_id)=='v35-relevance'):
        st.caption('No optimizer result is cached for this session. A new explicit '
                   'trial can use this existing fitted résumé.')
        if st.button('Compare the existing fitted résumé with a JD-aware alternative',
                     key=f'phase9f_v34_manual_existing_{application_id}_{context}'):
            manual_docx,manual_err=_docx_path(fit,repo_root,application_id)
            manual_generation=get_tailoring_generation(application_id,generation_id)
            if manual_docx is None or not isinstance(manual_generation,dict):
                st.error('Manual check unavailable: saved DOCX or generation missing. '+str(manual_err or ''))
            else:
                manual_mode=configured_mode(st,application_id)
                manual_tie=False
                manual_optimizer=(build_same_work_optimization if manual_mode=='v37-same-work'
                                  else build_certified_optimization)
                with st.spinner('Testing JD-aware alternatives against the existing fitted résumé…'):
                    manual=evaluate_auto(audit=audit,projects=projects,fit=fit,
                        generation=manual_generation,baseline_report=baseline_report,
                        raw_jd_text=raw_jd_text,source_docx=manual_docx,repo_root=repo_root,
                        application_id=application_id,optimizer=manual_optimizer,
                        generator=materialize_verified_candidate)
                    manual['a_vs_starting']=verify_fitted_a_against_baselines(
                        audit=audit,fit=fit,generation=manual_generation,
                        baseline_report=baseline_report,raw_jd_text=raw_jd_text,
                        source_docx=manual_docx)
                    new_label=manual_mode+'|library_tie='+str(bool(manual_tie))
                    new_context=hashlib.sha256((str(generation_id)+'|'+audit['docx_sha256']+
                        '|'+raw_jd_text+'|'+new_label).encode('utf-8')).hexdigest()[:16]
                    new_key=f'phase9f_auto_bestof_receipt_{int(application_id)}_{new_context}'
                    manual=selected_base_floor_gate(manual,manual.get('a_vs_starting'))
                    st.session_state[new_key]=manual
                    save_display_review(manual, receipt_context=new_context,
                        mode=manual_mode, mode_snapshot={
                            'generation_id':str(generation_id),'mode':manual_mode,
                            'library_tie_preference':manual_tie,'manual_existing_fit_trial':True})
                    st.session_state[f'phase9f_auto_bestof_run_mode_{int(application_id)}']={
                        'generation_id':str(generation_id),'mode':manual_mode,
                        'library_tie_preference':manual_tie,'manual_existing_fit_trial':True}
                st.rerun()
    # An explicit deduplication experiment reuses the EXACT saved fitted A.
    # It creates a new, separately keyed display receipt; no approved artifact
    # or historical optimizer receipt is rewritten.
    if run_mode != 'v37-same-work':
        st.caption('Optional V3.7 trial: compare same-work Base/Library alternatives without regenerating the fitted résumé.')
        if st.button('Test one-of-two duplicate removal using existing fitted résumé',
                     key=f'phase9f_v37_same_work_existing_{application_id}_{context}'):
            trial_docx,trial_err=_docx_path(fit,repo_root,application_id)
            trial_generation=get_tailoring_generation(application_id,generation_id)
            if trial_docx is None or not isinstance(trial_generation,dict):
                st.error('Same-work trial unavailable: saved fitted DOCX or generation missing. '+str(trial_err or ''))
            else:
                with st.spinner('Testing a de-duplicated whole-résumé alternative with native verification...'):
                    tested=evaluate_auto(audit=audit,projects=projects,fit=fit,
                        generation=trial_generation,baseline_report=baseline_report,
                        raw_jd_text=raw_jd_text,source_docx=trial_docx,repo_root=repo_root,
                        application_id=application_id,optimizer=build_same_work_optimization,
                        generator=materialize_verified_candidate)
                    tested['a_vs_starting']=verify_fitted_a_against_baselines(
                        audit=audit,fit=fit,generation=trial_generation,
                        baseline_report=baseline_report,raw_jd_text=raw_jd_text,
                        source_docx=trial_docx)
                    tested=selected_base_floor_gate(tested,tested.get('a_vs_starting'))
                    trial_mode='v37-same-work'
                    trial_context=hashlib.sha256((str(generation_id)+'|'+audit['docx_sha256']+
                        '|'+raw_jd_text+'|'+trial_mode+'|library_tie=False').encode('utf-8')).hexdigest()[:16]
                    trial_key=f'phase9f_auto_bestof_receipt_{int(application_id)}_{trial_context}'
                    st.session_state[trial_key]=tested
                    trial_snapshot={'generation_id':str(generation_id),'mode':trial_mode,
                                    'manual_existing_fit_trial':True}
                    save_display_review(tested,receipt_context=trial_context,
                                        mode=trial_mode,mode_snapshot=trial_snapshot)
                    st.session_state[f'phase9f_auto_bestof_run_mode_{int(application_id)}']=trial_snapshot
                st.rerun()
    # Historical cached B candidates also have to pass the new Base-floor
    # guard before they are displayed as recommendations. Do not rewrite
    # persisted receipts merely by inspecting an old result.
    if run_mode in ('v35-relevance','v37-same-work'):
        result=selected_base_floor_gate(result,result.get('a_vs_starting'))
    saved_proposal = result.get('proposal') or {}
    has_selection_receipt = run_mode in ('v35-relevance','v37-same-work') or saved_proposal.get('source_comparison')
    if has_selection_receipt:
        from tailoring.phase9f_v363_selection_receipts import build_bullet_selection_calculation
        from tailoring.phase9f_v364_decision_explorer import render_compact_decision_explorer
        calculation = build_bullet_selection_calculation(saved_proposal, result)
        render_compact_decision_explorer(st, calc=calculation, result=result,
                                         proposal=saved_proposal, audit=audit,
                                         projects=projects, application_id=int(application_id),
                                         context=context, baseline_report=baseline_report, raw_jd_text=raw_jd_text,
                                         offline_trial=trusted_offline_trial, offline_bonus=trusted_offline_bonus,
                                         repo_root=repo_root)
    elif trusted_offline_trial is not None or trusted_offline_bonus is not None:
        from tailoring.phase9f_v364_decision_explorer import _render_offline_receipts
        from tailoring.phase9f_v365_jd_evidence import requirement_catalog

        _render_offline_receipts(
            st, trial=trusted_offline_trial, bonus=trusted_offline_bonus, audit=audit,
            catalog=requirement_catalog(baseline_report, projects), raw_jd=raw_jd_text,
            scorer=(baseline_report.get('stable_analysis') or {}).get('scoring_version'),
            project_rows=[], project='All projects', key=f'v37_read_only_receipts_{application_id}_{context}',
        )
    if result.get('status')=='verified':
        if not has_selection_receipt:
            info = decision_summary({}, result)
            st.info(info['verdict'])
            if info['native_delta'] is not None:
                st.caption(f"Existing fitted résumé {info['a_score']} · Optimized alternative {info['b_score']} "
                           f"({info['native_delta']:+g} Job Match points).")
            _render_legacy_changes(st, result.get('proposal') or {}, application_id, context)
        st.caption('Scorer · ' + str(result.get('scoring_version') or 'unavailable'))
        if result.get('winner')=='optimized_candidate':
            doc=Path(result.get('candidate_file') or '');pdf=Path(result.get('candidate_pdf') or '')
            if (doc.is_file() and pdf.is_file() and doc.suffix.lower()=='.docx'
                and hashlib.sha256(doc.read_bytes()).hexdigest()==result.get('b_docx_sha256')
                and hashlib.sha256(pdf.read_bytes()).hexdigest()==result.get('candidate_pdf_sha256')):
                st.download_button('Download recommended résumé (unapproved DOCX)',
                    data=doc.read_bytes(),file_name=doc.name,mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    key=f'phase9f_auto_bestof_docx_{application_id}_{context}',on_click='ignore')
                st.download_button('Download recommended résumé PDF',data=pdf.read_bytes(),file_name=pdf.name,
                    mime='application/pdf',key=f'phase9f_auto_bestof_pdf_{application_id}_{context}',on_click='ignore')
    elif result.get('status')=='needs_review':
        st.warning(resume_terms(result.get('reason') or 'The optimized alternative requires factual evidence review.'))
        variants = saved_proposal.get('candidate_variants') or [saved_proposal]
        claims = sorted({
            (project['project'], text)
            for candidate in variants if candidate.get('requires_base_review')
            for project in candidate['projects']
            for text, sources in zip(project['after'], project['sources'], strict=True)
            if set(sources) == {'Selected Base'}
        })
        for project, text in claims:
            st.text(f'{project} · {text}')
        reviewed_snapshot, reviewed_scope = freeze_reviewed_slate(saved_proposal)
        if reviewed_snapshot is None:
            st.warning('Saved proposal cannot be bound to an immutable review identity. Review retry withheld; retain the existing résumé.')
        if claims and reviewed_snapshot is not None and st.checkbox('I verified these Base-only claims against the saved source résumé.', value=False,
                                  key=f'phase9f_auto_bestof_factual_review_{application_id}_{context}_{reviewed_scope}'):
            if st.button('Re-run reviewed actual-document challenger',key=f'phase9f_auto_bestof_review_run_{application_id}_{context}'):
                docx,err=_docx_path(fit,repo_root,application_id)
                generation=get_tailoring_generation(application_id,generation_id)
                if docx is not None:
                    reviewed=evaluate_auto(audit=audit,projects=projects,fit=fit,
                        generation=generation,baseline_report=baseline_report,
                        raw_jd_text=raw_jd_text,source_docx=docx,repo_root=repo_root,
                        application_id=application_id,optimizer=lambda _audit, _projects: freeze_reviewed_slate(reviewed_snapshot)[0],
                        generator=materialize_verified_candidate,base_reviewed=True)
                    reviewed['a_vs_starting']=verify_fitted_a_against_baselines(
                        audit=audit,fit=fit,generation=generation,baseline_report=baseline_report,
                        raw_jd_text=raw_jd_text,source_docx=docx)
                    reviewed = (selected_base_floor_gate(reviewed, reviewed['a_vs_starting'])
                                if run_mode=='v35-relevance' else reviewed)
                    st.session_state[key] = reviewed_core_floor(reviewed, baseline_report)
                    save_display_review(st.session_state[key])
                    st.rerun()
    elif run_mode not in ('v35-relevance','v37-same-work') and result.get('status') != 'not_run':
        st.info(resume_terms(result.get('reason') or 'Native résumé comparison unavailable.'))

    st.markdown('#### Did the existing fitted résumé improve over the starting résumé?')
    starting=result.get('a_vs_starting') if isinstance(result.get('a_vs_starting'),dict) else {}
    if starting.get('status')=='verified':
        st.caption('Existing fitted résumé native Job Match score **'+str(starting.get('a_score'))+
                   '** · Scorer: '+str(starting.get('scoring_version'))+'.')
        for label,title in (('initial','Initial résumé'),('selected_base','Selected Base résumé')):
            status=starting.get(label+'_comparison_status') or 'unavailable'
            if status=='unavailable':
                st.caption(title+': **not independently comparable** — no verified same-JD, same-scorer starting document evidence.')
            else:
                st.caption(title+': **'+status+'** · baseline '+str(starting.get(label+'_baseline_score'))+
                    ' → existing fitted résumé '+str(starting.get('a_score'))+' · Δ '+
                    f'{starting.get(label+"_delta",0):+g}'+
                    (' · Required/Core regressions: '+', '.join(starting.get(label+'_required_core_losses') or [])
                     if starting.get(label+'_required_core_losses') else ' · no Required/Core strength loss recorded'))
    else:
        st.caption('Comparison with starting documents is unavailable. '+
                   resume_terms(starting.get('reason') or 'This generation has no independent native-document receipt.'))
    with st.expander('Advanced fitting and optimizer receipt', expanded=False):
        _render_source_comparison(st, application_id=application_id, context=context,
                                  run_mode=run_mode, result=result, audit=audit, projects=projects)


def freeze_reviewed_slate(proposal: dict) -> tuple[dict | None, str]:
    """Bind review to all saved wording, sources, constraints and shortlist entries."""
    import hashlib
    import json
    try:
        encoded = json.dumps(proposal, sort_keys=True, ensure_ascii=False, allow_nan=False)
        snapshot = json.loads(encoded)
        if not isinstance(snapshot, dict) or not snapshot:
            return None, ''
        return snapshot, hashlib.sha256(encoded.encode('utf-8')).hexdigest()
    except (TypeError, ValueError, RecursionError):
        return None, ''


def reviewed_core_floor(result: dict, baseline_report: dict) -> dict:
    """Read-only floor on an explicitly reviewed retry; no scorer/objective change."""
    if result.get('winner') != 'optimized_candidate':
        return result
    from tailoring.phase9f_automatic_bestof_v30 import HARD, RANK
    out = dict(result)
    snapshots = result.get('native_document_evidence') or {}
    requirements = (baseline_report.get('stable_analysis') or {}).get('canonical_requirements') or []
    floors = {r['requirement_id'] for r in requirements if r.get('importance') in HARD}
    states = []
    valid = bool(requirements)
    for role, key in [('existing', 'a_docx_sha256'), ('alternative', 'b_docx_sha256')]:
        snap = snapshots.get(role) or {}
        valid &= bool(result.get(key)) and snap.get('docx_sha256') == result.get(key)
        rows = snap.get('requirements') or []
        values = {r['requirement_id']: r for r in rows}
        valid &= len(values) == len(rows) and floors <= values.keys()
        states.append(values)
    losses = []
    if valid:
        for rid in floors:
            a, b = states[0][rid], states[1][rid]
            strengths = [a.get('evidence_strength'), b.get('evidence_strength')]
            if (a.get('match_label') not in RANK or b.get('match_label') not in RANK
                    or any(type(s) is not int or not 0 <= s <= 5 for s in strengths)):
                valid = False
                break
            if RANK[b['match_label']] < RANK[a['match_label']] or strengths[1] < strengths[0]:
                losses.append(rid)
    out['reviewed_core_floor'] = 'passed' if valid and not losses else 'not_proven'
    if not valid or losses:
        out.update(winner='existing_final', hard_regressed_ids=losses,
                   reason='Reviewed challenger withheld: individual Required/Core floor lost or evidence unavailable.')
    return out


def _render_legacy_changes(st: Any, proposal: dict, application_id: int, context: str) -> None:
    changed = [row for row in proposal.get('projects') or [] if row.get('before') != row.get('after')]
    if not changed:
        return
    project = st.selectbox('Project changes', range(len(changed)),
        format_func=lambda index: changed[index].get('project') or 'Project',
        key=f'phase9f_legacy_project_{application_id}_{context}')
    row = changed[project]
    with st.expander('Changes between existing résumé and optimized alternative', expanded=False):
        for label, field in (('Existing fitted résumé', 'before'), ('Optimized alternative', 'after')):
            st.markdown('**' + label + '**')
            for bullet in row.get(field) or []:
                st.write(bullet)

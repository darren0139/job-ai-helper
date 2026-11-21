"""Opt-in native Streamlit UI: compare two actually rendered, like-for-like DOCX files."""
from __future__ import annotations

from pathlib import Path

from tailoring.phase9f_v364_decision_explorer import resume_terms
from tailoring.phase9f_v365_jd_evidence import source_wording_label
from typing import Any


def render_verified_best_of(st: Any, *, application_id: int, generation_id: str,
                            projects: dict | None, fit: dict | None,
                            baseline_report: dict, raw_jd_text: str,
                            execution: dict | None, decision: dict | None,
                            repo_root: Path) -> None:
    with st.expander('Verified best-of — compare actual one-page candidates (opt-in)', expanded=False):
        st.caption('A = current fitted DOCX. B = separate V2.6 bounded joint-bullet candidate with the same project set and bullet counts. '
                   'A remains the saved/default résumé. This does NOT run V2.9 variable-count allocation, '
                   're-run paid generation, or approve B automatically.')
        if not isinstance((baseline_report.get('meta') or {}).get('document_analysis'), dict):
            st.info('Best-of cannot run for this saved generation: the Initial résumé analysis was reconstructed from a profile, not verified from the original DOCX.')
            st.caption('This is a provenance prerequisite, not a fitting or bullet-allocation setting. '
                       'For a new test, start by analysing the actual Initial résumé DOCX against this JD, '
                       'then create a fresh application/generation from that document-grounded analysis. '
                       'Re-fitting this historical generation cannot retroactively create the missing receipt. '
                       'The existing saved résumé is unchanged.')
            return
        if not isinstance(projects, dict) or not isinstance(fit, dict) or not generation_id:
            st.info('Save and fit a normal generation first.')
            return
        from tailoring.phase9f_project_bullet_sources_v2_3 import _bound_candidate_sources
        from tailoring.phase9f_final_evidence_comparison_v2_4 import build_final_evidence_audit, _docx_path
        from tailoring.phase9f_joint_resume_optimizer_v2_6 import (build_joint_optimization, materialize_verified_candidate)
        candidates, reason = _bound_candidate_sources(execution, decision)
        if candidates is None:
            st.info('Frozen evidence source unavailable: '+str(reason))
            return
        audit = build_final_evidence_audit(projects, fit, candidates, repo_root=repo_root,
                  application_id=application_id, expected_generation_id=generation_id)
        if not audit.get('verified'):
            st.info('Verified fitted document unavailable: '+str(audit.get('notice') or ''))
            return
        proposal = build_joint_optimization(audit, projects)
        if proposal.get('status') != 'candidate':
            st.info('Existing fitted résumé is retained. No higher-coverage proposal found under the bounded search: '
                    +str(proposal.get('reason') or ''))
            return
        a, b = st.columns(2)
        a.metric('Existing JD coverage proxy', proposal['baseline_points'])
        b.metric('Proposed JD coverage proxy', proposal['proposed_points'])
        st.caption('These are diagnostic proxies only. Only fresh native Phase 8 actual-document Job Match scores decide the winner.')
        with st.expander('Inspect proposed changes and saved JD links', expanded=False):
            changes = [row for row in proposal.get('projects', []) if row.get('before') != row.get('after')]
            if changes:
                which = st.selectbox('Project with changed bullets', list(range(len(changes))),
                    format_func=lambda n: changes[n]['project'],
                    key=f'phase9f_bestof_project_{application_id}_{generation_id}')
                changed = changes[which]
                jd_labels = {}
                for ranked in projects.get('candidate_project_ranking') or []:
                    if isinstance(ranked, dict):
                        for req in ranked.get('requirement_matches') or []:
                            if isinstance(req, dict) and req.get('requirement_id') and req.get('requirement_text'):
                                jd_labels[str(req['requirement_id'])] = str(req['requirement_text'])
                old_col, new_col = st.columns(2)
                with old_col:
                    st.markdown('**Existing fitted résumé**')
                    for bullet in changed.get('before') or []:st.write('• '+str(bullet))
                with new_col:
                    st.markdown('**Optimized alternative**')
                    for i, bullet in enumerate(changed.get('after') or []):
                        st.write('• '+str(bullet))
                        owner=(changed.get('sources') or [])
                        rids=(changed.get('supported_jd_ids') or [])
                        if i < len(owner):st.caption('Source · ' + source_wording_label(owner[i]))
                        if i < len(rids):
                            st.caption('Saved JD evidence: '+('; '.join(
                                jd_labels.get(str(rid), 'Requirement text unavailable') for rid in rids[i]) or 'No strong JD link recorded'))
                st.caption('Gained JD IDs: '+(', '.join(proposal.get('gained_jd_ids') or []) or 'none')+
                           ' · Lost JD IDs: '+(', '.join(proposal.get('lost_jd_ids') or []) or 'none'))
                st.caption('These are saved selection links. Native Job Match results appear after document verification.')
            else:
                st.caption('No project-bullet differences recorded in this proposal.')
        reviewed = True
        if proposal.get('requires_base_review'):
            reviewed = st.checkbox('I reviewed the proposed Base-only bullets for factual accuracy.',value=False,
                                   key=f'phase9f_bestof_review_{application_id}_{generation_id}')
        allow = st.checkbox('I authorize creating a separate unapproved DOCX/PDF and scoring it against the exact frozen JD.',
                            value=False,key=f'phase9f_bestof_consent_{application_id}_{generation_id}')
        # Reruns must not show stale best-of scores for a changed JD or selected
        # starting-source receipt even if the output DOCX path is unchanged.
        import hashlib, json
        binding = hashlib.sha256(json.dumps({
            'raw_jd_text': raw_jd_text,
            'baseline_stable': (baseline_report.get('stable_analysis') or {}).get('input_fingerprint'),
            'selected_base': (baseline_report.get('meta') or {}).get('selected_base_analysis'),
            'document_authority': (baseline_report.get('meta') or {}).get('document_analysis'),
        }, sort_keys=True, default=str).encode('utf-8')).hexdigest()[:12]
        state_key = f'phase9f_bestof_result_{application_id}_{generation_id}_{audit["docx_sha256"]}_{binding}'
        if st.button('Generate candidate and verify best-of',disabled=not (allow and reviewed),
                     key=f'phase9f_bestof_run_{application_id}_{generation_id}'):
            from database.tailoring_generation_control import get_tailoring_generation
            from tailoring.phase8_verification import build_phase8_verification
            from tailoring.phase9f_verified_best_of_v291 import evaluate_existing_vs_candidate
            docx, error = _docx_path(fit,repo_root,application_id)
            if docx is None:
                st.error('Scoped fitted DOCX unavailable: '+error)
            else:
                saved=get_tailoring_generation(application_id,generation_id)
                with st.spinner('Generating a separate one-page candidate and comparing actual-document scores...'):
                    result=evaluate_existing_vs_candidate(audit=audit,projects=projects,fit=fit,
                        generation=saved,baseline_report=baseline_report,raw_jd_text=raw_jd_text,
                        source_docx=docx,repo_root=repo_root,application_id=application_id,
                        generator=materialize_verified_candidate,scorer=build_phase8_verification,
                        optimizer=lambda a,p:proposal,base_reviewed=reviewed)
                st.session_state[state_key]=result
        result=st.session_state.get(state_key)
        if not isinstance(result,dict):return
        status=result.get('status')
        if status!='verified':
            st.warning('No verified challenger promotion. Existing résumé remains untouched: '+resume_terms(result.get('reason') or status))
            return
        winner=result['winner']
        c,d,e=st.columns(3)
        c.metric('Existing fitted résumé · Job Match',result['original_score'])
        d.metric('Optimized alternative · Job Match',result['candidate_score'])
        e.metric('Difference',result['delta'])
        if winner=='optimized_candidate':
            st.success('Recommended résumé is the optimized alternative. ' + resume_terms(result['reason']))
        else:
            st.info('Keep the existing fitted résumé. ' + resume_terms(result['reason']))
        st.caption(result['claim']+' · scorer: '+result['scoring_version'])
        if result.get('improved_vs_both_baselines'):
            st.success('The recommended résumé also scores higher than both frozen Initial and Selected Base analyses without Required/Core regressions.')
        else:
            st.info('Improvement against BOTH Initial and Selected Base is not established; the best-of decision is limited to the two candidates.')
        if result.get('baseline_deltas'):
            st.caption('Winner minus baseline scores: '+', '.join(
                name+' '+f'{delta:+g}' for name,delta in sorted(result['baseline_deltas'].items())))
        st.caption('This does not prove improvement versus the Initial/Selected Base résumé or factual quality. '
                   'Use Phase 8 for that verdict, and review the recommended résumé before approval.')
        if winner == 'optimized_candidate':
            path=Path(result.get('candidate_file') or '')
            pdf=Path(result.get('candidate_pdf') or '')
            if (path.is_file() and pdf.is_file() and path.suffix.lower()=='.docx'
                    and result.get('candidate_docx_sha256') == __import__('hashlib').sha256(path.read_bytes()).hexdigest()):
                st.download_button('Download recommended résumé (unapproved DOCX)', data=path.read_bytes(),
                    file_name=path.name,mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    key=f'phase9f_bestof_download_{application_id}_{generation_id}')
                st.download_button('Download recommended résumé PDF',data=pdf.read_bytes(),file_name=pdf.name,
                    mime='application/pdf',key=f'phase9f_bestof_pdf_{application_id}_{generation_id}')
                st.warning('The recommended résumé is a separate unapproved file.')

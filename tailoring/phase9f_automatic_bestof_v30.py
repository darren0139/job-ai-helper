"""Non-LLM automatic best-of of two *actual* fitted DOCX files, not profiles.

No Initial DOCX provenance is asserted when it is absent. Candidate comparison
is based on the same native document-grounded scorer for both files. Candidate
B is a separate unapproved file; never overwrites an application generation.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable
import math

VERSION = 'phase9f-automatic-bestof-v3.0-bounded-a-b-v1'
HARD = {'required','core','deal_breaker'}
RANK = {'none':0, 'weak':1, 'transferable':2, 'direct':3}


def hold(message: str, *, winner: str='existing_final', status: str='withheld') -> dict[str, Any]:
    return {'version': VERSION, 'status':status, 'winner':winner,
            'reason':message, 'candidate_approved':False,
            'initial_improvement_verified':False, 'selected_base_improvement_verified':False}


def _rows(score: Any) -> tuple[dict[str, Any] | None, str]:
    if not isinstance(score, dict) or not score.get('docx_sha256') or not score.get('actual_docx_evidence'):
        return None, 'Missing actual-document authority.'
    if score.get('claim_review_required_count') != 0:
        return None, 'Claim-lineage is missing or requires review.'
    version=score.get('scoring_version');value=score.get('deterministic_alignment_score')
    if not isinstance(version,str) or not version or isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value) or not 0<=value<=100:
        return None, 'Missing or invalid scorer identity/score.'
    reqs=score.get('canonical_requirements')
    if not isinstance(reqs,list) or not reqs:
        return None, 'Empty canonical JD requirement rows.'
    result={}
    for row in reqs:
        if not isinstance(row,dict):return None,'Malformed canonical requirement.'
        rid=row.get('requirement_id');importance=str(row.get('importance') or '').casefold();match=str(row.get('match_label') or '').casefold()
        if not isinstance(rid,str) or not rid or rid in result or not importance or match not in RANK:
            return None,'Duplicate, missing or invalid requirement identity.'
        result[rid]=(importance,match)
    return {'score':float(value),'version':version,'requirements':result,'sha256':score['docx_sha256']},''


def compare_document_candidates(*, candidate_a: dict, candidate_b: dict) -> dict[str,Any]:
    """Choose B only if real-document evidence improves with zero hard losses."""
    a,e=_rows(candidate_a)
    if e:return hold('Existing fitted DOCX is not safely scoreable: '+e,winner='none')
    b,e=_rows(candidate_b)
    if e:return {**hold('Challenger rejected: '+e),'a_score':a['score']}
    if a['version']!=b['version'] or a['requirements'].keys()!=b['requirements'].keys():
        return hold('Different native scorer version or JD requirement identities.')
    if any(a['requirements'][rid][0]!=b['requirements'][rid][0] for rid in a['requirements']):
        return hold('JD Required/Core/Preferred classification changed between candidates.')
    losses=sorted(rid for rid,(kind,match) in a['requirements'].items()
        if kind in HARD and RANK[b['requirements'][rid][1]]<RANK[match])
    delta=round(b['score']-a['score'],6)
    winner='optimized_candidate' if delta>0 and not losses else 'existing_final'
    reason=('B has a higher native actual-DOCX score with no Required/Core loss.' if winner=='optimized_candidate'
            else 'Candidate B loses Required/Core strength; keep A.' if losses
            else 'Scores tie; keep A.' if delta==0 else 'Candidate B scores lower; keep A.')
    return {'version':VERSION, 'status':'verified','winner':winner,'reason':reason,
            'a_score':a['score'],'b_score':b['score'],'delta':delta,
            'scoring_version':a['version'],'hard_regressed_ids':losses,
            'a_docx_sha256':a['sha256'],'b_docx_sha256':b['sha256'],
            'candidate_approved':False,'initial_improvement_verified':False,
            'selected_base_improvement_verified':False,
            'claim':'Best of the two checked actual-DOCX candidates, not an Initial/Selected Base improvement or global optimum.'}


def _jd_identity(baseline_report: dict, raw_jd_text: str) -> tuple[set[str] | None,str]:
    if not isinstance(baseline_report,dict) or not isinstance(raw_jd_text,str) or not raw_jd_text.strip():
        return None,'Saved frozen JD or baseline report is unavailable.'
    saved=baseline_report.get('raw_jd_text')
    if isinstance(saved,str) and saved.strip() and saved.replace('\r\n','\n').strip()!=raw_jd_text.replace('\r\n','\n').strip():
        return None,'Stored JD is not identical to the frozen comparison JD.'
    stable=baseline_report.get('stable_analysis') or {}
    rows=stable.get('canonical_requirements')
    if not isinstance(rows,list) or not rows:return None,'Frozen JD requirement list is absent.'
    identities=[]
    for row in rows:
        if not isinstance(row,dict) or not isinstance(row.get('requirement_id'),str) or not row['requirement_id']:
            return None,'Invalid frozen JD requirement row.'
        identities.append(row['requirement_id'])
    if len(set(identities))!=len(identities):return None,'Duplicate frozen JD requirement IDs.'
    return set(identities),''


def native_document_score(*, docx_path: Path, generation_state: dict,
                          baseline_report: dict, raw_jd_text: str,
                          expected_sha256: str) -> dict:
    """Same direct DOCX document analysis + claim reconciliation as native Phase 8.

    In legacy mode this is specifically NOT an invented Initial-vs-Final Phase 8
    receipt. Both A and B go through this same native document-based path.
    """
    docx=Path(docx_path).resolve()
    if not docx.is_file() or sha256(docx.read_bytes()).hexdigest()!=expected_sha256:
        raise ValueError('Actual DOCX digest differs from saved final content.')
    from parse import read_resume_docx
    from tailoring.document_grounded_analysis import analyze_actual_resume_against_jd
    from tailoring.jd_user_input_overrides import apply_application_session_jd_user_inputs
    from tailoring.phase8_verification import build_final_resume_profile, audit_claim_lineage
    from tailoring.phase8_requirement_reconciliation import reconcile_final_requirement_matches
    from tailoring.final_scoring_seed import build_final_scoring_seed
    from analysis_stability.stable_evidence_scoring import compute_deterministic_alignment
    before=baseline_report.get('stable_analysis') or {}
    frozen_ids,reason=_jd_identity(baseline_report,raw_jd_text)
    if frozen_ids is None:raise ValueError(reason)
    resume_text=read_resume_docx(str(docx),preserve_complete_text=True)
    if not isinstance(resume_text,str) or not resume_text.strip():
        raise ValueError('Parser returned empty actual DOCX text.')
    profile=build_final_resume_profile(baseline_report.get('resume_profile') or {},generation_state)
    actual=analyze_actual_resume_against_jd(resume_text=resume_text,jd_text=raw_jd_text,
             jd_profile=baseline_report.get('jd_profile') or {},resume_profile=profile)
    preferred=((baseline_report.get('meta') or {}).get('jd_user_inputs') or {}).get('preferred_requirement_overrides') or []
    actual=apply_application_session_jd_user_inputs(actual,raw_jd_text=raw_jd_text,
            raw_resume_text=resume_text,preferred_requirements=preferred)
    after=actual.get('stable_analysis')
    if not isinstance(after,dict) or not isinstance(after.get('canonical_requirements'),list):
        raise ValueError('Native actual-document scoring receipt is missing.')
    after_ids=[r.get('requirement_id') for r in after['canonical_requirements'] if isinstance(r,dict)]
    if len(after_ids)!=len(after['canonical_requirements']) or set(after_ids)!=frozen_ids:
        raise ValueError('Actual document JD identities differ from the frozen application JD.')
    lineage=audit_claim_lineage(baseline_report.get('resume_profile') or {},generation_state)
    count=lineage.get('claim_review_required_count') if isinstance(lineage,dict) else None
    if isinstance(count,bool) or not isinstance(count,int) or count!=0:
        raise ValueError('Candidate claim lineage is missing or requires manual review.')
    reconciled,receipt=reconcile_final_requirement_matches(before_analysis=before,
        after_analysis=after,generation_state=generation_state,claim_lineage=lineage)
    if not isinstance(reconciled,dict) or not isinstance(reconciled.get('canonical_requirements'),list):
        raise ValueError('Native reconciled document evidence is missing.')
    original={r['requirement_id']:r for r in after['canonical_requirements']}
    limited={r['requirement_id']:r for r in reconciled['canonical_requirements']}
    if set(limited)!=frozen_ids:raise ValueError('Reconciled JD requirement set changed.')
    after=deepcopy(after)
    for row in after['canonical_requirements']:
        bound=limited[row['requirement_id']]
        if RANK.get(str(bound.get('match_label') or '').casefold(),-1)<RANK.get(str(row.get('match_label') or '').casefold(),-1):
            for name in ('match_label','match_value','evidence_strength'):
                row[name]=bound[name]
            row['evidence']=[]
    after.update(compute_deterministic_alignment(after['canonical_requirements']))
    after.update(deepcopy((build_final_scoring_seed(after).get('aggregate') or {})))
    return {'actual_docx_evidence':True,'docx_sha256':expected_sha256,
            'claim_review_required_count':0,
            'scoring_version':after.get('scoring_version'),
            'deterministic_alignment_score':after.get('deterministic_alignment_score'),
            'canonical_requirements':after['canonical_requirements']}



def compare_verified_starting_analyses(*, baseline_report:dict,raw_jd_text:str,
                                      chosen_document_score:dict) -> dict[str,Any]:
    """Informative source baselines; never used to pick the A/B winner.

    A missing historical Initial document is **unavailable**, never treated as
    a zero score or silently reconstructed from an LLM profile.
    """
    out={'initial_comparison_status':'unavailable','selected_base_comparison_status':'unavailable',
         'initial_improvement_verified':False,'selected_base_improvement_verified':False}
    current,error=_rows(chosen_document_score)
    if error or not isinstance(baseline_report,dict):return out
    try:
        from tailoring.document_grounded_analysis import validate_document_report,selected_base_analysis
        from tailoring.job_match_ab_analysis import current_ab_identity
        starting=baseline_report.get('frozen_initial_resume_report') or baseline_report
        if not isinstance(starting,dict):return out
        authority=validate_document_report(starting)
        if authority.get('identity')!=current_ab_identity(raw_jd_text):return out
        initial=starting.get('stable_analysis')
        selected=selected_base_analysis(baseline_report)
    except (ImportError,ValueError,RuntimeError,TypeError,KeyError,AttributeError):
        return out
    baseline_rows={'initial':initial}
    if isinstance(selected,dict):
        if selected.get('same_as_initial') is True:
            baseline_rows['selected_base']=initial
        elif isinstance(selected.get('stable_analysis'),dict):
            baseline_rows['selected_base']=selected['stable_analysis']
    for label,analysis in baseline_rows.items():
        if not isinstance(analysis,dict) or analysis.get('scoring_version')!=current['version']:
            continue
        v=analysis.get('deterministic_alignment_score');rows=analysis.get('canonical_requirements')
        if isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v) or not isinstance(rows,list):continue
        original={}
        for row in rows:
            if not isinstance(row,dict):break
            rid=row.get('requirement_id');kind=str(row.get('importance') or '').casefold();match=str(row.get('match_label') or '').casefold()
            if not isinstance(rid,str) or not rid or rid in original or not kind or match not in RANK:break
            original[rid]=(kind,match)
        if original.keys()!=current['requirements'].keys() or any(
            original[rid][0]!=current['requirements'][rid][0] for rid in original):continue
        required_losses=[rid for rid,(kind,match) in original.items() if kind in HARD
             and RANK[current['requirements'][rid][1]]<RANK[match]]
        delta=round(current['score']-float(v),6)
        status=('regressed' if required_losses or delta<0 else 'improved' if delta>0 else 'maintained')
        out[label+'_comparison_status']=status
        out[label+'_delta']=delta
        out[label+'_baseline_score']=float(v)
        out[label+'_final_score']=current['score']
        out[label+'_scoring_version']=current['version']
        out[label+'_required_core_losses']=required_losses
        out[label+'_improvement_verified']=(status=='improved')
    return out


def evaluate_auto(*, audit:dict, projects:dict, fit:dict, generation:dict,
                  baseline_report:dict, raw_jd_text:str,source_docx:Path,repo_root:Path,
                  application_id:int, optimizer:Callable, generator:Callable,
                  scorer:Callable=native_document_score,base_reviewed:bool=False,
                  guarded_floor_binding:dict|None=None) -> dict[str,Any]:
    """Run at most one A/B trial when explicit Build&Fit creates a new generation."""
    if not isinstance(audit,dict) or audit.get('verified') is not True:return hold('Verified final DOCX audit unavailable.')
    if not isinstance(generation,dict) or str(generation.get('generation_id') or '')!=str(audit.get('generation_id') or ''):
        return hold('Generation source differs from exact final audit.')
    if not isinstance(fit,dict) or fit.get('fit_one_page') is not True or str((generation.get('fit_result') or {}).get('docx_path') or '')!=str(fit.get('docx_path') or ''):
        return hold('A verified one-page fitted generation is required.')
    p=Path(source_docx).resolve();root=Path(repo_root).resolve()
    try:p.relative_to(root/'outputs'/'tailored_resumes')
    except ValueError:return hold('Original fitted DOCX is outside the owned output folder.')
    if not p.is_file() or sha256(p.read_bytes()).hexdigest()!=audit.get('docx_sha256'):
        return hold('Original fitted DOCX digest differs from audit.')
    if not isinstance(projects,dict):return hold('Current saved projects are missing.')
    frozen_ids,reason=_jd_identity(baseline_report,raw_jd_text)
    if reason:return hold(reason)
    proposal=None
    stage='optimize_source_selection'
    try:
        if guarded_floor_binding is not None:
            from tailoring import phase9f_v37_guarded_evaluation as guard
            stage='verify_guarded_source'
            guarded_scope=guard.verify_guarded_source(
                guarded_floor_binding,audit=audit,raw_jd=raw_jd_text,baseline_report=baseline_report,
                fit=fit,output_root=root/'outputs'/'tailored_resumes')
            stage='optimize_source_selection'
        proposal=optimizer(audit,projects)
        # V3.5 deliberately tests a small whole-resume shortlist through the
        # exact same independent one-page/native scorer gate used by V3.0.
        # Never choose a proxy winner without evaluating the actual DOCX.
        if isinstance(proposal,dict) and 'candidate_variants' in proposal:
            if guarded_floor_binding is not None:
                return hold('Guarded review requires one explicit candidate.')
            from tailoring.phase9f_jd_relevance_optimizer_v35 import VERSION as V35_VERSION, MAX_TRIALS
            variants=proposal.get('candidate_variants')
            if (proposal.get('version')!=V35_VERSION or not isinstance(variants,list)
                    or not 1 <= len(variants) <= MAX_TRIALS
                    or any(not isinstance(row,dict) or row.get('version')!=V35_VERSION
                           or row.get('status')!='candidate' or 'candidate_variants' in row
                           for row in variants)):
                return {**hold('Invalid V3.5 bounded independent trial shortlist.'),
                        'verification_stage':'optimize_source_selection',
                        'proposal':proposal,'candidate_verified':False}
            trial_results=[];trial_summary=[]
            for index,variant in enumerate(variants,1):
                trial=evaluate_auto(audit=audit,projects=projects,fit=fit,generation=generation,
                    baseline_report=baseline_report,raw_jd_text=raw_jd_text,
                    source_docx=source_docx,repo_root=repo_root,application_id=application_id,
                    optimizer=lambda _a,_p, v=variant: deepcopy(v),generator=generator,
                    scorer=scorer,base_reviewed=base_reviewed)
                trial_results.append(trial)
                trial_summary.append({'trial':index,'status':trial.get('status'),
                    'winner':trial.get('winner'), 'reason':trial.get('reason'),
                    'verification_stage':trial.get('verification_stage',''),
                    'a_score':trial.get('a_score'), 'b_score':trial.get('b_score'),
                    'native_delta':trial.get('delta'),
                    'proposal_version':variant['version'],
                    'relevance_diagnostics':variant.get('relevance_diagnostics')})
            verified=[row for row in trial_results if row.get('status')=='verified']
            # Different scores for the same SHA/JD/scorer indicate that the
            # comparator was not stable; never promote any challenger then.
            known={(row.get('a_score'),row.get('scoring_version')) for row in verified}
            if len(known)>1:
                final={**hold('Native scorer returned inconsistent results for the identical fitted A.'),
                    'verification_stage':'compare_v35_independent_trials',
                    'proposal':proposal,'candidate_verified':False}
            elif verified:
                winners=[row for row in verified if row.get('winner')=='optimized_candidate']
                final=(max(winners,key=lambda row:(float(row.get('delta') or 0),
                       -float(row.get('b_score') or 0))) if winners else
                       max(verified,key=lambda row:(float(row.get('delta') or 0),
                             -float(row.get('b_score') or 0))))
            elif any(row.get('status') == 'needs_review' for row in trial_results):
                final={**hold('A shortlisted alternative contains new Base-only evidence. Review it before rendering.',
                              status='needs_review'),
                       'verification_stage':'review_shortlist_source_claims',
                       'proposal':proposal,'candidate_verified':False}
            else:
                final={**hold('No V3.5 shortlist trial completed native one-page A/B verification.'),
                    'verification_stage':'compare_v35_independent_trials',
                    'proposal':proposal,'candidate_verified':False}
            # Persist withheld reasons even if another trial was verified.
            return {**final,'v35_trial_receipts':trial_summary,
                    'v35_tested_candidates':len(trial_summary),
                    'v35_verified_candidates':len(verified),
                    'v35_bounded_search':True}
        if not isinstance(proposal,dict) or proposal.get('status')!='candidate':
            return {**hold('No eligible different source-grounded challenger: '+str((proposal or {}).get('reason') or ''),
                           status='withheld' if guarded_floor_binding is not None else 'no_challenger'), 'proposal': proposal}
        if proposal.get('requires_base_review') and not base_reviewed:
            return {**hold('New Base-only evidence needs factual review before automatic candidate creation.',status='needs_review'),
                    'proposal':proposal}
        if guarded_floor_binding is not None:
            stage='verify_guarded_wording'
            guard.verify_guarded_wording(audit,proposal)
        stage='score_original_fitted_a'
        a=scorer(docx_path=p,generation_state=deepcopy(generation),baseline_report=baseline_report,
             raw_jd_text=raw_jd_text,expected_sha256=audit['docx_sha256'])
        va,reason_a=_rows(a)
        if reason_a:return hold('Existing candidate evidence invalid: '+reason_a)
        if va['sha256'] != audit['docx_sha256']:
            return hold('Scored A document digest does not match final evidence audit.')
        if guarded_floor_binding is not None:
            stage='verify_guarded_incumbent'
            guard.verify_guarded_incumbent(guarded_floor_binding,guarded_scope,a)
        stage='materialize_and_render_b'
        output=generator(source_docx=p,audit_sha=audit['docx_sha256'],proposal=proposal,
                         repo_root=root,application_id=application_id,generation_id=str(audit['generation_id']))
        dest=Path(str(output.get('docx_path') or '')).resolve()
        pdf=Path(str(output.get('pdf_path') or '')).resolve()
        owned=root/'outputs'/'tailored_resumes'/'optimizations'
        dest.relative_to(owned)
        pdf.relative_to(owned)
        if (output.get('status')!='generated' or output.get('pages')!=1 or
                not dest.is_file() or dest==p or dest.suffix.lower()!='.docx' or
                not pdf.is_file() or pdf.suffix.lower()!='.pdf'):
            return hold('Challenger DOCX/PDF identity or independent one-page render is invalid.')
        stage='verify_candidate_scoring_state'
        from tailoring.phase9f_verified_best_of_v291 import build_candidate_scoring_state
        candidate_state=build_candidate_scoring_state(original=generation,proposal=proposal,output=output)
        stage='score_actual_challenger_b'
        bsha=sha256(dest.read_bytes()).hexdigest()
        b=scorer(docx_path=dest,generation_state=candidate_state,baseline_report=baseline_report,
             raw_jd_text=raw_jd_text,expected_sha256=bsha)
        vb,reason_b=_rows(b)
        if reason_b:return hold('Challenger scored evidence invalid: '+reason_b)
        if vb['sha256']!=bsha:return hold('Scored B document digest does not match materialized challenger.')
        for value in (a,b):
            requirements=value.get('canonical_requirements') if isinstance(value,dict) else None
            if not isinstance(requirements,list) or {r.get('requirement_id') for r in requirements if isinstance(r,dict)}!=frozen_ids:
                return hold('A/B document requirement identities differ from frozen JD.')
        if guarded_floor_binding is not None:
            stage='verify_guarded_candidate'
            if sha256(dest.read_bytes()).hexdigest()!=bsha:
                return hold('The guarded challenger changed during native scoring.')
            guard.verify_guarded_artifact(proposal,dest,pdf)
            checked=guard.verify_guarded_scores(guarded_floor_binding,guarded_scope,a,b)
            if checked['status']!='verified':
                return {**hold('Guarded review withheld the challenger: '+checked['reason']),
                        'verification_stage':stage,'guarded_review':checked}
        stage='compare_native_a_and_b'
        compared=compare_document_candidates(candidate_a=a,candidate_b=b)
        if guarded_floor_binding is not None and compared.get('status')=='verified':
            compared.update(winner='existing_final',guarded_review=checked,
                            reason='Verified challenger available for explicit review. The existing fitted résumé remains selected.')
        if compared.get('status')=='verified':
            chosen=b if compared.get('winner')=='optimized_candidate' else a
            compared.update(compare_verified_starting_analyses(
                baseline_report=baseline_report,raw_jd_text=raw_jd_text,chosen_document_score=chosen))
            # Evidence attribution from scores already computed by the native gate.
            # This records excerpts and match strength without rerunning the scorer.
            compared['native_document_evidence'] = {
                label: {
                    'docx_sha256': score['docx_sha256'],
                    'pages': pages,
                    'requirements': [
                        {key: row.get(key) for key in (
                            'requirement_id', 'match_label', 'evidence_strength', 'evidence')}
                        for row in score['canonical_requirements']
                    ],
                }
                for label, score, pages in (
                    ('existing', a, fit.get('page_count')), ('alternative', b, output['pages']))
            }
        compared.update({'candidate_file':str(dest),'candidate_pdf':str(output.get('pdf_path') or ''),
             'generation_id':str(audit['generation_id']),'proposal_version':str(proposal.get('version') or ''),
             'proposal':proposal,'a_docx_sha256':audit['docx_sha256'],'b_docx_sha256':bsha,
             'candidate_pdf_sha256':sha256(pdf.read_bytes()).hexdigest()})
        return compared
    except (ValueError,RuntimeError,KeyError,TypeError,ImportError,OSError,AttributeError) as exc:
        # Preserve the *unverified* slate and precise failure point for diagnosis.
        # Never promote B, infer a score, or turn a failed render into evidence.
        return {**hold('Automatic A/B verification stopped safely: '+type(exc).__name__+': '+str(exc)),
                'verification_stage':stage,
                'proposal':proposal if isinstance(proposal,dict) else {},
                'candidate_verified':False}



def verify_fitted_a_against_baselines(*, audit:dict, fit:dict, generation:dict,
            baseline_report:dict, raw_jd_text:str, source_docx:Path,
            scorer:Callable=native_document_score) -> dict[str,Any]:
    """Independent, actual-document A-vs-frozen-baselines receipt for *every* fit.

    Also runs when no V3.1/V3.3 challenger exists. The document and metadata
    identities must agree. Unavailable historical baseline evidence is never
    silently converted to a comparison against the parse-only Base score.
    """
    result={'status':'unavailable', 'reason':'Actual fitted A not yet validated.',
            'initial_improvement_verified':False,'selected_base_improvement_verified':False}
    if not isinstance(audit,dict) or audit.get('verified') is not True:
        return result
    if not isinstance(fit,dict) or fit.get('fit_one_page') is not True:
        return {**result,'reason':'One-page fit receipt unavailable.'}
    if not isinstance(generation,dict) or str(generation.get('generation_id') or '')!=str(audit.get('generation_id') or ''):
        return {**result,'reason':'Generation and verified DOCX audit mismatch.'}
    if str((generation.get('fit_result') or {}).get('docx_path') or '')!=str(fit.get('docx_path') or ''):
        return {**result,'reason':'Generation and fit document paths differ.'}
    path=Path(source_docx).resolve()
    expected=str(audit.get('docx_sha256') or '')
    if not path.is_file() or sha256(path.read_bytes()).hexdigest()!=expected:
        return {**result,'reason':'Actual fitted DOCX digest mismatch.'}
    try:
        current=scorer(docx_path=path,generation_state=deepcopy(generation),
            baseline_report=baseline_report,raw_jd_text=raw_jd_text,
            expected_sha256=expected)
        parsed,reason=_rows(current)
        if reason:return {**result,'reason':'Native fitted A scoring withheld: '+reason}
        if parsed['sha256']!=expected:return {**result,'reason':'Native scorer returned a different DOCX digest.'}
        frozen,reason=_jd_identity(baseline_report,raw_jd_text)
        if frozen is None:return {**result,'reason':reason}
        if set(parsed['requirements'])!=frozen:
            return {**result,'reason':'Native A JD IDs differ from frozen requirements.'}
        compared=compare_verified_starting_analyses(baseline_report=baseline_report,
            raw_jd_text=raw_jd_text,chosen_document_score=current)
        return {'status':'verified','a_score':parsed['score'],
                'a_docx_sha256':expected,'scoring_version':parsed['version'],
                'reason':'Actual fitted DOCX scored; baseline comparisons only where frozen document authorities are comparable.',
                **compared}
    except (ValueError,RuntimeError,KeyError,TypeError,ImportError,OSError,AttributeError) as exc:
        return {**result,'reason':'Native A comparison unavailable: '+type(exc).__name__+': '+str(exc)}

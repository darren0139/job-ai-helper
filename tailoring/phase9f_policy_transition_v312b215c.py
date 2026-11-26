"""Explicit, non-persisting Phase 8 recheck across the B2.15 scope upgrade.

Never changes Phase 9E currentness, the F ledger, saved verification rows,
approval, generation metadata, or optimizer caches. Historical scope is used
only to authenticate the original execution, not to score the new documents.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from copy import deepcopy
from pathlib import Path
from typing import Any

VERSION = 'v312b215c-historical-phase8-preview-v1'
CURRENT_SCORER = 'stable-evidence-v1.16-phase6d20-v312b215-jd-eligibility-v312a17-fullstack-single-row'
OLD_SCORERS = {'stable-evidence-v1.16-phase6d20', 'stable-evidence-v1.16-phase6d20-v312a17-fullstack-single-row'}
SCOPE_FIELDS = {'canonical_requirement_ids', 'canonical_requirement_fingerprint'}
JD_FIELDS = ('library_jd_id', 'canonical_jd_id', 'source_version_id', 'raw_jd_sha256', 'source_application_link')


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str).encode('utf-8')).hexdigest()


def _file_hash(path: Path) -> str:
    _require(path.is_file(), 'The exact fitted DOCX is missing.')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_rows(snapshot: dict) -> dict:
    rows = snapshot.get('canonical_requirements')
    _require(isinstance(rows, list) and bool(rows), 'Canonical JD rows are missing.')
    by_id = {}
    compact = []
    for row in rows:
        _require(isinstance(row, dict), 'Malformed canonical JD row.')
        rid = str(row.get('requirement_id') or '')
        _require(bool(rid) and rid not in by_id, 'Missing or duplicate canonical JD identity.')
        by_id[rid] = row
        compact.append({'requirement_id': rid, 'text': ' '.join(str(row.get('text') or '').split()),
                        'importance': str(row.get('importance') or ''),
                        'atomic_group_id': str(row.get('atomic_group_id') or ''),
                        'group_weight_fraction': row.get('group_weight_fraction')})
    _require(sorted(by_id) == snapshot.get('canonical_requirement_ids'), 'Canonical JD identities do not reproduce.')
    _require(_fingerprint(compact) == snapshot.get('canonical_requirement_fingerprint'), 'Canonical JD fingerprint does not reproduce.')
    return by_id


def classify_transition(*, decision: dict, current_jd: dict, active_scorer: str) -> dict:
    """Bounded first release: exact D-bound, removal-only B2.15 handoffs."""
    _require(active_scorer == CURRENT_SCORER, 'The supported B2.15 scoring policy is not active.')
    _require(decision.get('scope_activation_status') == 'active' and decision.get('current_scope_status') == 'stale', 'An active historical binding is required.')
    historical = decision.get('current_jd_snapshot') or {}
    stored = (decision.get('semantic_identity') or {}).get('current_jd') or {}
    for key in JD_FIELDS:
        _require(bool(stored.get(key)) and historical.get(key) == stored[key] == current_jd.get(key), 'Exact JD binding changed: '+key)
    raw = historical.get('raw_text')
    _require(isinstance(raw, str) and bool(raw.strip()) and raw == current_jd.get('raw_text'), 'Exact JD text changed.')
    _require(hashlib.sha256(raw.encode('utf-8')).hexdigest() == stored.get('raw_jd_sha256'), 'Exact JD text hash does not reproduce.')
    _require(isinstance(historical.get('jd_profile'), dict) and historical['jd_profile'] == current_jd.get('jd_profile'), 'Linked JD profile changed.')
    for key in SCOPE_FIELDS:
        _require(historical.get(key) == stored.get(key), 'Historical JD scope is not bound: '+key)
    old = _canonical_rows(historical)
    new = _canonical_rows(current_jd)
    _require(set(new) < set(old), 'Only a strict removal-only JD eligibility transition is supported.')
    _require(all(old[rid] == row for rid, row in new.items()), 'A surviving canonical requirement changed; scope review is required.')
    stable = (decision.get('effective_starting_comparison') or decision.get('comparison') or {}).get('stable_analysis_snapshot') or {}
    _require(stable.get('scoring_version') in OLD_SCORERS, 'The historical scoring policy is not supported.')
    _require(not stable.get('matching_policy_identity') and not stable.get('effective_requirement_scope'), 'Reviewed or custom requirement scopes need separate migration.')
    stable_rows = stable.get('canonical_requirements') or []
    _require(len(stable_rows) == len(old) and sorted(r.get('requirement_id') for r in stable_rows) == sorted(old), 'Historical scoring scope does not match the bound JD.')
    return {'version': VERSION, 'old_scorer': stable['scoring_version'], 'new_scorer': active_scorer,
            'raw_jd_sha256': stored['raw_jd_sha256'], 'previous_count': len(old), 'current_count': len(new),
            'old_scope_fingerprint': historical['canonical_requirement_fingerprint'],
            'new_scope_fingerprint': current_jd['canonical_requirement_fingerprint'],
            'removed_requirements': [{'requirement_id': rid, 'text': old[rid].get('text'), 'importance': old[rid].get('importance')} for rid in sorted(set(old)-set(new))],
            'surviving_requirement_ids': sorted(new), 'historical_requirement_ids': sorted(old)}


def authenticate_execution(execution: dict, scope: dict) -> None:
    """The old immutable scope is only an ownership/integrity check."""
    identity = execution.get('semantic_identity') or {}
    _require(bool(identity) and _fingerprint(identity) == execution.get('execution_fingerprint'), 'Frozen execution identity is inconsistent.')
    for key in ('application_id', 'confirmation_fingerprint', 'phase9e_decision_fingerprint', 'starting_snapshot_fingerprint'):
        _require(execution.get(key) == scope.get(key), 'Frozen execution differs: '+key)
    for key in ('source', 'exact_jd', 'frozen_content'):
        _require(identity.get(key) == scope.get(key), 'Frozen execution semantic identity differs: '+key)
    evidence = execution.get('evidence_snapshot') or {}
    expected_evidence = identity.get('evidence_snapshot') or {}
    _require(isinstance(evidence.get('rows'), list) and evidence.get('policy_version') == expected_evidence.get('policy_version'), 'Frozen evidence scope is missing.')
    fp = _fingerprint({'policy_version': evidence['policy_version'], 'rows': evidence['rows']})
    _require(fp == evidence.get('snapshot_fingerprint') == execution.get('evidence_snapshot_fingerprint') == expected_evidence.get('snapshot_fingerprint'), 'Frozen evidence content changed.')
    section = execution.get('section_scope') or {}
    expected_section = identity.get('section_scope') or {}
    _require(section.get('scope_fingerprint') == execution.get('section_scope_fingerprint') == expected_section.get('scope_fingerprint') and bool(section.get('scope_fingerprint')), 'Frozen section scope changed.')
    _require(_fingerprint({k: v for k, v in section.items() if k not in {'opportunity', 'selected_evidence', 'scope_fingerprint'}}) == section['scope_fingerprint'], 'Frozen section scope fingerprint does not reproduce.')
    _require(_fingerprint(section.get('selected_evidence') or []) == section.get('selected_evidence_fingerprint') == expected_section.get('selected_evidence_fingerprint'), 'Frozen selected evidence changed.')
    artifact = execution.get('source_artifact') or {}
    expected_artifact = identity.get('source_artifact') or {}
    _require(artifact.get('artifact_type') == 'docx' and isinstance(artifact.get('sha256'), str) and len(artifact['sha256']) == 64 and all(artifact.get(k) == expected_artifact.get(k) for k in ('policy_version', 'artifact_type', 'sha256', 'byte_size')), 'Frozen selected source DOCX identity is missing or inconsistent.')


def authenticate_final(*, generation: dict, prior: dict, snapshot_fingerprint: str, final_sha: str) -> None:
    _require(generation.get('status') in {'draft', 'approved'}, 'Only a fitted draft or approved generation is eligible.')
    _require(prior.get('comparison_valid') is True, 'A prior comparable actual-document receipt is required.')
    for key in ('application_id', 'generation_id'):
        _require(generation.get(key) == prior.get(key), 'Prior document receipt belongs to a different '+key)
    _require(bool(snapshot_fingerprint) and prior.get('verified_generation_snapshot_fingerprint') == snapshot_fingerprint, 'The fitted generation snapshot changed after the prior verification.')
    _require(len(final_sha) == 64 and (prior.get('document_analysis') or {}).get('final_document_sha256') == final_sha, 'The fitted DOCX differs from the prior verification.')
    _require((generation.get('fit_result') or {}).get('fit_one_page') is True and (generation.get('fit_result') or {}).get('page_count') == 1, 'A saved one-page fit is required.')


def build_preview(*, transition: dict, baseline_report: dict, generation: dict, source_artifact: dict, prior: dict) -> dict:
    """Run the existing actual-DOCX Phase 8 engine, without publishing a gate."""
    from tailoring.phase8_verification import build_phase8_verification, build_phase8_generation_snapshot_fingerprint
    from tailoring.phase9f_v364_document_reverify import build_frozen_selected_base_document_report
    _require(not (baseline_report.get('meta') or {}).get('document_analysis'), 'This release supports selected-base handoffs only, not an uploaded Initial document.')
    _require(not ((baseline_report.get('meta') or {}).get('jd_user_inputs') or {}).get('preferred_requirement_overrides'), 'Application-local preferred scope needs separate migration.')
    raw = baseline_report.get('raw_jd_text')
    _require(isinstance(raw, str) and hashlib.sha256(raw.encode('utf-8')).hexdigest() == transition.get('raw_jd_sha256'), 'Frozen baseline JD differs from the transition.')
    path = Path(str((generation.get('fit_result') or {}).get('docx_path') or ''))
    final_sha = _file_hash(path)
    snapshot = build_phase8_generation_snapshot_fingerprint(generation)
    authenticate_final(generation=generation, prior=prior, snapshot_fingerprint=snapshot, final_sha=final_sha)
    _require((prior.get('starting_document_contract') or {}).get('selected_base_docx_sha256') == source_artifact.get('sha256'), 'The prior Selected Base DOCX authority differs.')
    for key in ('before_stable_analysis', 'after_stable_analysis'):
        previous = prior.get(key) or {}
        _require(previous.get('scoring_version') in OLD_SCORERS and sorted(r.get('requirement_id') for r in previous.get('canonical_requirements') or []) == transition['historical_requirement_ids'], 'Prior native receipt does not belong to the historical scoring scope: '+key)
    stable = baseline_report.get('stable_analysis') or {}
    _require(stable.get('scoring_version') == transition['old_scorer'] and sorted(r.get('requirement_id') for r in stable.get('canonical_requirements') or []) == transition['historical_requirement_ids'], 'Frozen baseline scoring scope does not reproduce.')
    sealed, contract = build_frozen_selected_base_document_report(baseline_report=deepcopy(baseline_report), jd_text=raw, source_artifact=source_artifact)
    refresh = contract.get('scoring_scope_refresh') or {}
    _require(refresh.get('removed_ids') == [r['requirement_id'] for r in transition['removed_requirements']] and refresh.get('added_ids') == [] and refresh.get('current_count') == transition['current_count'], 'Actual selected-base scoring scope did not reproduce the transition.')
    result = build_phase8_verification(baseline_report=sealed, generation_state=deepcopy(generation), raw_jd_text=raw)
    _require(result.get('comparison_valid') is True, 'Fresh native Phase 8 comparison is not comparable.')
    for key in ('before_stable_analysis', 'after_stable_analysis'):
        analysis = result.get(key) or {}
        _require(analysis.get('scoring_version') == CURRENT_SCORER and sorted(r.get('requirement_id') for r in analysis.get('canonical_requirements') or []) == transition['surviving_requirement_ids'], 'Native A/B scope or scorer differs: '+key)
    _require((result.get('document_analysis') or {}).get('final_document_sha256') == final_sha == _file_hash(path), 'Fitted DOCX changed during verification.')
    _require(result.get('verified_generation_snapshot_fingerprint') == snapshot, 'Native fitted snapshot identity differs.')
    # Deliberately never publish a normal verification receipt or a ready gate.
    return {'version': VERSION, 'status': 'native_preview_completed', 'transition': deepcopy(transition),
            'application_id': generation['application_id'], 'generation_id': generation['generation_id'],
            'prior_verification_id': prior.get('verification_id'), 'final_docx_sha256': final_sha,
            'selected_base_docx_sha256': contract['selected_base_docx_sha256'],
            'native_comparison': deepcopy(result['comparison']), 'native_verdict': result.get('verdict'),
            'native_claim_review_count': (result.get('claim_lineage') or {}).get('claim_review_required_count'),
            'native_readiness_checks': deepcopy(result.get('approval_readiness_reasons') or {}),
            'native_before_analysis': deepcopy(result['before_stable_analysis']),
            'native_after_analysis': deepcopy(result['after_stable_analysis']),
            'native_job_match_ab': deepcopy(result['job_match_ab']),
            'starting_document_contract': contract, 'approval_ready': False, 'blueprint_ready': False,
            'scope_reconfirmed': False, 'saved_as_phase8': False}


def run_transition_preview(application_id: int, generation_id: str) -> dict:
    """Authenticate through the production readers, then recheck without writes to app records."""
    from analysis_stability.stable_evidence_scoring import SCORING_VERSION
    from database import phase9f_tailoring_execution_manager as manager
    from database.tailoring_verification_manager import get_latest_tailoring_verification
    from tailoring.phase9f_application_confirmation import PHASE9E_PHASE9F_D_EXACT_BINDING_VERSION
    confirmation, decision, exact_jd, _, report = manager._load_execution_inputs(int(application_id))
    _require(decision.get('phase9e_version') == PHASE9E_PHASE9F_D_EXACT_BINDING_VERSION, 'An exact Phase 9F-D handoff is required.')
    transition = classify_transition(decision=decision, current_jd=exact_jd, active_scorer=SCORING_VERSION)
    # Reproduce the old execution scope using the original historical input.
    # Do NOT change the current linked JD or tell any generation/approval path
    # that its binding is current.
    scope = manager.validate_minor_full_execution_scope(application_id=int(application_id), confirmation=confirmation,
        decision=decision, exact_jd=decision['current_jd_snapshot'])
    execution = manager.get_phase9f_tailoring_execution(int(application_id), generation_id=str(generation_id))
    generation = manager.get_tailoring_generation(int(application_id), str(generation_id))
    _require(manager.is_phase9f_normal_lifecycle_execution(execution) and isinstance(generation, dict)
             and manager._normal_generation_matches_context(execution=execution, generation=generation)
             and manager._normal_generation_is_approvable(generation), 'The selected generation is not a completed fit of this frozen execution.')
    authenticate_execution(execution, scope)
    source = manager._resolve_prepared_source_artifact(decision=decision, confirmation=confirmation, expected_identity=execution['source_artifact'])
    baseline = manager.build_effective_tailoring_report(report, decision)
    prior = get_latest_tailoring_verification(int(application_id), str(generation_id))
    _require(isinstance(prior, dict), 'No prior Phase 8 actual-document receipt is available for this fit.')
    return build_preview(transition=transition, baseline_report=baseline, generation=generation, source_artifact=source, prior=prior)


def render_transition_preview(st, *, application_id: int, decision: dict) -> None:
    """No automatic scoring and no state promotion on opening a stale application."""
    from analysis_stability.stable_evidence_scoring import SCORING_VERSION
    from database.jd_library_manager import get_exact_job_description_for_application
    from database.tailoring_generation_control import list_tailoring_generations
    from tailoring.phase9f_application_confirmation import PHASE9E_PHASE9F_D_EXACT_BINDING_VERSION
    if decision.get('phase9e_version') != PHASE9E_PHASE9F_D_EXACT_BINDING_VERSION or decision.get('scope_activation_status') != 'active' or decision.get('current_scope_status') != 'stale':
        return
    try:
        transition = classify_transition(decision=decision, current_jd=get_exact_job_description_for_application(application_id) or {}, active_scorer=SCORING_VERSION)
    except (ValueError, KeyError, TypeError, sqlite3.Error) as exc:
        st.caption('Scoring-policy recheck unavailable: '+str(exc))
        return
    st.subheader('Phase 8 — Scoring policy transition recheck')
    st.info('The exact JD is unchanged. Recheck a previously fitted résumé using the new scoring scope, without replacing the Tailoring Base. Generation and approval remain blocked until the scope is reviewed and rebound.')
    st.caption(f"Canonical requirements: {transition['previous_count']} → {transition['current_count']}. No added or modified surviving requirements.")
    st.dataframe(transition['removed_requirements'], hide_index=True)
    try:
        versions = {str(g['generation_id']): g for g in list_tailoring_generations(application_id)
            if g.get('status') in {'draft', 'approved'} and g.get('phase9e_decision_fingerprint') == decision.get('decision_fingerprint')
            and (g.get('fit_result') or {}).get('fit_one_page') is True}
    except (ValueError, RuntimeError, KeyError, TypeError, sqlite3.Error) as exc:
        st.warning('Fitted history unavailable: '+str(exc))
        return
    if not versions:
        st.info('No fitted historical draft is available for this binding.')
        return
    gid = st.selectbox('Existing fitted version to recheck', list(versions),
        format_func=lambda value: f"{versions[value]['status'].title()} · {value[:8]}", key=f'b215c_preview_generation_{application_id}')
    if st.button('Recheck existing fitted résumé under current scoring policy', key=f'b215c_preview_run_{application_id}'):
        try:
            result = run_transition_preview(application_id, gid)
        except (ValueError, RuntimeError, OSError, KeyError, TypeError, sqlite3.Error) as exc:
            st.error('Recheck withheld: '+str(exc))
            return
        cmp = result['native_comparison']
        cols = st.columns(3)
        cols[0].metric('Selected Base Job Match', cmp['before_score'])
        cols[1].metric('Fitted Job Match', cmp['after_score'], delta=cmp['score_delta'])
        cols[2].metric('Required/Core delta', cmp['required_core_coverage_delta'])
        st.caption('Native verdict: '+str(result['native_verdict'])+' · Preview only; no saved approval or binding changes.')
        if cmp.get('important_regressions'):
            st.warning('Required/Core regression still detected.')
            st.dataframe(cmp['important_regressions'], hide_index=True)
        st.download_button('Download policy transition recheck JSON', data=json.dumps(result, ensure_ascii=False, indent=2, default=str).encode('utf-8'),
            file_name=f'phase8_policy_transition_preview_{application_id}_{gid[:8]}.json', mime='application/json', on_click='ignore', key=f'b215c_preview_download_{application_id}')

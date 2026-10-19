"""Bounded, explicit opt-in development analysis using the native evidence pipeline.

No research namespace cloning, fixture imports, alternate ranker or persistence.
The request-local context is reset even on failure. Published OFF identities stay intact.
"""
from copy import deepcopy
import hashlib
import json
import re

from . import coordinated_policy as policy
from .coordinated_runtime import CONTEXT, review_pending

IDENTITIES = {
    'scoring_version': 'stable-evidence-v1.18-phase6d22',
    'canonical_requirement_decomposition_version': 'jd-atomic-requirement-decomposition-v1.2',
    'coordinated_action_evidence_policy_version': 'coordinated-action-evidence-completeness-v1',
    'coordinated_partial_action_policy_version': 'coordinated-partial-action-credit-v1',
    'capability_none_recovery_policy_version': 'capability-single-row-none-recovery-v1.2',
    'capability_evidence_reselection_policy_version': 'capability-single-row-reselection-v1.1',
    'coordinated_language_version': policy.LANGUAGE_VERSION,
    'partial_action_variant': 'P3',
}


def targeted(row):
    """Also quarantine nearby unsupported coordination, without reinterpreting it."""
    texts = [s.get('raw_parent_text', '') for s in row.get('source_provenance', [])]
    # A profile-only parent is still subject to the gate, but cannot prove raw
    # grounding. Never let absence of a source receipt bypass completeness.
    texts.append(row.get('parent_text') or row.get('text', ''))
    return any(re.search(r'^\s*[\u00b7\u2022]?\s*design\b', text, re.I)
               and re.search(r'\b(?:develop|build)\b', text, re.I)
               and re.search(r'\b(?:maintain|deploy)\b', text, re.I)
               for text in texts)


def canonicalise_coordinated_requirements(jd_profile, raw_jd_text):
    from . import stable_evidence_scoring as n
    token = CONTEXT.set({'filter': None})
    try:
        result = n.canonicalise_requirements(jd_profile, raw_jd_text=raw_jd_text)
        result['canonical_requirement_decomposition_version'] = IDENTITIES['canonical_requirement_decomposition_version']
        return result
    finally:
        CONTEXT.reset(token)


def _evaluate_row(req, proofs, allowed, native_label, profile, raw_resume, acronym):
    from . import stable_evidence_scoring as n
    events = []
    stages = []
    phase = 'keyword_selection'

    def compatible(requirement, record):
        if requirement['requirement_id'] != req['requirement_id']:
            return True
        original = proofs.get(record.get('evidence_id'), {}).get('record')
        admitted = record.get('evidence_id') in allowed and original == record
        events.append({'stage': phase, 'source': record.get('source'),
                       'evidence_id': record.get('evidence_id'), 'admitted': admitted})
        return admitted

    def capture(name, rows):
        nonlocal phase
        phase = name
        for row in rows:
            native = row['match_label']
            selected = row.get('evidence') or []
            record = selected[0] if len(selected) == 1 else {}
            item = proofs.get(record.get('evidence_id'), {})
            admission = item.get('admission', 'REVIEW_REQUIRED')
            original = item.get('record', {})
            valid = (record.get('evidence_id') in allowed
                     and all(record.get(k) == original.get(k)
                             for k in ('source', 'section', 'text', 'evidence_id')))
            capped = native
            if native != 'none' and not valid:
                capped = 'none'  # internal quarantine only; never an effective review label
            elif admission == 'ELIGIBLE_PARTIAL':
                capped = 'none' if native_label == 'none' else policy.cap_label(native, admission)
            api_guard = item.get('proof', {}).get('independent_api_guard') or {}
            if valid and api_guard.get('label') in n.MATCH_VALUES:
                if n.MATCH_VALUES[capped] > n.MATCH_VALUES[api_guard['label']]:
                    capped = api_guard['label']
            stages.append({'stage': name, 'native_label': native, 'capped_label': capped,
                           'selected_evidence': deepcopy(selected), 'admission': admission,
                           'source_verified': valid,
                           'recovery': deepcopy(row.get('capability_none_recovery')),
                           'reselection': deepcopy(row.get('capability_evidence_reselection'))})
            row.update(match_label=capped, match_value=n.MATCH_VALUES[capped])
        return rows

    token = CONTEXT.set({'filter': compatible})
    try:
        keyword = n.build_deterministic_keyword_match(requirements=[req], acronym_map=acronym,
            resume_profile=profile, raw_resume_text=raw_resume)
        phase = 'link_selection'
        rows, _ = n.link_requirement_matches([req], keyword, acronym,
            resume_profile=profile, raw_resume_text=raw_resume)
        rows = capture('linked', rows)
        rows, _ = n.apply_structured_requirement_matches(rows, resume_profile=profile, raw_resume_text=raw_resume)
        rows = capture('structured', rows)
        rows, _ = n.validate_linked_matches(rows)
        rows = capture('validated_lexical_cap', rows)
        phase = 'single_row_reselection'
        index = n.build_resume_evidence_index(profile, raw_resume)
        rows, _ = n._apply_capability_single_row_reselection(rows, evidence_index=index, acronym_map=acronym)
        rows = capture('reselected', rows)
        rows = n.apply_taxonomy_caps_to_requirements(rows, retrieval_mode_override='off')
        rows = capture('capability_capped', rows)
        phase = 'none_recovery'
        rows, _ = n._apply_capability_none_recovery(rows, evidence_index=index, acronym_map=acronym)
        rows = capture('recovered', rows)
        rows = capture('post_recovery_invariant', rows)
        return rows[0], stages, events, keyword
    finally:
        CONTEXT.reset(token)


def build_coordinated_analysis(**inputs):
    from . import stable_evidence_scoring as n
    if inputs.get('retrieval_mode_override') not in (None, 'off', 'lexical'):
        raise ValueError('Coordinated development evaluation supports offline matching only')
    inputs = deepcopy(inputs)
    inputs['retrieval_mode_override'] = 'off'
    profile = inputs.get('resume_profile') or {}
    raw_resume = inputs.get('raw_resume_text', '')
    raw_jd = inputs.get('raw_jd_text', '')
    canonical = canonicalise_coordinated_requirements(inputs['jd_profile'], raw_jd)
    index = n.build_resume_evidence_index(profile, raw_resume)
    # Rebuild keyword proposals for the corrected geometry using the native selector.
    inputs['keyword_match'] = n.build_deterministic_keyword_match(
        requirements=canonical['requirements'], acronym_map=canonical['acronym_map'],
        resume_profile=profile, raw_resume_text=raw_resume)
    token = CONTEXT.set({'filter': None})
    try:
        unchecked = n.build_stable_analysis(**inputs)
    finally:
        CONTEXT.reset(token)
    out = deepcopy(unchecked)
    rows = []
    for req in unchecked['canonical_requirements']:
        if not targeted(req):
            rows.append(req)
            continue
        obligation = policy.prior.ground_to_raw_jd(policy.prior.extract_obligation(req), raw_jd)
        if obligation.get('conjunction') != 'AND':
            obligation.update(status='UNSUPPORTED', reason='outside_admitted_three_action_AND_grammar')
        proofs = {}
        for record in index:
            proof = policy.detect(obligation, record, index)
            # Restrict action ownership to the original project/experience record.
            admission = policy.eligibility(obligation, proof, 'P3')
            if record.get('section') not in ('projects', 'experience'):
                admission = 'REVIEW_REQUIRED'
            if not n._evidence_source_is_requirement_compatible(req, record):
                admission = 'REVIEW_REQUIRED'
            proofs[record['evidence_id']] = {'record': record, 'proof': proof, 'admission': admission}
        complete = {key for key, item in proofs.items() if item['admission'] == 'COMPLETE'}
        allowed = complete or {key for key, item in proofs.items() if item['admission'] == 'ELIGIBLE_PARTIAL'}
        native = req['match_label']
        stages = []
        events = []
        keyword = {}
        result = deepcopy(req)
        disposition = 'REVIEW_REQUIRED'
        if allowed:
            result, stages, events, keyword = _evaluate_row(req, proofs, allowed, native,
                                                          profile, raw_resume, canonical['acronym_map'])
            selected = result.get('evidence') or []
            if len(selected) == 1:
                disposition = proofs.get(selected[0].get('evidence_id'), {}).get('admission', 'REVIEW_REQUIRED')
            elif result['match_label'] == 'none':
                disposition = 'COMPLETE_NATIVE_NONE' if complete else 'ELIGIBLE_PARTIAL_NATIVE_NONE'
        if disposition == 'REVIEW_REQUIRED':
            # No unchecked credit or numeric zero escapes the quarantine.
            result.update(match_label=None, match_value=None, evidence_strength=None, evidence=[])
        result['coordinated_action_receipt'] = {
            'policy_identities': deepcopy(IDENTITIES), 'obligation': obligation,
            'proofs': proofs, 'disposition': disposition,
            'native_label': native, 'capped_label': result['match_label'],
            'native_selected_evidence': deepcopy(req.get('evidence', [])),
            'selected_evidence': deepcopy(result.get('evidence', [])),
            'stages': stages, 'compatibility_events': events, 'keyword_proposals': keyword,
            'parent_allocation': result['group_weight_fraction'],
            'synthetic_parent_contribution': (None if result['match_value'] is None else
                                             result['match_value'] * result['group_weight_fraction']),
        }
        rows.append(result)
    out['canonical_requirements'] = rows
    # Replace all aggregate fields together; do not retain unchecked percentages.
    for key in n.compute_deterministic_alignment([]):
        out.pop(key, None)
    out.update(n.compute_deterministic_alignment(rows,
        bullet_quality_score=inputs.get('bullet_quality_score', 0),
        structure_score=inputs.get('structure_score', 0)))
    out.update(IDENTITIES, development_preview_only=True,
               score_publication_status=('WITHHELD_PENDING_POLICY_REVIEW' if review_pending(rows)
                                         else 'DEVELOPMENT_PREVIEW_GOVERNED'))
    out['canonicalisation_debug']['canonical_requirement_decomposition_version'] = IDENTITIES['canonical_requirement_decomposition_version']
    for field, identity in (('capability_none_recovery', 'capability_none_recovery_policy_version'),
                            ('capability_evidence_reselection', 'capability_evidence_reselection_policy_version')):
        out[field]['native_policy_version'] = out[field]['policy_version']
        out[field]['policy_version'] = IDENTITIES[identity]
    out['input_fingerprint'] = hashlib.sha256(json.dumps({
        'native_fingerprint': unchecked['input_fingerprint'], 'identities': IDENTITIES,
        'evidence_index': index, 'canonical_rows': canonical['requirements'],
    }, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()
    return out

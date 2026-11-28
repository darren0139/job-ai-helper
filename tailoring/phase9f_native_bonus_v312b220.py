"""Native bonus coverage over independently bound document analyses."""
from hashlib import sha256
from io import BytesIO
import re

from analysis_stability.stable_evidence_scoring import IMPORTANCE_WEIGHTS, MATCH_VALUES, requirement_is_score_eligible
from tailoring.document_grounded_analysis import DOCUMENT_ANALYSIS_VERSION, text_fingerprint
from tailoring.job_match_ab_analysis import current_ab_identity
from tailoring.phase9e_blueprint_selection import fingerprint_value
from tailoring.phase9f_starting_source_ranking import canonical_requirement_scope_fingerprint
from tailoring.phase9f_v37_bonus_coverage import BONUS, bonus_catalog
from tailoring.phase9f_v37_hard_floor import HARD, compare_evidence_floor

VERSION = 'v312b220-native-bonus-coverage-v1'
SELECTION_POLICY = 'v312b220c-native-bonus-selection-v1'


def unavailable(reason):
    return {'version': VERSION, 'status': 'unavailable', 'reason': reason}


def _digest(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def _geometry(rows):
    fields = ('text', 'importance', 'parent_text', 'atomic_group_id', 'scoring_parent_occurrence_id',
              'group_weight_fraction', 'source_provenance', 'score_eligible', 'evidence_eligible')
    return {r['requirement_id']: [r.get(k) for k in fields] for r in rows}


def _observation(native, weight):
    label, strength = native.get('match_label'), native.get('evidence_strength')
    evidence = native.get('evidence') or []
    if (label not in MATCH_VALUES or native.get('match_value') != MATCH_VALUES[label]
            or type(strength) is not int or not 0 <= strength <= 5
            or (label == 'none' and strength != 0)
            or (label != 'none' and (not strength or not evidence or any(
                not isinstance(item, dict) or not isinstance(item.get('text'), str)
                or not item['text'].strip() for item in evidence)))):
        return None
    return {'match_label': label, 'evidence_strength': strength,
            'evidence': evidence if label != 'none' else [],
            'earned_units': round(weight * MATCH_VALUES[label], 6)}


def compare_native_bonus(before, after, *, raw_jd, before_document, after_document, identity):
    """Project current native document rows onto their original JD allocations."""
    try:
        if (not raw_jd.strip() or identity != current_ab_identity(raw_jd)
                or any(not _digest(doc) for doc in (before_document, after_document))
                or any(s['scoring_version'] != identity['scoring_version'] for s in (before, after))):
            return unavailable('Current JD, scorer or exact document identities are unavailable.')
        left, right = (s['canonical_requirements'] for s in (before, after))
        geometry = _geometry(left)
        if not geometry or len(geometry) != len(left) or len(geometry) != len(right) or geometry != _geometry(right):
            return unavailable('Canonical JD requirements or their original allocations differ.')
        catalog = bonus_catalog(left, raw_jd, expected_jd=raw_jd)
        right_rows = {r['requirement_id']: r for r in right}
        requirements = []
        for native in left:
            rid = native['requirement_id']
            req = catalog[rid]
            if req['importance'] not in BONUS:
                continue
            excluded = not requirement_is_score_eligible(native) or native.get('evidence_eligible') is False
            row = {**req, 'requirement_id': rid, 'status': 'excluded' if excluded else 'unavailable'}
            if req['eligible']:
                a, b = (_observation(r, req['weight']) for r in (native, right_rows[rid]))
                if a is not None and b is not None:
                    row.update(status='verified', before=a, after=b,
                               delta_units=round(b['earned_units'] - a['earned_units'], 6))
            requirements.append(row)
        lanes = {}
        for lane in BONUS:
            rows = [r for r in requirements if r['importance'] == lane and r['status'] != 'excluded']
            if any(r['status'] == 'unavailable' for r in rows):
                lanes[lane] = {'status': 'unavailable'}
            elif not rows:
                lanes[lane] = {'status': 'not_applicable'}
            else:
                available = round(sum(r['weight'] for r in rows), 6)
                a, b = (round(sum(r[side]['earned_units'] for r in rows), 6) for side in ('before', 'after'))
                lanes[lane] = {'status': 'applicable', 'available_units': available,
                               'before_units': a, 'after_units': b, 'delta_units': round(b - a, 6)}
        return {'version': VERSION, 'status': 'verified', 'jd_sha256': text_fingerprint(raw_jd),
                'native_identity': identity, 'before_docx_sha256': before_document,
                'after_docx_sha256': after_document, 'lanes': lanes, 'requirements': requirements}
    except (KeyError, TypeError, ValueError, AttributeError):
        return unavailable('Native document evidence or canonical JD metadata is incomplete.')


def phase8_native_bonus(receipt, *, raw_jd, final_path, selected_base_sha256):
    """Verify sealed Phase 8 scores and the current fitted/frozen source binding."""
    try:
        contract = receipt.get('starting_document_contract') or receipt['selected_base_bonus_binding']
        doc = receipt['document_analysis']
        selected = receipt['selected_base_analysis']
        before, after = selected['stable_analysis'], receipt['after_stable_analysis']
        base_auth, final_auth = selected['document_analysis'], doc['final']
        jd_digest = text_fingerprint(raw_jd)
        identity = current_ab_identity(raw_jd)
        if (receipt.get('comparison_valid') is not True or receipt.get('fit_one_page') is not True
                or (receipt.get('claim_lineage') or {}).get('claim_review_required_count') != 0
                or not (receipt.get('selected_base_job_match_ab') or receipt['job_match_ab']).get('comparable')
                or contract['mode'] not in ('selected_base_docx_only', 'selected_base_bonus_binding')
                or not _digest(selected_base_sha256) or contract['selected_base_docx_sha256'] != selected_base_sha256
                or contract['selected_base_resume_text_sha256'] != base_auth['resume_text_sha256']
                or contract['selected_base_document_analysis_fingerprint'] != base_auth['fingerprint']
                or sha256(final_path.read_bytes()).hexdigest() != doc['final_document_sha256']):
            return unavailable('The fitted DOCX or frozen Selected Base DOCX binding could not be verified.')
        for authority, stable in ((base_auth, before), (final_auth, after)):
            if (authority['version'] != DOCUMENT_ANALYSIS_VERSION
                    or authority['input_authority'] != 'ACTUAL_RESUME_DOCUMENT'
                    or authority['identity'] != identity or authority['jd_text_sha256'] != jd_digest
                    or not _digest(authority['resume_text_sha256'])
                    or authority['fingerprint'] != fingerprint_value({k: v for k, v in authority.items() if k != 'fingerprint'})
                    or authority['stable_analysis_fingerprint'] != fingerprint_value(stable)
                    or authority['canonical_requirement_fingerprint'] != canonical_requirement_scope_fingerprint(stable['canonical_requirements'])):
                return unavailable('Saved document analysis is stale or its native evidence has changed.')
        return compare_native_bonus(before, after, raw_jd=raw_jd, before_document=selected_base_sha256,
                                    after_document=doc['final_document_sha256'], identity=identity)
    except (OSError, KeyError, TypeError, ValueError, AttributeError):
        return unavailable('The selected verification lacks compatible actual DOCX receipts.')


def bind_selected_base_docx(authority, artifact):
    """Bind an existing Selected Base analysis to the actual frozen DOCX bytes."""
    from parse import read_resume_docx

    content = artifact['artifact_bytes']
    digest = sha256(content).hexdigest()
    if (artifact['artifact_type'] != 'docx' or digest != artifact['sha256']
            or len(content) != artifact['byte_size']):
        raise ValueError('Frozen Selected Base DOCX identity is inconsistent.')
    text_digest = text_fingerprint(read_resume_docx(BytesIO(content), preserve_complete_text=True))
    if text_digest != authority['resume_text_sha256']:
        raise ValueError('Frozen Selected Base DOCX text differs from native analysis.')
    return {'mode': 'selected_base_bonus_binding', 'selected_base_docx_sha256': digest,
            'selected_base_resume_text_sha256': text_digest,
            'selected_base_document_analysis_fingerprint': authority['fingerprint']}


def native_hard_floors(before, after):
    """Check scored, evidence-bound hard rows after the caller verifies scope."""
    new = {r['requirement_id']: r for r in after}
    checks = []
    for row in before:
        if row['importance'] not in HARD or not requirement_is_score_eligible(row):
            continue
        other = new.get(row['requirement_id'])
        fraction = row.get('group_weight_fraction')
        weight = (IMPORTANCE_WEIGHTS[row['importance']] * fraction
                  if type(fraction) in (int, float) and 0 < fraction <= 1 else None)
        a = _observation(row, weight) if weight is not None else None
        b = _observation(other, weight) if other and weight is not None else None
        checks.append({'requirement_id': row['requirement_id'], 'text': row['text'],
                       'importance': row['importance'], 'source_spans': row.get('source_provenance') or [],
                       'status': compare_evidence_floor(a, b) if a and b else 'unavailable',
                       'before': a, 'after': b})
    return checks


def shortlist_priorities(baseline, raw_jd):
    """Use original allocations for distinct saved links in the proxy solver."""
    if baseline.get('raw_jd_text') != raw_jd:
        return None
    rows = (baseline.get('stable_analysis') or {}).get('canonical_requirements') or []
    catalog = bonus_catalog(rows, raw_jd, expected_jd=raw_jd)
    hard = {r['requirement_id']: catalog[r['requirement_id']]['weight'] for r in rows
            if r['importance'] in HARD and requirement_is_score_eligible(r)}
    return {'required_core_saved_links': hard, **{
        lane + '_saved_links': {rid: row['weight'] for rid, row in catalog.items()
                                 if row['importance'] == lane and row['eligible']}
        for lane in ('preferred', 'supporting')}} if catalog else None


def native_selection(before, after, bonus, native_delta):
    """Require individual hard floors, then prefer verified coverage gains."""
    verified = bonus['status'] == 'verified'
    checks = native_hard_floors(before['canonical_requirements'], after['canonical_requirements']) if verified else []
    changes = [bonus['lanes'][k].get('delta_units', 0) for k in ('preferred', 'supporting')] if verified else [0, 0]
    if not verified or any(row['status'] == 'unavailable' for row in checks):
        decision = 'unavailable'
    elif any(row['status'] == 'regressed' for row in checks):
        decision = 'hard_regression'
    elif any(row['status'] == 'improved' for row in checks):
        decision = 'hard_improvement'
    elif (all(lane['status'] != 'unavailable' for lane in bonus['lanes'].values())
            and min(changes) >= 0 and max(changes) > 0):
        decision = 'bonus_improvement'
    else:
        decision = 'retain_incumbent'
    return {'policy': SELECTION_POLICY, 'decision': decision, 'hard_floors': checks,
            'hard_coverage_delta_units': round(sum(row['after']['earned_units'] - row['before']['earned_units']
                                                  for row in checks if row['before'] and row['after']), 6),
            'hard_strength_delta': sum(row['after']['evidence_strength'] - row['before']['evidence_strength']
                                       for row in checks if row['before'] and row['after']),
            'preferred_delta_units': changes[0] if verified and bonus['lanes']['preferred']['status'] != 'unavailable' else None,
            'supporting_delta_units': changes[1] if verified and bonus['lanes']['supporting']['status'] != 'unavailable' else None,
            'native_delta': native_delta,
            'native_score_disagreement': native_delta < 0 and decision in ('hard_improvement', 'bonus_improvement')}


def checked_phase8_base_floor(receipt, comparison, *, raw_jd, final_path, selected_base_sha256):
    """Use current saved base evidence only when it also reproduces scored A."""
    binding = phase8_native_bonus(receipt, raw_jd=raw_jd, final_path=final_path,
                                  selected_base_sha256=selected_base_sha256)
    if binding['status'] != 'verified':
        return {}
    before = receipt['selected_base_analysis']['stable_analysis']
    after = receipt['after_stable_analysis']
    actual = (comparison.get('native_document_evidence') or {}).get('existing') or {}
    fields = ('requirement_id', 'match_label', 'evidence_strength', 'evidence')
    expected = [{key: row.get(key) for key in fields} for row in after['canonical_requirements']]
    if (actual.get('requirements') != expected or actual.get('docx_sha256') != binding['after_docx_sha256']
            or comparison.get('a_docx_sha256') != binding['after_docx_sha256']
            or comparison.get('scoring_version') != after['scoring_version']
            or comparison.get('a_score') != after['deterministic_alignment_score']):
        return {}
    checks = native_hard_floors(before['canonical_requirements'], after['canonical_requirements'])
    failed = [r['requirement_id'] for r in checks if r['status'] in ('regressed', 'unavailable')]
    baseline = before['deterministic_alignment_score']
    delta = after['deterministic_alignment_score'] - baseline
    return {'selected_base_comparison_status': 'regressed' if failed or delta < 0 else 'improved' if delta > 0 else 'maintained',
            'selected_base_delta': delta, 'selected_base_baseline_score': baseline,
            'selected_base_improvement_verified': not failed and delta > 0,
            'selected_base_required_core_losses': failed, 'selected_base_comparison_source': 'current_phase8_docx'}

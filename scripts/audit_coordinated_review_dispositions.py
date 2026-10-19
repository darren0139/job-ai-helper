"""Stage 2F diagnostic only. Never imported by scoring or used as a label policy.

Consumes the existing guarded dashboard export; that export is not a test,
dashboard, or production dependency. Manual review categories and the proposed
exclusion catalogue below are audit judgments, not new independent scoring gold.
"""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path


# Independently read literal activity claims; no detector result creates this list.
# Exact strings deliberately bound this impact estimate to the existing packet.
EXCLUSION_CATALOGUE = {
    'Consumed REST APIs using HTTP requests and JSON responses.':
        'Explicit client consumption; no design, creation, maintenance or deployment claim.',
    'Integrated Supabase PostgREST generated REST APIs for CRUD and authentication.':
        'Integration of generated APIs; no custom endpoint or required artifact ownership claim.',
    'Configured ESP32 GPIO interrupts.':
        'Peripheral configuration; no explicit design/develop/maintain shared-object claim.',
}
TITLE = 'Synthetic acceptance project'
REASONS = {
    'PARTIAL_OWNERSHIP': 'One responsibility only; cloud maintenance is not requested deployment.',
    'MISSING_TECHNICAL_SCOPE': 'Action ownership asserted, but original required modifiers omitted.',
    'EXCLUDED_ONLY_NATIVE_NONE': 'Only explicit nonqualifying activities and native NONE; bounded exclusion candidate.',
    'TOPIC_RECOVERY_WITHOUT_OWNERSHIP': 'Native positive topic match without qualifying action ownership; detector/policy gap.',
    'SEPARATE_RECORDS': 'Separate bullets do not prove one complete ownership record or the P3 pair.',
    'EXPLICIT_LIFECYCLE_DENIAL': 'Design/development positive, lifecycle explicitly denied; P3 veto applies.',
    'API_AUTHORSHIP_GUARD': 'Generic backend/API ownership language fails independent API authorship guard.',
}


def proposed_exclusion(receipt):
    """Hypothetical R1 ONLY: reviewed finite exclusions + existing native NONE.

    Not a general absence detector. No omitted-action, scope, ambiguous, denied,
    multi-record or native-positive case is admitted. Source metadata alone is
    not evidence of responsibility. Unknown records always fail closed.
    """
    o = receipt['obligation']
    if (receipt['disposition'] != 'REVIEW_REQUIRED' or receipt['native_label'] != 'none'
            or o.get('status') != 'SUPPORTED' or o.get('conjunction') != 'AND'
            or not o.get('raw_jd_parent_span')):
        return False
    activities = []
    for item in receipt['proofs'].values():
        record, proof = item['record'], item['proof']
        if (record['evidence_id'] != proof['evidence_id']
                or record['source'] != proof['source']
                or record['text'] != proof['evidence_text']
                or record['section'] != 'projects'
                or proof.get('status') != 'INCOMPLETE'
                or proof.get('supported_actions') or proof.get('denied_actions')
                or proof.get('ambiguities')):
            return False
        if record['source'] == 'resume_profile.projects[0]' and record['text'] == TITLE:
            continue
        if record['source'] != 'resume_profile.projects[0].bullets[0]':
            return False
        activities.append(record['text'])
    return len(activities) == 1 and activities[0] in EXCLUSION_CATALOGUE


def primary_reason(family, scenario):
    """Manual, mutually exclusive review taxonomy; secondary receipts stay intact."""
    if scenario == 'Denied lifecycle':
        return 'EXPLICIT_LIFECYCLE_DENIAL'
    if scenario == 'Separate partial records':
        return 'SEPARATE_RECORDS'
    if scenario == 'Shortened object':
        return 'MISSING_TECHNICAL_SCOPE'
    if scenario in ('API consumption', 'PostgREST integration', 'Zero-overlap topic recovery'):
        return ('TOPIC_RECOVERY_WITHOUT_OWNERSHIP'
                if family == 'embedded' and scenario == 'Zero-overlap topic recovery'
                else 'EXCLUDED_ONLY_NATIVE_NONE')
    if family == 'backend':
        return 'API_AUTHORSHIP_GUARD'
    if scenario == 'Maintenance only':
        return 'PARTIAL_OWNERSHIP'
    raise ValueError('Unreviewed case: '+family+' / '+scenario)


def audit(batch):
    """Read actual receipts; attach separate, explicitly hypothetical annotations."""
    cases, all_rows, impacts = [], [], []
    baseline = Counter(r['P3'] for r in batch['rows'])
    for summary in batch['rows']:
        detail = batch['details'][summary['Case']]
        target = detail['after_rows'][0]
        receipt = target['coordinated_action_receipt']
        review_rows = [r for r in detail['after']['canonical_requirements']
                       if r.get('coordinated_action_receipt', {}).get('disposition') == 'REVIEW_REQUIRED']
        resolved = [r for r in review_rows if proposed_exclusion(r['coordinated_action_receipt'])]
        residual = len(review_rows)-len(resolved)
        impacts.append({'case': summary['Case'], 'actual_withheld': summary['Withheld'] == 'Yes',
                        'actual_review_rows': len(review_rows), 'R1_resolved_rows': len(resolved),
                        'hypothetical_withheld': bool(residual),
                        'hypothetical_remaining_review_rows': residual})
        for row in review_rows:
            rec = row['coordinated_action_receipt']
            all_rows.append({'case': summary['Case'], 'requirement_id': row['requirement_id'],
                             'native': rec['native_label'], 'R1_eligible': proposed_exclusion(rec)})
        if summary['P3'] != 'REVIEW_REQUIRED':
            continue
        family = summary['Job'].split('/ ')[1]
        reason = primary_reason(family, summary['Scenario'])
        eligible = proposed_exclusion(receipt)
        evidence = []
        for item in sorted(receipt['proofs'].values(), key=lambda item: item['record']['source']):
            p, record = item['proof'], item['record']
            evidence.append({**deepcopy(record), 'admission': item['admission'],
                'status': p['status'], 'supported_actions': p.get('supported_actions', []),
                'missing_actions': p.get('missing_actions', []), 'technical_scope': p.get('technical_scope'),
                'technical_supported_actions': p.get('technical_supported_actions', []),
                'denied_actions': p.get('denied_actions', []), 'ambiguities': p.get('ambiguities', []),
                'independent_api_guard': p.get('independent_api_guard'),
                'independent_literal_exclusion': EXCLUSION_CATALOGUE.get(record['text']),
                'ownership_spans': deepcopy(p.get('extended_receipts', []))})
        cases.append({'case': summary['Case'], 'job_id': detail['job_id'], 'family': family,
            'scenario': summary['Scenario'], 'parent_occurrence_id': detail['parent_occurrence_id'],
            'original_requirement': receipt['obligation']['raw_parent_text'],
            'corrected_requirement': target['text'], 'native_label': receipt['native_label'],
            'actual_disposition': receipt['disposition'], 'actual_label': target['match_label'],
            'required_actions': [a['action'] for a in receipt['obligation']['actions']],
            'primary_reason': reason, 'evidence': evidence,
            'native_selected_evidence': deepcopy(receipt['native_selected_evidence']),
            'source_provenance': deepcopy(target['source_provenance']),
            'raw_jd_parent_span': receipt['obligation']['raw_jd_parent_span'],
            'parent_allocation': receipt['parent_allocation'], 'actual_parent_credit': None,
            'actual_whole_jd_withheld': summary['Withheld'] == 'Yes',
            'R1_safe_if_approved': eligible, 'R1_requires_new_policy_decision': eligible,
            'current_policy_auto_resolution': False,
            'hypothetical_label': 'none' if eligible else 'REVIEW_REQUIRED',
            'hypothetical_parent_credit': 0 if eligible else None,
            'hypothetical_whole_jd_withheld': bool(residual),
            'remaining_decision': ('Approve finite exclusion with native NONE; absence is limited to this supplied packet.'
                if eligible else 'Retain review; any numeric resolution needs separate policy or additional evidence.'),
            'independent_checks': deepcopy(batch['expectations'][summary['Case']])})
    after = baseline.copy()
    count = sum(c['R1_safe_if_approved'] for c in cases)
    after['NONE'] += count
    after['REVIEW_REQUIRED'] -= count
    return {'kind': 'STAGE_2F_DIAGNOSTIC_NOT_SCORING_POLICY',
        'baseline_revision': batch['revision'], 'actual_label_counts': dict(sorted(baseline.items())),
        'actual_withheld': sum(i['actual_withheld'] for i in impacts),
        'actual_exceptions': deepcopy(batch['errors']),
        'reference_mismatches': sum(r['Stage 2E reference'] == 'MISMATCH' for r in batch['rows']),
        'independent_checks': sum(len(v) for v in batch['expectations'].values()),
        'independent_disagreements': [c for checks in batch['expectations'].values() for c in checks if not c['agrees']],
        'classification_counts': dict(sorted(Counter(c['primary_reason'] for c in cases).items())),
        'classification_definitions': REASONS, 'cases': cases,
        'hypothetical_R1': {'authorization': 'PROPOSED_ONLY', 'target_review_cases_resolved': count,
            'label_counts': dict(sorted(after.items())),
            'all_review_rows_before': len(all_rows),
            'all_review_rows_resolved': sum(r['R1_eligible'] for r in all_rows),
            'withheld_after': sum(i['hypothetical_withheld'] for i in impacts),
            'impacts_all_60': impacts, 'review_rows_including_other_parents': all_rows}}


def write_audit(batch_path, output_path):
    batch_path, output_path = Path(batch_path), Path(output_path)
    batch = json.loads(batch_path.read_text(encoding='utf-8'))
    before = json.dumps(batch, sort_keys=True)
    data = audit(batch)
    verify_packet(batch, data)
    if json.dumps(batch, sort_keys=True) != before:
        raise AssertionError('Audit mutated actual production receipts')
    data['input_sha256'] = hashlib.sha256(batch_path.read_bytes()).hexdigest()
    output_path.write_text(json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)+'\n',
                           encoding='utf-8')
    return data


def verify_packet(batch, data):
    """Validate the fresh diagnostic against the user baseline and literal sources.

    The manually enumerated R1 estimate is a proposal review check, not an oracle
    added to production scoring tests. Existing independent fixtures stay intact.
    """
    assert len(batch['rows']) == len(batch['details']) == 60
    assert data['actual_label_counts'] == {'DIRECT': 12, 'WEAK': 3, 'NONE': 5, 'REVIEW_REQUIRED': 40}
    assert data['actual_withheld'] == 45 and not data['actual_exceptions']
    assert not data['reference_mismatches'] and not data['independent_disagreements']
    assert len(data['cases']) == len({c['case'] for c in data['cases']}) == 40
    expected = {(family, scenario) for family in ('pipeline', 'embedded', 'fullstack', 'backend', 'cloud')
                for scenario in ('API consumption', 'PostgREST integration')}
    expected |= {(family, 'Zero-overlap topic recovery') for family in ('pipeline', 'fullstack', 'backend', 'cloud')}
    assert {(c['family'], c['scenario']) for c in data['cases'] if c['R1_safe_if_approved']} == expected
    root = Path(__file__).resolve().parents[1]
    corpus = json.loads((root/'tests/fixtures/per_jd_scoring_audit.json').read_text(encoding='utf-8'))
    raw_jds = {j['job_id']: j['frozen_inputs']['raw_jd_text'] for j in corpus['snapshot']['audit']['corpus']['jobs']}
    for detail in batch['details'].values():
        expected_records = {'resume_profile.projects[0]': TITLE,
                            **{f'resume_profile.projects[0].bullets[{i}]': text
                               for i, text in enumerate(detail['synthetic_evidence'])}}
        for row in detail['after']['canonical_requirements']:
            rec = row.get('coordinated_action_receipt')
            if not rec:
                continue
            assert {v['record']['source']: v['record']['text'] for v in rec['proofs'].values()} == expected_records
            assert len(rec['proofs']) == len(expected_records)
            o = rec['obligation']
            assert raw_jds[detail['job_id']][slice(*o['raw_jd_parent_span'])] == o['raw_parent_text']
            assert rec['parent_allocation'] == 1
            if rec['disposition'] == 'REVIEW_REQUIRED':
                assert row['match_label'] is None and row['match_value'] is None
                assert detail['after']['deterministic_alignment_score'] is None


def historical_scope_inventory():
    """JD geometry only; never reads historical candidate inputs or scores."""
    from analysis_stability import stable_evidence_scoring as native
    from analysis_stability.coordinated_integration import canonicalise_coordinated_requirements, targeted
    root = Path(__file__).resolve().parents[1]
    fixture = json.loads((root/'tests/fixtures/per_jd_scoring_audit.json').read_text(encoding='utf-8'))
    rows = []
    for job in fixture['snapshot']['audit']['corpus']['jobs']:
        raw = job['frozen_inputs']['raw_jd_text']
        before = native.canonicalise_requirements({}, raw_jd_text=raw)['requirements']
        after = canonicalise_coordinated_requirements({}, raw)['requirements']
        rows.append({'job_id': job['job_id'], 'native_rows': len(before), 'gated_rows': len(after),
                     'targeted_parents': [{'parent_occurrence_id': r['scoring_parent_occurrence_id'],
                                           'requirement_id': r['requirement_id'], 'text': r['text']}
                                          for r in after if targeted(r)]})
    return {'kind': 'RAW_JD_ONLY_NO_HISTORICAL_CANDIDATE_SCORE_INFERENCE', 'jobs': rows}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('guarded_batch_export', type=Path)
    parser.add_argument('new_ignored_output', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.new_ignored_output.exists() or not args.new_ignored_output.resolve().is_relative_to(root/'reports'):
        parser.error('Write to a new ignored reports/ path only')
    result = write_audit(args.guarded_batch_export, args.new_ignored_output)
    print(json.dumps({k: result[k] for k in ('actual_label_counts', 'actual_withheld', 'classification_counts')}, indent=2))
    print('Hypothetical R1:', {k: v for k, v in result['hypothetical_R1'].items() if not isinstance(v, list)})

"""Independent Stage 2I expectation delta and cached realistic preview data.

No local export is read. Historical Stage 2H inputs/observations are immutable;
these expectations are never passed into the scorer.
"""
from collections import Counter
from functools import lru_cache
import json

from scripts import audit_coordinated_realistic_evidence as realistic

EXPECTATIONS = realistic.ROOT/'tests/fixtures/coordinated_conflict_policy_v1.json'


def baseline_label(case_id):
    fixture = json.loads(EXPECTATIONS.read_text(encoding='utf-8'))
    for key, label in (('baseline_actual_direct','DIRECT'), ('baseline_actual_weak','WEAK'), ('baseline_actual_none','NONE')):
        if case_id in fixture[key]:
            return label
    return 'REVIEW_REQUIRED'


def expected_label(case_id):
    fixture = json.loads(EXPECTATIONS.read_text(encoding='utf-8'))
    return 'REVIEW_REQUIRED' if case_id in fixture['changed_selected_cases'] else baseline_label(case_id)


@lru_cache(maxsize=1)
def run_batch(revision):
    realistic.run_study.cache_clear()
    study = realistic.run_study()
    study = {**study, 'kind': 'STAGE_2I_EXECUTION_OF_IMMUTABLE_STAGE_2H_INPUTS'}
    rows, details = [], {}
    fixture = json.loads(EXPECTATIONS.read_text(encoding='utf-8'))
    for row in study['rows']:
        case_id = row['id']
        before = baseline_label(case_id)
        expected = expected_label(case_id)
        old_withheld = before == 'REVIEW_REQUIRED' or case_id in ('B01','B04','B05','C02')
        expected_withheld = old_withheld or case_id in fixture['changed_selected_cases'] or case_id in fixture['changed_companion_cases']
        detail = study['details'][case_id]
        affected = [r for r in detail['analysis']['canonical_requirements']
                    if (r.get('coordinated_action_receipt', {}).get('scoped_conflict') or {}).get('quarantine')]
        rows.append({'Case': case_id, 'Job': str(row['job_id'])+' / '+row['family'], 'Scenario': row['theme'],
            'Stage 2H actual': before, 'Stage 2I expected': expected, 'Actual': row['actual_label'],
            'Disposition': row['disposition'], 'Contribution': row['parent_credit'],
            'Alignment %': row['whole_jd_score'], 'Withheld': row['whole_jd_withheld'],
            'Conflicted parents': len(affected), 'Conflict reason': '; '.join(
                r['coordinated_action_receipt']['scoped_conflict']['reason'] for r in affected),
            'Expectation agreement': row['actual_label'] == expected and row['whole_jd_withheld'] == expected_withheld})
        details[case_id] = {'job_id': row['job_id'], 'scenario': case_id+' — '+row['theme'],
            'synthetic_evidence': [r['text'] for r in realistic.original_occurrences(detail['profile'], detail['raw_resume_text'])],
            'before_rows': [], 'after_rows': [detail['target']], 'after': detail['analysis'],
            'original_profile': detail['profile']}
    return {'revision': revision, 'rows': rows, 'details': details, 'errors': study['errors'], 'study': study,
            'counts': dict(Counter(r['Actual'] for r in rows)),
            'withheld': sum(r['Withheld'] for r in rows),
            'expectation_mismatches': [r['Case'] for r in rows if not r['Expectation agreement']]}

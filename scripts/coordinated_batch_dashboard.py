"""UI-only batch records and invalidation. No scoring policy or persistence."""
from collections import Counter
import hashlib
from importlib.metadata import version
import json
import re
from pathlib import Path
from threading import RLock

from scripts import coordinated_acceptance as acceptance
from analysis_stability.coordinated_integration import IDENTITIES

ROOT = acceptance.ROOT
REFERENCE = ROOT/'tests/fixtures/coordinated_stage2e_batch_reference_v1.json'
R1_EXPECTATIONS = ROOT/'tests/fixtures/coordinated_r1_contract_v1.json'
_lock = RLock()
_prepared = None


def revision_key():
    """Conservative source/input identity, independent of ignored diagnostics."""
    sources = {ROOT/'coordinated_actions_preview.py', Path(__file__),
               ROOT/'scripts/coordinated_acceptance.py', REFERENCE, R1_EXPECTATIONS}
    for folder in ('analysis_stability', 'tailoring', 'taxonomy_discovery', 'job_discovery'):
        sources.update((ROOT/folder).rglob('*.py'))
    sources.update((ROOT/'taxonomy').glob('*.json'))
    sources.update(ROOT/'tests/fixtures'/name for name in (
        'coordinated_action_ownership_oracle_v1.json',
        'coordinated_partial_action_policy_v1.json', 'per_jd_scoring_audit.json'))
    digest = hashlib.sha256(json.dumps(IDENTITIES, sort_keys=True).encode())
    digest.update(version('streamlit').encode())
    for path in sorted(sources):
        digest.update(str(path.relative_to(ROOT)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def prepare_revision(revision):
    """Invalidate the acceptance module's bounded legacy caches on source changes."""
    global _prepared
    with _lock:
        if revision != _prepared:
            acceptance.parents.cache_clear()
            acceptance._comparison_cached.cache_clear()
            _prepared = revision


def case_key(pid, scenario):
    return pid+'::'+scenario


def reference_expectation(family, scenario):
    ref = json.loads(REFERENCE.read_text(encoding='utf-8'))
    family_ref = ref['families'][family]
    if scenario in ref['complete_scenarios']:
        label = family_ref['positive_complete']
    elif scenario == ref['partial_scenario']:
        label = family_ref['design_development']
    elif scenario in ref['review_scenarios']:
        label = 'REVIEW_REQUIRED'
    else:
        raise ValueError('Scenario has no historical reference: '+scenario)
    return {'label': label, 'withheld': family_ref['withhold_all'] or label == 'REVIEW_REQUIRED'}


def current_expectation(family, scenario):
    """Independent Stage 2G delta over the immutable historical Stage 2E oracle.

    Scenario names are expectation lookup keys only, never scorer inputs.
    """
    historical = reference_expectation(family, scenario)
    expected = json.loads(R1_EXPECTATIONS.read_text(encoding='utf-8'))
    if scenario in expected['resolved_selected_cases'][family]:
        return {'label': 'NONE', 'withheld': False}
    return historical


def independent_checks(result, family):
    """Only exact reviewed synthetic inputs qualify; no inferred expectations."""
    fixture = json.loads((ROOT/'tests/fixtures/coordinated_partial_action_policy_v1.json').read_text(encoding='utf-8'))
    oracle = json.loads((ROOT/'tests/fixtures/coordinated_action_ownership_oracle_v1.json').read_text(encoding='utf-8'))
    receipts = result['after_rows'][0]['coordinated_action_receipt']['proofs']
    checks = []
    for index, text in enumerate(result['synthetic_evidence']):
        item = next((p for p in receipts.values()
                     if p['record']['source'].endswith(f'.bullets[{index}]')
                     and p['record']['text'] == text), None)
        for case in fixture['cases']:
            if case.get('family', 'embedded') == family and case['text'] == text:
                proof = (item or {}).get('proof', {})
                checks.append({'authority': fixture['schema_version'], 'source_index': index,
                    'dimensions': 'actions, technical scope, P3 admission',
                    'expected': {'actions': sorted(case['owned']), 'technical': case['technical'],
                                 'admission': case['policies'][2]},
                    'actual': {'actions': proof.get('supported_actions'), 'technical': proof.get('technical_scope'),
                               'admission': (item or {}).get('admission')}})
    parent = next(p for p in oracle['parents'] if p['parent_occurrence_id'] == result['parent_occurrence_id'])
    lifecycle = re.search(r'\band\s+(maintain|deploy)\b', parent['original_raw_parent'], re.I)
    if lifecycle is None:
        raise ValueError('Independent source has no reviewed mandatory lifecycle action')
    mandatory = {'design', 'develop', lifecycle.group(1).lower()}
    for case in parent['scenarios']:
        if case['evidence'] != result['synthetic_evidence']:
            continue
        for index, expected in enumerate(case['declared_actions_by_evidence']):
            item = next((p for p in receipts.values()
                         if p['record']['source'].endswith(f'.bullets[{index}]')), {})
            # Independent oracle uses build/develop synonyms; no detector output
            # is used to construct the expected action set.
            declared = {'develop' if a in ('build', 'implement') else a for a in expected}
            gold = sorted(declared & mandatory)
            checks.append({'authority': 'Stage 2B independent action oracle', 'source_index': index,
                           'dimensions': 'requested action ownership only',
                           'declared_activities': sorted(declared), 'mandatory_actions': sorted(mandatory),
                           'expected': gold, 'actual': item.get('proof', {}).get('supported_actions')})
    for check in checks:
        check['agrees'] = check['expected'] == check['actual']
    return checks


def summarize(result, family):
    row = result['after_rows'][0]
    receipt = row['coordinated_action_receipt']
    selected = row.get('evidence') or []
    if selected:
        diagnostic = receipt['proofs'][selected[0]['evidence_id']]
    else:
        diagnostic = next((p for p in receipt['proofs'].values()
                           if '.bullets[' in p['record']['source']), {})
    proof = diagnostic.get('proof', {})
    effective = row['match_label'].upper() if row['match_label'] is not None else 'REVIEW_REQUIRED'
    score = result['after']['deterministic_alignment_score']
    expected = reference_expectation(family, result['scenario'])
    current = current_expectation(family, result['scenario'])
    checks = independent_checks(result, family)
    summary = {
        'Case': case_key(result['parent_occurrence_id'], result['scenario']),
        'Job': str(result['job_id'])+' / '+family,
        'Scenario': result['scenario'], 'Before rows': len(result['before_rows']),
        'After rows': len(result['after_rows']),
        'Before contribution': sum(r['group_weight_fraction']*r['match_value'] for r in result['before_rows']),
        'Native': receipt['native_label'].upper(), 'P3': effective,
        'Disposition': receipt['disposition'],
        'After contribution': receipt['synthetic_parent_contribution'],
        'Alignment %': score, 'Missing actions': ', '.join(proof.get('missing_actions', [])),
        'Technical scope': proof.get('technical_scope', 'UNPROVEN'),
        'Withheld': 'Yes' if score is None else 'No',
        'Stage 2E reference': ('Matches' if expected == {'label': effective, 'withheld': score is None} else 'MISMATCH'),
        'Stage 2G expectation': ('Matches' if current == {'label': effective, 'withheld': score is None} else 'MISMATCH'),
        'R1 reason': (receipt.get('r1_exclusion') or {}).get('reason', 'Not applicable: admitted ownership'),
        'Independent checks': ('Not covered' if not checks else
                               f"{sum(c['agrees'] for c in checks)}/{len(checks)} agree"),
    }
    return summary, checks


def run_batch(revision, progress=None):
    prepare_revision(revision)
    plan = [(p, scenario) for p in acceptance.parents() for scenario in acceptance.scenarios(p)]
    rows, details, errors, expectations = [], {}, [], {}
    for number, (parent, scenario) in enumerate(plan, 1):
        key = case_key(parent['parent_occurrence_id'], scenario)
        family = parent['obligation']['object_family']
        try:
            result = acceptance.comparison(parent, scenario)
            row, checks = summarize(result, family)
            details[key] = result
            expectations[key] = checks
        except Exception as error:
            message = type(error).__name__+': '+str(error)
            errors.append({'Case': key, 'Job': str(parent['job_id'])+' / '+family,
                           'Scenario': scenario, 'Exception': message})
            row = {'Case': key, 'Job': str(parent['job_id'])+' / '+family,
                   'Scenario': scenario, 'P3': 'EXCEPTION', 'Disposition': 'EXCEPTION',
                   'Alignment %': None, 'Withheld': 'Unknown (exception)',
                   'Stage 2E reference': 'Not compared', 'Stage 2G expectation': 'Not compared',
                   'Independent checks': 'Not checked'}
        rows.append(row)
        if progress:
            progress(number, len(plan), str(parent['job_id'])+' / '+family+' — '+scenario)
    return {'revision': revision, 'rows': rows, 'details': details, 'errors': errors,
            'expectations': expectations}


def totals(batch):
    counts = Counter(row['P3'] for row in batch['rows'])
    checks = [c for cases in batch['expectations'].values() for c in cases]
    return {'total': len(batch['rows']),
            **{label: counts[label] for label in ('DIRECT', 'WEAK', 'NONE', 'REVIEW_REQUIRED')},
            'withheld': sum(r['Withheld'] == 'Yes' for r in batch['rows']),
            'exceptions': len(batch['errors']),
            'reference_mismatches': sum(r['Stage 2E reference'] == 'MISMATCH' for r in batch['rows']),
            'current_mismatches': sum(r.get('Stage 2G expectation') == 'MISMATCH' for r in batch['rows']),
            'unexpected_historical_changes': sum(
                r['Stage 2E reference'] == 'MISMATCH' and
                reference_expectation(r['Job'].split(' / ')[1], r['Scenario']) ==
                current_expectation(r['Job'].split(' / ')[1], r['Scenario']) for r in batch['rows']),
            'independent_checks': len(checks), 'independent_agreements': sum(c['agrees'] for c in checks),
            'independent_covered_cases': sum(bool(c) for c in batch['expectations'].values())}


def filter_rows(rows, jobs=(), scenarios=(), dispositions=()):
    return [r for r in rows if (not jobs or r['Job'] in jobs)
            and (not scenarios or r['Scenario'] in scenarios)
            and (not dispositions or r['Disposition'] in dispositions)]

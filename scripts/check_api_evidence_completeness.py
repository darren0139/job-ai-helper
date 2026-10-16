"""Offline API completeness comparison; no database, model or refresh entry point.

The optional Git reference loads only the old evaluator for an in-memory A/B
comparison through the shared scorer. The published taxonomy is never edited.
"""
from contextlib import contextmanager
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import types
from unittest.mock import patch

from analysis_stability import stable_evidence_scoring as scoring
from tailoring import capability_taxonomy as taxonomy
from tests.test_api_evidence_completeness import (
    BASELINE_SCORING_VERSION, native_inputs, scenario_results,
)

ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def baseline_evaluator(reference):
    source = subprocess.run(
        ['git', 'show', f'{reference}:tailoring/capability_taxonomy.py'],
        cwd=ROOT, check=True, capture_output=True, text=True, encoding='utf-8',
    ).stdout
    name = '_api_completeness_baseline_taxonomy'
    module = types.ModuleType(name)
    module.__file__ = str(ROOT / 'tailoring/capability_taxonomy.py')
    with patch.dict(sys.modules, {name: module}):
        exec(compile(source, module.__file__, 'exec'), module.__dict__)
        with patch.object(taxonomy, '_evaluate_capability_record', module._evaluate_capability_record), \
                patch.object(scoring, 'SCORING_VERSION', BASELINE_SCORING_VERSION):
            yield


def cross_job_projections(reference):
    """Selected-evidence projections, not complete candidate profiles or gold."""
    jobs = json.loads((ROOT / 'tests/fixtures/per_jd_scoring_audit.json').read_text(
        encoding='utf-8'))['snapshot']['audit']['corpus']['jobs']
    results = []
    for job in jobs:
        saved_rows = job['baseline_stable_analysis']['canonical_requirements']
        evidence = list(dict.fromkeys(
            e['text'] for r in saved_rows for e in r.get('evidence', [])
            if e.get('text')
        ))
        inputs = native_inputs('', evidence)
        inputs.update(jd_profile={}, raw_jd_text=job['frozen_inputs']['raw_jd_text'],
                      keyword_match={'present': [], 'missing': [{'keyword': r['text']} for r in saved_rows]})
        with baseline_evaluator(reference):
            before = scoring.build_stable_analysis(**deepcopy(inputs))
        after = scoring.build_stable_analysis(**deepcopy(inputs))
        b = {r['requirement_id']: r for r in before['canonical_requirements']}
        a = {r['requirement_id']: r for r in after['canonical_requirements']}
        assert a.keys() == b.keys(), 'Requirement identities changed'
        changes = []
        for rid, row in a.items():
            old = b[rid]
            for key in ('capability_id', 'knowledge_status', 'importance', 'group_weight_fraction',
                        'parent_text', 'source_provenance', 'score_eligible'):
                assert row.get(key) == old.get(key), (job['job_id'], rid, key)
            keys = ('match_label', 'match_value', 'evidence')
            if any(row.get(k) != old.get(k) for k in keys):
                assert row.get('capability_id') == 'backend.api_development', (job['job_id'], rid)
                changes.append({'requirement_id': rid, 'before_label': old['match_label'],
                                'after_label': row['match_label'], 'before_value': old['match_value'],
                                'after_value': row['match_value']})
        results.append({'job_id': job['job_id'], 'requirement_count': len(a),
                        'selected_evidence_fixture_rows': len(evidence), 'changes': changes,
                        'before_score': before['deterministic_alignment_score'],
                        'after_score': after['deterministic_alignment_score']})
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-ref', required=True)
    parser.add_argument('--protected-baseline', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    after = scenario_results()
    with baseline_evaluator(args.baseline_ref):
        before = scenario_results()
    for old, new in zip(before, after):
        assert old['case'] == new['case']
        assert [d['label'] for d in old['after_evaluator']] == old['baseline_evaluator_labels']
        old_rows = old['after_native']['canonical_requirements']
        assert [r['match_label'] for r in old_rows] == [r['match_label'] for r in old['baseline_native_rows']]
        assert old['after_native']['deterministic_alignment_score'] == old['baseline_score']
        assert [d['label'] for d in new['after_evaluator']] == new['expected_evaluator_labels']
        assert [r['match_label'] for r in new['after_native']['canonical_requirements']] == [new['expected_native_label']]
        new['executed_before_evaluator'] = old['after_evaluator']
        new['executed_before_native'] = old['after_native']
    cross_job = cross_job_projections(args.baseline_ref)
    protected_before = json.loads(args.protected_baseline.read_text(encoding='utf-8'))
    protected_after = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in protected_before}
    edited_policy = {'tailoring/capability_taxonomy.py', 'analysis_stability/stable_evidence_scoring.py'}
    unchanged = {p: protected_before[p] == protected_after[p] for p in protected_before if p not in edited_policy}
    assert all(unchanged.values()), 'Protected artifact changed'
    output = {'baseline_ref': args.baseline_ref, 'python': sys.version,
              'scoring_version': scoring.SCORING_VERSION,
              'taxonomy_version': taxonomy.get_default_taxonomy().version,
              'scenarios': after, 'cross_job_projections': cross_job,
              'cross_job_limitation': '30 disposable projections reuse only previously selected evidence. They are not complete profiles, verified gold, or live refresh/ranking predictions.',
              'protected_sha256_before': protected_before, 'protected_sha256_after': protected_after,
              'protected_unchanged': unchanged,
              'intentionally_edited_policy_sha256': {p: {'before': protected_before[p], 'after': protected_after[p]} for p in edited_policy},
              'live_database_access': False, 'live_snapshot_hash_verification': 'Not accessed; saved fixture hashes and disposable round trips only.'}
    args.output.write_text(json.dumps(output, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'scenarios': len(after), 'cross_job_projections': len(cross_job),
                      'changed_projection_jobs': sum(bool(r['changes']) for r in cross_job),
                      'protected_artifacts_unchanged': len(unchanged), 'output': str(args.output)}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

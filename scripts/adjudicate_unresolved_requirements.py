"""Explicit, report-only unresolved semantics benchmark; dry run is default."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path

from taxonomy_discovery import unresolved_adjudication as adjudication

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / 'tests/fixtures/unresolved_adjudication_benchmark_v1.json'


def prepare(manifest, source=adjudication.SOURCE):
    if 'review_version' in manifest:
        from taxonomy_discovery.unresolved_gold_review import validate
        validate(manifest)
    occurrences = adjudication.load_occurrences(source)
    by_key = {(r['job_id'], r['requirement']['requirement_id']): r for r in occurrences}
    seal = manifest.get('fingerprint')
    if seal != adjudication.fingerprint({k: v for k, v in manifest.items() if k != 'fingerprint'}):
        raise ValueError('Benchmark manifest integrity mismatch')
    if manifest['source_fingerprint'] != occurrences[0]['source_fingerprint']:
        raise ValueError('Frozen source changed; review a new manifest')
    cases = []; skipped = []
    for expected in manifest['expectations']:
        key = tuple(expected['key'])
        if key not in by_key: raise ValueError('Unknown frozen case identity')
        case = adjudication.build_input(by_key[key])
        if case is None:
            skipped.append({'key': list(key), 'reason': 'ALREADY_RESOLVED_NO_MODEL'})
        elif adjudication.fingerprint(case) != expected['input_fingerprint']:
            raise ValueError('Frozen input/current knowledge changed; benchmark needs review')
        else: cases.append(case)
    if 'review_version' in manifest:
        validate(manifest, cases=cases)
    return cases, skipped


def compare_reports(local, cloud):
    native = {r['input_fingerprint']: r for r in local['rows']}
    differences = []
    for r in cloud['rows']:
        old = native.get(r['input_fingerprint'])
        if not old: raise ValueError('Providers must use identical frozen inputs')
        if old['validation']['proposal'] != r['validation']['proposal']:
            differences.append({'job_id': r['input']['job_id'], 'requirement_id': r['input']['requirement_id'],
                'local': old['validation']['proposal'], 'cloud': r['validation']['proposal']})
    return differences


def write_report(report, path):
    path = Path(path).resolve()
    if path.suffix != '.json' or ROOT in path.parents and 'reports' not in path.relative_to(ROOT).parts:
        raise ValueError('Write reports to an external artifact directory or repository reports/ only')
    path.parent.mkdir(parents=True, exist_ok=True)
    report['fingerprint'] = adjudication.fingerprint(report)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    gate = report['gate']
    lines = ['# Unresolved requirement adjudication', '', gate['verdict'], '',
        'Report only. No production changes, approval, publication, research or scoring influence.', '',
        f"Executed calls: {report['executed_calls']}; optional cloud: {gate['optional_cloud']}", '',
        '## Quality gate', '', '| Metric | Numerator | Denominator | Rate | Pass |', '|---|---:|---:|---:|---|']
    for name, metric in gate['metrics'].items():
        lines.append(f"| {name} | {metric['numerator']} | {metric['denominator']} | {metric['rate']} | {metric['pass']} |")
    lines += ['', 'Label adequacy: ' + json.dumps(gate['label_adequacy']), '', '## Exact cases', '',
        '| Job | Requirement | Expected alternatives | Proposed route | Supporting spans | Validation |', '|---|---|---|---|---|---|']
    expected = {tuple(e['key']): e for e in report['expectations']}
    for row in report['rows']:
        case = row['input']; proposal = row['validation']['proposal']; e = expected[(case['job_id'], case['requirement_id'])]
        values = [case['job_id'], case['requirement_id'], e['acceptable_routes'] or 'DEFERRED/AMBIGUOUS',
            proposal['proposed_route'], proposal['source_spans'], row['validation']['valid_schema']]
        lines.append('| ' + ' | '.join(str(v).replace('|', '\\|').replace('\n', ' ') for v in values) + ' |')
    lines += ['', 'Critical pending: ' + json.dumps(gate['critical_pending']),
        'Failure IDs: ' + json.dumps(gate['failure_ids']), 'UNKNOWN IDs: ' + json.dumps(gate['unknown_ids']),
        '', 'Cloud calls require separate human authorization, a Qwen report, privacy review, verified pricing and a shared ledger.']
    path.with_suffix('.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--corpus', type=Path, default=adjudication.SOURCE)
    p.add_argument('--benchmark', type=Path, default=BENCHMARK)
    p.add_argument('--job-id', type=int); p.add_argument('--requirement-id')
    p.add_argument('--limit', type=int, default=40); p.add_argument('--max-cases', type=int)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--provider', choices=('ollama', 'openai'), default='ollama')
    p.add_argument('--model', default=None)
    p.add_argument('--execute', action='store_true'); p.add_argument('--dry-run', action='store_true')
    p.add_argument('--all-reviewed', action='store_true'); p.add_argument('--confirm-all-reviewed', action='store_true')
    p.add_argument('--local-report', type=Path)
    p.add_argument('--pricing', type=Path); p.add_argument('--max-cost-usd', type=float, default=.50)
    p.add_argument('--max-output-tokens', type=int, default=1200)
    p.add_argument('--authorize-paid', action='store_true'); p.add_argument('--privacy-reviewed', action='store_true')
    p.add_argument('--confirm-preflight'); p.add_argument('--experiment-id'); p.add_argument('--ledger', type=Path)
    args = p.parse_args(argv)
    model = args.model or ('qwen3:8b' if args.provider == 'ollama' else None)
    manifest = json.loads(args.benchmark.read_text(encoding='utf-8'))
    cases, skipped = prepare(manifest, args.corpus)
    expectations = manifest['expectations']
    execute = args.execute and not args.dry_run
    if args.limit < 1 or args.max_cases is not None and not 1 <= args.max_cases <= 50:
        p.error('Positive bounded case selection required')
    local = None
    if args.local_report:
        local = json.loads(args.local_report.read_text(encoding='utf-8'))
        if (local.get('fingerprint') != adjudication.fingerprint({k: v for k, v in local.items() if k != 'fingerprint'})
                or not local['rows'] or any(r['provider'] != 'ollama' or not r['attempted'] for r in local['rows'])):
            p.error('A genuine completed local Qwen benchmark must precede optional cloud/expansion')
    if args.all_reviewed:
        if (args.provider != 'ollama' or not args.confirm_all_reviewed or not local
                or local['gate']['verdict'] != 'LOCAL SUFFICIENT' or local.get('human_reviewed') is not True):
            p.error('All-corpus expansion requires separate initiation and human-reviewed sufficient local benchmark')
        cases = [c for r in adjudication.load_occurrences(args.corpus) if (c := adjudication.build_input(r))]
        expectations = [{'key': [c['job_id'], c['requirement_id']], 'acceptable_routes': [],
            'review_reason': 'All-corpus routing report, not independent gold evaluation'} for c in cases]
    elif args.limit > 50:
        p.error('Representative runs bounded to 50; no automatic 276 expansion')
    cases = [c for c in cases if (args.job_id is None or c['job_id'] == args.job_id)
        and (args.requirement_id is None or c['requirement_id'] == args.requirement_id)]
    if not args.all_reviewed: cases = cases[:min(args.limit, args.max_cases or args.limit)]
    if not cases: p.error('No selected unresolved cases')
    transport = None; plan = None; ledger = None; prior_requests = 0
    if args.provider == 'ollama' and execute:
        from taxonomy_discovery.unresolved_adjudication_providers import ollama_transport
        transport = ollama_transport
    elif args.provider == 'openai':
        from taxonomy_discovery.unresolved_adjudication_providers import preflight, ExperimentLedger, cloud_transport_factory
        if not model or not args.pricing: p.error('Exact paid model and freshly verified price file required')
        plan = preflight([adjudication.prompt_for(c) for c in cases], model,
            json.loads(args.pricing.read_text(encoding='utf-8')), args.max_output_tokens)
        if not 0 < args.max_cost_usd <= .50: p.error('Shared experiment cap cannot exceed US$0.50')
        if execute:
            if (not local or not args.authorize_paid or not args.privacy_reviewed or not args.ledger or not args.experiment_id
                    or args.confirm_preflight != plan['preflight_id']):
                p.error('Separate paid authorization, privacy and exact preflight confirmation required')
            if local.get('benchmark_fingerprint') != manifest['fingerprint'] or local.get('expectations') != expectations:
                p.error('Reviewer labels changed since local benchmark; no post-hoc comparison')
            if [r['input_fingerprint'] for r in local['rows']] != [adjudication.fingerprint(c) for c in cases]:
                p.error('Optional comparison must use the same frozen local inputs')
            ledger = ExperimentLedger(args.ledger, args.experiment_id, adjudication.fingerprint([c for c in cases]), args.max_cost_usd)
            with ledger.locked() as data:
                prior_requests = len(data['requests'])
                remaining = ledger.identity['ceiling_nanousd'] - sum(r['charged_nanousd'] for r in data['requests'])
                if sum(r['reserved_nanousd'] for r in plan['requests']) > remaining:
                    p.error('Whole confirmed comparison does not fit remaining shared experiment allowance; no requests sent')
            transport = cloud_transport_factory(plan=plan, ledger=ledger, consent_id=args.confirm_preflight,
                authorized=True, api_key=os.environ.get('OPENAI_API_KEY'))
    report = adjudication.run_cases(cases, expectations, transport=transport, execute=execute, provider=args.provider, model=model)
    report.update(expectations=expectations, benchmark_fingerprint=manifest['fingerprint'], skipped=skipped,
        cloud_preflight=plan, cloud_budget_ceiling_usd=.50, human_reviewed=False)
    if ledger is not None:
        with ledger.locked() as data:
            spent = sum(r['charged_nanousd'] for r in data['requests'])
            started = data['requests'][prior_requests:]
            report['cloud_requests'] = {'executed': len(started),
                'blocked': report['executed_calls'] - len(started),
                'ambiguous': sum(r['status'] == 'ambiguous' for r in started),
                'unmetered': sum(r['status'] == 'reserved' for r in started)}
            report['executed_calls'] = len(started)
            report['cloud_experiment'] = {'experiment_id': args.experiment_id,
                'ceiling_usd': ledger.identity['ceiling_nanousd'] / 1e9, 'reserved_usd': spent / 1e9,
                'observed_usd': sum(r.get('observed_nanousd', 0) for r in data['requests']) / 1e9,
                'remaining_usd': (ledger.identity['ceiling_nanousd'] - spent) / 1e9,
                'request_states': dict(Counter(r['status'] for r in data['requests']))}
    if local and args.provider == 'openai': report['model_disagreements'] = compare_reports(local, report)
    write_report(report, args.output)
    print(json.dumps({'report': str(args.output), 'gate': report['gate']['verdict'], 'executed_calls': report['executed_calls']}))


if __name__ == '__main__':
    main()

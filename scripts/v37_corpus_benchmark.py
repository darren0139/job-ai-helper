"""Run a bounded read-only V3.7 corpus pilot. Reports go to the requested new JSON."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from tailoring.phase9f_v37_corpus_benchmark import run_pilot


def evaluate_pilot_documents(case: dict, variants: dict, proposals: dict,
                             *, base_docx: Path | None = None, work_root: Path | None = None) -> None:
    from tailoring.phase9f_v37_document_trial import compare_native_trials, evaluate_document_trial

    existing = evaluate_document_trial(case, work_root=work_root)
    variants['existing_fitted_reference'] = {'native': existing}
    if base_docx is not None:
        variants['original_base']['native'] = evaluate_document_trial(case, base_docx=base_docx, work_root=work_root)
        variants['original_base']['status'] = variants['original_base']['native']['status']
        variants['original_base']['reason'] = variants['original_base']['native'].get(
            'reason', 'Unchanged source document. Derivative strategies use the common fitted layout.')
    if existing['status'] != 'verified':
        for name in proposals:
            variants[name]['native'] = {'status': 'failed', 'score': None, 'pages': None,
                                        'reason': 'The common fitted reference could not be verified.'}
        return
    cached = {}
    for name, proposal in proposals.items():
        signature = tuple(tuple(p['after']) for p in proposal['projects'])
        changed = any(p['before'] != p['after'] for p in proposal['projects'])
        if signature not in cached:
            measured = evaluate_document_trial(case, proposal, work_root=work_root) if changed else existing
            cached[signature] = {**measured, **compare_native_trials(existing, measured)}
        variants[name]['native'] = cached[signature]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--packet', type=Path, required=True, help='Frozen 42-JD JSON or source ZIP.')
    parser.add_argument('--generation-row', type=int, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True, help='New JSON report path.')
    parser.add_argument('--native', action='store_true', help='Render and score actual DOCX files in temporary storage.')
    parser.add_argument('--work-root', type=Path)
    parser.add_argument('--base-docx', action='append', default=[], metavar='APPLICATION_ID=PATH')
    args = parser.parse_args()
    bases = {}
    for binding in args.base_docx:
        identifier, sep, filename = binding.partition('=')
        if not sep or not identifier.isdecimal() or not filename or int(identifier) in bases:
            parser.error('--base-docx requires a unique APPLICATION_ID=PATH binding.')
        bases[int(identifier)] = Path(filename)
    if bases and not args.native:
        parser.error('--base-docx requires --native.')

    def evaluate(case, variants, proposals):
        evaluate_pilot_documents(case, variants, proposals, base_docx=bases.get(case['application_id']),
                                 work_root=args.work_root)

    result = run_pilot(args.database, Path.cwd(), args.generation_row, args.packet,
                       evaluate=evaluate if args.native else None)
    with args.output.open('x', encoding='utf-8') as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
        output.write('\n')
    print(json.dumps(result['outcomes'], sort_keys=True))


if __name__ == '__main__':
    main()

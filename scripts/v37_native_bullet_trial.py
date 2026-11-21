"""Measure one explicit native bullet counterfactual against a saved fitted generation."""
from __future__ import annotations

import argparse
from contextlib import closing
import json
from pathlib import Path

from tailoring.phase9f_v37_corpus_benchmark import load_case, readonly_db
from tailoring.phase9f_v37_counterfactual import OPERATIONS, evaluate_counterfactual


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True, type=Path)
    parser.add_argument('--generation-row', required=True, type=int)
    parser.add_argument('--project', required=True, help='Exact saved project display title.')
    parser.add_argument('--operation', required=True, choices=OPERATIONS)
    parser.add_argument('--remove', default='', help='Exact selected wording.')
    parser.add_argument('--insert', default='', help='Exact excluded wording.')
    parser.add_argument('--extra', default='', help='Additional excluded wording for a space test.')
    parser.add_argument('--extra-project', default='')
    parser.add_argument('--work-root', type=Path)
    parser.add_argument('--output', required=True, type=Path, help='New JSON report.')
    args = parser.parse_args()
    with closing(readonly_db(args.database)) as db:
        case = load_case(db, args.generation_row, Path.cwd())
    receipt = evaluate_counterfactual(
        case, operation=args.operation, project=args.project, remove=args.remove, insert=args.insert,
        extra=args.extra, extra_project=args.extra_project, work_root=args.work_root,
    )
    with args.output.open('x', encoding='utf-8') as output:
        json.dump(receipt, output, ensure_ascii=False, indent=2)
        output.write('\n')
    print(json.dumps({name: trial['status'] for name, trial in receipt['trials'].items()}, sort_keys=True))


if __name__ == '__main__':
    main()

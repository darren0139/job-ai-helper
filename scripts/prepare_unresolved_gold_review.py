"""Prepare a frozen human worksheet or import explicit human review receipts offline."""
import argparse
import json
from pathlib import Path

from scripts.adjudicate_unresolved_requirements import prepare
from taxonomy_discovery import unresolved_adjudication as a
from taxonomy_discovery import unresolved_gold_review as review


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipts', type=Path, help='Only completed independently reviewed receipts; never model output')
    parser.add_argument('--manifest-output', type=Path, default=review.ROOT / 'tests/fixtures/unresolved_adjudication_benchmark_v2.json')
    parser.add_argument('--worksheet-output', type=Path, default=review.ROOT / 'docs/unresolved_gold_review_v2.md')
    parser.add_argument('--packet-output', type=Path, default=review.ROOT / 'reports/unresolved_gold_review_v2.json')
    parser.add_argument('--template-output', type=Path, default=review.ROOT / 'reports/unresolved_gold_review_receipts_v2.json')
    args = parser.parse_args(argv)
    destinations = [args.manifest_output, args.worksheet_output, args.packet_output, args.template_output]
    # Preserve both the original and any previously frozen reviewed outputs.
    if len({p.resolve() for p in destinations}) != len(destinations) or any(p.exists() for p in destinations):
        parser.error('Choose distinct new output paths; existing manifests/worksheets are never overwritten')
    parent = review.original()
    cases, skipped = prepare(parent)
    if skipped or len(cases) != 40:
        parser.error('All original 40 inputs must remain available and unchanged')
    receipts = json.loads(args.receipts.read_text(encoding='utf-8')) if args.receipts else []
    manifest = review.versioned_manifest(parent, receipts, cases)
    markdown, items = review.worksheet(parent, cases, a.load_occurrences())
    # Worksheet is deliberately tied to original expectations, not imported decisions.
    # Imported labels and their receipts are exclusively in the newly frozen manifest.
    packet = {'review_version': review.REVIEW_VERSION, 'parent_fingerprint': parent['fingerprint'],
              'summary': review.summary(manifest), 'source_path': parent['source_path'],
              'cases': items, 'model_calls': 0, 'network_calls': 0}
    template = [{'key': e['key'], 'input_fingerprint': e['input_fingerprint'],
                 'source_fingerprint': parent['source_fingerprint'], 'origin': 'INDEPENDENT_HUMAN',
                 'independent_of_model_predictions': False, 'reviewer': '', 'reviewed_at': '',
                 'acceptable_routes': [], 'source_spans': [], 'rationale': '', 'source_reference': ''}
                for e in parent['expectations']]
    values = [manifest, markdown, packet, template]
    for path, value in zip(destinations, values):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value if isinstance(value, str) else json.dumps(value, ensure_ascii=True, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(review.summary(manifest), indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

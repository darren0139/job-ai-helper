"""Export a compact tracked-fixture summary; detailed JD records require opt-in."""
import argparse
import json
from pathlib import Path
import subprocess

from taxonomy_discovery import source_aware_inventory as inventory


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('bulk_unresolved_stage1_summary.json'))
    parser.add_argument('--records-output',type=Path,help='Explicit opt-in to larger redacted JD-only records')
    args=parser.parse_args()
    # Verify provenance is tracked, without reading any database or other checkout.
    subprocess.run(['git','ls-files','--error-unmatch',*inventory.FIXTURES],cwd=inventory.ROOT,
                   check=True,capture_output=True)
    paths=[args.output]+([args.records_output] if args.records_output else [])
    if len({p.resolve() for p in paths})!=len(paths):
        raise ValueError('Summary and detailed records must use different new paths')
    for path in paths:
        target=path.resolve()
        if not target.is_relative_to(inventory.ROOT) or target.exists():
            raise ValueError('Use a new output path inside this worktree; existing artifacts are never overwritten')
    exported=inventory.build_export(inventory.fixture_views())
    summary=inventory.compact_summary(exported)
    args.output.write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    if args.records_output:
        args.records_output.write_text(json.dumps(exported,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(args.output),'counts':summary['counts'],
                      'export_fingerprint':exported['export_fingerprint']}))


if __name__=='__main__':
    main()

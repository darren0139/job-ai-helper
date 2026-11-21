"""Read-only prerequisite/final-file verification for the separate B4 patch."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('candidate',type=Path)
parser.add_argument('--phase',choices=['before','after'],required=True)
args=parser.parse_args()
bundle=Path(__file__).resolve().parent
manifest=json.loads((bundle/'manifest.json').read_bytes())
assert sha256((bundle.parent/'B4.patch').read_bytes()).hexdigest()==manifest['patch_sha256'], 'B4 patch digest differs'
checks={r['path']:r['sha256'] for r in manifest['prerequisite_files']}
for row in manifest['files']:
    checks[row['path']]=row['before_sha256' if args.phase=='before' else 'after_sha256']
for name,expected in checks.items():
    path=args.candidate/name
    if expected is None:
        assert not path.exists(), f'Unexpected existing new file: {name}'
    else:
        assert path.is_file() and sha256(path.read_bytes()).hexdigest()==expected, f'Unexpected file bytes: {name}'
for row in manifest['protected_files']:
    actual=sha256((args.candidate/row['path']).read_bytes()).hexdigest()
    assert actual in {row['sha256_lf'],row['sha256_raw_master']}, f'Changed protected baseline: {row["path"]}'
print(f'Verified {len(checks)} B4 {args.phase} dependencies/files. No changes made.')

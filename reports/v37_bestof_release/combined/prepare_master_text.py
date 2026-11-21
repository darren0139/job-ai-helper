"""Checksum-guarded CRLF-to-LF preparation in an independent master checkout."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('candidate',type=Path)
parser.add_argument('--check',action='store_true')
args=parser.parse_args()
bundle=Path(__file__).resolve().parent
candidate=args.candidate.resolve()
assert candidate!=bundle.parents[2], 'Never prepare the original development checkout'
rows=json.loads((bundle/'baseline_text_preparation.json').read_bytes())
pending=[]
for row in rows:
    file=candidate/row['path']
    raw=file.read_bytes()
    actual=sha256(raw).hexdigest()
    if actual==row['prepared_sha256']: continue
    assert actual==row['raw_master_sha256'], f'Unexpected baseline bytes: {row["path"]}'
    prepared=raw.replace(b'\r\n',b'\n')
    assert sha256(prepared).hexdigest()==row['prepared_sha256'], row['path']
    pending.append((file,prepared))
# Validate every path before writing anything. No Git/index operation occurs.
if not args.check:
    for file,prepared in pending: file.write_bytes(prepared)
print(f'{"Checked" if args.check else "Prepared"} {len(rows)} reviewed baseline paths; {len(pending)} require LF conversion.')

"""Verify reviewed release bytes, without importing the app or touching a database."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('candidate', type=Path)
args = parser.parse_args()
bundle = Path(__file__).resolve().parent
manifest = json.loads((bundle / 'manifest.json').read_bytes())
for name, expected in manifest['patches'].items():
    assert sha256((bundle / name).read_bytes()).hexdigest() == expected, name
for row in manifest['integrated_files']:
    path = args.candidate / row['path']
    assert path.is_file(), f'Missing {row["path"]}'
    assert sha256(path.read_bytes()).hexdigest() == row['sha256'], row['path']
print(f'Verified four patches and {len(manifest["integrated_files"])} integrated source/test files.')

"""Authenticated source snapshots for tests, independent of checkout history.

These are exact Git blob bytes, not regenerated current code. No Git, network,
working-tree source fallback, model, database or filesystem writes are used.
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]/'tests/fixtures/historical_provenance'
STAGE2D = '3e6ff34501b4d68cbe3e66b55ec8af5b0e288026'
V122 = '07912485d4803f355a760f2623a4a08f5b729fa2'
SCORER_PATH = 'analysis_stability/stable_evidence_scoring.py'
POLICY_PATH = 'analysis_stability/jd_metadata_policy.py'


@dataclass(frozen=True)
class SourcePin:
    filename: str
    git_blob: str
    sha256: str
    size: int


PINS = {
    (STAGE2D, SCORER_PATH): SourcePin('stage2d_stable_evidence_scoring.py.txt',
        'db453efe860f0a561ce132064859f2c194a54738',
        '582863e5e3fe5356d0c8adfdac53dd7ec27b382bb1c45d11caf6b8df192384bd', 156701),
    (V122, SCORER_PATH): SourcePin('v122_stable_evidence_scoring.py.txt',
        'ae44831634cb3467800b72ea1e2950b0a3cc2fd5',
        '222361e6364afbccd2a69fffe448a0547ff801b10df456e698030586a779e65a', 159631),
    (V122, POLICY_PATH): SourcePin('v122_jd_metadata_policy.py.txt',
        'f59d01e7f77cc0b3f9f744a959c04e8c61065b74',
        '26f645b97bd14ad3c84699c8cf249f800194373b04b07b7c345d4aee4637569b', 8610),
}


def read_source(revision, path, *, fixture_root=ROOT):
    """Require the full reviewed commit:path pair and both immutable byte pins."""
    pin = PINS.get((revision, path))
    if pin is None:
        raise ValueError('Unregistered historical revision/path; no current-source fallback')
    try:
        data = (Path(fixture_root)/pin.filename).read_bytes()
    except FileNotFoundError as error:
        raise ValueError('Missing authenticated historical source: '+pin.filename) from error
    blob = hashlib.sha1(b'blob '+str(len(data)).encode('ascii')+b'\0'+data).hexdigest()
    if len(data) != pin.size or hashlib.sha256(data).hexdigest() != pin.sha256 or blob != pin.git_blob:
        raise ValueError('Historical source bytes do not match the reviewed Git/SHA-256 identity: '+pin.filename)
    return data

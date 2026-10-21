"""Read-only original V2 fixtures authenticated by an earlier Git-tree capture."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent/'fixtures/predicate_investigation_v2'
TREE = '0a406ec1799434ed1c66f360191f8bd10c5c3b27'
MANIFEST_ID = '161024a5780a23693b61e4bea21e139ccb60abcc3760d1147adac153d920d04d'
REPORT_ID = '1ab3fe2c5e73eca47ed4c292e8436806cc41482771150e9c45205dd0a6ad5611'
PINS = {
    'report.json': ('3f98ef19bc1d6ec32cf71985ec515354cd09c669aae2a7b098282088ed25ca5e',
                    'edfc2b3d9356cb44628fecfd75e3f9c36af9c3ac', 243066),
    'manifest.json': ('3b0c6891a98ca85ea09068568ee8652eddd5682e66dd460c4328202e56fdaf06',
                      'a183cd3001530fb52498e575c59c6631d7b0ab12', 124310),
}


def _fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,
        separators=(',',':'),allow_nan=False).encode()).hexdigest()


def verified_paths(*, root=ROOT, expected_manifest_identity=MANIFEST_ID):
    """Return original inputs only; never read reports/, Git, or current scoring."""
    if expected_manifest_identity != MANIFEST_ID:
        raise ValueError('Incorrect original predicate manifest identity')
    values={}
    for name,(digest,blob,size) in PINS.items():
        try:data=(Path(root)/name).read_bytes()
        except FileNotFoundError as error:
            raise ValueError('Missing authenticated predicate fixture: '+name) from error
        actual_blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        if len(data)!=size or hashlib.sha256(data).hexdigest()!=digest or actual_blob!=blob:
            raise ValueError('Historical predicate fixture byte identity changed: '+name)
        item=json.loads(data)
        if item.get('fingerprint')!=_fingerprint({k:v for k,v in item.items() if k!='fingerprint'}):
            raise ValueError('Historical predicate fixture seal changed: '+name)
        values[name]=item
    report,manifest=values['report.json'],values['manifest.json']
    if (manifest['fingerprint']!=MANIFEST_ID or report['fingerprint']!=REPORT_ID
            or report['manifest_fingerprint']!=MANIFEST_ID):
        raise ValueError('Historical predicate pair identity mismatch')
    return Path(root)/'report.json',Path(root)/'manifest.json'

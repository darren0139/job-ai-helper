"""Auditable registration and fail-closed historical preconditions. Stdlib only.

This module never imports an archived test or scoring/resolver implementation.
A registration check is not historical reproduction. No execution waiver exists.
"""
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT/'tests/fixtures/ollama_test_lanes_v1.json'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def test_ids(path, module):
    tree = ast.parse(Path(path).read_text(encoding='utf-8'))
    return [module+'.'+cls.name+'.'+method.name
            for cls in tree.body if isinstance(cls, ast.ClassDef)
            for method in cls.body if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef))
            and method.name.startswith('test_')]


def load_manifest(path=MANIFEST):
    value = json.loads(Path(path).read_text(encoding='utf-8'))
    if value.get('schema_version') != 'ollama-test-lanes-v1':
        raise ValueError('Unknown test lane manifest')
    return value


def inventory(root=ROOT, manifest=None):
    root = Path(root)
    value = manifest if manifest is not None else load_manifest(root/'tests/fixtures/ollama_test_lanes_v1.json')
    current = []
    for module in value['current_modules']:
        current.extend(test_ids(root/(module.replace('.', '/')+'.py'), module))
    if len(current) != len(set(current)):
        raise ValueError('Duplicate current test registration')
    historical = []
    actual_files = {p.relative_to(root).as_posix() for p in (root/'historical_tests').rglob('*.py')}
    registered_files = {item['path'] for item in value['archives']}
    if actual_files != registered_files:
        raise ValueError('Historical file registration gap')
    for item in value['archives']:
        path = root/item['path']
        if digest(path) != item['sha256']:
            raise ValueError('Historical archive bytes changed: '+item['path'])
        ids = test_ids(path, item['original_module'])
        if ids != item['test_ids']:
            raise ValueError('Historical method registration gap')
        historical.extend(ids)
    mappings = value['coverage_mapping']
    if len(historical) != len(set(historical)) or set(mappings) != set(historical):
        raise ValueError('Historical assertion coverage mapping gap')
    for old, item in mappings.items():
        if not item['boundary']:
            raise ValueError('Undocumented historical/current boundary')
        replacement = item['current_test']
        if replacement is not None and replacement not in current:
            raise ValueError('Missing current behavioral replacement: '+old)
        if replacement is None and not item.get('historical_only_reason'):
            raise ValueError('Unaccounted historical-only assertion')
    namespace='historical@'+value['retained_test_source_revision']+':'
    return {'status':'REGISTRATION_VALIDATED_ONLY', 'current_test_ids':current,
            'historical_test_ids':[namespace+test for test in historical],
            'original_historical_assertion_ids':historical,
            'historical_reproduction':'NOT_RUN',
            'historical_reproduction_validated':False}


def verify_bytes(root, expected):
    """Exact byte comparison, including CRLF; never regenerate or overwrite."""
    root = Path(root).resolve()
    blockers = []
    for name, sha256 in expected.items():
        path = (root/name).resolve()
        if not path.is_relative_to(root):
            blockers.append({'path':name,'reason':'OUTSIDE_BUNDLE'})
        elif not path.is_file():
            blockers.append({'path':name,'reason':'MISSING'})
        elif digest(path) != sha256:
            blockers.append({'path':name,'reason':'BYTE_HASH_MISMATCH'})
    return blockers


def historical_preconditions(root=ROOT, manifest=None):
    """Inspect immutable prerequisites without importing current or old code.

    This task supplies an assertion inventory, not an approved runtime bundle.
    Even matching artifacts cannot certify dependencies/runtime identity. Missing
    approval/pins therefore remain a hard block, not an environment toggle.
    """
    value = manifest if manifest is not None else load_manifest()
    registration = inventory(ROOT, value)
    expected = value['historical_artifacts']
    blockers = verify_bytes(root, expected)
    # Only parse an original preservation map after its independent byte pin.
    for name in value['preservation_maps']:
        if name not in expected:
            blockers.append({'path':name,'reason':'UNPINNED_PRESERVATION_MAP'})
            continue
        if any(b['path'] == name for b in blockers):
            continue
        data = json.loads((Path(root)/name).read_text(encoding='utf-8'))
        hashes = data.get('protected_hashes', data.get('protected_artifact_hashes'))
        if not isinstance(hashes, dict) or not hashes:
            blockers.append({'path':name,'reason':'PROTECTED_MAP_UNAVAILABLE'})
        else:
            blockers.extend(verify_bytes(root, hashes))
    blockers += [{'path':'historical_runtime', 'reason':'REVIEWED_SOURCE_DEPENDENCY_AND_EXECUTION_RECIPE_NOT_AVAILABLE'}]
    return {'lane':'historical', 'status':'BLOCKED',
            'registered_test_count':len(registration['historical_test_ids']),
            'attempted':False, 'validated':False, 'executed_test_count':0,
            'inference_requests':0, 'blockers':blockers,
            'meaning':'Prerequisite inspection only; no historical assertion executed or reproduction certified.'}
